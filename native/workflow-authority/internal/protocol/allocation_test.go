package protocol

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"strings"
	"testing"
	"time"
)

var allocationNow = time.Date(2026, 8, 3, 0, 1, 0, 0, time.UTC)

func allocationHello() AuthorityHello {
	return AuthorityHello{
		SchemaVersion: Version, Protocol: Name, Type: AuthorityHelloType,
		DaemonBuildSHA256:  "sha256:" + strings.Repeat("1", 64),
		ScannerBuildSHA256: "sha256:" + strings.Repeat("2", 64),
		PolicySHA256:       "sha256:" + strings.Repeat("3", 64),
		BootID:             "boot-01", SessionID: "session-01", Sequence: 7,
		IssuedAt: "2026-08-03T00:00:00Z", ExpiresAt: "2026-08-03T00:02:00Z",
		PriorChainDigest:      "sha256:" + strings.Repeat("4", 64),
		ConnectionNonceSHA256: "sha256:" + strings.Repeat("5", 64),
		Limits:                FrozenAllocationLimits(),
	}
}

func allocationProposal(helloDigest string, parts [][]byte) DispatchProposal {
	declared := make([]Part, len(parts))
	for index, part := range parts {
		declared[index] = Part{Role: []string{"system", "user"}[index], ContentLength: int64(len(part)), ContentSHA256: Digest(part)}
	}
	return DispatchProposal{
		SchemaVersion: Version, Protocol: Name, Type: DispatchProposalType,
		Mapping: Mapping, OperationFamily: "external_provider_dispatch",
		SubstrateAuthority: "not_asserted", Destination: Destination, Method: Method, Path: Path,
		Models: []string{"openai/gpt-5.6", "z-ai/glm-5.2"}, Parts: declared,
		Scope:       Scope{Repository: "design-machines/depot", RunID: "run-01", Lane: "assessment", Candidate: "candidate-01", Workload: "pipeline-assessment"},
		CallerNonce: "caller-nonce-01", AuthorityHelloSHA256: helloDigest,
	}
}

func TestAuthorityHelloAndProposalFrozenBytes(t *testing.T) {
	if AllocationFirstFrame != "daemon-u32be-canonical-authority_hello" || AllocationNextFrame != "caller-u32be-canonical-dispatch_proposal" || AllocationOrdering != "required-global-serialized-sequence" || AllocationDiscovery != "required-fixed-trusted-endpoint-only" || AllocationAncillary != "required-reject" {
		t.Fatal("allocation exchange ordering drifted")
	}
	hello := allocationHello()
	helloBytes, err := AuthorityHelloBytes(hello, allocationNow)
	if err != nil {
		t.Fatal(err)
	}
	if got := Digest(helloBytes); got != "sha256:0c87d5da2f7b95d06c6d4d88c7e4446e822d4e70d1ae6b61dafe4dec5623160b" {
		t.Fatalf("hello bytes drifted: %s\n%s", got, helloBytes)
	}
	parts := [][]byte{[]byte("system\n"), []byte("user \xf0\x9f\x8c\x8d\n")}
	proposal := allocationProposal(Digest(helloBytes), parts)
	proposalBytes, err := DispatchProposalBytes(proposal, parts)
	if err != nil {
		t.Fatal(err)
	}
	if got := Digest(proposalBytes); got != "sha256:6e2f9d1a114effc6f5b2812af231f2f794b6002a8b96c807e4e47e72d6321fd6" {
		t.Fatalf("proposal bytes drifted: %s\n%s", got, proposalBytes)
	}
	request, err := BindAllocationRequest(hello, proposal, parts, allocationNow)
	if err != nil || request.Authority.Nonce != proposal.CallerNonce || request.Authority.AllocationHelloSHA256 != Digest(helloBytes) || request.Authority.DispatchProposalSHA256 != Digest(proposalBytes) {
		t.Fatalf("allocation request binding mismatch: %+v %v", request.Authority, err)
	}
	wrongHelloDigest := proposal
	wrongHelloDigest.AuthorityHelloSHA256 = "sha256:" + strings.Repeat("0", 64)
	if _, err := BindAllocationRequest(hello, wrongHelloDigest, parts, allocationNow); err == nil {
		t.Fatal("proposal from another hello accepted")
	}
	otherHello := hello
	otherHello.ConnectionNonceSHA256 = "sha256:" + strings.Repeat("6", 64)
	if _, err := BindAllocationRequest(otherHello, proposal, parts, allocationNow); err == nil {
		t.Fatal("same-connection hello substitution accepted")
	}
	otherNonce := proposal
	otherNonce.CallerNonce = "caller-nonce-02"
	boundOtherNonce, err := BindAllocationRequest(hello, otherNonce, parts, allocationNow)
	otherProposalBytes, _ := DispatchProposalBytes(otherNonce, parts)
	if err != nil || boundOtherNonce.Authority.Nonce != otherNonce.CallerNonce || boundOtherNonce.Authority.DispatchProposalSHA256 != Digest(otherProposalBytes) || boundOtherNonce.Authority.DispatchProposalSHA256 == request.Authority.DispatchProposalSHA256 {
		t.Fatal("caller nonce was not bound through the proposal digest")
	}
}

