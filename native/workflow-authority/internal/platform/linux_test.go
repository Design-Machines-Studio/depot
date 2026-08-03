package platform

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

type fakeService struct {
	stopErr, serviceErr, disableErr   error
	stopped, serviceStopped, disabled int
	order                             []string
}

func (s *fakeService) StopSocket() error {
	s.stopped++
	s.order = append(s.order, "socket")
	return s.stopErr
}
func (s *fakeService) StopService() error {
	s.serviceStopped++
	s.order = append(s.order, "service")
	return s.serviceErr
}
func (s *fakeService) DisableUnits() error {
	s.disabled++
	s.order = append(s.order, "disable")
	return s.disableErr
}

func testPlatform(t *testing.T, root bool) (*Linux, *fakeService) {
	t.Helper()
	dir := t.TempDir()
	service := &fakeService{}
	uid := 1
	if root {
		uid = 0
	}
	p, err := NewTestLinux(dir, uid, service)
	if err != nil {
		t.Fatal(err)
	}
	paths := p.Paths()
	for path, mode := range map[string]os.FileMode{
		filepath.Dir(paths.Client): 0o755, filepath.Dir(paths.Admin): 0o755, filepath.Dir(paths.Daemon): 0o755,
		filepath.Dir(paths.Socket): 0o750, filepath.Dir(paths.Credential): 0o700, paths.State: 0o700,
	} {
		if err := os.MkdirAll(path, mode); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(path, mode); err != nil {
			t.Fatal(err)
		}
	}
	for path, mode := range map[string]os.FileMode{paths.Client: 0o755, paths.Admin: 0o750, paths.Daemon: 0o755, paths.Policy: 0o600} {
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("fixture\n"), mode); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(path, mode); err != nil {
			t.Fatal(err)
		}
	}
	return p, service
}

func TestFrozenPathsAndNoBroadRoot(t *testing.T) {
	p, _ := testPlatform(t, true)
	got := p.Paths()
	want := []string{ClientPath, AdminPath, DaemonPath, SocketPath, PolicyPath, CredentialPath, StatePath}
	have := []string{got.Client, got.Admin, got.Daemon, got.Socket, got.Policy, got.Credential, got.State}
	root := filepath.Dir(filepath.Dir(filepath.Dir(got.Client)))
	for i := range want {
		if !strings.HasSuffix(have[i], want[i]) || have[i] == root || have[i] == "/" {
			t.Fatalf("unsafe path %q", have[i])
		}
	}
	if _, err := NewTestLinux("/", 0, nil); !errors.Is(err, ErrUnavailable) {
		t.Fatal("broad test root accepted")
	}
}

func TestLayoutModesTypesAndLinks(t *testing.T) {
	p, _ := testPlatform(t, true)
	if err := p.ValidateLayout(); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(p.paths.Policy, 0o644); err != nil {
		t.Fatal(err)
	}
	if p.ValidateLayout() == nil {
		t.Fatal("weak policy mode accepted")
	}
	if err := os.Chmod(p.paths.Policy, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(p.paths.Client); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("/bin/false", p.paths.Client); err != nil {
		t.Fatal(err)
	}
	if p.ValidateLayout() == nil {
		t.Fatal("symlink accepted")
	}
}

func TestProvisionRevokeDisableAndRecovery(t *testing.T) {
	p, s := testPlatform(t, true)
	secret := []byte("openrouter-test-value")
	if err := p.ProvisionOpenRouter(secret); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(p.paths.Credential)
	if err != nil || string(data) != string(secret) {
		t.Fatal("credential mismatch")
	}
	info, _ := os.Stat(p.paths.Credential)
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("mode %o", info.Mode().Perm())
	}
	if p.Status().State != "ready" {
		t.Fatalf("status %s", p.Status().State)
	}
	if err := p.RevokeOpenRouter(); err != nil {
		t.Fatal(err)
	}
	if strings.Join(s.order[:2], ",") != "socket,service" {
		t.Fatal("revoke did not stop socket then service")
	}
	if _, err := os.Stat(p.paths.Credential); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("credential remains")
	}
	if err := p.RevokeOpenRouter(); err != nil {
		t.Fatal("revoke not idempotent")
	}
	if err := p.Disable(); err != nil {
		t.Fatal(err)
	}
	if err := p.Disable(); err != nil {
		t.Fatal("disable not idempotent")
	}
	if _, err := os.Stat(filepath.Join(p.paths.State, "service-disabled.tombstone")); err != nil {
		t.Fatal(err)
	}
	s.stopErr = errors.New("fixture stop failure")
	if err := p.RevokeOpenRouter(); err == nil || !strings.Contains(err.Error(), "stop workflow-authority.socket") {
		t.Fatalf("missing recovery: %v", err)
	}
}

