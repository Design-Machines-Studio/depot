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
#if FIDO_VERSION_MAJOR != 1 || FIDO_VERSION_MINOR < 16
#error "workflow-authority requires libfido2 >=1.16.0 and <2.0.0"
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

#define DM_MAX_DEVICES 16
typedef struct {
	char path[1024]; char manufacturer[256]; char product[256];
	unsigned short vendor_id; unsigned short product_id;
} dm_manifest_device;

static int dm_copy_string(char *dst, size_t dst_len, const char *src) {
	if (!dst || dst_len == 0 || !src || src[0] == '\0' || strlen(src) >= dst_len) return FIDO_ERR_INVALID_ARGUMENT;
	memcpy(dst, src, strlen(src) + 1); return FIDO_OK;
}

static int dm_manifest(dm_manifest_device *out, size_t capacity, size_t *count) {
	fido_dev_info_t *list = NULL; size_t found = 0; int rc = FIDO_ERR_INTERNAL;
	if (!out || !count || capacity == 0 || capacity > DM_MAX_DEVICES) return FIDO_ERR_INVALID_ARGUMENT;
	memset(out, 0, sizeof(*out) * capacity); *count = 0; fido_init(0);
	if ((list = fido_dev_info_new(capacity)) == NULL) return FIDO_ERR_INTERNAL;
	if ((rc = fido_dev_info_manifest(list, capacity, &found)) != FIDO_OK) goto done;
	if (found > capacity) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
	for (size_t i = 0; i < found; i++) {
		const fido_dev_info_t *info = fido_dev_info_ptr(list, i);
		if (!info || dm_copy_string(out[i].path, sizeof(out[i].path), fido_dev_info_path(info)) != FIDO_OK) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
		const char *manufacturer = fido_dev_info_manufacturer_string(info);
		const char *product = fido_dev_info_product_string(info);
		if (!manufacturer) manufacturer = "unknown"; if (!product) product = "unknown";
		if (strlen(manufacturer) >= sizeof(out[i].manufacturer) || strlen(product) >= sizeof(out[i].product)) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
		memcpy(out[i].manufacturer, manufacturer, strlen(manufacturer) + 1);
		memcpy(out[i].product, product, strlen(product) + 1);
		out[i].vendor_id = fido_dev_info_vendor(info); out[i].product_id = fido_dev_info_product(info);
	}
	*count = found; rc = FIDO_OK;
done:
	if (list) fido_dev_info_free(&list, capacity); return rc;
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

typedef struct {
	unsigned char *id; size_t id_len;
	unsigned char *pubkey; size_t pubkey_len;
	unsigned char *aaguid; size_t aaguid_len;
	unsigned int flags;
} dm_enrollment;

static void dm_free_enrollment(dm_enrollment *out) {
	if (out == NULL) return;
	if (out->id) { explicit_bzero(out->id, out->id_len); free(out->id); }
	if (out->pubkey) { explicit_bzero(out->pubkey, out->pubkey_len); free(out->pubkey); }
	if (out->aaguid) { explicit_bzero(out->aaguid, out->aaguid_len); free(out->aaguid); }
	memset(out, 0, sizeof(*out));
}

typedef struct { fido_dev_t *dev; fido_cred_t *cred; char *path; } dm_enroll_operation;

static dm_enroll_operation *dm_enroll_operation_new(const char *path, const char *rp_id,
	const unsigned char *challenge_hash, size_t challenge_hash_len,
	const unsigned char *user_id, size_t user_id_len,
	const unsigned char *exclude_id, size_t exclude_id_len) {
	dm_enroll_operation *op = NULL;
	if (!path || !rp_id || !challenge_hash || challenge_hash_len != 32 || !user_id || user_id_len == 0 || user_id_len > 64) return NULL;
	if ((op = calloc(1, sizeof(*op))) == NULL) return NULL; fido_init(0);
	if ((op->dev = fido_dev_new()) == NULL || (op->cred = fido_cred_new()) == NULL) goto fail;
	if ((op->path = strdup(path)) == NULL) goto fail;
	if (fido_dev_set_timeout(op->dev, 30000) != FIDO_OK) goto fail;
	if (fido_cred_set_type(op->cred, COSE_ES256) != FIDO_OK) goto fail;
	if (fido_cred_set_clientdata_hash(op->cred, challenge_hash, challenge_hash_len) != FIDO_OK) goto fail;
	if (fido_cred_set_rp(op->cred, rp_id, "Workflow Authority") != FIDO_OK) goto fail;
	if (fido_cred_set_user(op->cred, user_id, user_id_len, "workflow-authority", "Workflow Authority", NULL) != FIDO_OK) goto fail;
	if (fido_cred_set_rk(op->cred, FIDO_OPT_FALSE) != FIDO_OK) goto fail;
	if (fido_cred_set_uv(op->cred, FIDO_OPT_TRUE) != FIDO_OK) goto fail;
	if (exclude_id_len > 0 && (!exclude_id || fido_cred_exclude(op->cred, exclude_id, exclude_id_len) != FIDO_OK)) goto fail;
	return op;
fail:
	if (op) { if (op->dev) { fido_dev_close(op->dev); fido_dev_free(&op->dev); } if (op->cred) fido_cred_free(&op->cred); free(op->path); free(op); }
	return NULL;
}

static int dm_enroll_operation_run(dm_enroll_operation *op, const char *expected_rp, dm_enrollment *out) {
	int rc = FIDO_ERR_INTERNAL; const char *fmt = NULL; const char *actual_rp = NULL;
	if (!op || !op->dev || !op->cred || !expected_rp || !out) return FIDO_ERR_INVALID_ARGUMENT;
	memset(out, 0, sizeof(*out)); fido_init(0);
	if ((rc = fido_dev_open(op->dev, op->path)) != FIDO_OK) goto done;
	if (!fido_dev_has_uv(op->dev)) { rc = FIDO_ERR_UNSUPPORTED_OPTION; goto done; }
	// NULL is intentional: host-PIN fallback is outside the authority model.
	if ((rc = fido_dev_make_cred(op->dev, op->cred, NULL)) != FIDO_OK) goto done;
	fmt = fido_cred_fmt(op->cred); actual_rp = fido_cred_rp_id(op->cred);
	if (!fmt || strcmp(fmt, "packed") != 0 || !actual_rp || strcmp(actual_rp, expected_rp) != 0 || fido_cred_type(op->cred) != COSE_ES256) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
	out->flags = fido_cred_flags(op->cred);
	if ((out->flags & 0x05u) != 0x05u) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
	if (fido_cred_x5c_ptr(op->cred) != NULL) rc = fido_cred_verify(op->cred);
	else rc = fido_cred_verify_self(op->cred);
	if (rc != FIDO_OK) goto done;
	if ((rc = dm_copy(&out->id, &out->id_len, fido_cred_id_ptr(op->cred), fido_cred_id_len(op->cred))) != FIDO_OK) goto done;
	if ((rc = dm_copy(&out->pubkey, &out->pubkey_len, fido_cred_pubkey_ptr(op->cred), fido_cred_pubkey_len(op->cred))) != FIDO_OK) goto done;
	if ((rc = dm_copy(&out->aaguid, &out->aaguid_len, fido_cred_aaguid_ptr(op->cred), fido_cred_aaguid_len(op->cred))) != FIDO_OK) goto done;
	rc = FIDO_OK;
done:
	if (rc != FIDO_OK) dm_free_enrollment(out); return rc;
}

static int dm_enroll_operation_cancel(dm_enroll_operation *op) {
	if (!op || !op->dev) return FIDO_ERR_INVALID_ARGUMENT; fido_init(0); return fido_dev_cancel(op->dev);
}

static void dm_enroll_operation_free(dm_enroll_operation *op) {
	if (!op) return;
	if (op->dev) { fido_dev_close(op->dev); fido_dev_free(&op->dev); }
	if (op->cred) fido_cred_free(&op->cred); free(op->path); free(op);
}
*/
import "C"

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"math/big"
	"syscall"
	"time"
	"unsafe"

	"designmachines.dev/workflow-authority/internal/enrollment"
	"designmachines.dev/workflow-authority/internal/protocol"
)

