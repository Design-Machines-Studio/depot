package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
)

// main performs dependency readiness before any socket is created. The native
// IPC accept loop is added only once all production dependencies are available.
func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()
	if err := production(ctx); err != nil {
		fmt.Fprintln(os.Stderr, "workflow-authorityd: startup dependencies unavailable")
		os.Exit(78)
	}
}
