//go:build !linux && !darwin

package main

import (
	"errors"
	"os"
)

func validateResponsePipe(*os.File) error {
	return errors.New("fd3 anonymous-pipe proof unavailable on this host")
}

func validateInputFile(*os.File) error {
	return errors.New("input descriptor proof unavailable on this host")
}
