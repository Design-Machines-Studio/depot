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

static int dm_assert_exact(const char *path, const char *rp_id,
	const unsigned char *credential, size_t credential_len,
	const unsigned char *challenge_hash, size_t challenge_hash_len,
	dm_assertion *out) {
	int rc = FIDO_ERR_INTERNAL; fido_dev_t *dev = NULL; fido_assert_t *assert = NULL;
	if (!path || !rp_id || !credential || credential_len == 0 || challenge_hash_len != 32 || !out) return FIDO_ERR_INVALID_ARGUMENT;
	memset(out, 0, sizeof(*out)); fido_init(0);
	if ((dev = fido_dev_new()) == NULL || (assert = fido_assert_new()) == NULL) goto done;
	if ((rc = fido_dev_open(dev, path)) != FIDO_OK) goto done;
	if (!fido_dev_has_uv(dev)) { rc = FIDO_ERR_UNSUPPORTED_OPTION; goto done; }
	if ((rc = fido_assert_set_rp(assert, rp_id)) != FIDO_OK) goto done;
	if ((rc = fido_assert_set_clientdata_hash(assert, challenge_hash, challenge_hash_len)) != FIDO_OK) goto done;
	if ((rc = fido_assert_allow_cred(assert, credential, credential_len)) != FIDO_OK) goto done;
	if ((rc = fido_assert_set_up(assert, FIDO_OPT_TRUE)) != FIDO_OK) goto done;
	if ((rc = fido_assert_set_uv(assert, FIDO_OPT_TRUE)) != FIDO_OK) goto done;
	// A NULL PIN is intentional: authenticators requiring host PIN fail closed.
	if ((rc = fido_dev_get_assert(dev, assert, NULL)) != FIDO_OK) goto done;
	if (fido_assert_count(assert) != 1) { rc = FIDO_ERR_INVALID_ARGUMENT; goto done; }
	if ((rc = dm_copy(&out->authdata, &out->authdata_len, fido_assert_authdata_ptr(assert, 0), fido_assert_authdata_len(assert, 0))) != FIDO_OK) goto done;
	if ((rc = dm_copy(&out->sig, &out->sig_len, fido_assert_sig_ptr(assert, 0), fido_assert_sig_len(assert, 0))) != FIDO_OK) goto done;
	out->flags = fido_assert_flags(assert, 0); out->counter = fido_assert_sigcount(assert, 0); rc = FIDO_OK;
done:
	if (rc != FIDO_OK) dm_free_assertion(out);
	if (dev) { fido_dev_close(dev); fido_dev_free(&dev); }
	if (assert) fido_assert_free(&assert);
	return rc;
}
*/
import "C"

import (
	"bytes"
	"context"
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"syscall"
	"unsafe"

	"designmachines.dev/workflow-authority/internal/protocol"
)

type libfido2Adapter struct{ DevicePath string }

func NewFIDOAdapter() FIDO { return &libfido2Adapter{DevicePath: "/dev/hidraw0"} }
func (a *libfido2Adapter) Readiness(context.Context) Readiness {
	return Readiness{Production: a.DevicePath != "", Adapter: "libfido2", Version: FIDO2Version, InternalUV: true}
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
	var out C.dm_assertion
	rc := C.dm_assert_exact(cpath, crp, (*C.uchar)(unsafe.Pointer(&credential.ID[0])), C.size_t(len(credential.ID)), (*C.uchar)(unsafe.Pointer(&clientDataDigest[0])), 32, &out)
	defer C.dm_free_assertion(&out)
	if rc != C.FIDO_OK {
		return Assertion{}, ErrUnavailable
	}
	return Assertion{CredentialReference: credential.Reference, Generation: credential.Generation, ChallengeDigest: challengeDigest, Signature: C.GoBytes(unsafe.Pointer(out.sig), C.int(out.sig_len)), AuthenticatorData: C.GoBytes(unsafe.Pointer(out.authdata), C.int(out.authdata_len)), ClientDataJSON: clientData, UserPresence: uint(out.flags)&1 != 0, UserVerification: uint(out.flags)&4 != 0, Counter: uint32(out.counter)}, nil
}

func (a *libfido2Adapter) Verify(_ context.Context, challenge []byte, credential Credential, assertion Assertion) error {
	if !assertion.UserPresence || !assertion.UserVerification || assertion.HostPINRequested || assertion.Generation != credential.Generation {
		return ErrDenied
	}
	challengeDigest := sha256.Sum256(challenge)
	if assertion.ChallengeDigest != challengeDigest || len(assertion.AuthenticatorData) < 37 {
		return ErrDenied
	}
	var clientData struct {
		Challenge   string `json:"challenge"`
		CrossOrigin bool   `json:"crossOrigin"`
		Origin      string `json:"origin"`
		Type        string `json:"type"`
	}
	if err := protocol.DecodeClosed(assertion.ClientDataJSON, &clientData); err != nil || clientData.Challenge != base64.RawURLEncoding.EncodeToString(challengeDigest[:]) || clientData.CrossOrigin || clientData.Origin != "https://workflow-authority.designmachines.local" || clientData.Type != "webauthn.get" {
		return ErrDenied
	}
	rpHash := sha256.Sum256([]byte(credential.RPID))
	if !bytes.Equal(assertion.AuthenticatorData[:32], rpHash[:]) || assertion.AuthenticatorData[32]&0x01 == 0 || assertion.AuthenticatorData[32]&0x04 == 0 {
		return ErrDenied
	}
	counter := binary.BigEndian.Uint32(assertion.AuthenticatorData[33:37])
	if counter != assertion.Counter || (counter != 0 && counter <= credential.SignCount) {
		return ErrDenied
	}
	public, err := x509.ParsePKIXPublicKey(credential.PublicKey)
	if err != nil {
		return ErrDenied
	}
	key, ok := public.(*ecdsa.PublicKey)
	if !ok {
		return ErrDenied
	}
	clientHash := sha256.Sum256(assertion.ClientDataJSON)
	signed := append(append([]byte{}, assertion.AuthenticatorData...), clientHash[:]...)
	digest := sha256.Sum256(signed)
	if !ecdsa.VerifyASN1(key, digest[:], assertion.Signature) {
		return errors.New("fido_signature_invalid")
	}
	return nil
}

// LinuxPeerCredentials is eligibility evidence only. It never authorizes send.
func LinuxPeerCredentials(fd int) (Peer, error) {
	credential, err := syscall.GetsockoptUcred(fd, syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	if err != nil || credential.Pid < 1 {
		return Peer{}, ErrDenied
	}
	return Peer{UID: credential.Uid, PID: credential.Pid}, nil
}
