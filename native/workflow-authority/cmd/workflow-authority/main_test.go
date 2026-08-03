package main

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"

	"designmachines.dev/workflow-authority/internal/client"
	"designmachines.dev/workflow-authority/internal/enrollment"
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
	stableCalls                  int
	stableAt                     map[int]error
}

func (f *fakeTerminal) Stable() error {
	f.stableCalls++
	if err := f.stableAt[f.stableCalls]; err != nil {
		return err
	}
	return f.stableErr
}
func (f *fakeTerminal) MatchesInput(io.Reader) error { return f.matchErr }
func (f *fakeTerminal) ReadSecret(string) ([]byte, error) {
	return append([]byte(nil), f.secret...), f.readErr
}
func (f *fakeTerminal) Close() error { return nil }

type errorWriter struct{}

func (errorWriter) Write([]byte) (int, error) { return 0, errors.New("write failed") }

type fakeProviderClient struct {
	status       []byte
	statusErr    error
	result       client.Result
	dispatchErr  error
	options      client.DispatchOptions
	system, user []byte
}

func (f *fakeProviderClient) Status(context.Context) ([]byte, error) { return f.status, f.statusErr }
func (f *fakeProviderClient) Dispatch(_ context.Context, options client.DispatchOptions, system, user io.Reader) (client.Result, error) {
	f.options = options
	f.system, _ = io.ReadAll(system)
	f.user, _ = io.ReadAll(user)
	return f.result, f.dispatchErr
}

func withFakes(t *testing.T, p localPlatform, terminal adminTerminal) {
	t.Helper()
	oldPlatform, oldTerminal := openLinuxPlatform, openAdminTerminal
	openLinuxPlatform = func() (localPlatform, error) { return p, nil }
	openAdminTerminal = func() (adminTerminal, error) { return terminal, nil }
	t.Cleanup(func() { openLinuxPlatform, openAdminTerminal = oldPlatform, oldTerminal })
}

type fakeEnrollmentStore struct {
	active                          *enrollment.Credential
	trust                           enrollment.PublicTrust
	loadErr, commitErr, recoveryErr error
	enrolled, rotated, revoked      int
	recovered, publicRecovered      int
	revokedGeneration               uint64
}

func (f *fakeEnrollmentStore) Enroll(_ context.Context, _ enrollment.Credential) error {
	f.enrolled++
	return f.commitErr
}
func (f *fakeEnrollmentStore) Rotate(_ context.Context, _ enrollment.Credential) error {
	f.rotated++
	return f.commitErr
}
func (f *fakeEnrollmentStore) Revoke(_ context.Context, generation uint64, _ time.Time) error {
	f.revoked++
	f.revokedGeneration = generation
	return f.commitErr
}
func (f *fakeEnrollmentStore) Recover(_ context.Context, _ enrollment.Credential) error {
	f.recovered++
	return f.commitErr
}
func (f *fakeEnrollmentStore) RecoverPartial(context.Context) error {
	f.publicRecovered++
	return f.recoveryErr
}
func (f *fakeEnrollmentStore) LoadActive(context.Context) (*enrollment.Credential, error) {
	if f.loadErr != nil || f.active == nil {
		return nil, f.loadErr
	}
	copy := *f.active
	copy.ID = append([]byte(nil), f.active.ID...)
	return &copy, nil
}
func (f *fakeEnrollmentStore) LoadTrust(context.Context) (enrollment.PublicTrust, error) {
	if f.loadErr == nil && f.active == nil && len(f.trust.Credentials) == 0 {
		return enrollment.PublicTrust{}, os.ErrNotExist
	}
	return f.trust, f.loadErr
}

type fakeFIDOEnroller struct {
	request enrollment.Request
	result  enrollment.Credential
	err     error
	calls   int
}

func (f *fakeFIDOEnroller) Enroll(_ context.Context, request enrollment.Request) (enrollment.Credential, error) {
	f.calls++
	f.request = enrollment.Request{Generation: request.Generation, ExcludeCredentialID: append([]byte(nil), request.ExcludeCredentialID...), DeviceSelector: request.DeviceSelector}
	if f.err != nil {
		return enrollment.Credential{}, f.err
	}
	if len(f.result.ID) > 0 {
		result := f.result
		result.ID = append([]byte(nil), f.result.ID...)
		result.PublicKey = append([]byte(nil), f.result.PublicKey...)
		result.AAGUID = append([]byte(nil), f.result.AAGUID...)
		result.Generation = request.Generation
		result.DeviceSelector = "sha256:" + strings.Repeat("b", 64)
		return result, nil
	}
	return enrollment.Credential{ID: []byte("new-credential-id"), Generation: request.Generation}, nil
}

