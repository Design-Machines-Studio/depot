//go:build (!linux && !darwin) || (darwin && !cgo)

package client

import "net"

func requirePeerOwner(net.Conn, uint32) error { return ErrUnavailable }
