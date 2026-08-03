//go:build linux && cgo && libfido2

package authority

/*
#cgo pkg-config: libfido2
#include <stdlib.h>
#include <string.h>
#include <fido.h>

#if !defined(FIDO_VERSION_MAJOR) || !defined(FIDO_VERSION_MINOR) || !defined(FIDO_VERSION_PATCH)
#error "libfido2 version macros required"
#endif
#if FIDO_VERSION_MAJOR != 1 || FIDO_VERSION_MINOR != 17 || FIDO_VERSION_PATCH != 0
#error "workflow-authority requires exactly libfido2 1.17.0"
#endif

typedef struct {
	unsigned char *authdata; size_t authdata_len;
	unsigned char *sig; size_t sig_len;
	unsigned char *clientdata; size_t clientdata_len;
	unsigned int flags; unsigned int counter;
} dm_assertion;

static void dm_free_assertion(dm_assertion *out) {
	if (out == NULL) return;
	if (out->authdata) { explicit_bzero(out->authdata, out->authdata_len); free(out->authdata); }
	if (out->sig) { explicit_bzero(out->sig, out->sig_len); free(out->sig); }
	if (out->clientdata) { explicit_bzero(out->clientdata, out->clientdata_len); free(out->clientdata); }
	memset(out, 0, sizeof(*out));
}

static int dm_copy(unsigned char **dst, size_t *dst_len, const unsigned char *src, size_t src_len) {
	if (src == NULL || src_len == 0 || src_len > 4096) return FIDO_ERR_INVALID_ARGUMENT;
	*dst = malloc(src_len); if (*dst == NULL) return FIDO_ERR_INTERNAL;
	memcpy(*dst, src, src_len); *dst_len = src_len; return FIDO_OK;
}

static int dm_ready(const char *path) {
	int rc = FIDO_ERR_INTERNAL; fido_dev_t *dev = NULL;
	if (!path) return FIDO_ERR_INVALID_ARGUMENT; fido_init(0);
	if ((dev = fido_dev_new()) == NULL) return FIDO_ERR_INTERNAL;
	if ((rc = fido_dev_open(dev, path)) != FIDO_OK) goto done;
	if (!fido_dev_has_uv(dev)) { rc = FIDO_ERR_UNSUPPORTED_OPTION; goto done; }
	rc = FIDO_OK;
done:
	if (dev) { fido_dev_close(dev); fido_dev_free(&dev); }
	return rc;
}

typedef struct { fido_dev_t *dev; fido_assert_t *assert; char *path; } dm_operation;

static dm_operation *dm_operation_new(const char *path, const char *rp_id,
	const unsigned char *credential, size_t credential_len,
	const unsigned char *challenge_hash, size_t challenge_hash_len) {
	dm_operation *op = NULL;
	if (!path || !rp_id || !credential || credential_len == 0 || challenge_hash_len != 32) return NULL;
	if ((op = calloc(1, sizeof(*op))) == NULL) return NULL; fido_init(0);
	if ((op->dev = fido_dev_new()) == NULL || (op->assert = fido_assert_new()) == NULL) goto fail;
	if ((op->path = strdup(path)) == NULL) goto fail;
	if (fido_dev_set_timeout(op->dev, 30000) != FIDO_OK) goto fail;
	if (fido_assert_set_rp(op->assert, rp_id) != FIDO_OK) goto fail;
	if (fido_assert_set_clientdata_hash(op->assert, challenge_hash, challenge_hash_len) != FIDO_OK) goto fail;
	if (fido_assert_allow_cred(op->assert, credential, credential_len) != FIDO_OK) goto fail;
	if (fido_assert_set_up(op->assert, FIDO_OPT_TRUE) != FIDO_OK) goto fail;
	if (fido_assert_set_uv(op->assert, FIDO_OPT_TRUE) != FIDO_OK) goto fail;
	return op;
fail:
	if (op) { if (op->dev) { fido_dev_close(op->dev); fido_dev_free(&op->dev); } if (op->assert) fido_assert_free(&op->assert); free(op->path); free(op); }
	return NULL;
}

static int dm_operation_run(dm_operation *op, dm_assertion *out) {
	int rc = FIDO_ERR_INTERNAL; if (!op || !op->dev || !op->assert || !out) return FIDO_ERR_INVALID_ARGUMENT;
	memset(out, 0, sizeof(*out)); fido_init(0);
	if ((rc = fido_dev_open(op->dev, op->path)) != FIDO_OK) goto done;
	if (!fido_dev_has_uv(op->dev)) { rc = FIDO_ERR_UNSUPPORTED_OPTION; goto done; }
	// A NULL PIN is intentional: authenticators requiring host PIN fail closed.
	if ((rc = fido_dev_get_assert(op->dev, op->assert, NULL)) != FIDO_OK) goto done;
	if (fido_assert_count(op->assert) != 1) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
	if ((rc = dm_copy(&out->authdata, &out->authdata_len, fido_assert_authdata_raw_ptr(op->assert, 0), fido_assert_authdata_raw_len(op->assert, 0))) != FIDO_OK) goto done;
	if ((rc = dm_copy(&out->sig, &out->sig_len, fido_assert_sig_ptr(op->assert, 0), fido_assert_sig_len(op->assert, 0))) != FIDO_OK) goto done;
	out->flags = fido_assert_flags(op->assert, 0); out->counter = fido_assert_sigcount(op->assert, 0); rc = FIDO_OK;
done:
	if (rc != FIDO_OK) dm_free_assertion(out); return rc;
}

static int dm_operation_cancel(dm_operation *op) {
	if (!op || !op->dev) return FIDO_ERR_INVALID_ARGUMENT; fido_init(0); return fido_dev_cancel(op->dev);
}

static void dm_operation_free(dm_operation *op) {
	if (!op) return;
	if (op->dev) { fido_dev_close(op->dev); fido_dev_free(&op->dev); }
	if (op->assert) fido_assert_free(&op->assert); free(op->path); free(op);
}
*/
import "C"

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"syscall"
	"time"
	"unsafe"

	"designmachines.dev/workflow-authority/internal/protocol"
)

