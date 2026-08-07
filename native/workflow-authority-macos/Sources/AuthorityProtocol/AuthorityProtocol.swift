import Foundation

public enum AuthorityConstants {
    public static let schemaVersion = 2
    public static let authorityMode = "native_provider"
    public static let algorithm = "ecdsa-p256-sha256"
    public static let maximumFrameBytes = 1_048_576
    public static let maximumStringBytes = 4_096
    public static let maximumCollectionItems = 256
    public static let maximumJSONDepth = 16
    public static let maximumBinaryBytes = 262_144

    public static let clientExecutable = "/Library/Application Support/Design Machines/Workflow Authority/bin/wk-authority"
    public static let adminExecutable = "/Library/Application Support/Design Machines/Workflow Authority/bin/wk-authority-admin"
    public static let applicationBundle = "/Applications/Design Machines Workflow Authority.app"
    public static let rootServicePlist = "/Library/LaunchDaemons/\(rootMachService).plist"
    public static let guiAgentPlist = "/Library/LaunchAgents/studio.designmachines.workflow-authority.agent.plist"
    public static let rootServiceState = "/Library/Application Support/Design Machines/Workflow Authority/state"
    public static let rootMachService = "studio.designmachines.workflow-authority.service"
}

public enum ArtifactRole {
    public static let request = "workflow_authority_request"
    public static let grant = "workflow_authority_grant"
    public static let signatureEnvelope = "workflow_authority_signature_envelope"
    public static let publicKeyRecord = "workflow_authority_public_key_record"
    public static let providerResponse = "workflow_authority_provider_response"
    public static let evidenceDecision = "workflow_authority_evidence_decision"
    public static let substrateHandle = "repository_verification_substrate_handle"
    public static let substrateAttestation = "repository_verification_substrate_attestation"
}

public enum AuthorityOperation: String, Codable, CaseIterable, Sendable {
    case approveProfile = "approve_profile"
    case planVerification = "plan_verification"
    case runVerification = "run_verification"
    case recordResult = "record_result"
    case providerAttestation = "provider_attestation"
    case verifyEnvelope = "verify_envelope"
    case substrateEnrollEndpoint = "substrate_enroll_endpoint"
    case substratePrepare = "substrate_prepare"
    case substrateInspect = "substrate_inspect"
    case substrateExecute = "substrate_execute"
    case substrateCleanup = "substrate_cleanup"
    case keyEnroll = "key_enroll"
    case keyRotate = "key_rotate"
    case keyRevoke = "key_revoke"
    case status
    case doctor
}

public enum ProviderStatus: String, Codable, Sendable {
    case approved, denied, cancelled, unavailable
}

public enum SafeReasonCode: String, Codable, Error, CaseIterable, Sendable {
    case unavailable = "authority_provider_unavailable"
    case unauthorized = "authority_unauthorized"
    case cancelled = "authority_cancelled"
    case stale = "authority_stale"
    case malformed = "authority_provider_malformed"
    case internalFailure = "authority_internal"
}

public struct ProtocolFailure: Error, Equatable, Sendable {
    public let reason: SafeReasonCode
    public init(_ reason: SafeReasonCode) { self.reason = reason }
}

private struct AnyCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int? = nil
    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { return nil }
}

private func requireClosedKeys(_ decoder: Decoder, _ expected: Set<String>) throws {
    let container = try decoder.container(keyedBy: AnyCodingKey.self)
    guard Set(container.allKeys.map(\.stringValue)) == expected else {
        throw ProtocolFailure(.malformed)
    }
}

private func validString(_ value: String, allowEmpty: Bool = false, maximum: Int = AuthorityConstants.maximumStringBytes) -> Bool {
    (allowEmpty || !value.isEmpty) && value.utf8.count <= maximum
}

private func require(_ condition: @autoclosure () -> Bool, _ reason: SafeReasonCode = .malformed) throws {
    guard condition() else { throw ProtocolFailure(reason) }
}

