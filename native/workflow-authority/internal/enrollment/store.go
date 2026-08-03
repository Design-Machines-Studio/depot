package enrollment

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	privatePath = "/var/lib/design-machines/workflow-authority/enrollment-private.json"
	lockPath    = "/var/lib/design-machines/workflow-authority/enrollment.lock"
	publicPath  = "/etc/design-machines/workflow-authority/trust/authority-public.json"
	maxRecord   = 1 << 20
)

type PublicCredential struct {
	Generation        uint64    `json:"generation"`
	Reference         string    `json:"reference"`
	PublicKey         string    `json:"public_key"`
	Algorithm         int       `json:"algorithm"`
	RPID              string    `json:"rp_id"`
	EnrolledAt        time.Time `json:"enrolled_at"`
	InternalUV        bool      `json:"internal_uv"`
	AAGUID            string    `json:"aaguid"`
	AttestationFormat string    `json:"attestation_format"`
	DeviceSelector    string    `json:"device_selector"`
}

type LifecycleEvent struct {
	Sequence   uint64    `json:"sequence"`
	Generation uint64    `json:"generation"`
	Action     string    `json:"action"`
	At         time.Time `json:"at"`
}

type PublicTrust struct {
	Protocol         string             `json:"protocol"`
	ActiveGeneration *uint64            `json:"active_generation"`
	Credentials      []PublicCredential `json:"credentials"`
	Events           []LifecycleEvent   `json:"events"`
}

type privateRecord struct {
	Protocol     string      `json:"protocol"`
	Generation   uint64      `json:"generation"`
	Status       string      `json:"status"`
	CredentialID secretBytes `json:"credential_id,omitempty"`
	Trust        PublicTrust `json:"trust"`
	PublicSHA256 string      `json:"public_sha256"`
}

type secretBytes []byte

func (s secretBytes) MarshalJSON() ([]byte, error) {
	return json.Marshal(base64.RawURLEncoding.EncodeToString(s))
}
func (s *secretBytes) UnmarshalJSON(data []byte) error {
	var encoded string
	if json.Unmarshal(data, &encoded) != nil || encoded == "" {
		return ErrCorrupt
	}
	decoded, err := base64.RawURLEncoding.Strict().DecodeString(encoded)
	if err != nil || len(decoded) == 0 || len(decoded) > 4096 {
		zero(decoded)
		return ErrCorrupt
	}
	*s = decoded
	return nil
}
func (r *privateRecord) destroy() { zero(r.CredentialID); r.CredentialID = nil }

type Store struct {
	mu      sync.Mutex
	root    string
	owner   uint32
	fixture bool
}

func NewStore() *Store { return &Store{root: "/", owner: 0} }
func NewTestStore(root string, owner uint32) (*Store, error) {
	if !filepath.IsAbs(root) || filepath.Clean(root) == "/" {
		return nil, ErrDenied
	}
	info, err := os.Lstat(root)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || !ownedBy(info, owner) || info.Mode().Perm()&0o022 != 0 {
		return nil, ErrDenied
	}
	return &Store{root: filepath.Clean(root), owner: owner, fixture: true}, nil
}

func (s *Store) Enroll(ctx context.Context, credential Credential) error {
	return s.withLock(ctx, func() error {
		if ValidateCredential(credential) != nil {
			return ErrDenied
		}
		current, err := s.readPrivate(true)
		current.destroy()
		if err == nil {
			return ErrConflict
		}
		if !errors.Is(err, os.ErrNotExist) {
			return err
		}
		g := credential.Generation
		trust := PublicTrust{Protocol: Protocol, ActiveGeneration: &g, Credentials: []PublicCredential{publicCredential(credential)}, Events: []LifecycleEvent{{Sequence: 1, Generation: g, Action: "activated", At: credential.EnrolledAt.UTC()}}}
		return s.commit(privateRecord{Protocol: Protocol, Generation: g, Status: "active", CredentialID: append(secretBytes(nil), credential.ID...), Trust: trust})
	})
}

