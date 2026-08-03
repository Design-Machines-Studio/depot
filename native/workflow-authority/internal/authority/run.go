// Package authority implements exact-request authorization and replay-safe state.
package authority

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
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sync"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/protocol"
)

const (
	ProductionSocket = "/run/design-machines/workflow-authority/authority.sock"
	FIDO2Version     = "1.17.0"
)

type Diagnostic struct {
	Code string
	Exit int
}

func (e Diagnostic) Error() string { return e.Code }

var (
	ErrMalformed   = Diagnostic{"invalid_document", 2}
	ErrDenied      = Diagnostic{"authorization_denied", 3}
	ErrUnavailable = Diagnostic{"fido_unavailable", 4}
	ErrDurability  = Diagnostic{"durable_state_unavailable", 5}
	ErrConflict    = Diagnostic{"authority_conflict", 6}
)

type State string

const (
	Reserved    State = "reserved"
	Authorized  State = "fido_authorized_exact_request"
	SendStarted State = "send_started"
	Terminal    State = "terminal"
	Cleanup     State = "cleanup"
)

type Peer struct {
	UID uint32
	PID int32
}

type Credential struct {
	Reference  string     `json:"reference"`
	PublicKey  []byte     `json:"public_key"`
	Algorithm  int        `json:"algorithm"`
	Generation uint64     `json:"generation"`
	RPID       string     `json:"rp_id"`
	EnrolledAt time.Time  `json:"enrolled_at"`
	Status     string     `json:"status"`
	RevokedAt  *time.Time `json:"revoked_at,omitempty"`
	InternalUV bool       `json:"internal_uv"`
	SignCount  uint32     `json:"sign_count"`
	// ID is root-private input to the native adapter and is never serialized.
	ID []byte `json:"-"`
	// DeviceSelector is root-private runtime metadata. It binds assertions to
	// the exact bounded manifest identity selected during enrollment.
	DeviceSelector string `json:"-"`
}

type EnrollmentRegistry struct {
	mu      sync.Mutex
	active  uint64
	records map[uint64]Credential
}

func NewEnrollmentRegistry() *EnrollmentRegistry {
	return &EnrollmentRegistry{records: map[uint64]Credential{}}
}

// Enroll accepts only a root/operator ceremony result containing public CTAP2
// ES256 metadata and internal UV capability. It accepts no software secret.
func (r *EnrollmentRegistry) Enroll(credential Credential, rootCeremony bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if !rootCeremony || credential.Algorithm != -7 || !credential.InternalUV || credential.Generation == 0 || credential.Reference == "" || len(credential.PublicKey) == 0 || credential.RPID == "" || credential.Status != "active" || len(credential.ID) == 0 {
		return ErrDenied
	}
	if _, exists := r.records[credential.Generation]; exists {
		return ErrConflict
	}
	if r.active != 0 && credential.Generation <= r.active {
		return ErrConflict
	}
	if r.active != 0 {
		old := r.records[r.active]
		old.Status = "rotated"
		old.ID = nil
		r.records[r.active] = old
	}
	publicOnly := credential
	publicOnly.ID = nil
	r.records[credential.Generation] = publicOnly
	r.active = credential.Generation
	return nil
}

func (r *EnrollmentRegistry) Active() (Credential, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	credential, ok := r.records[r.active]
	if !ok || credential.Status != "active" {
		return Credential{}, ErrUnavailable
	}
	return credential, nil
}

func (r *EnrollmentRegistry) Revoke(generation uint64, at time.Time, rootCeremony bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	credential, ok := r.records[generation]
	if !rootCeremony || !ok {
		return ErrDenied
	}
	credential.Status = "revoked"
	credential.RevokedAt = &at
	credential.ID = nil
	r.records[generation] = credential
	if r.active == generation {
		r.active = 0
	}
	return nil
}

func (r *EnrollmentRegistry) Recover(credential Credential, rootCeremony, separateRecoveryCeremony bool) error {
	if !rootCeremony || !separateRecoveryCeremony {
		return ErrDenied
	}
	return r.Enroll(credential, true)
}