private func isDigest(_ value: String) -> Bool {
    value.range(of: #"^sha256:[0-9a-f]{64}$"#, options: .regularExpression) != nil
}

private func isCommit(_ value: String) -> Bool {
    value.range(of: #"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"#, options: .regularExpression) != nil
}

private func isTimestamp(_ value: String) -> Bool {
    guard validString(value, maximum: 64) else { return false }
    return ISO8601DateFormatter().date(from: value) != nil
}

public struct RequestBindings: Codable, Equatable, Sendable {
    public let repositoryDescriptorID: String
    public let repositoryScopeDigest: String
    public let runID: String
    public let authorizationEventID: String
    public let profileRef: String
    public let profileDigest: String
    public let authorityDigest: String
    public let trustedBaseCommit: String
    public let candidateCommit: String
    public let candidateSnapshotDigest: String
    public let includeWorktree: Bool
    public let cadenceBoundary: String
    public let laneID: String?
    public let provider: String?
    public let substrateDigest: String?

    enum CodingKeys: String, CodingKey, CaseIterable {
        case repositoryDescriptorID = "repository_descriptor_id"
        case repositoryScopeDigest = "repository_scope_digest"
        case runID = "run_id"
        case authorizationEventID = "authorization_event_id"
        case profileRef = "profile_ref"
        case profileDigest = "profile_digest"
        case authorityDigest = "authority_digest"
        case trustedBaseCommit = "trusted_base_commit"
        case candidateCommit = "candidate_commit"
        case candidateSnapshotDigest = "candidate_snapshot_digest"
        case includeWorktree = "include_worktree"
        case cadenceBoundary = "cadence_boundary"
        case laneID = "lane_id"
        case provider, substrateDigest = "substrate_digest"
    }

    public init(
        repositoryDescriptorID: String, repositoryScopeDigest: String, runID: String,
        authorizationEventID: String, profileRef: String, profileDigest: String,
        authorityDigest: String, trustedBaseCommit: String, candidateCommit: String,
        candidateSnapshotDigest: String, includeWorktree: Bool, cadenceBoundary: String,
        laneID: String?, provider: String?, substrateDigest: String?
    ) throws {
        self.repositoryDescriptorID = repositoryDescriptorID
        self.repositoryScopeDigest = repositoryScopeDigest
        self.runID = runID
        self.authorizationEventID = authorizationEventID
        self.profileRef = profileRef
        self.profileDigest = profileDigest
        self.authorityDigest = authorityDigest
        self.trustedBaseCommit = trustedBaseCommit
        self.candidateCommit = candidateCommit
        self.candidateSnapshotDigest = candidateSnapshotDigest
        self.includeWorktree = includeWorktree
        self.cadenceBoundary = cadenceBoundary
        self.laneID = laneID
        self.provider = provider
        self.substrateDigest = substrateDigest
        try validate()
    }

    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue)))
        let c = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            repositoryDescriptorID: c.decode(String.self, forKey: .repositoryDescriptorID),
            repositoryScopeDigest: c.decode(String.self, forKey: .repositoryScopeDigest),
            runID: c.decode(String.self, forKey: .runID),
            authorizationEventID: c.decode(String.self, forKey: .authorizationEventID),
            profileRef: c.decode(String.self, forKey: .profileRef),
            profileDigest: c.decode(String.self, forKey: .profileDigest),
            authorityDigest: c.decode(String.self, forKey: .authorityDigest),
            trustedBaseCommit: c.decode(String.self, forKey: .trustedBaseCommit),
            candidateCommit: c.decode(String.self, forKey: .candidateCommit),
            candidateSnapshotDigest: c.decode(String.self, forKey: .candidateSnapshotDigest),
            includeWorktree: c.decode(Bool.self, forKey: .includeWorktree),
            cadenceBoundary: c.decode(String.self, forKey: .cadenceBoundary),
            laneID: c.decodeIfPresent(String.self, forKey: .laneID),
            provider: c.decodeIfPresent(String.self, forKey: .provider),
            substrateDigest: c.decodeIfPresent(String.self, forKey: .substrateDigest)
        )
    }

    private func validate() throws {
        for value in [repositoryDescriptorID, runID, authorizationEventID, profileRef] { try require(validString(value)) }
        for value in [repositoryScopeDigest, profileDigest, authorityDigest, candidateSnapshotDigest] { try require(isDigest(value)) }
        try require(isCommit(trustedBaseCommit) && isCommit(candidateCommit))
        try require(["chunk", "revision_batch", "execution_level", "merge_candidate", "post_merge"].contains(cadenceBoundary))
        try require(laneID.map { validString($0) } ?? true)
        try require(provider.map { ["github", "blueprint", "other"].contains($0) } ?? true)
        try require(substrateDigest.map(isDigest) ?? true)
    }
}

