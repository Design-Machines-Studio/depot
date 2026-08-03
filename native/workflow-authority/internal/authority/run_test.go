package authority

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
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

type blockingFIDO struct{ started chan struct{} }

func (*blockingFIDO) Readiness(context.Context) Readiness {
	return Readiness{Adapter: "blocking-test", InternalUV: true}
}
func (f *blockingFIDO) Assert(ctx context.Context, _ []byte, _ Credential) (Assertion, error) {
	close(f.started)
	<-ctx.Done()
	return Assertion{}, ctx.Err()
}
func (*blockingFIDO) Verify(context.Context, []byte, Credential, Assertion) error { return ErrDenied }

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
	public, err := base64.RawURLEncoding.DecodeString(challenge.ResultSigner.PublicKeySEC1)
	if err != nil || len(public) != 65 || public[0] != 4 {
		t.Fatalf("result signer is not uncompressed SEC1: %x %v", public, err)
	}
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
	if got := wal.events[len(wal.events)-1].State; got != SendStarted {
		t.Fatalf("send right escaped before durable marker: %s", got)
	}
	terminal := []byte("terminal-input")
	if err := manager.Finalize(context.Background(), right, 64, "verified", protocol.Digest(terminal)); err != nil {
		t.Fatal(err)
	}
	if signature, err := manager.SignFinalized(right, terminal); err != nil || len(signature) == 0 {
		t.Fatalf("terminal signature unavailable: %v", err)
	}
	want := []State{Reserved, Authorized, SendStarted, Cleanup}
	for i, state := range want {
		if wal.events[i].State != state {
			t.Fatalf("transition %d = %s", i, wal.events[i].State)
		}
	}
}

func TestAtomicFinalizeConsumesAndSignsOnce(t *testing.T) {
	wal := &memoryWAL{}
	manager, challenge, peer, _ := reserve(t, &fakeFIDO{}, wal)
	canonical, _ := protocol.CanonicalJSON(challenge)
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err != nil {
		t.Fatal(err)
	}
	right, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer)
	if err != nil {
		t.Fatal(err)
	}
	terminal := []byte("terminal")
	if err := manager.Finalize(context.Background(), right, 64, "verified", protocol.Digest(terminal)); err != nil {
		t.Fatal(err)
	}
	if _, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer); err == nil {
		t.Fatal("finalized send reused")
	}
	if signature, err := manager.SignFinalized(right, terminal); err != nil || len(signature) == 0 {
		t.Fatalf("sign: %v", err)
	}
	if _, err := manager.SignFinalized(right, []byte("terminal")); err == nil {
		t.Fatal("finalized signer reused")
	}
	if got := manager.records[challenge.TransactionID].event.State; got != Cleanup {
		t.Fatalf("state=%s", got)
	}
}

func TestFinalizedSignerMismatchConsumesKey(t *testing.T) {
	manager, challenge, peer, _ := reserve(t, &fakeFIDO{}, &memoryWAL{})
	canonical, _ := protocol.CanonicalJSON(challenge)
	_, _ = manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical))
	right, _ := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer)
	terminal := []byte("terminal")
	if err := manager.Finalize(context.Background(), right, 1, "verified", protocol.Digest(terminal)); err != nil {
		t.Fatal(err)
	}
	if _, err := manager.SignFinalized(right, []byte("different-terminal")); err == nil {
		t.Fatal("finalized signer accepted unbound terminal")
	}
	if record := manager.records[challenge.TransactionID]; record.private != nil || !record.signed {
		t.Fatal("mismatched sign attempt retained authority")
	}
	if _, err := manager.SignFinalized(right, terminal); err == nil {
		t.Fatal("mismatched sign attempt was retryable")
	}
}

func TestAtomicFinalizeDurabilityFailureRecoversUnknown(t *testing.T) {
	wal := &memoryWAL{failAt: 4}
	manager, challenge, peer, clock := reserve(t, &fakeFIDO{}, wal)
	canonical, _ := protocol.CanonicalJSON(challenge)
	_, _ = manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical))
	right, _ := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer)
	terminal := []byte("terminal")
	if err := manager.Finalize(context.Background(), right, 64, "verified", protocol.Digest(terminal)); err == nil {
		t.Fatal("finalize survived durability failure")
	}
	if _, err := manager.SignFinalized(right, []byte("terminal")); err == nil {
		t.Fatal("unfinalized signer accepted")
	}
	_, _, config, _ := fixture(t)
	recovered, err := NewManager(config, &fakeFIDO{}, wal, clock)
	if err != nil {
		t.Fatal(err)
	}
	if recovered.records[challenge.TransactionID].event.Outcome != "outcome_unknown" {
		t.Fatal("failed finalize became retryable")
	}
}

