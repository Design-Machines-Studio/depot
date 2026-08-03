//go:build linux

// Package runtime composes the fixed Linux production authority daemon.
package runtime

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/ipc"
	"designmachines.dev/workflow-authority/internal/platform"
	"designmachines.dev/workflow-authority/internal/protocol"
	"designmachines.dev/workflow-authority/internal/provider"
)

const (
	bootIDPath = "/proc/sys/kernel/random/boot_id"
	groupPath  = "/etc/group"
	passwdPath = "/etc/passwd"
)

var ErrUnavailable = errors.New("runtime_unavailable")

type dependencies struct {
	euid           func() int
	loadEnrollment func(context.Context) (*enrollment.Credential, error)
	fido           authority.SelectorAwareFIDO
	providerCred   provider.CredentialReader
	loadPolicy     func(context.Context) ([]byte, string, error)
	openWAL        func() (authority.WAL, error)
	openState      func() (*ipc.DirStateStore, error)
	bootID         func() (string, error)
	allowedUIDs    func() (map[uint32]struct{}, error)
	activate       func() (net.Listener, error)
	random         io.Reader
	now            func() time.Time
	daemonDigest   func() (string, error)
}

type composition struct {
	server     *ipc.Server
	listener   net.Listener
	credential *enrollment.Credential
	policy     []byte
}

func productionDependencies() dependencies {
	store := enrollment.NewStore()
	reader := provider.FileCredentialReader{Path: provider.ProductionCredentialPath, Owner: 0}
	return dependencies{
		euid:           os.Geteuid,
		loadEnrollment: store.LoadActive,
		fido:           selectorAdapter(),
		providerCred:   reader,
		loadPolicy: func(ctx context.Context) ([]byte, string, error) {
			return provider.ReadProductionPolicy(ctx, 0)
		},
		openWAL:     openProductionWAL,
		openState:   openProductionState,
		bootID:      readBootID,
		allowedUIDs: readAllowedUIDs,
		activate: func() (net.Listener, error) {
			return ipc.ActivatedListener(3, platform.SocketPath)
		},
		random: rand.Reader,
		now:    func() time.Time { return time.Now().UTC() },
		daemonDigest: func() (string, error) {
			current, err := os.Executable()
			if err != nil {
				return "", ErrUnavailable
			}
			return executableDigest(platform.DaemonPath, current, 0)
		},
	}
}

func selectorAdapter() authority.SelectorAwareFIDO {
	adapter, ok := authority.NewFIDOAdapter().(authority.SelectorAwareFIDO)
	if !ok {
		return nil
	}
	return adapter
}

// ServeProduction accepts no caller configuration. Its only variable input is
// cancellation; all authority-bearing paths and limits are compiled constants.
func ServeProduction(ctx context.Context) error {
	composition, err := build(ctx, productionDependencies())
	if err != nil {
		return ErrUnavailable
	}
	defer composition.destroy()
	return composition.server.Serve(ctx, composition.listener)
}