func withEnrollmentFakes(t *testing.T, store enrollmentLifecycle, enroller enrollment.Enroller) {
	t.Helper()
	oldStore, oldEnroller, oldNow := openEnrollmentStore, openFIDOEnroller, enrollmentNow
	openEnrollmentStore = func() enrollmentLifecycle { return store }
	openFIDOEnroller = func() enrollment.Enroller { return enroller }
	enrollmentNow = func() time.Time { return time.Unix(1_900_000_000, 0).UTC() }
	t.Cleanup(func() { openEnrollmentStore, openFIDOEnroller, enrollmentNow = oldStore, oldEnroller, oldNow })
}

func TestFIDOEnrollmentLifecycleUsesOnlyFixedOrStoredSelection(t *testing.T) {
	p := &fakePlatform{}
	terminal := &fakeTerminal{}
	store := &fakeEnrollmentStore{}
	enroller := &fakeFIDOEnroller{}
	withFakes(t, p, terminal)
	withEnrollmentFakes(t, store, enroller)
	var stdout, stderr bytes.Buffer
	if code := run([]string{"workflow-authority-admin", "enroll-fido"}, strings.NewReader(""), &stdout, &stderr); code != 0 || store.enrolled != 1 {
		t.Fatalf("enroll code=%d calls=%d stdout=%q stderr=%q", code, store.enrolled, stdout.String(), stderr.String())
	}
	if enroller.request.Generation != 1 || enroller.request.DeviceSelector != "" || len(enroller.request.ExcludeCredentialID) != 0 {
		t.Fatalf("initial enrollment accepted caller selection: %#v", enroller.request)
	}

	store.active = &enrollment.Credential{ID: []byte("active-secret-id"), Generation: 7, DeviceSelector: "sha256:" + strings.Repeat("a", 64)}
	stdout.Reset()
	stderr.Reset()
	if code := run([]string{"workflow-authority-admin", "rotate-fido"}, strings.NewReader(""), &stdout, &stderr); code != 0 || store.rotated != 1 {
		t.Fatalf("rotate code=%d calls=%d stderr=%q", code, store.rotated, stderr.String())
	}
	if enroller.request.Generation != 8 || enroller.request.DeviceSelector != store.active.DeviceSelector || string(enroller.request.ExcludeCredentialID) != "active-secret-id" {
		t.Fatalf("rotation did not bind stored enrollment: %#v", enroller.request)
	}

	store.active = nil
	store.trust = enrollment.PublicTrust{Protocol: enrollment.Protocol, Credentials: []enrollment.PublicCredential{{Generation: 7}, {Generation: 11}}}
	stdout.Reset()
	stderr.Reset()
	if code := run([]string{"workflow-authority-admin", "recover-fido"}, strings.NewReader(""), &stdout, &stderr); code != 0 || store.recovered != 1 {
		t.Fatalf("recover code=%d calls=%d stderr=%q", code, store.recovered, stderr.String())
	}
	if enroller.request.Generation != 12 || enroller.request.DeviceSelector != "" || len(enroller.request.ExcludeCredentialID) != 0 {
		t.Fatalf("recovery accepted caller selection: %#v", enroller.request)
	}
}

func TestFIDOEnrollmentFailsClosedBeforeCommit(t *testing.T) {
	p := &fakePlatform{}
	terminal := &fakeTerminal{}
	store := &fakeEnrollmentStore{}
	enroller := &fakeFIDOEnroller{err: enrollment.ErrConflict}
	withFakes(t, p, terminal)
	withEnrollmentFakes(t, store, enroller)
	var stdout, stderr bytes.Buffer
	if code := run([]string{"workflow-authority-admin", "enroll-fido"}, strings.NewReader(""), &stdout, &stderr); code != exitUnavailable || store.enrolled != 0 || stdout.Len() != 0 || !strings.Contains(stderr.String(), "exactly one") {
		t.Fatalf("ambiguous device did not fail closed: code=%d commits=%d stdout=%q stderr=%q", code, store.enrolled, stdout.String(), stderr.String())
	}

	enroller.err = nil
	terminal.stableAt = map[int]error{terminal.stableCalls + 2: errors.New("changed")}
	stdout.Reset()
	stderr.Reset()
	if code := run([]string{"workflow-authority-admin", "enroll-fido"}, strings.NewReader(""), &stdout, &stderr); code != exitDeclined || store.enrolled != 0 || stdout.Len() != 0 {
		t.Fatalf("changed terminal committed enrollment: code=%d commits=%d stdout=%q stderr=%q calls=%d", code, store.enrolled, stdout.String(), stderr.String(), terminal.stableCalls)
	}
}

