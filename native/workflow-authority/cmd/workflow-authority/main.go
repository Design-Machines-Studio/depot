package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/platform"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

const (
	exitUsage       = 2
	exitDeclined    = 71
	exitUnavailable = 76
)

func main() { os.Exit(run(os.Args, os.Stdin, os.Stdout, os.Stderr)) }

type localPlatform interface {
	StatusJSON() ([]byte, error)
	RequireRoot() error
	ProvisionOpenRouter([]byte) error
	RevokeOpenRouter() error
	Disable() error
	UninstallPlan() ([]string, error)
}

type adminTerminal interface {
	Stable() error
	MatchesInput(io.Reader) error
	ReadSecret(string) ([]byte, error)
	Close() error
}

var openLinuxPlatform = func() (localPlatform, error) { return platform.NewLinux() }
var openAdminTerminal = func() (adminTerminal, error) { return platform.OpenTerminal() }

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) < 2 {
		return fail(stderr, "usage: workflow-authority <dispatch-provider-request|status>", exitUsage)
	}
	admin := filepath.Base(args[0]) == "workflow-authority-admin"
	command := args[1]
	if command == "dispatch-provider-request" && (admin || len(args) != 2) {
		return fail(stderr, "dispatch-provider-request accepts no options", exitUsage)
	}
	if command == "status" && len(args) != 2 {
		return fail(stderr, "status accepts no options", exitUsage)
	}
	administrative := command == "enroll-fido" || command == "provision-openrouter" || command == "revoke-openrouter" || command == "disable" || command == "uninstall-plan"
	if administrative && !admin {
		return fail(stderr, "administrative command requires workflow-authority-admin", exitDeclined)
	}
	if administrative && len(args) != 2 {
		return fail(stderr, "administrative commands accept no options", exitUsage)
	}
	if command != "status" && command != "dispatch-provider-request" && !administrative {
		return fail(stderr, "unknown command", exitUsage)
	}
	p, err := openLinuxPlatform()
	if err != nil {
		return fail(stderr, "workflow authority is unavailable on this host", exitUnavailable)
	}
	switch command {
	case "status":
		raw, err := p.StatusJSON()
		if err != nil {
			return fail(stderr, "status unavailable", exitUnavailable)
		}
		if _, err = stdout.Write(append(raw, '\n')); err != nil {
			return fail(stderr, "status output failed", exitUnavailable)
		}
		return 0
	case "dispatch-provider-request":
		if err := dispatch(stdin, stdout); err != nil {
			return fail(stderr, "provider dispatch failed closed", exitUnavailable)
		}
		return 0
	case "enroll-fido", "provision-openrouter", "revoke-openrouter", "disable", "uninstall-plan":
		return runAdmin(p, command, stdin, stdout, stderr)
	default:
		return fail(stderr, "unknown command", exitUsage)
	}
}

func runAdmin(p localPlatform, command string, stdin io.Reader, stdout, stderr io.Writer) int {
	if err := p.RequireRoot(); err != nil {
		return fail(stderr, "administrative command requires effective uid 0", exitDeclined)
	}
	terminal, err := openAdminTerminal()
	if err != nil {
		return fail(stderr, "administrative command requires a stable controlling /dev/tty", exitDeclined)
	}
	defer terminal.Close()
	if err := terminal.MatchesInput(stdin); err != nil {
		return fail(stderr, "administrative command requires stdin from the controlling terminal", exitDeclined)
	}
	if err := terminal.Stable(); err != nil {
		return fail(stderr, "controlling terminal changed", exitDeclined)
	}
	switch command {
	case "enroll-fido":
		// Enrollment creation is intentionally unavailable until the daemon exposes
		// a root-only ceremony endpoint backed by the production libfido2 adapter.
		return fail(stderr, "FIDO enrollment endpoint unavailable; recovery: leave service disabled and install the composed daemon", exitUnavailable)
	case "provision-openrouter":
		secret, err := terminal.ReadSecret("OpenRouter credential: ")
		if err != nil {
			return fail(stderr, "credential input unavailable", exitDeclined)
		}
		defer zero(secret)
		if len(secret) == 0 {
			return fail(stderr, "empty credential rejected", exitDeclined)
		}
		if err := terminal.Stable(); err != nil {
			return fail(stderr, "controlling terminal changed; credential was not provisioned", exitDeclined)
		}
		if err := p.ProvisionOpenRouter(secret); err != nil {
			return fail(stderr, err.Error(), exitUnavailable)
		}
		if terminal.Stable() != nil {
			return fail(stderr, "controlling terminal changed; provisioning may have completed, run status before recovery", exitUnavailable)
		}
		return contentFree(stdout, stderr, "provisioned")
	case "revoke-openrouter":
		if err := p.RevokeOpenRouter(); err != nil {
			return fail(stderr, err.Error(), exitUnavailable)
		}
		if terminal.Stable() != nil {
			return fail(stderr, "controlling terminal changed; revocation may have completed, run status before recovery", exitUnavailable)
		}
		return contentFree(stdout, stderr, "revoked")
	case "disable":
		if err := p.Disable(); err != nil {
			return fail(stderr, err.Error(), exitUnavailable)
		}
		if terminal.Stable() != nil {
			return fail(stderr, "controlling terminal changed; disable may have completed, inspect service state before recovery", exitUnavailable)
		}
		return contentFree(stdout, stderr, "disabled")
	case "uninstall-plan":
		plan, err := p.UninstallPlan()
		if err != nil {
			return fail(stderr, "uninstall plan unavailable", exitUnavailable)
		}
		for _, step := range plan {
			if terminal.Stable() != nil {
				return fail(stderr, "controlling terminal changed; uninstall plan aborted", exitDeclined)
			}
			if _, err := fmt.Fprintln(stdout, step); err != nil {
				return fail(stderr, "uninstall plan output failed", exitUnavailable)
			}
		}
		return 0
	}
	return exitUsage
}

