package client

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

type testFIDO struct {
	err   error
	ready bool
	hook  func()
	mu    sync.Mutex
	calls int
}

func (f *testFIDO) Readiness(context.Context) authority.Readiness {
	return authority.Readiness{Production: f.ready, Adapter: "libfido2", Version: authority.FIDO2Version, InternalUV: f.ready}
}
func (f *testFIDO) Assert(context.Context, []byte, authority.Credential) (authority.Assertion, error) {
	return authority.Assertion{}, authority.ErrUnavailable
}
func (f *testFIDO) Verify(_ context.Context, challenge []byte, credential authority.Credential, assertion authority.Assertion) error {
	f.mu.Lock()
	f.calls++
	f.mu.Unlock()
	if f.hook != nil {
		f.hook()
	}
	digest := sha256.Sum256(challenge)
	if f.err != nil || assertion.ChallengeDigest != digest || credential.Reference != "credential-generation-7" || assertion.Generation != 7 || assertion.CredentialReference != credential.Reference || !assertion.UserPresence || !assertion.UserVerification {
		return authority.ErrDenied
	}
	return nil
}

type testTerminal struct{ writes bytes.Buffer }

func (*testTerminal) Identity() (authority.TerminalIdentity, error) {
	return authority.TerminalIdentity{Device: 1, Inode: 2}, nil
}
func (t *testTerminal) Write(p []byte) (int, error) { return t.writes.Write(p) }
func (*testTerminal) ReadLine() (string, error)     { return "AUTHORIZE\n", nil }
func (*testTerminal) Close() error                  { return nil }

type serverMutation func(*protocol.AuthorityHello, *protocol.Challenge, *provider.AuthorizationProof, []byte, *protocol.TerminalResult)

type fixture struct {
	runner   *Runner
	listener *net.UnixListener
	fido     *testFIDO
	now      time.Time
	done     chan error
}

func newFixture(t *testing.T, mutate serverMutation) *fixture {
	return newFixtureCase(t, mutate, "", nil)
}