func TestExistingOrCorruptEnrollmentFailsBeforeFIDODeviceAccess(t *testing.T) {
	p := &fakePlatform{}
	terminal := &fakeTerminal{}
	enroller := &fakeFIDOEnroller{}
	store := &fakeEnrollmentStore{trust: enrollment.PublicTrust{Credentials: []enrollment.PublicCredential{{Generation: 1}}}}
	withFakes(t, p, terminal)
	withEnrollmentFakes(t, store, enroller)
	if code := run([]string{"workflow-authority-admin", "enroll-fido"}, strings.NewReader(""), io.Discard, io.Discard); code != exitDeclined || enroller.calls != 0 {
		t.Fatalf("existing enrollment reached FIDO device: code=%d calls=%d", code, enroller.calls)
	}
	store.trust = enrollment.PublicTrust{}
	store.loadErr = enrollment.ErrCorrupt
	if code := run([]string{"workflow-authority-admin", "enroll-fido"}, strings.NewReader(""), io.Discard, io.Discard); code != exitUnavailable || enroller.calls != 0 {
		t.Fatalf("corrupt enrollment reached FIDO device: code=%d calls=%d", code, enroller.calls)
	}
}

func TestAdminEnrollmentComposesWithDurableStoreAtTempRoot(t *testing.T) {
	root := t.TempDir()
	for _, item := range []struct {
		path string
		mode os.FileMode
	}{
		{"var", 0o755}, {"var/lib", 0o755}, {"var/lib/design-machines", 0o755}, {"var/lib/design-machines/workflow-authority", 0o700},
		{"etc", 0o755}, {"etc/design-machines", 0o755}, {"etc/design-machines/workflow-authority", 0o755}, {"etc/design-machines/workflow-authority/trust", 0o755},
	} {
		if err := os.Mkdir(filepath.Join(root, item.path), item.mode); err != nil {
			t.Fatal(err)
		}
	}
	store, err := enrollment.NewTestStore(root, uint32(os.Getuid()))
	if err != nil {
		t.Fatal(err)
	}
	private, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	public, err := x509.MarshalPKIXPublicKey(&private.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	id := []byte("temp-root-credential-id")
	enroller := &fakeFIDOEnroller{result: enrollment.Credential{
		Reference: enrollment.ReferenceForID(id), ID: id, PublicKey: public, Algorithm: enrollment.ES256,
		RPID: enrollment.RPID, EnrolledAt: time.Unix(1_900_000_000, 0).UTC(), Status: "active", InternalUV: true,
		AAGUID: bytes.Repeat([]byte{7}, 16), Format: "packed",
	}}
	var stdout, stderr bytes.Buffer
	if code := runFIDOLifecycle("enroll-fido", &fakeTerminal{}, store, enroller, &stdout, &stderr); code != 0 {
		t.Fatalf("real store enrollment code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for path, mode := range map[string]os.FileMode{
		filepath.Join(root, "etc/design-machines/workflow-authority/trust/authority-public.json"): 0o644,
		filepath.Join(root, "var/lib/design-machines/workflow-authority/enrollment-private.json"): 0o600,
		filepath.Join(root, "var/lib/design-machines/workflow-authority/enrollment.lock"):         0o600,
	} {
		info, err := os.Lstat(path)
		if err != nil || info.Mode().Perm() != mode || !info.Mode().IsRegular() {
			t.Fatalf("bad enrollment record %s mode=%v err=%v", path, info, err)
		}
	}
	if code := runFIDOLifecycle("enroll-fido", &fakeTerminal{}, store, enroller, io.Discard, io.Discard); code != exitDeclined || enroller.calls != 1 {
		t.Fatalf("repeat enrollment reached device: code=%d calls=%d", code, enroller.calls)
	}
}

func TestFIDORevocationAndPublicRecoveryAreContentFree(t *testing.T) {
	p := &fakePlatform{}
	terminal := &fakeTerminal{}
	store := &fakeEnrollmentStore{active: &enrollment.Credential{ID: []byte("secret-id-never-output"), Generation: 4}}
	withFakes(t, p, terminal)
	withEnrollmentFakes(t, store, &fakeFIDOEnroller{})
	var stdout, stderr bytes.Buffer
	if code := run([]string{"workflow-authority-admin", "revoke-fido"}, strings.NewReader(""), &stdout, &stderr); code != 0 || store.revoked != 1 || store.revokedGeneration != 4 || strings.Contains(stdout.String()+stderr.String(), "secret-id") {
		t.Fatalf("revoke code=%d calls=%d stdout=%q stderr=%q", code, store.revoked, stdout.String(), stderr.String())
	}
	stdout.Reset()
	stderr.Reset()
	if code := run([]string{"workflow-authority-admin", "recover-fido-public"}, strings.NewReader(""), &stdout, &stderr); code != 0 || store.publicRecovered != 1 || !strings.Contains(stdout.String(), "public-trust-recovered") {
		t.Fatalf("public recovery code=%d calls=%d stdout=%q stderr=%q", code, store.publicRecovered, stdout.String(), stderr.String())
	}
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
	if code := runProvider(&fakeProviderClient{status: status}, "provider-transport-status", nil, &stdout, &stderr); code != 0 || stdout.String() != string(status)+"\n" || stderr.Len() != 0 {
		t.Fatalf("status code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestFullDispatchCLIUsesExactDescriptorsAndSeparatesReceipt(t *testing.T) {
	stdout, response := runDispatchHelper(t, "verified")
	if string(response) != "verified-response" || string(stdout) != "{\"outcome\":\"verified\"}\n" {
		t.Fatalf("descriptor separation failed response=%q stdout=%q", response, stdout)
	}
}

func TestUnsignedPostDialAmbiguityUsesExit75WithoutOutput(t *testing.T) {
	stdout, response := runDispatchHelper(t, "uncertain")
	if len(response) != 0 || len(stdout) != 0 {
		t.Fatalf("unsigned ambiguity emitted output response=%q stdout=%q", response, stdout)
	}
}

func runDispatchHelper(t *testing.T, helperCase string) ([]byte, []byte) {
	t.Helper()
	system, err := os.CreateTemp(t.TempDir(), "system")
	if err != nil {
		t.Fatal(err)
	}
	user, err := os.CreateTemp(t.TempDir(), "user")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := system.WriteString("system-secret"); err != nil {
		t.Fatal(err)
	}
	if _, err := user.WriteString("user-secret"); err != nil {
		t.Fatal(err)
	}
	if _, err := system.Seek(0, 0); err != nil {
		t.Fatal(err)
	}
	if _, err := user.Seek(0, 0); err != nil {
		t.Fatal(err)
	}
	responseRead, responseWrite, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer responseRead.Close()
	command := exec.Command(os.Args[0], "-test.run=^TestDispatchCLIHelper$")
	command.Env = append(os.Environ(), "DM_CLIENT_FD_HELPER=1", "DM_CLIENT_FD_CASE="+helperCase)
	command.ExtraFiles = []*os.File{responseWrite, system, user}
	stdout, err := command.Output()
	_ = responseWrite.Close()
	_ = system.Close()
	_ = user.Close()
	if err != nil {
		t.Fatalf("dispatch helper: %v", err)
	}
	response, err := io.ReadAll(responseRead)
	if err != nil {
		t.Fatal(err)
	}
	return stdout, response
}

func TestDispatchCLIHelper(t *testing.T) {
	if os.Getenv("DM_CLIENT_FD_HELPER") != "1" {
		return
	}
	providerClient := &fakeProviderClient{result: client.Result{Receipt: []byte(`{"outcome":"verified"}`), Response: []byte("verified-response"), ExitCode: 0}}
	expectedCode := 0
	if os.Getenv("DM_CLIENT_FD_CASE") == "uncertain" {
		providerClient.result = client.Result{}
		providerClient.dispatchErr = client.ErrUncertain
		expectedCode = exitVerification
	}
	args := []string{"--repository", "owner/repo", "--run-id", "run-1", "--lane", "lane-1", "--candidate", "candidate-1", "--workload", "workload-1", "--nonce", "nonce-1", "--model", "openai/gpt-5", "--fallback-model", "", "--system-fd", "4", "--user-fd", "5", "--response-fd", "3"}
	code := runProvider(providerClient, "dispatch-provider-request", args, os.Stdout, os.Stderr)
	if code != expectedCode || string(providerClient.system) != "system-secret" || string(providerClient.user) != "user-secret" || providerClient.options.Repository != "owner/repo" {
		os.Exit(99)
	}
	os.Exit(0)
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
