package authority

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

func TestStubNeverReportsProductionReady(t *testing.T) {
	adapter := NewFIDOAdapter()
	readiness := adapter.Readiness(context.Background())
	if readiness.Production || readiness.Adapter != "stub" || readiness.InternalUV {
		t.Fatalf("unsafe stub readiness: %+v", readiness)
	}
	if _, err := adapter.Assert(context.Background(), []byte("challenge"), Credential{}); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("stub assertion: %v", err)
	}
}

func TestFIDOUPUVHostPINAndGenerationFailures(t *testing.T) {
	mutations := map[string]func(*Assertion){"missing-up": func(a *Assertion) { a.UserPresence = false }, "missing-uv": func(a *Assertion) { a.UserVerification = false }, "host-pin": func(a *Assertion) { a.HostPINRequested = true }, "generation": func(a *Assertion) { a.Generation++ }, "credential": func(a *Assertion) { a.CredentialReference = "other" }}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			manager, challenge, peer, _ := reserve(t, &fakeFIDO{mutate: mutate}, &memoryWAL{})
			canonical, _ := protocol.CanonicalJSON(challenge)
			if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err == nil {
				t.Fatal("invalid assertion authorized")
			}
		})
	}
}

type fakeTerminal struct {
	identity []TerminalIdentity
	writes   bytes.Buffer
	line     string
	err      error
	calls    int
}

func (t *fakeTerminal) Identity() (TerminalIdentity, error) {
	if t.err != nil {
		return TerminalIdentity{}, t.err
	}
	i := t.calls
	if i >= len(t.identity) {
		i = len(t.identity) - 1
	}
	t.calls++
	return t.identity[i], nil
}
func (t *fakeTerminal) Write(p []byte) (int, error) { return t.writes.Write(p) }
func (t *fakeTerminal) ReadLine() (string, error)   { return t.line, t.err }

func TestConsentRendersExactScopeAndStableTTY(t *testing.T) {
	_, challenge, _, _ := fixture(t)
	challenge.ResultSigner = protocol.ResultSigner{Kind: "ephemeral-es256", PublicKeySEC1: "public-signer"}
	id := TerminalIdentity{Device: 1, Inode: 2}
	terminal := &fakeTerminal{identity: []TerminalIdentity{id, id, id}, line: "AUTHORIZE\n"}
	if err := ConfirmExactScope(terminal, challenge); err != nil {
		t.Fatal(err)
	}
	rendered := terminal.writes.String()
	for _, value := range []string{challenge.Scope.Repository, challenge.Scope.RunID, challenge.Scope.Lane, challenge.Scope.Candidate, challenge.Models[0], challenge.RequestBodySHA256, challenge.PolicySHA256, challenge.ExpiresAt, challenge.ResultSigner.PublicKeySEC1} {
		if !strings.Contains(rendered, value) {
			t.Fatalf("scope omitted %q", value)
		}
	}
	if strings.Contains(rendered, "prompt-secret") || strings.Contains(rendered, "response-secret") {
		t.Fatal("content leaked")
	}
}

func TestConsentRejectsTTYChangeRedirectAndDecline(t *testing.T) {
	_, challenge, _, _ := fixture(t)
	challenge.ResultSigner = protocol.ResultSigner{Kind: "ephemeral-es256", PublicKeySEC1: "public"}
	stable := TerminalIdentity{1, 2}
	cases := map[string]*fakeTerminal{"changed": {identity: []TerminalIdentity{stable, {1, 3}}, line: "AUTHORIZE\n"}, "decline": {identity: []TerminalIdentity{stable, stable, stable}, line: "no\n"}, "missing": {identity: []TerminalIdentity{stable}, err: os.ErrNotExist}}
	for name, terminal := range cases {
		t.Run(name, func(t *testing.T) {
			if err := ConfirmExactScope(terminal, challenge); err == nil {
				t.Fatal("unsafe terminal accepted")
			}
		})
	}
}

