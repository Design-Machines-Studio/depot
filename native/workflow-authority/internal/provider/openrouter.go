// Package provider owns disclosure scanning, OpenRouter wire construction, and
// content-free terminal projection. Callers never receive provider credentials.
package provider

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
)

const (
	ProductionPolicyPath = "/etc/design-machines/workflow-authority/provider-policy.json"
	ScannerBuildDigest   = "sha256:6c80aa1dd68d34f2a3fd9e5d0fb54bd8eeaef1b31074e40de3dfaa15e10842da"
	maxProviderResponse  = int64(8 << 20)
)

var (
	ErrPolicy        = errors.New("provider_policy_rejected")
	ErrBinding       = errors.New("provider_binding_invalid")
	ErrTransport     = errors.New("provider_transport_failed")
	ErrProvenance    = errors.New("provider_provenance_missing")
	ErrSink          = errors.New("provider_response_delivery_failed")
	ErrStartup       = errors.New("provider_startup_unavailable")
	providerMetadata = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$`)
)

type Scanner interface {
	Scan(context.Context, [][]byte, []byte) error
}

// BuiltinScanner is compiled into the daemon. It implements the fixed policy's
// high-confidence token classes without executing a caller-selected program.
type BuiltinScanner struct{}

var secretPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----`),
	regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
	regexp.MustCompile(`gh[pousr]_[A-Za-z0-9_]{20,}`),
	regexp.MustCompile(`(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s:/]+:[^\s@]+@`),
	regexp.MustCompile(`(?i)(?:authorization\s*:\s*bearer|access[_-]?token\s*[=:]|session[_-]?(?:id|token)\s*[=:])\s*[A-Za-z0-9._~+/=-]{8,}`),
	regexp.MustCompile(`sk-or-v1-[A-Za-z0-9_-]{16,}`),
	regexp.MustCompile(`(?i)(?:classified|regulated|strictly confidential)\s*[=:]\s*[^\s]{4,}`),
}

type disclosurePolicy struct {
	SchemaVersion      int `json:"schemaVersion"`
	DisclosureControls struct {
		RefuseClasses []string `json:"refuseClasses"`
		OnMatch       string   `json:"onMatch"`
		ExitCode      int      `json:"exitCode"`
	} `json:"disclosureControls"`
}

func (BuiltinScanner) Scan(ctx context.Context, parts [][]byte, policy []byte) error {
	var parsed disclosurePolicy
	if ctx.Err() != nil || json.Unmarshal(policy, &parsed) != nil || parsed.SchemaVersion != 2 || parsed.DisclosureControls.OnMatch != "decline-disclosure" || parsed.DisclosureControls.ExitCode != 3 {
		return ErrPolicy
	}
	required := []string{"high-confidence credentials", "private keys", "authenticated connection strings / DSNs", "access or session tokens", "explicitly classified private or regulated values"}
	if len(parsed.DisclosureControls.RefuseClasses) != len(required) {
		return ErrPolicy
	}
	for i := range required {
		if parsed.DisclosureControls.RefuseClasses[i] != required[i] {
			return ErrPolicy
		}
	}
	aggregate := bytes.Join(parts, nil)
	for _, part := range parts {
		if !utf8.Valid(part) {
			return ErrPolicy
		}
	}
	for _, pattern := range secretPatterns {
		if pattern.Match(aggregate) {
			return ErrPolicy
		}
	}
	return nil
}