public struct AuthorityRequest: Codable, Equatable, Sendable {
    public let schemaVersion: Int
    public let artifactRole: String
    public let operation: AuthorityOperation
    public let bindings: RequestBindings
    public let nonce: String
    public let sequence: Int
    public let keyID: String
    public let bootID: String
    public let sessionID: String
    public let issuedAt: String
    public let expiresAt: String
    public let documentDigest: String

    enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version", artifactRole = "artifact_role", operation, bindings, nonce, sequence
        case keyID = "key_id", bootID = "boot_id", sessionID = "session_id"
        case issuedAt = "issued_at", expiresAt = "expires_at", documentDigest = "document_digest"
    }

    public init(operation: AuthorityOperation, bindings: RequestBindings, nonce: String, sequence: Int, keyID: String, bootID: String, sessionID: String, issuedAt: String, expiresAt: String, documentDigest: String) throws {
        schemaVersion = AuthorityConstants.schemaVersion; artifactRole = ArtifactRole.request
        self.operation = operation; self.bindings = bindings; self.nonce = nonce; self.sequence = sequence
        self.keyID = keyID; self.bootID = bootID; self.sessionID = sessionID
        self.issuedAt = issuedAt; self.expiresAt = expiresAt; self.documentDigest = documentDigest
        try validate()
    }

    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue)))
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let decodedVersion = try c.decode(Int.self, forKey: .schemaVersion)
        let decodedRole = try c.decode(String.self, forKey: .artifactRole)
        try require(decodedVersion == AuthorityConstants.schemaVersion)
        try require(decodedRole == ArtifactRole.request)
        try self.init(operation: c.decode(AuthorityOperation.self, forKey: .operation), bindings: c.decode(RequestBindings.self, forKey: .bindings), nonce: c.decode(String.self, forKey: .nonce), sequence: c.decode(Int.self, forKey: .sequence), keyID: c.decode(String.self, forKey: .keyID), bootID: c.decode(String.self, forKey: .bootID), sessionID: c.decode(String.self, forKey: .sessionID), issuedAt: c.decode(String.self, forKey: .issuedAt), expiresAt: c.decode(String.self, forKey: .expiresAt), documentDigest: c.decode(String.self, forKey: .documentDigest))
    }

    private func validate() throws {
        try require(nonce.range(of: #"^[0-9a-f]{64}$"#, options: .regularExpression) != nil)
        try require(sequence >= 1)
        for value in [keyID, bootID, sessionID] { try require(validString(value)) }
        try require(isTimestamp(issuedAt) && isTimestamp(expiresAt))
        guard let issued = ISO8601DateFormatter().date(from: issuedAt), let expires = ISO8601DateFormatter().date(from: expiresAt) else { throw ProtocolFailure(.malformed) }
        try require(expires > issued, .stale)
        try require(isDigest(documentDigest))
    }
}

public struct AuthorityGrant: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let authorityMode: String
    public let requestDigest: String; public let keyID: String; public let publicKeyDigest: String
    public let operation: AuthorityOperation; public let bindings: RequestBindings; public let nonce: String
    public let sequence: Int; public let bootID: String; public let sessionID: String
    public let issuedAt: String; public let expiresAt: String
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", authorityMode = "authority_mode", requestDigest = "request_digest", keyID = "key_id", publicKeyDigest = "public_key_digest", operation, bindings, nonce, sequence, bootID = "boot_id", sessionID = "session_id", issuedAt = "issued_at", expiresAt = "expires_at" }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); authorityMode = try c.decode(String.self, forKey: .authorityMode); requestDigest = try c.decode(String.self, forKey: .requestDigest); keyID = try c.decode(String.self, forKey: .keyID); publicKeyDigest = try c.decode(String.self, forKey: .publicKeyDigest); operation = try c.decode(AuthorityOperation.self, forKey: .operation); bindings = try c.decode(RequestBindings.self, forKey: .bindings); nonce = try c.decode(String.self, forKey: .nonce); sequence = try c.decode(Int.self, forKey: .sequence); bootID = try c.decode(String.self, forKey: .bootID); sessionID = try c.decode(String.self, forKey: .sessionID); issuedAt = try c.decode(String.self, forKey: .issuedAt); expiresAt = try c.decode(String.self, forKey: .expiresAt)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.grant && authorityMode == AuthorityConstants.authorityMode)
        try require(isDigest(requestDigest) && isDigest(publicKeyDigest) && validString(keyID) && validString(bootID) && validString(sessionID) && sequence >= 1)
        try require(nonce.range(of: #"^[0-9a-f]{64}$"#, options: .regularExpression) != nil && isTimestamp(issuedAt) && isTimestamp(expiresAt))
    }
}

public struct SignatureEnvelope: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let authorityMode: String; public let algorithm: String
    public let keyID: String; public let publicKeyDigest: String; public let requestDigest: String; public let documentDigest: String; public let signature: String
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", authorityMode = "authority_mode", algorithm, keyID = "key_id", publicKeyDigest = "public_key_digest", requestDigest = "request_digest", documentDigest = "document_digest", signature }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); authorityMode = try c.decode(String.self, forKey: .authorityMode); algorithm = try c.decode(String.self, forKey: .algorithm); keyID = try c.decode(String.self, forKey: .keyID); publicKeyDigest = try c.decode(String.self, forKey: .publicKeyDigest); requestDigest = try c.decode(String.self, forKey: .requestDigest); documentDigest = try c.decode(String.self, forKey: .documentDigest); signature = try c.decode(String.self, forKey: .signature)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.signatureEnvelope && authorityMode == AuthorityConstants.authorityMode && algorithm == AuthorityConstants.algorithm)
        try require(validString(keyID) && isDigest(publicKeyDigest) && isDigest(requestDigest) && isDigest(documentDigest))
        try require(validString(signature) && signature.range(of: #"^p256-sha256:[A-Za-z0-9+/]+={0,2}$"#, options: .regularExpression) != nil)
    }
}

public struct PublicKeyRecord: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let recordDigest: String; public let keyID: String; public let algorithm: String; public let publicKeyDigest: String; public let issuerIdentity: String; public let activatedAt: String; public let revokedAt: String?; public let verifyNotBefore: String; public let verifyNotAfter: String
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", recordDigest = "record_digest", keyID = "key_id", algorithm, publicKeyDigest = "public_key_digest", issuerIdentity = "issuer_identity", activatedAt = "activated_at", revokedAt = "revoked_at", verifyNotBefore = "verify_not_before", verifyNotAfter = "verify_not_after" }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); recordDigest = try c.decode(String.self, forKey: .recordDigest); keyID = try c.decode(String.self, forKey: .keyID); algorithm = try c.decode(String.self, forKey: .algorithm); publicKeyDigest = try c.decode(String.self, forKey: .publicKeyDigest); issuerIdentity = try c.decode(String.self, forKey: .issuerIdentity); activatedAt = try c.decode(String.self, forKey: .activatedAt); revokedAt = try c.decodeIfPresent(String.self, forKey: .revokedAt); verifyNotBefore = try c.decode(String.self, forKey: .verifyNotBefore); verifyNotAfter = try c.decode(String.self, forKey: .verifyNotAfter)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.publicKeyRecord && algorithm == AuthorityConstants.algorithm)
        try require(isDigest(recordDigest) && isDigest(publicKeyDigest) && validString(keyID) && validString(issuerIdentity))
        try require([activatedAt, verifyNotBefore, verifyNotAfter].allSatisfy(isTimestamp) && (revokedAt.map(isTimestamp) ?? true))
    }
}