func TestWALFailureNeverPublishesTransition(t *testing.T) {
	wal := &memoryWAL{}
	manager, challenge, peer, _ := reserve(t, &fakeFIDO{}, wal)
	canonical, _ := protocol.CanonicalJSON(challenge)
	wal.failAt = 2
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err == nil {
		t.Fatal("authorization fsync failure accepted")
	}
	if manager.records[challenge.TransactionID].event.State != Reserved {
		t.Fatal("failed authorization published")
	}
	wal.failAt = 0
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err != nil {
		t.Fatal(err)
	}
	wal.failAt = 4
	if _, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer); err == nil {
		t.Fatal("send fsync failure accepted")
	}
	if manager.records[challenge.TransactionID].event.State != Authorized {
		t.Fatal("failed send published")
	}
	wal.failAt = 0
	if _, err := manager.BeginSend(context.Background(), challenge.TransactionID, "connection-01", peer); err != nil {
		t.Fatal(err)
	}
	beforeBytes := manager.bytes
	wal.failAt = 6
	terminal := []byte("terminal")
	if err := manager.Finalize(context.Background(), SendRight{TransactionID: challenge.TransactionID}, 10, "verified", protocol.Digest(terminal)); err == nil {
		t.Fatal("finalize fsync failure accepted")
	}
	if manager.records[challenge.TransactionID].event.State != SendStarted || manager.bytes != beforeBytes {
		t.Fatal("failed finalize published")
	}
	wal.failAt = 0
	if err := manager.Finalize(context.Background(), SendRight{TransactionID: challenge.TransactionID}, 10, "provider_failure", ""); err != nil {
		t.Fatal(err)
	}
	if record := manager.records[challenge.TransactionID]; record.event.State != Cleanup || record.private != nil {
		t.Fatal("failure finalization retained signing authority")
	}

	cancelWAL := &memoryWAL{}
	cancelManager, cancelChallenge, _, _ := reserve(t, &fakeFIDO{}, cancelWAL)
	cancelWAL.failAt = 2
	if err := cancelManager.Cancel(context.Background(), cancelChallenge.TransactionID); err == nil {
		t.Fatal("cancel fsync failure accepted")
	}
	if record := cancelManager.records[cancelChallenge.TransactionID]; record.event.State != Reserved || record.cancelled {
		t.Fatal("failed cancel published")
	}
}

func TestCancelableAssertionSeamInterruptsAndBoundsWait(t *testing.T) {
	ctx, cancelContext := context.WithCancel(context.Background())
	results := make(chan assertionResult, 1)
	interrupted := make(chan struct{})
	go func() { <-interrupted; results <- assertionResult{err: context.Canceled} }()
	cancelContext()
	started := time.Now()
	_, err := waitCancelableAssertion(ctx, func() error { close(interrupted); return nil }, results, time.Second)
	if !errors.Is(err, ErrConflict) || time.Since(started) > 250*time.Millisecond {
		t.Fatalf("cancellation did not interrupt: %v", err)
	}

	stuckCtx, stuckCancel := context.WithCancel(context.Background())
	stuckCancel()
	started = time.Now()
	_, err = waitCancelableAssertion(stuckCtx, func() error { return nil }, make(chan assertionResult), 10*time.Millisecond)
	if !errors.Is(err, ErrConflict) || time.Since(started) > 250*time.Millisecond {
		t.Fatalf("bounded cancellation grace failed: %v", err)
	}
}

