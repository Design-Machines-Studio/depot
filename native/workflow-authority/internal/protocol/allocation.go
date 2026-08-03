package protocol

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"time"
	"unicode/utf8"
)

const (
	AuthorityHelloType   = "authority_hello"
	DispatchProposalType = "dispatch_proposal"
	ConsentAckType       = "consent_ack"
	SafeErrorType        = "safe_error"
	AllocationTransport  = "unix-sock-stream-single-connection"
	AllocationFirstFrame = "daemon-u32be-canonical-authority_hello"
	AllocationNextFrame  = "caller-u32be-canonical-dispatch_proposal"
	AllocationPartFrames = "caller-ordered-u64be-exact-utf8"
	AllocationOrdering   = "global-serialized-sequence"
	AllocationDiscovery  = "fixed-trusted-endpoint-only"
	AllocationAncillary  = "reject"
)

type AllocationLimits struct {
	MaxRequestBytes      int64  `json:"max_request_bytes"`
	MaxResponseBytes     int64  `json:"max_response_bytes"`
	MaxParts             int    `json:"max_parts"`
	MaxActiveAllocations int    `json:"max_active_allocations"`
	AllocationTTLSeconds int    `json:"allocation_ttl_seconds"`
	Cancellation         string `json:"cancellation"`
}

func FrozenAllocationLimits() AllocationLimits {
	return AllocationLimits{
		MaxRequestBytes:      8_388_608,
		MaxResponseBytes:     8_388_608,
		MaxParts:             256,
		MaxActiveAllocations: 1,
		AllocationTTLSeconds: 120,
		Cancellation:         "consume_tombstone",
	}
}

// AuthorityHello is allocated and emitted by the daemon before it reads any
// repository-controlled request bytes. No field in this type is caller-owned.
type AuthorityHello struct {
	SchemaVersion         int              `json:"schema_version"`
	Protocol              string           `json:"protocol"`
	Type                  string           `json:"type"`
	DaemonBuildSHA256     string           `json:"daemon_build_sha256"`
	ScannerBuildSHA256    string           `json:"scanner_build_sha256"`
	PolicySHA256          string           `json:"policy_sha256"`
	BootID                string           `json:"boot_id"`
	SessionID             string           `json:"session_id"`
	Sequence              uint64           `json:"sequence"`
	IssuedAt              string           `json:"issued_at"`
	ExpiresAt             string           `json:"expires_at"`
	PriorChainDigest      string           `json:"prior_chain_digest"`
	ConnectionNonceSHA256 string           `json:"connection_nonce_sha256"`
	Limits                AllocationLimits `json:"limits"`
}

// DispatchProposal contains only facts the caller is permitted to propose.
// The raw part bytes follow in declared order and must match Parts exactly.
type DispatchProposal struct {
	SchemaVersion        int      `json:"schema_version"`
	Protocol             string   `json:"protocol"`
	Type                 string   `json:"type"`
	Mapping              string   `json:"mapping"`
	OperationFamily      string   `json:"operation_family"`
	SubstrateAuthority   string   `json:"substrate_authority"`
	Destination          string   `json:"destination"`
	Method               string   `json:"method"`
	Path                 string   `json:"path"`
	Models               []string `json:"models"`
	Parts                []Part   `json:"parts"`
	Scope                Scope    `json:"scope"`
	CallerNonce          string   `json:"caller_nonce"`
	AuthorityHelloSHA256 string   `json:"authority_hello_sha256"`
}

type ConsentAck struct {
	SchemaVersion   int    `json:"schema_version"`
	Protocol        string `json:"protocol"`
	Type            string `json:"type"`
	ChallengeSHA256 string `json:"challenge_sha256"`
}

type SafeError struct {
	SchemaVersion    int    `json:"schema_version"`
	Protocol         string `json:"protocol"`
	Type             string `json:"type"`
	Code             string `json:"code"`
	ExitCode         int    `json:"exit_code"`
	Consumed         bool   `json:"consumed"`
	NetworkAttempted bool   `json:"network_attempted"`
}

func ValidateAuthorityHello(hello AuthorityHello, now time.Time) error {
	if hello.SchemaVersion != Version || hello.Protocol != Name || hello.Type != AuthorityHelloType || hello.Limits != FrozenAllocationLimits() || hello.Sequence == 0 {
		return ErrInvalidDocument
	}
	for _, digest := range []string{hello.DaemonBuildSHA256, hello.ScannerBuildSHA256, hello.PolicySHA256, hello.PriorChainDigest, hello.ConnectionNonceSHA256} {
		if !digestPattern.MatchString(digest) {
			return ErrInvalidDocument
		}
	}
	for _, id := range []string{hello.BootID, hello.SessionID} {
		if !idPattern.MatchString(id) {
			return ErrInvalidDocument
		}
	}
	if !timePattern.MatchString(hello.IssuedAt) || !timePattern.MatchString(hello.ExpiresAt) {
		return ErrInvalidDocument
	}
	issued, issuedErr := time.Parse(time.RFC3339, hello.IssuedAt)
	expires, expiresErr := time.Parse(time.RFC3339, hello.ExpiresAt)
	if issuedErr != nil || expiresErr != nil || issued.After(now) || !issued.Before(expires) {
		return ErrInvalidDocument
	}
	if !now.Before(expires) {
		return errors.New("authorization_expired")
	}
	if expires.Sub(issued) != time.Duration(FrozenAllocationLimits().AllocationTTLSeconds)*time.Second {
		return ErrInvalidDocument
	}
	return nil
}