func TestCanonicalJSONUnicodeSeparatorProfile(t *testing.T) {
	got, err := CanonicalJSON(map[string]string{"control": "\u0001", "text": "café\u2028x\u2029"})
	if err != nil {
		t.Fatal(err)
	}
	want := []byte(`{"control":"\u0001","text":"café\u2028x\u2029"}`)
	if string(got) != string(want) {
		t.Fatalf("canonical unicode profile mismatch:\n got %q\nwant %q", got, want)
	}
}

func TestAllocationRejectsCallerHostFieldsAndAlteredParts(t *testing.T) {
	helloBytes, _ := AuthorityHelloBytes(allocationHello(), allocationNow)
	parts := [][]byte{[]byte("system\n"), []byte("user \xf0\x9f\x8c\x8d\n")}
	proposal := allocationProposal(Digest(helloBytes), parts)
	canonical, _ := CanonicalJSON(proposal)
	hostile := append(canonical[:len(canonical)-1], []byte(`,"sequence":9}`)...)
	var decoded DispatchProposal
	if err := DecodeClosed(hostile, &decoded); err == nil {
		t.Fatal("caller-provided host sequence accepted")
	}
	altered := append([]byte(nil), parts[1]...)
	altered[0] = 'X'
	if err := ValidateDispatchProposal(proposal, [][]byte{parts[0], altered}); err != ErrPartMismatch {
		t.Fatalf("altered part accepted: %v", err)
	}
	if err := ValidateDispatchProposal(proposal, [][]byte{parts[0], {0xff}}); err != ErrPartMismatch {
		t.Fatalf("non-UTF8 part accepted: %v", err)
	}
}

func TestAllocationTimeAndLifecycleLimitsFailClosed(t *testing.T) {
	hello := allocationHello()
	if err := ValidateAuthorityHello(hello, time.Date(2026, 8, 3, 0, 2, 0, 0, time.UTC)); err == nil || err.Error() != "authorization_expired" {
		t.Fatalf("expired allocation accepted: %v", err)
	}
	hello.Limits.MaxActiveAllocations = 2
	if err := ValidateAuthorityHello(hello, allocationNow); err != ErrInvalidDocument {
		t.Fatalf("parallel allocation downgrade accepted: %v", err)
	}
	hello = allocationHello()
	hello.Sequence = uint64(^uint64(0)>>1) + 1
	if err := ValidateAuthorityHello(hello, allocationNow); err != ErrInvalidDocument {
		t.Fatalf("cross-language sequence overflow accepted: %v", err)
	}
	hello = allocationHello()
	hello.ExpiresAt = "2026-08-03T00:03:00Z"
	if err := ValidateAuthorityHello(hello, allocationNow); err != ErrInvalidDocument {
		t.Fatalf("non-frozen TTL accepted: %v", err)
	}
}

