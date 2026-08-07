// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "WorkflowAuthorityMacOS",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "AuthorityClientCore", targets: ["AuthorityClientCore"]),
        .executable(name: "wk-authority", targets: ["AuthorityClient"]),
    ],
    dependencies: [],
    targets: [
        .target(name: "AuthorityProtocol"),
        .target(name: "AuthorityClientCore", dependencies: ["AuthorityProtocol"]),
        .executableTarget(name: "AuthorityClient", dependencies: ["AuthorityClientCore"]),
        .testTarget(
            name: "AuthorityProtocolTests",
            dependencies: ["AuthorityProtocol", "AuthorityClientCore"]
        ),
    ],
    swiftLanguageModes: [.v6]
)
