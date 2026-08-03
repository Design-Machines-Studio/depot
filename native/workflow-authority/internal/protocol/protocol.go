// Package protocol implements the closed M0 provider-dispatch wire contract.
package protocol

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"time"
)

const (
	Version          = 1
	Name             = "workflow-authority-provider-dispatch-v1"
	Mapping          = "openrouter-chat-v1"
	Destination      = "https://openrouter.ai"
	Method           = "POST"
	Path             = "/api/v1/chat/completions"
	MaxFrameBytes    = 1 << 20
	MaxDepth         = 16
	ContractDigest   = "sha256:4d5a7a7089e557a962ed0c467c11298ff1da596c8891a98d815d058875cc1d8a"
	ContractRevision = 1
)

var (
	ErrInvalidDocument = errors.New("invalid_document")
	ErrNonCanonical    = errors.New("noncanonical_document")
	ErrFrameTooLarge   = errors.New("frame_too_large")
	ErrTrailingData    = errors.New("exchange_trailing_data")
	ErrPartMismatch    = errors.New("part_frame_mismatch")
	digestPattern      = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
	idPattern          = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$`)
	timePattern        = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$`)
)

type Scope struct {
	Repository string `json:"repository"`
	RunID      string `json:"run_id"`
	Lane       string `json:"lane"`
	Candidate  string `json:"candidate"`
	Workload   string `json:"workload"`
}

type Limits struct {
	MaxRequestBytes      int64 `json:"max_request_bytes"`
	MaxResponseBytes     int64 `json:"max_response_bytes"`
	MaxParts             int   `json:"max_parts"`
	MaxPendingPerPeer    int   `json:"max_pending_per_peer"`
	MaxPendingRepository int   `json:"max_pending_per_repository"`
	MaxPendingDaemon     int   `json:"max_pending_per_daemon"`
}

type Authority struct {
	DaemonBuildSHA256     string `json:"daemon_build_sha256"`
	ScannerBuildSHA256    string `json:"scanner_build_sha256"`
	PolicySHA256          string `json:"policy_sha256"`
	Nonce                 string `json:"nonce"`
	Sequence              uint64 `json:"sequence"`
	BootID                string `json:"boot_id"`
	SessionID             string `json:"session_id"`
	ConnectionNonceSHA256 string `json:"connection_nonce_sha256"`
	IssuedAt              string `json:"issued_at"`
	ExpiresAt             string `json:"expires_at"`
	PriorChainDigest      string `json:"prior_chain_digest"`
}

type Part struct {
	Role          string `json:"role"`
	ContentLength int64  `json:"content_length"`
	ContentSHA256 string `json:"content_sha256"`
}

type Request struct {
	SchemaVersion      int       `json:"schema_version"`
	Protocol           string    `json:"protocol"`
	Mapping            string    `json:"mapping"`
	OperationFamily    string    `json:"operation_family"`
	SubstrateAuthority string    `json:"substrate_authority"`
	Destination        string    `json:"destination"`
	Method             string    `json:"method"`
	Path               string    `json:"path"`
	Models             []string  `json:"models"`
	Parts              []Part    `json:"parts"`
	Scope              Scope     `json:"scope"`
	Authority          Authority `json:"authority"`
	Limits             Limits    `json:"limits"`
}

type ResultSigner struct {
	Kind          string `json:"kind"`
	PublicKeySEC1 string `json:"public_key_sec1"`
}

type Challenge struct {
	SchemaVersion         int          `json:"schema_version"`
	Protocol              string       `json:"protocol"`
	Mapping               string       `json:"mapping"`
	OperationFamily       string       `json:"operation_family"`
	SubstrateAuthority    string       `json:"substrate_authority"`
	TransactionID         string       `json:"transaction_id"`
	ConnectionNonceSHA256 string       `json:"connection_nonce_sha256"`
	PeerUID               uint32       `json:"peer_uid"`
	PeerPID               int32        `json:"peer_pid"`
	RequestBodySHA256     string       `json:"request_body_sha256"`
	Destination           string       `json:"destination"`
	Method                string       `json:"method"`
	Path                  string       `json:"path"`
	Models                []string     `json:"models"`
	Scope                 Scope        `json:"scope"`
	DaemonBuildSHA256     string       `json:"daemon_build_sha256"`
	ScannerBuildSHA256    string       `json:"scanner_build_sha256"`
	PolicySHA256          string       `json:"policy_sha256"`
	Nonce                 string       `json:"nonce"`
	Sequence              uint64       `json:"sequence"`
	BootID                string       `json:"boot_id"`
	SessionID             string       `json:"session_id"`
	IssuedAt              string       `json:"issued_at"`
	ExpiresAt             string       `json:"expires_at"`
	Limits                Limits       `json:"limits"`
	ResultSigner          ResultSigner `json:"result_signer"`
	AuthorityAssertion    any          `json:"authority_assertion"`
	PriorChainDigest      string       `json:"prior_chain_digest"`
}

