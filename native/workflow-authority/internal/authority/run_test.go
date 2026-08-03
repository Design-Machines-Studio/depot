package authority

import (
	"context"
	"crypto/sha256"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

type fakeClock struct{ now time.Time }

func (c *fakeClock) Now() time.Time { return c.now }

type memoryWAL struct {
	mu      sync.Mutex
	events  []Event
	failAt  int
	appends int
}

func (w *memoryWAL) Append(_ context.Context, event Event) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.appends++
	if w.failAt == w.appends {
		return ErrDurability
	}
	w.events = append(w.events, event)
	return nil
}
func (w *memoryWAL) Events(context.Context) ([]Event, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	return append([]Event(nil), w.events...), nil
}
func (*memoryWAL) Close() error { return nil }

type fakeFIDO struct {
	mutate func(*Assertion)
	seen   []byte
	err    error
}

func (*fakeFIDO) Readiness(context.Context) Readiness {
	return Readiness{Production: false, Adapter: "fake", Version: "test", InternalUV: true}
}
func (f *fakeFIDO) Assert(_ context.Context, challenge []byte, credential Credential) (Assertion, error) {
	f.seen = append([]byte(nil), challenge...)
	if f.err != nil {
		return Assertion{}, f.err
	}
	digest := sha256.Sum256(challenge)
	a := Assertion{CredentialReference: credential.Reference, Generation: credential.Generation, ChallengeDigest: digest, Signature: []byte("public-test-signature"), AuthenticatorData: []byte("public-test-authdata"), UserPresence: true, UserVerification: true, Counter: 1}
	if f.mutate != nil {
		f.mutate(&a)
	}
	return a, nil
}
func (*fakeFIDO) Verify(_ context.Context, challenge []byte, credential Credential, assertion Assertion) error {
	digest := sha256.Sum256(challenge)
	if digest != assertion.ChallengeDigest || assertion.Generation != credential.Generation {
		return ErrDenied
	}
	return nil
}

func fixture(t *testing.T) (protocol.Request, protocol.Challenge, Config, *fakeClock) {
	t.Helper()
	now := time.Date(2026, 8, 3, 0, 0, 0, 0, time.UTC)
	d := protocol.Digest([]byte("body"))
	limits := protocol.Limits{MaxRequestBytes: 8388608, MaxResponseBytes: 8388608, MaxParts: 256, MaxPendingPerPeer: 4, MaxPendingRepository: 16, MaxPendingDaemon: 64}
	scope := protocol.Scope{Repository: "design-machines/depot", RunID: "run-01", Lane: "assessment", Candidate: "candidate-01", Workload: "pipeline-assessment"}
	authority := protocol.Authority{DaemonBuildSHA256: d, ScannerBuildSHA256: d, PolicySHA256: d, Nonce: "nonce-01", Sequence: 7, BootID: "boot-01", SessionID: "session-01", ConnectionNonceSHA256: d, IssuedAt: now.Format(time.RFC3339), ExpiresAt: now.Add(2 * time.Minute).Format(time.RFC3339), PriorChainDigest: d}
	r := protocol.Request{SchemaVersion: 1, Protocol: protocol.Name, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: []string{"openai/gpt-5.6", "z-ai/glm-5.2"}, Parts: []protocol.Part{{Role: "user", ContentLength: 5, ContentSHA256: d}}, Scope: scope, Authority: authority, Limits: limits}
	c := protocol.Challenge{SchemaVersion: 1, Protocol: protocol.Name, Mapping: protocol.Mapping, OperationFamily: r.OperationFamily, SubstrateAuthority: r.SubstrateAuthority, TransactionID: "transaction-01", ConnectionNonceSHA256: authority.ConnectionNonceSHA256, PeerUID: 501, PeerPID: 4321, RequestBodySHA256: d, Destination: r.Destination, Method: r.Method, Path: r.Path, Models: append([]string(nil), r.Models...), Scope: scope, DaemonBuildSHA256: d, ScannerBuildSHA256: d, PolicySHA256: d, Nonce: authority.Nonce, Sequence: authority.Sequence, BootID: authority.BootID, SessionID: authority.SessionID, IssuedAt: authority.IssuedAt, ExpiresAt: authority.ExpiresAt, Limits: limits, PriorChainDigest: d}
	config := Config{BootID: "boot-01", SessionID: "session-01", AllowedUIDs: map[uint32]struct{}{501: {}}, MaxOperations: 2, MaxBytes: 16 << 20, MaxConcurrent: 2, Credential: Credential{Reference: "credential-generation-1", PublicKey: []byte("public-only"), Algorithm: -7, Generation: 1, RPID: "workflow-authority.designmachines.local", EnrolledAt: now, Status: "active", InternalUV: true}}
	return r, c, config, &fakeClock{now: now}
}

func reserve(t *testing.T, fido *fakeFIDO, wal *memoryWAL) (*Manager, protocol.Challenge, Peer, *fakeClock) {
	t.Helper()
	request, challenge, config, clock := fixture(t)
	manager, err := NewManager(config, fido, wal, clock)
	if err != nil {
		t.Fatal(err)
	}
	peer := Peer{UID: 501, PID: 4321}
	challenge, err = manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "connection-01")
	if err != nil {
		t.Fatal(err)
	}
	return manager, challenge, peer, clock
}