public struct EvidenceDecision: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let verifierID: String; public let verifierKeyID: String; public let provider: String; public let providerRunID: String; public let headCommit: String; public let evidenceRef: String; public let evidenceDigest: String; public let verifiedAt: String; public let outcome: String; public let exitCode: Int
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", verifierID = "verifier_id", verifierKeyID = "verifier_key_id", provider, providerRunID = "provider_run_id", headCommit = "head_commit", evidenceRef = "evidence_ref", evidenceDigest = "evidence_digest", verifiedAt = "verified_at", outcome, exitCode = "exit_code" }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); verifierID = try c.decode(String.self, forKey: .verifierID); verifierKeyID = try c.decode(String.self, forKey: .verifierKeyID); provider = try c.decode(String.self, forKey: .provider); providerRunID = try c.decode(String.self, forKey: .providerRunID); headCommit = try c.decode(String.self, forKey: .headCommit); evidenceRef = try c.decode(String.self, forKey: .evidenceRef); evidenceDigest = try c.decode(String.self, forKey: .evidenceDigest); verifiedAt = try c.decode(String.self, forKey: .verifiedAt); outcome = try c.decode(String.self, forKey: .outcome); exitCode = try c.decode(Int.self, forKey: .exitCode)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.evidenceDecision)
        try require([verifierID, verifierKeyID, providerRunID, evidenceRef].allSatisfy { validString($0) } && ["github", "blueprint", "other"].contains(provider) && isCommit(headCommit) && isDigest(evidenceDigest) && isTimestamp(verifiedAt) && ["passed", "failed"].contains(outcome))
    }
}