func Digest(payload []byte) string {
	sum := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(sum[:])
}

// CanonicalJSON matches M0's UTF-8, compact, sorted-key JSON form.
func CanonicalJSON(value any) ([]byte, error) {
	raw, err := json.Marshal(value)
	if err != nil {
		return nil, ErrInvalidDocument
	}
	var generic any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&generic); err != nil {
		return nil, ErrInvalidDocument
	}
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(generic); err != nil {
		return nil, ErrInvalidDocument
	}
	return bytes.TrimSuffix(out.Bytes(), []byte{'\n'}), nil
}

// DecodeClosed rejects duplicate/unknown fields, excessive depth, trailing data,
// and non-canonical encodings before returning a typed document.
func DecodeClosed(raw []byte, destination any) error {
	if len(raw) > MaxFrameBytes {
		return ErrFrameTooLarge
	}
	if err := inspectJSON(raw); err != nil {
		return err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	decoder.UseNumber()
	if err := decoder.Decode(destination); err != nil {
		return ErrInvalidDocument
	}
	if decoder.More() {
		return ErrTrailingData
	}
	canonical, err := CanonicalJSON(destination)
	if err != nil {
		return err
	}
	if !bytes.Equal(raw, canonical) {
		return ErrNonCanonical
	}
	return nil
}

func inspectJSON(raw []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var walk func(int) error
	walk = func(depth int) error {
		if depth > MaxDepth {
			return ErrInvalidDocument
		}
		token, err := decoder.Token()
		if err != nil {
			return ErrInvalidDocument
		}
		delim, ok := token.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]struct{}{}
			for decoder.More() {
				keyToken, err := decoder.Token()
				if err != nil {
					return ErrInvalidDocument
				}
				key, ok := keyToken.(string)
				if !ok {
					return ErrInvalidDocument
				}
				if _, exists := seen[key]; exists {
					return ErrInvalidDocument
				}
				seen[key] = struct{}{}
				if err := walk(depth + 1); err != nil {
					return err
				}
			}
			end, err := decoder.Token()
			if err != nil || end != json.Delim('}') {
				return ErrInvalidDocument
			}
		case '[':
			for decoder.More() {
				if err := walk(depth + 1); err != nil {
					return err
				}
			}
			end, err := decoder.Token()
			if err != nil || end != json.Delim(']') {
				return ErrInvalidDocument
			}
		default:
			return ErrInvalidDocument
		}
		return nil
	}
	if err := walk(1); err != nil {
		return err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return ErrTrailingData
	}
	return nil
}

func ValidateRequest(r Request, now time.Time) error {
	if r.SchemaVersion != Version || r.Protocol != Name || r.Mapping != Mapping || r.OperationFamily != "external_provider_dispatch" || r.SubstrateAuthority != "not_asserted" || r.Destination != Destination || r.Method != Method || r.Path != Path {
		return ErrInvalidDocument
	}
	if len(r.Models) == 0 || len(r.Models) > 256 || len(r.Parts) == 0 || len(r.Parts) > 256 {
		return ErrInvalidDocument
	}
	if r.Limits != (Limits{MaxRequestBytes: 8_388_608, MaxResponseBytes: 8_388_608, MaxParts: 256, MaxPendingPerPeer: 4, MaxPendingRepository: 16, MaxPendingDaemon: 64}) {
		return ErrInvalidDocument
	}
	seenModels := make(map[string]struct{}, len(r.Models))
	for _, model := range r.Models {
		if !idPattern.MatchString(model) {
			return ErrInvalidDocument
		}
		if _, exists := seenModels[model]; exists {
			return ErrInvalidDocument
		}
		seenModels[model] = struct{}{}
	}
	for _, part := range r.Parts {
		if (part.Role != "system" && part.Role != "user") || part.ContentLength < 0 || part.ContentLength > MaxFrameBytes || !digestPattern.MatchString(part.ContentSHA256) {
			return ErrInvalidDocument
		}
	}
	for _, value := range []string{r.Scope.Repository, r.Scope.RunID, r.Scope.Lane, r.Scope.Candidate, r.Scope.Workload, r.Authority.Nonce, r.Authority.BootID, r.Authority.SessionID} {
		if !idPattern.MatchString(value) {
			return ErrInvalidDocument
		}
	}
	for _, digest := range []string{r.Authority.DaemonBuildSHA256, r.Authority.ScannerBuildSHA256, r.Authority.PolicySHA256, r.Authority.ConnectionNonceSHA256, r.Authority.PriorChainDigest} {
		if !digestPattern.MatchString(digest) {
			return ErrInvalidDocument
		}
	}
	if !timePattern.MatchString(r.Authority.IssuedAt) || !timePattern.MatchString(r.Authority.ExpiresAt) {
		return ErrInvalidDocument
	}
	expires, err := time.Parse(time.RFC3339, r.Authority.ExpiresAt)
	if err != nil || !now.Before(expires) {
		return errors.New("authorization_expired")
	}
	issued, err := time.Parse(time.RFC3339, r.Authority.IssuedAt)
	if err != nil || issued.After(now) || !issued.Before(expires) || r.Authority.Sequence == 0 {
		return ErrInvalidDocument
	}
	return nil
}

