package ipc

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"sync"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

type GuardedConn interface {
	net.Conn
	Receive([]byte) (int, error)
}

type PeerAuthenticator interface {
	Authenticate(net.Conn) (authority.Peer, error)
}

type AuthorityManager interface {
	Reserve(context.Context, protocol.Request, protocol.Challenge, []byte, authority.Peer, string) (protocol.Challenge, error)
	Cancel(context.Context, string) error
	Shutdown(context.Context) error
}

type ProviderDispatcher interface {
	Dispatch(context.Context, provider.DispatchInput, provider.ResponseSink) (provider.TerminalResult, error)
}

type ConnGuard func(net.Conn) (GuardedConn, error)

type Server struct {
	Allocator  Allocator
	Peers      PeerAuthenticator
	Guard      ConnGuard
	Manager    AuthorityManager
	Dispatcher ProviderDispatcher
	Clock      func() time.Time
	QueueDepth int

	mu           sync.Mutex
	active       GuardedConn
	stopped      bool
	shutdownOnce sync.Once
	shutdownErr  error
	serveCancel  context.CancelFunc
	serveDone    chan struct{}
}

func (s *Server) Serve(ctx context.Context, listener net.Listener) error {
	if listener == nil || s.Allocator == nil || s.Peers == nil || s.Guard == nil || s.Manager == nil || s.Dispatcher == nil || s.Clock == nil || s.QueueDepth < 1 {
		return provider.ErrStartup
	}
	serveContext, cancel := context.WithCancel(ctx)
	s.mu.Lock()
	if s.stopped || s.serveCancel != nil {
		s.mu.Unlock()
		cancel()
		return provider.ErrStartup
	}
	done := make(chan struct{})
	s.serveCancel = cancel
	s.serveDone = done
	s.mu.Unlock()
	defer func() {
		cancel()
		close(done)
	}()
	queue := make(chan net.Conn, s.QueueDepth)
	workerDone := make(chan struct{})
	go func() {
		defer close(workerDone)
		for conn := range queue {
			s.handle(serveContext, conn)
		}
	}()
	go func() {
		<-serveContext.Done()
		_ = listener.Close()
		s.mu.Lock()
		if s.active != nil {
			_ = s.active.Close()
		}
		s.mu.Unlock()
	}()
	for {
		conn, err := listener.Accept()
		if err != nil {
			close(queue)
			<-workerDone
			if serveContext.Err() != nil || s.isStopped() || errors.Is(err, net.ErrClosed) {
				return s.shutdown(context.Background())
			}
			_ = s.shutdown(context.Background())
			return err
		}
		select {
		case queue <- conn:
		default:
			_ = conn.Close()
		}
	}
}