func TestEnrollmentRotationRevokeAndRecovery(t *testing.T) {
	now := time.Now().UTC()
	credential := Credential{Reference: "generation-1", PublicKey: []byte("public"), Algorithm: -7, Generation: 1, RPID: "workflow-authority.designmachines.local", EnrolledAt: now, Status: "active", InternalUV: true, ID: []byte("root-private-id")}
	registry := NewEnrollmentRegistry()
	if err := registry.Enroll(credential, false); err == nil {
		t.Fatal("repository bootstrapped enrollment")
	}
	if err := registry.Enroll(credential, true); err != nil {
		t.Fatal(err)
	}
	active, _ := registry.Active()
	if len(active.ID) != 0 {
		t.Fatal("raw credential id persisted")
	}
	next := credential
	next.Reference = "generation-2"
	next.Generation = 2
	if err := registry.Enroll(next, true); err != nil {
		t.Fatal(err)
	}
	if err := registry.Revoke(2, now, true); err != nil {
		t.Fatal(err)
	}
	if _, err := registry.Active(); err == nil {
		t.Fatal("revoked credential stayed active")
	}
	next.Generation = 3
	if err := registry.Recover(next, true, false); err == nil {
		t.Fatal("single-party recovery accepted")
	}
	if err := registry.Recover(next, true, true); err != nil {
		t.Fatal(err)
	}
}

func TestProtocolClosedDecoderFramingAndDepth(t *testing.T) {
	request, _, _, clock := fixture(t)
	canonical, err := protocol.CanonicalJSON(request)
	if err != nil {
		t.Fatal(err)
	}
	var decoded protocol.Request
	if err := protocol.DecodeClosed(canonical, &decoded); err != nil {
		t.Fatal(err)
	}
	if err := protocol.ValidateRequest(decoded, clock.Now()); err != nil {
		t.Fatal(err)
	}
	for name, raw := range map[string][]byte{"duplicate": []byte(`{"authority":{},"authority":{}}`), "unknown": append(canonical[:len(canonical)-1], []byte(`,"unknown":true}`)...), "noncanonical": append([]byte(" "), canonical...)} {
		t.Run(name, func(t *testing.T) {
			var got protocol.Request
			if err := protocol.DecodeClosed(raw, &got); err == nil {
				t.Fatal("invalid JSON accepted")
			}
		})
	}
	deep := []byte(strings.Repeat("[", 17) + "0" + strings.Repeat("]", 17))
	var got any
	if err := protocol.DecodeClosed(deep, &got); err == nil {
		t.Fatal("deep document accepted")
	}
	var wire bytes.Buffer
	header := make([]byte, 4)
	binary.BigEndian.PutUint32(header, protocol.MaxFrameBytes+1)
	wire.Write(header)
	if _, err := protocol.ReadFrame(&wire); !errors.Is(err, protocol.ErrFrameTooLarge) {
		t.Fatalf("oversize: %v", err)
	}
	if err := protocol.RequireNoAncillary(1); err == nil {
		t.Fatal("ancillary descriptor accepted")
	}
	framed := append([]byte{0, 0, 0, 1, 'x'}, 'y')
	if _, err := protocol.ReadSingleFrame(bytes.NewReader(framed)); !errors.Is(err, protocol.ErrTrailingData) {
		t.Fatalf("trailing exchange accepted: %v", err)
	}
}

