//go:build fixture

// Command workflow-authority-fixture is offline test scaffolding for the
// black-box acceptance harness in tests/test_workflow_authority_integration.py.
//
// It exists only under the `fixture` build tag and is absent from every
// untagged build, including `go build ./...`. It ships in no artifact, is
// never installed, and holds no production code path: it composes the real
// ipc.Server, authority.Manager, provider.Dispatcher, and client.Runner
// through the sanctioned injected-root seams, mirroring the wiring in
// internal/client/integration_test.go.
//
// The production daemon cannot be pointed at a temporary root -- platform
// .NewLinux has no caller-controlled paths, platform.NewTestLinux is
// constructor-only, and client.NewProduction takes no paths -- so a black-box
// harness needs this launcher to obtain a daemon and client it can run as
// separate OS processes.
//
// Two modes:
//
//	-mode daemon  Build a fixture root, serve the broker on a Unix socket, and
//	              print one JSON line describing the environment, then block
//	              until SIGINT/SIGTERM.
//	-mode client  Dial a running fixture daemon, perform one dispatch, and
//	              print one JSON line describing the result.
//
// No instant in this file is a calendar literal. Every fixture time derives
// from the wall clock, optionally shifted by -clock-offset, because
// ipc.Server.handle applies the allocation's ExpiresAt as a real net.Conn
// deadline: a frozen date silently expires every fixture connection once that
// date passes.
package main

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/client"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/ipc"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

// Sentinels the harness plants and then hunts for. They are fixture-only
// strings; none is a real credential. REQ-E2E-07 and REQ-E2E-08 assert their
// absence from argv, environment, logs, receipts, and surviving artifacts,
// and the harness arms those scans with positive-control scenarios that plant
// each sentinel where the scanner must find it.
const (
	providerCredentialSentinel = "fixture-provider-credential"
	credentialIDSentinel       = "fixture-root-private-credential-id"
	responseSentinel           = "fixture assistant response"
)

type fixtureClock struct{ now time.Time }

func (c fixtureClock) Now() time.Time { return c.now }

// fixtureFIDO is the structural stand-in for a real authenticator. It performs
// no cryptography: Verify checks the challenge binding, credential identity,
// and presence/verification flags. Every claim this harness makes about real
// FIDO hardware is therefore a GAP, never a PASS.
type fixtureFIDO struct{ assertions, verifications atomic.Int32 }

func (*fixtureFIDO) Readiness(context.Context) authority.Readiness {
	return authority.Readiness{Production: false, Adapter: "fixture", Version: "fixture", InternalUV: true}
}

func (f *fixtureFIDO) Assert(_ context.Context, challenge []byte, credential authority.Credential) (authority.Assertion, error) {
	f.assertions.Add(1)
	authenticatorData := make([]byte, 37)
	binary.BigEndian.PutUint32(authenticatorData[33:], 1)
	return authority.Assertion{
		CredentialReference: credential.Reference,
		Generation:          credential.Generation,
		ChallengeDigest:     sha256.Sum256(challenge),
		Signature:           []byte("fixture-fido-signature"),
		AuthenticatorData:   authenticatorData,
		ClientDataJSON:      []byte(`{"type":"webauthn.get","origin":"fixture.invalid"}`),
		UserPresence:        true,
		UserVerification:    true,
		Counter:             1,
	}, nil
}

func (f *fixtureFIDO) Verify(_ context.Context, challenge []byte, credential authority.Credential, assertion authority.Assertion) error {
	f.verifications.Add(1)
	if assertion.ChallengeDigest != sha256.Sum256(challenge) || assertion.CredentialReference != credential.Reference ||
		assertion.Generation != credential.Generation || !assertion.UserPresence || !assertion.UserVerification || assertion.HostPINRequested {
		return authority.ErrDenied
	}
	return nil
}

