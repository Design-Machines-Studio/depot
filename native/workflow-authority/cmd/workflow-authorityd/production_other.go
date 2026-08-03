//go:build !linux

package main

import (
	"context"
	"errors"
)

func production(context.Context) error { return errors.New("linux production authority unavailable") }
