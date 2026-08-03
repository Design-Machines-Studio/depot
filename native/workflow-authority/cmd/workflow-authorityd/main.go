package main

import (
	"context"
	"fmt"
	"os"

	"designmachines.dev/workflow-authority/internal/authority"
	"designmachines.dev/workflow-authority/internal/provider"
)

// main performs dependency readiness before any socket is created. The native
// IPC accept loop is added only once all production dependencies are available.
func main() {
	if err := readiness(context.Background()); err != nil {
		fmt.Fprintln(os.Stderr, "workflow-authorityd: startup dependencies unavailable")
		os.Exit(78)
	}
}

func readiness(ctx context.Context) error {
	fido := authority.NewFIDOAdapter()
	ready := fido.Readiness(ctx)
	if !ready.Production || !ready.InternalUV || ready.Adapter != "libfido2" || ready.Version != authority.FIDO2Version {
		return provider.ErrStartup
	}
	credential, err := (provider.FileCredentialReader{Path: provider.ProductionCredentialPath, Owner: 0}).Read(ctx)
	if err != nil {
		return provider.ErrStartup
	}
	credential.Destroy()
	policy, _, err := provider.ReadProductionPolicy(ctx, 0)
	if err != nil {
		return provider.ErrStartup
	}
	for i := range policy {
		policy[i] = 0
	}
	_ = provider.ProductionTransport()
	return provider.ErrStartup // no socket readiness until the IPC composition lands.
}