func newFixtureCase(t *testing.T, mutate serverMutation, safeStage string, safe *protocol.SafeError) *fixture {
	t.Helper()
	root, err := os.MkdirTemp("/tmp", "wa-client-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(root) })
	socketDir := filepath.Join(root, "run")
	trustDir := filepath.Join(root, "trust")
	if err := os.Mkdir(socketDir, 0o750); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(trustDir, 0o755); err != nil {
		t.Fatal(err)
	}
	socket := filepath.Join(socketDir, "authority.sock")
	listener, err := net.ListenUnix("unix", &net.UnixAddr{Name: socket, Net: "unix"})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(socket, 0o660); err != nil {
		t.Fatal(err)
	}
	private, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	publicDER, _ := x509.MarshalPKIXPublicKey(&private.PublicKey)
	now := time.Date(2026, 8, 4, 0, 0, 30, 0, time.UTC)
	generation := uint64(7)
	record := enrollment.PublicCredential{Generation: generation, Reference: "credential-generation-7", PublicKey: base64.RawURLEncoding.EncodeToString(publicDER), Algorithm: enrollment.ES256, RPID: enrollment.RPID, EnrolledAt: now.Add(-time.Hour), InternalUV: true, AAGUID: base64.RawURLEncoding.EncodeToString(make([]byte, 16)), AttestationFormat: "packed"}
	trust := enrollment.PublicTrust{Protocol: enrollment.Protocol, ActiveGeneration: &generation, Credentials: []enrollment.PublicCredential{record}, Events: []enrollment.LifecycleEvent{{Sequence: 1, Generation: generation, Action: "activated", At: record.EnrolledAt}}}
	recordRaw, _ := protocol.CanonicalJSON(trust)
	trustPath := filepath.Join(trustDir, "authority-public.json")
	if err := os.WriteFile(trustPath, recordRaw, 0o644); err != nil {
		t.Fatal(err)
	}
	fido := &testFIDO{ready: true}
	runner := &Runner{socketPath: socket, trustPath: trustPath, socketAnchor: root, trustAnchor: root, expectedOwner: uint32(os.Geteuid()), now: func() time.Time { return now }, fido: fido}
	runner.dial = func(ctx context.Context, path string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", path)
	}
	runner.confirm = func(_ context.Context, challenge protocol.Challenge) error {
		terminal := &testTerminal{}
		return authority.ConfirmExactScope(terminal, challenge)
	}
	fx := &fixture{runner: runner, listener: listener, fido: fido, now: now, done: make(chan error, 1)}
	go func() { fx.done <- serveOnce(listener, now, private, mutate, safeStage, safe) }()
	t.Cleanup(func() { _ = listener.Close() })
	return fx
}

func (f *fixture) wait(t *testing.T) {
	t.Helper()
	select {
	case err := <-f.done:
		if err != nil && !errors.Is(err, net.ErrClosed) && err.Error() != "durable_state_unavailable" {
			t.Fatalf("server: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not finish")
	}
}

func serveOnce(listener *net.UnixListener, now time.Time, signer *ecdsa.PrivateKey, mutate serverMutation, safeStage string, safe *protocol.SafeError) error {
	conn, err := listener.AcceptUnix()
	if err != nil {
		return err
	}
	defer conn.Close()
	hello := protocol.AuthorityHello{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.AuthorityHelloType, DaemonBuildSHA256: protocol.Digest([]byte("daemon")), ScannerBuildSHA256: protocol.Digest([]byte("scanner")), PolicySHA256: protocol.Digest([]byte("policy")), BootID: "boot-1", SessionID: "session-1", Sequence: 1, IssuedAt: now.Add(-30 * time.Second).Format(time.RFC3339), ExpiresAt: now.Add(90 * time.Second).Format(time.RFC3339), PriorChainDigest: protocol.Digest([]byte("prior")), ConnectionNonceSHA256: protocol.Digest([]byte("connection")), Limits: protocol.FrozenAllocationLimits()}
	if mutate != nil {
		mutate(&hello, nil, nil, nil, nil)
	}
	helloRaw, _ := protocol.CanonicalJSON(hello)
	if err := protocol.WriteFrame(conn, helloRaw); err != nil {
		return err
	}
	proposalRaw, err := protocol.ReadFrame(conn)
	if err != nil {
		return nil
	}
	var proposal protocol.DispatchProposal
	if protocol.DecodeClosed(proposalRaw, &proposal) != nil {
		return errors.New("proposal decode")
	}
	parts := make([][]byte, len(proposal.Parts))
	for index := range parts {
		var header [8]byte
		if _, err := io.ReadFull(conn, header[:]); err != nil {
			return err
		}
		parts[index] = make([]byte, binary.BigEndian.Uint64(header[:]))
		if _, err := io.ReadFull(conn, parts[index]); err != nil {
			return err
		}
	}
	request, err := protocol.BindAllocationRequest(hello, proposal, parts, now)
	if err != nil {
		return err
	}
	body, err := provider.BuildBody(request, parts)
	if err != nil {
		return err
	}
	if safeStage == "challenge" && safe != nil {
		raw, _ := protocol.CanonicalJSON(*safe)
		return protocol.WriteFrame(conn, raw)
	}
	public := elliptic.Marshal(elliptic.P256(), signer.PublicKey.X, signer.PublicKey.Y)
	challenge := protocol.Challenge{SchemaVersion: 1, Protocol: protocol.Name, Mapping: request.Mapping, OperationFamily: request.OperationFamily, SubstrateAuthority: request.SubstrateAuthority, TransactionID: "transaction-1", ConnectionNonceSHA256: request.Authority.ConnectionNonceSHA256, PeerUID: uint32(os.Geteuid()), PeerPID: int32(os.Getpid()), RequestBodySHA256: protocol.Digest(body), Destination: request.Destination, Method: request.Method, Path: request.Path, Models: request.Models, Scope: request.Scope, DaemonBuildSHA256: request.Authority.DaemonBuildSHA256, ScannerBuildSHA256: request.Authority.ScannerBuildSHA256, PolicySHA256: request.Authority.PolicySHA256, Nonce: request.Authority.Nonce, Sequence: request.Authority.Sequence, BootID: request.Authority.BootID, SessionID: request.Authority.SessionID, IssuedAt: request.Authority.IssuedAt, ExpiresAt: request.Authority.ExpiresAt, Limits: request.Limits, ResultSigner: protocol.ResultSigner{Kind: "ephemeral-es256", PublicKeySEC1: base64.RawURLEncoding.EncodeToString(public)}, PriorChainDigest: request.Authority.PriorChainDigest, AllocationHelloSHA256: request.Authority.AllocationHelloSHA256, DispatchProposalSHA256: request.Authority.DispatchProposalSHA256}
	if mutate != nil {
		mutate(nil, &challenge, nil, nil, nil)
	}
	challengeRaw, _ := protocol.CanonicalJSON(challenge)
	if err := protocol.WriteFrame(conn, challengeRaw); err != nil {
		return err
	}
	if _, err := protocol.ReadFrame(conn); err != nil {
		return nil
	}
	if safeStage == "proof" && safe != nil {
		raw, _ := protocol.CanonicalJSON(*safe)
		return protocol.WriteFrame(conn, raw)
	}
	authData := make([]byte, 37)
	binary.BigEndian.PutUint32(authData[33:], 5)
	proof := provider.AuthorizationProof{SchemaVersion: 1, Protocol: protocol.Name, Type: "authorization_proof", ChallengeSHA256: protocol.Digest(challengeRaw), AuthorityAssertion: provider.FIDOAssertion{Kind: "fido2-es256", CredentialID: base64.RawURLEncoding.EncodeToString([]byte("credential-generation-7")), AuthenticatorData: base64.RawURLEncoding.EncodeToString(authData), ClientDataJSON: base64.RawURLEncoding.EncodeToString([]byte(`{"challenge":"test"}`)), SignatureDER: base64.RawURLEncoding.EncodeToString([]byte("assertion-signature")), UserPresence: true, UserVerification: true}}
	response := []byte("verified-response-secret")
	selected := request.Models[0]
	proofRaw, _ := protocol.CanonicalJSON(proof)
	result := protocol.TerminalResult{SchemaVersion: 1, Protocol: protocol.Name, OperationFamily: "external_provider_dispatch", SubstrateAuthority: "not_asserted", Outcome: "verified", ExitCode: 0, RequestBodySHA256: challenge.RequestBodySHA256, ResponseSHA256: protocol.Digest(response), ResponseLength: int64(len(response)), PartCount: len(parts), Models: request.Models, SelectedModel: &selected, Provider: "openrouter", GenerationID: "generation-1", ServingProvider: "provider-1", UsageSHA256: protocol.Digest([]byte("usage")), Fallback: false, Scope: request.Scope, Sequence: request.Authority.Sequence, IssuedAt: request.Authority.IssuedAt, CompletedAt: now.Format(time.RFC3339), ChallengeSHA256: protocol.Digest(challengeRaw), AuthorityAssertionSHA256: protocol.Digest(mustCanonical(proof.AuthorityAssertion)), ResultSignerSHA256: protocol.Digest(mustCanonical(challenge.ResultSigner)), PriorChainDigest: request.Authority.PriorChainDigest, Cleanup: protocol.TerminalCleanup{Reservation: "consumed", Connection: "closed", ContentBuffer: "discarded"}, Signature: protocol.TerminalSignature{Kind: "es256"}}
	if mutate != nil {
		mutate(nil, nil, &proof, response, &result)
	}
	proofRaw, _ = protocol.CanonicalJSON(proof)
	if err := protocol.WriteFrame(conn, proofRaw); err != nil {
		return err
	}
	var responseHeader [8]byte
	binary.BigEndian.PutUint64(responseHeader[:], uint64(len(response)))
	if writeAll(conn, responseHeader[:]) != nil || writeAll(conn, response) != nil {
		return err
	}
	input, err := protocol.TerminalSignatureInput(result)
	if err != nil {
		return err
	}
	digest := sha256.Sum256(input)
	signature, _ := ecdsa.SignASN1(rand.Reader, signer, digest[:])
	result.Signature.SignatureDER = base64.RawURLEncoding.EncodeToString(signature)
	terminalRaw, _ := protocol.CanonicalJSON(result)
	return protocol.WriteFrame(conn, terminalRaw)
}

func mustCanonical(value any) []byte { raw, _ := protocol.CanonicalJSON(value); return raw }

func validOptions() DispatchOptions {
	return DispatchOptions{Repository: "owner/repository", RunID: "run-1", Lane: "pipeline-assessment-artifact-delegation-v1", Candidate: "candidate-1", Workload: "pipeline-assessment", Nonce: "nonce-1", Model: "openai/gpt-5", FallbackModel: "anthropic/claude-sonnet-4"}
}

func TestDispatchWithholdsUntilBothProofsVerify(t *testing.T) {
	fx := newFixture(t, nil)
	result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewBufferString("system-secret"), bytes.NewBufferString("user-secret"))
	if err != nil {
		t.Fatal(err)
	}
	if string(result.Response) != "verified-response-secret" || !bytes.Contains(result.Receipt, []byte(`"outcome":"verified"`)) || bytes.Contains(result.Receipt, result.Response) || fx.fido.calls != 1 {
		t.Fatalf("invalid verified result: response=%q receipt=%s calls=%d", result.Response, result.Receipt, fx.fido.calls)
	}
	fx.wait(t)
}

func TestEveryBindingMutationFailsWithoutResponse(t *testing.T) {
	mutations := map[string]serverMutation{
		"stale-hello": func(h *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if h != nil {
				h.IssuedAt = "2026-08-03T00:00:00Z"
				h.ExpiresAt = "2026-08-03T00:02:00Z"
			}
		},
		"scope": func(_ *protocol.AuthorityHello, c *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if c != nil {
				c.Scope.Candidate = "other"
			}
		},
		"nonce": func(_ *protocol.AuthorityHello, c *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if c != nil {
				c.Nonce = "other"
			}
		},
		"body": func(_ *protocol.AuthorityHello, c *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if c != nil {
				c.RequestBodySHA256 = protocol.Digest([]byte("wrong"))
			}
		},
		"proposal-digest": func(_ *protocol.AuthorityHello, c *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if c != nil {
				c.DispatchProposalSHA256 = protocol.Digest([]byte("wrong"))
			}
		},
		"proof-challenge": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, p *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if p != nil {
				p.ChallengeSHA256 = protocol.Digest([]byte("wrong"))
			}
		},
		"proof-reference": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, p *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if p != nil {
				p.AuthorityAssertion.CredentialID = base64.RawURLEncoding.EncodeToString([]byte("other"))
			}
		},
		"proof-missing-up": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, p *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if p != nil {
				p.AuthorityAssertion.UserPresence = false
			}
		},
		"proof-missing-uv": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, p *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if p != nil {
				p.AuthorityAssertion.UserVerification = false
			}
		},
		"proof-authdata": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, p *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if p != nil {
				p.AuthorityAssertion.AuthenticatorData = base64.RawURLEncoding.EncodeToString([]byte("short"))
			}
		},
		"response-digest": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, r *protocol.TerminalResult) {
			if r != nil {
				r.ResponseSHA256 = protocol.Digest([]byte("wrong"))
			}
		},
		"terminal-scope": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, r *protocol.TerminalResult) {
			if r != nil {
				r.Scope.Repository = "other/repo"
			}
		},
		"terminal-challenge": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, r *protocol.TerminalResult) {
			if r != nil {
				r.ChallengeSHA256 = protocol.Digest([]byte("wrong"))
			}
		},
		"terminal-signature": func(_ *protocol.AuthorityHello, c *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
			if c != nil {
				x, y := elliptic.P256().ScalarBaseMult([]byte{2})
				c.ResultSigner.PublicKeySEC1 = base64.RawURLEncoding.EncodeToString(elliptic.Marshal(elliptic.P256(), x, y))
			}
		},
		"terminal-before-issued": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, result *protocol.TerminalResult) {
			if result != nil {
				result.CompletedAt = "2026-08-03T23:59:00Z"
			}
		},
		"terminal-in-future": func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, result *protocol.TerminalResult) {
			if result != nil {
				result.CompletedAt = "2026-08-04T00:00:31Z"
			}
		},
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			fx := newFixture(t, mutate)
			result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewBufferString("system"), bytes.NewBufferString("user"))
			if err == nil || len(result.Response) != 0 || len(result.Receipt) != 0 {
				t.Fatalf("mutation released result: %+v err=%v", result, err)
			}
			fx.wait(t)
		})
	}
}

