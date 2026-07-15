"""Core-owned exact boundary around the Docker I/O backend."""

from __future__ import annotations

from .model import invalid_policy


class DockerAdapter:
    """Final authority-bearing adapter; the backend remains replaceable I/O."""

    __slots__ = ("_backend",)

    def __init__(self, *args, **kwargs):
        # Delayed composition avoids a core/resources -> adapters dependency.
        # The public adapter module is fully loaded before callers construct us.
        from .adapters.docker import DockerBackend

        object.__setattr__(self, "_backend", DockerBackend(*args, **kwargs))

    def __getattr__(self, name):
        return getattr(self._backend, name)

    def __setattr__(self, name, value):
        raise AttributeError("DockerAdapter is immutable")

    def _trusted_backend(self):
        from .adapters.docker import DockerBackend

        backend = object.__getattribute__(self, "_backend")
        if type(backend) is not DockerBackend:
            raise invalid_policy("invalid_guarded_cleanup_execution")
        return backend, DockerBackend

    def revalidate_action(self, *args, **kwargs):
        backend, backend_type = self._trusted_backend()
        return backend_type.revalidate_action(backend, *args, **kwargs)

    def _reconcile_results(self, *args, **kwargs):
        backend, backend_type = self._trusted_backend()
        return backend_type._reconcile_results(backend, *args, **kwargs)

    def _result_transaction_id(self, *args, **kwargs):
        backend, backend_type = self._trusted_backend()
        return backend_type._result_transaction_id(backend, *args, **kwargs)

    def inventory(self):
        return self._backend.inventory()

    def inventory_registered(self, records):
        return self._backend.inventory_registered(records)
