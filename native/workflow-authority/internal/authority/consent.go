package authority

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"syscall"

	"designmachines.dev/workflow-authority/internal/protocol"
)

type ConsentTerminal interface {
	Identity() (TerminalIdentity, error)
	Write([]byte) (int, error)
	ReadLine() (string, error)
}

type TerminalIdentity struct {
	Device uint64
	Inode  uint64
}

type ControllingTerminal struct {
	file   *os.File
	reader *bufio.Reader
}

func OpenControllingTerminal() (*ControllingTerminal, error) {
	file, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return nil, ErrUnavailable
	}
	if info, err := file.Stat(); err != nil || info.Mode()&os.ModeCharDevice == 0 {
		_ = file.Close()
		return nil, ErrUnavailable
	}
	return &ControllingTerminal{file: file, reader: bufio.NewReader(file)}, nil
}

func (t *ControllingTerminal) Identity() (TerminalIdentity, error) {
	info, err := t.file.Stat()
	if err != nil || info.Mode()&os.ModeCharDevice == 0 {
		return TerminalIdentity{}, ErrUnavailable
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return TerminalIdentity{}, ErrUnavailable
	}
	return TerminalIdentity{Device: uint64(stat.Dev), Inode: uint64(stat.Ino)}, nil
}
func (t *ControllingTerminal) Write(payload []byte) (int, error) { return t.file.Write(payload) }
func (t *ControllingTerminal) ReadLine() (string, error)         { return t.reader.ReadString('\n') }
func (t *ControllingTerminal) Close() error                      { return t.file.Close() }

// ConfirmExactScope renders only authority metadata and digests. Prompt and
// provider response bytes never cross the terminal boundary.
func ConfirmExactScope(terminal ConsentTerminal, challenge protocol.Challenge) error {
	before, err := terminal.Identity()
	if err != nil {
		return ErrUnavailable
	}
	challengeBytes, err := protocol.CanonicalJSON(challenge)
	if err != nil {
		return ErrMalformed
	}
	view := fmt.Sprintf("Workflow Authority exact request\nrepository: %s\nrun: %s\nlane: %s\ncandidate: %s\nworkload: %s\ndestination: %s%s\nmodels: %s\nbody: %s\npolicy: %s\nbudget: request=%d response=%d\nexpires: %s\nsigner: %s\nchallenge: %s\nType AUTHORIZE to continue: ", challenge.Scope.Repository, challenge.Scope.RunID, challenge.Scope.Lane, challenge.Scope.Candidate, challenge.Scope.Workload, challenge.Destination, challenge.Path, strings.Join(challenge.Models, ","), challenge.RequestBodySHA256, challenge.PolicySHA256, challenge.Limits.MaxRequestBytes, challenge.Limits.MaxResponseBytes, challenge.ExpiresAt, challenge.ResultSigner.PublicKeySEC1, protocol.Digest(challengeBytes))
	if _, err := io.WriteString(writerAdapter{terminal}, view); err != nil {
		return ErrUnavailable
	}
	afterDisplay, err := terminal.Identity()
	if err != nil || afterDisplay != before {
		return ErrUnavailable
	}
	line, err := terminal.ReadLine()
	if err != nil {
		return ErrUnavailable
	}
	afterRead, err := terminal.Identity()
	if err != nil || afterRead != before {
		return ErrUnavailable
	}
	if line != "AUTHORIZE\n" {
		return ErrDenied
	}
	return nil
}

type writerAdapter struct{ ConsentTerminal }

func (w writerAdapter) Write(p []byte) (int, error) {
	n, err := w.ConsentTerminal.Write(p)
	if err == nil && n != len(p) {
		err = io.ErrShortWrite
	}
	return n, err
}

var errRedirectedInput = errors.New("redirected_input_rejected")
