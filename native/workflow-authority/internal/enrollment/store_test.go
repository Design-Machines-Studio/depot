package enrollment

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"
)

type fakeEnroller struct {
	mu    sync.Mutex
	calls []Request
	err   error
}

func (f *fakeEnroller) Enroll(ctx context.Context, request Request) (Credential, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, Request{Generation: request.Generation, ExcludeCredentialID: append([]byte(nil), request.ExcludeCredentialID...)})
	if ctx.Err() != nil || f.err != nil || request.Generation == 0 {
		return Credential{}, ErrUnavailable
	}
	id := []byte(fmt.Sprintf("credential-secret-generation-%d", request.Generation))
	return testCredentialWithID(request.Generation, id), nil
}

func testCredential(t *testing.T, generation uint64) Credential {
	t.Helper()
	return testCredentialWithID(generation, []byte(fmt.Sprintf("credential-secret-generation-%d", generation)))
}

func testCredentialWithID(generation uint64, id []byte) Credential {
	private, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	public, _ := x509.MarshalPKIXPublicKey(&private.PublicKey)
	return Credential{Reference: ReferenceForID(id), ID: append([]byte(nil), id...), PublicKey: public, Algorithm: ES256, Generation: generation, RPID: RPID, EnrolledAt: time.Unix(1_800_000_000+int64(generation), 0).UTC(), Status: "active", InternalUV: true, AAGUID: bytes.Repeat([]byte{byte(generation)}, 16), Format: "packed", DeviceSelector: "sha256:" + strings.Repeat("a", 64)}
}

func newFixtureStore(t *testing.T) (*Store, string) {
	t.Helper()
	root := t.TempDir()
	for _, item := range []struct {
		path string
		mode os.FileMode
	}{
		{"var", 0o755}, {"var/lib", 0o755}, {"var/lib/design-machines", 0o755},
		{"var/lib/design-machines/workflow-authority", 0o700},
		{"etc", 0o755}, {"etc/design-machines", 0o755},
		{"etc/design-machines/workflow-authority", 0o755},
		{"etc/design-machines/workflow-authority/trust", 0o755},
	} {
		if err := os.Mkdir(filepath.Join(root, item.path), item.mode); err != nil {
			t.Fatal(err)
		}
	}
	store, err := NewTestStore(root, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	return store, root
}

func TestFakeEnrollerStateMachineRotationRevocationAndRecovery(t *testing.T) {
	store, _ := newFixtureStore(t)
	enroller := &fakeEnroller{}
	first, err := enroller.Enroll(context.Background(), Request{Generation: 1})
	if err != nil || store.Enroll(context.Background(), first) != nil {
		t.Fatalf("first enrollment: %v", err)
	}
	second, err := enroller.Enroll(context.Background(), Request{Generation: 2, ExcludeCredentialID: first.ID})
	if err != nil || store.Rotate(context.Background(), second) != nil {
		t.Fatalf("rotation: %v", err)
	}
	if !bytes.Equal(enroller.calls[1].ExcludeCredentialID, first.ID) {
		t.Fatal("rotation did not exclude the active credential")
	}
	if err := store.Revoke(context.Background(), 2, second.EnrolledAt.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if loaded, err := store.LoadActive(context.Background()); !errors.Is(err, ErrUnavailable) || loaded != nil {
		t.Fatalf("revoked enrollment became active: %v", err)
	}
	recovery, _ := enroller.Enroll(context.Background(), Request{Generation: 3, ExcludeCredentialID: second.ID})
	if err := store.Recover(context.Background(), recovery); err != nil {
		t.Fatal(err)
	}
	loaded, err := store.LoadActive(context.Background())
	if err != nil || loaded.Generation != 3 {
		t.Fatalf("recovery generation: %#v %v", loaded, err)
	}
	loaded.Destroy()
	trust, err := store.LoadTrust(context.Background())
	if err != nil || len(trust.Credentials) != 3 || len(trust.Events) != 5 || trust.Credentials[0].Reference != first.Reference || trust.Credentials[1].Reference != second.Reference {
		t.Fatalf("append-only public history lost: %#v %v", trust, err)
	}
	active, err := trust.ActiveRecord()
	if err != nil || active.Generation != 3 {
		t.Fatalf("public active lookup: %#v %v", active, err)
	}
}

func TestPublicRecordContainsNoCredentialIDOrSecretSentinel(t *testing.T) {
	store, root := newFixtureStore(t)
	secret := []byte("RAW-CREDENTIAL-ID-SENTINEL-never-public")
	credential := testCredentialWithID(1, secret)
	if err := store.Enroll(context.Background(), credential); err != nil {
		t.Fatal(err)
	}
	public, err := os.ReadFile(filepath.Join(root, strings.TrimPrefix(publicPath, "/")))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(public, secret) || bytes.Contains(public, []byte(base64.RawURLEncoding.EncodeToString(secret))) || bytes.Contains(public, []byte("credential_id")) || bytes.Contains(public, []byte(credential.DeviceSelector)) || bytes.Contains(public, []byte("device_selector")) {
		t.Fatal("public record exposed the credential ID")
	}
	if err := store.Enroll(context.Background(), credential); err == nil || strings.Contains(err.Error(), string(secret)) {
		t.Fatalf("secret appeared in error or stale generation accepted: %v", err)
	}
}

func TestClosedCorruptAndMismatchedRecordsFailClosed(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(t *testing.T, root string)
	}{
		{"unknown-private-field", func(t *testing.T, root string) {
			path := filepath.Join(root, strings.TrimPrefix(privatePath, "/"))
			data, _ := os.ReadFile(path)
			data = bytes.Replace(data, []byte("\n"), []byte(",\"unexpected\":true}\n"), 1)
			data = bytes.Replace(data, []byte("},\"unexpected"), []byte(",\"unexpected"), 1)
			if err := os.WriteFile(path, data, 0o600); err != nil {
				t.Fatal(err)
			}
		}},
		{"mismatched-public", func(t *testing.T, root string) {
			path := filepath.Join(root, strings.TrimPrefix(publicPath, "/"))
			data, _ := os.ReadFile(path)
			data = bytes.Replace(data, []byte("\"generation\":1"), []byte("\"generation\":9"), 1)
			if err := os.WriteFile(path, data, 0o644); err != nil {
				t.Fatal(err)
			}
		}},
		{"corrupt-private", func(t *testing.T, root string) {
			path := filepath.Join(root, strings.TrimPrefix(privatePath, "/"))
			if err := os.WriteFile(path, []byte("{\"protocol\":"), 0o600); err != nil {
				t.Fatal(err)
			}
		}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store, root := newFixtureStore(t)
			if err := store.Enroll(context.Background(), testCredential(t, 1)); err != nil {
				t.Fatal(err)
			}
			tt.mutate(t, root)
			if loaded, err := store.LoadActive(context.Background()); err == nil || loaded != nil {
				t.Fatal("corrupt records loaded")
			}
		})
	}
}

