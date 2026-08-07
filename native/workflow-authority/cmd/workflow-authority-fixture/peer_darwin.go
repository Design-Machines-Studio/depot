//go:build fixture && darwin

package main

import (
	"net"
	"os"
	"syscall"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/ipc"
)

// macOS getsockopt level and option for local (Unix domain) sockets. Go's
// syscall package does not export them. LOCAL_PEERPID yields the connecting
// process id as the kernel sees it, which is what the client verifies:
// client.go asserts challenge.PeerPID equals its own os.Getpid().
const (
	solLocal     = 0
	localPeerPID = 0x002
)

// peerSource is reported in the ready document so the harness can label what
// the daemon actually observed. On darwin the PID is kernel-derived but the
// UID is assumed from the fixture's own euid: macOS LOCAL_PEERCRED returns an
// xucred that Go's syscall package cannot decode, and the product ships no
// darwin peer authenticator. Daemon-side UID authentication therefore remains
// a GAP on this host, and the harness reports it as one.
const peerSource = "darwin-local-peerpid"

type darwinPeers struct{ allowed map[uint32]struct{} }

func (p darwinPeers) Authenticate(conn net.Conn) (authority.Peer, error) {
	raw, ok := conn.(syscall.Conn)
	if !ok {
		return authority.Peer{}, authority.ErrDenied
	}
	control, err := raw.SyscallConn()
	if err != nil {
		return authority.Peer{}, authority.ErrDenied
	}
	var pid int
	var socketErr error
	if err := control.Control(func(fd uintptr) {
		pid, socketErr = syscall.GetsockoptInt(int(fd), solLocal, localPeerPID)
	}); err != nil || socketErr != nil || pid < 1 {
		return authority.Peer{}, authority.ErrDenied
	}
	uid := uint32(os.Geteuid())
	if _, allowed := p.allowed[uid]; !allowed {
		return authority.Peer{}, authority.ErrDenied
	}
	return authority.Peer{UID: uid, PID: int32(pid)}, nil
}

func fixturePeerAuthenticator(owner uint32) ipc.PeerAuthenticator {
	return darwinPeers{allowed: map[uint32]struct{}{owner: {}}}
}

type darwinGuard struct{ net.Conn }

func (c *darwinGuard) Receive(payload []byte) (int, error) { return c.Read(payload) }

// The production Linux guard rejects ancillary data on every read. There is no
// darwin equivalent in the product, so this guard is a plain read and the
// ancillary-data rejection lane is a GAP on this host.
func fixtureGuardConn(conn net.Conn) (ipc.GuardedConn, error) {
	if _, ok := conn.(*net.UnixConn); !ok {
		return nil, authority.ErrDenied
	}
	return &darwinGuard{Conn: conn}, nil
}
