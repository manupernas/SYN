// swift-tools-version: 5.10
import PackageDescription
let package = Package(
    name: "syn-dvr-engine",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "syn-dvr-engine", targets: ["syn-dvr-engine"])],
    targets: [
        .executableTarget(name: "syn-dvr-engine", path: "Sources/syn-dvr-engine")
    ]
)