func TestStatusRequiresTrustAndFreshRootPeerHelloWithoutOpeningFIDO(t *testing.T) {
	fx := newFixture(t, nil)
	fx.runner.fido = nil
	raw, err := fx.runner.Status(context.Background())
	if err != nil || !bytes.Contains(raw, []byte(`"production_ready":true`)) || !bytes.Contains(raw, []byte(`"m1_acceptance":true`)) {
		t.Fatalf("status=%s err=%v", raw, err)
	}
	fx.wait(t)

}

func TestPublicTrustRejectsStaleMultipleAndMalformedHistories(t *testing.T) {
	tests := map[string]func(*enrollment.PublicTrust){
		"stale-active-generation": func(trust *enrollment.PublicTrust) {
			stale := uint64(6)
			trust.ActiveGeneration = &stale
		},
		"multiple-active-events": func(trust *enrollment.PublicTrust) {
			trust.Events = append(trust.Events, enrollment.LifecycleEvent{Sequence: 2, Generation: 7, Action: "activated", At: trust.Credentials[0].EnrolledAt})
		},
		"future-enrollment": func(trust *enrollment.PublicTrust) {
			trust.Credentials[0].EnrolledAt = time.Date(2027, 1, 1, 0, 0, 0, 0, time.UTC)
			trust.Events[0].At = trust.Credentials[0].EnrolledAt
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			fx := newFixture(t, nil)
			raw, err := os.ReadFile(fx.runner.trustPath)
			if err != nil {
				t.Fatal(err)
			}
			var trust enrollment.PublicTrust
			if protocol.DecodeClosed(raw, &trust) != nil {
				t.Fatal("fixture trust invalid")
			}
			mutate(&trust)
			raw, _ = protocol.CanonicalJSON(trust)
			if err := os.WriteFile(fx.runner.trustPath, raw, 0o644); err != nil {
				t.Fatal(err)
			}
			if _, err := fx.runner.loadTrust(); err == nil {
				t.Fatal("invalid history accepted")
			}
			_ = fx.listener.Close()
		})
	}
	t.Run("unknown-field", func(t *testing.T) {
		fx := newFixture(t, nil)
		raw, err := os.ReadFile(fx.runner.trustPath)
		if err != nil {
			t.Fatal(err)
		}
		raw[len(raw)-1] = ','
		raw = append(raw, []byte(`"unexpected":true}`)...)
		if err := os.WriteFile(fx.runner.trustPath, raw, 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := fx.runner.loadTrust(); err == nil {
			t.Fatal("open JSON accepted")
		}
		_ = fx.listener.Close()
	})
}