func containsBytes(haystack, needle []byte) bool {
	if len(needle) == 0 || len(needle) > len(haystack) {
		return false
	}
	for i := 0; i+len(needle) <= len(haystack); i++ {
		match := true
		for j := range needle {
			if haystack[i+j] != needle[j] {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

type message struct {
	Content string `json:"content"`
	Role    string `json:"role"`
}
type chatBody struct {
	Messages    []message `json:"messages"`
	Models      []string  `json:"models"`
	Temperature any       `json:"temperature"`
}

// BuildBody preserves each ordered UTF-8 part as exactly one message.
func BuildBody(request protocol.Request, parts [][]byte) ([]byte, error) {
	if len(parts) != len(request.Parts) {
		return nil, ErrBinding
	}
	messages := make([]message, len(parts))
	for i, part := range parts {
		if int64(len(part)) != request.Parts[i].ContentLength || protocol.Digest(part) != request.Parts[i].ContentSHA256 || !utf8.Valid(part) {
			return nil, ErrBinding
		}
		messages[i] = message{Content: string(part), Role: request.Parts[i].Role}
	}
	body, err := protocol.CanonicalJSON(chatBody{Messages: messages, Models: append([]string(nil), request.Models...), Temperature: nil})
	if err != nil || int64(len(body)) > request.Limits.MaxRequestBytes {
		return nil, ErrBinding
	}
	return body, nil
}

type Authority interface {
	Authorize(context.Context, string, string, authority.Peer, string) (authority.Assertion, error)
	Cancel(context.Context, string) error
	BeginSend(context.Context, string, string, authority.Peer) (authority.SendRight, error)
	Finalize(context.Context, authority.SendRight, int64, string, string) error
	SignFinalized(authority.SendRight, []byte) ([]byte, error)
}

type DispatchInput struct {
	Request                                             protocol.Request
	Challenge                                           protocol.Challenge
	Parts                                               [][]byte
	TransactionID, ConnectionID, ConsentChallengeDigest string
	Peer                                                authority.Peer
}

type Dispatcher struct {
	Scanner     Scanner
	Policy      []byte
	Credentials CredentialReader
	Transport   *Transport
	Authority   Authority
	Clock       func() time.Time
}

type Signature = protocol.TerminalSignature
type Cleanup = protocol.TerminalCleanup
type TerminalResult = protocol.TerminalResult

type providerResponse struct {
	ID       string           `json:"id"`
	Model    string           `json:"model"`
	Provider string           `json:"provider"`
	Usage    json.RawMessage  `json:"usage"`
	Choices  []providerChoice `json:"choices"`
}
type providerChoice struct {
	Message      providerMessage `json:"message"`
	Error        json.RawMessage `json:"error"`
	FinishReason *string         `json:"finish_reason"`
}
type providerMessage struct {
	Content json.RawMessage `json:"content"`
	Role    string          `json:"role"`
}

func decodeJSONString(raw []byte) ([]byte, error) {
	if len(raw) < 2 || raw[0] != '"' || raw[len(raw)-1] != '"' {
		return nil, ErrProvenance
	}
	out := make([]byte, 0, len(raw)-2)
	for i := 1; i < len(raw)-1; i++ {
		value := raw[i]
		if value != '\\' {
			if value < 0x20 {
				zero(out)
				return nil, ErrProvenance
			}
			out = append(out, value)
			continue
		}
		i++
		if i >= len(raw)-1 {
			zero(out)
			return nil, ErrProvenance
		}
		switch raw[i] {
		case '"', '\\', '/':
			out = append(out, raw[i])
		case 'b':
			out = append(out, '\b')
		case 'f':
			out = append(out, '\f')
		case 'n':
			out = append(out, '\n')
		case 'r':
			out = append(out, '\r')
		case 't':
			out = append(out, '\t')
		case 'u':
			first, next, ok := jsonHexRune(raw, i+1)
			if !ok {
				zero(out)
				return nil, ErrProvenance
			}
			i = next - 1
			if first >= 0xD800 && first <= 0xDBFF {
				if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
					zero(out)
					return nil, ErrProvenance
				}
				second, end, valid := jsonHexRune(raw, i+3)
				if !valid || second < 0xDC00 || second > 0xDFFF {
					zero(out)
					return nil, ErrProvenance
				}
				first = 0x10000 + ((first - 0xD800) << 10) + (second - 0xDC00)
				i = end - 1
			} else if first >= 0xDC00 && first <= 0xDFFF {
				zero(out)
				return nil, ErrProvenance
			}
			out = utf8.AppendRune(out, rune(first))
		default:
			zero(out)
			return nil, ErrProvenance
		}
	}
	if !utf8.Valid(out) {
		zero(out)
		return nil, ErrProvenance
	}
	return out, nil
}

func jsonHexRune(raw []byte, start int) (uint32, int, bool) {
	if start+4 > len(raw)-1 {
		return 0, start, false
	}
	var value uint32
	for _, item := range raw[start : start+4] {
		value <<= 4
		switch {
		case item >= '0' && item <= '9':
			value += uint32(item - '0')
		case item >= 'a' && item <= 'f':
			value += uint32(item-'a') + 10
		case item >= 'A' && item <= 'F':
			value += uint32(item-'A') + 10
		default:
			return 0, start, false
		}
	}
	return value, start + 4, true
}

func zeroProviderResponse(value *providerResponse) {
	if value == nil {
		return
	}
	zero(value.Usage)
	for i := range value.Choices {
		zero(value.Choices[i].Error)
		zero(value.Choices[i].Message.Content)
	}
}

type FIDOAssertion struct {
	Kind              string `json:"kind"`
	CredentialID      string `json:"credential_id"`
	AuthenticatorData string `json:"authenticator_data"`
	ClientDataJSON    string `json:"client_data_json"`
	SignatureDER      string `json:"signature_der"`
	UserPresence      bool   `json:"user_presence"`
	UserVerification  bool   `json:"user_verification"`
}
type AuthorizationProof struct {
	SchemaVersion      int           `json:"schema_version"`
	Protocol           string        `json:"protocol"`
	Type               string        `json:"type"`
	ChallengeSHA256    string        `json:"challenge_sha256"`
	AuthorityAssertion FIDOAssertion `json:"authority_assertion"`
}

func (d *Dispatcher) Dispatch(ctx context.Context, in DispatchInput, sink ResponseSink) (TerminalResult, error) {
	if sink == nil {
		return TerminalResult{}, ErrStartup
	}
	closed := false
	defer func() {
		if !closed {
			_ = sink.Abort()
		}
	}()
	if d.Scanner == nil || d.Credentials == nil || d.Transport == nil || d.Authority == nil || sink.ConnectionID() != in.ConnectionID || ScannerBuildDigest != in.Request.Authority.ScannerBuildSHA256 {
		return TerminalResult{}, ErrStartup
	}
	policyDigest := protocol.Digest(d.Policy)
	if policyDigest != in.Request.Authority.PolicySHA256 || policyDigest != in.Challenge.PolicySHA256 {
		return TerminalResult{}, ErrBinding
	}
	if err := validateBoundSnapshot(in, d.now()); err != nil {
		return TerminalResult{}, err
	}
	body, err := BuildBody(in.Request, in.Parts)
	if err != nil {
		return TerminalResult{}, err
	}
	if protocol.Digest(body) != in.Challenge.RequestBodySHA256 {
		return TerminalResult{}, ErrBinding
	}
	if err := d.Scanner.Scan(ctx, in.Parts, d.Policy); err != nil {
		return TerminalResult{}, ErrPolicy
	}
	assertion, err := d.Authority.Authorize(ctx, in.TransactionID, in.ConnectionID, in.Peer, in.ConsentChallengeDigest)
	if err != nil {
		return TerminalResult{}, err
	}
	challengeBytes, _ := protocol.CanonicalJSON(in.Challenge)
	wireAssertion := FIDOAssertion{Kind: "fido2-es256", CredentialID: base64.RawURLEncoding.EncodeToString([]byte(assertion.CredentialReference)), AuthenticatorData: base64.RawURLEncoding.EncodeToString(assertion.AuthenticatorData), ClientDataJSON: base64.RawURLEncoding.EncodeToString(assertion.ClientDataJSON), SignatureDER: base64.RawURLEncoding.EncodeToString(assertion.Signature), UserPresence: assertion.UserPresence, UserVerification: assertion.UserVerification}
	proof := AuthorizationProof{SchemaVersion: 1, Protocol: protocol.Name, Type: "authorization_proof", ChallengeSHA256: protocol.Digest(challengeBytes), AuthorityAssertion: wireAssertion}
	if err := sink.WriteAuthorizationProof(ctx, proof); err != nil {
		_ = d.Authority.Cancel(context.Background(), in.TransactionID)
		return TerminalResult{}, ErrSink
	}
	assertionBytes, _ := protocol.CanonicalJSON(wireAssertion)
	credential, err := d.Credentials.Read(ctx)
	if err != nil {
		_ = d.Authority.Cancel(context.Background(), in.TransactionID)
		return TerminalResult{}, err
	}
	defer credential.Destroy()
	if protocol.Digest(body) != in.Challenge.RequestBodySHA256 {
		_ = d.Authority.Cancel(context.Background(), in.TransactionID)
		return TerminalResult{}, ErrBinding
	}
	right, err := d.Authority.BeginSend(ctx, in.TransactionID, in.ConnectionID, in.Peer)
	if err != nil {
		_ = d.Authority.Cancel(context.Background(), in.TransactionID)
		return TerminalResult{}, err
	}
	response, sendErr := d.Transport.Send(ctx, credential, body)
	defer zero(response)
	if sendErr != nil {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "unknown", nil, int64(len(response)), false, sink)
	}
	var projected providerResponse
	if json.Unmarshal(response, &projected) != nil {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "provider_failure", nil, int64(len(response)), false, sink)
	}
	defer zeroProviderResponse(&projected)
	if !providerMetadata.MatchString(projected.ID) || !providerMetadata.MatchString(projected.Provider) || !exactModel(projected.Model, in.Request.Models) || len(projected.Choices) != 1 || !validDeliveredChoice(projected.Choices[0]) {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "provider_failure", nil, int64(len(response)), false, sink)
	}
	usageCanonical, usageErr := canonicalUsage(projected.Usage)
	if usageErr != nil {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "provider_failure", nil, int64(len(response)), false, sink)
	}
	usageDigest := protocol.Digest(usageCanonical)
	zero(usageCanonical)
	content, contentErr := decodeJSONString(projected.Choices[0].Message.Content)
	defer zero(content)
	if contentErr != nil || len(content) == 0 || int64(len(content)) > maxProviderResponse {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "provider_failure", nil, int64(len(response)), false, sink)
	}
	if err := sink.WriteResponse(ctx, content); err != nil {
		return d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "unknown", nil, int64(len(content)), true, sink)
	}
	selected := projected.Model
	fallback := selected != in.Request.Models[0]
	result, err := d.finalizePostSend(ctx, in, right, body, challengeBytes, assertionBytes, "verified", content, int64(len(content)), true, sink, &selected, &projected.ID, &projected.Provider, &usageDigest, &fallback)
	if err == nil {
		closed = true
	}
	return result, err
}

