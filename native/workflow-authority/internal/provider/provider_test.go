package provider

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
)

func policyFixture() []byte {
	return []byte(`{"schemaVersion":2,"disclosureControls":{"refuseClasses":["high-confidence credentials","private keys","authenticated connection strings / DSNs","access or session tokens","explicitly classified private or regulated values"],"onMatch":"decline-disclosure","exitCode":3}}`)
}

func fixtureRequest(parts [][]byte) protocol.Request {
	d := "sha256:" + repeat("0", 64)
	declared := make([]protocol.Part, len(parts))
	roles := []string{"system", "user"}
	for i, p := range parts {
		declared[i] = protocol.Part{Role: roles[i%2], ContentLength: int64(len(p)), ContentSHA256: protocol.Digest(p)}
	}
	return protocol.Request{SchemaVersion: 1, Protocol: protocol.Name, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: []string{"openai/gpt-5.6", "z-ai/glm-5.2"}, Parts: declared, Scope: protocol.Scope{Repository: "repo", RunID: "run", Lane: "lane", Candidate: "candidate", Workload: "workload"}, Authority: protocol.Authority{DaemonBuildSHA256: d, ScannerBuildSHA256: ScannerBuildDigest, PolicySHA256: d, Nonce: "caller-nonce", Sequence: 1, BootID: "boot", SessionID: "session", ConnectionNonceSHA256: d, IssuedAt: "2026-08-03T00:00:00Z", ExpiresAt: "2026-08-03T00:02:00Z", PriorChainDigest: d, AllocationHelloSHA256: d, DispatchProposalSHA256: d}, Limits: protocol.Limits{MaxRequestBytes: 8388608, MaxResponseBytes: 8388608, MaxParts: 256, MaxPendingPerPeer: 4, MaxPendingRepository: 16, MaxPendingDaemon: 64}}
}
func repeat(s string, n int) string {
	out := ""
	for i := 0; i < n; i++ {
		out += s
	}
	return out
}

func TestBuildBodyFrozenVector(t *testing.T) {
	parts := [][]byte{[]byte("system\n"), []byte("user 🌍\\\"\n")}
	got, err := BuildBody(fixtureRequest(parts), parts)
	if err != nil {
		t.Fatal(err)
	}
	want := []byte("{\"messages\":[{\"content\":\"system\\n\",\"role\":\"system\"},{\"content\":\"user 🌍\\\\\\\"\\n\",\"role\":\"user\"}],\"models\":[\"openai/gpt-5.6\",\"z-ai/glm-5.2\"],\"temperature\":null}")
	if string(got) != string(want) {
		t.Fatalf("body mismatch\n got %s\nwant %s", got, want)
	}
}

func TestFixtureTLSExactlyOneAttemptAndCredentialIsolation(t *testing.T) {
	var requests atomic.Int32
	var authorization string
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		authorization = r.Header.Get("Authorization")
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "generation-fixture", "model": "z-ai/glm-5.2", "provider": "fixture", "usage": map[string]int{"total_tokens": 2}, "choices": []any{map[string]any{"message": map[string]any{"role": "assistant", "content": "fixture-content"}, "finish_reason": "stop"}}})
	}))
	defer server.Close()
	path := filepath.Join(t.TempDir(), "credential")
	if os.WriteFile(path, []byte("fixture-token-value\n"), 0o600) != nil {
		t.Fatal("fixture")
	}
	credential, err := (FileCredentialReader{Path: path, FixtureMode: true}).Read(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	defer credential.Destroy()
	transport := fixtureTransport(server)
	body := []byte(`{"messages":[],"models":[],"temperature":null}`)
	response, err := transport.Send(context.Background(), credential, body)
	if err != nil {
		t.Fatal(err)
	}
	if requests.Load() != 1 || authorization != "Bearer fixture-token-value" || len(response) == 0 {
		t.Fatalf("requests=%d authorization=%q", requests.Load(), authorization)
	}
	if string(response) == authorization {
		t.Fatal("credential escaped into response")
	}
}

func TestRejectionsHaveZeroRequests(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewTLSServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { requests.Add(1) }))
	defer server.Close()
	fixture := &Credential{bytes: []byte("fixture-value"), fixture: true}
	prod := &Credential{bytes: []byte("production-value")}
	tlsConfig := server.Client().Transport.(*http.Transport).TLSClientConfig
	cases := []*Transport{{Origin: ProductionURL, Fixture: true, TLSConfig: tlsConfig}, {Origin: server.URL + protocol.Path, Fixture: false, TLSConfig: tlsConfig}, {Origin: server.URL + "/wrong", Fixture: true, TLSConfig: tlsConfig}}
	creds := []*Credential{fixture, prod, fixture}
	for i, tr := range cases {
		if _, err := tr.Send(context.Background(), creds[i], []byte("{}")); err == nil {
			t.Fatalf("case %d accepted", i)
		}
	}
	if requests.Load() != 0 {
		t.Fatalf("unexpected requests: %d", requests.Load())
	}
}