func TestStaleGenerationAndPartialRotationRecovery(t *testing.T) {
	store, root := newFixtureStore(t)
	first := testCredential(t, 4)
	if err := store.Enroll(context.Background(), first); err != nil {
		t.Fatal(err)
	}
	if err := store.Rotate(context.Background(), testCredential(t, 4)); !errors.Is(err, ErrConflict) {
		t.Fatalf("stale generation: %v", err)
	}
	second := testCredential(t, 5)
	current, err := store.readPrivate(false)
	if err != nil {
		t.Fatal(err)
	}
	defer current.destroy()
	trust := cloneTrust(current.Trust)
	trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: current.Generation, Action: "rotated", At: second.EnrolledAt})
	trust.Credentials = append(trust.Credentials, publicCredential(second))
	g := second.Generation
	trust.ActiveGeneration = &g
	trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: g, Action: "activated", At: second.EnrolledAt})
	publicBytes, _ := marshalClosed(trust)
	private := privateRecord{Protocol: Protocol, Generation: g, Status: "active", CredentialID: append(secretBytes(nil), second.ID...), DeviceSelector: second.DeviceSelector, Trust: trust, PublicSHA256: digest(publicBytes)}
	privateBytes, _ := marshalClosed(private)
	if err := os.WriteFile(filepath.Join(root, strings.TrimPrefix(privatePath, "/")), privateBytes, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := store.LoadActive(context.Background()); err == nil {
		t.Fatal("partial rotation did not fail closed")
	}
	if err := store.RecoverPartial(context.Background()); err != nil {
		t.Fatal(err)
	}
	loaded, err := store.LoadActive(context.Background())
	if err != nil || loaded.Generation != 5 {
		t.Fatalf("partial recovery: %#v %v", loaded, err)
	}
	loaded.Destroy()
}

