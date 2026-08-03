//go:build linux

package ipc

import (
	"errors"
	"net"
	"syscall"

	"designmachines.dev/workflow-authority/internal/authority"
)

type LinuxPeerAuthenticator struct {
	AllowedUIDs map[uint32]struct{}
}

func (a LinuxPeerAuthenticator) Authenticate(conn net.Conn) (authority.Peer, error) {
	raw, ok := conn.(syscall.Conn)
	if !ok {
		return authority.Peer{}, authority.ErrDenied
	}
	control, err := raw.SyscallConn()
	if err != nil {
		return authority.Peer{}, authority.ErrDenied
	}
	var credential *syscall.Ucred
	var socketErr error
	if err := control.Control(func(fd uintptr) {
		credential, socketErr = syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
	}); err != nil || socketErr != nil || credential == nil || credential.Pid < 1 {
		return authority.Peer{}, authority.ErrDenied
	}
	if _, allowed := a.AllowedUIDs[credential.Uid]; !allowed {
		return authority.Peer{}, authority.ErrDenied
	}
	return authority.Peer{UID: credential.Uid, PID: credential.Pid}, nil
}

type linuxGuardedConn struct{ *net.UnixConn }

func GuardLinuxUnixConn(conn net.Conn) (GuardedConn, error) {
	unix, ok := conn.(*net.UnixConn)
	if !ok {
		return nil, authority.ErrDenied
	}
	return &linuxGuardedConn{UnixConn: unix}, nil
}

func (c *linuxGuardedConn) Receive(payload []byte) (int, error) {
	oob := make([]byte, syscall.CmsgSpace(4))
	n, oobn, flags, _, err := c.ReadMsgUnix(payload, oob)
	if err != nil {
		return n, err
	}
	if oobn != 0 || flags&syscall.MSG_CTRUNC != 0 {
		zero(payload[:n])
		return 0, errors.New("ancillary_data_rejected")
	}
	return n, nil
}
