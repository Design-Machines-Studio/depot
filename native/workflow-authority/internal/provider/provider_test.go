package provider

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
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
	return protocol.Request{SchemaVersion: 1, Protocol: protocol.Name, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: []string{"openai/gpt-5.6", "z-ai/glm-5.2"}, Parts: declared, Scope: protocol.Scope{Repository: "repo", RunID: "run", Lane: "lane", Candidate: "candidate", Workload: "workload"}, Authority: protocol.Authority{DaemonBuildSHA256: d, ScannerBuildSHA256: ScannerBuildDigest, PolicySHA256: d, Nonce: "nonce", Sequence: 1, BootID: "boot", SessionID: "session", ConnectionNonceSHA256: d, IssuedAt: "2026-08-03T00:00:00Z", ExpiresAt: "2026-08-03T00:02:00Z", PriorChainDigest: d}, Limits: protocol.Limits{MaxRequestBytes: 8388608, MaxResponseBytes: 8388608, MaxParts: 256, MaxPendingPerPeer: 4, MaxPendingRepository: 16, MaxPendingDaemon: 64}}
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
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "generation-fixture", "model": "z-ai/glm-5.2", "provider": "fixture", "usage": map[string]int{"total_tokens": 2}})
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
		{[]byte("AKIAABCDEFGHIJKLMNOP")},
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

type captureSink struct {
	id                 string
	proof              bool
	response, terminal []byte
	closed             bool
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
	if !s.proof || s.response != nil {
		return ErrSink
	}
	s.response = append([]byte(nil), b...)
	return nil
}
func (s *captureSink) WriteTerminalAndClose(_ context.Context, b []byte) error {
	if s.response == nil || s.closed {
		return ErrSink
	}
	s.terminal = append([]byte(nil), b...)
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
	c := protocol.Challenge{SchemaVersion: req.SchemaVersion, Protocol: req.Protocol, Mapping: req.Mapping, OperationFamily: req.OperationFamily, SubstrateAuthority: req.SubstrateAuthority, TransactionID: "transaction-01", ConnectionNonceSHA256: req.Authority.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: protocol.Digest(body), Destination: req.Destination, Method: req.Method, Path: req.Path, Models: append([]string(nil), req.Models...), Scope: req.Scope, DaemonBuildSHA256: req.Authority.DaemonBuildSHA256, ScannerBuildSHA256: req.Authority.ScannerBuildSHA256, PolicySHA256: req.Authority.PolicySHA256, Nonce: req.Authority.Nonce, Sequence: req.Authority.Sequence, BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, IssuedAt: req.Authority.IssuedAt, ExpiresAt: req.Authority.ExpiresAt, Limits: req.Limits, PriorChainDigest: req.Authority.PriorChainDigest}
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
	mutations := []func(*DispatchInput){func(v *DispatchInput) { v.Challenge.Scope.RunID = "other" }, func(v *DispatchInput) { v.Challenge.Models[0] = "other/model" }, func(v *DispatchInput) { v.Challenge.DaemonBuildSHA256 = protocol.Digest([]byte("other")) }, func(v *DispatchInput) { v.ConsentChallengeDigest = protocol.Digest([]byte("other")) }, func(v *DispatchInput) { v.Request.SubstrateAuthority = "asserted" }}
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
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "generation-fixture", "model": "openai/gpt-5.6", "provider": "fixture-provider", "usage": map[string]int{"total_tokens": 2}})
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
	c := protocol.Challenge{SchemaVersion: req.SchemaVersion, Protocol: req.Protocol, Mapping: req.Mapping, OperationFamily: req.OperationFamily, SubstrateAuthority: req.SubstrateAuthority, TransactionID: "transaction-positive", ConnectionNonceSHA256: req.Authority.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: protocol.Digest(body), Destination: req.Destination, Method: req.Method, Path: req.Path, Models: append([]string(nil), req.Models...), Scope: req.Scope, DaemonBuildSHA256: req.Authority.DaemonBuildSHA256, ScannerBuildSHA256: req.Authority.ScannerBuildSHA256, PolicySHA256: req.Authority.PolicySHA256, Nonce: req.Authority.Nonce, Sequence: req.Authority.Sequence, BootID: req.Authority.BootID, SessionID: req.Authority.SessionID, IssuedAt: req.Authority.IssuedAt, ExpiresAt: req.Authority.ExpiresAt, Limits: req.Limits, PriorChainDigest: req.Authority.PriorChainDigest}
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
	if _, err := d.Dispatch(context.Background(), input, &captureSink{id: "connection-positive"}); err == nil {
		t.Fatal("replay accepted")
	}
	if requests.Load() != 1 {
		t.Fatal("replay contacted provider")
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

func TestNoKeyShapedSentinelsInResultTypes(t *testing.T) {
	raw, _ := json.Marshal(TerminalResult{})
	sum := sha256.Sum256(raw)
	if containsBytes(raw, []byte("credential")) || containsBytes(raw, []byte("api_key")) || sum == ([32]byte{}) {
		t.Fatal("secret surface in terminal")
	}
}
