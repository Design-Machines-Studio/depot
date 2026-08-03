//go:build darwin

package main

import (
	"errors"
	"os"
	"syscall"
)

func validateResponsePipe(pipe *os.File) error {
	info, err := pipe.Stat()
	if err != nil || info.Mode()&os.ModeNamedPipe == 0 || info.Mode().IsRegular() {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Nlink != 0 {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	flags, _, errno := syscall.Syscall(syscall.SYS_FCNTL, pipe.Fd(), uintptr(syscall.F_GETFL), 0)
	if errno != 0 || (int(flags)&syscall.O_ACCMODE != syscall.O_WRONLY && int(flags)&syscall.O_ACCMODE != syscall.O_RDWR) {
		return errors.New("fd3 must be anonymous writable pipe")
	}
	return nil
}

func validateInputFile(input *os.File) error {
	info, err := input.Stat()
	if err != nil || (!info.Mode().IsRegular() && info.Mode()&os.ModeNamedPipe == 0) {
		return errors.New("input must be readable regular file or anonymous pipe")
	}
	flags, _, errno := syscall.Syscall(syscall.SYS_FCNTL, input.Fd(), uintptr(syscall.F_GETFL), 0)
	if errno != 0 || int(flags)&syscall.O_ACCMODE == syscall.O_WRONLY {
		return errors.New("input must be readable regular file or anonymous pipe")
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || (info.Mode().IsRegular() && stat.Nlink != 1) || (info.Mode()&os.ModeNamedPipe != 0 && stat.Nlink != 0) {
		return errors.New("input descriptor is not stable")
	}
	return nil
}