func contentFree(w, stderr io.Writer, state string) int {
	raw, err := json.Marshal(map[string]any{"schema_version": 1, "protocol": "workflow-authority-admin-result-v1", "state": state})
	if err != nil {
		return fail(stderr, "administrative result unavailable", exitUnavailable)
	}
	if _, err := w.Write(append(raw, '\n')); err != nil {
		return fail(stderr, "administrative result output failed", exitUnavailable)
	}
	return 0
}
func fail(w io.Writer, message string, code int) int { _, _ = fmt.Fprintln(w, message); return code }

// dispatch owns one fixed connection. It validates and buffers before fd 3;
// because the current daemon has no accept loop/trust-chain endpoint, every
// reachable production attempt fails closed before response release.
func dispatch(stdin io.Reader, stdout io.Writer) error {
	fd3 := os.NewFile(3, "workflow-authority-response")
	if fd3 == nil {
		return errors.New("fd3 unavailable")
	}
	defer fd3.Close()
	if err := validateResponsePipe(fd3); err != nil {
		return err
	}
	wire, err := io.ReadAll(io.LimitReader(stdin, 8_388_609))
	if err != nil || len(wire) > 8_388_608 {
		return protocol.ErrFrameTooLarge
	}
	reader := bytes.NewReader(wire)
	request, parts, err := protocol.ReadRequestExchange(reader, time.Now().UTC())
	if err != nil {
		return err
	}
	if reader.Len() != 0 {
		return protocol.ErrTrailingData
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	dialer := net.Dialer{Timeout: 5 * time.Second}
	conn, err := dialer.DialContext(ctx, "unix", platform.SocketPath)
	if err != nil {
		return err
	}
	defer conn.Close()
	if _, err = conn.Write(wire); err != nil {
		return err
	}
	challengeRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return err
	}
	var challenge protocol.Challenge
	if err = protocol.DecodeClosed(challengeRaw, &challenge); err != nil {
		return err
	}
	body, err := provider.BuildBody(request, parts)
	if err != nil || protocol.Digest(body) != challenge.RequestBodySHA256 {
		zero(body)
		return errors.New("terminal_binding_invalid")
	}
	zero(body)
	if err = validateChallenge(request, challenge); err != nil {
		return err
	}
	terminal, err := authority.OpenControllingTerminal()
	if err != nil {
		return err
	}
	defer terminal.Close()
	if err = authority.ConfirmExactScope(terminal, challenge); err != nil {
		return err
	}
	ack, _ := protocol.CanonicalJSON(map[string]any{"challenge_sha256": protocol.Digest(challengeRaw), "protocol": protocol.Name, "schema_version": 1, "type": "consent_ack"})
	if err = protocol.WriteFrame(conn, ack); err != nil {
		return err
	}
	// Trust-chain verification and terminal projection are intentionally not
	// guessed here. No byte is written to fd 3 or stdout without that verifier.
	return errors.New("production trust-chain verifier unavailable")
}

func validateChallenge(r protocol.Request, c protocol.Challenge) error {
	a := r.Authority
	if c.SchemaVersion != 1 || c.Protocol != protocol.Name || c.Mapping != r.Mapping || c.OperationFamily != r.OperationFamily || c.SubstrateAuthority != r.SubstrateAuthority || c.Destination != r.Destination || c.Method != r.Method || c.Path != r.Path || c.Scope != r.Scope || c.ConnectionNonceSHA256 != a.ConnectionNonceSHA256 || c.DaemonBuildSHA256 != a.DaemonBuildSHA256 || c.ScannerBuildSHA256 != a.ScannerBuildSHA256 || c.PolicySHA256 != a.PolicySHA256 || c.Nonce != a.Nonce || c.Sequence != a.Sequence || c.BootID != a.BootID || c.SessionID != a.SessionID || c.IssuedAt != a.IssuedAt || c.ExpiresAt != a.ExpiresAt || c.PriorChainDigest != a.PriorChainDigest || c.AuthorityAssertion != nil || c.PeerUID != uint32(os.Geteuid()) || c.PeerPID != int32(os.Getpid()) || !same(c.Models, r.Models) {
		return errors.New("terminal_binding_invalid")
	}
	return nil
}
func same(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
func zero(p []byte) {
	for i := range p {
		p[i] = 0
	}
}

// Kept here to freeze the response framing limit for the future verifier.
func readResponse(r io.Reader, limit uint64) ([]byte, error) {
	var h [8]byte
	if _, e := io.ReadFull(r, h[:]); e != nil {
		return nil, e
	}
	n := binary.BigEndian.Uint64(h[:])
	if n > limit {
		return nil, protocol.ErrFrameTooLarge
	}
	p := make([]byte, n)
	_, e := io.ReadFull(r, p)
	return p, e
}
