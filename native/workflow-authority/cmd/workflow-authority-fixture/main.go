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
	// Holds the fixture provider's response open so the harness can act while a
	// dispatch is genuinely in flight: kill the client, open a competing
	// connection, or race a second request. Without it those cases resolve
	// faster than the harness can observe them and the assertions become
	// timing-dependent rather than deterministic.
	providerDelay := flag.Duration("provider-delay", 0, "daemon mode: hold the fixture provider response open")

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
		if err := runDaemon(*root, now, *providerDelay); err != nil {
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

// fixtureDirs are the three fixture root subdirectories, created with the same
// modes the production layout uses.
type fixtureDirs struct{ run, trust, state string }

func prepareFixtureDirs(root string) (fixtureDirs, error) {
	dirs := fixtureDirs{
		run:   filepath.Join(root, "run"),
		trust: filepath.Join(root, "trust"),
		state: filepath.Join(root, "state"),
	}
	for path, mode := range map[string]os.FileMode{dirs.run: 0o750, dirs.trust: 0o755, dirs.state: 0o700} {
		if err := os.MkdirAll(path, mode); err != nil {
			return fixtureDirs{}, err
		}
		if err := os.Chmod(path, mode); err != nil {
			return fixtureDirs{}, err
		}
	}
	return dirs, nil
}

// fixtureIdentity is the enrolled credential the daemon publishes as public
// trust and hands to the authority manager. credentialID is the
// credentialIDSentinel: only its derived reference appears in the trust
// document, and REQ-E2E-07/08 assert the raw ID reaches no artifact at all.
type fixtureIdentity struct {
	credentialID        []byte
	credentialReference string
	publicDER           []byte
	generation          uint64
	enrolledAt          time.Time
	trustPath           string
}

func writeFixtureTrust(trustDir string, now time.Time) (fixtureIdentity, error) {
	credentialID := []byte(credentialIDSentinel)
	credentialReference := enrollment.ReferenceForID(credentialID)
	credentialKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return fixtureIdentity{}, err
	}
	publicDER, err := x509.MarshalPKIXPublicKey(&credentialKey.PublicKey)
	if err != nil {
		return fixtureIdentity{}, err
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
		return fixtureIdentity{}, err
	}
	trustPath := filepath.Join(trustDir, "authority-public.json")
	if err := os.WriteFile(trustPath, trustRaw, 0o644); err != nil {
		return fixtureIdentity{}, err
	}
	return fixtureIdentity{
		credentialID: credentialID, credentialReference: credentialReference,
		publicDER: publicDER, generation: generation,
		enrolledAt: publicCredential.EnrolledAt, trustPath: trustPath,
	}, nil
}

// fixtureProvider owns the loopback TLS provider the dispatcher talks to, its
// request counters, and the canary listener nothing legitimate may ever reach.
type fixtureProvider struct {
	server         *httptest.Server
	credentialPath string
	requests       atomic.Int32
	rejections     atomic.Int32
	canary         net.Listener
	canaryHits     atomic.Int32
}

func newFixtureProvider(root string, delay time.Duration) (*fixtureProvider, error) {
	p := &fixtureProvider{credentialPath: filepath.Join(root, "openrouter-credential")}
	if err := os.WriteFile(p.credentialPath, []byte(providerCredentialSentinel+"\n"), 0o600); err != nil {
		return nil, err
	}
	p.server = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p.requests.Add(1)
		if delay > 0 {
			// Counted before sleeping, so a request that is in flight is
			// already visible to the harness through /counters.
			time.Sleep(delay)
		}
		if r.Method != protocol.Method || r.URL.Path != protocol.Path || r.Header.Get("Authorization") != "Bearer "+providerCredentialSentinel {
			p.rejections.Add(1)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil {
			p.rejections.Add(1)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id": "generation-fixture", "model": "z-ai/glm-5.2", "provider": "fixture-provider",
			"usage":   map[string]int{"total_tokens": 2},
			"choices": []any{map[string]any{"message": map[string]any{"role": "assistant", "content": responseSentinel}, "finish_reason": "stop"}},
		})
	}))
	// A second listener that nothing legitimate may ever reach. REQ-E2E-03
	// asserts env/flag overrides cannot redirect the broker: pointing an
	// override at this canary and observing zero connections is the
	// differential proof, where an unchanged outcome alone would not be.
	canary, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		p.server.Close()
		return nil, err
	}
	p.canary = canary
	go func() {
		for {
			conn, err := canary.Accept()
			if err != nil {
				return
			}
			p.canaryHits.Add(1)
			_ = conn.Close()
		}
	}()
	return p, nil
}

func (p *fixtureProvider) origin() string { return p.server.URL + protocol.Path }

func (p *fixtureProvider) close() {
	p.server.Close()
	_ = p.canary.Close()
}