func TestScannerRejectsBeforeTransport(t *testing.T) {
	policy := policyFixture()
	cases := [][][]byte{
		{[]byte("-----BEGIN PRIVATE KEY-----")},
		{[]byte("AK" + "IAABCDEFGHIJKLMNOP")},
		{[]byte("ghp_abcdefghijklmnopqrstuvwxyz")},
		{[]byte("postgres://user:password@database.invalid/db")},
		{[]byte("access_token=abcdefghijk")},
		{[]byte("session-id: abcdefghijk")},
		{[]byte("classified=private-value")},
		{[]byte("ghp_abcdefghij"), []byte("klmnopqrstuvwxyz")},
		{[]byte("postgres://user:"), []byte("password@database.invalid/db")},
	}
	for i, parts := range cases {
		if err := (BuiltinScanner{}).Scan(context.Background(), parts, policy); err != ErrPolicy {
			t.Fatalf("case %d: got %v", i, err)
		}
	}
	if err := (BuiltinScanner{}).Scan(context.Background(), [][]byte{[]byte("ordinary review text")}, policy); err != nil {
		t.Fatal(err)
	}
}

type providerMemoryWAL struct{ events []authority.Event }

func (w *providerMemoryWAL) Append(_ context.Context, e authority.Event) error {
	w.events = append(w.events, e)
	return nil
}
func (w *providerMemoryWAL) Events(context.Context) ([]authority.Event, error) {
	return append([]authority.Event(nil), w.events...), nil
}
func (w *providerMemoryWAL) Close() error { return nil }

type providerClock struct{ at time.Time }

func (c providerClock) Now() time.Time { return c.at }

type providerFIDO struct{ calls atomic.Int32 }

func (f *providerFIDO) Readiness(context.Context) authority.Readiness {
	return authority.Readiness{InternalUV: true}
}
func (f *providerFIDO) Assert(context.Context, []byte, authority.Credential) (authority.Assertion, error) {
	f.calls.Add(1)
	return authority.Assertion{CredentialReference: "credential-1", Generation: 1, Signature: []byte("fixture-signature"), AuthenticatorData: []byte("fixture-authenticator-data"), ClientDataJSON: []byte(`{"fixture":true}`), UserPresence: true, UserVerification: true}, nil
}
func (*providerFIDO) Verify(context.Context, []byte, authority.Credential, authority.Assertion) error {
	return nil
}

type rejectingReader struct{}

func (rejectingReader) Read(context.Context) (*Credential, error) {
	return nil, errors.New("must not run")
}

type staticReader struct{ value []byte }

func (r staticReader) Read(context.Context) (*Credential, error) {
	return &Credential{bytes: append([]byte(nil), r.value...), fixture: true}, nil
}

type testSink struct{ id string }

func (s testSink) ConnectionID() string { return s.id }
func (testSink) WriteAuthorizationProof(context.Context, AuthorizationProof) error {
	return errors.New("must not run")
}
func (testSink) WriteResponse(context.Context, []byte) error { return errors.New("must not run") }
func (testSink) WriteTerminalAndClose(context.Context, []byte) error {
	return errors.New("must not run")
}
func (testSink) Abort() error { return nil }

type captureSink struct {
	id                 string
	proof              bool
	response, terminal []byte
	responseWritten    bool
	closed             bool
	failTerminal       bool
}

func (s *captureSink) ConnectionID() string { return s.id }
func (s *captureSink) WriteAuthorizationProof(_ context.Context, _ AuthorizationProof) error {
	if s.proof {
		return ErrSink
	}
	s.proof = true
	return nil
}
func (s *captureSink) WriteResponse(_ context.Context, b []byte) error {
	if !s.proof || s.responseWritten {
		return ErrSink
	}
	s.responseWritten = true
	s.response = append([]byte(nil), b...)
	return nil
}
func (s *captureSink) WriteTerminalAndClose(_ context.Context, b []byte) error {
	if !s.responseWritten || s.closed {
		return ErrSink
	}
	if s.failTerminal {
		return ErrSink
	}
	s.terminal = append([]byte(nil), b...)
	s.closed = true
	return nil
}

