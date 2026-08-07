//go:build fixture

// This file exists only under the `fixture` build tag. It is test scaffolding
// for the offline black-box acceptance harness and is absent from every
// untagged build, including `go build ./...` and the shipped binaries.
//
// It exposes no new production behavior: NewFixtureRunner sets the same
// unexported Runner fields that the in-package integration test already sets,
// and every path it accepts must be caller-supplied. Production callers still
// have only NewProduction, whose paths are fixed.

package client

import (
	"context"
	"net"
	"time"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/protocol"
)

// FixtureConfig carries the injected-root wiring for a harness Runner. Every
// field is required; NewFixtureRunner returns nil rather than defaulting a
// missing one, so a misconfigured harness fails closed instead of silently
// dialing a production path.
type FixtureConfig struct {
	SocketPath    string
	TrustPath     string
	Anchor        string
	ExpectedOwner uint32
	Now           func() time.Time
	FIDO          authority.FIDO
}

// NewFixtureRunner mirrors the wiring in integration_test.go exactly: the same
// fields, an ordinary Unix dialer, and an auto-approving consent confirmer.
// Consent confirmation is not what this harness proves -- the daemon-side
// challenge binding is -- so the confirmer is deliberately trivial.
func NewFixtureRunner(config FixtureConfig) *Runner {
	if config.SocketPath == "" || config.TrustPath == "" || config.Anchor == "" || config.Now == nil || config.FIDO == nil {
		return nil
	}
	r := &Runner{
		socketPath: config.SocketPath, trustPath: config.TrustPath,
		socketAnchor: config.Anchor, trustAnchor: config.Anchor,
		expectedOwner: config.ExpectedOwner, now: config.Now, fido: config.FIDO,
		confirm: func(context.Context, protocol.Challenge) error { return nil },
	}
	r.dial = func(ctx context.Context, path string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", path)
	}
	return r
}