func (s *Server) Stop(ctx context.Context, listener net.Listener) error {
	s.mu.Lock()
	s.stopped = true
	cancel := s.serveCancel
	done := s.serveDone
	active := s.active
	s.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	if listener != nil {
		_ = listener.Close()
	}
	if active != nil {
		_ = active.Close()
	}
	if done == nil {
		return provider.ErrStartup
	}
	select {
	case <-done:
		return s.shutdownErr
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (s *Server) isStopped() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.stopped
}

func (s *Server) shutdown(ctx context.Context) error {
	s.shutdownOnce.Do(func() {
		managerErr := s.Manager.Shutdown(ctx)
		allocatorErr := s.Allocator.Close()
		if managerErr != nil {
			s.shutdownErr = managerErr
		} else {
			s.shutdownErr = allocatorErr
		}
	})
	return s.shutdownErr
}

func (s *Server) handle(ctx context.Context, raw net.Conn) {
	defer raw.Close()
	peer, err := s.Peers.Authenticate(raw)
	if err != nil {
		return
	}
	conn, err := s.Guard(raw)
	if err != nil {
		return
	}
	s.mu.Lock()
	s.active = conn
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		if s.active == conn {
			s.active = nil
		}
		s.mu.Unlock()
	}()
	allocation, err := s.Allocator.Allocate(ctx)
	if err != nil {
		return
	}
	reason := "connection_abandoned"
	defer func() { _ = s.Allocator.Consume(context.Background(), allocation, reason) }()
	expires, err := time.Parse(time.RFC3339, allocation.Hello.ExpiresAt)
	if err != nil || conn.SetDeadline(expires) != nil {
		reason = "allocation_deadline_invalid"
		return
	}
	hello, err := protocol.AuthorityHelloBytes(allocation.Hello, s.Clock().UTC())
	if err != nil || protocol.WriteFrame(conn, hello) != nil {
		reason = "hello_write_failed"
		return
	}
	proposalRaw, err := readFrame(conn)
	if err != nil {
		reason = "proposal_read_failed"
		return
	}
	defer zero(proposalRaw)
	var proposal protocol.DispatchProposal
	if protocol.DecodeClosed(proposalRaw, &proposal) != nil {
		s.writeSafe(conn, "authorization_declined")
		reason = "proposal_invalid"
		return
	}
	limits := protocol.FrozenAllocationLimits()
	parts, err := readParts(conn, proposal.Parts, limits.MaxParts, limits.MaxRequestBytes)
	if err != nil {
		s.writeSafe(conn, "authorization_declined")
		reason = "parts_invalid"
		return
	}
	defer zeroParts(parts)
	request, err := protocol.BindAllocationRequest(allocation.Hello, proposal, parts, s.Clock().UTC())
	if err != nil {
		s.writeSafe(conn, "authorization_declined")
		reason = "binding_invalid"
		return
	}
	body, err := provider.BuildBody(request, parts)
	if err != nil {
		s.writeSafe(conn, "authorization_declined")
		reason = "body_invalid"
		return
	}
	defer zero(body)
	challenge := buildChallenge(request, peer, allocation.ConnectionID, protocol.Digest(body))
	reserved, err := s.Manager.Reserve(ctx, request, challenge, body, peer, allocation.ConnectionID)
	if err != nil {
		s.writeSafe(conn, "authority_unavailable")
		reason = "reserve_failed"
		return
	}
	challengeRaw, err := protocol.CanonicalJSON(reserved)
	if err != nil || protocol.WriteFrame(conn, challengeRaw) != nil {
		_ = s.Manager.Cancel(context.Background(), reserved.TransactionID)
		reason = "challenge_write_failed"
		return
	}
	ackRaw, err := readFrame(conn)
	if err != nil {
		_ = s.Manager.Cancel(context.Background(), reserved.TransactionID)
		reason = "consent_read_failed"
		return
	}
	defer zero(ackRaw)
	var ack protocol.ConsentAck
	if protocol.DecodeClosed(ackRaw, &ack) != nil || protocol.ValidateConsentAck(ack) != nil || ack.ChallengeSHA256 != protocol.Digest(challengeRaw) {
		_ = s.Manager.Cancel(context.Background(), reserved.TransactionID)
		s.writeSafe(conn, "consent_connection_invalid")
		reason = "consent_invalid"
		return
	}
	if conn.SetDeadline(time.Time{}) != nil {
		_ = s.Manager.Cancel(context.Background(), reserved.TransactionID)
		reason = "connection_deadline_clear_failed"
		return
	}
	sink := &provider.OriginalConnectionSink{ID: allocation.ConnectionID, Conn: conn}
	_, err = s.Dispatcher.Dispatch(ctx, provider.DispatchInput{Request: request, Challenge: reserved, Parts: parts, TransactionID: reserved.TransactionID, ConnectionID: allocation.ConnectionID, ConsentChallengeDigest: ack.ChallengeSHA256, Peer: peer}, sink)
	if err != nil {
		_ = sink.Abort()
		reason = "dispatch_ambiguous"
		return
	}
	reason = "terminal_complete"
}