func (s *Store) Rotate(ctx context.Context, credential Credential) error {
	return s.withLock(ctx, func() error {
		if ValidateCredential(credential) != nil {
			return ErrDenied
		}
		current, err := s.readState()
		if err != nil {
			return err
		}
		defer current.destroy()
		if current.Status != "active" || credential.Generation <= current.Generation {
			return ErrConflict
		}
		trust := cloneTrust(current.Trust)
		trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: current.Generation, Action: "rotated", At: credential.EnrolledAt.UTC()})
		trust.Credentials = append(trust.Credentials, publicCredential(credential))
		g := credential.Generation
		trust.ActiveGeneration = &g
		trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: g, Action: "activated", At: credential.EnrolledAt.UTC()})
		return s.commit(privateRecord{Protocol: Protocol, Generation: g, Status: "active", CredentialID: append(secretBytes(nil), credential.ID...), Trust: trust})
	})
}

func (s *Store) Revoke(ctx context.Context, generation uint64, at time.Time) error {
	return s.withLock(ctx, func() error {
		if generation == 0 || at.IsZero() {
			return ErrDenied
		}
		current, err := s.readState()
		if err != nil {
			return err
		}
		defer current.destroy()
		if current.Status != "active" || current.Generation != generation || at.Before(activeEnrolledAt(current.Trust)) {
			return ErrConflict
		}
		trust := cloneTrust(current.Trust)
		trust.ActiveGeneration = nil
		trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: generation, Action: "revoked", At: at.UTC()})
		return s.commit(privateRecord{Protocol: Protocol, Generation: generation, Status: "revoked", Trust: trust})
	})
}

func (s *Store) Recover(ctx context.Context, credential Credential) error {
	return s.withLock(ctx, func() error {
		if ValidateCredential(credential) != nil {
			return ErrDenied
		}
		current, err := s.readState()
		if err != nil {
			return err
		}
		defer current.destroy()
		if current.Status != "revoked" || credential.Generation <= maxGeneration(current.Trust) {
			return ErrConflict
		}
		trust := cloneTrust(current.Trust)
		trust.Credentials = append(trust.Credentials, publicCredential(credential))
		g := credential.Generation
		trust.ActiveGeneration = &g
		trust.Events = append(trust.Events, LifecycleEvent{Sequence: uint64(len(trust.Events) + 1), Generation: g, Action: "recovered", At: credential.EnrolledAt.UTC()})
		return s.commit(privateRecord{Protocol: Protocol, Generation: g, Status: "active", CredentialID: append(secretBytes(nil), credential.ID...), Trust: trust})
	})
}

func (s *Store) RecoverPartial(ctx context.Context) error {
	return s.withLock(ctx, func() error {
		private, err := s.readPrivate(false)
		if err != nil {
			return err
		}
		defer private.destroy()
		publicBytes, err := marshalClosed(private.Trust)
		if err != nil || digest(publicBytes) != private.PublicSHA256 || validateTrust(private.Trust) != nil {
			return ErrCorrupt
		}
		return s.writeRecord(publicPath, 0o644, publicBytes)
	})
}

func (s *Store) LoadActive(ctx context.Context) (*Credential, error) {
	var result *Credential
	err := s.withLock(ctx, func() error {
		private, err := s.readState()
		if err != nil {
			return err
		}
		defer private.destroy()
		if private.Status != "active" || private.Trust.ActiveGeneration == nil {
			return ErrUnavailable
		}
		credential, err := private.activeCredential()
		if err != nil {
			return err
		}
		result = &credential
		return nil
	})
	if err != nil {
		return nil, err
	}
	return result, nil
}

func (s *Store) LoadTrust(ctx context.Context) (PublicTrust, error) {
	var result PublicTrust
	err := s.withLock(ctx, func() error {
		private, err := s.readState()
		if err != nil {
			return err
		}
		defer private.destroy()
		result = cloneTrust(private.Trust)
		return nil
	})
	return result, err
}

func (s *Store) withLock(ctx context.Context, fn func() error) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil {
		return ErrUnavailable
	}
	lock, err := s.acquireProcessLock(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = syscall.Flock(int(lock.Fd()), syscall.LOCK_UN); _ = lock.Close() }()
	return fn()
}

