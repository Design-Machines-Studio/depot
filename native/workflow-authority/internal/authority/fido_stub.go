//go:build !linux || !cgo || !libfido2

package authority

import "context"

type unavailableFIDO struct{}

func NewFIDOAdapter() FIDO { return unavailableFIDO{} }
func (unavailableFIDO) Readiness(context.Context) Readiness {
	return Readiness{Production: false, Adapter: "stub", Version: "unavailable", InternalUV: false}
}
func (unavailableFIDO) Assert(context.Context, []byte, Credential) (Assertion, error) {
	return Assertion{}, ErrUnavailable
}
func (unavailableFIDO) Verify(context.Context, []byte, Credential, Assertion) error {
	return ErrUnavailable
}