// newFixtureBroker wires the durable allocator, WAL, authority manager,
// dispatcher, and IPC server that sit behind the fixture socket.
//
// The peer is derived from the connection by the kernel, never injected and
// never supplied by the caller. The client verifies that the daemon saw its own
// PID (client.go asserts challenge.PeerPID == os.Getpid()), so a fabricated
// peer identity here would make every authorization proof the harness collects
// a statement about the fixture rather than about the broker.
func newFixtureBroker(dirs fixtureDirs, identity fixtureIdentity, policy []byte,
	owner uint32, now time.Time, prov *fixtureProvider) (*ipc.Server, *fixtureFIDO, error) {
	store, err := ipc.OpenDirStateStore(dirs.state, owner)
	if err != nil {
		return nil, nil, err
	}
	allocator, err := ipc.NewDurableAllocator(ipc.AllocatorConfig{
		DaemonBuildSHA256: protocol.Digest([]byte("fixture-daemon")), ScannerBuildSHA256: provider.ScannerBuildDigest,
		PolicySHA256: protocol.Digest(policy), BootID: "fixture-boot", SessionID: "fixture-session",
		Clock: func() time.Time { return now }, Random: strings.NewReader(strings.Repeat("r", 256)),
	}, store)
	if err != nil {
		return nil, nil, err
	}
	wal, err := authority.OpenDirWAL(dirs.state, owner)
	if err != nil {
		return nil, nil, err
	}
	fido := &fixtureFIDO{}
	manager, err := authority.NewManager(authority.Config{
		BootID: "fixture-boot", SessionID: "fixture-session", AllowedUIDs: map[uint32]struct{}{owner: {}},
		MaxOperations: 8, MaxBytes: 16 << 20, MaxConcurrent: 1,
		Credential: authority.Credential{
			Reference: identity.credentialReference, PublicKey: identity.publicDER,
			Algorithm: enrollment.ES256, Generation: identity.generation,
			RPID: enrollment.RPID, EnrolledAt: identity.enrolledAt, Status: "active", InternalUV: true,
			ID: append([]byte(nil), identity.credentialID...),
		},
	}, fido, wal, fixtureClock{now: now})
	if err != nil {
		return nil, nil, err
	}
	dispatcher := &provider.Dispatcher{
		Scanner: provider.BuiltinScanner{}, Policy: policy,
		Credentials: provider.FileCredentialReader{Path: prov.credentialPath, FixtureMode: true, Owner: owner},
		Transport: &provider.Transport{
			Origin: prov.origin(), Fixture: true, Timeout: 5 * time.Second,
			TLSConfig: prov.server.Client().Transport.(*http.Transport).TLSClientConfig,
		},
		Authority: manager, Clock: func() time.Time { return now },
	}
	return &ipc.Server{
		Allocator: allocator, Peers: fixturePeerAuthenticator(owner), Guard: fixtureGuardConn,
		Manager: manager, Dispatcher: dispatcher, Clock: func() time.Time { return now }, QueueDepth: 1,
	}, fido, nil
}

// listenFixtureSocket opens the broker's Unix socket inside the fixture run dir.
func listenFixtureSocket(runDir string) (*net.UnixListener, string, error) {
	socketPath := filepath.Join(runDir, "authority.sock")
	listener, err := net.ListenUnix("unix", &net.UnixAddr{Name: socketPath, Net: "unix"})
	if err != nil {
		return nil, "", err
	}
	if err := os.Chmod(socketPath, 0o660); err != nil {
		_ = listener.Close()
		return nil, "", err
	}
	return listener, socketPath, nil
}

// serveFixtureCounters starts the plain-HTTP loopback control surface. It
// carries counters only -- never response bytes, credential material, or
// receipts -- so observing it can never itself become the leak REQ-E2E-07 is
// meant to detect.
func serveFixtureCounters(prov *fixtureProvider, fido *fixtureFIDO) (net.Listener, error) {
	control, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/counters", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]int32{
			"provider_requests":   prov.requests.Load(),
			"provider_rejections": prov.rejections.Load(),
			"fido_assertions":     fido.assertions.Load(),
			"fido_verifications":  fido.verifications.Load(),
			"canary_hits":         prov.canaryHits.Load(),
		})
	})
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = server.Serve(control) }()
	return control, nil
}

func runDaemon(root string, now time.Time, providerDelay time.Duration) error {
	owner := uint32(os.Geteuid())

	dirs, err := prepareFixtureDirs(root)
	if err != nil {
		return err
	}
	identity, err := writeFixtureTrust(dirs.trust, now)
	if err != nil {
		return err
	}
	policy := []byte(`{"schemaVersion":2,"disclosureControls":{"refuseClasses":["high-confidence credentials","private keys","authenticated connection strings / DSNs","access or session tokens","explicitly classified private or regulated values"],"onMatch":"decline-disclosure","exitCode":3}}`)

	prov, err := newFixtureProvider(root, providerDelay)
	if err != nil {
		return err
	}
	defer prov.close()

	server, fido, err := newFixtureBroker(dirs, identity, policy, owner, now, prov)
	if err != nil {
		return err
	}
	listener, socketPath, err := listenFixtureSocket(dirs.run)
	if err != nil {
		return err
	}
	control, err := serveFixtureCounters(prov, fido)
	if err != nil {
		return err
	}
	defer control.Close()

	serveContext, cancelServe := context.WithCancel(context.Background())
	defer cancelServe()
	serveDone := make(chan error, 1)
	go func() { serveDone <- server.Serve(serveContext, listener) }()

	if err := emit(map[string]any{
		"ready":               true,
		"root":                root,
		"socket":              socketPath,
		"trust":               identity.trustPath,
		"state":               dirs.state,
		"policy_digest":       protocol.Digest(policy),
		"provider_origin":     prov.origin(),
		"provider_credential": prov.credentialPath,
		"control":             "http://" + control.Addr().String(),
		"canary":              prov.canary.Addr().String(),
		"clock":               now.Format(time.RFC3339),
		"pid":                 os.Getpid(),
		"peer_source":         peerSource,
		"production":          false,
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