func (s *Store) acquireProcessLock(ctx context.Context) (*os.File, error) {
	resolved := s.resolve(lockPath)
	dir, base, err := s.openSecureParent(resolved, filepath.Dir(lockPath))
	if err != nil {
		return nil, err
	}
	defer dir.Close()
	f, err := dir.OpenFile(base, os.O_RDWR|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, 0o600)
	created := err == nil
	if errors.Is(err, os.ErrExist) {
		f, err = dir.OpenFile(base, os.O_RDWR|syscall.O_NOFOLLOW, 0)
	}
	if err != nil {
		return nil, ErrUnavailable
	}
	if created {
		if err := f.Chmod(0o600); err != nil {
			f.Close()
			return nil, ErrUnavailable
		}
	}
	if info, err := f.Stat(); err != nil || !validFile(info, s.owner, 0o600) {
		f.Close()
		return nil, ErrCorrupt
	}
	for {
		err = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			return f, nil
		}
		if err != syscall.EWOULDBLOCK && err != syscall.EAGAIN {
			f.Close()
			return nil, ErrUnavailable
		}
		select {
		case <-ctx.Done():
			f.Close()
			return nil, ErrUnavailable
		case <-time.After(5 * time.Millisecond):
		}
	}
}

func (s *Store) commit(private privateRecord) error {
	defer private.destroy()
	if validateTrust(private.Trust) != nil {
		return ErrCorrupt
	}
	publicBytes, err := marshalClosed(private.Trust)
	if err != nil {
		return ErrCorrupt
	}
	private.PublicSHA256 = digest(publicBytes)
	privateBytes, err := marshalClosed(private)
	if err != nil {
		return ErrCorrupt
	}
	defer zero(privateBytes)
	if len(private.CredentialID) > 0 && bytes.Contains(publicBytes, []byte(base64.RawURLEncoding.EncodeToString(private.CredentialID))) {
		return ErrCorrupt
	}
	if err := s.writeRecord(privatePath, 0o600, privateBytes); err != nil {
		return err
	}
	return s.writeRecord(publicPath, 0o644, publicBytes)
}

func (s *Store) readState() (privateRecord, error) {
	private, err := s.readPrivate(false)
	if err != nil {
		return privateRecord{}, err
	}
	publicBytes, err := s.readRecord(publicPath, 0o644)
	if err != nil {
		private.destroy()
		return privateRecord{}, err
	}
	var public PublicTrust
	if decodeClosed(publicBytes, &public) != nil || validateTrust(public) != nil {
		private.destroy()
		return privateRecord{}, ErrCorrupt
	}
	canonical, _ := marshalClosed(public)
	if !bytes.Equal(publicBytes, canonical) || digest(canonical) != private.PublicSHA256 || !bytes.Equal(canonical, mustMarshal(private.Trust)) {
		private.destroy()
		return privateRecord{}, ErrCorrupt
	}
	return private, nil
}

func (s *Store) readPrivate(missingOK bool) (privateRecord, error) {
	data, err := s.readRecord(privatePath, 0o600)
	if err != nil {
		if missingOK && errors.Is(err, os.ErrNotExist) {
			return privateRecord{}, os.ErrNotExist
		}
		return privateRecord{}, err
	}
	defer zero(data)
	var record privateRecord
	if decodeClosed(data, &record) != nil || record.Protocol != Protocol || record.PublicSHA256 == "" || validateTrust(record.Trust) != nil {
		record.destroy()
		return privateRecord{}, ErrCorrupt
	}
	canonical, err := marshalClosed(record)
	if err != nil || !bytes.Equal(data, canonical) {
		zero(canonical)
		record.destroy()
		return privateRecord{}, ErrCorrupt
	}
	zero(canonical)
	if record.Trust.ActiveGeneration == nil {
		if record.Status != "revoked" || len(record.CredentialID) != 0 || record.Generation == 0 {
			record.destroy()
			return privateRecord{}, ErrCorrupt
		}
	} else {
		if record.Status != "active" || record.Generation != *record.Trust.ActiveGeneration || len(record.CredentialID) == 0 {
			record.destroy()
			return privateRecord{}, ErrCorrupt
		}
		credential, err := record.activeCredential()
		if err != nil {
			record.destroy()
			return privateRecord{}, err
		}
		credential.Destroy()
	}
	return record, nil
}

func (r privateRecord) activeCredential() (Credential, error) {
	if r.Trust.ActiveGeneration == nil {
		return Credential{}, ErrUnavailable
	}
	for _, public := range r.Trust.Credentials {
		if public.Generation == *r.Trust.ActiveGeneration {
			key, e1 := base64.RawURLEncoding.Strict().DecodeString(public.PublicKey)
			aaguid, e2 := base64.RawURLEncoding.Strict().DecodeString(public.AAGUID)
			if e1 != nil || e2 != nil {
				return Credential{}, ErrCorrupt
			}
			c := Credential{Reference: public.Reference, ID: append([]byte(nil), r.CredentialID...), PublicKey: key, Algorithm: public.Algorithm, Generation: public.Generation, RPID: public.RPID, EnrolledAt: public.EnrolledAt, Status: "active", InternalUV: public.InternalUV, AAGUID: aaguid, Format: public.AttestationFormat, DeviceSelector: public.DeviceSelector}
			if ValidateCredential(c) != nil {
				c.Destroy()
				return Credential{}, ErrCorrupt
			}
			return c, nil
		}
	}
	return Credential{}, ErrCorrupt
}

