//go:build linux

package main

import (
	"errors"
	"os"
	"syscall"
)

const pipeFSMagic = 0x50495045

func validateResponsePipe(pipe *os.File) error {
	info, err := pipe.Stat()
	if err != nil || info.Mode()&os.ModeNamedPipe == 0 || info.Mode().IsRegular() {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	flags, _, errno := syscall.Syscall(syscall.SYS_FCNTL, pipe.Fd(), uintptr(syscall.F_GETFL), 0)
	if errno != 0 || (int(flags)&syscall.O_ACCMODE != syscall.O_WRONLY && int(flags)&syscall.O_ACCMODE != syscall.O_RDWR) {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	var filesystem syscall.Statfs_t
	if err := syscall.Fstatfs(int(pipe.Fd()), &filesystem); err != nil || uint64(filesystem.Type) != pipeFSMagic {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	return nil
}
