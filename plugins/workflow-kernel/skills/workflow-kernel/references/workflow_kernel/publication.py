"""Trusted publication transaction for validated inspection results."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from ._files import _OwnedResourceScope, bind_durable_path
from .inspection import (
    InspectionError,
    authoritative_bytes,
    finalize_authoritative_result,
    load_host_publication_authority_key,
    normalize_owned_path,
    render_markdown,
    validate_authoritative_result,
    validate_published_outputs,
)


def _replace_bytes(path, encoded, suffix):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    binding = bind_durable_path(destination)
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        directory.revalidate()
        directory.regular_exists(binding.path.name)
        descriptor, temporary = directory.create_temporary(
            binding.path.name + ".tmp-",
            suffix,
        )
        owned.own_temporary(descriptor, temporary)
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("publication write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        directory.require_identity(descriptor, temporary)
        directory.replace(temporary, binding.path.name)
        owned.disown_temporary()
        directory.fsync()


def _replace_json(path, value):
    encoded = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    _replace_bytes(path, encoded, ".json")


def _output_guard(repository_root, authoritative_path, markdown_path):
    root = Path(repository_root).resolve(strict=True)
    destinations = (Path(authoritative_path), Path(markdown_path))
    if (
        destinations[0] == destinations[1]
        or destinations[0].resolve(strict=False)
        == destinations[1].resolve(strict=False)
    ):
        raise InspectionError("invalid_publication_outputs")
    for destination in destinations:
        if (
            not destination.resolve(strict=False).is_relative_to(root)
            or any(
                item.is_symlink()
                for item in (destination, *destination.parents)
            )
        ):
            raise InspectionError("invalid_publication_outputs")
        destination.parent.mkdir(parents=True, exist_ok=True)
    identities = {
        path.parent: (
            os.stat(path.parent, follow_symlinks=False).st_dev,
            os.stat(path.parent, follow_symlinks=False).st_ino,
        )
        for path in destinations
    }

    def revalidate():
        for parent, identity in identities.items():
            current = os.stat(parent, follow_symlinks=False)
            if (
                not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != identity
            ):
                raise InspectionError("publication_outputs_changed")
        for destination in destinations:
            try:
                entry = os.stat(destination, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(entry.st_mode):
                raise InspectionError("invalid_publication_outputs")
        if all(path.exists() for path in destinations) and os.path.samefile(
            *destinations
        ):
            raise InspectionError("invalid_publication_outputs")

    revalidate()
    return revalidate


def _write_snapshot_file(path, encoded):
    destination = Path(path)
    descriptor = None
    identity = None
    try:
        descriptor = os.open(
            destination,
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
            | getattr(os, "O_NOFOLLOW", 0),
            0o400,
        )
        opened = os.fstat(descriptor)
        identity = (opened.st_dev, opened.st_ino)
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("publication snapshot write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        entry = os.stat(destination, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o400
            or opened.st_size != len(encoded)
            or identity != (entry.st_dev, entry.st_ino)
        ):
            raise InspectionError("publication_action_not_verified")
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if identity is not None:
            try:
                entry = os.stat(destination, follow_symlinks=False)
                if (
                    stat.S_ISREG(entry.st_mode)
                    and (entry.st_dev, entry.st_ino) == identity
                ):
                    destination.unlink()
            except OSError:
                pass
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _fsync_directory(path):
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _discard_stage(stage):
    stage = Path(stage)
    try:
        os.chmod(stage, 0o700)
    except OSError:
        return
    for name in ("authoritative.json", "report.md"):
        try:
            (stage / name).unlink()
        except FileNotFoundError:
            pass
    stage.rmdir()


def _commit_snapshot(root, published, markdown, publication_key):
    publications = root / ".inspection-publications"
    result_root = publications / published["inspection_id"]
    for directory in (publications, result_root):
        created = False
        try:
            directory.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        entry = os.stat(directory, follow_symlinks=False)
        if (
            not stat.S_ISDIR(entry.st_mode)
            or directory.is_symlink()
            or (
                hasattr(os, "getuid")
                and entry.st_uid != os.getuid()
            )
            or stat.S_IMODE(entry.st_mode) & 0o022
        ):
            raise InspectionError("invalid_publication_outputs")
        if created:
            _fsync_directory(directory.parent)
    digest = published["publication_state_digest"].removeprefix("sha256:")
    destination = result_root / digest
    stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=result_root))
    os.chmod(stage, 0o700)
    try:
        _write_snapshot_file(
            stage / "authoritative.json",
            authoritative_bytes(
                published,
                publication_authority_key=publication_key,
            ),
        )
        _write_snapshot_file(stage / "report.md", markdown.encode("utf-8"))
        os.chmod(stage, 0o500)
        _fsync_directory(stage)
        try:
            os.rename(stage, destination)
        except OSError:
            _discard_stage(stage)
            if not destination.is_dir() or destination.is_symlink():
                raise InspectionError(
                    "publication_action_not_verified"
                ) from None
        _fsync_directory(result_root)
    except BaseException:
        if stage.exists():
            try:
                _discard_stage(stage)
            except OSError:
                pass
        raise
    return destination


def publish_authoritative_result(input_result, repository_root):
    """Publish JSON and Markdown as one guarded lifecycle transaction."""
    publication_key = load_host_publication_authority_key(repository_root)
    current = validate_authoritative_result(
        input_result,
        publication_authority_key=publication_key,
    )
    if current["publication_status"] != "authoritative_json_ready":
        raise InspectionError("invalid_publication_transition")
    outputs = current["profile_snapshot"]["outputs"]
    root = Path(repository_root).resolve(strict=True)
    markdown_path = root / normalize_owned_path(
        repository_root,
        outputs["markdown"],
    )
    authoritative_path = root / normalize_owned_path(
        repository_root,
        outputs["authoritative_json"],
    )
    revalidate = _output_guard(root, authoritative_path, markdown_path)
    markdown = render_markdown(
        current,
        publication_authority_key=publication_key,
    )
    _replace_json(authoritative_path, current)
    revalidate()
    _replace_bytes(markdown_path, markdown.encode("utf-8"), ".md")
    revalidate()
    rendered = finalize_authoritative_result(
        current,
        publication_status="markdown_rendered",
        publication_authority_key=publication_key,
        publication_repository_root=repository_root,
    )
    _replace_json(authoritative_path, rendered)
    revalidate()
    published = finalize_authoritative_result(
        rendered,
        publication_status="published",
        publication_authority_key=publication_key,
        publication_repository_root=repository_root,
    )
    try:
        _commit_snapshot(root, published, markdown, publication_key)
        validate_published_outputs(
            published,
            root,
            publication_authority_key=publication_key,
        )
        _replace_bytes(markdown_path, markdown.encode("utf-8"), ".md")
        revalidate()
        _replace_json(authoritative_path, published)
        revalidate()
    except BaseException as error:
        if isinstance(error, InspectionError):
            raise
        raise InspectionError("publication_action_not_verified") from None
    return published


__all__ = ["publish_authoritative_result"]
