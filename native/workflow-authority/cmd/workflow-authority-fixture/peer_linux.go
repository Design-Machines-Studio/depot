//go:build fixture && linux

package main

import (
	"net"

	"designmachines.dev/workflow-authority/internal/ipc"
)

// On Linux the fixture uses the production peer authenticator and guard, so
// peer UID and PID are fully kernel-derived and the ancillary-data rejection
// lane is genuinely exercised. Both are GAPs on darwin.
const peerSource = "linux-so-peercred"

func fixturePeerAuthenticator(owner uint32) ipc.PeerAuthenticator {
	return ipc.LinuxPeerAuthenticator{AllowedUIDs: map[uint32]struct{}{owner: {}}}
}

func fixtureGuardConn(conn net.Conn) (ipc.GuardedConn, error) {
	return ipc.GuardLinuxUnixConn(conn)
}
