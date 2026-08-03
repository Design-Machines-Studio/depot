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
	publicPath  = "/etc/design-machines/workflow-authority/trust/authority-public.json"
	maxRecord   = 32 << 10
)

type privateRecord struct {
	Protocol          string      `json:"protocol"`
	Generation        uint64      `json:"generation"`
	Reference         string      `json:"reference"`
	CredentialID      secretBytes `json:"credential_id"`
	PublicKey         string      `json:"public_key"`
	PublicSHA256      string      `json:"public_sha256"`
	Algorithm         int         `json:"algorithm"`
	RPID              string      `json:"rp_id"`
	EnrolledAt        time.Time   `json:"enrolled_at"`
	Status            string      `json:"status"`
	RevokedAt         *time.Time  `json:"revoked_at,omitempty"`
	InternalUV        bool        `json:"internal_uv"`
	AAGUID            string      `json:"aaguid,omitempty"`
	AttestationFormat string      `json:"attestation_format"`
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

func (r *privateRecord) destroy() {
	zero(r.CredentialID)
	r.CredentialID = nil
}

type PublicRecord struct {
	Protocol          string     `json:"protocol"`
	Generation        uint64     `json:"generation"`
	Reference         string     `json:"reference"`
	PublicKey         string     `json:"public_key"`
	Algorithm         int        `json:"algorithm"`
	RPID              string     `json:"rp_id"`
	EnrolledAt        time.Time  `json:"enrolled_at"`
	Status            string     `json:"status"`
	RevokedAt         *time.Time `json:"revoked_at,omitempty"`
	InternalUV        bool       `json:"internal_uv"`
	AAGUID            string     `json:"aaguid,omitempty"`
	AttestationFormat string     `json:"attestation_format"`
}

type Store struct {
	mu      sync.Mutex
	root    string
	owner   uint32
	fixture bool
}

func NewStore() *Store { return &Store{root: "/", owner: 0} }

// NewTestStore is the only path-injecting constructor. It must never be used by
// production wiring.
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
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil || ValidateCredential(credential) != nil {
		return ErrDenied
	}
	current, err := s.readPrivate(true)
	defer current.destroy()
	if err == nil {
		return ErrConflict
	}
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return s.commit(credential)
}

func (s *Store) Rotate(ctx context.Context, credential Credential) error {
	return s.replace(ctx, credential, "active")
}

func (s *Store) Recover(ctx context.Context, credential Credential) error {
	return s.replace(ctx, credential, "revoked")
}

func (s *Store) replace(ctx context.Context, credential Credential, requiredStatus string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil || ValidateCredential(credential) != nil {
		return ErrDenied
	}
	current, err := s.readPrivate(false)
	if err != nil {
		return err
	}
	defer current.destroy()
	if current.Status != requiredStatus || credential.Generation <= current.Generation {
		return ErrConflict
	}
	return s.commit(credential)
}

func (s *Store) RecoverPartial(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil {
		return ErrUnavailable
	}
	private, err := s.readPrivate(false)
	if err != nil {
		return err
	}
	defer private.destroy()
	public, publicBytes, err := private.publicProjection()
	if err != nil || digest(publicBytes) != private.PublicSHA256 {
		return ErrCorrupt
	}
	if err := validatePublic(public); err != nil {
		return err
	}
	return s.writeRecord(publicPath, 0o644, publicBytes)
}

func (s *Store) Revoke(ctx context.Context, generation uint64, at time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil || generation == 0 || at.IsZero() {
		return ErrDenied
	}
	private, err := s.readPrivate(false)
	if err != nil {
		return err
	}
	defer private.destroy()
	if private.Generation != generation || private.Status != "active" || at.Before(private.EnrolledAt) {
		return ErrConflict
	}
	credential, err := private.credential()
	if err != nil {
		return err
	}
	defer credential.Destroy()
	credential.Status = "revoked"
	when := at.UTC()
	credential.RevokedAt = &when
	return s.commit(credential)
}

func (s *Store) LoadActive(ctx context.Context) (*Credential, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if ctx.Err() != nil {
		return nil, ErrUnavailable
	}
	private, err := s.readPrivate(false)
	if err != nil {
		return nil, err
	}
	defer private.destroy()
	public, publicBytes, err := private.publicProjection()
	if err != nil || digest(publicBytes) != private.PublicSHA256 || validatePublic(public) != nil {
		return nil, ErrCorrupt
	}
	actualPublic, err := s.readPublic()
	if err != nil || !bytes.Equal(actualPublic, publicBytes) {
		return nil, ErrCorrupt
	}
	credential, err := private.credential()
	if err != nil || credential.Status != "active" || credential.RevokedAt != nil {
		if err == nil {
			credential.Destroy()
		}
		return nil, ErrUnavailable
	}
	return &credential, nil
}