func dispatchFixture(t *testing.T, transport *Transport, transaction string) (Dispatcher, DispatchInput, protocol.Challenge, *captureSink) {
	t.Helper()
	now := time.Date(2026, 8, 3, 0, 1, 0, 0, time.UTC)
	parts := [][]byte{[]byte("system"), []byte("ordinary review text")}
	req := fixtureRequest(parts)
	req.Authority.Nonce, req.Authority.IssuedAt, req.Authority.ExpiresAt = transaction, now.Add(-time.Minute).Format(time.RFC3339), now.Add(time.Minute).Format(time.RFC3339)
	req.Authority.PolicySHA256 = protocol.Digest(policyFixture())
	body, _ := BuildBody(req, parts)
	peer := authority.Peer{UID: 501, PID: 4321}
	c := protocol.Challenge{SchemaVersion: req.SchemaVersion, Protocol: req.Protocol, Mapping: req.Mapping, OperationFamily: req.OperationFamily, SubstrateAuthority: req.SubstrateAuthority, TransactionID: transaction, ConnectionNonceSHA256: req.Authority.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: protocol.Digest(body), Destination: req.Destination, Method: req.Method, Path: req.Path, Models: append([]string(nil), req.Models...), Scope: req.Scope, DaemonBuildSHA256: req.Authority.DaemonBuildSHA256, ScannerBuildSHA256: req.Authority.ScannerBuildSHA256, PolicySHA256: req.Authority.PolicySHA256, Nonce: req.Authority.Nonce, Sequence: req.Authority.Sequence, BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, IssuedAt: req.Authority.IssuedAt, ExpiresAt: req.Authority.ExpiresAt, Limits: req.Limits, PriorChainDigest: req.Authority.PriorChainDigest, AllocationHelloSHA256: req.Authority.AllocationHelloSHA256, DispatchProposalSHA256: req.Authority.DispatchProposalSHA256}
	manager, err := authority.NewManager(authority.Config{BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, AllowedUIDs: map[uint32]struct{}{peer.UID: {}}, MaxOperations: 8, MaxBytes: 32 << 20, MaxConcurrent: 4, Credential: authority.Credential{Reference: "credential-1", PublicKey: []byte("public"), Algorithm: -7, Generation: 1, RPID: "workflow-authority.designmachines.local", Status: "active", InternalUV: true}}, &providerFIDO{}, &providerMemoryWAL{}, providerClock{now})
	if err != nil {
		t.Fatal(err)
	}
	bound, err := manager.Reserve(context.Background(), req, c, body, peer, "connection-"+transaction)
	if err != nil {
		t.Fatal(err)
	}
	canonical, _ := protocol.CanonicalJSON(bound)
	input := DispatchInput{Request: req, Challenge: bound, Parts: parts, TransactionID: transaction, ConnectionID: "connection-" + transaction, ConsentChallengeDigest: protocol.Digest(canonical), Peer: peer}
	d := Dispatcher{Scanner: BuiltinScanner{}, Policy: policyFixture(), Credentials: staticReader{[]byte("fixture-token-value")}, Transport: transport, Authority: manager, Clock: func() time.Time { return now }}
	return d, input, bound, &captureSink{id: input.ConnectionID}
}

func TestSignedPostSendFailureOutcomesAreContentFree(t *testing.T) {
	var providerRequests atomic.Int32
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		providerRequests.Add(1)
		_, _ = w.Write([]byte(`{"malformed":true}`))
	}))
	defer server.Close()
	providerFailureDispatcher, providerFailureInput, providerFailureChallenge, providerFailureSink := dispatchFixture(t, fixtureTransport(server), "provider-failure")
	providerFailure, err := providerFailureDispatcher.Dispatch(context.Background(), providerFailureInput, providerFailureSink)
	if err != nil {
		t.Fatal(err)
	}
	assertSignedContentFreeTerminal(t, providerFailure, providerFailureChallenge, providerFailureSink, "provider_failure", 73)

	var attempts atomic.Int32
	unknownTransport := &Transport{Origin: "https://fixture.invalid" + protocol.Path, Fixture: true, Timeout: time.Second, DialTLS: func(context.Context, string, string, *tls.Config) (net.Conn, error) {
		attempts.Add(1)
		return nil, errors.New("fixture transport ambiguity")
	}}
	unknownDispatcher, unknownInput, unknownChallenge, unknownSink := dispatchFixture(t, unknownTransport, "provider-unknown")
	unknown, err := unknownDispatcher.Dispatch(context.Background(), unknownInput, unknownSink)
	if err != nil {
		t.Fatal(err)
	}
	if attempts.Load() != 1 {
		t.Fatalf("network attempts=%d", attempts.Load())
	}
	assertSignedContentFreeTerminal(t, unknown, unknownChallenge, unknownSink, "unknown", 74)

	sinkFailureDispatcher, sinkFailureInput, _, sinkFailureSink := dispatchFixture(t, fixtureTransport(server), "terminal-sink-failure")
	sinkFailureSink.failTerminal = true
	if _, err := sinkFailureDispatcher.Dispatch(context.Background(), sinkFailureInput, sinkFailureSink); err != ErrSink {
		t.Fatalf("terminal sink failure=%v", err)
	}
	if providerRequests.Load() != 2 {
		t.Fatalf("provider requests=%d", providerRequests.Load())
	}
	if _, err := sinkFailureDispatcher.Dispatch(context.Background(), sinkFailureInput, &captureSink{id: sinkFailureInput.ConnectionID}); err == nil {
		t.Fatal("terminal sink failure became retryable")
	}
	if providerRequests.Load() != 2 {
		t.Fatal("terminal sink failure replay contacted provider")
	}
}