func buildChallenge(request protocol.Request, peer authority.Peer, transactionID, bodyDigest string) protocol.Challenge {
	a := request.Authority
	return protocol.Challenge{SchemaVersion: request.SchemaVersion, Protocol: request.Protocol, Mapping: request.Mapping, OperationFamily: request.OperationFamily, SubstrateAuthority: request.SubstrateAuthority, TransactionID: transactionID, ConnectionNonceSHA256: a.ConnectionNonceSHA256, PeerUID: peer.UID, PeerPID: peer.PID, RequestBodySHA256: bodyDigest, Destination: request.Destination, Method: request.Method, Path: request.Path, Models: append([]string(nil), request.Models...), Scope: request.Scope, DaemonBuildSHA256: a.DaemonBuildSHA256, ScannerBuildSHA256: a.ScannerBuildSHA256, PolicySHA256: a.PolicySHA256, Nonce: a.Nonce, Sequence: a.Sequence, BootID: a.BootID, SessionID: a.SessionID, IssuedAt: a.IssuedAt, ExpiresAt: a.ExpiresAt, Limits: request.Limits, PriorChainDigest: a.PriorChainDigest, AllocationHelloSHA256: a.AllocationHelloSHA256, DispatchProposalSHA256: a.DispatchProposalSHA256}
}

func readFrame(conn GuardedConn) ([]byte, error) {
	var header [4]byte
	if err := receiveFull(conn, header[:]); err != nil {
		return nil, err
	}
	size := binary.BigEndian.Uint32(header[:])
	if size > protocol.MaxFrameBytes {
		return nil, protocol.ErrFrameTooLarge
	}
	payload := make([]byte, int(size))
	if err := receiveFull(conn, payload); err != nil {
		zero(payload)
		return nil, err
	}
	return payload, nil
}

func readParts(conn GuardedConn, declared []protocol.Part, maxParts int, limit int64) ([][]byte, error) {
	if len(declared) == 0 || len(declared) > maxParts {
		return nil, protocol.ErrPartMismatch
	}
	parts := make([][]byte, 0, len(declared))
	var total int64
	for _, part := range declared {
		var header [8]byte
		if receiveFull(conn, header[:]) != nil {
			zeroParts(parts)
			return nil, protocol.ErrPartMismatch
		}
		size := binary.BigEndian.Uint64(header[:])
		if size > protocol.MaxFrameBytes || int64(size) != part.ContentLength || total+int64(size) > limit {
			zeroParts(parts)
			return nil, protocol.ErrPartMismatch
		}
		payload := make([]byte, int(size))
		if receiveFull(conn, payload) != nil || protocol.Digest(payload) != part.ContentSHA256 {
			zero(payload)
			zeroParts(parts)
			return nil, protocol.ErrPartMismatch
		}
		total += int64(size)
		parts = append(parts, payload)
	}
	return parts, nil
}

func receiveFull(conn GuardedConn, target []byte) error {
	for len(target) > 0 {
		n, err := conn.Receive(target)
		if n > 0 {
			target = target[n:]
		}
		if err != nil {
			return err
		}
		if n <= 0 {
			return io.ErrUnexpectedEOF
		}
	}
	return nil
}

func (s *Server) writeSafe(conn io.Writer, code string) {
	value := protocol.SafeError{SchemaVersion: protocol.Version, Protocol: protocol.Name, Type: protocol.SafeErrorType, Code: code, Consumed: true}
	switch code {
	case "authority_unavailable":
		value.ExitCode = 70
	case "disclosure_declined":
		value.ExitCode = 72
	default:
		value.ExitCode = 71
	}
	if protocol.ValidateSafeError(value) != nil {
		return
	}
	payload, err := protocol.CanonicalJSON(value)
	if err == nil {
		_ = protocol.WriteFrame(conn, payload)
	}
}

func zeroParts(parts [][]byte) {
	for _, part := range parts {
		zero(part)
	}
}
