package ipc

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

type fixtureGuard struct {
	net.Conn
	failAt, calls int
}

func (c *fixtureGuard) Receive(target []byte) (int, error) {
	c.calls++
	if c.failAt > 0 && c.calls == c.failAt {
		return 0, errors.New("ancillary_data_rejected")
	}
	return c.Conn.Read(target)
}

type fixturePeers struct {
	peer authority.Peer
	err  error
}

func (p fixturePeers) Authenticate(net.Conn) (authority.Peer, error) { return p.peer, p.err }

type fixtureAllocator struct {
	allocation Allocation
	consumed   []string
	closed     int
}

func (a *fixtureAllocator) Allocate(context.Context) (Allocation, error) { return a.allocation, nil }
func (a *fixtureAllocator) Consume(_ context.Context, _ Allocation, reason string) error {
	a.consumed = append(a.consumed, reason)
	return nil
}
func (a *fixtureAllocator) Close() error { a.closed++; return nil }

type fixtureManager struct {
	challenge protocol.Challenge
	cancelled int
	shutdown  int
}

func (m *fixtureManager) Reserve(_ context.Context, _ protocol.Request, challenge protocol.Challenge, _ []byte, _ authority.Peer, _ string) (protocol.Challenge, error) {
	m.challenge = challenge
	return challenge, nil
}
func (m *fixtureManager) Cancel(context.Context, string) error { m.cancelled++; return nil }
func (m *fixtureManager) Shutdown(context.Context) error       { m.shutdown++; return nil }

type fixtureDispatcher struct {
	called       int
	connectionID string
	fail         bool
}

func (d *fixtureDispatcher) Dispatch(ctx context.Context, input provider.DispatchInput, sink provider.ResponseSink) (provider.TerminalResult, error) {
	d.called++
	d.connectionID = sink.ConnectionID()
	if d.fail {
		return provider.TerminalResult{}, provider.ErrTransport
	}
	proof := provider.AuthorizationProof{SchemaVersion: 1, Protocol: protocol.Name, Type: "authorization_proof", ChallengeSHA256: input.ConsentChallengeDigest}
	if err := sink.WriteAuthorizationProof(ctx, proof); err != nil {
		return provider.TerminalResult{}, err
	}
	if err := sink.WriteResponse(ctx, []byte("fixture-response")); err != nil {
		return provider.TerminalResult{}, err
	}
	if err := sink.WriteTerminalAndClose(ctx, []byte(`{"fixture":"terminal"}`)); err != nil {
		return provider.TerminalResult{}, err
	}
	return provider.TerminalResult{}, nil
}

func fixtureServer(now time.Time, failAt int) (*Server, *fixtureAllocator, *fixtureManager, *fixtureDispatcher) {
	digest := protocol.Digest([]byte("fixture"))
	hello := protocol.AuthorityHello{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.AuthorityHelloType, DaemonBuildSHA256: digest, ScannerBuildSHA256: digest, PolicySHA256: digest, BootID: "boot-01", SessionID: "session-01", Sequence: 1, IssuedAt: now.Format(time.RFC3339), ExpiresAt: now.Add(120 * time.Second).Format(time.RFC3339), PriorChainDigest: protocol.Digest(nil), ConnectionNonceSHA256: digest, Limits: protocol.FrozenAllocationLimits()}
	allocator := &fixtureAllocator{allocation: Allocation{Hello: hello, ConnectionID: "connection-fixture"}}
	manager := &fixtureManager{}
	dispatcher := &fixtureDispatcher{}
	server := &Server{Allocator: allocator, Peers: fixturePeers{peer: authority.Peer{UID: 501, PID: 42}}, Guard: func(conn net.Conn) (GuardedConn, error) { return &fixtureGuard{Conn: conn, failAt: failAt}, nil }, Manager: manager, Dispatcher: dispatcher, Clock: func() time.Time { return now }, QueueDepth: 1}
	return server, allocator, manager, dispatcher
}

