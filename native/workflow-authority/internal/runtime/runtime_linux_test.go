//go:build linux

package runtime

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/ipc"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

type fixtureFIDO struct{ ready bool }

func (f fixtureFIDO) Readiness(context.Context) authority.Readiness {
	return f.ReadinessFor(context.Background(), "")
}
func (f fixtureFIDO) ReadinessFor(context.Context, string) authority.Readiness {
	return authority.Readiness{Production: f.ready, InternalUV: f.ready, Adapter: "libfido2", Version: authority.FIDO2Version}
}
func (fixtureFIDO) Assert(context.Context, []byte, authority.Credential) (authority.Assertion, error) {
	return authority.Assertion{}, authority.ErrUnavailable
}
func (fixtureFIDO) Verify(context.Context, []byte, authority.Credential, authority.Assertion) error {
	return authority.ErrUnavailable
}

type blockedListener struct {
	once   sync.Once
	closed chan struct{}
}

func newBlockedListener() *blockedListener           { return &blockedListener{closed: make(chan struct{})} }
func (l *blockedListener) Accept() (net.Conn, error) { <-l.closed; return nil, net.ErrClosed }
func (l *blockedListener) Close() error              { l.once.Do(func() { close(l.closed) }); return nil }
func (*blockedListener) Addr() net.Addr              { return &net.UnixAddr{Name: "fixture", Net: "unix"} }

func validEnrollment(t *testing.T) *enrollment.Credential {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	public, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	id := []byte("root-private-credential-id")
	return &enrollment.Credential{Reference: enrollment.ReferenceForID(id), ID: id, PublicKey: public, Algorithm: enrollment.ES256, Generation: 1, RPID: enrollment.RPID, EnrolledAt: time.Now().Add(-time.Hour).UTC(), Status: "active", InternalUV: true, AAGUID: make([]byte, 16), Format: "packed", DeviceSelector: "sha256:" + strings.Repeat("a", 64)}
}

func fixtureDependencies(t *testing.T) (dependencies, *int) {
	t.Helper()
	root := t.TempDir()
	state := filepath.Join(root, "state")
	if err := os.Mkdir(state, 0o700); err != nil {
		t.Fatal(err)
	}
	secretPath := filepath.Join(root, "openrouter")
	if err := os.WriteFile(secretPath, []byte("fixture-provider-secret"), 0o600); err != nil {
		t.Fatal(err)
	}
	credential := validEnrollment(t)
	activations := 0
	d := dependencies{
		euid: func() int { return 0 },
		loadEnrollment: func(context.Context) (*enrollment.Credential, error) {
			copy := *credential
			copy.ID = append([]byte(nil), credential.ID...)
			return &copy, nil
		},
		fido:         fixtureFIDO{ready: true},
		providerCred: provider.FileCredentialReader{Path: secretPath, FixtureMode: true, Owner: uint32(os.Geteuid())},
		loadPolicy: func(context.Context) ([]byte, string, error) {
			value := []byte(`{"schemaVersion":2,"disclosureControls":{"refuseClasses":["high-confidence credentials","private keys","authenticated connection strings / DSNs","access or session tokens","explicitly classified private or regulated values"],"onMatch":"decline-disclosure","exitCode":3}}`)
			return value, protocol.Digest(value), nil
		},
		openWAL:     func() (authority.WAL, error) { return authority.OpenDirWAL(state, uint32(os.Geteuid())) },
		openState:   func() (*ipc.DirStateStore, error) { return ipc.OpenDirStateStore(state, uint32(os.Geteuid())) },
		bootID:      func() (string, error) { return "01234567-89ab-cdef-0123-456789abcdef", nil },
		allowedUIDs: func() (map[uint32]struct{}, error) { return map[uint32]struct{}{uint32(os.Geteuid()): {}}, nil },
		activate:    func() (net.Listener, error) { activations++; return newBlockedListener(), nil },
		random:      strings.NewReader(strings.Repeat("r", 128)), now: func() time.Time { return time.Now().UTC() },
		daemonDigest: func() (string, error) { return protocol.Digest([]byte("daemon")), nil },
	}
	return d, &activations
}

func TestBuildActivatesOnlyAfterEveryPrivateDependency(t *testing.T) {
	d, activations := fixtureDependencies(t)
	c, err := build(context.Background(), d)
	if err != nil || *activations != 1 {
		t.Fatalf("build=%v activations=%d", err, *activations)
	}
	if c.server.QueueDepth != 1 {
		t.Fatal("first milestone is not serialized")
	}
	policy := c.policy
	_ = c.server.Manager.Shutdown(context.Background())
	_ = c.server.Allocator.Close()
	c.destroy()
	for _, value := range policy {
		if value != 0 {
			t.Fatal("policy not erased")
		}
	}
}

