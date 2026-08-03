// Package client implements the fixed-path public workflow-authority client.
package client

import (
	"context"
	"crypto/elliptic"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/platform"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

const (
	PublicTrustPath = "/etc/design-machines/workflow-authority/trust/authority-public.json"
	maxResponse     = uint64(8_388_608)
)

var (
	ErrUsage       = errors.New("usage_error")
	ErrUnavailable = errors.New("authority_unavailable")
	ErrDeclined    = errors.New("authorization_declined")
	ErrDisclosure  = errors.New("disclosure_declined")
	ErrUncertain   = errors.New("result_verification_failed")
)

type DispatchOptions struct {
	Repository, RunID, Lane, Candidate, Workload, Nonce string
	Model, FallbackModel                                string
}

type Result struct {
	Receipt  []byte
	Response []byte
	ExitCode int
}

type consentConfirmer func(context.Context, protocol.Challenge) error

type Runner struct {
	socketPath, trustPath     string
	socketAnchor, trustAnchor string
	expectedOwner             uint32
	now                       func() time.Time
	dial                      func(context.Context, string) (net.Conn, error)
	confirm                   consentConfirmer
	fido                      authority.FIDO
}

func NewProduction() *Runner {
	r := &Runner{socketPath: platform.SocketPath, trustPath: PublicTrustPath, socketAnchor: string(filepath.Separator), trustAnchor: string(filepath.Separator), expectedOwner: 0, now: func() time.Time { return time.Now().UTC() }, fido: authority.NewFIDOAdapter()}
	r.dial = func(ctx context.Context, path string) (net.Conn, error) {
		return (&net.Dialer{Timeout: 5 * time.Second}).DialContext(ctx, "unix", path)
	}
	r.confirm = confirmProductionConsent
	return r
}

func (r *Runner) Dispatch(ctx context.Context, options DispatchOptions, system, user io.Reader) (Result, error) {
	if err := validateOptions(options); err != nil {
		return Result{}, err
	}
	parts, err := readParts(system, user)
	if err != nil {
		return Result{}, err
	}
	defer zeroParts(parts)
	credential, err := r.loadTrust()
	if err != nil {
		return Result{}, ErrUnavailable
	}
	conn, err := r.connect(ctx)
	if err != nil {
		return Result{}, ErrUnavailable
	}
	defer conn.Close()
	stopCancellation := make(chan struct{})
	defer close(stopCancellation)
	go func() {
		select {
		case <-ctx.Done():
			_ = conn.Close()
		case <-stopCancellation:
		}
	}()
	_ = conn.SetDeadline(time.Now().Add(2 * time.Minute))

	helloRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return Result{}, ErrUnavailable
	}
	var hello protocol.AuthorityHello
	if err := protocol.DecodeClosed(helloRaw, &hello); err != nil || protocol.ValidateAuthorityHello(hello, r.now()) != nil {
		return Result{}, ErrUnavailable
	}
	proposal := makeProposal(options, parts, protocol.Digest(helloRaw))
	proposalRaw, err := protocol.DispatchProposalBytes(proposal, parts)
	if err != nil {
		return Result{}, ErrUsage
	}
	request, err := protocol.BindAllocationRequest(hello, proposal, parts, r.now())
	if err != nil {
		return Result{}, ErrUnavailable
	}
	if err := protocol.WriteFrame(conn, proposalRaw); err != nil || writeParts(conn, parts) != nil {
		return Result{}, ErrUnavailable
	}

	challengeRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return Result{}, ErrUnavailable
	}
	if safe, ok := decodeSafeError(challengeRaw); ok {
		return Result{}, safeError(safe)
	}
	var challenge protocol.Challenge
	if protocol.DecodeClosed(challengeRaw, &challenge) != nil || validateChallenge(request, challenge, parts, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	if validateFresh(request, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	if err := r.confirm(ctx, challenge); err != nil {
		if ctx.Err() != nil {
			return Result{}, ErrUncertain
		}
		return Result{}, ErrDeclined
	}
	if validateFresh(request, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	ack := protocol.ConsentAck{SchemaVersion: protocol.Version, Protocol: protocol.Name, Type: protocol.ConsentAckType, ChallengeSHA256: protocol.Digest(challengeRaw)}
	ackRaw, _ := protocol.CanonicalJSON(ack)
	if protocol.WriteFrame(conn, ackRaw) != nil {
		return Result{}, ErrUncertain
	}

	proofRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return Result{}, ErrUncertain
	}
	if validateFresh(request, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	proof, assertion, err := decodeAndVerifyProof(ctx, proofRaw, challengeRaw, credential, r.fido)
	if err != nil {
		return Result{}, ErrUncertain
	}
	response, err := readResponse(conn, maxResponse)
	if err != nil {
		return Result{}, ErrUncertain
	}
	defer zero(response)
	terminalRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return Result{}, ErrUncertain
	}
	if validateFresh(request, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	var result protocol.TerminalResult
	if protocol.DecodeClosed(terminalRaw, &result) != nil || verifyTerminal(request, challenge, challengeRaw, proof, assertion, response, result, r.now()) != nil {
		return Result{}, ErrUncertain
	}
	if trailing(conn) != nil || ctx.Err() != nil {
		return Result{}, ErrUncertain
	}
	verifiedResponse := []byte(nil)
	if result.Outcome == "verified" {
		verifiedResponse = append([]byte(nil), response...)
	}
	return Result{Receipt: append([]byte(nil), terminalRaw...), Response: verifiedResponse, ExitCode: result.ExitCode}, nil
}

func (r *Runner) Status(ctx context.Context) ([]byte, error) {
	credential, err := r.loadTrust()
	readiness := r.fido.Readiness(ctx)
	if err != nil || credential.Status != "active" || !readiness.Production || !readiness.InternalUV || readiness.Adapter != "libfido2" || readiness.Version != authority.FIDO2Version {
		return nil, ErrUnavailable
	}
	conn, err := r.connect(ctx)
	if err != nil {
		return nil, ErrUnavailable
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(5 * time.Second))
	raw, err := protocol.ReadFrame(conn)
	if err != nil {
		return nil, ErrUnavailable
	}
	var hello protocol.AuthorityHello
	if protocol.DecodeClosed(raw, &hello) != nil || protocol.ValidateAuthorityHello(hello, r.now()) != nil {
		return nil, ErrUnavailable
	}
	return protocol.CanonicalJSON(map[string]any{"m1_acceptance": true, "production_ready": true, "protocol": protocol.Name, "schema_version": 1})
}

func (r *Runner) connect(ctx context.Context) (net.Conn, error) {
	if r == nil || r.socketPath == "" || r.trustPath == "" || r.dial == nil || r.confirm == nil || r.fido == nil || r.now == nil {
		return nil, ErrUnavailable
	}
	if err := validateSocketPath(r.socketPath, r.socketAnchor, r.expectedOwner); err != nil {
		return nil, err
	}
	conn, err := r.dial(ctx, r.socketPath)
	if err != nil {
		return nil, err
	}
	if err := validateSocketPath(r.socketPath, r.socketAnchor, r.expectedOwner); err != nil || requirePeerOwner(conn, r.expectedOwner) != nil {
		_ = conn.Close()
		return nil, ErrUnavailable
	}
	return conn, nil
}

func validateOptions(o DispatchOptions) error {
	if o.Repository == "" || o.RunID == "" || o.Lane == "" || o.Candidate == "" || o.Workload == "" || o.Nonce == "" || o.Model == "" || o.FallbackModel == o.Model {
		return ErrUsage
	}
	models := []string{o.Model}
	if o.FallbackModel != "" {
		models = append(models, o.FallbackModel)
	}
	proposal := protocol.DispatchProposal{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.DispatchProposalType, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: models, Parts: []protocol.Part{{Role: "system", ContentLength: 0, ContentSHA256: protocol.Digest(nil)}, {Role: "user", ContentLength: 0, ContentSHA256: protocol.Digest(nil)}}, Scope: protocol.Scope{Repository: o.Repository, RunID: o.RunID, Lane: o.Lane, Candidate: o.Candidate, Workload: o.Workload}, CallerNonce: o.Nonce, AuthorityHelloSHA256: protocol.Digest(nil)}
	return protocol.ValidateDispatchProposal(proposal, [][]byte{{}, {}})
}

func makeProposal(o DispatchOptions, parts [][]byte, helloDigest string) protocol.DispatchProposal {
	models := []string{o.Model}
	if o.FallbackModel != "" {
		models = append(models, o.FallbackModel)
	}
	return protocol.DispatchProposal{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.DispatchProposalType, Mapping: protocol.Mapping, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Destination: protocol.Destination, Method: protocol.Method, Path: protocol.Path, Models: models, Parts: []protocol.Part{{Role: "system", ContentLength: int64(len(parts[0])), ContentSHA256: protocol.Digest(parts[0])}, {Role: "user", ContentLength: int64(len(parts[1])), ContentSHA256: protocol.Digest(parts[1])}}, Scope: protocol.Scope{Repository: o.Repository, RunID: o.RunID, Lane: o.Lane, Candidate: o.Candidate, Workload: o.Workload}, CallerNonce: o.Nonce, AuthorityHelloSHA256: helloDigest}
}

func readParts(readers ...io.Reader) ([][]byte, error) {
	parts := make([][]byte, len(readers))
	var total int64
	for i, reader := range readers {
		if reader == nil {
			return nil, ErrUsage
		}
		part, err := io.ReadAll(io.LimitReader(reader, int64(protocol.MaxFrameBytes)+1))
		if err != nil || len(part) > protocol.MaxFrameBytes {
			zeroParts(parts)
			return nil, ErrUsage
		}
		parts[i] = part
		total += int64(len(part))
	}
	if total > 8_388_608 {
		zeroParts(parts)
		return nil, ErrUsage
	}
	return parts, nil
}

func writeParts(w io.Writer, parts [][]byte) error {
	for _, part := range parts {
		var header [8]byte
		binary.BigEndian.PutUint64(header[:], uint64(len(part)))
		if writeAll(w, header[:]) != nil || writeAll(w, part) != nil {
			return ErrUnavailable
		}
	}
	return nil
}

func validateChallenge(request protocol.Request, challenge protocol.Challenge, parts [][]byte, now time.Time) error {
	body, err := provider.BuildBody(request, parts)
	if err != nil {
		return err
	}
	defer zero(body)
	a := request.Authority
	if protocol.ValidateRequest(request, now) != nil || challenge.SchemaVersion != 1 || challenge.Protocol != protocol.Name || challenge.Mapping != request.Mapping || challenge.OperationFamily != request.OperationFamily || challenge.SubstrateAuthority != request.SubstrateAuthority || challenge.Destination != request.Destination || challenge.Method != request.Method || challenge.Path != request.Path || challenge.Scope != request.Scope || challenge.RequestBodySHA256 != protocol.Digest(body) || challenge.ConnectionNonceSHA256 != a.ConnectionNonceSHA256 || challenge.DaemonBuildSHA256 != a.DaemonBuildSHA256 || challenge.ScannerBuildSHA256 != a.ScannerBuildSHA256 || challenge.PolicySHA256 != a.PolicySHA256 || challenge.Nonce != a.Nonce || challenge.Sequence != a.Sequence || challenge.BootID != a.BootID || challenge.SessionID != a.SessionID || challenge.IssuedAt != a.IssuedAt || challenge.ExpiresAt != a.ExpiresAt || challenge.PriorChainDigest != a.PriorChainDigest || challenge.AllocationHelloSHA256 != a.AllocationHelloSHA256 || challenge.DispatchProposalSHA256 != a.DispatchProposalSHA256 || challenge.AuthorityAssertion != nil || challenge.PeerUID != uint32(os.Geteuid()) || challenge.PeerPID != int32(os.Getpid()) || challenge.TransactionID == "" || challenge.ResultSigner.Kind != "ephemeral-es256" || challenge.ResultSigner.PublicKeySEC1 == "" || !same(challenge.Models, request.Models) || challenge.Limits != request.Limits {
		return ErrUncertain
	}
	signer, err := base64.RawURLEncoding.DecodeString(challenge.ResultSigner.PublicKeySEC1)
	if err != nil {
		return ErrUncertain
	}
	if x, y := elliptic.Unmarshal(elliptic.P256(), signer); x == nil || y == nil {
		return ErrUncertain
	}
	return nil
}

func validateFresh(request protocol.Request, now time.Time) error {
	return protocol.ValidateRequest(request, now)
}

func confirmProductionConsent(ctx context.Context, challenge protocol.Challenge) error {
	terminal, err := authority.OpenControllingTerminal()
	if err != nil {
		return err
	}
	results := make(chan error, 1)
	go func() { results <- authority.ConfirmExactScope(terminal, challenge) }()
	select {
	case err := <-results:
		_ = terminal.Close()
		return err
	case <-ctx.Done():
		_ = terminal.Close()
		select {
		case <-results:
		case <-time.After(time.Second):
		}
		return ctx.Err()
	}
}

func decodeSafeError(raw []byte) (protocol.SafeError, bool) {
	var value protocol.SafeError
	if protocol.DecodeClosed(raw, &value) == nil && protocol.ValidateSafeError(value) == nil {
		return value, true
	}
	return protocol.SafeError{}, false
}

func safeError(value protocol.SafeError) error {
	switch value.ExitCode {
	case 71:
		return ErrDeclined
	case 72:
		return ErrDisclosure
	default:
		return ErrUnavailable
	}
}

func decodeAndVerifyProof(ctx context.Context, raw, challengeRaw []byte, credential authority.Credential, verifier authority.FIDO) (provider.AuthorizationProof, authority.Assertion, error) {
	var proof provider.AuthorizationProof
	if protocol.DecodeClosed(raw, &proof) != nil || proof.SchemaVersion != 1 || proof.Protocol != protocol.Name || proof.Type != "authorization_proof" || proof.ChallengeSHA256 != protocol.Digest(challengeRaw) || proof.AuthorityAssertion.Kind != "fido2-es256" || !proof.AuthorityAssertion.UserPresence || !proof.AuthorityAssertion.UserVerification {
		return proof, authority.Assertion{}, ErrUncertain
	}
	decode := func(value string) ([]byte, error) { return base64.RawURLEncoding.DecodeString(value) }
	reference, err1 := decode(proof.AuthorityAssertion.CredentialID)
	authData, err2 := decode(proof.AuthorityAssertion.AuthenticatorData)
	clientData, err3 := decode(proof.AuthorityAssertion.ClientDataJSON)
	signature, err4 := decode(proof.AuthorityAssertion.SignatureDER)
	if err1 != nil || err2 != nil || err3 != nil || err4 != nil || string(reference) != credential.Reference || len(authData) < 37 {
		return proof, authority.Assertion{}, ErrUncertain
	}
	assertion := authority.Assertion{CredentialReference: string(reference), Generation: credential.Generation, Signature: signature, AuthenticatorData: authData, ClientDataJSON: clientData, UserPresence: true, UserVerification: true, Counter: binary.BigEndian.Uint32(authData[33:37])}
	challengeInput := mustChallengeInput(challengeRaw)
	assertion.ChallengeDigest = sha256.Sum256(challengeInput)
	if verifier.Verify(ctx, challengeInput, credential, assertion) != nil {
		return proof, assertion, ErrUncertain
	}
	return proof, assertion, nil
}

func mustChallengeInput(challengeRaw []byte) []byte {
	var challenge protocol.Challenge
	if protocol.DecodeClosed(challengeRaw, &challenge) != nil {
		return nil
	}
	input, _ := protocol.ChallengeInput(challenge)
	return input
}

func verifyTerminal(request protocol.Request, challenge protocol.Challenge, challengeRaw []byte, proof provider.AuthorizationProof, assertion authority.Assertion, response []byte, result protocol.TerminalResult, now time.Time) error {
	if protocol.ValidateTerminalResult(result) != nil || result.RequestBodySHA256 != challenge.RequestBodySHA256 || result.ResponseSHA256 != protocol.Digest(response) || result.ResponseLength != int64(len(response)) || result.PartCount != len(request.Parts) || !same(result.Models, request.Models) || result.Scope != request.Scope || result.Sequence != request.Authority.Sequence || result.IssuedAt != request.Authority.IssuedAt || result.ChallengeSHA256 != protocol.Digest(challengeRaw) || proof.ChallengeSHA256 != protocol.Digest(challengeRaw) || result.PriorChainDigest != request.Authority.PriorChainDigest || result.Signature.Kind != "es256" || result.SelectedModel == nil {
		return ErrUncertain
	}
	issued, issuedErr := time.Parse(time.RFC3339, result.IssuedAt)
	completed, completedErr := time.Parse(time.RFC3339, result.CompletedAt)
	if issuedErr != nil || completedErr != nil || completed.Before(issued) || completed.After(now) {
		return ErrUncertain
	}
	assertionRaw, _ := protocol.CanonicalJSON(proof.AuthorityAssertion)
	signerRaw, _ := protocol.CanonicalJSON(challenge.ResultSigner)
	if result.AuthorityAssertionSHA256 != protocol.Digest(assertionRaw) || result.ResultSignerSHA256 != protocol.Digest(signerRaw) || assertion.CredentialReference == "" {
		return ErrUncertain
	}
	input, err := protocol.TerminalSignatureInput(result)
	if err != nil || protocol.VerifyTerminalES256(challenge.ResultSigner.PublicKeySEC1, result.Signature.SignatureDER, input) != nil {
		return ErrUncertain
	}
	return nil
}

func readResponse(r io.Reader, limit uint64) ([]byte, error) {
	var header [8]byte
	if _, err := io.ReadFull(r, header[:]); err != nil {
		return nil, err
	}
	length := binary.BigEndian.Uint64(header[:])
	if length > limit {
		return nil, protocol.ErrFrameTooLarge
	}
	payload := make([]byte, length)
	_, err := io.ReadFull(r, payload)
	return payload, err
}

func trailing(conn net.Conn) error {
	_ = conn.SetReadDeadline(time.Now().Add(100 * time.Millisecond))
	var one [1]byte
	n, err := conn.Read(one[:])
	if n != 0 || (err == nil) {
		return protocol.ErrTrailingData
	}
	if errors.Is(err, io.EOF) {
		return nil
	}
	if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
		return protocol.ErrTrailingData
	}
	return err
}

func writeAll(w io.Writer, payload []byte) error {
	for len(payload) > 0 {
		n, err := w.Write(payload)
		if err != nil || n < 1 || n > len(payload) {
			return io.ErrShortWrite
		}
		payload = payload[n:]
	}
	return nil
}
func same(a, b []string) bool {
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
func zero(value []byte) {
	for i := range value {
		value[i] = 0
	}
}
func zeroParts(parts [][]byte) {
	for _, part := range parts {
		zero(part)
	}
}