func TestShutdownCancelsInProgressFIDO(t *testing.T) {
	request, challenge, config, clock := fixture(t)
	fido := &blockingFIDO{started: make(chan struct{})}
	wal := &memoryWAL{}
	manager, err := NewManager(config, fido, wal, clock)
	if err != nil {
		t.Fatal(err)
	}
	peer := Peer{UID: 501, PID: 4321}
	challenge, err = manager.Reserve(context.Background(), request, challenge, []byte("body"), peer, "connection-01")
	if err != nil {
		t.Fatal(err)
	}
	canonical, _ := protocol.CanonicalJSON(challenge)
	finished := make(chan error, 1)
	go func() {
		_, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical))
		finished <- err
	}()
	select {
	case <-fido.started:
	case <-time.After(time.Second):
		t.Fatal("FIDO did not start")
	}
	started := time.Now()
	if err := manager.Shutdown(context.Background()); err != nil {
		t.Fatal(err)
	}
	if time.Since(started) > 250*time.Millisecond {
		t.Fatal("shutdown waited for device timeout")
	}
	select {
	case err := <-finished:
		if !errors.Is(err, ErrConflict) {
			t.Fatalf("authorize after shutdown: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("shutdown did not cancel FIDO")
	}
}

func TestRawAuthenticatorDataES256Vector(t *testing.T) {
	challenge := []byte("exact-challenge")
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	public, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	challengeDigest := sha256.Sum256(challenge)
	clientData, _ := protocol.CanonicalJSON(map[string]any{"challenge": base64.RawURLEncoding.EncodeToString(challengeDigest[:]), "crossOrigin": false, "origin": "https://workflow-authority.designmachines.local", "type": "webauthn.get"})
	rpID := "workflow-authority.designmachines.local"
	rpHash := sha256.Sum256([]byte(rpID))
	authdata := append([]byte{}, rpHash[:]...)
	authdata = append(authdata, 0x05, 0, 0, 0, 2)
	clientHash := sha256.Sum256(clientData)
	signed := append(append([]byte{}, authdata...), clientHash[:]...)
	digest := sha256.Sum256(signed)
	signature, err := ecdsa.SignASN1(rand.Reader, key, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	credential := Credential{Reference: "credential-generation-1", PublicKey: public, Algorithm: -7, Generation: 1, RPID: rpID, Status: "active", InternalUV: true, SignCount: 1}
	assertion := Assertion{CredentialReference: credential.Reference, Generation: 1, ChallengeDigest: challengeDigest, Signature: signature, AuthenticatorData: authdata, ClientDataJSON: clientData, UserPresence: true, UserVerification: true, Counter: binary.BigEndian.Uint32(authdata[33:37])}
	if err := verifyES256Assertion(challenge, credential, assertion); err != nil {
		t.Fatal(err)
	}
	assertion.AuthenticatorData[32] &^= 0x04
	if err := verifyES256Assertion(challenge, credential, assertion); err == nil {
		t.Fatal("missing raw UV flag accepted")
	}
}

func TestRestartReconstructsBudgetsOncePerTransaction(t *testing.T) {
	request, challenge, config, clock := fixture(t)
	config.MaxOperations = 1
	config.MaxBytes = 20
	event := Event{Version: 1, TransactionID: challenge.TransactionID, Nonce: request.Authority.Nonce, Sequence: request.Authority.Sequence, State: Reserved, RequestBodySHA256: challenge.RequestBodySHA256, Scope: challenge.Scope, RequestBytes: 4}
	terminal := event
	terminal.State = Terminal
	terminal.ResponseBytes = 6
	wal := &memoryWAL{events: []Event{event, terminal}}
	manager, err := NewManager(config, &fakeFIDO{}, wal, clock)
	if err != nil {
		t.Fatal(err)
	}
	if manager.operations != 1 || manager.bytes != 10 {
		t.Fatalf("reconstructed operations=%d bytes=%d", manager.operations, manager.bytes)
	}
	request.Authority.Nonce = "nonce-02"
	request.Authority.Sequence = 8
	challenge.Nonce = "nonce-02"
	challenge.Sequence = 8
	challenge.TransactionID = "transaction-02"
	if _, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), Peer{UID: 501, PID: 4321}, "connection-02"); err == nil {
		t.Fatal("restart reset operation budget")
	}
}

func TestFrozenPendingBounds(t *testing.T) {
	attempt := func(manager *Manager, index int, uid uint32, repository string) error {
		request, challenge, _, _ := fixture(t)
		token := fmt.Sprintf("n-%d", index)
		request.Authority.Nonce = token
		request.Authority.Sequence = uint64(index + 1)
		request.Scope.Repository = repository
		challenge.Nonce = token
		challenge.Sequence = uint64(index + 1)
		challenge.TransactionID = fmt.Sprintf("t-%d", index)
		challenge.Scope.Repository = repository
		challenge.PeerUID = uid
		challenge.PeerPID = int32(index + 10)
		_, err := manager.Reserve(context.Background(), request, challenge, []byte("body"), Peer{UID: uid, PID: int32(index + 10)}, fmt.Sprintf("c-%d", index))
		return err
	}
	newBounded := func(allowed map[uint32]struct{}) *Manager {
		_, _, config, clock := fixture(t)
		config.AllowedUIDs = allowed
		config.MaxOperations = 100
		config.MaxConcurrent = 100
		config.MaxBytes = 1 << 30
		manager, err := NewManager(config, &fakeFIDO{}, &memoryWAL{}, clock)
		if err != nil {
			t.Fatal(err)
		}
		return manager
	}
	peerManager := newBounded(map[uint32]struct{}{501: {}})
	for i := 0; i < 4; i++ {
		if err := attempt(peerManager, i, 501, fmt.Sprintf("repo/%d", i)); err != nil {
			t.Fatal(err)
		}
	}
	if err := attempt(peerManager, 4, 501, "repo/4"); !errors.Is(err, ErrConflict) {
		t.Fatalf("per-peer bound: %v", err)
	}
	allowed := map[uint32]struct{}{}
	for i := 0; i < 65; i++ {
		allowed[uint32(1000+i)] = struct{}{}
	}
	repositoryManager := newBounded(allowed)
	for i := 0; i < 16; i++ {
		if err := attempt(repositoryManager, i, uint32(1000+i), "shared/repo"); err != nil {
			t.Fatal(err)
		}
	}
	if err := attempt(repositoryManager, 16, 1016, "shared/repo"); !errors.Is(err, ErrConflict) {
		t.Fatalf("repository bound: %v", err)
	}
	daemonManager := newBounded(allowed)
	for i := 0; i < 64; i++ {
		if err := attempt(daemonManager, i, uint32(1000+i), fmt.Sprintf("repo/%d", i)); err != nil {
			t.Fatal(err)
		}
	}
	if err := attempt(daemonManager, 64, 1064, "repo/64"); !errors.Is(err, ErrConflict) {
		t.Fatalf("daemon bound: %v", err)
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
