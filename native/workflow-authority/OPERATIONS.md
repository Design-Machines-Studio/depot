# Workflow Authority Linux operator workflow

This is the Linux-first operator contract for the first broker-mediated provider
dispatch milestone. The commands below are documentation only: repository
validation must not install files, enable services, access a FIDO authenticator,
or contact a provider.

Read [THREAT-MODEL.md](THREAT-MODEL.md) before provisioning. In particular,
ordinary FIDO UP+UV is user presence, not a trusted hardware display of scope.

## Fixed boundary

The production binaries accept no socket, enrollment-record, credential,
authenticator-path, or authenticator-selector option or environment override.
The installed paths are fixed in `internal/platform`, and the systemd units
activate the fixed Unix socket. Initial enrollment and revoked-state recovery
accept exactly one eligible authenticator; multiple attached authenticators fail
closed. Rotation uses only the selector already held in the root-private
enrollment record.

macOS will use the same provider-dispatch protocol and receipt verification, but
this Linux systemd/libfido2 installation workflow does not claim macOS runtime
support.

## Ubuntu distro prerequisites

Use Ubuntu's signed packages from the configured distro repositories for the Go
launcher, cgo compiler, `pkg-config`, and libfido2 development files:

```sh
sudo apt install golang-go build-essential pkg-config libfido2-dev
```

The distro Go launcher may be older than the module toolchain. The validator
resolves `go` from the operator's executable `PATH`, sets `GOTOOLCHAIN=auto`,
and requires the module-selected toolchain to report `go1.26.5`. It resolves
`gofmt` from that selected toolchain's `GOROOT`. The supported native-library
range is libfido2 1.x at 1.16.0 or newer; 1.15 and older and major version 2 or
newer fail closed.

## Production-tag build proof from a repository checkout

From a candidate repository checkout, run the complete validation gate:

```sh
WORKFLOW_AUTHORITY_REQUIRE_PRODUCTION_BUILD=1 ./tools/validate-workflow-authority.sh
```

The production adapter is behind the `libfido2` build tag; an untagged build
deliberately contains the fail-closed fixture adapter and must not be installed
as production authority. A green candidate-branch gate proves that the tagged
source builds on the host. It does not authorize installing binaries from that
checkout, access a FIDO authenticator, provision a provider credential, contact
a provider, or claim broker status `ready`.

## Reviewed trusted-main artifacts

Only after review and merge, build installation artifacts from a clean checkout
of the reviewed trusted-main commit. Record and verify that exact commit before
building:

```sh
git status --short
git rev-parse HEAD
cd native/workflow-authority
GO_BIN="$(command -v go)"
LIBFIDO2_VERSION="$(pkg-config --modversion libfido2)"
IFS=. read -r LIBFIDO2_MAJOR LIBFIDO2_MINOR LIBFIDO2_PATCH <<EOF
$LIBFIDO2_VERSION
EOF
LIBFIDO2_CPPFLAGS="-DWORKFLOW_AUTHORITY_LIBFIDO2_MAJOR=$LIBFIDO2_MAJOR -DWORKFLOW_AUTHORITY_LIBFIDO2_MINOR=$LIBFIDO2_MINOR -DWORKFLOW_AUTHORITY_LIBFIDO2_PATCH=$LIBFIDO2_PATCH"
CGO_CPPFLAGS="$LIBFIDO2_CPPFLAGS" GOTOOLCHAIN=auto "$GO_BIN" build -tags libfido2 -o workflow-authority ./cmd/workflow-authority
cp workflow-authority workflow-authority-admin
CGO_CPPFLAGS="$LIBFIDO2_CPPFLAGS" GOTOOLCHAIN=auto "$GO_BIN" build -tags libfido2 -o workflow-authorityd ./cmd/workflow-authorityd
```

The two client filenames intentionally contain the same binary: administrative
commands are enabled only when its basename is `workflow-authority-admin`.
Portable/macOS fixture validation is useful protocol evidence, but it is an
explicit production-build coverage gap rather than Linux/libfido2 proof.

## Package installation

Run these steps from a trusted, verified package staging directory as root,
using only artifacts built from the reviewed, merged trusted-main commit. Do
not build or copy binaries from a feature or repository-worker checkout.

