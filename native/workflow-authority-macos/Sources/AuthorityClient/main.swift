import Foundation
import AuthorityClientCore
import AuthorityProtocol

private func boundedInput(arguments: [String]) throws -> Data {
    let handle: FileHandle
    switch arguments.count {
    case 1:
        handle = .standardInput
    case 3 where arguments[1] == "--input-fd":
        guard let descriptor = Int32(arguments[2]), descriptor >= 0 else { throw AuthorityClientFailure(.malformed) }
        handle = FileHandle(fileDescriptor: descriptor, closeOnDealloc: false)
    default:
        throw AuthorityClientFailure(.malformed)
    }
    var result = Data()
    while result.count <= AuthorityConstants.maximumFrameBytes {
        let remaining = AuthorityConstants.maximumFrameBytes + 1 - result.count
        guard let chunk = try handle.read(upToCount: min(65_536, remaining)), !chunk.isEmpty else { break }
        result.append(chunk)
    }
    guard !result.isEmpty && result.count <= AuthorityConstants.maximumFrameBytes else { throw AuthorityClientFailure(.malformed) }
    return result
}

@main
private enum Main {
    static func main() async {
        AuthorityEnvironment.clearSensitiveVariables()
        do {
            let request = try boundedInput(arguments: CommandLine.arguments)
            let response = try await AuthorityClientCore(transport: MachAuthorityTransport()).exchange(request)
            try FileHandle.standardOutput.write(contentsOf: response)
            Foundation.exit(ClientExitCode.success.rawValue)
        } catch let failure as AuthorityClientFailure {
            let line = "wk-authority: \(failure.reason.rawValue)\n"
            try? FileHandle.standardError.write(contentsOf: Data(line.utf8))
            Foundation.exit(failure.exitCode.rawValue)
        } catch {
            try? FileHandle.standardError.write(contentsOf: Data("wk-authority: authority_internal\n".utf8))
            Foundation.exit(ClientExitCode.internalFailure.rawValue)
        }
    }
}