func TestFixedPathTrustRejectsSymlinksModesAndAlternateEnvironment(t *testing.T) {
	fx := newFixture(t, nil)
	if err := os.Chmod(fx.runner.trustPath, 0o666); err != nil {
		t.Fatal(err)
	}
	if _, err := fx.runner.Status(context.Background()); err == nil {
		t.Fatal("writable trust accepted")
	}
	_ = fx.listener.Close()

	fx = newFixture(t, nil)
	target := fx.runner.trustPath + ".real"
	if err := os.Rename(fx.runner.trustPath, target); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, fx.runner.trustPath); err != nil {
		t.Fatal(err)
	}
	if _, err := fx.runner.Status(context.Background()); err == nil {
		t.Fatal("symlink trust accepted")
	}
	_ = fx.listener.Close()

	t.Setenv("WORKFLOW_AUTHORITY_SOCKET", "/tmp/attacker.sock")
	t.Setenv("WORKFLOW_AUTHORITY_TRUST", "/tmp/attacker.json")
	production := NewProduction()
	if production.socketPath != "/run/design-machines/workflow-authority/authority.sock" || production.trustPath != PublicTrustPath {
		t.Fatal("environment changed production paths")
	}
}

func TestInvalidOptionsAndVerifierFailureDoNotRelease(t *testing.T) {
	fx := newFixture(t, nil)
	bad := validOptions()
	bad.Nonce = ""
	if result, err := fx.runner.Dispatch(context.Background(), bad, bytes.NewReader(nil), bytes.NewReader(nil)); !errors.Is(err, ErrUsage) || len(result.Response) != 0 {
		t.Fatalf("invalid options: %+v %v", result, err)
	}
	_ = fx.listener.Close()

	fx = newFixture(t, nil)
	fx.fido.err = errors.New("forged")
	if result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil)); err == nil || len(result.Response) != 0 {
		t.Fatal("failed FIDO proof released response")
	}
	fx.wait(t)
}

