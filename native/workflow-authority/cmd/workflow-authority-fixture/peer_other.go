//go:build fixture && !darwin && !linux

package main

import (
	"net"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/ipc"
)

// No peer authentication exists for this host. The fixture fails closed rather
// than inventing a peer identity.
const peerSource = "unsupported"

type unsupportedPeers struct{}

func (unsupportedPeers) Authenticate(net.Conn) (authority.Peer, error) {
	return authority.Peer{}, authority.ErrDenied
}

func fixturePeerAuthenticator(uint32) ipc.PeerAuthenticator { return unsupportedPeers{} }

func fixtureGuardConn(net.Conn) (ipc.GuardedConn, error) { return nil, authority.ErrDenied }
