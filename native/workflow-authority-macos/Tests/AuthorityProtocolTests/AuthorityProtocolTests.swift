import Foundation
import Testing
@testable import AuthorityProtocol
@testable import AuthorityClientCore

private let digest = "sha256:" + String(repeating: "a", count: 64)
private let nonce = String(repeating: "b", count: 64)
private let commit = String(repeating: "c", count: 40)

private func request() throws -> AuthorityRequest {
    let bindings = try RequestBindings(
        repositoryDescriptorID: "repository", repositoryScopeDigest: digest,
        runID: "run", authorizationEventID: "event", profileRef: "profile",
        profileDigest: digest, authorityDigest: digest, trustedBaseCommit: commit,
        candidateCommit: commit, candidateSnapshotDigest: digest,
        includeWorktree: false, cadenceBoundary: "chunk", laneID: nil,
        provider: nil, substrateDigest: nil
    )
    return try AuthorityRequest(
        operation: .approveProfile, bindings: bindings, nonce: nonce, sequence: 1,
        keyID: "key", bootID: "boot", sessionID: "session",
        issuedAt: "2026-08-02T00:00:00Z", expiresAt: "2026-08-02T00:01:00Z",
        documentDigest: digest
    )
}

@Suite("Authority protocol")
struct AuthorityProtocolTests {
    @Test
    func testCanonicalBytesMatchPythonFixture() throws {
        let data = try CanonicalJSON.encode(request())
        let expected = #"{"artifact_role":"workflow_authority_request","bindings":{"authority_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","authorization_event_id":"event","cadence_boundary":"chunk","candidate_commit":"cccccccccccccccccccccccccccccccccccccccc","candidate_snapshot_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","include_worktree":false,"lane_id":null,"profile_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","profile_ref":"profile","provider":null,"repository_descriptor_id":"repository","repository_scope_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","run_id":"run","substrate_digest":null,"trusted_base_commit":"cccccccccccccccccccccccccccccccccccccccc"},"boot_id":"boot","document_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expires_at":"2026-08-02T00:01:00Z","issued_at":"2026-08-02T00:00:00Z","key_id":"key","nonce":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","operation":"approve_profile","schema_version":2,"sequence":1,"session_id":"session"}"#
        #expect(data == Data(expected.utf8))
        #expect(try CanonicalJSON.encode(request()) == data)
        #expect(try CanonicalJSON.decode(AuthorityRequest.self, from: data) == request())
    }

    @Test
    func testRejectsUnknownDuplicateNoncanonicalAndOversizedFrames() throws {
        let valid = try CanonicalJSON.encode(request())
        var object = try #require(JSONSerialization.jsonObject(with: valid) as? [String: Any])
        object["unknown"] = true
        let unknown = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: unknown) }
        let duplicate = Data(#"{"schema_version":2,"schema_version":2}"#.utf8)
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: duplicate) }
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: Data(" \n".utf8) + valid) }
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: Data(repeating: 32, count: AuthorityConstants.maximumFrameBytes + 1)) }
    }

    @Test
    func testRejectsTruncationExtraFrameInvalidUnicodeAndAmbiguousNumber() throws {
        let valid = try CanonicalJSON.encode(request())
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: Data(valid.dropLast())) }
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: valid + valid) }
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: Data([0x7b, 0x22, 0x78, 0x22, 0x3a, 0xff, 0x7d])) }
        let fractional = Data(#"{"schema_version":2.0}"#.utf8)
        #expect(throws: (any Error).self) { try CanonicalJSON.decode(AuthorityRequest.self, from: fractional) }
    }

    @Test
    func testOperationSetIsExact() {
        #expect(Set(AuthorityOperation.allCases.map(\.rawValue)) == Set([
            "approve_profile", "plan_verification", "run_verification", "record_result",
            "provider_attestation", "verify_envelope", "substrate_enroll_endpoint",
            "substrate_prepare", "substrate_inspect", "substrate_execute", "substrate_cleanup",
            "key_enroll", "key_rotate", "key_revoke", "status", "doctor",
        ]))
    }

    @Test
    func testDiagnosticsAreClosedAndRedacting() {
        let sink = CapturingSink()
        let logger = RedactingDiagnosticLogger(sink: sink)
        logger.record(.responseRejected)
        let output = sink.lines.joined()
        #expect(output == "wk-authority: response_rejected")
        for marker in ["PUBLIC-MARKER", nonce, "p256-sha256:", "authorization_context", "docker_endpoint"] {
            #expect(!output.contains(marker))
        }
    }

    @Test
    func testSafeErrorsHaveStableExitCodes() {
        #expect(AuthorityClientFailure(.unavailable).exitCode == .unavailable)
        #expect(AuthorityClientFailure(.unauthorized).exitCode == .unauthorized)
        #expect(AuthorityClientFailure(.cancelled).exitCode == .cancelled)
        #expect(AuthorityClientFailure(.stale).exitCode == .stale)
        #expect(AuthorityClientFailure(.malformed).exitCode == .malformed)
        #expect(AuthorityClientFailure(.internalFailure).exitCode == .internalFailure)
    }

    @Test
    func testSessionIsSingleUseAndCancellationClosesTransport() async throws {
        let transport = BlockingTransport()
        let client = AuthorityClientCore(transport: transport)
        let task = Task { try await client.exchange(CanonicalJSON.encode(request())) }
        await Task.yield()
        task.cancel()
        _ = await task.result
        #expect(transport.wasCancelled)
        do {
            _ = try await client.exchange(CanonicalJSON.encode(request()))
            Issue.record("a second operation must fail closed")
        } catch let failure as AuthorityClientFailure {
            #expect(failure.reason == .malformed)
        }
    }
}

private final class CapturingSink: DiagnosticSink, @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [String] = []
    var lines: [String] { lock.withLock { storage } }
    func emit(_ line: String) { lock.withLock { storage.append(line) } }
}

private final class BlockingTransport: AuthorityTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var cancelled = false
    var wasCancelled: Bool { lock.withLock { cancelled } }
    func exchange(_ request: Data, maximumResponseBytes: Int) async throws -> Data {
        while !wasCancelled { await Task.yield() }
        throw CancellationError()
    }
    func cancel() { lock.withLock { cancelled = true } }
}
