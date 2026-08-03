//go:build linux

package ipc

import (
	"errors"
	"net"
	"os"
	"syscall"
)

// ActivatedListener accepts only the fixed descriptor installed by systemd
// and verifies that its kernel pathname matches trusted composition.
func ActivatedListener(fd uintptr, expectedPath string) (net.Listener, error) {
	if fd != 3 || expectedPath == "" {
		return nil, errors.New("socket_activation_invalid")
	}
	file := os.NewFile(fd, "workflow-authority.socket")
	if file == nil {
		return nil, errors.New("socket_activation_invalid")
	}
	listener, err := net.FileListener(file)
	_ = file.Close()
	if err != nil {
		return nil, errors.New("socket_activation_invalid")
	}
	unix, ok := listener.(*net.UnixListener)
	if !ok || unix.Addr().Network() != "unix" || unix.Addr().String() != expectedPath {
		_ = listener.Close()
		return nil, errors.New("socket_activation_invalid")
	}
	info, err := os.Lstat(expectedPath)
	if err != nil || info.Mode()&os.ModeSocket == 0 || info.Mode()&os.ModeSymlink != 0 || info.Mode().Perm() != 0o660 {
		_ = listener.Close()
		return nil, errors.New("socket_activation_invalid")
	}
	stat, statOK := info.Sys().(*syscall.Stat_t)
	if !statOK || stat.Uid != 0 || stat.Nlink != 1 {
		_ = listener.Close()
		return nil, errors.New("socket_activation_invalid")
	}
	raw, err := unix.SyscallConn()
	if err != nil {
		_ = listener.Close()
		return nil, errors.New("socket_activation_invalid")
	}
	valid := false
	if raw.Control(func(descriptor uintptr) {
		accept, acceptErr := syscall.GetsockoptInt(int(descriptor), syscall.SOL_SOCKET, syscall.SO_ACCEPTCONN)
		typeValue, typeErr := syscall.GetsockoptInt(int(descriptor), syscall.SOL_SOCKET, syscall.SO_TYPE)
		valid = acceptErr == nil && typeErr == nil && accept == 1 && typeValue == syscall.SOCK_STREAM
	}) != nil || !valid {
		_ = listener.Close()
		return nil, errors.New("socket_activation_invalid")
	}
	return listener, nil
}