type Assertion struct {
	CredentialReference string
	Generation          uint64
	ChallengeDigest     [32]byte
	Signature           []byte
	AuthenticatorData   []byte
	ClientDataJSON      []byte
	UserPresence        bool
	UserVerification    bool
	Counter             uint32
	HostPINRequested    bool
}

type FIDO interface {
	Readiness(context.Context) Readiness
	Assert(context.Context, []byte, Credential) (Assertion, error)
	Verify(context.Context, []byte, Credential, Assertion) error
}

type SelectorAwareFIDO interface {
	FIDO
	ReadinessFor(context.Context, string) Readiness
}

func CredentialFromEnrollment(source enrollment.Credential) (Credential, error) {
	if enrollment.ValidateCredential(source) != nil {
		return Credential{}, ErrDenied
	}
	return Credential{Reference: source.Reference, PublicKey: append([]byte(nil), source.PublicKey...), Algorithm: source.Algorithm, Generation: source.Generation, RPID: source.RPID, EnrolledAt: source.EnrolledAt, Status: source.Status, RevokedAt: source.RevokedAt, InternalUV: source.InternalUV, ID: append([]byte(nil), source.ID...), DeviceSelector: source.DeviceSelector}, nil
}

type Readiness struct {
	Production       bool
	Adapter, Version string
	InternalUV       bool
}

type assertionResult struct {
	assertion Assertion
	err       error
}

func waitCancelableAssertion(ctx context.Context, cancelNative func() error, results <-chan assertionResult, grace time.Duration) (Assertion, error) {
	select {
	case result := <-results:
		return result.assertion, result.err
	case <-ctx.Done():
		if err := cancelNative(); err != nil {
			return Assertion{}, ErrUnavailable
		}
		timer := time.NewTimer(grace)
		defer timer.Stop()
		select {
		case <-results:
			return Assertion{}, ErrConflict
		case <-timer.C:
			// The worker retains sole cleanup ownership and the device timeout is
			// the final backstop; the cancelled caller is never held for it.
			return Assertion{}, ErrConflict
		}
	}
}

type Clock interface{ Now() time.Time }
type realClock struct{}

func (realClock) Now() time.Time { return time.Now().UTC() }

type Event struct {
	Version              int            `json:"version"`
	TransactionID        string         `json:"transaction_id"`
	Nonce                string         `json:"nonce"`
	Sequence             uint64         `json:"sequence"`
	BootID               string         `json:"boot_id"`
	SessionID            string         `json:"session_id"`
	State                State          `json:"state"`
	RequestBodySHA256    string         `json:"request_body_sha256"`
	Scope                protocol.Scope `json:"scope"`
	ChallengeSHA256      string         `json:"challenge_sha256,omitempty"`
	AssertionSHA256      string         `json:"assertion_sha256,omitempty"`
	SignerPublicKey      string         `json:"signer_public_key,omitempty"`
	TerminalSHA256       string         `json:"terminal_sha256,omitempty"`
	Outcome              string         `json:"outcome,omitempty"`
	RequestBytes         int64          `json:"request_bytes"`
	ResponseBytes        int64          `json:"response_bytes"`
	CredentialGeneration uint64         `json:"credential_generation,omitempty"`
	SignCount            uint32         `json:"sign_count,omitempty"`
	At                   string         `json:"at"`
}

type WAL interface {
	Append(context.Context, Event) error
	Events(context.Context) ([]Event, error)
	Close() error
}

// DirWAL anchors all paths to an opened directory and fsyncs each event and the
// directory. It rejects non-owned, linked, non-regular, or permissive state.
type DirWAL struct {
	mu    sync.Mutex
	root  *os.Root
	owner uint32
}