func TestSymlinkHardlinkModeOwnerAndParentAttacks(t *testing.T) {
	t.Run("symlink-record", func(t *testing.T) {
		store, root := newFixtureStore(t)
		target := filepath.Join(root, "target")
		if err := os.WriteFile(target, []byte("sentinel"), 0o600); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(target, filepath.Join(root, strings.TrimPrefix(privatePath, "/"))); err != nil {
			t.Fatal(err)
		}
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err == nil {
			t.Fatal("symlink accepted")
		}
	})
	t.Run("symlink-lock", func(t *testing.T) {
		store, root := newFixtureStore(t)
		target := filepath.Join(root, "lock-target")
		if err := os.WriteFile(target, nil, 0o600); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(target, filepath.Join(root, strings.TrimPrefix(lockPath, "/"))); err != nil {
			t.Fatal(err)
		}
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err == nil {
			t.Fatal("symlink lock accepted")
		}
	})
	t.Run("symlink-public-record", func(t *testing.T) {
		store, root := newFixtureStore(t)
		target := filepath.Join(root, "public-target")
		if err := os.WriteFile(target, []byte("sentinel"), 0o644); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(target, filepath.Join(root, strings.TrimPrefix(publicPath, "/"))); err != nil {
			t.Fatal(err)
		}
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err == nil {
			t.Fatal("public symlink accepted")
		}
	})
	t.Run("hardlink-record", func(t *testing.T) {
		store, root := newFixtureStore(t)
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err != nil {
			t.Fatal(err)
		}
		private := filepath.Join(root, strings.TrimPrefix(privatePath, "/"))
		if err := os.Link(private, filepath.Join(filepath.Dir(private), "copy")); err != nil {
			t.Fatal(err)
		}
		if _, err := store.LoadActive(context.Background()); err == nil {
			t.Fatal("hardlink accepted")
		}
	})
	t.Run("wrong-mode", func(t *testing.T) {
		store, root := newFixtureStore(t)
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(filepath.Join(root, strings.TrimPrefix(privatePath, "/")), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := store.LoadActive(context.Background()); err == nil {
			t.Fatal("wrong mode accepted")
		}
	})
	t.Run("symlink-parent", func(t *testing.T) {
		store, root := newFixtureStore(t)
		trust := filepath.Join(root, "etc/design-machines/workflow-authority/trust")
		if err := os.Rename(trust, trust+"-real"); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(trust+"-real", trust); err != nil {
			t.Fatal(err)
		}
		if err := store.Enroll(context.Background(), testCredential(t, 1)); err == nil {
			t.Fatal("symlink parent accepted")
		}
	})
	t.Run("wrong-owner-expectation", func(t *testing.T) {
		root := t.TempDir()
		if _, err := NewTestStore(root, uint32(os.Getuid()+1)); err == nil {
			t.Fatal("wrong owner accepted")
		}
	})
}

func TestConcurrentActivationSerializesGeneration(t *testing.T) {
	store, _ := newFixtureStore(t)
	if err := store.Enroll(context.Background(), testCredential(t, 1)); err != nil {
		t.Fatal(err)
	}
	const count = 24
	var wg sync.WaitGroup
	results := make(chan error, count)
	for i := 1; i <= count; i++ {
		wg.Add(1)
		go func(generation uint64) {
			defer wg.Done()
			results <- store.Rotate(context.Background(), testCredential(t, generation+1))
		}(uint64(i))
	}
	wg.Wait()
	close(results)
	for err := range results {
		if err != nil && !errors.Is(err, ErrConflict) {
			t.Fatalf("unexpected concurrent error: %v", err)
		}
	}
	loaded, err := store.LoadActive(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Generation < 2 || loaded.Generation > count+1 {
		t.Fatalf("bad generation %d", loaded.Generation)
	}
	loaded.Destroy()
}

func TestTwoStoreInstancesPreventStaleInterleaving(t *testing.T) {
	first, root := newFixtureStore(t)
	second, err := NewTestStore(root, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	if err := first.Enroll(context.Background(), testCredential(t, 1)); err != nil {
		t.Fatal(err)
	}
	start := make(chan struct{})
	results := make(chan error, 2)
	go func() { <-start; results <- first.Rotate(context.Background(), testCredential(t, 2)) }()
	go func() { <-start; results <- second.Rotate(context.Background(), testCredential(t, 3)) }()
	close(start)
	err1, err2 := <-results, <-results
	for _, err := range []error{err1, err2} {
		if err != nil && !errors.Is(err, ErrConflict) {
			t.Fatalf("cross-store error: %v", err)
		}
	}
	loaded, err := first.LoadActive(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Generation < 2 || loaded.Generation > 3 {
		t.Fatalf("stale generation won: %d", loaded.Generation)
	}
	loaded.Destroy()
	trust, err := second.LoadTrust(context.Background())
	if err != nil || validateTrust(trust) != nil {
		t.Fatalf("split public/private state: %v", err)
	}
}

func TestCancellationAndRequestValidation(t *testing.T) {
	store, _ := newFixtureStore(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := store.Enroll(ctx, testCredential(t, 1)); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("cancel: %v", err)
	}
	enroller := &fakeEnroller{}
	if _, err := enroller.Enroll(ctx, Request{Generation: 1}); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("enroller cancel: %v", err)
	}
	bad := testCredential(t, 1)
	bad.RPID = "attacker.invalid"
	if err := store.Enroll(context.Background(), bad); !errors.Is(err, ErrDenied) {
		t.Fatalf("bad RP: %v", err)
	}
}

func TestProductionPathsAreFixed(t *testing.T) {
	store := NewStore()
	if store.fixture || store.resolve(privatePath) != privatePath || store.resolve(publicPath) != publicPath || store.resolve(lockPath) != lockPath {
		t.Fatal("production paths became injectable")
	}
	if runtime.GOOS == "windows" {
		t.Skip("Unix ownership contract")
	}
}

func TestDecodedPrivateSecretCanBeDestroyed(t *testing.T) {
	record := privateRecord{CredentialID: secretBytes("secret-sentinel")}
	alias := record.CredentialID
	record.destroy()
	if !bytes.Equal(alias, make([]byte, len(alias))) || record.CredentialID != nil {
		t.Fatal("decoded private secret was not zeroized")
	}
}

func base64Raw(value []byte) string {
	return base64.RawURLEncoding.EncodeToString(value)
}