func TestServiceStopFailurePreservesCredential(t *testing.T) {
	p, s := testPlatform(t, true)
	if err := p.ProvisionOpenRouter([]byte("secret")); err != nil {
		t.Fatal(err)
	}
	s.serviceErr = errors.New("busy")
	if err := p.RevokeOpenRouter(); err == nil || !strings.Contains(err.Error(), "stop workflow-authority.service") {
		t.Fatalf("bad recovery %v", err)
	}
	if _, err := os.Stat(p.paths.Credential); err != nil {
		t.Fatal("credential removed before service drained")
	}
	if strings.Join(s.order, ",") != "socket,service" {
		t.Fatalf("bad order %v", s.order)
	}
}

func TestMutationRequiresRootAndRejectsLinkAttacks(t *testing.T) {
	p, _ := testPlatform(t, false)
	if !errors.Is(p.ProvisionOpenRouter([]byte("x")), ErrUnavailable) {
		t.Fatal("non-root provision accepted")
	}
	if !errors.Is(p.Disable(), ErrUnavailable) {
		t.Fatal("non-root disable accepted")
	}
	root, _ := testPlatform(t, true)
	target := filepath.Join(t.TempDir(), "target")
	if err := os.WriteFile(target, []byte("keep"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, root.paths.Credential); err != nil {
		t.Fatal(err)
	}
	if root.ProvisionOpenRouter([]byte("secret")) == nil {
		t.Fatal("symlink provision accepted")
	}
	if root.RevokeOpenRouter() == nil {
		t.Fatal("symlink revoke accepted")
	}
	got, _ := os.ReadFile(target)
	if string(got) != "keep" {
		t.Fatal("link target changed")
	}
}

func TestUninstallPlanPreservesStateAndIsExact(t *testing.T) {
	p, _ := testPlatform(t, true)
	plan, err := p.UninstallPlan()
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(plan, "\n")
	for _, path := range []string{p.paths.Client, p.paths.Admin, p.paths.Daemon, p.paths.Socket, p.paths.Policy, p.paths.Credential, p.paths.State} {
		if !strings.Contains(joined, path) {
			t.Fatalf("missing %s", path)
		}
	}
	if strings.Contains(joined, "rm -rf") {
		t.Fatal("recursive uninstall plan")
	}
	if !strings.Contains(joined, "preserve forensic state") {
		t.Fatal("state preservation absent")
	}
}

func TestStatusIsContentFree(t *testing.T) {
	p, _ := testPlatform(t, true)
	raw, err := p.StatusJSON()
	if err != nil {
		t.Fatal(err)
	}
	for _, forbidden := range []string{"credential", "openrouter", "policy_sha256", "authorized", "production_ready"} {
		if strings.Contains(string(raw), forbidden) {
			t.Fatalf("status leaks %q: %s", forbidden, raw)
		}
	}
}

func TestMissingTTYAndRegularFileRejected(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "not-a-tty")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if _, err := terminalIdentity(f); !errors.Is(err, ErrUnavailable) {
		t.Fatal("redirected regular input accepted as tty")
	}
}