// finalizePostSend is the sole post-network exit. It durably consumes the send
// right, signs the exact terminal projection once, then emits the frozen empty
// response frame for content-free outcomes before closing with the terminal.
func (d *Dispatcher) finalizePostSend(ctx context.Context, in DispatchInput, right authority.SendRight, body, challengeBytes, assertionBytes []byte, outcome string, delivered []byte, accountedBytes int64, responseFrameStarted bool, sink ResponseSink, provenance ...any) (TerminalResult, error) {
	exitCode, walOutcome := 74, "outcome_unknown"
	var selected, generation, serving, usage *string
	var fallback *bool
	if outcome == "provider_failure" {
		exitCode, walOutcome = 73, "provider_failure"
	}
	if outcome == "verified" {
		exitCode, walOutcome = 0, "verified"
		if len(provenance) != 5 {
			return TerminalResult{}, ErrBinding
		}
		selected, _ = provenance[0].(*string)
		generation, _ = provenance[1].(*string)
		serving, _ = provenance[2].(*string)
		usage, _ = provenance[3].(*string)
		fallback, _ = provenance[4].(*bool)
		if selected == nil || generation == nil || serving == nil || usage == nil || fallback == nil {
			return TerminalResult{}, ErrBinding
		}
	}
	signerBytes, _ := protocol.CanonicalJSON(in.Challenge.ResultSigner)
	result := TerminalResult{SchemaVersion: 1, Protocol: protocol.Name, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Outcome: outcome, ExitCode: exitCode, RequestBodySHA256: protocol.Digest(body), ResponseSHA256: protocol.Digest(delivered), ResponseLength: int64(len(delivered)), PartCount: len(in.Parts), Models: append([]string(nil), in.Request.Models...), SelectedModel: selected, Provider: "openrouter", GenerationID: generation, ServingProvider: serving, UsageSHA256: usage, Fallback: fallback, Scope: in.Request.Scope, Sequence: in.Request.Authority.Sequence, IssuedAt: in.Request.Authority.IssuedAt, CompletedAt: d.now().Format(time.RFC3339), ChallengeSHA256: protocol.Digest(challengeBytes), AuthorityAssertionSHA256: protocol.Digest(assertionBytes), ResultSignerSHA256: protocol.Digest(signerBytes), PriorChainDigest: in.Request.Authority.PriorChainDigest, Cleanup: Cleanup{Reservation: "consumed", Connection: "closed", ContentBuffer: "discarded"}, Signature: Signature{Kind: "es256"}}
	terminalInput, err := protocol.TerminalSignatureInput(result)
	if err != nil {
		return TerminalResult{}, ErrBinding
	}
	if err := d.Authority.Finalize(context.Background(), right, accountedBytes, walOutcome, protocol.Digest(terminalInput)); err != nil {
		return TerminalResult{}, err
	}
	sig, err := d.Authority.SignFinalized(right, terminalInput)
	if err != nil {
		return TerminalResult{}, err
	}
	result.Signature.SignatureDER = base64.RawURLEncoding.EncodeToString(sig)
	terminal, err := protocol.CanonicalJSON(result)
	if err != nil {
		return TerminalResult{}, ErrBinding
	}
	if !responseFrameStarted {
		if err := sink.WriteResponse(ctx, nil); err != nil {
			return TerminalResult{}, ErrSink
		}
	}
	if err := sink.WriteTerminalAndClose(ctx, terminal); err != nil {
		return TerminalResult{}, ErrSink
	}
	return result, nil
}