func writeFixtureRequest(t *testing.T, conn net.Conn, hello protocol.AuthorityHello, validAck bool) {
	t.Helper()
	helloRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		t.Fatal(err)
	}
	var observed protocol.AuthorityHello
	if err := protocol.DecodeClosed(helloRaw, &observed); err != nil || observed.Sequence != hello.Sequence {
		t.Fatalf("hello = %#v, %v", observed, err)
	}
	part := []byte("fixture prompt")
	proposal := protocol.DispatchProposal{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.DispatchProposalType, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: []string{"model/fixture"}, Parts: []protocol.Part{{Role: "user", ContentLength: int64(len(part)), ContentSHA256: protocol.Digest(part)}}, Scope: protocol.Scope{Repository: "repo", RunID: "run", Lane: "lane", Candidate: "candidate", Workload: "workload"}, CallerNonce: "caller-nonce", AuthorityHelloSHA256: protocol.Digest(helloRaw)}
	proposalRaw, _ := protocol.CanonicalJSON(proposal)
	if err := protocol.WriteFrame(conn, proposalRaw); err != nil {
		t.Fatal(err)
	}
	var length [8]byte
	binary.BigEndian.PutUint64(length[:], uint64(len(part)))
	if _, err := conn.Write(append(length[:], part...)); err != nil {
		t.Fatal(err)
	}
	challengeRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		t.Fatal(err)
	}
	var challenge protocol.Challenge
	if err := protocol.DecodeClosed(challengeRaw, &challenge); err != nil {
		t.Fatal(err)
	}
	digest := protocol.Digest(challengeRaw)
	if !validAck {
		digest = protocol.Digest([]byte("wrong"))
	}
	ack, _ := protocol.CanonicalJSON(protocol.ConsentAck{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.ConsentAckType, ChallengeSHA256: digest})
	if err := protocol.WriteFrame(conn, ack); err != nil {
		t.Fatal(err)
	}
}

func TestServerWritesHelloBeforeCallerBytesAndKeepsResponseOnConnection(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 0)
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	writeFixtureRequest(t, client, allocator.allocation.Hello, true)
	if _, err := protocol.ReadFrame(client); err != nil {
		t.Fatal("authorization proof:", err)
	}
	var length [8]byte
	if _, err := io.ReadFull(client, length[:]); err != nil || binary.BigEndian.Uint64(length[:]) != uint64(len("fixture-response")) {
		t.Fatalf("response header: %v", err)
	}
	response := make([]byte, len("fixture-response"))
	if _, err := io.ReadFull(client, response); err != nil || string(response) != "fixture-response" {
		t.Fatalf("response: %q %v", response, err)
	}
	if _, err := protocol.ReadFrame(client); err != nil {
		t.Fatal("terminal:", err)
	}
	<-done
	if dispatcher.called != 1 || dispatcher.connectionID != allocator.allocation.ConnectionID {
		t.Fatal("dispatcher did not bind original connection")
	}
	if len(allocator.consumed) != 1 || allocator.consumed[0] != "terminal_complete" {
		t.Fatalf("consume = %#v", allocator.consumed)
	}
}

func TestServerRejectsWrongConsentBeforeDispatch(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, manager, dispatcher := fixtureServer(now, 0)
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	writeFixtureRequest(t, client, allocator.allocation.Hello, false)
	raw, err := protocol.ReadFrame(client)
	if err != nil {
		t.Fatal(err)
	}
	var safe protocol.SafeError
	if protocol.DecodeClosed(raw, &safe) != nil || safe.Code != "consent_connection_invalid" {
		t.Fatalf("safe error = %#v", safe)
	}
	<-done
	if manager.cancelled != 1 || dispatcher.called != 0 {
		t.Fatal("invalid consent reached dispatch")
	}
}

func TestServerRejectsAlteredPartBeforeReservation(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, manager, dispatcher := fixtureServer(now, 0)
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	helloRaw, err := protocol.ReadFrame(client)
	if err != nil {
		t.Fatal(err)
	}
	declared := []byte("expected")
	altered := []byte("tampered")
	proposal := protocol.DispatchProposal{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.DispatchProposalType, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: []string{"model/fixture"}, Parts: []protocol.Part{{Role: "user", ContentLength: int64(len(declared)), ContentSHA256: protocol.Digest(declared)}}, Scope: protocol.Scope{Repository: "repo", RunID: "run", Lane: "lane", Candidate: "candidate", Workload: "workload"}, CallerNonce: "caller-nonce", AuthorityHelloSHA256: protocol.Digest(helloRaw)}
	proposalRaw, _ := protocol.CanonicalJSON(proposal)
	if err := protocol.WriteFrame(client, proposalRaw); err != nil {
		t.Fatal(err)
	}
	var length [8]byte
	binary.BigEndian.PutUint64(length[:], uint64(len(altered)))
	if _, err := client.Write(append(length[:], altered...)); err != nil {
		t.Fatal(err)
	}
	raw, err := protocol.ReadFrame(client)
	if err != nil {
		t.Fatal(err)
	}
	var safe protocol.SafeError
	if protocol.DecodeClosed(raw, &safe) != nil || safe.Code != "authorization_declined" {
		t.Fatalf("safe error = %#v", safe)
	}
	<-done
	if manager.challenge.TransactionID != "" || dispatcher.called != 0 || len(allocator.consumed) != 1 || allocator.consumed[0] != "parts_invalid" {
		t.Fatal("altered body crossed reservation boundary")
	}
}