func assertSignedContentFreeTerminal(t *testing.T, result TerminalResult, challenge protocol.Challenge, sink *captureSink, outcome string, exit int) {
	t.Helper()
	if result.Outcome != outcome || result.ExitCode != exit || !sink.responseWritten || len(sink.response) != 0 || !sink.closed || result.ResponseLength != 0 || result.ResponseSHA256 != protocol.Digest(nil) {
		t.Fatalf("content-free outcome mismatch: %+v sink=%+v", result, sink)
	}
	if result.SelectedModel != nil || result.GenerationID != nil || result.ServingProvider != nil || result.UsageSHA256 != nil || result.Fallback != nil {
		t.Fatal("unverified provenance was inferred")
	}
	input, err := protocol.TerminalSignatureInput(result)
	if err != nil || protocol.VerifyTerminalES256(challenge.ResultSigner.PublicKeySEC1, result.Signature.SignatureDER, input) != nil {
		t.Fatalf("signed terminal invalid: %v", err)
	}
}
func (s *captureSink) Abort() error {
	s.closed = true
	return nil
}

func TestDispatcherRejectsSubstitutionBeforeRealManagerAuthorization(t *testing.T) {
	now := time.Date(2026, 8, 3, 0, 1, 0, 0, time.UTC)
	parts := [][]byte{[]byte("system"), []byte("ordinary review text")}
	req := fixtureRequest(parts)
	req.Authority.IssuedAt = now.Add(-time.Minute).Format(time.RFC3339)
	req.Authority.ExpiresAt = now.Add(time.Minute).Format(time.RFC3339)
	req.Authority.PolicySHA256 = protocol.Digest(policyFixture())
	body, err := BuildBody(req, parts)
	if err != nil {
		t.Fatal(err)
	}
	peer := authority.Peer{UID: 501, PID: 4321}
	c := protocol.Challenge{SchemaVersion: req.SchemaVersion, Protocol: req.Protocol, Mapping: req.Mapping, OperationFamily: req.OperationFamily, SubstrateAuthority: req.SubstrateAuthority, TransactionID: "transaction-01", ConnectionNonceSHA256: req.Authority.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: protocol.Digest(body), Destination: req.Destination, Method: req.Method, Path: req.Path, Models: append([]string(nil), req.Models...), Scope: req.Scope, DaemonBuildSHA256: req.Authority.DaemonBuildSHA256, ScannerBuildSHA256: req.Authority.ScannerBuildSHA256, PolicySHA256: req.Authority.PolicySHA256, Nonce: req.Authority.Nonce, Sequence: req.Authority.Sequence, BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, IssuedAt: req.Authority.IssuedAt, ExpiresAt: req.Authority.ExpiresAt, Limits: req.Limits, PriorChainDigest: req.Authority.PriorChainDigest, AllocationHelloSHA256: req.Authority.AllocationHelloSHA256, DispatchProposalSHA256: req.Authority.DispatchProposalSHA256}
	fido := &providerFIDO{}
	wal := &providerMemoryWAL{}
	manager, err := authority.NewManager(authority.Config{BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, AllowedUIDs: map[uint32]struct{}{peer.UID: {}}, MaxOperations: 8, MaxBytes: 32 << 20, MaxConcurrent: 4, Credential: authority.Credential{Reference: "credential-1", PublicKey: []byte("public"), Algorithm: -7, Generation: 1, RPID: "workflow-authority.designmachines.local", Status: "active", InternalUV: true}}, fido, wal, providerClock{now})
	if err != nil {
		t.Fatal(err)
	}
	bound, err := manager.Reserve(context.Background(), req, c, body, peer, "connection-1")
	if err != nil {
		t.Fatal(err)
	}
	canonical, _ := protocol.CanonicalJSON(bound)
	d := Dispatcher{Scanner: BuiltinScanner{}, Policy: policyFixture(), Credentials: rejectingReader{}, Transport: &Transport{}, Authority: manager, Clock: func() time.Time { return now }}
	base := DispatchInput{Request: req, Challenge: bound, Parts: parts, TransactionID: bound.TransactionID, ConnectionID: "connection-1", ConsentChallengeDigest: protocol.Digest(canonical), Peer: peer}
	mutations := []func(*DispatchInput){
		func(v *DispatchInput) { v.Challenge.Scope.RunID = "other" },
		func(v *DispatchInput) { v.Challenge.Models[0] = "other/model" },
		func(v *DispatchInput) { v.Challenge.DaemonBuildSHA256 = protocol.Digest([]byte("other")) },
		func(v *DispatchInput) { v.Challenge.Nonce = "other-caller-nonce" },
		func(v *DispatchInput) { v.Challenge.AllocationHelloSHA256 = protocol.Digest([]byte("other-hello")) },
		func(v *DispatchInput) { v.Challenge.DispatchProposalSHA256 = protocol.Digest([]byte("other-proposal")) },
		func(v *DispatchInput) { v.ConsentChallengeDigest = protocol.Digest([]byte("other")) },
		func(v *DispatchInput) { v.Request.SubstrateAuthority = "asserted" },
	}
	for i, mutate := range mutations {
		v := base
		v.Challenge = bound
		v.Challenge.Models = append([]string(nil), bound.Models...)
		mutate(&v)
		if _, err := d.Dispatch(context.Background(), v, testSink{"connection-1"}); err != ErrBinding {
			t.Fatalf("case %d: %v", i, err)
		}
	}
	if fido.calls.Load() != 0 {
		t.Fatalf("FIDO called %d times", fido.calls.Load())
	}
}

