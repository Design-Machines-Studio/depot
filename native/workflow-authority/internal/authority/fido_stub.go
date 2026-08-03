//go:build !linux || !cgo || !libfido2

package authority

import (
	"context"

	"designmachines.dev/workflow-authority/internal/enrollment"
)

type unavailableFIDO struct{}

func NewFIDOAdapter() FIDO                 { return unavailableFIDO{} }
func NewFIDOEnroller() enrollment.Enroller { return unavailableFIDO{} }
func (unavailableFIDO) Readiness(context.Context) Readiness {
	return Readiness{Production: false, Adapter: "stub", Version: "unavailable", InternalUV: false}
}
func (unavailableFIDO) ReadinessFor(context.Context, string) Readiness {
	return Readiness{Production: false, Adapter: "stub", Version: "unavailable", InternalUV: false}
}
func (unavailableFIDO) Assert(context.Context, []byte, Credential) (Assertion, error) {
	return Assertion{}, ErrUnavailable
}
func (unavailableFIDO) Verify(context.Context, []byte, Credential, Assertion) error {
	return ErrUnavailable
}
func (unavailableFIDO) Enroll(context.Context, enrollment.Request) (enrollment.Credential, error) {
	return enrollment.Credential{}, enrollment.ErrUnavailable
}