func OpenDirWAL(path string, owner uint32) (*DirWAL, error) {
	info, err := os.Lstat(path)
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0o700 {
		return nil, ErrDurability
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner {
		return nil, ErrDurability
	}
	root, err := os.OpenRoot(path)
	if err != nil {
		return nil, ErrDurability
	}
	return &DirWAL{root: root, owner: owner}, nil
}

func (w *DirWAL) Append(_ context.Context, event Event) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if event.Version != 1 {
		return ErrDurability
	}
	if info, err := w.root.Lstat("authority.wal"); err == nil {
		stat, ok := info.Sys().(*syscall.Stat_t)
		if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 || stat.Uid != w.owner || stat.Nlink != 1 {
			return ErrDurability
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ErrDurability
	}
	f, err := w.root.OpenFile("authority.wal", os.O_WRONLY|os.O_APPEND|os.O_CREATE|syscall.O_NOFOLLOW, 0o600)
	if err != nil {
		return ErrDurability
	}
	payload, err := protocol.CanonicalJSON(event)
	if err == nil {
		payload = append(payload, '\n')
		_, err = f.Write(payload)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	dir, dirErr := w.root.Open(".")
	if dirErr == nil {
		dirErr = dir.Sync()
		_ = dir.Close()
	}
	if err != nil || dirErr != nil {
		return ErrDurability
	}
	return nil
}

func (w *DirWAL) Events(_ context.Context) ([]Event, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	data, err := w.root.ReadFile("authority.wal")
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, ErrDurability
	}
	lines := bytesLines(data)
	events := make([]Event, 0, len(lines))
	for _, line := range lines {
		var event Event
		if err := json.Unmarshal(line, &event); err != nil || event.Version != 1 {
			return nil, ErrDurability
		}
		events = append(events, event)
	}
	return events, nil
}
func bytesLines(data []byte) [][]byte {
	var out [][]byte
	start := 0
	for i, b := range data {
		if b == '\n' {
			if i > start {
				out = append(out, data[start:i])
			}
			start = i + 1
		}
	}
	if start != len(data) {
		out = append(out, data[start:])
	}
	return out
}
func (w *DirWAL) Close() error { return w.root.Close() }

type Config struct {
	BootID, SessionID string
	AllowedUIDs       map[uint32]struct{}
	MaxOperations     int
	MaxBytes          int64
	MaxConcurrent     int
	Credential        Credential
}

type reservation struct {
	event          Event
	request        protocol.Request
	challenge      protocol.Challenge
	connectionID   string
	peer           Peer
	private        *ecdsa.PrivateKey
	cancelled      bool
	finalized      bool
	signed         bool
	terminalSHA256 string
}

type Manager struct {
	mu         sync.Mutex
	config     Config
	fido       FIDO
	clock      Clock
	wal        WAL
	records    map[string]*reservation
	sequences  map[uint64]struct{}
	nonces     map[string]struct{}
	operations int
	bytes      int64
	active     map[string]context.CancelFunc
}

func NewManager(config Config, fido FIDO, wal WAL, clock Clock) (*Manager, error) {
	if config.BootID == "" || config.SessionID == "" || len(config.AllowedUIDs) == 0 || config.MaxOperations < 1 || config.MaxBytes < 1 || config.MaxConcurrent < 1 || fido == nil || wal == nil {
		return nil, ErrMalformed
	}
	if config.Credential.Algorithm != -7 || !config.Credential.InternalUV || config.Credential.Status != "active" {
		return nil, ErrUnavailable
	}
	if clock == nil {
		clock = realClock{}
	}
	m := &Manager{config: config, fido: fido, clock: clock, wal: wal, records: map[string]*reservation{}, sequences: map[uint64]struct{}{}, nonces: map[string]struct{}{}, active: map[string]context.CancelFunc{}}
	events, err := wal.Events(context.Background())
	if err != nil {
		return nil, err
	}
	latest := make(map[string]Event)
	for _, event := range events {
		m.nonces[event.Nonce] = struct{}{}
		m.sequences[event.Sequence] = struct{}{}
		if event.CredentialGeneration == m.config.Credential.Generation && event.SignCount > m.config.Credential.SignCount {
			m.config.Credential.SignCount = event.SignCount
		}
		latest[event.TransactionID] = event
	}
	for _, event := range latest {
		if consumesSendBudget(event) {
			m.operations++
			m.bytes += event.RequestBytes + event.ResponseBytes
		}
		if event.State == SendStarted {
			event.State = Terminal
			event.Outcome = "outcome_unknown"
			if err := wal.Append(context.Background(), event); err != nil {
				return nil, err
			}
		} else if event.State == Reserved || event.State == Authorized {
			event.State = Cleanup
			event.Outcome = "restart_requires_fresh_authorization"
			if err := wal.Append(context.Background(), event); err != nil {
				return nil, err
			}
		}
		m.records[event.TransactionID] = &reservation{event: event}
	}
	return m, nil
}

func (m *Manager) Reserve(ctx context.Context, request protocol.Request, challenge protocol.Challenge, requestBody []byte, peer Peer, connectionID string) (protocol.Challenge, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.config.AllowedUIDs[peer.UID]; !ok || peer.PID < 1 || connectionID == "" {
		return protocol.Challenge{}, ErrDenied
	}
	if err := protocol.ValidateRequest(request, m.clock.Now()); err != nil {
		return protocol.Challenge{}, ErrDenied
	}
	if request.Authority.BootID != m.config.BootID || request.Authority.SessionID != m.config.SessionID || challenge.PeerUID != peer.UID || challenge.PeerPID != peer.PID {
		return protocol.Challenge{}, ErrDenied
	}
	if err := exactBinding(request, challenge); err != nil {
		return protocol.Challenge{}, err
	}
	if int64(len(requestBody)) > request.Limits.MaxRequestBytes || protocol.Digest(requestBody) != challenge.RequestBodySHA256 {
		return protocol.Challenge{}, ErrDenied
	}
	requestBytes := int64(len(requestBody))
	if _, ok := m.nonces[request.Authority.Nonce]; ok {
		return protocol.Challenge{}, ErrDenied
	}
	if _, ok := m.sequences[request.Authority.Sequence]; ok {
		return protocol.Challenge{}, ErrDenied
	}
	if m.operations >= m.config.MaxOperations || m.bytes+requestBytes > m.config.MaxBytes || m.pendingLocked() >= min(m.config.MaxConcurrent, 64) || m.pendingForPeerLocked(peer.UID) >= 4 || m.pendingForRepositoryLocked(request.Scope.Repository) >= 16 {
		return protocol.Challenge{}, ErrConflict
	}
	private, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return protocol.Challenge{}, ErrUnavailable
	}
	public := elliptic.Marshal(elliptic.P256(), private.PublicKey.X, private.PublicKey.Y)
	challenge.ResultSigner = protocol.ResultSigner{Kind: "ephemeral-es256", PublicKeySEC1: base64.RawURLEncoding.EncodeToString(public)}
	challenge.AuthorityAssertion = nil
	challengeBytes, err := protocol.CanonicalJSON(challenge)
	if err != nil {
		return protocol.Challenge{}, ErrMalformed
	}
	event := Event{Version: 1, TransactionID: challenge.TransactionID, Nonce: request.Authority.Nonce, Sequence: request.Authority.Sequence, BootID: request.Authority.BootID, SessionID: request.Authority.SessionID, State: Reserved, RequestBodySHA256: challenge.RequestBodySHA256, Scope: challenge.Scope, ChallengeSHA256: protocol.Digest(challengeBytes), SignerPublicKey: challenge.ResultSigner.PublicKeySEC1, RequestBytes: requestBytes, At: m.clock.Now().Format(time.RFC3339)}
	if err := m.wal.Append(ctx, event); err != nil {
		zeroKey(private)
		return protocol.Challenge{}, err
	}
	m.nonces[event.Nonce] = struct{}{}
	m.sequences[event.Sequence] = struct{}{}
	m.records[event.TransactionID] = &reservation{event: event, request: request, challenge: challenge, connectionID: connectionID, peer: peer, private: private}
	return challenge, nil
}