func TestChangedTerminalIdentityRejected(t *testing.T) {
	first, err := os.OpenFile("/dev/null", os.O_RDWR, 0)
	if err != nil {
		t.Skip(err)
	}
	defer first.Close()
	second, err := os.OpenFile("/dev/zero", os.O_RDWR, 0)
	if err != nil {
		t.Skip(err)
	}
	defer second.Close()
	changed, err := terminalIdentity(second)
	if err != nil {
		t.Skip(err)
	}
	terminal := &Terminal{file: first, identity: changed, openCurrent: func() (*os.File, error) { return os.OpenFile("/dev/null", os.O_RDWR, 0) }}
	if !errors.Is(terminal.Stable(), ErrUnavailable) {
		t.Fatal("changed terminal identity accepted")
	}
}

func TestCredentialParentSwapRejected(t *testing.T) {
	p, _ := testPlatform(t, true)
	parent := filepath.Dir(p.paths.Credential)
	moved := parent + ".moved"
	if err := os.Rename(parent, moved); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(moved, parent); err != nil {
		t.Fatal(err)
	}
	if p.ProvisionOpenRouter([]byte("secret")) == nil {
		t.Fatal("symlinked parent accepted")
	}
	if _, err := os.Stat(filepath.Join(moved, "openrouter")); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("swapped parent received credential")
	}
}

func TestSystemdUnitsFreezeExecutableEnvironmentAndBounds(t *testing.T) {
	_, file, _, _ := runtime.Caller(0)
	root := filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", "packaging", "linux"))
	socket, err := os.ReadFile(filepath.Join(root, "workflow-authority.socket"))
	if err != nil {
		t.Fatal(err)
	}
	service, err := os.ReadFile(filepath.Join(root, "workflow-authority.service"))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"ListenStream=" + SocketPath, "SocketUser=root", "SocketGroup=workflow-authority", "SocketMode=0660", "DirectoryMode=0750", "RemoveOnStop=yes", "Service=workflow-authority.service"} {
		if !strings.Contains(string(socket), want) {
			t.Errorf("socket missing %s", want)
		}
	}
	for _, want := range []string{"ExecStart=" + DaemonPath, "User=root", "Group=root", "UMask=0077", "PrivateTmp=yes", "NoNewPrivileges=yes", "CapabilityBoundingSet=", "AmbientCapabilities=", "ProtectSystem=strict", "UnsetEnvironment=HTTPS_PROXY HTTP_PROXY ALL_PROXY NO_PROXY https_proxy http_proxy all_proxy no_proxy OPENROUTER_API_KEY", "DevicePolicy=closed", "DeviceAllow=/dev/hidraw0 rw", "SystemCallFilter=@system-service @network-io", "SystemCallErrorNumber=EPERM", "LimitNOFILE=256", "TasksMax=32", "MemoryMax=256M", "LimitCORE=0", "TimeoutStopSec=15s"} {
		if !strings.Contains(string(service), want) {
			t.Errorf("service missing %s", want)
		}
	}
	for _, forbidden := range []string{"EnvironmentFile=", "$", "%E", "/bin/sh", "bash -c"} {
		if strings.Contains(string(service), forbidden) {
			t.Errorf("service contains override surface %s", forbidden)
		}
	}
}

func TestExistingTombstoneMustBeExact(t *testing.T) {
	p, _ := testPlatform(t, true)
	path := filepath.Join(p.paths.State, "service-disabled.tombstone")
	if err := os.WriteFile(path, []byte("forged\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if p.Disable() == nil {
		t.Fatal("forged tombstone accepted")
	}
}

func TestHardLinkRejected(t *testing.T) {
	p, _ := testPlatform(t, true)
	if err := p.ProvisionOpenRouter([]byte("secret")); err != nil {
		t.Fatal(err)
	}
	if err := os.Link(p.paths.Credential, filepath.Join(filepath.Dir(p.paths.Credential), "copy")); err != nil {
		t.Fatal(err)
	}
	if p.ValidateLayout() == nil {
		t.Fatal("hard-linked credential accepted")
	}
	if p.RevokeOpenRouter() == nil {
		t.Fatal("hard-linked credential revoked without inspection")
	}
}
