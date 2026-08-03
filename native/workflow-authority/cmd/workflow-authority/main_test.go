package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"strings"
	"syscall"
	"testing"

	"designmachines.dev/workflow-authority/internal/client"
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

type fakeProviderClient struct {
	status    []byte
	statusErr error
}

func (f fakeProviderClient) Status(context.Context) ([]byte, error) { return f.status, f.statusErr }
func (fakeProviderClient) Dispatch(context.Context, client.DispatchOptions, io.Reader, io.Reader) (client.Result, error) {
	return client.Result{}, client.ErrUnavailable
}

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

func TestExactProviderCLIAndStatus(t *testing.T) {
	args := []string{"--repository", "owner/repo", "--run-id", "run-1", "--lane", "lane-1", "--candidate", "candidate-1", "--workload", "workload-1", "--nonce", "nonce-1", "--model", "openai/gpt-5", "--fallback-model", "", "--system-fd", "4", "--user-fd", "5", "--response-fd", "3"}
	options, err := parseDispatch(args)
	if err != nil || options.Repository != "owner/repo" || options.Model != "openai/gpt-5" {
		t.Fatalf("valid CLI rejected: %+v %v", options, err)
	}
	withoutFallback := append(append([]string(nil), args[:14]...), args[16:]...)
	if options, err := parseDispatch(withoutFallback); err != nil || options.FallbackModel != "" {
		t.Fatalf("optional fallback rejected: %+v %v", options, err)
	}
	for name, mutate := range map[string]func([]string) []string{
		"missing":      func(v []string) []string { return append(v[:2], v[4:]...) },
		"unknown":      func(v []string) []string { v[0] = "--socket"; return v },
		"duplicate":    func(v []string) []string { v[2] = "--repository"; return v },
		"alternate-fd": func(v []string) []string { v[len(v)-1] = "9"; return v },
	} {
		t.Run(name, func(t *testing.T) {
			copyArgs := append([]string(nil), args...)
			if _, err := parseDispatch(mutate(copyArgs)); err == nil {
				t.Fatal("invalid closed CLI accepted")
			}
		})
	}
	var stdout, stderr bytes.Buffer
	status := []byte(`{"m1_acceptance":true,"production_ready":true,"protocol":"workflow-authority-provider-dispatch-v1","schema_version":1}`)
	if code := runProvider(fakeProviderClient{status: status}, "provider-transport-status", nil, &stdout, &stderr); code != 0 || stdout.String() != string(status)+"\n" || stderr.Len() != 0 {
		t.Fatalf("status code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestProviderEnvironmentIsScrubbed(t *testing.T) {
	for _, name := range []string{"HOST_AUTHORITY_BROKER", "DM_VERIFICATION_SUBSTRATE", "OPENROUTER_API_KEY", "HTTPS_PROXY"} {
		t.Setenv(name, "attacker-controlled")
	}
	scrubProviderEnvironment()
	for _, name := range []string{"HOST_AUTHORITY_BROKER", "DM_VERIFICATION_SUBSTRATE", "OPENROUTER_API_KEY", "HTTPS_PROXY"} {
		if _, exists := os.LookupEnv(name); exists {
			t.Fatalf("sensitive environment survived: %s", name)
		}
	}
}