func TestDispatcherFixtureFinalizesOnceAndClosesTerminal(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "generation-fixture", "model": "openai/gpt-5.6", "provider": "fixture-provider", "usage": map[string]int{"total_tokens": 2}, "choices": []any{map[string]any{"message": map[string]any{"role": "assistant", "content": "exact assistant bytes"}, "finish_reason": "stop"}}})
	}))
	defer server.Close()
	now := time.Date(2026, 8, 3, 0, 1, 0, 0, time.UTC)
	parts := [][]byte{[]byte("system"), []byte("ordinary review text")}
	req := fixtureRequest(parts)
	req.Authority.IssuedAt = now.Add(-time.Minute).Format(time.RFC3339)
	req.Authority.ExpiresAt = now.Add(time.Minute).Format(time.RFC3339)
	req.Authority.PolicySHA256 = protocol.Digest(policyFixture())
	body, _ := BuildBody(req, parts)
	peer := authority.Peer{UID: 501, PID: 4321}
	c := protocol.Challenge{SchemaVersion: req.SchemaVersion, Protocol: req.Protocol, Mapping: req.Mapping, OperationFamily: req.OperationFamily, SubstrateAuthority: req.SubstrateAuthority, TransactionID: "transaction-positive", ConnectionNonceSHA256: req.Authority.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: protocol.Digest(body), Destination: req.Destination, Method: req.Method, Path: req.Path, Models: append([]string(nil), req.Models...), Scope: req.Scope, DaemonBuildSHA256: req.Authority.DaemonBuildSHA256, ScannerBuildSHA256: req.Authority.ScannerBuildSHA256, PolicySHA256: req.Authority.PolicySHA256, Nonce: req.Authority.Nonce, Sequence: req.Authority.Sequence, BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, IssuedAt: req.Authority.IssuedAt, ExpiresAt: req.Authority.ExpiresAt, Limits: req.Limits, PriorChainDigest: req.Authority.PriorChainDigest, AllocationHelloSHA256: req.Authority.AllocationHelloSHA256, DispatchProposalSHA256: req.Authority.DispatchProposalSHA256}
	fido := &providerFIDO{}
	manager, err := authority.NewManager(authority.Config{BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, AllowedUIDs: map[uint32]struct{}{peer.UID: {}}, MaxOperations: 8, MaxBytes: 32 << 20, MaxConcurrent: 4, Credential: authority.Credential{Reference: "credential-1", PublicKey: []byte("public"), Algorithm: -7, Generation: 1, RPID: "workflow-authority.designmachines.local", Status: "active", InternalUV: true}}, fido, &providerMemoryWAL{}, providerClock{now})
	if err != nil {
		t.Fatal(err)
	}
	bound, err := manager.Reserve(context.Background(), req, c, body, peer, "connection-positive")
	if err != nil {
		t.Fatal(err)
	}
	canonical, _ := protocol.CanonicalJSON(bound)
	input := DispatchInput{Request: req, Challenge: bound, Parts: parts, TransactionID: bound.TransactionID, ConnectionID: "connection-positive", ConsentChallengeDigest: protocol.Digest(canonical), Peer: peer}
	d := Dispatcher{Scanner: BuiltinScanner{}, Policy: policyFixture(), Credentials: staticReader{[]byte("fixture-token-value")}, Transport: fixtureTransport(server), Authority: manager, Clock: func() time.Time { return now }}
	sink := &captureSink{id: "connection-positive"}
	result, err := d.Dispatch(context.Background(), input, sink)
	if err != nil {
		t.Fatal(err)
	}
	if result.Outcome != "verified" || !sink.closed || len(sink.response) == 0 || len(sink.terminal) == 0 || requests.Load() != 1 {
		t.Fatalf("result=%v closed=%v requests=%d", result.Outcome, sink.closed, requests.Load())
	}
	if string(sink.response) != "exact assistant bytes" || result.ResponseSHA256 != protocol.Digest(sink.response) || result.ResponseLength != int64(len(sink.response)) {
		t.Fatalf("delivered response binding mismatch: %q %+v", sink.response, result)
	}
	if result.GenerationID == nil || *result.GenerationID != "generation-fixture" || result.ServingProvider == nil || *result.ServingProvider != "fixture-provider" || result.UsageSHA256 == nil || *result.UsageSHA256 != protocol.Digest([]byte(`{"total_tokens":2}`)) || result.Fallback == nil || *result.Fallback {
		t.Fatalf("provider provenance mismatch: %+v", result)
	}
	terminalInput, err := protocol.TerminalSignatureInput(result)
	if err != nil || protocol.VerifyTerminalES256(bound.ResultSigner.PublicKeySEC1, result.Signature.SignatureDER, terminalInput) != nil {
		t.Fatalf("provider terminal signer projection mismatch: %v", err)
	}
	canonicalResult, _ := protocol.CanonicalJSON(result)
	if string(canonicalResult) != string(sink.terminal) {
		t.Fatal("provider terminal bytes differ from signed typed result")
	}
	if _, err := d.Dispatch(context.Background(), input, &captureSink{id: "connection-positive"}); err == nil {
		t.Fatal("replay accepted")
	}
	if requests.Load() != 1 {
		t.Fatal("replay contacted provider")
	}
}