public struct ProviderResponse: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let status: ProviderStatus; public let reasonCode: SafeReasonCode?
    public let request: AuthorityRequest; public let grant: AuthorityGrant?; public let envelope: SignatureEnvelope?; public let keyRecord: PublicKeyRecord?; public let evidenceDecision: EvidenceDecision?
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", status, reasonCode = "reason_code", request, grant, envelope, keyRecord = "key_record", evidenceDecision = "evidence_decision" }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); status = try c.decode(ProviderStatus.self, forKey: .status); reasonCode = try c.decodeIfPresent(SafeReasonCode.self, forKey: .reasonCode); request = try c.decode(AuthorityRequest.self, forKey: .request); grant = try c.decodeIfPresent(AuthorityGrant.self, forKey: .grant); envelope = try c.decodeIfPresent(SignatureEnvelope.self, forKey: .envelope); keyRecord = try c.decodeIfPresent(PublicKeyRecord.self, forKey: .keyRecord); evidenceDecision = try c.decodeIfPresent(EvidenceDecision.self, forKey: .evidenceDecision)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.providerResponse)
        if status == .approved { try require(reasonCode == nil && grant != nil && envelope != nil && keyRecord != nil) }
        else { try require(reasonCode != nil && grant == nil && envelope == nil && keyRecord == nil && evidenceDecision == nil) }
    }
}

public struct SubstrateHandle: Codable, Equatable, Sendable {
    public let schemaVersion: Int; public let artifactRole: String; public let handleID: String; public let issuerIdentity: String; public let expiresAt: String
    enum CodingKeys: String, CodingKey, CaseIterable { case schemaVersion = "schema_version", artifactRole = "artifact_role", handleID = "handle_id", issuerIdentity = "issuer_identity", expiresAt = "expires_at" }
    public init(from decoder: Decoder) throws {
        try requireClosedKeys(decoder, Set(CodingKeys.allCases.map(\.rawValue))); let c = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try c.decode(Int.self, forKey: .schemaVersion); artifactRole = try c.decode(String.self, forKey: .artifactRole); handleID = try c.decode(String.self, forKey: .handleID); issuerIdentity = try c.decode(String.self, forKey: .issuerIdentity); expiresAt = try c.decode(String.self, forKey: .expiresAt)
        try require(schemaVersion == AuthorityConstants.schemaVersion && artifactRole == ArtifactRole.substrateHandle && validString(handleID) && validString(issuerIdentity) && isTimestamp(expiresAt))
    }
}

public enum CanonicalJSON {
    public static func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        let data = try encoder.encode(value)
        guard data.count <= AuthorityConstants.maximumFrameBytes else { throw ProtocolFailure(.malformed) }
        return data
    }

    public static func decode<T: Codable>(_ type: T.Type, from data: Data) throws -> T {
        guard !data.isEmpty && data.count <= AuthorityConstants.maximumFrameBytes else { throw ProtocolFailure(.malformed) }
        var scanner = try ClosedJSONScanner(data)
        try scanner.validate()
        let value: T
        do { value = try JSONDecoder().decode(type, from: data) }
        catch let failure as ProtocolFailure { throw failure }
        catch { throw ProtocolFailure(.malformed) }
        guard try encode(value) == data else { throw ProtocolFailure(.malformed) }
        return value
    }
}

