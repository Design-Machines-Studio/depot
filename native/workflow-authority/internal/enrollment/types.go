// Package enrollment owns production FIDO credential enrollment records.
package enrollment

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"time"
)

const (
	Protocol = "workflow-authority-fido-enrollment-v1"
	RPID     = "workflow-authority.designmachines.local"
	ES256    = -7
)

var (
	ErrDenied      = errors.New("enrollment_denied")
	ErrUnavailable = errors.New("enrollment_unavailable")
	ErrConflict    = errors.New("enrollment_conflict")
	ErrCorrupt     = errors.New("enrollment_corrupt")
	ErrDurability  = errors.New("enrollment_commit_sync_uncertain")
)

type Request struct {
	Generation          uint64
	ExcludeCredentialID []byte
}

type Credential struct {
	Reference  string
	ID         []byte
	PublicKey  []byte
	Algorithm  int
	Generation uint64
	RPID       string
	EnrolledAt time.Time
	Status     string
	RevokedAt  *time.Time
	InternalUV bool
	AAGUID     []byte
	Format     string
}

func (c *Credential) Destroy() {
	if c == nil {
		return
	}
	zero(c.ID)
	c.ID = nil
}

func ReferenceForID(id []byte) string {
	digest := sha256.Sum256(id)
	return "fido2-es256-" + hex.EncodeToString(digest[:16])
}

type Enroller interface {
	Enroll(context.Context, Request) (Credential, error)
}

func ValidateCredential(c Credential) error {
	if c.Reference == "" || len(c.Reference) > 96 || len(c.ID) == 0 || len(c.ID) > 4096 || len(c.PublicKey) == 0 || len(c.PublicKey) > 4096 || c.Algorithm != ES256 || c.Generation == 0 || c.RPID != RPID || c.EnrolledAt.IsZero() || c.Status != "active" || c.RevokedAt != nil || !c.InternalUV || len(c.AAGUID) > 64 || c.Format != "packed" || c.Reference != ReferenceForID(c.ID) {
		return ErrDenied
	}
	if validatePublicKey(c.PublicKey) != nil {
		return ErrDenied
	}
	return nil
}

func validatePublicKey(der []byte) error {
	parsed, err := x509.ParsePKIXPublicKey(der)
	key, ok := parsed.(*ecdsa.PublicKey)
	if err != nil || !ok || key.Curve != elliptic.P256() || key.X == nil || key.Y == nil || !key.Curve.IsOnCurve(key.X, key.Y) {
		return ErrCorrupt
	}
	return nil
}

func zero(value []byte) {
	for i := range value {
		value[i] = 0
	}
}
