// Package platform owns the fixed Linux installation and lifecycle boundary.
package platform

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

const (
	ClientPath            = "/usr/local/bin/workflow-authority"
	AdminPath             = "/usr/local/sbin/workflow-authority-admin"
	DaemonPath            = "/usr/local/libexec/design-machines/workflow-authorityd"
	SocketPath            = "/run/design-machines/workflow-authority/authority.sock"
	TmpfilesPath          = "/usr/lib/tmpfiles.d/workflow-authority.conf"
	PolicyPath            = "/etc/design-machines/workflow-authority/provider-policy.json"
	CredentialPath        = "/etc/design-machines/workflow-authority/credentials/openrouter"
	StatePath             = "/var/lib/design-machines/workflow-authority"
	TrustDirPath          = "/etc/design-machines/workflow-authority/trust"
	PublicTrustPath       = "/etc/design-machines/workflow-authority/trust/authority-public.json"
	PrivateEnrollmentPath = "/var/lib/design-machines/workflow-authority/enrollment-private.json"
	EnrollmentLockPath    = "/var/lib/design-machines/workflow-authority/enrollment.lock"
)

var ErrUnavailable = errors.New("authority_unavailable")

type Paths struct {
	Client, Admin, Daemon, Socket, Policy, Credential, State string
	TrustDir, PublicTrust, PrivateEnrollment, EnrollmentLock string
}

type ServiceController interface {
	StopSocket() error
	StopService() error
	DisableUnits() error
}

type noopService struct{}

func (noopService) StopSocket() error   { return ErrUnavailable }
func (noopService) StopService() error  { return ErrUnavailable }
func (noopService) DisableUnits() error { return ErrUnavailable }

type systemdService struct{}

func (systemdService) run(args ...string) error {
	cmd := exec.Command("/usr/bin/systemctl", args...)
	cmd.Env = []string{"PATH=/usr/sbin:/usr/bin:/sbin:/bin", "LANG=C.UTF-8"}
	cmd.Stdin = nil
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	return cmd.Run()
}
func (s systemdService) StopSocket() error  { return s.run("stop", "workflow-authority.socket") }
func (s systemdService) StopService() error { return s.run("stop", "workflow-authority.service") }
func (s systemdService) DisableUnits() error {
	return s.run("disable", "workflow-authority.socket", "workflow-authority.service")
}

type Linux struct {
	paths    Paths
	euid     int
	rootGID  uint32
	authGID  uint32
	testRoot string
	service  ServiceController
	test     bool
}

// NewLinux has no caller-controlled paths. Production rejects non-Linux hosts.
func NewLinux() (*Linux, error) {
	if runtime.GOOS != "linux" {
		return nil, ErrUnavailable
	}
	group, err := user.LookupGroup("workflow-authority")
	if err != nil {
		return nil, ErrUnavailable
	}
	gid, err := strconv.ParseUint(group.Gid, 10, 32)
	if err != nil {
		return nil, ErrUnavailable
	}
	return &Linux{paths: frozenPaths(""), euid: os.Geteuid(), rootGID: 0, authGID: uint32(gid), service: systemdService{}}, nil
}

// NewTestLinux is the only injected-root seam. It is constructor-only and is
// intentionally unreachable from CLI arguments or environment variables.
func NewTestLinux(root string, euid int, service ServiceController) (*Linux, error) {
	if root == "" || !filepath.IsAbs(root) || filepath.Clean(root) == string(filepath.Separator) {
		return nil, ErrUnavailable
	}
	if service == nil {
		service = noopService{}
	}
	gid := uint32(os.Getegid())
	cleanRoot := filepath.Clean(root)
	return &Linux{paths: frozenPaths(cleanRoot), euid: euid, rootGID: gid, authGID: gid, testRoot: cleanRoot, service: service, test: true}, nil
}

func frozenPaths(root string) Paths {
	join := func(path string) string {
		if root == "" {
			return path
		}
		return filepath.Join(root, strings.TrimPrefix(path, "/"))
	}
	return Paths{
		Client: join(ClientPath), Admin: join(AdminPath), Daemon: join(DaemonPath), Socket: join(SocketPath),
		Policy: join(PolicyPath), Credential: join(CredentialPath), State: join(StatePath), TrustDir: join(TrustDirPath),
		PublicTrust: join(PublicTrustPath), PrivateEnrollment: join(PrivateEnrollmentPath), EnrollmentLock: join(EnrollmentLockPath),
	}
}
func (p *Linux) Paths() Paths { return p.paths }
func (p *Linux) RequireRoot() error {
	if p == nil || (p.test && p.euid != 0) || (!p.test && os.Geteuid() != 0) {
		return ErrUnavailable
	}
	return nil
}