type libfido2Adapter struct{}

func NewFIDOAdapter() FIDO                 { return &libfido2Adapter{} }
func NewFIDOEnroller() enrollment.Enroller { return &libfido2Adapter{} }
func (a *libfido2Adapter) Readiness(ctx context.Context) Readiness {
	return a.ReadinessFor(ctx, "")
}
func (a *libfido2Adapter) ReadinessFor(ctx context.Context, selector string) Readiness {
	device, err := selectManifestDevice(selector)
	if ctx.Err() != nil || err != nil {
		return Readiness{Production: false, Adapter: "libfido2", Version: FIDO2Version}
	}
	path := C.CString(device.path)
	defer C.free(unsafe.Pointer(path))
	ready := C.dm_ready(path) == C.FIDO_OK
	return Readiness{Production: ready, Adapter: "libfido2", Version: FIDO2Version, InternalUV: ready}
}

func (a *libfido2Adapter) Assert(ctx context.Context, challenge []byte, credential Credential) (Assertion, error) {
	if err := ctx.Err(); err != nil || credential.Algorithm != -7 || !credential.InternalUV || credential.Status != "active" || len(credential.ID) == 0 || credential.DeviceSelector == "" {
		return Assertion{}, ErrUnavailable
	}
	challengeDigest := sha256.Sum256(challenge)
	clientData, err := protocol.CanonicalJSON(map[string]any{"challenge": base64.RawURLEncoding.EncodeToString(challengeDigest[:]), "crossOrigin": false, "origin": "https://workflow-authority.designmachines.local", "type": "webauthn.get"})
	if err != nil {
		return Assertion{}, ErrUnavailable
	}
	clientDataDigest := sha256.Sum256(clientData)
	device, err := selectManifestDevice(credential.DeviceSelector)
	if err != nil {
		return Assertion{}, ErrUnavailable
	}
	cpath := C.CString(device.path)
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

type enrollmentResult struct {
	credential enrollment.Credential
	err        error
}

func (a *libfido2Adapter) Enroll(ctx context.Context, request enrollment.Request) (enrollment.Credential, error) {
	if ctx.Err() != nil || request.Generation == 0 || len(request.ExcludeCredentialID) > 4096 || len(request.ExcludeCredentialID) > 0 && request.DeviceSelector == "" {
		return enrollment.Credential{}, enrollment.ErrUnavailable
	}
	device, err := selectManifestDevice(request.DeviceSelector)
	if err != nil {
		return enrollment.Credential{}, enrollment.ErrUnavailable
	}
	var challenge [32]byte
	if _, err := rand.Read(challenge[:]); err != nil {
		return enrollment.Credential{}, enrollment.ErrUnavailable
	}
	userID := sha256.Sum256([]byte("workflow-authority.designmachines.local/root-authority"))
	excludeCopy := append([]byte(nil), request.ExcludeCredentialID...)
	defer func() {
		for i := range excludeCopy {
			excludeCopy[i] = 0
		}
	}()
	cpath := C.CString(device.path)
	crp := C.CString(enrollment.RPID)
	defer C.free(unsafe.Pointer(cpath))
	defer C.free(unsafe.Pointer(crp))
	var exclude *C.uchar
	if len(excludeCopy) > 0 {
		exclude = (*C.uchar)(unsafe.Pointer(&excludeCopy[0]))
	}
	op := C.dm_enroll_operation_new(cpath, crp, (*C.uchar)(unsafe.Pointer(&challenge[0])), 32, (*C.uchar)(unsafe.Pointer(&userID[0])), 32, exclude, C.size_t(len(excludeCopy)))
	if op == nil {
		return enrollment.Credential{}, enrollment.ErrUnavailable
	}
	results := make(chan enrollmentResult, 1)
	release := make(chan struct{})
	go func() {
		var out C.dm_enrollment
		expectedRP := C.CString(enrollment.RPID)
		rc := C.dm_enroll_operation_run(op, expectedRP, &out)
		C.free(unsafe.Pointer(expectedRP))
		result := enrollmentResult{err: enrollment.ErrUnavailable}
		if rc == C.FIDO_OK {
			rawPublic := C.GoBytes(unsafe.Pointer(out.pubkey), C.int(out.pubkey_len))
			publicDER, err := marshalES256PublicKey(rawPublic)
			for i := range rawPublic {
				rawPublic[i] = 0
			}
			if err == nil {
				id := C.GoBytes(unsafe.Pointer(out.id), C.int(out.id_len))
				result = enrollmentResult{credential: enrollment.Credential{Reference: enrollment.ReferenceForID(id), ID: id, PublicKey: publicDER, Algorithm: enrollment.ES256, Generation: request.Generation, RPID: enrollment.RPID, EnrolledAt: time.Now().UTC(), Status: "active", InternalUV: uint(out.flags)&4 != 0, AAGUID: C.GoBytes(unsafe.Pointer(out.aaguid), C.int(out.aaguid_len)), Format: "packed", DeviceSelector: device.selector}}
			}
		}
		C.dm_free_enrollment(&out)
		results <- result
		<-release
		C.dm_enroll_operation_free(op)
	}()
	select {
	case result := <-results:
		close(release)
		if result.err != nil || enrollment.ValidateCredential(result.credential) != nil {
			result.credential.Destroy()
			return enrollment.Credential{}, enrollment.ErrUnavailable
		}
		return result.credential, nil
	case <-ctx.Done():
		if C.dm_enroll_operation_cancel(op) != C.FIDO_OK {
			close(release)
			return enrollment.Credential{}, enrollment.ErrUnavailable
		}
		select {
		case result := <-results:
			result.credential.Destroy()
		case <-time.After(500 * time.Millisecond):
		}
		close(release)
		return enrollment.Credential{}, enrollment.ErrConflict
	}
}

type manifestDevice struct{ path, selector string }

func selectManifestDevice(requested string) (manifestDevice, error) {
	devices, err := manifestDevices()
	if err != nil {
		return manifestDevice{}, enrollment.ErrUnavailable
	}
	selected, selector, err := enrollment.SelectDevice(devices, requested)
	if err != nil {
		return manifestDevice{}, err
	}
	return manifestDevice{path: selected.Path, selector: selector}, nil
}

func manifestDevices() ([]enrollment.DeviceManifest, error) {
	var raw [16]C.dm_manifest_device
	var count C.size_t
	if C.dm_manifest(&raw[0], 16, &count) != C.FIDO_OK || count > 16 {
		return nil, enrollment.ErrUnavailable
	}
	devices := make([]enrollment.DeviceManifest, 0, int(count))
	for i := 0; i < int(count); i++ {
		path := C.GoString(&raw[i].path[0])
		manufacturer := C.GoString(&raw[i].manufacturer[0])
		product := C.GoString(&raw[i].product[0])
		devices = append(devices, enrollment.DeviceManifest{Path: path, Manufacturer: manufacturer, Product: product, VendorID: uint16(raw[i].vendor_id), ProductID: uint16(raw[i].product_id)})
	}
	return devices, nil
}

func marshalES256PublicKey(raw []byte) ([]byte, error) {
	if len(raw) == 65 && raw[0] == 4 {
		raw = raw[1:]
	}
	if len(raw) != 64 {
		return nil, enrollment.ErrUnavailable
	}
	curve := elliptic.P256()
	x := new(big.Int).SetBytes(raw[:32])
	y := new(big.Int).SetBytes(raw[32:])
	if !curve.IsOnCurve(x, y) {
		return nil, enrollment.ErrUnavailable
	}
	return x509.MarshalPKIXPublicKey(&ecdsa.PublicKey{Curve: curve, X: x, Y: y})
}

// LinuxPeerCredentials is eligibility evidence only. It never authorizes send.
func LinuxPeerCredentials(fd int) (Peer, error) {
	credential, err := syscall.GetsockoptUcred(fd, syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	if err != nil || credential.Pid < 1 {
		return Peer{}, ErrDenied
	}
	return Peer{UID: credential.Uid, PID: credential.Pid}, nil
}
