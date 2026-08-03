package provider

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"syscall"

	"designmachines.dev/workflow-authority/internal/protocol"
)

const ProductionCredentialPath = "/etc/design-machines/workflow-authority/credentials/openrouter"
const productionRootPath = "/etc/design-machines/workflow-authority"

type Credential struct {
	bytes   []byte
	fixture bool
	locked  bool
}

func (c *Credential) Bytes() []byte { return c.bytes }
func (c *Credential) Fixture() bool { return c.fixture }
func (c *Credential) Destroy() {
	if c == nil {
		return
	}
	if c.locked {
		_ = syscall.Munlock(c.bytes)
	}
	zero(c.bytes)
	c.bytes = nil
}

type CredentialReader interface {
	Read(context.Context) (*Credential, error)
}

func ReadProductionPolicy(ctx context.Context, owner uint32) ([]byte, string, error) {
	if ctx.Err() != nil || owner != 0 {
		return nil, "", ErrStartup
	}
	root, err := openProductionRoot(owner)
	if err != nil {
		return nil, "", err
	}
	defer root.Close()
	f, err := root.OpenFile("provider-policy.json", os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, "", ErrStartup
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return nil, "", ErrStartup
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 || stat.Uid != owner || stat.Nlink != 1 {
		return nil, "", ErrStartup
	}
	data, err := io.ReadAll(io.LimitReader(f, 1<<20))
	if err != nil || len(data) == 0 || !json.Valid(data) {
		zero(data)
		return nil, "", ErrStartup
	}
	return data, protocol.Digest(data), nil
}

type FileCredentialReader struct {
	Path        string
	FixtureMode bool
	Owner       uint32
}

func (r FileCredentialReader) Read(ctx context.Context) (*Credential, error) {
	if ctx.Err() != nil || r.Path == "" || (!r.FixtureMode && r.Path != ProductionCredentialPath) {
		return nil, ErrStartup
	}
	var f *os.File
	var err error
	if !r.FixtureMode {
		root, rootErr := openProductionRoot(r.Owner)
		if rootErr != nil {
			return nil, ErrStartup
		}
		defer root.Close()
		info, statErr := root.Lstat("credentials")
		if statErr != nil || !info.IsDir() || info.Mode().Perm() != 0o700 || info.Mode()&os.ModeSymlink != 0 || !ownedBy(info, r.Owner) {
			return nil, ErrStartup
		}
		f, err = root.OpenFile("credentials/openrouter", os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	} else {
		f, err = os.OpenFile(r.Path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	}
	if err != nil {
		return nil, ErrStartup
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return nil, ErrStartup
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || stat.Nlink != 1 || (!r.FixtureMode && (stat.Uid != r.Owner || info.Mode().Perm() != 0o600)) {
		return nil, ErrStartup
	}
	data, err := io.ReadAll(io.LimitReader(f, 4097))
	if err != nil || len(data) == 0 || len(data) > 4096 {
		zero(data)
		return nil, ErrStartup
	}
	for len(data) > 0 && (data[len(data)-1] == '\n' || data[len(data)-1] == '\r') {
		data = data[:len(data)-1]
	}
	if len(data) == 0 {
		return nil, ErrStartup
	}
	locked := syscall.Mlock(data) == nil
	return &Credential{bytes: data, fixture: r.FixtureMode, locked: locked}, nil
}

func openProductionRoot(owner uint32) (*os.Root, error) {
	root, err := os.OpenRoot(productionRootPath)
	if err != nil {
		return nil, ErrStartup
	}
	f, err := root.Open(".")
	if err != nil {
		root.Close()
		return nil, ErrStartup
	}
	info, statErr := f.Stat()
	_ = f.Close()
	if statErr != nil || !info.IsDir() || info.Mode().Perm() != 0o700 || !ownedBy(info, owner) {
		root.Close()
		return nil, ErrStartup
	}
	return root, nil
}

func ownedBy(info os.FileInfo, owner uint32) bool {
	stat, ok := info.Sys().(*syscall.Stat_t)
	return ok && stat.Uid == owner
}

// RotateCredential performs a durable replace; it never truncates the active key.
func RotateCredential(path string, next []byte, owner uint32) error {
	if path != ProductionCredentialPath || owner != 0 || len(next) == 0 || len(next) > 4096 {
		return ErrStartup
	}
	root, err := openProductionRoot(owner)
	if err != nil {
		return ErrStartup
	}
	defer root.Close()
	info, err := root.Lstat("credentials")
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0o700 || !ownedBy(info, owner) {
		return ErrStartup
	}
	tmp, err := root.OpenFile("credentials/.openrouter.rotate", os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, 0o600)
	if err != nil {
		return ErrStartup
	}
	ok := false
	defer func() {
		tmp.Close()
		if !ok {
			_ = root.Remove("credentials/.openrouter.rotate")
		}
	}()
	if err = tmp.Chmod(0o600); err == nil {
		_, err = tmp.Write(next)
	}
	if err == nil {
		err = tmp.Sync()
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = root.Rename("credentials/.openrouter.rotate", "credentials/openrouter")
	}
	if err == nil {
		var d *os.File
		d, err = root.Open("credentials")
		if err == nil {
			err = d.Sync()
			_ = d.Close()
		}
	}
	if err != nil {
		return ErrStartup
	}
	ok = true
	return nil
}

func RevokeCredential(path string, owner uint32) error {
	if path != ProductionCredentialPath || owner != 0 {
		return ErrStartup
	}
	root, err := openProductionRoot(owner)
	if err != nil {
		return ErrStartup
	}
	defer root.Close()
	if err := root.Remove("credentials/openrouter"); err != nil && !errors.Is(err, os.ErrNotExist) {
		return ErrStartup
	}
	d, err := root.Open("credentials")
	if err != nil {
		return ErrStartup
	}
	defer d.Close()
	if d.Sync() != nil {
		return ErrStartup
	}
	return nil
}