func publicCredential(c Credential) PublicCredential {
	return PublicCredential{Generation: c.Generation, Reference: c.Reference, PublicKey: base64.RawURLEncoding.EncodeToString(c.PublicKey), Algorithm: c.Algorithm, RPID: c.RPID, EnrolledAt: c.EnrolledAt.UTC(), InternalUV: c.InternalUV, AAGUID: base64.RawURLEncoding.EncodeToString(c.AAGUID), AttestationFormat: c.Format, DeviceSelector: c.DeviceSelector}
}

func validateTrust(t PublicTrust) error {
	if t.Protocol != Protocol || len(t.Credentials) == 0 || len(t.Events) == 0 || len(t.Credentials) > 1024 || len(t.Events) > 4096 {
		return ErrCorrupt
	}
	credentials := make(map[uint64]PublicCredential, len(t.Credentials))
	var previous uint64
	for _, c := range t.Credentials {
		key, e1 := base64.RawURLEncoding.Strict().DecodeString(c.PublicKey)
		aaguid, e2 := base64.RawURLEncoding.Strict().DecodeString(c.AAGUID)
		if c.Generation <= previous || c.Reference == "" || c.Algorithm != ES256 || c.RPID != RPID || c.EnrolledAt.IsZero() || !c.InternalUV || c.AttestationFormat != "packed" || !validSelector(c.DeviceSelector) || e1 != nil || e2 != nil || len(aaguid) != 16 || validatePublicKey(key) != nil {
			return ErrCorrupt
		}
		credentials[c.Generation] = c
		previous = c.Generation
	}
	var active uint64
	var lastAction string
	activated := make(map[uint64]bool)
	for i, e := range t.Events {
		c, ok := credentials[e.Generation]
		if e.Sequence != uint64(i+1) || !ok || e.At.IsZero() || e.At.Before(c.EnrolledAt) {
			return ErrCorrupt
		}
		switch e.Action {
		case "activated":
			if active != 0 || activated[e.Generation] {
				return ErrCorrupt
			}
			active = e.Generation
			activated[e.Generation] = true
		case "rotated":
			if active != e.Generation {
				return ErrCorrupt
			}
			active = 0
		case "revoked":
			if active != e.Generation {
				return ErrCorrupt
			}
			active = 0
		case "recovered":
			if active != 0 || lastAction != "revoked" || activated[e.Generation] {
				return ErrCorrupt
			}
			active = e.Generation
			activated[e.Generation] = true
		default:
			return ErrCorrupt
		}
		lastAction = e.Action
	}
	for g := range credentials {
		if !activated[g] {
			return ErrCorrupt
		}
	}
	if (active == 0) != (t.ActiveGeneration == nil) || active != 0 && *t.ActiveGeneration != active {
		return ErrCorrupt
	}
	return nil
}

func validSelector(s string) bool {
	if len(s) != 71 || !strings.HasPrefix(s, "sha256:") {
		return false
	}
	_, err := hex.DecodeString(strings.TrimPrefix(s, "sha256:"))
	return err == nil
}
func activeEnrolledAt(t PublicTrust) time.Time {
	if t.ActiveGeneration == nil {
		return time.Time{}
	}
	for _, c := range t.Credentials {
		if c.Generation == *t.ActiveGeneration {
			return c.EnrolledAt
		}
	}
	return time.Time{}
}
func maxGeneration(t PublicTrust) uint64 {
	if len(t.Credentials) == 0 {
		return 0
	}
	return t.Credentials[len(t.Credentials)-1].Generation
}
func cloneTrust(t PublicTrust) PublicTrust {
	data := mustMarshal(t)
	var out PublicTrust
	_ = decodeClosed(data, &out)
	return out
}
func mustMarshal(v any) []byte { data, _ := marshalClosed(v); return data }

