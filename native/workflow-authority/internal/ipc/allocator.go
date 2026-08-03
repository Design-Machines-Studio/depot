package ipc

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io"
	"math"
	"os"
	"sync"
	"syscall"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

var (
	ErrBusy       = errors.New("allocation_busy")
	ErrDurability = errors.New("allocation_durability_unavailable")
	ErrConsumed   = errors.New("allocation_already_consumed")
)

type Allocation struct {
	Hello        protocol.AuthorityHello
	ConnectionID string
}

type Allocator interface {
	Allocate(context.Context) (Allocation, error)
	Consume(context.Context, Allocation, string) error
	Close() error
}

type AllocatorConfig struct {
	DaemonBuildSHA256  string
	ScannerBuildSHA256 string
	PolicySHA256       string
	BootID             string
	SessionID          string
	Clock              func() time.Time
	Random             io.Reader
}

type allocatorActive struct {
	Sequence         uint64 `json:"sequence"`
	HelloSHA256      string `json:"hello_sha256"`
	PriorChainDigest string `json:"prior_chain_digest"`
	ConnectionID     string `json:"connection_id"`
}

type allocatorState struct {
	Version          int              `json:"version"`
	Sequence         uint64           `json:"sequence"`
	PriorChainDigest string           `json:"prior_chain_digest"`
	Active           *allocatorActive `json:"active"`
}

type stateStore interface {
	Load() (allocatorState, bool, error)
	Save(allocatorState) error
	Close() error
}

type DurableAllocator struct {
	mu       sync.Mutex
	config   AllocatorConfig
	store    stateStore
	state    allocatorState
	closed   bool
	poisoned bool
}

func NewDurableAllocator(config AllocatorConfig, store stateStore) (*DurableAllocator, error) {
	if store == nil || config.Clock == nil || config.DaemonBuildSHA256 == "" || config.ScannerBuildSHA256 == "" || config.PolicySHA256 == "" || config.BootID == "" || config.SessionID == "" {
		return nil, ErrDurability
	}
	if config.Random == nil {
		config.Random = rand.Reader
	}
	state, found, err := store.Load()
	if err != nil {
		return nil, ErrDurability
	}
	if !found {
		state = allocatorState{Version: 1, PriorChainDigest: protocol.Digest(nil)}
	} else if state.Version != 1 || state.Sequence > math.MaxInt64 || !validDigest(state.PriorChainDigest) || !validActiveState(state) {
		return nil, ErrDurability
	}
	allocator := &DurableAllocator{config: config, store: store, state: state}
	if state.Active != nil {
		allocator.advanceChain("crash_recovery")
		if err := store.Save(allocator.state); err != nil {
			return nil, ErrDurability
		}
	}
	return allocator, nil
}

func (a *DurableAllocator) Allocate(ctx context.Context) (Allocation, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.closed || a.poisoned || ctx.Err() != nil || a.state.Sequence >= math.MaxInt64 {
		return Allocation{}, ErrDurability
	}
	if a.state.Active != nil {
		return Allocation{}, ErrBusy
	}
	nonce := make([]byte, 32)
	connection := make([]byte, 16)
	if _, err := io.ReadFull(a.config.Random, nonce); err != nil {
		return Allocation{}, ErrDurability
	}
	defer zero(nonce)
	if _, err := io.ReadFull(a.config.Random, connection); err != nil {
		return Allocation{}, ErrDurability
	}
	defer zero(connection)
	now := a.config.Clock().UTC().Truncate(time.Second)
	sequence := a.state.Sequence + 1
	hello := protocol.AuthorityHello{
		SchemaVersion: protocol.Version, Protocol: protocol.Name, Type: protocol.AuthorityHelloType,
		DaemonBuildSHA256: a.config.DaemonBuildSHA256, ScannerBuildSHA256: a.config.ScannerBuildSHA256,
		PolicySHA256: a.config.PolicySHA256, BootID: a.config.BootID, SessionID: a.config.SessionID,
		Sequence: sequence, IssuedAt: now.Format(time.RFC3339),
		ExpiresAt:        now.Add(time.Duration(protocol.FrozenAllocationLimits().AllocationTTLSeconds) * time.Second).Format(time.RFC3339),
		PriorChainDigest: a.state.PriorChainDigest, ConnectionNonceSHA256: protocol.Digest(nonce),
		Limits: protocol.FrozenAllocationLimits(),
	}
	helloBytes, err := protocol.AuthorityHelloBytes(hello, now)
	if err != nil {
		return Allocation{}, ErrDurability
	}
	allocation := Allocation{Hello: hello, ConnectionID: "connection-" + hex.EncodeToString(connection)}
	a.state.Sequence = sequence
	a.state.Active = &allocatorActive{Sequence: sequence, HelloSHA256: protocol.Digest(helloBytes), PriorChainDigest: a.state.PriorChainDigest, ConnectionID: allocation.ConnectionID}
	if err := a.store.Save(a.state); err != nil {
		a.poisoned = true
		return Allocation{}, ErrDurability
	}
	return allocation, nil
}