func validateBoundSnapshot(in DispatchInput, now time.Time) error {
	if err := protocol.ValidateRequest(in.Request, now); err != nil {
		return ErrBinding
	}
	challengeBytes, err := protocol.CanonicalJSON(in.Challenge)
	if err != nil || protocol.Digest(challengeBytes) != in.ConsentChallengeDigest {
		return ErrBinding
	}
	r, c, a := in.Request, in.Challenge, in.Request.Authority
	if in.TransactionID != c.TransactionID || c.SchemaVersion != r.SchemaVersion || c.Protocol != r.Protocol || c.Mapping != r.Mapping || c.OperationFamily != r.OperationFamily || c.SubstrateAuthority != r.SubstrateAuthority || c.ConnectionNonceSHA256 != a.ConnectionNonceSHA256 || c.Destination != r.Destination || c.Method != r.Method || c.Path != r.Path || !sameStrings(c.Models, r.Models) || c.Scope != r.Scope || c.DaemonBuildSHA256 != a.DaemonBuildSHA256 || c.ScannerBuildSHA256 != a.ScannerBuildSHA256 || c.PolicySHA256 != a.PolicySHA256 || c.Nonce != a.Nonce || c.Sequence != a.Sequence || c.BootID != a.BootID || c.SessionID != a.SessionID || c.IssuedAt != a.IssuedAt || c.ExpiresAt != a.ExpiresAt || c.PriorChainDigest != a.PriorChainDigest || c.AllocationHelloSHA256 != a.AllocationHelloSHA256 || c.DispatchProposalSHA256 != a.DispatchProposalSHA256 || c.AuthorityAssertion != nil || c.PeerUID != in.Peer.UID || c.PeerPID != in.Peer.PID {
		return ErrBinding
	}
	if r.Destination != protocol.Destination || r.Method != protocol.Method || r.Path != protocol.Path || r.Mapping != protocol.Mapping || r.OperationFamily != "external_provider_dispatch" || r.SubstrateAuthority != "not_asserted" || strings.TrimSpace(a.DaemonBuildSHA256) == "" {
		return ErrBinding
	}
	return nil
}