func TestProviderProvenanceRejectsInvalidMetadataUsageAndChoiceErrors(t *testing.T) {
	if providerMetadata.MatchString("") || providerMetadata.MatchString("bad provider") || providerMetadata.MatchString(repeat("a", 257)) {
		t.Fatal("invalid provider metadata accepted")
	}
	canonical, err := canonicalUsage(json.RawMessage(`{"total_tokens":2,"prompt_tokens":1}`))
	if err != nil || string(canonical) != `{"prompt_tokens":1,"total_tokens":2}` {
		t.Fatalf("canonical usage=%q err=%v", canonical, err)
	}
	for _, raw := range []string{"", "null", "[]", `"usage"`} {
		if _, err := canonicalUsage(json.RawMessage(raw)); err == nil {
			t.Fatalf("invalid usage accepted: %q", raw)
		}
	}
	stop, length, filtered := "stop", "length", "content_filter"
	errorReason, unknown, toolCalls := "error", "future_reason", "tool_calls"
	for _, choice := range []providerChoice{{FinishReason: &stop}, {FinishReason: &length}, {FinishReason: &filtered, Error: json.RawMessage("null")}} {
		if !successfulFinishReason(choice) {
			t.Fatalf("completed choice rejected: %+v", choice)
		}
	}
	for _, choice := range []providerChoice{{}, {FinishReason: &errorReason}, {FinishReason: &unknown}, {FinishReason: &toolCalls}, {FinishReason: &stop, Error: json.RawMessage(`{"code":500}`)}} {
		if successfulFinishReason(choice) {
			t.Fatalf("incomplete or failed choice accepted: %+v", choice)
		}
	}
}