```sh
install -o root -g root -m 0755 workflow-authority /usr/local/bin/workflow-authority
install -o root -g root -m 0750 workflow-authority-admin /usr/local/sbin/workflow-authority-admin
install -o root -g root -m 0755 workflow-authorityd /usr/local/libexec/design-machines/workflow-authorityd
install -o root -g root -m 0644 packaging/linux/workflow-authority.service /etc/systemd/system/workflow-authority.service
install -o root -g root -m 0644 packaging/linux/workflow-authority.socket /etc/systemd/system/workflow-authority.socket
install -o root -g root -m 0644 packaging/linux/workflow-authority-runtime.service /etc/systemd/system/workflow-authority-runtime.service
install -o root -g root -m 0644 packaging/linux/workflow-authority-tmpfiles.conf /usr/lib/tmpfiles.d/workflow-authority.conf
systemd-tmpfiles --create /usr/lib/tmpfiles.d/workflow-authority.conf
systemctl daemon-reload
```

Install the fixed root-owned provider policy at
`/etc/design-machines/workflow-authority/provider-policy.json` with mode `0600`.
Create the `workflow-authority` group and add only independently authenticated
local client accounts. Do not enable or start the socket yet.

## Later interactive enrollment and credential custody

Run administrative commands interactively from the controlling terminal. The
program rejects redirected stdin and a terminal that changes during the
operation. This human ceremony happens only after trusted-main installation; it
is not part of repository production-build proof.

```sh
sudo /usr/local/sbin/workflow-authority-admin enroll-fido
sudo /usr/local/sbin/workflow-authority-admin provision-openrouter
/usr/local/bin/workflow-authority status
sudo systemctl enable --now workflow-authority.socket
```

The OpenRouter credential is read with terminal echo disabled and is never
accepted through argv, environment, a file supplied by the caller, or stdout.
Successful admin commands emit only a content-free state receipt.

Status is intentionally content-free:

- `enrollment-required`: no complete enrollment record exists;
- `provider-required`: enrollment exists but provider custody is incomplete;
- `ready`: fixed layout, enrollment files, and provider custody are present;
- `degraded` or `unavailable`: do not enable dispatch; follow recovery.

## Minimal automated caller environment

Pipeline/Baseplate callers export only non-secret scope and routing inputs. The
socket, provider credential, FIDO selector, policy path, and authorization mode
are fixed host configuration and have no environment override:

```sh
export DM_PROVIDER_REPOSITORY="design-machines/assembly-baseplate"
export DM_PROVIDER_RUN_ID="pipeline-run-20260804-001"
export DM_PROVIDER_LANE="pipeline-assessment-artifact-delegation-v1"
export DM_PROVIDER_CANDIDATE="candidate-sha256-0123456789abcdef"
export DM_PROVIDER_WORKLOAD="pipeline-assessment"
export DM_PROVIDER_NONCE="fresh-single-use-caller-nonce"
export OPENROUTER_EXEC_ALLOWED_PATHS="docs/example.md"
```

Do not export `OPENROUTER_API_KEY`, a broker/socket path, a FIDO credential or
selector, `OPENROUTER_PAYLOAD_AUTHORIZATION`, or
`OPENROUTER_PAYLOAD_APPROVAL_SHA256` for automated broker dispatch. The first
provider milestone also exports no `DM_VERIFICATION_SUBSTRATE`: its receipts
state `substrate_authority: not_asserted` until the separate observed Docker
attestation milestone exists.

## Rotation, revocation, and recovery

```sh
sudo /usr/local/sbin/workflow-authority-admin rotate-fido
sudo /usr/local/sbin/workflow-authority-admin revoke-fido
sudo /usr/local/sbin/workflow-authority-admin recover-fido
sudo /usr/local/sbin/workflow-authority-admin recover-fido-public
```

Use `rotate-fido` while the current enrollment is active. Use `revoke-fido` to
make the current enrollment inactive, then `recover-fido` with exactly one new
eligible authenticator. `recover-fido-public` is narrower: it republishes the
public trust history only when the root-private record and its stored digest are
valid. It never invents or replaces enrollment authority.

If any command reports that completion is uncertain, keep
`workflow-authority.socket` stopped, run `status`, preserve
`/var/lib/design-machines/workflow-authority` and
`/etc/design-machines/workflow-authority/trust/authority-public.json`, and retry
only the named recovery command.

## Disable and uninstall planning

```sh
sudo /usr/local/sbin/workflow-authority-admin disable
sudo /usr/local/sbin/workflow-authority-admin revoke-openrouter
sudo /usr/local/sbin/workflow-authority-admin uninstall-plan
```

`uninstall-plan` prints exact non-recursive removal steps. It preserves the
root-private state and public enrollment history by default so an operator can
audit or recover the installation. Review the printed plan before carrying out
any removal; the command itself does not delete files.
