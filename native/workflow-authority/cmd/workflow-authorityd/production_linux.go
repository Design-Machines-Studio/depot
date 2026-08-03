//go:build linux

package main

import (
	"context"

	authorityruntime "designmachines.dev/workflow-authority/internal/runtime"
)

func production(ctx context.Context) error { return authorityruntime.ServeProduction(ctx) }