func main() {
	mode := flag.String("mode", "", "daemon or client")
	root := flag.String("root", "", "absolute fixture root, created by the caller")
	clockOffset := flag.Duration("clock-offset", 0, "shift every fixture instant by this duration")
	// The in-process integration test shares one clock between daemon and
	// client. Across processes the harness reproduces that by reading the
	// daemon's instant from its ready line and handing it back here, so
	// freshness and terminal-result windows are evaluated against the same
	// value on both sides. This is a runtime value, never a literal.
	clockAt := flag.String("clock", "", "RFC3339 instant to use instead of the wall clock")

	socketPath := flag.String("socket", "", "client mode: broker socket path")
	trustPath := flag.String("trust", "", "client mode: public trust document path")
	repository := flag.String("repository", "design-machines/depot", "client mode: dispatch scope repository")
	runID := flag.String("run", "fixture-run", "client mode: dispatch scope run id")
	lane := flag.String("lane", "pipeline-assessment-artifact-delegation-v1", "client mode: dispatch scope lane")
	candidate := flag.String("candidate", "candidate-fixture", "client mode: dispatch scope candidate")
	workload := flag.String("workload", "pipeline-assessment", "client mode: dispatch scope workload")
	nonce := flag.String("nonce", "fixture-caller-nonce", "client mode: caller nonce")
	model := flag.String("model", "z-ai/glm-5.2", "client mode: primary model")
	fallbackModel := flag.String("fallback-model", "minimax/minimax-m2.5", "client mode: fallback model")
	system := flag.String("system", "system fixture", "client mode: system part")
	user := flag.String("user", "ordinary user fixture", "client mode: user part")
	repeat := flag.Int("repeat", 1, "client mode: dispatch attempts on one runner")
	flag.Parse()

	if *root == "" || !filepath.IsAbs(*root) {
		fail("fixture root must be an absolute path")
	}
	now := time.Now().UTC().Truncate(time.Second).Add(*clockOffset)
	if *clockAt != "" {
		parsed, err := time.Parse(time.RFC3339, *clockAt)
		if err != nil {
			fail("clock must be RFC3339: " + err.Error())
		}
		now = parsed.UTC()
	}

	switch *mode {
	case "daemon":
		if err := runDaemon(*root, now); err != nil {
			fail(err.Error())
		}
	case "client":
		options := client.DispatchOptions{
			Repository: *repository, RunID: *runID, Lane: *lane, Candidate: *candidate,
			Workload: *workload, Nonce: *nonce, Model: *model, FallbackModel: *fallbackModel,
		}
		if err := runClient(*root, *socketPath, *trustPath, now, options, *system, *user, *repeat); err != nil {
			fail(err.Error())
		}
	default:
		fail("mode must be daemon or client")
	}
}

func fail(reason string) {
	// Diagnostics go to stderr so stdout stays a single machine-readable line.
	fmt.Fprintln(os.Stderr, reason)
	os.Exit(1)
}

// emit writes exactly one JSON line to stdout, so the harness can read a
// single line and proceed without waiting for process exit. os.Stdout is
// unbuffered, and Sync is deliberately not called: on a pipe it fails with
// EBADF, which would turn a successful emit into a spurious error.
func emit(document any) error {
	raw, err := json.Marshal(document)
	if err != nil {
		return err
	}
	_, err = os.Stdout.Write(append(raw, '\n'))
	return err
}