type Status struct {
	SchemaVersion int    `json:"schema_version"`
	Protocol      string `json:"protocol"`
	State         string `json:"state"`
}

func (p *Linux) Status() Status {
	state := "unavailable"
	if p != nil {
		if p.ValidateLayout() == nil {
			if !p.enrollmentPresent() {
				state = "enrollment-required"
			} else if p.check(p.paths.Credential, 0o600, false) == nil {
				state = "ready"
			} else if _, err := os.Lstat(p.paths.Credential); errors.Is(err, os.ErrNotExist) {
				state = "provider-required"
			}
		} else if p.check(p.paths.State, 0o700, true) == nil {
			state = "degraded"
		}
	}
	return Status{1, "workflow-authority-local-status-v1", state}
}

func (p *Linux) StatusJSON() ([]byte, error) { return json.Marshal(p.Status()) }

func (p *Linux) ValidateLayout() error {
	if p == nil {
		return ErrUnavailable
	}
	checks := []struct {
		path string
		mode os.FileMode
		dir  bool
	}{
		{p.paths.Client, 0o755, false}, {p.paths.Admin, 0o750, false}, {p.paths.Daemon, 0o755, false},
		{filepath.Dir(p.paths.Socket), 0o750, true}, {filepath.Dir(p.paths.Credential), 0o700, true},
		{p.paths.Policy, 0o600, false}, {p.paths.State, 0o700, true}, {p.paths.TrustDir, 0o755, true},
	}
	for _, c := range checks {
		if err := p.check(c.path, c.mode, c.dir); err != nil {
			return err
		}
	}
	if _, err := os.Lstat(p.paths.Credential); err == nil {
		if err := p.check(p.paths.Credential, 0o600, false); err != nil {
			return err
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return ErrUnavailable
	}
	enrollment := []struct {
		path string
		mode os.FileMode
	}{{p.paths.PublicTrust, 0o644}, {p.paths.PrivateEnrollment, 0o600}, {p.paths.EnrollmentLock, 0o600}}
	present := 0
	for _, record := range enrollment {
		if _, err := os.Lstat(record.path); err == nil {
			present++
			if err := p.check(record.path, record.mode, false); err != nil {
				return err
			}
		} else if !errors.Is(err, os.ErrNotExist) {
			return ErrUnavailable
		}
	}
	if present != 0 && present != len(enrollment) {
		return ErrUnavailable
	}
	return nil
}

func (p *Linux) enrollmentPresent() bool {
	return p != nil && p.check(p.paths.PublicTrust, 0o644, false) == nil && p.check(p.paths.PrivateEnrollment, 0o600, false) == nil && p.check(p.paths.EnrollmentLock, 0o600, false) == nil
}

func (p *Linux) check(path string, mode os.FileMode, dir bool) error {
	if err := p.checkAncestors(path); err != nil {
		return err
	}
	info, err := os.Lstat(path)
	if err != nil || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm() != mode || info.IsDir() != dir || (!dir && !info.Mode().IsRegular()) {
		return ErrUnavailable
	}
	st, ok := info.Sys().(*syscall.Stat_t)
	wantUID := uint32(0)
	if p.test {
		wantUID = uint32(os.Geteuid())
	}
	wantGID := p.rootGID
	if filepath.Clean(path) == filepath.Clean(filepath.Dir(p.paths.Socket)) {
		wantGID = p.authGID
	}
	if !ok || st.Uid != wantUID || st.Gid != wantGID || (!dir && st.Nlink != 1) {
		return ErrUnavailable
	}
	return nil
}

func (p *Linux) checkAncestors(path string) error {
	stop := string(filepath.Separator)
	if p.test {
		// The injected root is the trust anchor in tests; host temp-directory
		// ancestry is outside the emulated installation boundary.
		stop = p.testRoot
	}
	wantUID := uint32(0)
	wantGID := p.rootGID
	if p.test {
		wantUID = uint32(os.Geteuid())
	}
	for parent := filepath.Dir(filepath.Clean(path)); parent != stop && parent != string(filepath.Separator); parent = filepath.Dir(parent) {
		info, err := os.Lstat(parent)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm()&0o022 != 0 {
			return ErrUnavailable
		}
		st, ok := info.Sys().(*syscall.Stat_t)
		if !ok || st.Uid != wantUID || st.Gid != wantGID {
			return ErrUnavailable
		}
	}
	return nil
}

func (p *Linux) ProvisionOpenRouter(secret []byte) error {
	if p.RequireRoot() != nil || len(secret) == 0 || len(secret) > 4096 || bytes.IndexByte(secret, 0) >= 0 {
		return ErrUnavailable
	}
	parent := filepath.Dir(p.paths.Credential)
	if err := p.check(parent, 0o700, true); err != nil {
		return err
	}
	root, err := os.OpenRoot(parent)
	if err != nil {
		return ErrUnavailable
	}
	defer root.Close()
	if err := rejectRootEntry(root, "openrouter"); err != nil {
		return err
	}
	tmp := ".openrouter.rotate"
	f, err := root.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, 0o600)
	if err != nil {
		return recovery("provision", "remove "+filepath.Join(parent, tmp)+" after verifying it is not a symlink", err)
	}
	committed := false
	defer func() {
		_ = f.Close()
		if !committed {
			_ = root.Remove(tmp)
		}
	}()
	if err = f.Chmod(0o600); err == nil {
		_, err = f.Write(secret)
	}
	if err == nil {
		err = f.Sync()
	}
	if err == nil {
		err = validateCredentialFile(f, p.expectedOwner(), p.rootGID)
	}
	if closeErr := f.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = root.Rename(tmp, "openrouter")
	}
	if err == nil {
		err = syncRoot(root)
	}
	if err != nil {
		return recovery("provision", "run status; if credential is absent retry provision-openrouter", err)
	}
	committed = true
	return nil
}

