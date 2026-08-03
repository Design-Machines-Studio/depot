//go:build linux

package client

import (
	"net"
	"syscall"
)

func requirePeerOwner(conn net.Conn, expected uint32) error {
	raw, ok := conn.(syscall.Conn)
	if !ok {
		return ErrUnavailable
	}
	control, err := raw.SyscallConn()
	if err != nil {
		return ErrUnavailable
	}
	var peerErr error
	if control.Control(func(fd uintptr) {
		credential, err := syscall.GetsockoptUcred(int(fd), syscall.SOL_SOCKET, syscall.SO_PEERCRED)
		if err != nil || credential.Uid != expected || credential.Pid < 1 {
			peerErr = ErrUnavailable
		}
	}) != nil || peerErr != nil {
		return ErrUnavailable
	}
	return nil
}