func TestBuildFailsClosedBeforeActivationForMissingDependencies(t *testing.T) {
	tests := map[string]func(*dependencies){
		"not-root":   func(d *dependencies) { d.euid = func() int { return 1000 } },
		"stub-build": func(d *dependencies) { d.daemonDigest = func() (string, error) { return "", errors.New("stub") } },
		"enrollment": func(d *dependencies) {
			d.loadEnrollment = func(context.Context) (*enrollment.Credential, error) { return nil, errors.New("corrupt history") }
		},
		"selector-readiness": func(d *dependencies) { d.fido = fixtureFIDO{} },
		"provider-credential": func(d *dependencies) {
			d.providerCred = provider.FileCredentialReader{Path: "/absent", FixtureMode: true}
		},
		"policy": func(d *dependencies) {
			d.loadPolicy = func(context.Context) ([]byte, string, error) { return []byte("{}"), "sha256:bad", nil }
		},
		"boot":  func(d *dependencies) { d.bootID = func() (string, error) { return "", errors.New("bad boot") } },
		"group": func(d *dependencies) { d.allowedUIDs = func() (map[uint32]struct{}, error) { return nil, nil } },
		"wal":   func(d *dependencies) { d.openWAL = func() (authority.WAL, error) { return nil, errors.New("bad wal") } },
		"state": func(d *dependencies) {
			d.openState = func() (*ipc.DirStateStore, error) { return nil, errors.New("bad state") }
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			d, activations := fixtureDependencies(t)
			mutate(&d)
			if c, err := build(context.Background(), d); err == nil || c != nil || *activations != 0 {
				t.Fatalf("composition escaped: c=%v err=%v activations=%d", c, err, *activations)
			}
		})
	}
}

func TestCancellationClosesListenerAndDrainsServer(t *testing.T) {
	d, _ := fixtureDependencies(t)
	c, err := build(context.Background(), d)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- c.server.Serve(ctx, c.listener) }()
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("shutdown did not propagate")
	}
	c.destroy()
}

func TestExecutableIdentityRejectsSymlinkModeLinkAndDifferentProcessImage(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "libexec")
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "workflow-authorityd")
	if err := os.WriteFile(path, []byte("binary"), 0o755); err != nil {
		t.Fatal(err)
	}
	owner := uint32(os.Geteuid())
	if digest, err := executableDigestAt(path, path, owner, root); err != nil || digest != protocol.Digest([]byte("binary")) {
		t.Fatalf("digest=%s err=%v", digest, err)
	}
	other := filepath.Join(dir, "other")
	if err := os.WriteFile(other, []byte("binary"), 0o755); err != nil {
		t.Fatal(err)
	}
	if _, err := executableDigestAt(path, other, owner, root); err == nil {
		t.Fatal("different inode accepted")
	}
	if err := os.Chmod(path, 0o775); err != nil {
		t.Fatal(err)
	}
	if _, err := executableDigestAt(path, path, owner, root); err == nil {
		t.Fatal("writable executable accepted")
	}
	if err := os.Chmod(path, 0o755); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(dir, "linked")
	if err := os.Link(path, link); err != nil {
		t.Fatal(err)
	}
	if _, err := executableDigestAt(path, path, owner, root); err == nil {
		t.Fatal("multiply-linked executable accepted")
	}
	if err := os.Remove(link); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(path, path+".real"); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(path+".real", path); err != nil {
		t.Fatal(err)
	}
	if _, err := executableDigestAt(path, path, owner, root); err == nil {
		t.Fatal("symlink executable accepted")
	}
}

func TestBootAndGroupIdentityParsing(t *testing.T) {
	if got, err := parseBootID([]byte("01234567-89ab-cdef-0123-456789abcdef\n")); err != nil || got == "" {
		t.Fatal(err)
	}
	for _, bad := range []string{"", "01234567-89AB-cdef-0123-456789abcdef", "not-a-uuid"} {
		if _, err := parseBootID([]byte(bad)); err == nil {
			t.Fatalf("accepted %q", bad)
		}
	}
	group := []byte("root:x:0:\nworkflow-authority:x:991:alice,bob\n")
	passwd := []byte("root:x:0:0:root:/root:/bin/sh\nalice:x:1000:1000::/home/alice:/bin/sh\nbob:x:1001:991::/home/bob:/bin/sh\n")
	uids, err := parseAllowedUIDs(group, passwd)
	if err != nil || len(uids) != 2 {
		t.Fatalf("uids=%v err=%v", uids, err)
	}
	if _, err := parseAllowedUIDs([]byte("root:x:0:\n"), passwd); err == nil {
		t.Fatal("missing group accepted")
	}
	if _, err := parseAllowedUIDs([]byte("workflow-authority:x:991:ghost\n"), passwd); err == nil {
		t.Fatal("unknown member accepted")
	}
}