func TestCancellationAndConcurrentIndependentRequestsFailOrVerifyAtomically(t *testing.T) {
	fx := newFixture(t, nil)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if result, err := fx.runner.Dispatch(ctx, validOptions(), bytes.NewReader(nil), bytes.NewReader(nil)); err == nil || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("cancelled dispatch released data: %+v err=%v", result, err)
	}
	_ = fx.listener.Close()

	fixtures := []*fixture{newFixture(t, nil), newFixture(t, nil), newFixture(t, nil)}
	errorsByRequest := make(chan error, len(fixtures))
	for _, current := range fixtures {
		go func(current *fixture) {
			result, err := current.runner.Dispatch(context.Background(), validOptions(), bytes.NewBufferString("system"), bytes.NewBufferString("user"))
			if err == nil && string(result.Response) != "verified-response-secret" {
				err = errors.New("partial concurrent response")
			}
			errorsByRequest <- err
		}(current)
	}
	for range fixtures {
		if err := <-errorsByRequest; err != nil {
			t.Fatal(err)
		}
	}
	for _, current := range fixtures {
		current.wait(t)
	}
}

func TestSignedProviderFailureAndUnknownReturnReceiptWithoutResponse(t *testing.T) {
	for outcome, exit := range map[string]int{"provider_failure": 73, "unknown": 74} {
		t.Run(outcome, func(t *testing.T) {
			fx := newFixture(t, func(_ *protocol.AuthorityHello, _ *protocol.Challenge, _ *provider.AuthorizationProof, _ []byte, result *protocol.TerminalResult) {
				if result != nil {
					result.Outcome, result.ExitCode = outcome, exit
				}
			})
			result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil))
			if err != nil || result.ExitCode != exit || len(result.Response) != 0 || !bytes.Contains(result.Receipt, []byte(`"outcome":"`+outcome+`"`)) {
				t.Fatalf("signed outcome rejected or released response: %+v err=%v", result, err)
			}
			fx.wait(t)
		})
	}
}

