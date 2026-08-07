import Foundation
import AuthorityProtocol

public protocol AuthorityTransport: Sendable {
    func exchange(_ request: Data, maximumResponseBytes: Int) async throws -> Data
    func cancel()
}

public enum ClientExitCode: Int32, Sendable {
    case success = 0, unavailable = 20, unauthorized = 21, cancelled = 22, stale = 23, malformed = 24, internalFailure = 25
}

public struct AuthorityClientFailure: Error, Equatable, Sendable {
    public let reason: SafeReasonCode
    public init(_ reason: SafeReasonCode) { self.reason = reason }
    public var exitCode: ClientExitCode {
        switch reason {
        case .unavailable: .unavailable
        case .unauthorized: .unauthorized
        case .cancelled: .cancelled
        case .stale: .stale
        case .malformed: .malformed
        case .internalFailure: .internalFailure
        }
    }
}

public actor AuthoritySession {
    private let transport: any AuthorityTransport
    private var consumed = false
    public init(transport: any AuthorityTransport) { self.transport = transport }

    public func exchange(_ requestData: Data) async throws -> Data {
        guard !consumed else { throw AuthorityClientFailure(.malformed) }
        consumed = true
        let request: AuthorityRequest
        do { request = try CanonicalJSON.decode(AuthorityRequest.self, from: requestData) }
        catch let failure as ProtocolFailure { throw AuthorityClientFailure(failure.reason) }
        catch { throw AuthorityClientFailure(.malformed) }

        return try await withTaskCancellationHandler {
            do {
                try Task.checkCancellation()
                let responseData = try await transport.exchange(requestData, maximumResponseBytes: AuthorityConstants.maximumFrameBytes)
                try Task.checkCancellation()
                let response = try CanonicalJSON.decode(ProviderResponse.self, from: responseData)
                guard response.request == request else { throw AuthorityClientFailure(.malformed) }
                switch response.status {
                case .approved: return responseData
                case .denied: throw AuthorityClientFailure(.unauthorized)
                case .cancelled: throw AuthorityClientFailure(.cancelled)
                case .unavailable: throw AuthorityClientFailure(.unavailable)
                }
            } catch is CancellationError {
                throw AuthorityClientFailure(.cancelled)
            } catch let failure as AuthorityClientFailure {
                throw failure
            } catch let failure as ProtocolFailure {
                throw AuthorityClientFailure(failure.reason)
            } catch {
                throw AuthorityClientFailure(.unavailable)
            }
        } onCancel: {
            transport.cancel()
        }
    }
}

public struct AuthorityClientCore: Sendable {
    private let session: AuthoritySession
    public init(transport: any AuthorityTransport) { session = AuthoritySession(transport: transport) }
    public func exchange(_ request: Data) async throws -> Data { try await session.exchange(request) }
}

#if os(macOS)
@objc private protocol AuthorityXPCService {
    func exchange(_ request: NSData, withReply reply: @escaping (NSData?, NSError?) -> Void)
}

private final class XPCReplyGate: @unchecked Sendable {
    private let lock = NSLock()
    private var completed = false
    func claim() -> Bool {
        lock.withLock {
            guard !completed else { return false }
            completed = true
            return true
        }
    }
}

public final class MachAuthorityTransport: AuthorityTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var connection: NSXPCConnection?
    public init() {}

    public func exchange(_ request: Data, maximumResponseBytes: Int) async throws -> Data {
        let current = NSXPCConnection(machServiceName: AuthorityConstants.rootMachService, options: [])
        current.remoteObjectInterface = NSXPCInterface(with: AuthorityXPCService.self)
        lock.withLock { connection = current }
        current.resume()
        defer { lock.withLock { connection = nil }; current.invalidate() }
        let response: Data = try await withCheckedThrowingContinuation { continuation in
            let gate = XPCReplyGate()
            let proxy = current.remoteObjectProxyWithErrorHandler { _ in
                if gate.claim() { continuation.resume(throwing: AuthorityClientFailure(.unavailable)) }
            } as? AuthorityXPCService
            guard let proxy else {
                if gate.claim() { continuation.resume(throwing: AuthorityClientFailure(.unavailable)) }
                return
            }
            proxy.exchange(request as NSData) { value, error in
                guard gate.claim() else { return }
                if error != nil { continuation.resume(throwing: AuthorityClientFailure(.unavailable)); return }
                guard let value else { continuation.resume(throwing: AuthorityClientFailure(.malformed)); return }
                continuation.resume(returning: value as Data)
            }
        }
        guard response.count <= maximumResponseBytes else { throw AuthorityClientFailure(.malformed) }
        return response
    }

    public func cancel() { lock.withLock { connection?.invalidate(); connection = nil } }
}
#else
public struct MachAuthorityTransport: AuthorityTransport {
    public init() {}
    public func exchange(_ request: Data, maximumResponseBytes: Int) async throws -> Data { throw AuthorityClientFailure(.unavailable) }
    public func cancel() {}
}
#endif

public enum AuthorityEnvironment {
    public static func clearSensitiveVariables() {
        for name in ["WK_AUTHORITY_SERVICE", "WK_AUTHORITY_COMMAND", "WK_AUTHORITY_SOCKET", "WK_AUTHORITY_KEY", "WORKFLOW_AUTHORITY_SERVICE", "WORKFLOW_AUTHORITY_COMMAND"] {
            unsetenv(name)
        }
    }
}