func exactBinding(r protocol.Request, c protocol.Challenge) error {
	a := r.Authority
	if c.SchemaVersion != r.SchemaVersion || c.Protocol != r.Protocol || c.Mapping != r.Mapping || c.OperationFamily != r.OperationFamily || c.SubstrateAuthority != r.SubstrateAuthority || c.ConnectionNonceSHA256 != a.ConnectionNonceSHA256 || c.Destination != r.Destination || c.Method != r.Method || c.Path != r.Path || !equalStrings(c.Models, r.Models) || c.Scope != r.Scope || c.DaemonBuildSHA256 != a.DaemonBuildSHA256 || c.ScannerBuildSHA256 != a.ScannerBuildSHA256 || c.PolicySHA256 != a.PolicySHA256 || c.Nonce != a.Nonce || c.Sequence != a.Sequence || c.BootID != a.BootID || c.SessionID != a.SessionID || c.IssuedAt != a.IssuedAt || c.ExpiresAt != a.ExpiresAt || c.PriorChainDigest != a.PriorChainDigest || c.AllocationHelloSHA256 != a.AllocationHelloSHA256 || c.DispatchProposalSHA256 != a.DispatchProposalSHA256 {
		return ErrDenied
	}
	return nil
}
func equalStrings(a, b []string) bool {
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

func (m *Manager) Authorize(ctx context.Context, transactionID, connectionID string, peer Peer, consentChallengeDigest string) (Assertion, error) {
	m.mu.Lock()
	record, err := m.ownedLocked(transactionID, connectionID, peer, Reserved)
	if err != nil {
		m.mu.Unlock()
		return Assertion{}, err
	}
	challenge := record.challenge
	credential := m.config.Credential
	m.mu.Unlock()
	canonical, _ := protocol.CanonicalJSON(challenge)
	if consentChallengeDigest != protocol.Digest(canonical) {
		return Assertion{}, ErrDenied
	}
	input, err := protocol.ChallengeInput(challenge)
	if err != nil {
		return Assertion{}, ErrMalformed
	}
	m.mu.Lock()
	if _, err := m.ownedLocked(transactionID, connectionID, peer, Reserved); err != nil {
		m.mu.Unlock()
		return Assertion{}, err
	}
	if _, exists := m.active[transactionID]; exists {
		m.mu.Unlock()
		return Assertion{}, ErrConflict
	}
	fidoContext, cancelFIDO := context.WithCancel(ctx)
	m.active[transactionID] = cancelFIDO
	m.mu.Unlock()
	assertion, err := m.fido.Assert(fidoContext, input, credential)
	cancelFIDO()
	m.mu.Lock()
	delete(m.active, transactionID)
	m.mu.Unlock()
	if err != nil {
		return Assertion{}, redactFIDO(err)
	}
	counterRollback := (assertion.Counter != 0 || credential.SignCount != 0) && assertion.Counter <= credential.SignCount
	if assertion.HostPINRequested || !assertion.UserPresence || !assertion.UserVerification || assertion.Generation != credential.Generation || assertion.CredentialReference != credential.Reference || counterRollback {
		return Assertion{}, ErrDenied
	}
	if err := m.fido.Verify(ctx, input, credential, assertion); err != nil {
		return Assertion{}, ErrDenied
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	record, err = m.ownedLocked(transactionID, connectionID, peer, Reserved)
	if err != nil {
		return Assertion{}, err
	}
	digest := sha256.Sum256(append(append([]byte{}, assertion.AuthenticatorData...), assertion.Signature...))
	next := record.event
	next.State = Authorized
	next.AssertionSHA256 = fmt.Sprintf("sha256:%x", digest)
	next.CredentialGeneration = credential.Generation
	next.SignCount = assertion.Counter
	next.At = m.clock.Now().Format(time.RFC3339)
	if err := m.wal.Append(ctx, next); err != nil {
		return Assertion{}, err
	}
	record.event = next
	if assertion.Counter != 0 {
		m.config.Credential.SignCount = assertion.Counter
	}
	return assertion, nil
}

type SendRight struct{ TransactionID string }

// BeginSend returns an opaque right only after send_started is durable.
// Provider transport must call this immediately before its first network byte.
func (m *Manager) BeginSend(ctx context.Context, transactionID, connectionID string, peer Peer) (SendRight, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	record, err := m.ownedLocked(transactionID, connectionID, peer, Authorized)
	if err != nil {
		return SendRight{}, err
	}
	if record.cancelled {
		return SendRight{}, ErrConflict
	}
	if m.operations >= m.config.MaxOperations || m.bytes+record.event.RequestBytes > m.config.MaxBytes {
		return SendRight{}, ErrConflict
	}
	next := record.event
	next.State = SendStarted
	next.At = m.clock.Now().Format(time.RFC3339)
	if err := m.wal.Append(ctx, next); err != nil {
		return SendRight{}, err
	}
	record.event = next
	m.operations++
	m.bytes += record.event.RequestBytes
	return SendRight{TransactionID: transactionID}, nil
}

func consumesSendBudget(event Event) bool {
	if event.State == SendStarted || event.State == Terminal {
		return true
	}
	if event.State != Cleanup {
		return false
	}
	return event.Outcome == "verified" || event.Outcome == "provider_failure" || event.Outcome == "outcome_unknown"
}

// Finalize consumes send authority with one durable cleanup record. The
// ephemeral signer survives only when any closed post-send outcome binds the
// exact terminal input digest that the subsequent one-shot signature must
// match. A restart never reconstructs this process-local key.
func (m *Manager) Finalize(ctx context.Context, right SendRight, responseBytes int64, outcome, terminalSHA256 string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	record, ok := m.records[right.TransactionID]
	validDigest := validSHA256(terminalSHA256)
	if !ok || record.event.State != SendStarted || record.finalized || responseBytes < 0 || m.bytes+responseBytes > m.config.MaxBytes || (outcome != "verified" && outcome != "provider_failure" && outcome != "outcome_unknown") || !validDigest {
		return ErrConflict
	}
	next := record.event
	next.State = Cleanup
	next.ResponseBytes = responseBytes
	next.Outcome = outcome
	next.TerminalSHA256 = terminalSHA256
	next.At = m.clock.Now().Format(time.RFC3339)
	if err := m.wal.Append(ctx, next); err != nil {
		return err
	}
	record.event = next
	record.finalized = true
	record.terminalSHA256 = terminalSHA256
	m.bytes += responseBytes
	return nil
}

// SignFinalized signs once after durable consumption and destroys the key.
// Terminal write/close failure therefore cannot mint a retry receipt.
func (m *Manager) SignFinalized(right SendRight, terminalInput []byte) ([]byte, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	record, ok := m.records[right.TransactionID]
	if !ok || record.event.State != Cleanup || !record.finalized || record.signed || record.private == nil || len(terminalInput) == 0 {
		return nil, ErrConflict
	}
	record.signed = true
	if protocol.Digest(terminalInput) != record.terminalSHA256 {
		zeroKey(record.private)
		record.private = nil
		return nil, ErrConflict
	}
	digest := sha256.Sum256(terminalInput)
	signature, err := ecdsa.SignASN1(rand.Reader, record.private, digest[:])
	zeroKey(record.private)
	record.private = nil
	if err != nil {
		return nil, ErrUnavailable
	}
	return signature, nil
}

func (m *Manager) Cancel(ctx context.Context, transactionID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	record, ok := m.records[transactionID]
	if !ok {
		return ErrDenied
	}
	if record.event.State == SendStarted || record.event.State == Terminal {
		return ErrConflict
	}
	next := record.event
	next.State = Cleanup
	next.Outcome = "cancelled"
	next.At = m.clock.Now().Format(time.RFC3339)
	if err := m.wal.Append(ctx, next); err != nil {
		return err
	}
	record.event = next
	record.cancelled = true
	zeroKey(record.private)
	record.private = nil
	return nil
}

func (m *Manager) ownedLocked(id, connection string, peer Peer, state State) (*reservation, error) {
	record, ok := m.records[id]
	if !ok || record.event.State != state {
		return nil, ErrDenied
	}
	if record.connectionID != connection || record.peer != peer {
		return nil, ErrDenied
	}
	expires, err := time.Parse(time.RFC3339, record.challenge.ExpiresAt)
	if err != nil || !m.clock.Now().Before(expires) {
		return nil, ErrDenied
	}
	return record, nil
}
func (m *Manager) pendingLocked() int {
	count := 0
	for _, r := range m.records {
		if r.event.State != Terminal && r.event.State != Cleanup {
			count++
		}
	}
	return count
}
func (m *Manager) pendingForPeerLocked(uid uint32) int {
	count := 0
	for _, record := range m.records {
		if record.peer.UID == uid && record.event.State != Terminal && record.event.State != Cleanup {
			count++
		}
	}
	return count
}
func (m *Manager) pendingForRepositoryLocked(repository string) int {
	count := 0
	for _, record := range m.records {
		if record.event.Scope.Repository == repository && record.event.State != Terminal && record.event.State != Cleanup {
			count++
		}
	}
	return count
}
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
func validSHA256(value string) bool {
	if len(value) != 71 || value[:7] != "sha256:" {
		return false
	}
	_, err := hex.DecodeString(value[7:])
	return err == nil
}
func redactFIDO(err error) error {
	if errors.Is(err, context.Canceled) || errors.Is(err, ErrConflict) {
		return ErrConflict
	}
	return ErrUnavailable
}
func zeroKey(key *ecdsa.PrivateKey) {
	if key != nil {
		key.D.SetInt64(0)
	}
}

func (m *Manager) Shutdown(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	defer func() {
		zeroBytes(m.config.Credential.ID)
		m.config.Credential.ID = nil
	}()
	for _, cancel := range m.active {
		cancel()
	}
	for _, record := range m.records {
		if record.event.State == Reserved || record.event.State == Authorized {
			next := record.event
			next.State = Cleanup
			next.Outcome = "shutdown_cancelled"
			if err := m.wal.Append(ctx, next); err != nil {
				return err
			}
			record.event = next
		}
		if record.event.State == SendStarted {
			next := record.event
			next.State = Terminal
			next.Outcome = "outcome_unknown"
			if err := m.wal.Append(ctx, next); err != nil {
				return err
			}
			record.event = next
		}
		zeroKey(record.private)
		record.private = nil
	}
	return m.wal.Close()
}

func zeroBytes(value []byte) {
	for i := range value {
		value[i] = 0
	}
}

func verifyES256Assertion(challenge []byte, credential Credential, assertion Assertion) error {
	if !assertion.UserPresence || !assertion.UserVerification || assertion.HostPINRequested || assertion.Generation != credential.Generation || assertion.CredentialReference != credential.Reference {
		return ErrDenied
	}
	challengeDigest := sha256.Sum256(challenge)
	if assertion.ChallengeDigest != challengeDigest || len(assertion.AuthenticatorData) < 37 {
		return ErrDenied
	}
	var clientData struct {
		Challenge   string `json:"challenge"`
		CrossOrigin bool   `json:"crossOrigin"`
		Origin      string `json:"origin"`
		Type        string `json:"type"`
	}
	if err := protocol.DecodeClosed(assertion.ClientDataJSON, &clientData); err != nil || clientData.Challenge != base64.RawURLEncoding.EncodeToString(challengeDigest[:]) || clientData.CrossOrigin || clientData.Origin != "https://workflow-authority.designmachines.local" || clientData.Type != "webauthn.get" {
		return ErrDenied
	}
	rpHash := sha256.Sum256([]byte(credential.RPID))
	if !bytes.Equal(assertion.AuthenticatorData[:32], rpHash[:]) || assertion.AuthenticatorData[32]&0x01 == 0 || assertion.AuthenticatorData[32]&0x04 == 0 {
		return ErrDenied
	}
	counter := binary.BigEndian.Uint32(assertion.AuthenticatorData[33:37])
	if counter != assertion.Counter || (counter != 0 && counter <= credential.SignCount) {
		return ErrDenied
	}
	public, err := x509.ParsePKIXPublicKey(credential.PublicKey)
	if err != nil {
		return ErrDenied
	}
	key, ok := public.(*ecdsa.PublicKey)
	if !ok {
		return ErrDenied
	}
	clientHash := sha256.Sum256(assertion.ClientDataJSON)
	signed := append(append([]byte{}, assertion.AuthenticatorData...), clientHash[:]...)
	digest := sha256.Sum256(signed)
	if !ecdsa.VerifyASN1(key, digest[:], assertion.Signature) {
		return ErrDenied
	}
	return nil
}
