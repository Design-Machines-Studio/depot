# Workflow Authority macOS foundation

This package is source/test scaffolding and **not a trusted installation**. It is inert unless built and invoked directly. Ad-hoc builds cannot satisfy the signed production client identity checks planned for the installed broker.

Development checks require only Swift 6 Command Line Tools and must remain offline:

```sh
swift package --package-path native/workflow-authority-macos dump-package
swift test --package-path native/workflow-authority-macos
```

Do not install, sign, notarize, register launchd jobs, modify privileged paths, access live Keychain state, or treat local build output as production evidence. The client uses only the compiled Mach service identifier; repository files, arguments, environment variables, working directory, `PATH`, and symlinks cannot redirect it.

Chunk 02 owns only the protocol and client foundation declared here. Chunk 03 is the sole later owner of `Package.swift` expansion for GUI agent, root service, admin, packaging, or other targets; later workers must not invent undeclared targets concurrently.