func build(ctx context.Context, d dependencies) (*composition, error) {
	if ctx.Err() != nil || d.euid == nil || d.euid() != 0 || d.fido == nil || d.providerCred == nil || d.loadEnrollment == nil || d.loadPolicy == nil || d.openWAL == nil || d.openState == nil || d.bootID == nil || d.allowedUIDs == nil || d.activate == nil || d.random == nil || d.now == nil || d.daemonDigest == nil {
		return nil, ErrUnavailable
	}
	daemonDigest, err := d.daemonDigest()
	if err != nil || !validDigest(daemonDigest) {
		return nil, ErrUnavailable
	}
	enrolled, err := d.loadEnrollment(ctx)
	if err != nil || enrolled == nil {
		return nil, ErrUnavailable
	}
	fail := func() (*composition, error) { enrolled.Destroy(); return nil, ErrUnavailable }
	credential, err := authority.CredentialFromEnrollment(*enrolled)
	if err != nil {
		return fail()
	}
	ready := d.fido.ReadinessFor(ctx, enrolled.DeviceSelector)
	if !ready.Production || !ready.InternalUV || ready.Adapter != "libfido2" || ready.Version != authority.FIDO2Version {
		zero(credential.ID)
		return fail()
	}
	providerSecret, err := d.providerCred.Read(ctx)
	if err != nil || providerSecret == nil {
		zero(credential.ID)
		return fail()
	}
	providerSecret.Destroy()
	policy, policyDigest, err := d.loadPolicy(ctx)
	if err != nil || len(policy) == 0 || protocol.Digest(policy) != policyDigest || !validDigest(policyDigest) || !validDigest(provider.ScannerBuildDigest) || (provider.BuiltinScanner{}).Scan(ctx, [][]byte{[]byte("workflow-authority readiness")}, policy) != nil {
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	bootID, err := d.bootID()
	validatedBootID, bootErr := parseBootID([]byte(bootID))
	if err != nil || bootErr != nil || validatedBootID != bootID {
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	sessionID, err := randomID(d.random, 32, "session-")
	if err != nil {
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	uids, err := d.allowedUIDs()
	if err != nil || len(uids) == 0 {
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	wal, err := d.openWAL()
	if err != nil {
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	manager, err := authority.NewManager(authority.Config{BootID: bootID, SessionID: sessionID, AllowedUIDs: uids, MaxOperations: 128, MaxBytes: 64 << 20, MaxConcurrent: 1, Credential: credential}, d.fido, wal, nil)
	if err != nil {
		_ = wal.Close()
		zero(policy)
		zero(credential.ID)
		return fail()
	}
	state, err := d.openState()
	if err != nil {
		_ = manager.Shutdown(context.Background())
		zero(policy)
		return fail()
	}
	allocator, err := ipc.NewDurableAllocator(ipc.AllocatorConfig{DaemonBuildSHA256: daemonDigest, ScannerBuildSHA256: provider.ScannerBuildDigest, PolicySHA256: policyDigest, BootID: bootID, SessionID: sessionID, Clock: d.now, Random: d.random}, state)
	if err != nil {
		_ = state.Close()
		_ = manager.Shutdown(context.Background())
		zero(policy)
		return fail()
	}
	dispatcher := &provider.Dispatcher{Scanner: provider.BuiltinScanner{}, Policy: policy, Credentials: d.providerCred, Transport: provider.ProductionTransport(), Authority: manager, Clock: d.now}
	server := &ipc.Server{Allocator: allocator, Peers: ipc.LinuxPeerAuthenticator{AllowedUIDs: uids}, Guard: ipc.GuardLinuxUnixConn, Manager: manager, Dispatcher: dispatcher, Clock: d.now, QueueDepth: 1}
	listener, err := d.activate()
	if err != nil {
		_ = allocator.Close()
		_ = manager.Shutdown(context.Background())
		zero(policy)
		return fail()
	}
	return &composition{server: server, listener: listener, credential: enrolled, policy: policy}, nil
}

func (c *composition) destroy() {
	if c == nil {
		return
	}
	if c.listener != nil {
		_ = c.listener.Close()
	}
	if c.credential != nil {
		c.credential.Destroy()
	}
	zero(c.policy)
	c.policy = nil
}

func executableDigest(installed, current string, owner uint32) (string, error) {
	return executableDigestAt(installed, current, owner, "/")
}

func executableDigestAt(installed, current string, owner uint32, anchor string) (string, error) {
	if filepath.Clean(installed) != installed || !filepath.IsAbs(installed) || validateAncestors(filepath.Dir(installed), owner, anchor) != nil {
		return "", ErrUnavailable
	}
	info, err := os.Lstat(installed)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0o755 || info.Mode()&os.ModeSymlink != 0 || info.Size() < 1 || info.Size() > 128<<20 {
		return "", ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner || stat.Nlink != 1 {
		return "", ErrUnavailable
	}
	currentInfo, err := os.Stat(current)
	if err != nil || !os.SameFile(info, currentInfo) {
		return "", ErrUnavailable
	}
	f, err := os.OpenFile(installed, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return "", ErrUnavailable
	}
	h := sha256.New()
	opened, statErr := f.Stat()
	if statErr != nil || !os.SameFile(info, opened) {
		_ = f.Close()
		return "", ErrUnavailable
	}
	_, copyErr := io.Copy(h, f)
	closeErr := f.Close()
	if copyErr != nil || closeErr != nil {
		return "", ErrUnavailable
	}
	return "sha256:" + hex.EncodeToString(h.Sum(nil)), nil
}

func validateAncestors(start string, owner uint32, anchor string) error {
	anchor = filepath.Clean(anchor)
	if !filepath.IsAbs(anchor) {
		return ErrUnavailable
	}
	for current := filepath.Clean(start); ; current = filepath.Dir(current) {
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
		if current == "/" {
			return ErrUnavailable
		}
	}
}

func readBootID() (string, error) {
	raw, err := readRootFile(bootIDPath, 0o444, 0, 128)
	if err != nil {
		return "", ErrUnavailable
	}
	defer zero(raw)
	return parseBootID(raw)
}

func parseBootID(raw []byte) (string, error) {
	value := strings.TrimSpace(string(raw))
	parts := strings.Split(value, "-")
	if len(parts) != 5 || len(parts[0]) != 8 || len(parts[1]) != 4 || len(parts[2]) != 4 || len(parts[3]) != 4 || len(parts[4]) != 12 {
		return "", ErrUnavailable
	}
	if _, err := hex.DecodeString(strings.Join(parts, "")); err != nil || strings.ToLower(value) != value {
		return "", ErrUnavailable
	}
	return value, nil
}

func readAllowedUIDs() (map[uint32]struct{}, error) {
	groups, err := readRootFile(groupPath, 0o644, 0, 1<<20)
	if err != nil {
		return nil, err
	}
	defer zero(groups)
	passwords, err := readRootFile(passwdPath, 0o644, 0, 1<<20)
	if err != nil {
		return nil, err
	}
	defer zero(passwords)
	return parseAllowedUIDs(groups, passwords)
}

func parseAllowedUIDs(groups, passwords []byte) (map[uint32]struct{}, error) {
	var gid uint64
	members := map[string]struct{}{}
	found := false
	for scanner := bufio.NewScanner(strings.NewReader(string(groups))); scanner.Scan(); {
		fields := strings.Split(scanner.Text(), ":")
		if len(fields) != 4 || fields[0] != "workflow-authority" {
			continue
		}
		if found {
			return nil, ErrUnavailable
		}
		parsed, err := strconv.ParseUint(fields[2], 10, 32)
		if err != nil {
			return nil, ErrUnavailable
		}
		gid, found = parsed, true
		if fields[3] != "" {
			for _, member := range strings.Split(fields[3], ",") {
				if member == "" {
					return nil, ErrUnavailable
				}
				members[member] = struct{}{}
			}
		}
	}
	if !found {
		return nil, ErrUnavailable
	}
	uids := map[uint32]struct{}{}
	seenNames := map[string]struct{}{}
	for scanner := bufio.NewScanner(strings.NewReader(string(passwords))); scanner.Scan(); {
		fields := strings.Split(scanner.Text(), ":")
		if len(fields) != 7 {
			return nil, ErrUnavailable
		}
		uid, e1 := strconv.ParseUint(fields[2], 10, 32)
		primary, e2 := strconv.ParseUint(fields[3], 10, 32)
		if e1 != nil || e2 != nil {
			return nil, ErrUnavailable
		}
		if _, duplicate := seenNames[fields[0]]; duplicate {
			return nil, ErrUnavailable
		}
		seenNames[fields[0]] = struct{}{}
		_, supplementary := members[fields[0]]
		if supplementary || primary == gid {
			uids[uint32(uid)] = struct{}{}
			delete(members, fields[0])
		}
	}
	if len(members) != 0 || len(uids) == 0 {
		return nil, ErrUnavailable
	}
	return uids, nil
}

func readRootFile(path string, mode os.FileMode, owner uint32, limit int64) ([]byte, error) {
	if validateAncestors(filepath.Dir(path), owner, "/") != nil {
		return nil, ErrUnavailable
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != mode || info.Mode()&os.ModeSymlink != 0 {
		return nil, ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner || stat.Nlink != 1 {
		return nil, ErrUnavailable
	}
	f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, ErrUnavailable
	}
	defer f.Close()
	raw, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil || len(raw) == 0 || int64(len(raw)) > limit {
		zero(raw)
		return nil, ErrUnavailable
	}
	return raw, nil
}

func openProductionWAL() (authority.WAL, error) {
	if validateAncestors(filepath.Dir(platform.StatePath), 0, "/") != nil {
		return nil, ErrUnavailable
	}
	return authority.OpenDirWAL(platform.StatePath, 0)
}

func openProductionState() (*ipc.DirStateStore, error) {
	if validateAncestors(filepath.Dir(platform.StatePath), 0, "/") != nil {
		return nil, ErrUnavailable
	}
	return ipc.OpenDirStateStore(platform.StatePath, 0)
}

func randomID(source io.Reader, bytes int, prefix string) (string, error) {
	value := make([]byte, bytes)
	if _, err := io.ReadFull(source, value); err != nil {
		zero(value)
		return "", ErrUnavailable
	}
	defer zero(value)
	return prefix + hex.EncodeToString(value), nil
}

func validDigest(value string) bool {
	if len(value) != 71 || !strings.HasPrefix(value, "sha256:") {
		return false
	}
	_, err := hex.DecodeString(value[7:])
	return err == nil
}

func zero(value []byte) {
	for i := range value {
		value[i] = 0
	}
}