func sameStrings(a, b []string) bool {
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

func exactModel(actual string, requested []string) bool {
	for _, candidate := range requested {
		if actual == candidate {
			return true
		}
	}
	return false
}

func successfulFinishReason(choice providerChoice) bool {
	if len(choice.Error) != 0 && !bytes.Equal(choice.Error, []byte("null")) {
		return false
	}
	if choice.FinishReason == nil {
		return false
	}
	switch *choice.FinishReason {
	case "stop", "length", "content_filter":
		return true
	default:
		return false
	}
}

func validDeliveredChoice(choice providerChoice) bool {
	return choice.Message.Role == "assistant" && len(choice.Message.Content) != 0 && successfulFinishReason(choice)
}

func canonicalUsage(raw json.RawMessage) ([]byte, error) {
	if len(raw) == 0 || bytes.Equal(raw, []byte("null")) {
		return nil, ErrProvenance
	}
	var usage map[string]any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if decoder.Decode(&usage) != nil || usage == nil {
		return nil, ErrProvenance
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return nil, ErrProvenance
	}
	canonical, err := protocol.CanonicalJSON(usage)
	if err != nil {
		return nil, ErrProvenance
	}
	return canonical, nil
}

func (d *Dispatcher) now() time.Time {
	if d.Clock != nil {
		return d.Clock().UTC()
	}
	return time.Now().UTC()
}
func zero(b []byte) {
	for i := range b {
		b[i] = 0
	}
	_ = sha256.Sum256(b)
}