type libfido2Adapter struct{ DevicePath string }

func NewFIDOAdapter() FIDO { return &libfido2Adapter{DevicePath: "/dev/hidraw0"} }
func (a *libfido2Adapter) Readiness(ctx context.Context) Readiness {
	if ctx.Err() != nil || a.DevicePath == "" {
		return Readiness{Production: false, Adapter: "libfido2", Version: FIDO2Version}
	}
	path := C.CString(a.DevicePath)
	defer C.free(unsafe.Pointer(path))
	ready := C.dm_ready(path) == C.FIDO_OK
	return Readiness{Production: ready, Adapter: "libfido2", Version: FIDO2Version, InternalUV: ready}
}

func (a *libfido2Adapter) Assert(ctx context.Context, challenge []byte, credential Credential) (Assertion, error) {
	if err := ctx.Err(); err != nil || credential.Algorithm != -7 || !credential.InternalUV || credential.Status != "active" || len(credential.ID) == 0 {
		return Assertion{}, ErrUnavailable
	}
	challengeDigest := sha256.Sum256(challenge)
	clientData, err := protocol.CanonicalJSON(map[string]any{"challenge": base64.RawURLEncoding.EncodeToString(challengeDigest[:]), "crossOrigin": false, "origin": "https://workflow-authority.designmachines.local", "type": "webauthn.get"})
	if err != nil {
		return Assertion{}, ErrUnavailable
	}
	clientDataDigest := sha256.Sum256(clientData)
	cpath := C.CString(a.DevicePath)
	crp := C.CString(credential.RPID)
	defer C.free(unsafe.Pointer(cpath))
	defer C.free(unsafe.Pointer(crp))
	op := C.dm_operation_new(cpath, crp, (*C.uchar)(unsafe.Pointer(&credential.ID[0])), C.size_t(len(credential.ID)), (*C.uchar)(unsafe.Pointer(&clientDataDigest[0])), 32)
	if op == nil {
		return Assertion{}, ErrUnavailable
	}
	results := make(chan assertionResult, 1)
	release := make(chan struct{})
	go func() {
		var out C.dm_assertion
		rc := C.dm_operation_run(op, &out)
		result := assertionResult{err: ErrUnavailable}
		if rc == C.FIDO_OK {
			result = assertionResult{assertion: Assertion{CredentialReference: credential.Reference, Generation: credential.Generation, ChallengeDigest: challengeDigest, Signature: C.GoBytes(unsafe.Pointer(out.sig), C.int(out.sig_len)), AuthenticatorData: C.GoBytes(unsafe.Pointer(out.authdata), C.int(out.authdata_len)), ClientDataJSON: clientData, UserPresence: uint(out.flags)&1 != 0, UserVerification: uint(out.flags)&4 != 0, Counter: uint32(out.counter)}}
		}
		C.dm_free_assertion(&out)
		results <- result
		<-release
		C.dm_operation_free(op)
	}()
	assertion, err := waitCancelableAssertion(ctx, func() error {
		if C.dm_operation_cancel(op) != C.FIDO_OK {
			return ErrUnavailable
		}
		return nil
	}, results, 500*time.Millisecond)
	close(release)
	return assertion, err
}

func (a *libfido2Adapter) Verify(_ context.Context, challenge []byte, credential Credential, assertion Assertion) error {
	return verifyES256Assertion(challenge, credential, assertion)
}

// LinuxPeerCredentials is eligibility evidence only. It never authorizes send.
func LinuxPeerCredentials(fd int) (Peer, error) {
	credential, err := syscall.GetsockoptUcred(fd, syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	if err != nil || credential.Pid < 1 {
		return Peer{}, ErrDenied
	}
	return Peer{UID: credential.Uid, PID: credential.Pid}, nil
}