func (s *Store) commit(credential Credential) error {
	public := projection(credential)
	publicBytes, err := marshalClosed(public)
	if err != nil {
		return ErrCorrupt
	}
	private := privateRecord{
		Protocol: Protocol, Generation: credential.Generation, Reference: credential.Reference,
		CredentialID: append(secretBytes(nil), credential.ID...), PublicKey: base64.RawURLEncoding.EncodeToString(credential.PublicKey),
		PublicSHA256: digest(publicBytes), Algorithm: credential.Algorithm, RPID: credential.RPID,
		EnrolledAt: credential.EnrolledAt.UTC(), Status: credential.Status, RevokedAt: credential.RevokedAt,
		InternalUV: credential.InternalUV, AAGUID: base64.RawURLEncoding.EncodeToString(credential.AAGUID), AttestationFormat: credential.Format,
	}
	privateBytes, err := marshalClosed(private)
	if err != nil {
		return ErrCorrupt
	}
	defer zero(privateBytes)
	if bytes.Contains(publicBytes, []byte(base64.RawURLEncoding.EncodeToString(private.CredentialID))) {
		return ErrCorrupt
	}
	if err := s.writeRecord(privatePath, 0o600, privateBytes); err != nil {
		return err
	}
	if err := s.writeRecord(publicPath, 0o644, publicBytes); err != nil {
		return err
	}
	return nil
}

func projection(c Credential) PublicRecord {
	return PublicRecord{Protocol: Protocol, Generation: c.Generation, Reference: c.Reference, PublicKey: base64.RawURLEncoding.EncodeToString(c.PublicKey), Algorithm: c.Algorithm, RPID: c.RPID, EnrolledAt: c.EnrolledAt.UTC(), Status: c.Status, RevokedAt: c.RevokedAt, InternalUV: c.InternalUV, AAGUID: base64.RawURLEncoding.EncodeToString(c.AAGUID), AttestationFormat: c.Format}
}

func (r privateRecord) publicProjection() (PublicRecord, []byte, error) {
	public := PublicRecord{Protocol: r.Protocol, Generation: r.Generation, Reference: r.Reference, PublicKey: r.PublicKey, Algorithm: r.Algorithm, RPID: r.RPID, EnrolledAt: r.EnrolledAt, Status: r.Status, RevokedAt: r.RevokedAt, InternalUV: r.InternalUV, AAGUID: r.AAGUID, AttestationFormat: r.AttestationFormat}
	data, err := marshalClosed(public)
	return public, data, err
}

func (r privateRecord) credential() (Credential, error) {
	id := append([]byte(nil), r.CredentialID...)
	publicKey, err := base64.RawURLEncoding.Strict().DecodeString(r.PublicKey)
	if err != nil {
		zero(id)
		return Credential{}, ErrCorrupt
	}
	aaguid, err := base64.RawURLEncoding.Strict().DecodeString(r.AAGUID)
	if err != nil {
		zero(id)
		return Credential{}, ErrCorrupt
	}
	c := Credential{Reference: r.Reference, ID: id, PublicKey: publicKey, Algorithm: r.Algorithm, Generation: r.Generation, RPID: r.RPID, EnrolledAt: r.EnrolledAt, Status: r.Status, RevokedAt: r.RevokedAt, InternalUV: r.InternalUV, AAGUID: aaguid, Format: r.AttestationFormat}
	if c.Status == "active" {
		if ValidateCredential(c) != nil {
			c.Destroy()
			return Credential{}, ErrCorrupt
		}
	} else if c.Status != "revoked" || c.RevokedAt == nil || c.RevokedAt.Before(c.EnrolledAt) || c.Generation == 0 || c.Reference != ReferenceForID(c.ID) || c.Algorithm != ES256 || c.RPID != RPID || c.EnrolledAt.IsZero() || !c.InternalUV || c.Format != "packed" || validatePublicKey(c.PublicKey) != nil {
		c.Destroy()
		return Credential{}, ErrCorrupt
	}
	return c, nil
}

func validatePublic(r PublicRecord) error {
	if r.Protocol != Protocol || r.Generation == 0 || r.Reference == "" || r.Algorithm != ES256 || r.RPID != RPID || r.EnrolledAt.IsZero() || !r.InternalUV || r.AttestationFormat != "packed" || (r.Status != "active" && r.Status != "revoked") || (r.Status == "active" && r.RevokedAt != nil) || (r.Status == "revoked" && r.RevokedAt == nil) {
		return ErrCorrupt
	}
	key, err := base64.RawURLEncoding.Strict().DecodeString(r.PublicKey)
	if err != nil || len(key) == 0 || len(key) > 4096 || validatePublicKey(key) != nil {
		return ErrCorrupt
	}
	return nil
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
	if decodeClosed(data, &record) != nil || record.Protocol != Protocol || record.PublicSHA256 == "" || len(record.CredentialID) == 0 {
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
	credential, err := record.credential()
	if err != nil {
		record.destroy()
		return privateRecord{}, ErrCorrupt
	}
	credential.Destroy()
	return record, nil
}

func (s *Store) readPublic() ([]byte, error) {
	data, err := s.readRecord(publicPath, 0o644)
	if err != nil {
		return nil, err
	}
	var record PublicRecord
	if decodeClosed(data, &record) != nil || validatePublic(record) != nil {
		return nil, ErrCorrupt
	}
	canonical, err := marshalClosed(record)
	if err != nil || !bytes.Equal(data, canonical) {
		return nil, ErrCorrupt
	}
	return data, nil
}

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
	expectedMode := os.FileMode(0o755)
	if productionDir == filepath.Dir(privatePath) {
		expectedMode = 0o700
	}
	if err := s.validateAncestors(dirPath, expectedMode); err != nil {
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
	if statErr != nil || !info.IsDir() || info.Mode().Perm() != expectedMode || !ownedBy(info, s.owner) {
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

func marshalClosed(value any) ([]byte, error) {
	data, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}

func decodeClosed(data []byte, value any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(value); err != nil {
		return err
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return fmt.Errorf("trailing data")
	}
	return nil
}

func digest(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
