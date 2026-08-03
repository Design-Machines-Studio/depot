package client

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/x509"
	"encoding/base64"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
)

type publicTrustRecord struct {
	SchemaVersion int    `json:"schema_version"`
	Protocol      string `json:"protocol"`
	Reference     string `json:"reference"`
	PublicKeyPKIX string `json:"public_key_pkix"`
	Algorithm     int    `json:"algorithm"`
	Generation    uint64 `json:"generation"`
	RPID          string `json:"rp_id"`
	EnrolledAt    string `json:"enrolled_at"`
	Status        string `json:"status"`
	InternalUV    bool   `json:"internal_uv"`
	SignCount     uint32 `json:"sign_count"`
}

var trustReferencePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$`)

func (r *Runner) loadTrust() (authority.Credential, error) {
	if err := validateRegularPath(r.trustPath, r.trustAnchor, 0o644, r.expectedOwner); err != nil {
		return authority.Credential{}, err
	}
	root, err := os.OpenRoot(filepath.Dir(r.trustPath))
	if err != nil {
		return authority.Credential{}, ErrUnavailable
	}
	defer root.Close()
	file, err := root.OpenFile(filepath.Base(r.trustPath), os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return authority.Credential{}, ErrUnavailable
	}
	raw, err := ioReadBounded(file, protocol.MaxFrameBytes)
	closeErr := file.Close()
	if err != nil || closeErr != nil {
		return authority.Credential{}, ErrUnavailable
	}
	var record publicTrustRecord
	if protocol.DecodeClosed(raw, &record) != nil || record.SchemaVersion != 1 || record.Protocol != "workflow-authority-fido-enrollment-v1" || !trustReferencePattern.MatchString(record.Reference) || record.Algorithm != -7 || record.Generation == 0 || record.Generation > math.MaxInt64 || record.RPID != "workflow-authority.designmachines.local" || record.Status != "active" || !record.InternalUV {
		return authority.Credential{}, ErrUnavailable
	}
	publicKey, err := base64.RawURLEncoding.DecodeString(record.PublicKeyPKIX)
	enrolled, timeErr := time.Parse(time.RFC3339, record.EnrolledAt)
	parsed, keyErr := x509.ParsePKIXPublicKey(publicKey)
	key, keyOK := parsed.(*ecdsa.PublicKey)
	if err != nil || timeErr != nil || enrolled.After(r.now()) || keyErr != nil || !keyOK || key.Curve != elliptic.P256() {
		return authority.Credential{}, ErrUnavailable
	}
	return authority.Credential{Reference: record.Reference, PublicKey: publicKey, Algorithm: -7, Generation: record.Generation, RPID: record.RPID, EnrolledAt: enrolled, Status: record.Status, InternalUV: true, SignCount: record.SignCount}, nil
}

func validateSocketPath(path, anchor string, owner uint32) error {
	if path == "" || filepath.Clean(path) != path || validateParent(filepath.Dir(path), 0o750, owner) != nil || validateAncestors(filepath.Dir(path), anchor, owner) != nil {
		return ErrUnavailable
	}
	info, err := os.Lstat(path)
	if err != nil || info.Mode()&os.ModeSymlink != 0 || info.Mode()&os.ModeSocket == 0 || info.Mode().Perm() != 0o660 {
		return ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner || stat.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func validateRegularPath(path, anchor string, mode os.FileMode, owner uint32) error {
	if path == "" || filepath.Clean(path) != path || validateParent(filepath.Dir(path), 0o755, owner) != nil || validateAncestors(filepath.Dir(path), anchor, owner) != nil {
		return ErrUnavailable
	}
	info, err := os.Lstat(path)
	if err != nil || info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() || info.Mode().Perm() != mode {
		return ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner || stat.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func validateAncestors(start, anchor string, owner uint32) error {
	start, anchor = filepath.Clean(start), filepath.Clean(anchor)
	if anchor == "." || !filepath.IsAbs(anchor) {
		return ErrUnavailable
	}
	for current := start; ; current = filepath.Dir(current) {
		info, err := os.Lstat(current)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm()&0o022 != 0 {
			return ErrUnavailable
		}
		stat, ok := info.Sys().(*syscall.Stat_t)
		if !ok || stat.Uid != owner {
			return ErrUnavailable
		}
		if current == anchor {
			return nil
		}
		parent := filepath.Dir(current)
		if parent == current {
			return ErrUnavailable
		}
	}
}

func validateParent(path string, mode os.FileMode, owner uint32) error {
	info, err := os.Lstat(path)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm() != mode {
		return ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner || info.Mode().Perm()&0o022 != 0 {
		return ErrUnavailable
	}
	return nil
}

func ioReadBounded(file *os.File, limit int) ([]byte, error) {
	info, err := file.Stat()
	if err != nil || info.Size() < 1 || info.Size() > int64(limit) {
		return nil, ErrUnavailable
	}
	payload := make([]byte, info.Size())
	if _, err := file.ReadAt(payload, 0); err != nil {
		return nil, ErrUnavailable
	}
	return payload, nil
}