private struct ClosedJSONScanner {
    let bytes: [UInt8]
    var index = 0
    init(_ data: Data) throws {
        guard String(data: data, encoding: .utf8) != nil else { throw ProtocolFailure(.malformed) }
        bytes = Array(data)
    }
    mutating func validate() throws { try value(depth: 0); skip(); try require(index == bytes.count) }
    mutating func skip() { while index < bytes.count && [9, 10, 13, 32].contains(bytes[index]) { index += 1 } }
    mutating func value(depth: Int) throws {
        try require(depth <= AuthorityConstants.maximumJSONDepth); skip(); try require(index < bytes.count)
        switch bytes[index] {
        case 123: try object(depth: depth)
        case 91: try array(depth: depth)
        case 34: _ = try string()
        case 116: try literal("true")
        case 102: try literal("false")
        case 110: try literal("null")
        default: try integer()
        }
    }
    mutating func object(depth: Int) throws {
        index += 1; skip(); var keys = Set<String>(); var count = 0
        if take(125) { return }
        while true {
            skip(); let key = try string(); try require(keys.insert(key).inserted); count += 1
            try require(count <= AuthorityConstants.maximumCollectionItems); skip(); try require(take(58)); try value(depth: depth + 1); skip()
            if take(125) { return }; try require(take(44))
        }
    }
    mutating func array(depth: Int) throws {
        index += 1; skip(); var count = 0
        if take(93) { return }
        while true { count += 1; try require(count <= AuthorityConstants.maximumCollectionItems); try value(depth: depth + 1); skip(); if take(93) { return }; try require(take(44)) }
    }
    mutating func string() throws -> String {
        try require(take(34)); let start = index - 1; var escaped = false
        while index < bytes.count {
            let byte = bytes[index]; index += 1
            if escaped { escaped = false; continue }
            if byte == 92 { escaped = true; continue }
            if byte == 34 {
                let fragment = Data(bytes[start..<index]); let decoded = try JSONDecoder().decode(String.self, from: fragment)
                try require(decoded.utf8.count <= AuthorityConstants.maximumStringBytes); return decoded
            }
            try require(byte >= 32)
        }
        throw ProtocolFailure(.malformed)
    }
    mutating func literal(_ text: StaticString) throws { for byte in String(describing: text).utf8 { try require(take(byte)) } }
    mutating func integer() throws {
        if take(45) { try require(index < bytes.count) }
        if take(48) { if index < bytes.count { try require(!(48...57).contains(bytes[index])) } }
        else { try require(index < bytes.count && (49...57).contains(bytes[index])); while index < bytes.count && (48...57).contains(bytes[index]) { index += 1 } }
        if index < bytes.count { try require(![46, 69, 101, 43].contains(bytes[index])) }
    }
    mutating func take(_ byte: UInt8) -> Bool { guard index < bytes.count && bytes[index] == byte else { return false }; index += 1; return true }
}

public enum DiagnosticEvent: String, Sendable { case requestRejected = "request_rejected", connectionUnavailable = "connection_unavailable", authorizationDenied = "authorization_denied", authorizationCancelled = "authorization_cancelled", responseRejected = "response_rejected", internalFailure = "internal_failure" }
public protocol DiagnosticSink: Sendable { func emit(_ line: String) }
public struct RedactingDiagnosticLogger: Sendable {
    private let sink: any DiagnosticSink
    public init(sink: any DiagnosticSink) { self.sink = sink }
    public func record(_ event: DiagnosticEvent) { sink.emit("wk-authority: \(event.rawValue)") }
}

// Narrow dependency seams. Production implementations belong to later chunks.
public protocol PeerIdentityChecking: Sendable { func isEligible(auditToken: Data) async throws -> Bool }
public protocol UserAuthorizing: Sendable { func authorize(operation: AuthorityOperation) async throws -> Bool }
public protocol DocumentSigning: Sendable { func sign(document: Data) async throws -> Data }
public protocol PublicKeyRegistering: Sendable { func record(for keyID: String) async throws -> PublicKeyRecord? }
public protocol AuthorityClock: Sendable { func now() -> Date }
public protocol BootSessionIdentifying: Sendable { func bootID() -> String; func sessionID() -> String }
public protocol NonceStoring: Sendable { func consume(nonce: String, sequence: Int) async throws -> Bool }
public protocol RepositoryResolving: Sendable { func resolve(descriptorID: String) async throws -> String }
public protocol DockerControlling: Sendable { func perform(operation: AuthorityOperation, request: Data) async throws -> Data }
public protocol LifecycleSupervising: Sendable { func begin(operation: AuthorityOperation) async throws; func finish(operation: AuthorityOperation) async }
public protocol AuthorityPersisting: Sendable { func store(document: Data) async throws }
public protocol CancellationChecking: Sendable { func checkCancellation() throws }
