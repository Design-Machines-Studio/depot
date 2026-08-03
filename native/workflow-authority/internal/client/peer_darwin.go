//go:build darwin && cgo

package client

/*
#include <sys/types.h>
#include <unistd.h>
*/
import "C"

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
		var uid C.uid_t
		var gid C.gid_t
		if C.getpeereid(C.int(fd), &uid, &gid) != 0 || uint32(uid) != expected {
			peerErr = ErrUnavailable
		}
	}) != nil || peerErr != nil {
		return ErrUnavailable
	}
	return nil
}
