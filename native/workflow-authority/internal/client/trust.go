package client

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/x509"
	"encoding/base64"
	"os"
	"path/filepath"
	"syscall"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/protocol"
)

func (r *Runner) loadTrust() (authority.Credential, error) {
	if r == nil || r.now == nil || r.trustPath == "" {
		return authority.Credential{}, ErrUnavailable
	}
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
	var trust enrollment.PublicTrust
	if protocol.DecodeClosed(raw, &trust) != nil {
		return authority.Credential{}, ErrUnavailable
	}
	record, err := trust.ActiveRecord()
	if err != nil || record.EnrolledAt.After(r.now()) {
		return authority.Credential{}, ErrUnavailable
	}
	publicKey, err := base64.RawURLEncoding.Strict().DecodeString(record.PublicKey)
	parsed, keyErr := x509.ParsePKIXPublicKey(publicKey)
	key, keyOK := parsed.(*ecdsa.PublicKey)
	if err != nil || keyErr != nil || !keyOK || key.Curve != elliptic.P256() {
		return authority.Credential{}, ErrUnavailable
	}
	return authority.Credential{Reference: record.Reference, PublicKey: publicKey, Algorithm: record.Algorithm, Generation: record.Generation, RPID: record.RPID, EnrolledAt: record.EnrolledAt, Status: "active", InternalUV: record.InternalUV}, nil
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