func TestFrozenM0RequestGrammarRejectsEveryRelaxation(t *testing.T) {
	request, _, _, clock := fixture(t)
	mutations := map[string]func(*protocol.Request){
		"duplicate-model":     func(r *protocol.Request) { r.Models = append(r.Models, r.Models[0]) },
		"bad-model":           func(r *protocol.Request) { r.Models[0] = " model" },
		"bad-role":            func(r *protocol.Request) { r.Parts[0].Role = "assistant" },
		"bad-part-digest":     func(r *protocol.Request) { r.Parts[0].ContentSHA256 = "sha256:ABC" },
		"oversize-part":       func(r *protocol.Request) { r.Parts[0].ContentLength = protocol.MaxFrameBytes + 1 },
		"bad-scope":           func(r *protocol.Request) { r.Scope.Repository = "../repo" },
		"changed-limit":       func(r *protocol.Request) { r.Limits.MaxPendingPerPeer = 5 },
		"issued-after-expiry": func(r *protocol.Request) { r.Authority.IssuedAt = r.Authority.ExpiresAt },
		"fractional-time":     func(r *protocol.Request) { r.Authority.IssuedAt = "2026-08-03T00:00:00.1Z" },
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			changed := request
			changed.Models = append([]string(nil), request.Models...)
			changed.Parts = append([]protocol.Part(nil), request.Parts...)
			mutate(&changed)
			if err := protocol.ValidateRequest(changed, clock.Now()); err == nil {
				t.Fatal("relaxed M0 request accepted")
			}
		})
	}
}

func TestRequestExchangeBindsPartLengthDigestAndOrder(t *testing.T) {
	request, _, _, clock := fixture(t)
	part := []byte("hello")
	request.Parts[0].ContentLength = int64(len(part))
	request.Parts[0].ContentSHA256 = protocol.Digest(part)
	header, _ := protocol.CanonicalJSON(request)
	var wire bytes.Buffer
	if err := protocol.WriteFrame(&wire, header); err != nil {
		t.Fatal(err)
	}
	var size [8]byte
	binary.BigEndian.PutUint64(size[:], uint64(len(part)))
	wire.Write(size[:])
	wire.Write(part)
	decoded, parts, err := protocol.ReadRequestExchange(bytes.NewReader(wire.Bytes()), clock.Now())
	if err != nil || decoded.Scope != request.Scope || !bytes.Equal(parts[0], part) {
		t.Fatalf("exchange failed: %v", err)
	}
	mutated := append([]byte(nil), wire.Bytes()...)
	mutated[len(mutated)-1] ^= 1
	if _, _, err := protocol.ReadRequestExchange(bytes.NewReader(mutated), clock.Now()); !errors.Is(err, protocol.ErrPartMismatch) {
		t.Fatalf("part substitution accepted: %v", err)
	}
}

func TestPinnedNativeSourceAndNoHostPINFallback(t *testing.T) {
	path := filepath.Join("fido_libfido2.go")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	source := string(raw)
	for _, marker := range []string{"FIDO_VERSION_MAJOR != 1", "FIDO_VERSION_MINOR != 17", "FIDO_VERSION_PATCH != 0", "dm_ready", "fido_dev_has_uv", "fido_dev_set_timeout(op->dev, 30000)", "fido_assert_authdata_raw_ptr", "dm_operation_cancel", "fido_dev_cancel(op->dev)", "FIDO_OPT_TRUE", "fido_dev_get_assert(op->dev, op->assert, NULL)"} {
		if !strings.Contains(source, marker) {
			t.Fatalf("native invariant missing: %s", marker)
		}
	}
}

func TestNoPrivateOrAssertionSentinelInDurableEvents(t *testing.T) {
	manager, challenge, peer, _ := reserve(t, &fakeFIDO{}, &memoryWAL{})
	canonical, _ := protocol.CanonicalJSON(challenge)
	if _, err := manager.Authorize(context.Background(), challenge.TransactionID, "connection-01", peer, protocol.Digest(canonical)); err != nil {
		t.Fatal(err)
	}
	wal := manager.wal.(*memoryWAL)
	raw, _ := protocol.CanonicalJSON(wal.events)
	for _, forbidden := range []string{"public-test-signature", "public-test-authdata", "root-private-id", "private_key"} {
		if strings.Contains(string(raw), forbidden) {
			t.Fatalf("durable secret-shaped material: %s", forbidden)
		}
	}
}