func TestSafeErrorOnlyAcceptedAtPreNetworkChallengeStage(t *testing.T) {
	for code, expected := range map[string]error{"authority_unavailable": ErrUnavailable, "authorization_declined": ErrDeclined, "disclosure_declined": ErrDisclosure} {
		safe := &protocol.SafeError{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.SafeErrorType, Code: code, Consumed: true}
		switch code {
		case "authority_unavailable":
			safe.ExitCode = 70
		case "authorization_declined":
			safe.ExitCode = 71
		case "disclosure_declined":
			safe.ExitCode = 72
		}
		fx := newFixtureCase(t, nil, "challenge", safe)
		result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil))
		if !errors.Is(err, expected) || len(result.Response) != 0 || len(result.Receipt) != 0 {
			t.Fatalf("safe error %s: %+v err=%v", code, result, err)
		}
		fx.wait(t)
	}
	safe := &protocol.SafeError{SchemaVersion: 1, Protocol: protocol.Name, Type: protocol.SafeErrorType, Code: "authority_unavailable", ExitCode: 70, Consumed: true}
	fx := newFixtureCase(t, nil, "proof", safe)
	if result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil)); !errors.Is(err, ErrUncertain) || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("post-consent safe error was retryable: %+v err=%v", result, err)
	}
	fx.wait(t)
}

