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
	if AllocationFirstFrame != "daemon-u32be-canonical-authority_hello" || AllocationNextFrame != "caller-u32be-canonical-dispatch_proposal" || AllocationOrdering != "global-serialized-sequence" || AllocationDiscovery != "fixed-trusted-endpoint-only" {
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
	if err := ValidateSafeError(SafeError{SchemaVersion: 1, Protocol: Name, Type: SafeErrorType, Code: "provider_failure", ExitCode: 73, Consumed: true, NetworkAttempted: true}); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSafeError(SafeError{SchemaVersion: 1, Protocol: Name, Type: SafeErrorType, Code: "provider_failure", ExitCode: 73, Consumed: true, NetworkAttempted: false}); err == nil {
		t.Fatal("provider failure network state downgrade accepted")
	}
	document := map[string]any{"schema_version": 1, "protocol": Name, "outcome": "verified", "signature": map[string]any{"kind": "es256", "signature_der": "placeholder"}}
	input, err := TerminalSignatureInput(document)
	if err != nil {
		t.Fatal(err)
	}
	expected := "workflow-authority\x00provider-dispatch-v1\x00terminal\x00{\"outcome\":\"verified\",\"protocol\":\"workflow-authority-provider-dispatch-v1\",\"schema_version\":1}"
	if string(input) != expected {
		t.Fatalf("terminal projection drifted: %q", input)
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