func (p *Linux) expectedOwner() uint32 {
	if p.test {
		return uint32(os.Geteuid())
	}
	return 0
}
func validateCredentialFile(f *os.File, owner, group uint32) error {
	i, e := f.Stat()
	if e != nil || !i.Mode().IsRegular() || i.Mode().Perm() != 0o600 {
		return ErrUnavailable
	}
	s, ok := i.Sys().(*syscall.Stat_t)
	if !ok || s.Uid != owner || s.Gid != group || s.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func rejectExistingLink(path string) error {
	i, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil || !i.Mode().IsRegular() || i.Mode()&os.ModeSymlink != 0 {
		return ErrUnavailable
	}
	st, ok := i.Sys().(*syscall.Stat_t)
	if !ok || st.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func rejectRootEntry(root *os.Root, name string) error {
	i, err := root.Lstat(name)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil || !i.Mode().IsRegular() || i.Mode()&os.ModeSymlink != 0 {
		return ErrUnavailable
	}
	st, ok := i.Sys().(*syscall.Stat_t)
	if !ok || st.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func (p *Linux) RevokeOpenRouter() error {
	if p.RequireRoot() != nil {
		return ErrUnavailable
	}
	if err := p.service.StopSocket(); err != nil {
		return recovery("revoke", "stop workflow-authority.socket, then retry revoke-openrouter", err)
	}
	if err := p.service.StopService(); err != nil {
		return recovery("revoke", "keep workflow-authority.socket stopped; stop workflow-authority.service, then retry revoke-openrouter", err)
	}
	parent := filepath.Dir(p.paths.Credential)
	if err := p.check(parent, 0o700, true); err != nil {
		return err
	}
	root, err := os.OpenRoot(parent)
	if err != nil {
		return ErrUnavailable
	}
	defer root.Close()
	if err := rejectRootEntry(root, "openrouter"); err != nil {
		return err
	}
	if err := root.Remove("openrouter"); err != nil && !errors.Is(err, os.ErrNotExist) {
		return recovery("revoke", "verify the credential path and retry revoke-openrouter", err)
	}
	if err := syncRoot(root); err != nil {
		return recovery("revoke", "keep the socket stopped and retry revoke-openrouter", err)
	}
	return p.writeTombstone("credential-revoked")
}

func (p *Linux) Disable() error {
	if p.RequireRoot() != nil {
		return ErrUnavailable
	}
	if err := p.service.StopSocket(); err != nil {
		return recovery("disable", "stop workflow-authority.socket manually, then retry disable", err)
	}
	if err := p.service.StopService(); err != nil {
		return recovery("disable", "keep workflow-authority.socket stopped; stop workflow-authority.service, then retry disable", err)
	}
	if err := p.service.DisableUnits(); err != nil {
		return recovery("disable", "disable workflow-authority.socket and workflow-authority.service, then retry disable", err)
	}
	return p.writeTombstone("service-disabled")
}

func (p *Linux) writeTombstone(name string) error {
	if err := p.check(p.paths.State, 0o700, true); err != nil {
		return err
	}
	path := filepath.Join(p.paths.State, name+".tombstone")
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, 0o600)
	if errors.Is(err, os.ErrExist) {
		return validateTombstone(path, p.expectedOwner(), p.rootGID)
	}
	if err != nil {
		return recovery(name, "preserve state and retry the command", err)
	}
	if err = f.Chmod(0o600); err == nil {
		_, err = f.Write([]byte("workflow-authority lifecycle tombstone\n"))
	}
	if err == nil {
		err = f.Sync()
	}
	if err == nil {
		err = validateTombstoneFile(f, p.expectedOwner(), p.rootGID)
	}
	if closeErr := f.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = syncDir(p.paths.State)
	}
	return err
}
func validateTombstone(path string, owner, group uint32) error {
	i, e := os.Lstat(path)
	if e != nil || !i.Mode().IsRegular() || i.Mode().Perm() != 0o600 {
		return ErrUnavailable
	}
	s, ok := i.Sys().(*syscall.Stat_t)
	if !ok || s.Uid != owner || s.Gid != group || s.Nlink != 1 {
		return ErrUnavailable
	}
	b, e := os.ReadFile(path)
	if e != nil || !bytes.Equal(b, []byte("workflow-authority lifecycle tombstone\n")) {
		return ErrUnavailable
	}
	return nil
}

func validateTombstoneFile(f *os.File, owner, group uint32) error {
	i, err := f.Stat()
	if err != nil || !i.Mode().IsRegular() || i.Mode().Perm() != 0o600 {
		return ErrUnavailable
	}
	st, ok := i.Sys().(*syscall.Stat_t)
	if !ok || st.Uid != owner || st.Gid != group || st.Nlink != 1 {
		return ErrUnavailable
	}
	return nil
}

func (p *Linux) UninstallPlan() ([]string, error) {
	if p.RequireRoot() != nil {
		return nil, ErrUnavailable
	}
	paths := []string{p.paths.Client, p.paths.Admin, p.paths.Daemon, p.paths.Socket, p.paths.Policy, p.paths.Credential}
	for _, path := range paths {
		if path == "" || path == "/" || !filepath.IsAbs(path) {
			return nil, ErrUnavailable
		}
	}
	return []string{
		"systemctl stop workflow-authority.socket workflow-authority.service",
		"systemctl is-active --quiet workflow-authority.socket workflow-authority.service must report inactive before removal",
		"systemctl disable workflow-authority.socket workflow-authority.service",
		"remove exactly: " + strings.Join(paths, ", "),
		"remove exactly: /etc/systemd/system/workflow-authority.socket, /etc/systemd/system/workflow-authority.service, /etc/systemd/system/workflow-authority-runtime.service",
		"remove exactly: " + TmpfilesPath,
		"rmdir exactly if empty: /run/design-machines/workflow-authority",
		"systemctl daemon-reload",
		"after verifying no members or files depend on it: groupdel workflow-authority",
		"preserve forensic state by default: " + p.paths.State,
		"preserve enrollment history for reversible recovery by default: " + p.paths.PublicTrust,
	}, nil
}

func syncDir(path string) error {
	d, e := os.Open(path)
	if e != nil {
		return e
	}
	defer d.Close()
	return d.Sync()
}
func syncRoot(root *os.Root) error {
	d, e := root.Open(".")
	if e != nil {
		return e
	}
	defer d.Close()
	return d.Sync()
}
func recovery(op, action string, err error) error {
	return fmt.Errorf("%s failed: %w; recovery: %s", op, err, action)
}

type TerminalIdentity struct{ Device, Inode uint64 }
type Terminal struct {
	file        *os.File
	identity    TerminalIdentity
	openCurrent func() (*os.File, error)
	identify    func(*os.File) (TerminalIdentity, error)
}

func OpenTerminal() (*Terminal, error) {
	f, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return nil, ErrUnavailable
	}
	id, err := terminalIdentity(f)
	if err != nil {
		_ = f.Close()
		return nil, err
	}
	return &Terminal{file: f, identity: id, openCurrent: func() (*os.File, error) { return os.OpenFile("/dev/tty", os.O_RDWR, 0) }, identify: terminalIdentity}, nil
}
func terminalIdentity(f *os.File) (TerminalIdentity, error) {
	i, e := f.Stat()
	if e != nil || i.Mode()&os.ModeCharDevice == 0 || runtime.GOOS != "linux" {
		return TerminalIdentity{}, ErrUnavailable
	}
	var term syscall.Termios
	if _, _, errno := syscall.Syscall6(syscall.SYS_IOCTL, f.Fd(), 0x5401, uintptr(unsafePointer(&term)), 0, 0, 0); errno != 0 {
		return TerminalIdentity{}, ErrUnavailable
	}
	s, ok := i.Sys().(*syscall.Stat_t)
	if !ok {
		return TerminalIdentity{}, ErrUnavailable
	}
	return TerminalIdentity{uint64(s.Dev), uint64(s.Ino)}, nil
}
func (t *Terminal) Stable() error {
	if t.identify == nil {
		return ErrUnavailable
	}
	id, e := t.identify(t.file)
	if e != nil || id != t.identity {
		return ErrUnavailable
	}
	if t.openCurrent == nil {
		return ErrUnavailable
	}
	current, e := t.openCurrent()
	if e != nil {
		return ErrUnavailable
	}
	defer current.Close()
	fresh, e := t.identify(current)
	if e != nil || fresh != t.identity {
		return ErrUnavailable
	}
	return nil
}
func (t *Terminal) MatchesInput(input io.Reader) error {
	f, ok := input.(*os.File)
	if !ok {
		return ErrUnavailable
	}
	if t.identify == nil {
		return ErrUnavailable
	}
	id, err := t.identify(f)
	if err != nil || id != t.identity {
		return ErrUnavailable
	}
	return t.Stable()
}
func (t *Terminal) Write(p []byte) (int, error) {
	if t.Stable() != nil {
		return 0, ErrUnavailable
	}
	return t.file.Write(p)
}
func (t *Terminal) ReadLine() (string, error) {
	if t.Stable() != nil {
		return "", ErrUnavailable
	}
	b, e := t.readMutableLine(4096)
	if e != nil {
		return "", ErrUnavailable
	}
	s := string(b)
	zeroCapacity(b)
	if t.Stable() != nil {
		return "", ErrUnavailable
	}
	return s, nil
}
func (t *Terminal) ReadSecret(prompt string) (line []byte, err error) {
	if t.Stable() != nil {
		return nil, ErrUnavailable
	}
	if _, e := io.WriteString(t.file, prompt); e != nil {
		return nil, ErrUnavailable
	}
	// Linux TCGETS/TCSETS. No shell, child process, argv, environment, or temp file sees the bytes.
	if runtime.GOOS != "linux" {
		return nil, ErrUnavailable
	}
	var term syscall.Termios
	if _, _, e := syscall.Syscall6(syscall.SYS_IOCTL, t.file.Fd(), 0x5401, uintptr(unsafePointer(&term)), 0, 0, 0); e != 0 {
		return nil, ErrUnavailable
	}
	original := term
	term.Lflag &^= syscall.ECHO
	if _, _, e := syscall.Syscall6(syscall.SYS_IOCTL, t.file.Fd(), 0x5402, uintptr(unsafePointer(&term)), 0, 0, 0); e != 0 {
		return nil, ErrUnavailable
	}
	defer func() {
		_, _, restoreErr := syscall.Syscall6(syscall.SYS_IOCTL, t.file.Fd(), 0x5402, uintptr(unsafePointer(&original)), 0, 0, 0)
		if restoreErr != 0 {
			zeroCapacity(line)
			line = nil
			err = ErrUnavailable
		}
	}()
	line, readErr := t.readMutableLine(4096)
	_, _ = io.WriteString(t.file, "\n")
	if readErr != nil || t.Stable() != nil {
		zeroCapacity(line)
		return nil, ErrUnavailable
	}
	for len(line) > 0 && (line[len(line)-1] == '\r' || line[len(line)-1] == '\n') {
		line = line[:len(line)-1]
	}
	return line, nil
}
func (t *Terminal) readMutableLine(limit int) ([]byte, error) {
	out := make([]byte, 0, limit+1)
	one := []byte{0}
	for len(out) <= limit {
		n, e := t.file.Read(one)
		if n == 1 {
			out = append(out, one[0])
			one[0] = 0
			if out[len(out)-1] == '\n' {
				return out, nil
			}
		}
		if e != nil {
			zeroCapacity(out)
			return nil, ErrUnavailable
		}
	}
	zeroCapacity(out)
	return nil, ErrUnavailable
}
func (t *Terminal) Close() error { return t.file.Close() }

// unsafePointer is isolated so ordinary lifecycle code cannot accidentally use
// unsafe conversions. The syscall operates only on a stack Termios value.
func unsafePointer(value *syscall.Termios) unsafe.Pointer { return unsafe.Pointer(value) }
func zeroBytes(value []byte) {
	for i := range value {
		value[i] = 0
	}
}
func zeroCapacity(value []byte) {
	if value != nil {
		zeroBytes(value[:cap(value)])
	}
}