func validActiveState(state allocatorState) bool {
	if state.Active == nil {
		return true
	}
	active := state.Active
	if active.Sequence == 0 || active.Sequence != state.Sequence || active.Sequence > math.MaxInt64 || !validDigest(active.HelloSHA256) || active.PriorChainDigest != state.PriorChainDigest {
		return false
	}
	if len(active.ConnectionID) != len("connection-")+32 || active.ConnectionID[:len("connection-")] != "connection-" {
		return false
	}
	_, err := hex.DecodeString(active.ConnectionID[len("connection-"):])
	return err == nil
}

func validDigest(value string) bool {
	if len(value) != len("sha256:")+64 || value[:len("sha256:")] != "sha256:" {
		return false
	}
	_, err := hex.DecodeString(value[len("sha256:"):])
	return err == nil
}

func (a *DurableAllocator) Consume(ctx context.Context, allocation Allocation, reason string) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.closed || a.poisoned || ctx.Err() != nil || a.state.Active == nil || !validConsumeReason(reason) {
		return ErrConsumed
	}
	active := a.state.Active
	if active.Sequence != allocation.Hello.Sequence || active.ConnectionID != allocation.ConnectionID {
		return ErrConsumed
	}
	a.advanceChain(reason)
	if err := a.store.Save(a.state); err != nil {
		a.poisoned = true
		return ErrDurability
	}
	return nil
}

func validConsumeReason(reason string) bool {
	switch reason {
	case "connection_abandoned", "allocation_deadline_invalid", "hello_write_failed", "proposal_read_failed", "proposal_invalid", "parts_invalid", "binding_invalid", "body_invalid", "reserve_failed", "challenge_write_failed", "consent_read_failed", "consent_invalid", "connection_deadline_clear_failed", "dispatch_ambiguous", "terminal_complete", "crash_recovery":
		return true
	default:
		return false
	}
}

func (a *DurableAllocator) advanceChain(reason string) {
	tombstone := struct {
		Version          int    `json:"version"`
		Sequence         uint64 `json:"sequence"`
		HelloSHA256      string `json:"hello_sha256"`
		PriorChainDigest string `json:"prior_chain_digest"`
		Reason           string `json:"reason"`
	}{1, a.state.Active.Sequence, a.state.Active.HelloSHA256, a.state.PriorChainDigest, reason}
	raw, _ := protocol.CanonicalJSON(tombstone)
	a.state.PriorChainDigest = protocol.Digest(raw)
	a.state.Active = nil
}

func (a *DurableAllocator) Close() error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.closed {
		return nil
	}
	a.closed = true
	return a.store.Close()
}

type DirStateStore struct {
	mu    sync.Mutex
	root  *os.Root
	owner uint32
}

func OpenDirStateStore(path string, owner uint32) (*DirStateStore, error) {
	info, err := os.Lstat(path)
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0o700 {
		return nil, ErrDurability
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != owner {
		return nil, ErrDurability
	}
	root, err := os.OpenRoot(path)
	if err != nil {
		return nil, ErrDurability
	}
	return &DirStateStore{root: root, owner: owner}, nil
}

func (s *DirStateStore) Load() (allocatorState, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, err := s.root.Lstat("allocator-state.json"); errors.Is(err, os.ErrNotExist) {
		return allocatorState{}, false, nil
	} else if err != nil || s.validate("allocator-state.json") != nil {
		return allocatorState{}, false, ErrDurability
	}
	data, err := s.root.ReadFile("allocator-state.json")
	if err != nil {
		return allocatorState{}, false, ErrDurability
	}
	var state allocatorState
	if protocol.DecodeClosed(data, &state) != nil {
		return allocatorState{}, false, ErrDurability
	}
	canonical, err := protocol.CanonicalJSON(state)
	if err != nil || string(canonical) != string(data) {
		return allocatorState{}, false, ErrDurability
	}
	return state, true, nil
}

func (s *DirStateStore) Save(state allocatorState) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	payload, err := protocol.CanonicalJSON(state)
	if err != nil {
		return ErrDurability
	}
	name := "allocator-state.tmp"
	f, err := s.root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_TRUNC|syscall.O_NOFOLLOW, 0o600)
	if err == nil {
		var written int
		written, err = f.Write(payload)
		if err == nil && written != len(payload) {
			err = io.ErrShortWrite
		}
	}
	if err == nil {
		err = f.Sync()
	}
	if f != nil {
		if closeErr := f.Close(); err == nil {
			err = closeErr
		}
	}
	if err == nil {
		err = s.validate(name)
	}
	if err == nil {
		err = s.root.Rename(name, "allocator-state.json")
	}
	dir, dirErr := s.root.Open(".")
	if dirErr == nil {
		dirErr = dir.Sync()
		_ = dir.Close()
	}
	if err != nil || dirErr != nil {
		return ErrDurability
	}
	return nil
}

func (s *DirStateStore) validate(name string) error {
	info, err := s.root.Lstat(name)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0o600 {
		return ErrDurability
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != s.owner || stat.Nlink != 1 {
		return ErrDurability
	}
	return nil
}

func (s *DirStateStore) Close() error { return s.root.Close() }

func zero(value []byte) {
	for index := range value {
		value[index] = 0
	}
}
