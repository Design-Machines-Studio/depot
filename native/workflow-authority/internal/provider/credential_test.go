package provider

import (
	"os"
	"testing"
)

func TestOpenProductionRootAtRequiresPackagedModeAndOwner(t *testing.T) {
	path := t.TempDir()
	owner := uint32(os.Geteuid())

	if err := os.Chmod(path, 0o755); err != nil {
		t.Fatal(err)
	}
	root, err := openProductionRootAt(path, owner)
	if err != nil {
		t.Fatalf("root-owned 0755 directory rejected: %v", err)
	}
	if err := root.Close(); err != nil {
		t.Fatal(err)
	}

	for name, mode := range map[string]os.FileMode{
		"private":        0o700,
		"group-writable": 0o775,
		"other-writable": 0o757,
		"sticky":         os.ModeSticky | 0o755,
	} {
		t.Run(name, func(t *testing.T) {
			if err := os.Chmod(path, mode); err != nil {
				t.Fatal(err)
			}
			if root, err := openProductionRootAt(path, owner); err == nil {
				_ = root.Close()
				t.Fatalf("mode %04o accepted", mode)
			}
		})
	}

	if err := os.Chmod(path, 0o755); err != nil {
		t.Fatal(err)
	}
	wrongOwner := owner + 1
	if root, err := openProductionRootAt(path, wrongOwner); err == nil {
		_ = root.Close()
		t.Fatal("wrong ownership accepted")
	}
}
