package provider

import (
	"bufio"
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
	"strconv"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

const ProductionURL = "https://openrouter.ai/api/v1/chat/completions"

const maxProviderMetadata = int64(128 << 10)

type Transport struct {
	Origin    string
	Fixture   bool
	TLSConfig *tls.Config
	DialTLS   func(context.Context, string, string, *tls.Config) (net.Conn, error)
	Timeout   time.Duration
}

func ProductionTransport() *Transport {
	dialer := &net.Dialer{Timeout: 30 * time.Second, KeepAlive: -1}
	return &Transport{Origin: ProductionURL, TLSConfig: &tls.Config{MinVersion: tls.VersionTLS13}, DialTLS: func(ctx context.Context, network, address string, config *tls.Config) (net.Conn, error) {
		return (&tls.Dialer{NetDialer: dialer, Config: config}).DialContext(ctx, network, address)
	}, Timeout: 10 * time.Minute}
}

func (t *Transport) Send(ctx context.Context, credential *Credential, body []byte) ([]byte, error) {
	if credential == nil || len(credential.Bytes()) == 0 || t == nil || t.Origin == "" || t.Fixture != credential.Fixture() {
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
	config := t.TLSConfig
	if config == nil {
		config = &tls.Config{MinVersion: tls.VersionTLS13}
	} else {
		config = config.Clone()
	}
	config.ServerName = u.Hostname()
	config.NextProtos = []string{"http/1.1"}
	dial := t.DialTLS
	if dial == nil {
		d := &net.Dialer{Timeout: 30 * time.Second, KeepAlive: -1}
		dial = func(ctx context.Context, network, address string, c *tls.Config) (net.Conn, error) {
			return (&tls.Dialer{NetDialer: d, Config: c}).DialContext(ctx, network, address)
		}
	}
	port := u.Port()
	if port == "" {
		port = "443"
	}
	address := net.JoinHostPort(u.Hostname(), port)
	conn, err := dial(requestCtx, "tcp", address, config) // the sole attempt; no retry exists.
	if err != nil {
		return nil, ErrTransport
	}
	if deadline, ok := requestCtx.Deadline(); ok {
		if err := conn.SetDeadline(deadline); err != nil {
			_ = conn.Close()
			return nil, ErrTransport
		}
	}
	done := make(chan struct{})
	go func() {
		select {
		case <-requestCtx.Done():
			_ = conn.Close()
		case <-done:
		}
	}()
	defer close(done)
	closed := false
	defer func() {
		if !closed {
			_ = conn.Close()
		}
	}()
	header := make([]byte, 0, 256+len(credential.Bytes()))
	header = append(header, "POST "...)
	header = append(header, u.EscapedPath()...)
	header = append(header, " HTTP/1.1\r\nHost: "...)
	header = append(header, u.Host...)
	header = append(header, "\r\nAuthorization: Bearer "...)
	header = append(header, credential.Bytes()...)
	header = append(header, "\r\nContent-Type: application/json\r\nAccept: application/json\r\nContent-Length: "...)
	header = strconv.AppendInt(header, int64(len(body)), 10)
	header = append(header, "\r\nConnection: close\r\n\r\n"...)
	if err := writeConnection(conn, header); err != nil {
		zero(header)
		return nil, ErrTransport
	}
	zero(header)
	if err := writeConnection(conn, body); err != nil {
		return nil, ErrTransport
	}
	wire := &io.LimitedReader{R: conn, N: maxProviderResponse + maxProviderMetadata + 1}
	headerBlock, err := readHeaderBlock(wire, maxProviderMetadata)
	if err != nil {
		return nil, ErrTransport
	}
	resp, err := http.ReadResponse(bufio.NewReader(io.MultiReader(bytes.NewReader(headerBlock), wire)), &http.Request{Method: http.MethodPost})
	if err != nil {
		return nil, ErrTransport
	}
	if resp.ContentLength > maxProviderResponse {
		_ = resp.Body.Close()
		return nil, ErrTransport
	}
	limited := io.LimitReader(resp.Body, maxProviderResponse+1)
	response, readErr := io.ReadAll(limited)
	bodyCloseErr := resp.Body.Close()
	connCloseErr := conn.Close()
	closed = true
	if readErr != nil || bodyCloseErr != nil || (connCloseErr != nil && !errors.Is(connCloseErr, net.ErrClosed)) || int64(len(response)) > maxProviderResponse || wire.N <= 0 {
		zero(response)
		return nil, ErrTransport
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return response, ErrTransport
	}
	return response, nil
}

func protocolPath() string { return "/api/v1/chat/completions" }

func readHeaderBlock(reader io.Reader, limit int64) ([]byte, error) {
	if limit < 4 {
		return nil, ErrTransport
	}
	header := make([]byte, 0, minInt64(limit, 4096))
	var one [1]byte
	for int64(len(header)) < limit {
		n, err := reader.Read(one[:])
		if n == 1 {
			header = append(header, one[0])
			if len(header) >= 4 && bytes.Equal(header[len(header)-4:], []byte("\r\n\r\n")) {
				return header, nil
			}
		}
		if err != nil {
			zero(header)
			return nil, ErrTransport
		}
	}
	zero(header)
	return nil, ErrTransport
}

func minInt64(value int64, capValue int) int {
	if value < int64(capValue) {
		return int(value)
	}
	return capValue
}

type ResponseSink interface {
	ConnectionID() string
	WriteAuthorizationProof(context.Context, AuthorizationProof) error
	WriteResponse(context.Context, []byte) error
	WriteTerminalAndClose(context.Context, []byte) error
}

type OriginalConnectionSink struct {
	ID        string
	Conn      net.Conn
	proofUsed bool
	used      bool
	closed    bool
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
	if s == nil || s.Conn == nil || s.ID == "" || !s.proofUsed || s.used || s.closed || ctx.Err() != nil {
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

func (s *OriginalConnectionSink) WriteTerminalAndClose(ctx context.Context, payload []byte) error {
	if s == nil || s.Conn == nil || !s.used || s.closed || ctx.Err() != nil || len(payload) > protocol.MaxFrameBytes {
		return ErrSink
	}
	s.closed = true
	defer s.Conn.Close()
	var length [4]byte
	binary.BigEndian.PutUint32(length[:], uint32(len(payload)))
	if writeConnection(s.Conn, length[:]) != nil || writeConnection(s.Conn, payload) != nil {
		return ErrSink
	}
	if half, ok := s.Conn.(interface{ CloseWrite() error }); ok {
		if half.CloseWrite() != nil {
			return ErrSink
		}
	}
	if err := s.Conn.Close(); err != nil && !errors.Is(err, net.ErrClosed) {
		return ErrSink
	}
	return nil
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
