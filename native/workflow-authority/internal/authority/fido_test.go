package authority

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"encoding/binary"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/protocol"
)

func TestUnavailableAdapterNeverReportsProductionReady(t *testing.T) {
	adapter := NewFIDOAdapter()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	readiness := adapter.Readiness(ctx)
	if readiness.Production || readiness.InternalUV {
		t.Fatalf("unavailable adapter reported ready: %+v", readiness)
	}
	switch readiness.Adapter {
	case "stub":
		if readiness.Version != "unavailable" {
			t.Fatalf("unexpected stub version: %+v", readiness)
		}
	case "libfido2":
		if readiness.Version != FIDO2Version {
			t.Fatalf("unexpected libfido2 compatibility label: %+v", readiness)
		}
	default:
		t.Fatalf("unexpected FIDO adapter: %+v", readiness)
	}
	if _, err := adapter.Assert(ctx, []byte("challenge"), Credential{}); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("unavailable assertion: %v", err)
	}
}

func TestUnavailableEnrollerFailsClosed(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	credential, err := NewFIDOEnroller().Enroll(ctx, enrollment.Request{Generation: 1})
	if !errors.Is(err, enrollment.ErrUnavailable) || len(credential.ID) != 0 {
		t.Fatalf("unavailable enrollment did not fail closed: %#v %v", credential, err)
	}
}

func TestStubSelectorReadinessAndEnrollmentMapper(t *testing.T) {
	adapter, ok := NewFIDOAdapter().(SelectorAwareFIDO)
	if !ok {
		t.Fatal("adapter lost selector-aware readiness seam")
	}
	if readiness := adapter.ReadinessFor(context.Background(), "sha256:"+strings.Repeat("a", 64)); readiness.Production {
		t.Fatalf("stub selector readiness became production: %+v", readiness)
	}
	private, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	public, err := x509.MarshalPKIXPublicKey(&private.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	id := []byte("root-private-credential-id")
	source := enrollment.Credential{Reference: enrollment.ReferenceForID(id), ID: id, PublicKey: public, Algorithm: enrollment.ES256, Generation: 7, RPID: enrollment.RPID, EnrolledAt: time.Unix(1_800_000_000, 0).UTC(), Status: "active", InternalUV: true, AAGUID: bytes.Repeat([]byte{7}, 16), Format: "packed", DeviceSelector: "sha256:" + strings.Repeat("b", 64)}
	mapped, err := CredentialFromEnrollment(source)
	if err != nil || mapped.DeviceSelector != source.DeviceSelector || !bytes.Equal(mapped.ID, source.ID) {
		t.Fatalf("map: %#v %v", mapped, err)
	}
	source.Destroy()
	if bytes.Equal(mapped.ID, source.ID) || len(mapped.ID) == 0 {
		t.Fatal("mapper did not take independent root-private ownership")
	}
	encoded, err := json.Marshal(mapped)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(encoded, mapped.ID) || bytes.Contains(encoded, []byte(mapped.DeviceSelector)) {
		t.Fatal("runtime metadata escaped serialization")
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
	for _, marker := range []string{"WORKFLOW_AUTHORITY_LIBFIDO2_MAJOR != 1", "WORKFLOW_AUTHORITY_LIBFIDO2_MINOR < 16", "workflow-authority requires libfido2 >=1.16.0 and <2.0.0", "dm_ready", "fido_dev_has_uv", "fido_dev_set_timeout(op->dev, 30000)", "fido_assert_authdata_raw_ptr", "dm_operation_cancel", "fido_dev_cancel(op->dev)", "FIDO_OPT_TRUE", "fido_dev_get_assert(op->dev, op->assert, NULL)"} {
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
