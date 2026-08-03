package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"designmachines.dev/workflow-authority/internal/client"
	"designmachines.dev/workflow-authority/internal/platform"
)

const (
	exitUsage       = 2
	exitAuthority   = 70
	exitDeclined    = 71
	exitDisclosure  = 72
	exitProvider    = 73
	exitUnknown     = 74
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

type providerClient interface {
	Dispatch(context.Context, client.DispatchOptions, io.Reader, io.Reader) (client.Result, error)
	Status(context.Context) ([]byte, error)
}

var openProviderClient = func() providerClient { return client.NewProduction() }

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) < 2 {
		return fail(stderr, "usage: workflow-authority <dispatch-provider-request|provider-transport-status|status>", exitUsage)
	}
	admin := filepath.Base(args[0]) == "workflow-authority-admin"
	command := args[1]
	if admin && (command == "provider-transport-status" || command == "dispatch-provider-request") {
		return fail(stderr, "provider commands require workflow-authority", exitUsage)
	}
	if (command == "status" || command == "provider-transport-status") && len(args) != 2 {
		return fail(stderr, "status accepts no options", exitUsage)
	}
	administrative := command == "enroll-fido" || command == "provision-openrouter" || command == "revoke-openrouter" || command == "disable" || command == "uninstall-plan"
	if administrative && !admin {
		return fail(stderr, "administrative command requires workflow-authority-admin", exitDeclined)
	}
	if administrative && len(args) != 2 {
		return fail(stderr, "administrative commands accept no options", exitUsage)
	}
	if command != "status" && command != "provider-transport-status" && command != "dispatch-provider-request" && !administrative {
		return fail(stderr, "unknown command", exitUsage)
	}
	if command == "provider-transport-status" || command == "dispatch-provider-request" {
		scrubProviderEnvironment()
		return runProvider(openProviderClient(), command, args[2:], stdout, stderr)
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
		return fail(stderr, "provider dispatch routing error", exitUsage)
	case "enroll-fido", "provision-openrouter", "revoke-openrouter", "disable", "uninstall-plan":
		return runAdmin(p, command, stdin, stdout, stderr)
	default:
		return fail(stderr, "unknown command", exitUsage)
	}
}

func runProvider(providerClient providerClient, command string, args []string, stdout, stderr io.Writer) int {
	if command == "provider-transport-status" {
		raw, err := providerClient.Status(context.Background())
		if err != nil {
			return fail(stderr, "host authority unavailable", exitAuthority)
		}
		if _, err := stdout.Write(append(raw, '\n')); err != nil {
			return fail(stderr, "status output failed", exitAuthority)
		}
		return 0
	}
	options, err := parseDispatch(args)
	if err != nil {
		return fail(stderr, "closed dispatch arguments violated", exitUsage)
	}
	fd3, fd4, fd5 := os.NewFile(3, "workflow-authority-response"), os.NewFile(4, "workflow-authority-system"), os.NewFile(5, "workflow-authority-user")
	if fd3 == nil || fd4 == nil || fd5 == nil {
		return fail(stderr, "fixed descriptor contract unavailable", exitUsage)
	}
	defer fd3.Close()
	defer fd4.Close()
	defer fd5.Close()
	if validateResponsePipe(fd3) != nil || validateInputFile(fd4) != nil || validateInputFile(fd5) != nil {
		return fail(stderr, "fixed descriptor contract violated", exitUsage)
	}
	result, dispatchErr := providerClient.Dispatch(context.Background(), options, fd4, fd5)
	if dispatchErr != nil {
		switch {
		case errors.Is(dispatchErr, client.ErrUsage):
			return fail(stderr, "invalid provider request", exitUsage)
		case errors.Is(dispatchErr, client.ErrDeclined):
			return fail(stderr, "authorization declined", exitDeclined)
		case errors.Is(dispatchErr, client.ErrDisclosure):
			return fail(stderr, "disclosure declined", exitDisclosure)
		case errors.Is(dispatchErr, client.ErrUnavailable):
			return fail(stderr, "host authority unavailable", exitAuthority)
		default:
			return fail(stderr, "provider result verification failed", exitUnknown)
		}
	}
	defer zero(result.Response)
	if result.ExitCode != 0 && result.ExitCode != exitProvider && result.ExitCode != exitUnknown {
		return fail(stderr, "invalid signed provider outcome", exitUnknown)
	}
	if _, err := stdout.Write(append(result.Receipt, '\n')); err != nil {
		return fail(stderr, "receipt output failed", exitUnknown)
	}
	if result.ExitCode == 0 {
		if err := writeAll(fd3, result.Response); err != nil {
			return fail(stderr, "response delivery failed", exitUnknown)
		}
	}
	return result.ExitCode
}

func parseDispatch(args []string) (client.DispatchOptions, error) {
	if len(args) != 20 && len(args) != 22 {
		return client.DispatchOptions{}, client.ErrUsage
	}
	values := map[string]string{}
	seen := map[string]struct{}{}
	allowed := map[string]struct{}{"--repository": {}, "--run-id": {}, "--lane": {}, "--candidate": {}, "--workload": {}, "--nonce": {}, "--model": {}, "--fallback-model": {}, "--system-fd": {}, "--user-fd": {}, "--response-fd": {}}
	for index := 0; index < len(args); index += 2 {
		key := args[index]
		if _, ok := allowed[key]; !ok || index+1 >= len(args) {
			return client.DispatchOptions{}, client.ErrUsage
		}
		if _, duplicate := seen[key]; duplicate {
			return client.DispatchOptions{}, client.ErrUsage
		}
		seen[key] = struct{}{}
		values[key] = args[index+1]
	}
	if values["--system-fd"] != "4" || values["--user-fd"] != "5" || values["--response-fd"] != "3" {
		return client.DispatchOptions{}, client.ErrUsage
	}
	options := client.DispatchOptions{Repository: values["--repository"], RunID: values["--run-id"], Lane: values["--lane"], Candidate: values["--candidate"], Workload: values["--workload"], Nonce: values["--nonce"], Model: values["--model"], FallbackModel: values["--fallback-model"]}
	for _, required := range []string{"--repository", "--run-id", "--lane", "--candidate", "--workload", "--nonce", "--model", "--system-fd", "--user-fd", "--response-fd"} {
		if _, ok := seen[required]; !ok || values[required] == "" {
			return client.DispatchOptions{}, client.ErrUsage
		}
	}
	if options.Repository == "" || options.RunID == "" || options.Lane == "" || options.Candidate == "" || options.Workload == "" || options.Nonce == "" || options.Model == "" {
		return client.DispatchOptions{}, client.ErrUsage
	}
	return options, nil
}

func scrubProviderEnvironment() {
	for _, name := range []string{"HOST_AUTHORITY_BROKER", "DM_VERIFICATION_SUBSTRATE", "OPENROUTER_API_KEY", "OPENROUTER_BASE", "OPENROUTER_ZDR", "OPENROUTER_PAYLOAD_AUTHORIZATION", "OPENROUTER_PAYLOAD_APPROVAL_SHA256", "OPENROUTER_AUTHORIZATION_MODE", "OPENROUTER_RECEIPT_FILE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"} {
		_ = os.Unsetenv(name)
	}
}

func writeAll(writer io.Writer, payload []byte) error {
	for len(payload) > 0 {
		n, err := writer.Write(payload)
		if err != nil || n < 1 || n > len(payload) {
			return io.ErrShortWrite
		}
		payload = payload[n:]
	}
	return nil
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

func zero(p []byte) {
	for i := range p {
		p[i] = 0
	}
}