func TestMutableAssistantContentDecodeAndWipe(t *testing.T) {
	raw := json.RawMessage(`"line\nquote:\" globe:\uD83C\uDF0D"`)
	decoded, err := decodeJSONString(raw)
	if err != nil || string(decoded) != "line\nquote:\" globe:🌍" {
		t.Fatalf("decoded=%q err=%v", decoded, err)
	}
	zero(decoded)
	for i, value := range decoded {
		if value != 0 {
			t.Fatalf("decoded byte %d was not wiped", i)
		}
	}
	empty, err := decodeJSONString(json.RawMessage(`""`))
	if err != nil || len(empty) != 0 {
		t.Fatalf("valid empty JSON string decode=%q err=%v", empty, err)
	}
	for _, invalid := range []json.RawMessage{
		json.RawMessage(`null`),
		json.RawMessage(`"bad\xescape"`),
		json.RawMessage(`"unpaired-high:\uD83C"`),
		json.RawMessage(`"unpaired-low:\uDF0D"`),
		json.RawMessage(`"bad-pair:\uD83C\u0041"`),
	} {
		if decoded, decodeErr := decodeJSONString(invalid); decodeErr == nil {
			zero(decoded)
			t.Fatalf("invalid JSON string accepted: %q", invalid)
		}
	}
	response := providerResponse{Usage: json.RawMessage(`{"total_tokens":2}`), Choices: []providerChoice{{Error: json.RawMessage(`{"code":500}`), Message: providerMessage{Content: append(json.RawMessage(nil), raw...)}}}}
	zeroProviderResponse(&response)
	for _, buffer := range [][]byte{response.Usage, response.Choices[0].Error, response.Choices[0].Message.Content} {
		for i, value := range buffer {
			if value != 0 {
				t.Fatalf("provider buffer byte %d was not wiped", i)
			}
		}
	}
}

func TestDeliveredChoiceRequiresExactAssistantRole(t *testing.T) {
	stop := "stop"
	content := json.RawMessage(`"answer"`)
	if !validDeliveredChoice(providerChoice{FinishReason: &stop, Message: providerMessage{Role: "assistant", Content: content}}) {
		t.Fatal("exact assistant choice rejected")
	}
	for _, role := range []string{"", "user", "Assistant", " assistant"} {
		if validDeliveredChoice(providerChoice{FinishReason: &stop, Message: providerMessage{Role: role, Content: content}}) {
			t.Fatalf("invalid role accepted: %q", role)
		}
	}
}

func TestCredentialRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "target")
	_ = os.WriteFile(target, []byte("fixture"), 0o600)
	link := filepath.Join(dir, "link")
	if os.Symlink(target, link) != nil {
		t.Skip("symlink unavailable")
	}
	if _, err := (FileCredentialReader{Path: link, FixtureMode: true}).Read(context.Background()); err == nil {
		t.Fatal("symlink accepted")
	}
}

func TestProductionTransportHasNoProxyOrRedirect(t *testing.T) {
	tr := ProductionTransport()
	if tr.Origin != ProductionURL {
		t.Fatal(tr.Origin)
	}
	if tr.DialTLS == nil || tr.TLSConfig == nil {
		t.Fatal("production TLS unavailable")
	}
	credential := &Credential{bytes: []byte("production-fixture-sentinel")}
	var address string
	tr.DialTLS = func(_ context.Context, _, candidate string, _ *tls.Config) (net.Conn, error) {
		address = candidate
		return nil, errors.New("stop before network")
	}
	if _, err := tr.Send(context.Background(), credential, []byte("{}")); err == nil {
		t.Fatal("injected dial failure accepted")
	}
	if address != "openrouter.ai:443" {
		t.Fatalf("production address=%q", address)
	}
}

func TestTransportCancellationClosesPostDialIO(t *testing.T) {
	client, server := net.Pipe()
	defer server.Close()
	ctx, cancel := context.WithCancel(context.Background())
	tr := &Transport{Origin: "https://fixture.invalid" + protocol.Path, Fixture: true, Timeout: time.Minute, DialTLS: func(context.Context, string, string, *tls.Config) (net.Conn, error) {
		return client, nil
	}}
	done := make(chan error, 1)
	go func() {
		_, err := tr.Send(ctx, &Credential{bytes: []byte("fixture"), fixture: true}, []byte("{}"))
		done <- err
	}()
	go io.Copy(io.Discard, server)
	cancel()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("cancelled transport succeeded")
		}
	case <-time.After(time.Second):
		t.Fatal("cancellation did not close post-dial I/O")
	}
}

func TestResponseBound(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests := make([]byte, maxProviderResponse+1)
		_, _ = w.Write(requests)
	}))
	defer server.Close()
	c := &Credential{bytes: []byte("fixture"), fixture: true}
	tr := fixtureTransport(server)
	if _, err := tr.Send(context.Background(), c, []byte("{}")); err == nil {
		t.Fatal("oversize accepted")
	}
}