func ReadFrame(r io.Reader) ([]byte, error) {
	var header [4]byte
	if _, err := io.ReadFull(r, header[:]); err != nil {
		return nil, ErrInvalidDocument
	}
	size := binary.BigEndian.Uint32(header[:])
	if size > MaxFrameBytes {
		return nil, ErrFrameTooLarge
	}
	payload := make([]byte, size)
	if _, err := io.ReadFull(r, payload); err != nil {
		return nil, ErrInvalidDocument
	}
	return payload, nil
}

func WriteFrame(w io.Writer, payload []byte) error {
	if len(payload) > MaxFrameBytes {
		return ErrFrameTooLarge
	}
	var header [4]byte
	binary.BigEndian.PutUint32(header[:], uint32(len(payload)))
	if err := writeAll(w, header[:]); err != nil {
		return errors.New("durable_state_unavailable")
	}
	if err := writeAll(w, payload); err != nil {
		return errors.New("durable_state_unavailable")
	}
	return nil
}

func writeAll(w io.Writer, payload []byte) error {
	for len(payload) > 0 {
		n, err := w.Write(payload)
		if err != nil {
			return err
		}
		if n <= 0 || n > len(payload) {
			return io.ErrShortWrite
		}
		payload = payload[n:]
	}
	return nil
}

// ReadSingleFrame rejects a second frame or any trailing byte.
func ReadSingleFrame(r io.Reader) ([]byte, error) {
	payload, err := ReadFrame(r)
	if err != nil {
		return nil, err
	}
	var trailing [1]byte
	n, err := r.Read(trailing[:])
	if n != 0 || (err != nil && err != io.EOF) || err == nil {
		return nil, ErrTrailingData
	}
	return payload, nil
}

// ReadRequestExchange consumes the M0 control frame followed by its ordered
// uint64-length-prefixed content parts and verifies every declared digest.
func ReadRequestExchange(r io.Reader, now time.Time) (Request, [][]byte, error) {
	header, err := ReadFrame(r)
	if err != nil {
		return Request{}, nil, err
	}
	var request Request
	if err := DecodeClosed(header, &request); err != nil {
		return Request{}, nil, err
	}
	if err := ValidateRequest(request, now); err != nil {
		return Request{}, nil, err
	}
	total := int64(4 + len(header))
	parts := make([][]byte, 0, len(request.Parts))
	for _, declared := range request.Parts {
		var lengthBytes [8]byte
		if _, err := io.ReadFull(r, lengthBytes[:]); err != nil {
			return Request{}, nil, ErrPartMismatch
		}
		length := binary.BigEndian.Uint64(lengthBytes[:])
		if length > MaxFrameBytes || int64(length) != declared.ContentLength {
			return Request{}, nil, ErrPartMismatch
		}
		part := make([]byte, int(length))
		if _, err := io.ReadFull(r, part); err != nil {
			return Request{}, nil, ErrPartMismatch
		}
		if Digest(part) != declared.ContentSHA256 {
			return Request{}, nil, ErrPartMismatch
		}
		total += 8 + int64(length)
		if total > request.Limits.MaxRequestBytes {
			return Request{}, nil, ErrFrameTooLarge
		}
		parts = append(parts, part)
	}
	return request, parts, nil
}

func ChallengeInput(challenge Challenge) ([]byte, error) {
	canonical, err := CanonicalJSON(challenge)
	if err != nil {
		return nil, err
	}
	return append([]byte("workflow-authority\x00provider-dispatch-v1\x00challenge\x00"), canonical...), nil
}

func RequireNoAncillary(descriptorCount int) error {
	if descriptorCount != 0 {
		return fmt.Errorf("%w", ErrInvalidDocument)
	}
	return nil
}