func TestExactRequestLifecycleAndFsyncLinearization(t *testing.T) {
	wal := &memoryWAL{}
	fido := &fakeFIDO{}
	manager, challenge, peer, _ := reserve(t, fido, wal)
	bytes, _ := protocol.CanonicalJSON(challenge)
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(bytes)); err != nil {
		t.Fatal(err)
	}
	if len(fido.seen) == 0 {
		t.Fatal("FIDO did not receive exact challenge input")
	}
	right, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer)
	if err != nil {
		t.Fatal(err)
	}
	if signature, err := manager.SignTerminal(right, []byte("terminal-input")); err != nil || len(signature) == 0 {
		t.Fatalf("terminal signature unavailable: %v", err)
	}
	if got := wal.events[len(wal.events)-1].State; got != SendStarted {
		t.Fatalf("send right escaped before durable marker: %s", got)
	}
	if err := manager.Complete(context.Background(), challenge.TransactionID, 64, "verified"); err != nil {
		t.Fatal(err)
	}
	if err := manager.Cleanup(context.Background(), challenge.TransactionID); err != nil {
		t.Fatal(err)
	}
	want := []State{Reserved, Authorized, SendStarted, Terminal, Cleanup}
	for i, state := range want {
		if wal.events[i].State != state {
			t.Fatalf("transition %d = %s", i, wal.events[i].State)
		}
	}
}

func TestReplayScopePeerConnectionAndConsentMismatch(t *testing.T) {
	request, challenge, config, clock := fixture(t)
	wal := &memoryWAL{}
	manager, _ := NewManager(config, &fakeFIDO{}, wal, clock)
	peer := Peer{UID: 501, PID: 4321}
	reserved, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "one")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "two"); !errors.Is(err, ErrDenied) {
		t.Fatalf("duplicate: %v", err)
	}
	canonical, _ := protocol.CanonicalJSON(reserved)
	for name, tc := range map[string]struct {
		connection string
		peer       Peer
		digest     string
	}{"connection": {"two", peer, protocol.Digest(canonical)}, "peer": {"one", Peer{UID: 501, PID: 9}, protocol.Digest(canonical)}, "digest": {"one", peer, "sha256:" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}} {
		t.Run(name, func(t *testing.T) {
			if _, err := manager.Authorize(context.Background(), reserved.TransactionID, tc.connection, tc.peer, tc.digest); err == nil {
				t.Fatal("substitution accepted")
			}
		})
	}
	request.Authority.Nonce = "nonce-02"
	request.Authority.Sequence = 8
	challenge.Nonce = "nonce-02"
	challenge.Sequence = 8
	challenge.TransactionID = "transaction-02"
	challenge.Scope.Lane = "research"
	if _, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "one"); err == nil {
		t.Fatal("altered scope accepted")
	}
}

func TestCancelSendHasSingleWinner(t *testing.T) {
	manager, challenge, peer, _ := reserve(t, &fakeFIDO{}, &memoryWAL{})
	canonical, _ := protocol.CanonicalJSON(challenge)
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err != nil {
		t.Fatal(err)
	}
	start := make(chan struct{})
	outcomes := make(chan error, 2)
	go func() {
		<-start
		_, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer)
		outcomes <- err
	}()
	go func() { <-start; outcomes <- manager.Cancel(context.Background(), challenge.TransactionID) }()
	close(start)
	a, b := <-outcomes, <-outcomes
	if (a == nil) == (b == nil) {
		t.Fatalf("expected one winner: %v %v", a, b)
	}
}

func TestCrashAfterSendRecoversOutcomeUnknown(t *testing.T) {
	wal := &memoryWAL{}
	manager, challenge, peer, clock := reserve(t, &fakeFIDO{}, wal)
	canonical, _ := protocol.CanonicalJSON(challenge)
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err != nil {
		t.Fatal(err)
	}
	if _, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer); err != nil {
		t.Fatal(err)
	}
	_, _, config, _ := fixture(t)
	recovered, err := NewManager(config, &fakeFIDO{}, wal, clock)
	if err != nil {
		t.Fatal(err)
	}
	if recovered.records[challenge.TransactionID].event.Outcome != "outcome_unknown" {
		t.Fatal("ambiguous send was retryable")
	}
}

func TestEveryDurableBoundaryFailsClosed(t *testing.T) {
	for point := 1; point <= 3; point++ {
		t.Run(string(rune('0'+point)), func(t *testing.T) {
			wal := &memoryWAL{failAt: point}
			fido := &fakeFIDO{}
			request, challenge, config, clock := fixture(t)
			manager, _ := NewManager(config, fido, wal, clock)
			peer := Peer{UID: 501, PID: 4321}
			reserved, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "connection-01")
			if point == 1 {
				if err == nil {
					t.Fatal("reservation survived fsync failure")
				}
				return
			}
			canonical, _ := protocol.CanonicalJSON(reserved)
			_, err = manager.Authorize(context.Background(), reserved.TransactionID, "connection-01", peer, protocol.Digest(canonical))
			if point == 2 {
				if err == nil {
					t.Fatal("authorization survived fsync failure")
				}
				return
			}
			_, err = manager.BeginSend(context.Background(), reserved.TransactionID, "connection-01", peer)
			if err == nil {
				t.Fatal("send survived fsync failure")
			}
		})
	}
}

func TestDirWALChecksAndPersists(t *testing.T) {
	dir := t.TempDir()
	if err := os.Chmod(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	wal, err := OpenDirWAL(dir, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	event := Event{Version: 1, TransactionID: "t", Nonce: "n", Sequence: 1, State: Reserved}
	if err := wal.Append(context.Background(), event); err != nil {
		t.Fatal(err)
	}
	events, err := wal.Events(context.Background())
	if err != nil || len(events) != 1 {
		t.Fatalf("events=%v err=%v", events, err)
	}
	if err := wal.Close(); err != nil {
		t.Fatal(err)
	}
}
