package client

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
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/ipc"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

type integrationClock struct{ now time.Time }

func (c integrationClock) Now() time.Time { return c.now }

type integrationFIDO struct{ assertions atomic.Int32 }

func (*integrationFIDO) Readiness(context.Context) authority.Readiness {
	return authority.Readiness{Production: false, Adapter: "fixture", Version: "fixture", InternalUV: true}
}

func (f *integrationFIDO) Assert(_ context.Context, challenge []byte, credential authority.Credential) (authority.Assertion, error) {
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

func (*integrationFIDO) Verify(_ context.Context, challenge []byte, credential authority.Credential, assertion authority.Assertion) error {
	if assertion.ChallengeDigest != sha256.Sum256(challenge) || assertion.CredentialReference != credential.Reference || assertion.Generation != credential.Generation || !assertion.UserPresence || !assertion.UserVerification || assertion.HostPINRequested {
		return authority.ErrDenied
	}
	return nil
}

type integrationPeer struct{ peer authority.Peer }

func (p integrationPeer) Authenticate(net.Conn) (authority.Peer, error) { return p.peer, nil }

type integrationGuard struct{ net.Conn }

func (c *integrationGuard) Receive(value []byte) (int, error) { return c.Read(value) }

func guardIntegrationConn(conn net.Conn) (ipc.GuardedConn, error) {
	if _, ok := conn.(*net.UnixConn); !ok {
		return nil, errors.New("fixture requires Unix connection")
	}
	return &integrationGuard{Conn: conn}, nil
}

func TestEndToEndUnixBrokerDispatchAndReplayRejection(t *testing.T) {
	root, err := os.MkdirTemp("/tmp", "wa-e2e-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(root) })
	now := time.Date(2026, 8, 4, 2, 0, 0, 0, time.UTC)
	owner := uint32(os.Geteuid())
	peer := authority.Peer{UID: owner, PID: int32(os.Getpid())}

	runDir := filepath.Join(root, "run")
	trustDir := filepath.Join(root, "trust")
	stateDir := filepath.Join(root, "state")
	for path, mode := range map[string]os.FileMode{runDir: 0o750, trustDir: 0o755, stateDir: 0o700} {
		if err := os.Mkdir(path, mode); err != nil {
			t.Fatal(err)
		}
	}

	credentialID := []byte("fixture-root-private-credential-id")
	credentialReference := enrollment.ReferenceForID(credentialID)
	credentialKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	publicDER, err := x509.MarshalPKIXPublicKey(&credentialKey.PublicKey)
	if err != nil {
		t.Fatal(err)
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
		t.Fatal(err)
	}
	trustPath := filepath.Join(trustDir, "authority-public.json")
	if err := os.WriteFile(trustPath, trustRaw, 0o644); err != nil {
		t.Fatal(err)
	}

	policy := []byte(`{"schemaVersion":2,"disclosureControls":{"refuseClasses":["high-confidence credentials","private keys","authenticated connection strings / DSNs","access or session tokens","explicitly classified private or regulated values"],"onMatch":"decline-disclosure","exitCode":3}}`)
	providerCredentialPath := filepath.Join(root, "openrouter-credential")
	if err := os.WriteFile(providerCredentialPath, []byte("fixture-provider-credential\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	var providerRequests atomic.Int32
	providerServer := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		providerRequests.Add(1)
		if r.Method != protocol.Method || r.URL.Path != protocol.Path || r.Header.Get("Authorization") != "Bearer fixture-provider-credential" {
			t.Errorf("unexpected provider request: method=%s path=%s", r.Method, r.URL.Path)
		}
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil {
			t.Error("provider body was not JSON")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"id": "generation-fixture", "model": "z-ai/glm-5.2", "provider": "fixture-provider",
			"usage":   map[string]int{"total_tokens": 2},
			"choices": []any{map[string]any{"message": map[string]any{"role": "assistant", "content": "fixture assistant response"}, "finish_reason": "stop"}},
		})
	}))
	defer providerServer.Close()

	store, err := ipc.OpenDirStateStore(stateDir, owner)
	if err != nil {
		t.Fatal(err)
	}
	allocator, err := ipc.NewDurableAllocator(ipc.AllocatorConfig{
		DaemonBuildSHA256: protocol.Digest([]byte("fixture-daemon")), ScannerBuildSHA256: provider.ScannerBuildDigest,
		PolicySHA256: protocol.Digest(policy), BootID: "fixture-boot", SessionID: "fixture-session",
		Clock: func() time.Time { return now }, Random: strings.NewReader(strings.Repeat("r", 256)),
	}, store)
	if err != nil {
		t.Fatal(err)
	}
	wal, err := authority.OpenDirWAL(stateDir, owner)
	if err != nil {
		t.Fatal(err)
	}
	fido := &integrationFIDO{}
	manager, err := authority.NewManager(authority.Config{
		BootID: "fixture-boot", SessionID: "fixture-session", AllowedUIDs: map[uint32]struct{}{owner: {}},
		MaxOperations: 8, MaxBytes: 16 << 20, MaxConcurrent: 1,
		Credential: authority.Credential{
			Reference: credentialReference, PublicKey: publicDER, Algorithm: enrollment.ES256, Generation: generation,
			RPID: enrollment.RPID, EnrolledAt: publicCredential.EnrolledAt, Status: "active", InternalUV: true,
			ID: append([]byte(nil), credentialID...),
		},
	}, fido, wal, integrationClock{now: now})
	if err != nil {
		t.Fatal(err)
	}
	dispatcher := &provider.Dispatcher{
		Scanner: provider.BuiltinScanner{}, Policy: policy,
		Credentials: provider.FileCredentialReader{Path: providerCredentialPath, FixtureMode: true, Owner: owner},
		Transport: &provider.Transport{
			Origin: providerServer.URL + protocol.Path, Fixture: true, Timeout: time.Second,
			TLSConfig: providerServer.Client().Transport.(*http.Transport).TLSClientConfig,
		},
		Authority: manager, Clock: func() time.Time { return now },
	}

	socketPath := filepath.Join(runDir, "authority.sock")
	listener, err := net.ListenUnix("unix", &net.UnixAddr{Name: socketPath, Net: "unix"})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(socketPath, 0o660); err != nil {
		t.Fatal(err)
	}
	server := &ipc.Server{
		Allocator: allocator, Peers: integrationPeer{peer: peer}, Guard: guardIntegrationConn,
		Manager: manager, Dispatcher: dispatcher, Clock: func() time.Time { return now }, QueueDepth: 1,
	}
	serveContext, cancelServe := context.WithCancel(context.Background())
	serveDone := make(chan error, 1)
	go func() { serveDone <- server.Serve(serveContext, listener) }()

	runner := &Runner{
		socketPath: socketPath, trustPath: trustPath, socketAnchor: root, trustAnchor: root,
		expectedOwner: owner, now: func() time.Time { return now }, fido: fido,
		confirm: func(context.Context, protocol.Challenge) error { return nil },
	}
	runner.dial = func(ctx context.Context, path string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", path)
	}

	options := DispatchOptions{
		Repository: "design-machines/depot", RunID: "fixture-run", Lane: "pipeline-assessment-artifact-delegation-v1",
		Candidate: "candidate-fixture", Workload: "pipeline-assessment", Nonce: "fixture-caller-nonce",
		Model: "z-ai/glm-5.2", FallbackModel: "minimax/minimax-m2.5",
	}
	result, err := runner.Dispatch(context.Background(), options, bytes.NewBufferString("system fixture"), bytes.NewBufferString("ordinary user fixture"))
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 || string(result.Response) != "fixture assistant response" || len(result.Receipt) == 0 {
		t.Fatalf("unexpected result: exit=%d response=%q receipt=%d", result.ExitCode, result.Response, len(result.Receipt))
	}
	if providerRequests.Load() != 1 || fido.assertions.Load() != 1 {
		t.Fatalf("requests=%d assertions=%d", providerRequests.Load(), fido.assertions.Load())
	}
	if _, err := runner.Dispatch(context.Background(), options, bytes.NewBufferString("system fixture"), bytes.NewBufferString("ordinary user fixture")); err == nil {
		t.Fatal("replayed caller nonce unexpectedly succeeded")
	}
	if providerRequests.Load() != 1 {
		t.Fatal("replay contacted provider")
	}

	cancelServe()
	select {
	case err := <-serveDone:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("server did not shut down")
	}
	for _, secret := range [][]byte{credentialID, []byte("fixture-provider-credential"), []byte("fixture assistant response")} {
		if bytes.Contains(result.Receipt, secret) {
			t.Fatal("content-free receipt leaked authority/provider material")
		}
	}
	if _, err := io.Copy(io.Discard, bytes.NewReader(result.Response)); err != nil {
		t.Fatal(err)
	}
}
