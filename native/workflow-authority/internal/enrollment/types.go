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
	"fmt"
	"strings"
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
	// DeviceSelector is a content-free selector obtained from trusted admin
	// manifest inspection. It is never a device path and must not originate in
	// repository-worker argv or environment.
	DeviceSelector string
}

type DeviceManifest struct {
	Path, Manufacturer, Product string
	VendorID, ProductID         uint16
}

func SelectDevice(devices []DeviceManifest, requested string) (DeviceManifest, string, error) {
	if len(devices) == 0 || len(devices) > 16 || requested != "" && !validSelector(requested) {
		return DeviceManifest{}, "", ErrUnavailable
	}
	type candidate struct {
		device   DeviceManifest
		selector string
	}
	candidates := make([]candidate, 0, len(devices))
	seen := map[string]struct{}{}
	for _, device := range devices {
		if device.Path == "" || len(device.Path) > 1023 || strings.ContainsRune(device.Path, 0) || len(device.Manufacturer) > 255 || len(device.Product) > 255 || strings.ContainsRune(device.Manufacturer, 0) || strings.ContainsRune(device.Product, 0) {
			return DeviceManifest{}, "", ErrUnavailable
		}
		identity := fmt.Sprintf("%04x:%04x\x00%s\x00%s\x00%s", device.VendorID, device.ProductID, device.Manufacturer, device.Product, device.Path)
		digest := sha256.Sum256([]byte(identity))
		selector := "sha256:" + hex.EncodeToString(digest[:])
		if _, duplicate := seen[selector]; duplicate {
			return DeviceManifest{}, "", ErrConflict
		}
		seen[selector] = struct{}{}
		candidates = append(candidates, candidate{device, selector})
	}
	if requested == "" {
		if len(candidates) != 1 {
			return DeviceManifest{}, "", ErrConflict
		}
		return candidates[0].device, candidates[0].selector, nil
	}
	var selected candidate
	matches := 0
	for _, candidate := range candidates {
		if candidate.selector == requested {
			selected = candidate
			matches++
		}
	}
	if matches != 1 {
		return DeviceManifest{}, "", ErrConflict
	}
	return selected.device, selected.selector, nil
}

type Credential struct {
	Reference      string
	ID             []byte
	PublicKey      []byte
	Algorithm      int
	Generation     uint64
	RPID           string
	EnrolledAt     time.Time
	Status         string
	RevokedAt      *time.Time
	InternalUV     bool
	AAGUID         []byte
	Format         string
	DeviceSelector string
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
	if c.Reference == "" || len(c.Reference) > 96 || len(c.ID) == 0 || len(c.ID) > 4096 || len(c.PublicKey) == 0 || len(c.PublicKey) > 4096 || c.Algorithm != ES256 || c.Generation == 0 || c.RPID != RPID || c.EnrolledAt.IsZero() || c.Status != "active" || c.RevokedAt != nil || !c.InternalUV || len(c.AAGUID) != 16 || c.Format != "packed" || c.Reference != ReferenceForID(c.ID) || !validSelector(c.DeviceSelector) {
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