func fixtureTransport(server *httptest.Server) *Transport {
	return &Transport{Origin: server.URL + protocol.Path, Fixture: true, TLSConfig: server.Client().Transport.(*http.Transport).TLSClientConfig, Timeout: time.Second}
}

func TestOriginalSinkTerminalRequiresEOFAndCannotBeRetrievedAgain(t *testing.T) {
	server, client := net.Pipe()
	sink := &OriginalConnectionSink{ID: "connection", Conn: server}
	received := make(chan []byte, 1)
	go func() { b, _ := io.ReadAll(client); received <- b }()
	proof := AuthorizationProof{SchemaVersion: 1, Protocol: protocol.Name, Type: "authorization_proof", ChallengeSHA256: protocol.Digest([]byte("challenge")), AuthorityAssertion: FIDOAssertion{Kind: "fido2-es256", CredentialID: "Y3JlZA", AuthenticatorData: "YXV0aA", ClientDataJSON: "Y2xpZW50", SignatureDER: "c2ln", UserPresence: true, UserVerification: true}}
	if err := sink.WriteAuthorizationProof(context.Background(), proof); err != nil {
		t.Fatal(err)
	}
	if err := sink.WriteResponse(context.Background(), []byte("response")); err != nil {
		t.Fatal(err)
	}
	if err := sink.WriteTerminalAndClose(context.Background(), []byte(`{"terminal":true}`)); err != nil {
		t.Fatal(err)
	}
	if len(<-received) == 0 || !sink.closed {
		t.Fatal("terminal EOF not observed")
	}
	if err := sink.WriteTerminalAndClose(context.Background(), []byte("again")); err == nil {
		t.Fatal("terminal retrieved twice")
	}
}

func TestOriginalSinkContentFreeOutcomeWritesExactlyZeroLengthResponseFrame(t *testing.T) {
	server, client := net.Pipe()
	sink := &OriginalConnectionSink{ID: "connection", Conn: server}
	received := make(chan []byte, 1)
	go func() { b, _ := io.ReadAll(client); received <- b }()
	proof := AuthorizationProof{SchemaVersion: 1, Protocol: protocol.Name, Type: "authorization_proof", ChallengeSHA256: protocol.Digest([]byte("challenge")), AuthorityAssertion: FIDOAssertion{Kind: "fido2-es256", CredentialID: "Y3JlZA", AuthenticatorData: "YXV0aA", ClientDataJSON: "Y2xpZW50", SignatureDER: "c2ln", UserPresence: true, UserVerification: true}}
	proofRaw, _ := protocol.CanonicalJSON(proof)
	if err := sink.WriteAuthorizationProof(context.Background(), proof); err != nil {
		t.Fatal(err)
	}
	if err := sink.WriteResponse(context.Background(), nil); err != nil {
		t.Fatal(err)
	}
	terminal := []byte(`{"outcome":"unknown"}`)
	if err := sink.WriteTerminalAndClose(context.Background(), terminal); err != nil {
		t.Fatal(err)
	}
	wire := <-received
	offset := 4 + len(proofRaw)
	if len(wire) < offset+8 || !bytes.Equal(wire[offset:offset+8], make([]byte, 8)) {
		t.Fatalf("missing exact zero-length response frame: %x", wire[offset:])
	}
	terminalLength := int(binary.BigEndian.Uint32(wire[offset+8 : offset+12]))
	if terminalLength != len(terminal) || !bytes.Equal(wire[offset+12:], terminal) {
		t.Fatal("terminal did not immediately follow zero-length response frame")
	}
}

func TestOriginalSinkCancellationForcesEOF(t *testing.T) {
	server, client := net.Pipe()
	sink := &OriginalConnectionSink{ID: "connection", Conn: server, proofUsed: true, used: true}
	received := make(chan error, 1)
	go func() {
		_, err := io.ReadAll(client)
		received <- err
	}()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := sink.WriteTerminalAndClose(ctx, []byte(`{"terminal":true}`)); err == nil {
		t.Fatal("cancelled terminal accepted")
	}
	select {
	case err := <-received:
		if err != nil {
			t.Fatalf("client did not receive EOF: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled terminal left connection open")
	}
	if !sink.closed {
		t.Fatal("cancelled sink not closed")
	}
}

func TestNoKeyShapedSentinelsInResultTypes(t *testing.T) {
	raw, _ := json.Marshal(TerminalResult{})
	sum := sha256.Sum256(raw)
	if containsBytes(raw, []byte("credential")) || containsBytes(raw, []byte("api_key")) || sum == ([32]byte{}) {
		t.Fatal("secret surface in terminal")
	}
}