func ValidateDispatchProposal(proposal DispatchProposal, partBytes [][]byte) error {
	if proposal.SchemaVersion != Version || proposal.Protocol != Name || proposal.Type != DispatchProposalType || proposal.Mapping != Mapping || proposal.OperationFamily != "external_provider_dispatch" || proposal.SubstrateAuthority != "not_asserted" || proposal.Destination != Destination || proposal.Method != Method || proposal.Path != Path {
		return ErrInvalidDocument
	}
	limits := FrozenAllocationLimits()
	if !idPattern.MatchString(proposal.CallerNonce) || !digestPattern.MatchString(proposal.AuthorityHelloSHA256) || len(proposal.Models) == 0 || len(proposal.Models) > limits.MaxParts || len(proposal.Parts) == 0 || len(proposal.Parts) > limits.MaxParts || len(partBytes) != len(proposal.Parts) {
		return ErrInvalidDocument
	}
	for _, value := range []string{proposal.Scope.Repository, proposal.Scope.RunID, proposal.Scope.Lane, proposal.Scope.Candidate, proposal.Scope.Workload} {
		if !idPattern.MatchString(value) {
			return ErrInvalidDocument
		}
	}
	seenModels := make(map[string]struct{}, len(proposal.Models))
	for _, model := range proposal.Models {
		if !idPattern.MatchString(model) {
			return ErrInvalidDocument
		}
		if _, exists := seenModels[model]; exists {
			return ErrInvalidDocument
		}
		seenModels[model] = struct{}{}
	}
	var total int64
	for index, part := range proposal.Parts {
		if (part.Role != "system" && part.Role != "user") || part.ContentLength < 0 || part.ContentLength > MaxFrameBytes || !digestPattern.MatchString(part.ContentSHA256) || int64(len(partBytes[index])) != part.ContentLength || Digest(partBytes[index]) != part.ContentSHA256 || !utf8.Valid(partBytes[index]) {
			return ErrPartMismatch
		}
		total += part.ContentLength
	}
	if total > limits.MaxRequestBytes {
		return ErrFrameTooLarge
	}
	return nil
}

func AuthorityHelloBytes(hello AuthorityHello, now time.Time) ([]byte, error) {
	if err := ValidateAuthorityHello(hello, now); err != nil {
		return nil, err
	}
	return CanonicalJSON(hello)
}

func DispatchProposalBytes(proposal DispatchProposal, partBytes [][]byte) ([]byte, error) {
	if err := ValidateDispatchProposal(proposal, partBytes); err != nil {
		return nil, err
	}
	return CanonicalJSON(proposal)
}

func ValidateConsentAck(ack ConsentAck) error {
	if ack.SchemaVersion != Version || ack.Protocol != Name || ack.Type != ConsentAckType || !digestPattern.MatchString(ack.ChallengeSHA256) {
		return ErrInvalidDocument
	}
	return nil
}

var safeErrorExit = map[string]int{
	"authorization_declined": 71, "authorization_expired": 71, "authorization_replayed": 71,
	"consent_connection_invalid": 71, "disclosure_declined": 72, "provider_failure": 73,
	"provider_result_unknown": 74, "result_verification_failed": 75, "authority_unavailable": 70,
}

var safeErrorNetworkAttempted = map[string]bool{
	"authorization_declined": false, "authorization_expired": false, "authorization_replayed": false,
	"consent_connection_invalid": false, "disclosure_declined": false, "authority_unavailable": false,
	"provider_failure": true, "provider_result_unknown": true, "result_verification_failed": true,
}

func ValidateSafeError(value SafeError) error {
	exit, ok := safeErrorExit[value.Code]
	if value.SchemaVersion != Version || value.Protocol != Name || value.Type != SafeErrorType || !ok || value.ExitCode != exit || !value.Consumed || value.NetworkAttempted != safeErrorNetworkAttempted[value.Code] {
		return ErrInvalidDocument
	}
	return nil
}

// TerminalSignatureInput removes only the signature member and freezes the
// exact v1 domain-separated bytes. Callers must validate the terminal document
// with its closed result validator before invoking this projection helper.
func TerminalSignatureInput(document any) ([]byte, error) {
	raw, err := CanonicalJSON(document)
	if err != nil {
		return nil, err
	}
	var projection map[string]json.RawMessage
	if err := DecodeClosed(raw, &projection); err != nil {
		return nil, err
	}
	if _, exists := projection["signature"]; !exists {
		return nil, ErrInvalidDocument
	}
	delete(projection, "signature")
	canonical, err := CanonicalJSON(projection)
	if err != nil {
		return nil, err
	}
	return append([]byte("workflow-authority\x00provider-dispatch-v1\x00terminal\x00"), canonical...), nil
}

// VerifyTerminalES256 verifies the production ephemeral signer projection.
// Both inputs use the protocol's unpadded base64url encoding.
func VerifyTerminalES256(publicKeySEC1, signatureDER string, terminalInput []byte) error {
	if len(publicKeySEC1) > 4096 || len(signatureDER) > 4096 || len(terminalInput) > MaxFrameBytes {
		return ErrInvalidDocument
	}
	keyBytes, err := base64.RawURLEncoding.DecodeString(publicKeySEC1)
	if err != nil {
		return ErrInvalidDocument
	}
	keyX, keyY := elliptic.Unmarshal(elliptic.P256(), keyBytes)
	if keyX == nil || keyY == nil {
		return ErrInvalidDocument
	}
	signature, err := base64.RawURLEncoding.DecodeString(signatureDER)
	if err != nil {
		return ErrInvalidDocument
	}
	digest := sha256.Sum256(terminalInput)
	if !ecdsa.VerifyASN1(&ecdsa.PublicKey{Curve: elliptic.P256(), X: keyX, Y: keyY}, digest[:], signature) {
		return errors.New("terminal_binding_invalid")
	}
	return nil
}