func (s *Store) resolve(path string) string {
	if !s.fixture {
		return path
	}
	return filepath.Join(s.root, strings.TrimPrefix(path, "/"))
}
func (s *Store) readRecord(path string, mode os.FileMode) ([]byte, error) {
	resolved := s.resolve(path)
	dir, base, err := s.openSecureParent(resolved, filepath.Dir(path))
	if err != nil {
		return nil, err
	}
	defer dir.Close()
	f, err := dir.OpenFile(base, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || !validFile(info, s.owner, mode) {
		return nil, ErrCorrupt
	}
	data, err := io.ReadAll(io.LimitReader(f, maxRecord+1))
	if err != nil || len(data) == 0 || len(data) > maxRecord {
		zero(data)
		return nil, ErrCorrupt
	}
	return data, nil
}
func (s *Store) writeRecord(path string, mode os.FileMode, data []byte) error {
	resolved := s.resolve(path)
	dir, base, err := s.openSecureParent(resolved, filepath.Dir(path))
	if err != nil {
		return err
	}
	defer dir.Close()
	var nonce [12]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return ErrUnavailable
	}
	tmp := "." + base + "." + hex.EncodeToString(nonce[:]) + ".tmp"
	if existing, err := dir.Lstat(base); err == nil {
		if !validFile(existing, s.owner, mode) {
			return ErrCorrupt
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ErrUnavailable
	}
	f, err := dir.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, mode)
	if err != nil {
		return ErrUnavailable
	}
	committed := false
	defer func() {
		_ = f.Close()
		if !committed {
			_ = dir.Remove(tmp)
		}
	}()
	if err := f.Chmod(mode); err != nil {
		return ErrUnavailable
	}
	if _, err := f.Write(data); err != nil {
		return ErrUnavailable
	}
	if err := f.Sync(); err != nil {
		return ErrUnavailable
	}
	info, err := f.Stat()
	if err != nil || !validFile(info, s.owner, mode) {
		return ErrCorrupt
	}
	if err := f.Close(); err != nil {
		return ErrUnavailable
	}
	if err := dir.Rename(tmp, base); err != nil {
		return ErrUnavailable
	}
	committed = true
	d, err := dir.Open(".")
	if err != nil {
		return ErrDurability
	}
	err = d.Sync()
	_ = d.Close()
	if err != nil {
		return ErrDurability
	}
	return nil
}
func (s *Store) openSecureParent(resolved, productionDir string) (*os.Root, string, error) {
	dirPath := filepath.Dir(resolved)
	mode := os.FileMode(0o755)
	if productionDir == filepath.Dir(privatePath) {
		mode = 0o700
	}
	if err := s.validateAncestors(dirPath, mode); err != nil {
		return nil, "", err
	}
	root, err := os.OpenRoot(dirPath)
	if err != nil {
		return nil, "", ErrUnavailable
	}
	f, err := root.Open(".")
	if err != nil {
		root.Close()
		return nil, "", ErrUnavailable
	}
	info, statErr := f.Stat()
	_ = f.Close()
	if statErr != nil || !info.IsDir() || info.Mode().Perm() != mode || !ownedBy(info, s.owner) {
		root.Close()
		return nil, "", ErrCorrupt
	}
	return root, filepath.Base(resolved), nil
}
func (s *Store) validateAncestors(dir string, finalMode os.FileMode) error {
	start := "/"
	if s.fixture {
		start = s.root
	}
	rel, err := filepath.Rel(start, dir)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return ErrDenied
	}
	current := start
	for _, part := range strings.Split(rel, string(filepath.Separator)) {
		if part == "" || part == "." {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || !ownedBy(info, s.owner) || info.Mode().Perm()&0o022 != 0 {
			return ErrCorrupt
		}
	}
	info, err := os.Lstat(dir)
	if err != nil || info.Mode().Perm() != finalMode {
		return ErrCorrupt
	}
	return nil
}
func validFile(info os.FileInfo, owner uint32, mode os.FileMode) bool {
	stat, ok := info.Sys().(*syscall.Stat_t)
	return ok && info.Mode().IsRegular() && info.Mode().Perm() == mode && stat.Uid == owner && stat.Nlink == 1
}
func ownedBy(info os.FileInfo, owner uint32) bool {
	stat, ok := info.Sys().(*syscall.Stat_t)
	return ok && stat.Uid == owner
}
func marshalClosed(v any) ([]byte, error) {
	data, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}
func decodeClosed(data []byte, v any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(v); err != nil {
		return err
	}
	if err := d.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return fmt.Errorf("trailing data")
	}
	return nil
}
func digest(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
