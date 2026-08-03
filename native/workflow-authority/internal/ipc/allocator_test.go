package ipc

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/protocol"
)

type memoryStateStore struct {
	state  allocatorState
	fail   bool
	closed bool
}

func (s *memoryStateStore) Load() (allocatorState, error) { return s.state, nil }
func (s *memoryStateStore) Save(state allocatorState) error {
	s.state = state
	if s.fail {
		return ErrDurability
	}
	return nil
}
func (s *memoryStateStore) Close() error { s.closed = true; return nil }

func allocatorConfig(now time.Time) AllocatorConfig {
	digest := protocol.Digest([]byte("fixture"))
	return AllocatorConfig{DaemonBuildSHA256: digest, ScannerBuildSHA256: digest, PolicySHA256: digest, BootID: "boot-01", SessionID: "session-01", Clock: func() time.Time { return now }, Random: &repeatReader{value: 7}}
}

type repeatReader struct{ value byte }

func (r *repeatReader) Read(target []byte) (int, error) {
	for index := range target {
		target[index] = r.value
		r.value++
	}
	return len(target), nil
}

func TestAllocatorConsumesEverySequenceAndRejectsConcurrency(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	store := &memoryStateStore{}
	allocator, err := NewDurableAllocator(allocatorConfig(now), store)
	if err != nil {
		t.Fatal(err)
	}
	first, err := allocator.Allocate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := allocator.Allocate(context.Background()); !errors.Is(err, ErrBusy) {
		t.Fatalf("second allocation = %v", err)
	}
	if err := allocator.Consume(context.Background(), first, "terminal_complete"); err != nil {
		t.Fatal(err)
	}
	second, err := allocator.Allocate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if second.Hello.Sequence != first.Hello.Sequence+1 || second.Hello.PriorChainDigest == first.Hello.PriorChainDigest {
		t.Fatal("sequence or chain was reused")
	}
	if err := allocator.Consume(context.Background(), first, "replay"); !errors.Is(err, ErrConsumed) {
		t.Fatalf("replay consume = %v", err)
	}
}

func TestAllocatorCrashRecoveryTombstonesActiveAllocation(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	store := &memoryStateStore{}
	first, _ := NewDurableAllocator(allocatorConfig(now), store)
	allocation, err := first.Allocate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	recovered, err := NewDurableAllocator(allocatorConfig(now.Add(time.Second)), store)
	if err != nil {
		t.Fatal(err)
	}
	next, err := recovered.Allocate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if next.Hello.Sequence != allocation.Hello.Sequence+1 || next.Hello.PriorChainDigest == allocation.Hello.PriorChainDigest {
		t.Fatal("crash recovery reused active allocation")
	}
}

func TestAllocatorAmbiguousSaveNeverRollsBackSequence(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	store := &memoryStateStore{fail: true}
	allocator, err := NewDurableAllocator(allocatorConfig(now), store)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := allocator.Allocate(context.Background()); !errors.Is(err, ErrDurability) {
		t.Fatalf("allocate = %v", err)
	}
	if _, err := allocator.Allocate(context.Background()); !errors.Is(err, ErrDurability) {
		t.Fatalf("ambiguous allocation was reused: %v", err)
	}
}

func TestAllocatorRecoveryRejectsInconsistentActiveState(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	mutations := map[string]func(*allocatorState){
		"sequence mismatch":      func(state *allocatorState) { state.Active.Sequence++ },
		"prior chain mismatch":   func(state *allocatorState) { state.Active.PriorChainDigest = protocol.Digest([]byte("other-chain")) },
		"invalid hello digest":   func(state *allocatorState) { state.Active.HelloSHA256 = "sha256:invalid" },
		"invalid connection":     func(state *allocatorState) { state.Active.ConnectionID = "connection-invalid" },
		"populated zero version": func(state *allocatorState) { state.Version = 0 },
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			store := &memoryStateStore{}
			allocator, err := NewDurableAllocator(allocatorConfig(now), store)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := allocator.Allocate(context.Background()); err != nil {
				t.Fatal(err)
			}
			corrupt := store.state
			active := *corrupt.Active
			corrupt.Active = &active
			mutate(&corrupt)
			store.state = corrupt
			if _, err := NewDurableAllocator(allocatorConfig(now), store); !errors.Is(err, ErrDurability) {
				t.Fatalf("corrupt recovery = %v", err)
			}
		})
	}
}

func TestAllocatorFailedConsumePoisonsProcessUntilRecovery(t *testing.T) {
	now := time.Date(2026, 8, 4, 1, 2, 3, 0, time.UTC)
	store := &memoryStateStore{}
	allocator, err := NewDurableAllocator(allocatorConfig(now), store)
	if err != nil {
		t.Fatal(err)
	}
	allocation, err := allocator.Allocate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	store.fail = true
	if err := allocator.Consume(context.Background(), allocation, "terminal_complete"); !errors.Is(err, ErrDurability) {
		t.Fatalf("consume = %v", err)
	}
	if _, err := allocator.Allocate(context.Background()); !errors.Is(err, ErrDurability) {
		t.Fatalf("poisoned allocator issued authority: %v", err)
	}
}

func TestDirStateStorePersistsCanonicalStateAndRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	if err := os.Chmod(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	store, err := OpenDirStateStore(dir, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	state := allocatorState{Version: 1, Sequence: 4, PriorChainDigest: protocol.Digest(nil)}
	if err := store.Save(state); err != nil {
		t.Fatal(err)
	}
	loaded, err := store.Load()
	if err != nil || loaded.Sequence != 4 {
		t.Fatalf("load = %#v, %v", loaded, err)
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(filepath.Join(dir, "allocator-state.json")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("outside", filepath.Join(dir, "allocator-state.json")); err != nil {
		t.Fatal(err)
	}
	store, err = OpenDirStateStore(dir, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Load(); !errors.Is(err, ErrDurability) {
		t.Fatalf("symlink load = %v", err)
	}
}
