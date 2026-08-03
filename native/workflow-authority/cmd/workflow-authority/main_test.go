package main

import (
	"bytes"
	"errors"
	"io"
	"os"
	"strings"
	"syscall"
	"testing"
)

type fakePlatform struct {
	status                   []byte
	statusErr, rootErr       error
	provisionErr, revokeErr  error
	disableErr, uninstallErr error
	plan                     []string
	provisioned, revoked     int
	disabled                 int
}

func (f *fakePlatform) StatusJSON() ([]byte, error)      { return f.status, f.statusErr }
func (f *fakePlatform) RequireRoot() error               { return f.rootErr }
func (f *fakePlatform) ProvisionOpenRouter([]byte) error { f.provisioned++; return f.provisionErr }
func (f *fakePlatform) RevokeOpenRouter() error          { f.revoked++; return f.revokeErr }
func (f *fakePlatform) Disable() error                   { f.disabled++; return f.disableErr }
func (f *fakePlatform) UninstallPlan() ([]string, error) { return f.plan, f.uninstallErr }

type fakeTerminal struct {
	matchErr, stableErr, readErr error
	secret                       []byte
}

func (f *fakeTerminal) Stable() error                { return f.stableErr }
func (f *fakeTerminal) MatchesInput(io.Reader) error { return f.matchErr }
func (f *fakeTerminal) ReadSecret(string) ([]byte, error) {
	return append([]byte(nil), f.secret...), f.readErr
}
func (f *fakeTerminal) Close() error { return nil }

type errorWriter struct{}

func (errorWriter) Write([]byte) (int, error) { return 0, errors.New("write failed") }

func withFakes(t *testing.T, p localPlatform, terminal adminTerminal) {
	t.Helper()
	oldPlatform, oldTerminal := openLinuxPlatform, openAdminTerminal
	openLinuxPlatform = func() (localPlatform, error) { return p, nil }
	openAdminTerminal = func() (adminTerminal, error) { return terminal, nil }
	t.Cleanup(func() { openLinuxPlatform, openAdminTerminal = oldPlatform, oldTerminal })
}

func TestBasenameAndExitClassification(t *testing.T) {
	var stderr bytes.Buffer
	if code := run([]string{"workflow-authority", "disable"}, strings.NewReader(""), io.Discard, &stderr); code != exitDeclined {
		t.Fatalf("non-admin basename code=%d", code)
	}
	if code := run([]string{"workflow-authority-admin", "unknown"}, strings.NewReader(""), io.Discard, io.Discard); code != exitUsage {
		t.Fatalf("unknown command code=%d", code)
	}
}

func TestStatusAndAdminOutputErrorsFailClosed(t *testing.T) {
	p := &fakePlatform{status: []byte(`{"schema_version":1}`), plan: []string{"one", "two"}}
	terminal := &fakeTerminal{}
	withFakes(t, p, terminal)
	if code := run([]string{"workflow-authority", "status"}, strings.NewReader(""), errorWriter{}, io.Discard); code != exitUnavailable {
		t.Fatalf("status write code=%d", code)
	}
	if code := run([]string{"workflow-authority-admin", "revoke-openrouter"}, strings.NewReader(""), errorWriter{}, io.Discard); code != exitUnavailable || p.revoked != 1 {
		t.Fatalf("admin write code=%d revoked=%d", code, p.revoked)
	}
	if code := run([]string{"workflow-authority-admin", "uninstall-plan"}, strings.NewReader(""), errorWriter{}, io.Discard); code != exitUnavailable {
		t.Fatalf("uninstall write code=%d", code)
	}
}

func TestStatusAndAdminSuccessKeepStdoutSeparated(t *testing.T) {
	p := &fakePlatform{status: []byte(`{"schema_version":1}`)}
	terminal := &fakeTerminal{}
	withFakes(t, p, terminal)
	var stdout, stderr bytes.Buffer
	if code := run([]string{"workflow-authority", "status"}, strings.NewReader(""), &stdout, &stderr); code != 0 || stdout.String() != "{\"schema_version\":1}\n" || stderr.Len() != 0 {
		t.Fatalf("status code/output separation: code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	stdout.Reset()
	if code := run([]string{"workflow-authority-admin", "disable"}, strings.NewReader(""), &stdout, &stderr); code != 0 || !strings.Contains(stdout.String(), `"state":"disabled"`) || stderr.Len() != 0 {
		t.Fatalf("admin code/output separation: code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestRedirectedAdminInputRejectedBeforeMutation(t *testing.T) {
	p := &fakePlatform{}
	terminal := &fakeTerminal{matchErr: errors.New("redirected")}
	withFakes(t, p, terminal)
	var stdout bytes.Buffer
	code := run([]string{"workflow-authority-admin", "provision-openrouter"}, strings.NewReader("literal-secret"), &stdout, io.Discard)
	if code != exitDeclined || p.provisioned != 0 || stdout.Len() != 0 {
		t.Fatalf("code=%d provisioned=%d stdout=%q", code, p.provisioned, stdout.String())
	}
}

func TestResponseChannelRequiresAnonymousPipe(t *testing.T) {
	regular, err := os.CreateTemp(t.TempDir(), "fd3")
	if err != nil {
		t.Fatal(err)
	}
	defer regular.Close()
	if validateResponsePipe(regular) == nil {
		t.Fatal("regular response file accepted")
	}
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	defer w.Close()
	if validateResponsePipe(r) == nil {
		t.Fatal("read-only anonymous pipe accepted as response sink")
	}
	if err := validateResponsePipe(w); err != nil {
		t.Fatalf("anonymous response pipe rejected: %v", err)
	}
	namedPath := t.TempDir() + "/named-fifo"
	if err := syscall.Mkfifo(namedPath, 0o600); err != nil {
		t.Fatal(err)
	}
	named, err := os.OpenFile(namedPath, os.O_RDWR|syscall.O_NONBLOCK, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer named.Close()
	if validateResponsePipe(named) == nil {
		t.Fatal("filesystem-backed named FIFO accepted")
	}
}