func runDaemon(root string, now time.Time) error {
	owner := uint32(os.Geteuid())

	runDir := filepath.Join(root, "run")
	trustDir := filepath.Join(root, "trust")
	stateDir := filepath.Join(root, "state")
	for path, mode := range map[string]os.FileMode{runDir: 0o750, trustDir: 0o755, stateDir: 0o700} {
		if err := os.MkdirAll(path, mode); err != nil {
			return err
		}
		if err := os.Chmod(path, mode); err != nil {
			return err
		}
	}

	credentialID := []byte(credentialIDSentinel)
	credentialReference := enrollment.ReferenceForID(credentialID)
	credentialKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	publicDER, err := x509.MarshalPKIXPublicKey(&credentialKey.PublicKey)
	if err != nil {
		return err
	}
	generation := uint64(1)
	publicCredential := enrollment.PublicCredential{
		Generation: generation, Reference: credentialReference,
		PublicKey: base64.RawURLEncoding.EncodeToString(publicDER), Algorithm: enrollment.ES256,
		RPID: enrollment.RPID, EnrolledAt: now.Add(-time.Hour), InternalUV: true,
		AAGUID: base64.RawURLEncoding.EncodeToString(make([]byte, 16)), AttestationFormat: "packed",
	}
	trust := enrollment.PublicTrust{
		Protocol: enrollment.Protocol, ActiveGeneration: &generation,
		Credentials: []enrollment.PublicCredential{publicCredential},
		Events:      []enrollment.LifecycleEvent{{Sequence: 1, Generation: generation, Action: "activated", At: publicCredential.EnrolledAt}},
	}
	trustRaw, err := protocol.CanonicalJSON(trust)
	if err != nil {
		return err
	}
	trustPath := filepath.Join(trustDir, "authority-public.json")
	if err := os.WriteFile(trustPath, trustRaw, 0o644); err != nil {
		return err
	}

	policy := []byte(`{"schemaVersion":2,"disclosureControls":{"refuseClasses":["high-confidence credentials","private keys","authenticated connection strings / DSNs","access or session tokens","explicitly classified private or regulated values"],"onMatch":"decline-disclosure","exitCode":3}}`)
	providerCredentialPath := filepath.Join(root, "openrouter-credential")
	if err := os.WriteFile(providerCredentialPath, []byte(providerCredentialSentinel+"\n"), 0o600); err != nil {
		return err
	}

	var providerRequests atomic.Int32
	var providerRejections atomic.Int32
	providerServer := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		providerRequests.Add(1)
		if r.Method != protocol.Method || r.URL.Path != protocol.Path || r.Header.Get("Authorization") != "Bearer "+providerCredentialSentinel {
			providerRejections.Add(1)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil {
			providerRejections.Add(1)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id": "generation-fixture", "model": "z-ai/glm-5.2", "provider": "fixture-provider",
			"usage":   map[string]int{"total_tokens": 2},
			"choices": []any{map[string]any{"message": map[string]any{"role": "assistant", "content": responseSentinel}, "finish_reason": "stop"}},
		})
	}))
	defer providerServer.Close()

	// A second listener that nothing legitimate may ever reach. REQ-E2E-03
	// asserts env/flag overrides cannot redirect the broker: pointing an
	// override at this canary and observing zero connections is the
	// differential proof, where an unchanged outcome alone would not be.
	canary, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return err
	}
	defer canary.Close()
	var canaryHits atomic.Int32
	go func() {
		for {
			conn, err := canary.Accept()
			if err != nil {
				return
			}
			canaryHits.Add(1)
			_ = conn.Close()
		}
	}()

	store, err := ipc.OpenDirStateStore(stateDir, owner)
	if err != nil {
		return err
	}
	allocator, err := ipc.NewDurableAllocator(ipc.AllocatorConfig{
		DaemonBuildSHA256: protocol.Digest([]byte("fixture-daemon")), ScannerBuildSHA256: provider.ScannerBuildDigest,
		PolicySHA256: protocol.Digest(policy), BootID: "fixture-boot", SessionID: "fixture-session",
		Clock: func() time.Time { return now }, Random: strings.NewReader(strings.Repeat("r", 256)),
	}, store)
	if err != nil {
		return err
	}
	wal, err := authority.OpenDirWAL(stateDir, owner)
	if err != nil {
		return err
	}
	fido := &fixtureFIDO{}
	manager, err := authority.NewManager(authority.Config{
		BootID: "fixture-boot", SessionID: "fixture-session", AllowedUIDs: map[uint32]struct{}{owner: {}},
		MaxOperations: 8, MaxBytes: 16 << 20, MaxConcurrent: 1,
		Credential: authority.Credential{
			Reference: credentialReference, PublicKey: publicDER, Algorithm: enrollment.ES256, Generation: generation,
			RPID: enrollment.RPID, EnrolledAt: publicCredential.EnrolledAt, Status: "active", InternalUV: true,
			ID: append([]byte(nil), credentialID...),
		},
	}, fido, wal, fixtureClock{now: now})
	if err != nil {
		return err
	}
	dispatcher := &provider.Dispatcher{
		Scanner: provider.BuiltinScanner{}, Policy: policy,
		Credentials: provider.FileCredentialReader{Path: providerCredentialPath, FixtureMode: true, Owner: owner},
		Transport: &provider.Transport{
			Origin: providerServer.URL + protocol.Path, Fixture: true, Timeout: 5 * time.Second,
			TLSConfig: providerServer.Client().Transport.(*http.Transport).TLSClientConfig,
		},
		Authority: manager, Clock: func() time.Time { return now },
	}

	socketPath := filepath.Join(runDir, "authority.sock")
	listener, err := net.ListenUnix("unix", &net.UnixAddr{Name: socketPath, Net: "unix"})
	if err != nil {
		return err
	}
	if err := os.Chmod(socketPath, 0o660); err != nil {
		return err
	}
	// The peer is derived from the connection by the kernel, never injected and
	// never supplied by the caller. The client verifies that the daemon saw its
	// own PID (client.go asserts challenge.PeerPID == os.Getpid()), so a
	// fabricated peer identity here would make every authorization proof below
	// a statement about the fixture rather than about the broker.
	server := &ipc.Server{
		Allocator: allocator, Peers: fixturePeerAuthenticator(owner), Guard: fixtureGuardConn,
		Manager: manager, Dispatcher: dispatcher, Clock: func() time.Time { return now }, QueueDepth: 1,
	}

	// Plain-HTTP loopback control surface. It carries counters only -- never
	// response bytes, credential material, or receipts -- so observing it can
	// never itself become the leak REQ-E2E-07 is meant to detect.
	control, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return err
	}
	defer control.Close()
	controlMux := http.NewServeMux()
	controlMux.HandleFunc("/counters", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]int32{
			"provider_requests":   providerRequests.Load(),
			"provider_rejections": providerRejections.Load(),
			"fido_assertions":     fido.assertions.Load(),
			"fido_verifications":  fido.verifications.Load(),
			"canary_hits":         canaryHits.Load(),
		})
	})
	controlServer := &http.Server{Handler: controlMux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = controlServer.Serve(control) }()

	serveContext, cancelServe := context.WithCancel(context.Background())
	defer cancelServe()
	serveDone := make(chan error, 1)
	go func() { serveDone <- server.Serve(serveContext, listener) }()

	if err := emit(map[string]any{
		"ready":            true,
		"root":             root,
		"socket":           socketPath,
		"trust":            trustPath,
		"state":            stateDir,
		"policy_digest":    protocol.Digest(policy),
		"provider_origin":  providerServer.URL + protocol.Path,
		"provider_credential": providerCredentialPath,
		"control":          "http://" + control.Addr().String(),
		"canary":           canary.Addr().String(),
		"clock":            now.Format(time.RFC3339),
		"pid":              os.Getpid(),
		"peer_source":      peerSource,
		"production":       false,
	}); err != nil {
		return err
	}

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	select {
	case <-signals:
		cancelServe()
	case err := <-serveDone:
		return err
	}
	select {
	case err := <-serveDone:
		return err
	case <-time.After(5 * time.Second):
		return errors.New("fixture daemon did not shut down")
	}
}