func TestTypedConsentSafeErrorAndTerminalES256Projection(t *testing.T) {
	digest := "sha256:" + strings.Repeat("a", 64)
	if err := ValidateConsentAck(ConsentAck{SchemaVersion: 1, Protocol: Name, Type: ConsentAckType, ChallengeSHA256: digest}); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSafeError(SafeError{SchemaVersion: 1, Protocol: Name, Type: SafeErrorType, Code: "authorization_declined", ExitCode: 71, Consumed: true, NetworkAttempted: false}); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSafeError(SafeError{SchemaVersion: 1, Protocol: Name, Type: SafeErrorType, Code: "provider_failure", ExitCode: 73, Consumed: true, NetworkAttempted: true}); err == nil {
		t.Fatal("post-send outcome accepted as unsigned safe error")
	}
	selected := "openai/gpt-5.6"
	generation, serving, usage, fallback := "generation-01", "provider-01", digest, false
	document := TerminalResult{
		SchemaVersion: 1, Protocol: Name, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted",
		Outcome: "verified", ExitCode: 0, RequestBodySHA256: digest, ResponseSHA256: digest,
		ResponseLength: 2, PartCount: 2, Models: []string{selected, "z-ai/glm-5.2"}, SelectedModel: &selected,
		Provider: "openrouter", GenerationID: &generation, ServingProvider: &serving, UsageSHA256: &usage, Fallback: &fallback,
		Scope:    Scope{Repository: "design-machines/depot", RunID: "run-01", Lane: "assessment", Candidate: "candidate-01", Workload: "pipeline-assessment"},
		Sequence: 7, IssuedAt: "2026-08-03T00:00:00Z", CompletedAt: "2026-08-03T00:00:03Z",
		ChallengeSHA256: digest, AuthorityAssertionSHA256: digest, ResultSignerSHA256: digest, PriorChainDigest: digest,
		Cleanup:   TerminalCleanup{Reservation: "consumed", Connection: "closed", ContentBuffer: "discarded"},
		Signature: TerminalSignature{Kind: "es256", SignatureDER: "AQ"},
	}
	input, err := TerminalSignatureInput(document)
	if err != nil {
		t.Fatal(err)
	}
	if got := Digest(input); got != "sha256:a3cf86fea1196b642958ec23155e32ffadd0726697b91572602ad3e23f969205" {
		t.Fatalf("terminal projection drifted: %s\n%s", got, input)
	}
	fixtureDocument := document
	fixtureDocument.Signature = TerminalSignature{Kind: "fixture-rsa-sha256-v1", Domain: "fixture.workflow-authority.invalid", Value: "fixture-rsa-sha256-v1:" + strings.Repeat("0", 256)}
	fixtureInput, err := TerminalSignatureInput(fixtureDocument)
	if err != nil || string(fixtureInput) != string(input) {
		t.Fatalf("signature kind changed terminal projection: %v", err)
	}
	if _, err := TerminalSignatureInput(map[string]any{"schema_version": 1, "protocol": Name, "outcome": "verified", "signature": map[string]any{"kind": "es256", "signature_der": "AQ"}}); err == nil {
		t.Fatal("incomplete terminal projected")
	}
	invalidSequence := document
	invalidSequence.Sequence = uint64(^uint64(0)>>1) + 1
	if _, err := TerminalSignatureInput(invalidSequence); err == nil {
		t.Fatal("out-of-range terminal sequence projected")
	}
	failure := document
	failure.Outcome, failure.ExitCode = "provider_failure", 73
	failure.ResponseSHA256, failure.ResponseLength = Digest(nil), 0
	failure.SelectedModel, failure.GenerationID, failure.ServingProvider, failure.UsageSHA256, failure.Fallback = nil, nil, nil, nil, nil
	if _, err := TerminalSignatureInput(failure); err != nil {
		t.Fatalf("content-free signed failure rejected: %v", err)
	}
	mixed := failure
	mixed.GenerationID = &generation
	if _, err := TerminalSignatureInput(mixed); err == nil {
		t.Fatal("failure with invented provenance projected")
	}
	downgrade := failure
	downgrade.Signature = TerminalSignature{Kind: "hmac", Value: "forbidden"}
	if _, err := TerminalSignatureInput(downgrade); err == nil {
		t.Fatal("terminal signature downgrade projected")
	}
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	hash := sha256.Sum256(input)
	signature, _ := ecdsa.SignASN1(rand.Reader, key, hash[:])
	publicKey := base64.RawURLEncoding.EncodeToString(elliptic.Marshal(elliptic.P256(), key.X, key.Y))
	if err := VerifyTerminalES256(publicKey, base64.RawURLEncoding.EncodeToString(signature), input); err != nil {
		t.Fatal(err)
	}
	input[0] ^= 1
	if err := VerifyTerminalES256(publicKey, base64.RawURLEncoding.EncodeToString(signature), input); err == nil {
		t.Fatal("altered terminal projection verified")
	}
}
