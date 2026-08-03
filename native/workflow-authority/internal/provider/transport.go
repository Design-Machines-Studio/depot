package provider

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

const ProductionURL = "https://openrouter.ai/api/v1/chat/completions"

type Transport struct {
	Origin  string
	Fixture bool
	Client  *http.Client
	Timeout time.Duration
}

func ProductionTransport() *Transport {
	dialer := &net.Dialer{Timeout: 30 * time.Second, KeepAlive: -1}
	rt := &http.Transport{Proxy: nil, DialContext: dialer.DialContext, ForceAttemptHTTP2: true, DisableKeepAlives: true, MaxIdleConns: 0, TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS13}}
	return &Transport{Origin: ProductionURL, Client: &http.Client{Transport: rt, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect_rejected") }}, Timeout: 10 * time.Minute}
}

func (t *Transport) Send(ctx context.Context, credential *Credential, body []byte) ([]byte, error) {
	if credential == nil || len(credential.Bytes()) == 0 || t == nil || t.Client == nil || t.Origin == "" || t.Fixture != credential.Fixture() {
		return nil, ErrTransport
	}
	u, err := url.Parse(t.Origin)
	if err != nil || u.Scheme != "https" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != protocolPath() {
		return nil, ErrTransport
	}
	if !t.Fixture && (t.Origin != ProductionURL || u.Host != "openrouter.ai") {
		return nil, ErrTransport
	}
	if t.Fixture && u.Host == "openrouter.ai" {
		return nil, ErrTransport
	}
	requestCtx := ctx
	var cancel context.CancelFunc
	if t.Timeout > 0 {
		requestCtx, cancel = context.WithTimeout(ctx, t.Timeout)
		defer cancel()
	}
	req, err := http.NewRequestWithContext(requestCtx, http.MethodPost, t.Origin, bytes.NewReader(body))
	if err != nil {
		return nil, ErrTransport
	}
	authorizationBytes := append([]byte("Bearer "), credential.Bytes()...)
	// net/http requires immutable string header values. Keep that unavoidable
	// copy request-scoped, erase the mutable assembly buffer immediately, and
	// drop all request/header references as soon as Do returns.
	authorization := string(authorizationBytes)
	zero(authorizationBytes)
	req.Header = http.Header{"Authorization": []string{authorization}, "Content-Type": []string{"application/json"}, "Accept": []string{"application/json"}}
	resp, err := t.Client.Do(req) // exactly one attempt; no retry loop exists.
	req.Header.Del("Authorization")
	authorization = ""
	if err != nil {
		return nil, ErrTransport
	}
	defer resp.Body.Close()
	limited := io.LimitReader(resp.Body, maxProviderResponse+1)
	response, readErr := io.ReadAll(limited)
	if readErr != nil || int64(len(response)) > maxProviderResponse {
		zero(response)
		return nil, ErrTransport
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return response, ErrTransport
	}
	return response, nil
}

func protocolPath() string { return "/api/v1/chat/completions" }

type ResponseSink interface {
	ConnectionID() string
	WriteAuthorizationProof(context.Context, AuthorizationProof) error
	WriteResponse(context.Context, []byte) error
}

type OriginalConnectionSink struct {
	ID        string
	Conn      net.Conn
	proofUsed bool
	used      bool
}

func (s *OriginalConnectionSink) ConnectionID() string { return s.ID }
func (s *OriginalConnectionSink) WriteAuthorizationProof(ctx context.Context, proof AuthorizationProof) error {
	if s == nil || s.Conn == nil || s.ID == "" || s.proofUsed || s.used || ctx.Err() != nil {
		return ErrSink
	}
	payload, err := protocol.CanonicalJSON(proof)
	if err != nil || len(payload) > protocol.MaxFrameBytes {
		return ErrSink
	}
	s.proofUsed = true
	var length [4]byte
	binary.BigEndian.PutUint32(length[:], uint32(len(payload)))
	if err := writeConnection(s.Conn, length[:]); err != nil {
		return err
	}
	return writeConnection(s.Conn, payload)
}
func (s *OriginalConnectionSink) WriteResponse(ctx context.Context, payload []byte) error {
	if s == nil || s.Conn == nil || s.ID == "" || !s.proofUsed || s.used || ctx.Err() != nil {
		return ErrSink
	}
	if raw, ok := s.Conn.(syscall.Conn); ok {
		rc, err := raw.SyscallConn()
		if err != nil {
			return ErrSink
		}
		regular := false
		if rc.Control(func(fd uintptr) {
			var st syscall.Stat_t
			if syscall.Fstat(int(fd), &st) == nil {
				regular = st.Mode&syscall.S_IFMT == syscall.S_IFREG
			}
		}) != nil || regular {
			return ErrSink
		}
	}
	s.used = true
	deadline := time.Now().Add(30 * time.Second)
	_ = s.Conn.SetWriteDeadline(deadline)
	var length [8]byte
	binary.BigEndian.PutUint64(length[:], uint64(len(payload)))
	if err := writeConnection(s.Conn, length[:]); err != nil {
		return err
	}
	return writeConnection(s.Conn, payload)
}

func writeConnection(conn net.Conn, payload []byte) error {
	for len(payload) > 0 {
		n, err := conn.Write(payload)
		if err != nil || n <= 0 || n > len(payload) {
			return ErrSink
		}
		payload = payload[n:]
	}
	return nil
}

func RejectRegularFileSink(f *os.File) error {
	info, err := f.Stat()
	if err != nil || info.Mode().IsRegular() {
		return ErrSink
	}
	return nil
}
