// Package provider owns disclosure scanning, OpenRouter wire construction, and
// content-free terminal projection. Callers never receive provider credentials.
package provider

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
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
	ErrPolicy     = errors.New("provider_policy_rejected")
	ErrBinding    = errors.New("provider_binding_invalid")
	ErrTransport  = errors.New("provider_transport_failed")
	ErrProvenance = errors.New("provider_provenance_missing")
	ErrSink       = errors.New("provider_response_delivery_failed")
	ErrStartup    = errors.New("provider_startup_unavailable")
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
	SignTerminal(authority.SendRight, []byte) ([]byte, error)
	Complete(context.Context, string, int64, string) error
	Cleanup(context.Context, string) error
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

type Signature struct {
	Kind         string `json:"kind"`
	SignatureDER string `json:"signature_der"`
}
type Cleanup struct {
	Reservation   string `json:"reservation"`
	Connection    string `json:"connection"`
	ContentBuffer string `json:"content_buffer"`
}
type TerminalResult struct {
	SchemaVersion            int            `json:"schema_version"`
	Protocol                 string         `json:"protocol"`
	OperationFamily          string         `json:"operation_family"`
	SubstrateAuthority       string         `json:"substrate_authority"`
	Outcome                  string         `json:"outcome"`
	ExitCode                 int            `json:"exit_code"`
	RequestBodySHA256        string         `json:"request_body_sha256"`
	ResponseSHA256           string         `json:"response_sha256"`
	ResponseLength           int64          `json:"response_length"`
	PartCount                int            `json:"part_count"`
	Models                   []string       `json:"models"`
	SelectedModel            *string        `json:"selected_model"`
	Provider                 string         `json:"provider"`
	Scope                    protocol.Scope `json:"scope"`
	Sequence                 uint64         `json:"sequence"`
	IssuedAt                 string         `json:"issued_at"`
	CompletedAt              string         `json:"completed_at"`
	ChallengeSHA256          string         `json:"challenge_sha256"`
	AuthorityAssertionSHA256 string         `json:"authority_assertion_sha256"`
	ResultSignerSHA256       string         `json:"result_signer_sha256"`
	PriorChainDigest         string         `json:"prior_chain_digest"`
	Cleanup                  Cleanup        `json:"cleanup"`
	Signature                Signature      `json:"signature"`
}

type providerResponse struct {
	ID       string          `json:"id"`
	Model    string          `json:"model"`
	Provider string          `json:"provider"`
	Usage    json.RawMessage `json:"usage"`
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
	if d.Scanner == nil || d.Credentials == nil || d.Transport == nil || d.Authority == nil || sink == nil || sink.ConnectionID() != in.ConnectionID || ScannerBuildDigest != in.Request.Authority.ScannerBuildSHA256 {
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
	// The frozen terminal requires cleanup.connection="closed" while that same
	// connection is still needed to emit the terminal frame. Until IPC owns an
	// atomic close-and-terminal projection, signing would assert a future state.
	// Refuse before FIDO, credential access, DNS, or provider contact.
	return TerminalResult{}, ErrStartup

	/* unreachable transport composition retained for the contract revision that
	truthfully separates response delivery from completed connection cleanup.
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
	outcome, exitCode, walOutcome := "verified", 0, "verified"
	if sendErr != nil {
		outcome, exitCode, walOutcome = "unknown", 74, "outcome_unknown"
	}
	selected := in.Request.Models[0]
	if sendErr == nil {
		var projected providerResponse
		if json.Unmarshal(response, &projected) != nil || projected.ID == "" || projected.Provider == "" || len(projected.Usage) == 0 || string(projected.Usage) == "null" || !exactModel(projected.Model, in.Request.Models) {
			sendErr = ErrProvenance
			outcome, exitCode, walOutcome = "provider_failure", 73, "provider_failure"
		} else {
			selected = projected.Model
		}
	}
	if sendErr == nil {
		if err := sink.WriteResponse(ctx, response); err != nil {
			sendErr, outcome, exitCode, walOutcome = ErrSink, "unknown", 74, "outcome_unknown"
		}
	}
	responseDigest := protocol.Digest(response)
	signerBytes, _ := protocol.CanonicalJSON(in.Challenge.ResultSigner)
	// Provider is the frozen destination projection, not serving-provider
	// provenance. The exact raw response digest transitively binds the verified
	// generation id, response model, serving provider, and usage object.
	result := TerminalResult{SchemaVersion: 1, Protocol: protocol.Name, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Outcome: outcome, ExitCode: exitCode, RequestBodySHA256: protocol.Digest(body), ResponseSHA256: responseDigest, ResponseLength: int64(len(response)), PartCount: len(in.Parts), Models: append([]string(nil), in.Request.Models...), SelectedModel: &selected, Provider: "openrouter", Scope: in.Request.Scope, Sequence: in.Request.Authority.Sequence, IssuedAt: in.Request.Authority.IssuedAt, CompletedAt: d.now().Format(time.RFC3339), ChallengeSHA256: protocol.Digest(challengeBytes), AuthorityAssertionSHA256: protocol.Digest(assertionBytes), ResultSignerSHA256: protocol.Digest(signerBytes), PriorChainDigest: in.Request.Authority.PriorChainDigest, Cleanup: Cleanup{Reservation: "consumed", Connection: "closed", ContentBuffer: "discarded"}, Signature: Signature{Kind: "es256"}}
	unsignedBytes, _ := protocol.CanonicalJSON(result)
	var unsigned map[string]any
	_ = json.Unmarshal(unsignedBytes, &unsigned)
	delete(unsigned, "signature")
	canonical, _ := protocol.CanonicalJSON(unsigned)
	sig, signErr := d.Authority.SignTerminal(right, append([]byte("workflow-authority\x00provider-dispatch-v1\x00terminal\x00"), canonical...))
	if signErr != nil {
		return TerminalResult{}, signErr
	}
	result.Signature.SignatureDER = base64.RawURLEncoding.EncodeToString(sig)
	if completeErr := d.Authority.Complete(ctx, in.TransactionID, int64(len(response)), walOutcome); completeErr != nil {
		return TerminalResult{}, completeErr
	}
	if cleanupErr := d.Authority.Cleanup(ctx, in.TransactionID); cleanupErr != nil {
		return TerminalResult{}, cleanupErr
	}
	zero(response)
	return result, sendErr */
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
	if in.TransactionID != c.TransactionID || c.SchemaVersion != r.SchemaVersion || c.Protocol != r.Protocol || c.Mapping != r.Mapping || c.OperationFamily != r.OperationFamily || c.SubstrateAuthority != r.SubstrateAuthority || c.ConnectionNonceSHA256 != a.ConnectionNonceSHA256 || c.Destination != r.Destination || c.Method != r.Method || c.Path != r.Path || !sameStrings(c.Models, r.Models) || c.Scope != r.Scope || c.DaemonBuildSHA256 != a.DaemonBuildSHA256 || c.ScannerBuildSHA256 != a.ScannerBuildSHA256 || c.PolicySHA256 != a.PolicySHA256 || c.Nonce != a.Nonce || c.Sequence != a.Sequence || c.BootID != a.BootID || c.SessionID != a.SessionID || c.IssuedAt != a.IssuedAt || c.ExpiresAt != a.ExpiresAt || c.PriorChainDigest != a.PriorChainDigest || c.AuthorityAssertion != nil || c.PeerUID != in.Peer.UID || c.PeerPID != in.Peer.PID {
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

func (r TerminalResult) String() string { return fmt.Sprintf("%s:%d", r.Outcome, r.ExitCode) }