func TestServerRejectsUnauthorizedPeerWithoutHello(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 0)
	server.Peers = fixturePeers{err: authority.ErrDenied}
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	_ = client.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := protocol.ReadFrame(client); err == nil {
		t.Fatal("unauthorized peer received hello")
	}
	<-done
	if len(allocator.consumed) != 0 || dispatcher.called != 0 {
		t.Fatal("unauthorized peer allocated authority")
	}
}

func TestServerRejectsAncillaryDataAndConsumesAllocation(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 1)
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	if _, err := protocol.ReadFrame(client); err != nil {
		t.Fatal(err)
	}
	_ = protocol.WriteFrame(client, []byte(`{}`))
	<-done
	if dispatcher.called != 0 || len(allocator.consumed) != 1 || allocator.consumed[0] != "proposal_read_failed" {
		t.Fatalf("consume = %#v", allocator.consumed)
	}
}

func TestServerEOFConsumesAllocationWithoutDispatch(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 0)
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	if _, err := protocol.ReadFrame(client); err != nil {
		t.Fatal(err)
	}
	_ = client.Close()
	<-done
	if dispatcher.called != 0 || len(allocator.consumed) != 1 || allocator.consumed[0] != "proposal_read_failed" {
		t.Fatalf("consume = %#v", allocator.consumed)
	}
}

func TestServerStaleAllocationIsConsumedBeforeCallerInput(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 0)
	server.Clock = func() time.Time { return now.Add(121 * time.Second) }
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	_ = client.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := protocol.ReadFrame(client); err == nil {
		t.Fatal("stale allocation emitted an authority hello")
	}
	<-done
	if dispatcher.called != 0 || len(allocator.consumed) != 1 || allocator.consumed[0] != "hello_write_failed" {
		t.Fatalf("consume = %#v", allocator.consumed)
	}
}

func TestServerNeverWritesUnsignedSafeErrorAfterDispatcher(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, _, dispatcher := fixtureServer(now, 0)
	dispatcher.fail = true
	daemon, client := net.Pipe()
	done := make(chan struct{})
	go func() { server.handle(context.Background(), daemon); close(done) }()
	writeFixtureRequest(t, client, allocator.allocation.Hello, true)
	_ = client.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := protocol.ReadFrame(client); err == nil {
		t.Fatal("dispatcher failure emitted unsigned retry frame")
	}
	<-done
	if len(allocator.consumed) != 1 || allocator.consumed[0] != "dispatch_ambiguous" {
		t.Fatalf("consume = %#v", allocator.consumed)
	}
}

type failingListener struct{ err error }

func (l failingListener) Accept() (net.Conn, error) { return nil, l.err }
func (failingListener) Close() error                { return nil }
func (failingListener) Addr() net.Addr              { return fixtureAddr("fixture") }

type fixtureAddr string

func (a fixtureAddr) Network() string { return "fixture" }
func (a fixtureAddr) String() string  { return string(a) }

func TestServerUnexpectedAcceptFailureShutsDownDependencies(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	server, allocator, manager, _ := fixtureServer(now, 0)
	want := errors.New("accept failed")
	if err := server.Serve(context.Background(), failingListener{err: want}); !errors.Is(err, want) {
		t.Fatalf("serve = %v", err)
	}
	if manager.shutdown != 1 || allocator.closed != 1 {
		t.Fatalf("shutdown manager=%d allocator=%d", manager.shutdown, allocator.closed)
	}
}
