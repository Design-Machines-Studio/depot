package enrollment

import (
	"errors"
	"strings"
	"testing"
)

func TestManifestDeviceSelectionFailsClosedAndIsDeterministic(t *testing.T) {
	if _, _, err := SelectDevice(nil, ""); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("zero devices: %v", err)
	}
	first := DeviceManifest{Path: "/dev/hidraw4", Manufacturer: "Example", Product: "Key", VendorID: 1, ProductID: 2}
	second := DeviceManifest{Path: "/dev/hidraw5", Manufacturer: "Example", Product: "Key", VendorID: 1, ProductID: 2}
	selected, selector, err := SelectDevice([]DeviceManifest{first}, "")
	if err != nil || selected != first || !validSelector(selector) {
		t.Fatalf("single selection: %#v %q %v", selected, selector, err)
	}
	if _, _, err := SelectDevice([]DeviceManifest{first, second}, ""); !errors.Is(err, ErrConflict) {
		t.Fatalf("ambiguous selection: %v", err)
	}
	selected, selectedAgain, err := SelectDevice([]DeviceManifest{second, first}, selector)
	if err != nil || selected != first || selectedAgain != selector {
		t.Fatalf("explicit selection drifted: %#v %q %v", selected, selectedAgain, err)
	}
	if _, _, err := SelectDevice([]DeviceManifest{first, first}, selector); !errors.Is(err, ErrConflict) {
		t.Fatalf("duplicate selector: %v", err)
	}
	if _, _, err := SelectDevice([]DeviceManifest{{Path: strings.Repeat("x", 1024)}}, ""); !errors.Is(err, ErrUnavailable) {
		t.Fatalf("unbounded path: %v", err)
	}
	if strings.Contains(selector, first.Path) {
		t.Fatal("selector exposed device path")
	}
}
