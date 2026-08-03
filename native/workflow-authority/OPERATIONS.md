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

## Package installation

Run these steps from a trusted, verified package staging directory as root. Do
not build or copy binaries from a repository-worker checkout.

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

## Enrollment and credential custody

Run administrative commands interactively from the controlling terminal. The
program rejects redirected stdin and a terminal that changes during the
operation.

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