func TestFreshnessRecheckedAfterConsentAndBeforeTerminal(t *testing.T) {
	fx := newFixture(t, nil)
	current := fx.now
	fx.runner.now = func() time.Time { return current }
	fx.runner.confirm = func(context.Context, protocol.Challenge) error {
		current = fx.now.Add(2 * time.Minute)
		return nil
	}
	if result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil)); !errors.Is(err, ErrUncertain) || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("expired post-consent request accepted: %+v err=%v", result, err)
	}
	fx.wait(t)

	fx = newFixture(t, nil)
	current = fx.now
	fx.runner.now = func() time.Time { return current }
	fx.fido.hook = func() { current = fx.now.Add(2 * time.Minute) }
	if result, err := fx.runner.Dispatch(context.Background(), validOptions(), bytes.NewReader(nil), bytes.NewReader(nil)); !errors.Is(err, ErrUncertain) || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("expired pre-terminal request accepted: %+v err=%v", result, err)
	}
	fx.wait(t)
}

func TestInFlightSocketAndConsentCancellationReleaseNothing(t *testing.T) {
	reachedProof := make(chan struct{})
	releaseServer := make(chan struct{})
	fx := newFixture(t, func(_ *protocol.AuthorityHello, _ *protocol.Challenge, proof *provider.AuthorizationProof, _ []byte, _ *protocol.TerminalResult) {
		if proof != nil {
			close(reachedProof)
			<-releaseServer
		}
	})
	ctx, cancel := context.WithCancel(context.Background())
	results := make(chan Result, 1)
	errorsOut := make(chan error, 1)
	go func() {
		result, err := fx.runner.Dispatch(ctx, validOptions(), bytes.NewReader(nil), bytes.NewReader(nil))
		results <- result
		errorsOut <- err
	}()
	<-reachedProof
	cancel()
	result, err := <-results, <-errorsOut
	if !errors.Is(err, ErrUncertain) || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("socket cancellation released data: %+v err=%v", result, err)
	}
	close(releaseServer)
	fx.wait(t)

	fx = newFixture(t, nil)
	enteredConsent := make(chan struct{})
	fx.runner.confirm = func(ctx context.Context, _ protocol.Challenge) error {
		close(enteredConsent)
		<-ctx.Done()
		return ctx.Err()
	}
	ctx, cancel = context.WithCancel(context.Background())
	go func() {
		result, err := fx.runner.Dispatch(ctx, validOptions(), bytes.NewReader(nil), bytes.NewReader(nil))
		results <- result
		errorsOut <- err
	}()
	<-enteredConsent
	cancel()
	result, err = <-results, <-errorsOut
	if !errors.Is(err, ErrUncertain) || len(result.Response) != 0 || len(result.Receipt) != 0 {
		t.Fatalf("consent cancellation released data: %+v err=%v", result, err)
	}
	fx.wait(t)
}
