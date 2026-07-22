"""Shared validation for executable argument arrays."""

from __future__ import annotations

import re
from pathlib import Path

from .redaction import contains_high_confidence_secret, normalize_durable_string


MAX_ARGV_ITEMS = 256
MAX_ARGUMENT_LENGTH = 4096

_SHELL_EXECUTABLES = frozenset({
    "ash", "bash", "csh", "dash", "fish", "ksh", "mksh", "powershell",
    "cmd", "cmd.exe", "powershell.exe", "pwsh", "pwsh.exe", "sh", "tcsh",
    "yash", "zsh",
})
_ENVIRONMENT_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def _uses_shell_command_string(argv: tuple[str, ...]) -> bool:
    initial_name = Path(argv[0]).name.casefold()
    if initial_name.endswith(".exe"):
        initial_name = initial_name[:-4]
    shell_index = 0
    if initial_name == "env":
        shell_index = 1
        while shell_index < len(argv):
            option = argv[shell_index]
            if option.startswith("-") and not option.startswith("--") and len(option) > 2:
                cluster = option[1:]
                for position, marker in enumerate(cluster):
                    if marker == "S":
                        return True
                    if marker in {"u", "C"}:
                        shell_index += 2 if position == len(cluster) - 1 else 1
                        break
                else:
                    shell_index += 1
                continue
            if (
                option == "-S" or option.startswith("-S")
                or option == "--split-string" or option.startswith("--split-string=")
            ):
                return True
            if _ENVIRONMENT_ASSIGNMENT.fullmatch(option):
                shell_index += 1
                continue
            if option in {"-u", "--unset", "-C", "--chdir"}:
                shell_index += 2
                continue
            if option.startswith(("--unset=", "--chdir=")) or option in {"-", "-i", "--ignore-environment"}:
                shell_index += 1
                continue
            if option.startswith(("-u", "-C")) and len(option) > 2:
                shell_index += 1
                continue
            if option == "--":
                shell_index += 1
            break
    if shell_index >= len(argv):
        return False
    shell_name = Path(argv[shell_index]).name.casefold()
    if shell_name.endswith(".exe") and shell_name[:-4] in _SHELL_EXECUTABLES:
        shell_name = shell_name[:-4]
    if shell_name not in _SHELL_EXECUTABLES:
        return False
    options = argv[shell_index + 1:]
    option_index = 0
    value_parameters = {
        "configurationfile", "configurationname", "custompipename", "executionpolicy",
        "inputformat", "outputformat", "settingsfile", "version", "windowstyle",
        "workingdirectory",
    }
    while option_index < len(options):
        option = options[option_index]
        if option == "--":
            break
        folded = option.casefold()
        if shell_name == "cmd":
            if folded.startswith(("/c", "/k")):
                return True
            if option.startswith(("/", "-")):
                option_index += 1
                continue
            break
        if shell_name in {"powershell", "pwsh"}:
            if not option.startswith("-"):
                break
            parameter = folded.lstrip("-")
            if (
                parameter in {"c", "cwa", "ec"}
                or (len(parameter) >= 2 and "command".startswith(parameter))
                or "encodedcommand".startswith(parameter)
                or parameter == "commandwithargs"
            ):
                return True
            if parameter == "f" or (len(parameter) >= 2 and "file".startswith(parameter)):
                break
            matches = {name for name in value_parameters if len(parameter) >= 2 and name.startswith(parameter)}
            if parameter in {"config", "ep", "o", "of", "settings", "v", "w", "wd"} or len(matches) == 1:
                option_index += 2
            else:
                option_index += 1
            continue
        if not option.startswith(("-", "+")):
            break
        if folded == "--command" or folded.startswith("--command="):
            return True
        if shell_name == "fish" and (
            folded == "--init-command" or folded.startswith("--init-command=")
            or (len(option) > 1 and option[0] in "-+" and "C" in option[1:])
        ):
            return True
        if option in {"--rcfile", "--init-file"}:
            option_index += 2
            continue
        if option.startswith(("--rcfile=", "--init-file=")):
            option_index += 1
            continue
        if option.startswith("--"):
            option_index += 1
            continue
        if len(option) > 1 and option[0] in "-+" and "c" in option[1:]:
            return True
        option_index += 2 if option in {"-O", "-o"} else 1
    return False


def _passes_secret_value(argv: tuple[str, ...]) -> bool:
    for index, argument in enumerate(argv):
        flag, separator, _value = argument.partition("=")
        if not flag.startswith(("-", "/")):
            continue
        compact = re.sub(r"[^a-z0-9]", "", flag.casefold())
        segments = {part for part in flag.casefold().replace("_", "-").split("-") if part}
        secret = compact.endswith((
            "apikey", "accesskey", "secretkey", "privatekey", "clientsecret",
            "clientauth", "authorization", "password", "passwd", "passphrase",
            "credential", "credentials", "creds", "cookie", "dsn", "bearer", "token",
        )) or bool(segments & {
            "key", "secret", "password", "passwd", "authorization", "passphrase",
            "credential", "credentials", "creds", "cookie", "dsn", "bearer",
        }) or (
            "token" in segments and (len(segments) == 1 or bool(segments & {
                "access", "api", "auth", "bearer", "client", "github", "oauth",
                "private", "refresh", "session",
            }))
        )
        if secret and (separator or index + 1 < len(argv)):
            return True
    return False


def validate_safe_argv(value, *, name: str = "argv") -> tuple[str, ...]:
    """Return one immutable safe argv or raise a bounded ValueError."""
    # Public contract documents are JSON-shaped. Keep this list-only boundary
    # identical to the pre-extraction behavioral-contract validator; callers
    # that need immutability receive the tuple returned below.
    if type(value) is not list or not value or len(value) > MAX_ARGV_ITEMS:
        raise ValueError(f"invalid {name}")
    argv = []
    for argument in value:
        if (
            type(argument) is not str or not argument
            or len(argument) > MAX_ARGUMENT_LENGTH
            or "\x00" in argument or any(ord(char) < 0x20 for char in argument)
            or contains_high_confidence_secret(argument)
        ):
            raise ValueError(f"invalid {name} argument")
        try:
            if normalize_durable_string(argument) != argument:
                raise ValueError(f"unsafe {name} argument")
        except ValueError:
            raise ValueError(f"unsafe {name} argument") from None
        argv.append(argument)
    result = tuple(argv)
    if _uses_shell_command_string(result):
        raise ValueError("shell command snippets are not executable checks")
    if any(_ENVIRONMENT_ASSIGNMENT.fullmatch(argument) for argument in result):
        raise ValueError("executable checks must not embed environment values")
    if _passes_secret_value(result):
        raise ValueError("executable checks must not embed secret values")
    return result