func runClient(root, socketPath, trustPath string, now time.Time, options client.DispatchOptions, system, user string, repeat int) error {
	if socketPath == "" || trustPath == "" {
		return errors.New("client mode requires -socket and -trust")
	}
	if repeat < 1 {
		return errors.New("repeat must be at least 1")
	}
	runner := client.NewFixtureRunner(client.FixtureConfig{
		SocketPath: socketPath, TrustPath: trustPath, Anchor: root,
		ExpectedOwner: uint32(os.Geteuid()), Now: func() time.Time { return now }, FIDO: &fixtureFIDO{},
	})
	if runner == nil {
		return errors.New("fixture runner configuration incomplete")
	}

	attempts := make([]map[string]any, 0, repeat)
	for attempt := 0; attempt < repeat; attempt++ {
		result, err := runner.Dispatch(context.Background(), options,
			bytes.NewBufferString(system), bytes.NewBufferString(user))
		record := map[string]any{"attempt": attempt, "exit_code": result.ExitCode}
		if err != nil {
			// The error string is the terminal contract the harness asserts on
			// (host_authority_unavailable and friends). Response bytes are never
			// reported on a failed attempt.
			record["error"] = err.Error()
			record["ok"] = false
		} else {
			record["ok"] = true
			record["response"] = string(result.Response)
			record["receipt_b64"] = base64.StdEncoding.EncodeToString(result.Receipt)
			record["receipt_bytes"] = len(result.Receipt)
		}
		attempts = append(attempts, record)
	}
	return emit(map[string]any{"attempts": attempts})
}
