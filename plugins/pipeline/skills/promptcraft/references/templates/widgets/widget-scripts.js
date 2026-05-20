// Copy-back round-trip for decision-table widgets.
// Self-contained HTML artifacts open via file:// — relative <script src> to the
// templates dir would not resolve next to the artifact. So agents INLINE this
// file's contents into the base.html WIDGET_SCRIPTS slot inside a
// <script defer> ... </script> block. Include it once per artifact.
//
// Behaviour: each [data-copy-island] button serializes its enclosing
// .widget--edit table to an array of objects (keyed by each <th data-field>),
// wraps it under the section's data-island-key, and writes it to the clipboard.
// The human edits cells in the browser, clicks Copy, and pastes the JSON back to
// Claude or into the artifact's #pipeline-data island.
(function () {
  "use strict";

  function serializeTable(table) {
    var headers = [].slice.call(table.querySelectorAll("thead th"));
    var fields = headers.map(function (th) {
      return { key: th.getAttribute("data-field") || th.textContent.trim(), list: th.getAttribute("data-list") === "true" };
    });
    var rows = [].slice.call(table.querySelectorAll("tbody tr"));
    return rows.map(function (tr) {
      var cells = [].slice.call(tr.querySelectorAll("td"));
      var obj = {};
      fields.forEach(function (f, i) {
        var raw = cells[i] ? cells[i].textContent.trim() : "";
        obj[f.key] = f.list
          ? raw.split(",").map(function (s) { return s.trim(); }).filter(Boolean)
          : raw;
      });
      return obj;
    });
  }

  function writeClipboard(text, button) {
    var done = function () {
      var prev = button.textContent;
      button.textContent = "Copied ✓";
      setTimeout(function () { button.textContent = prev; }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done, button); });
    } else {
      fallbackCopy(text, done, button);
    }
  }

  function fallbackCopy(text, done, button) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "absolute";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      done();
    } catch (e) {
      button.textContent = "Copy failed";
      console.warn("widget copy-back: clipboard write failed", e);
    }
    document.body.removeChild(ta);
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-island]");
    if (!button) return;
    var section = button.closest(".widget--edit");
    var table = section && section.querySelector("table");
    if (!table) return;
    var key = section.getAttribute("data-island-key") || "rows";
    var payload = {};
    payload[key] = serializeTable(table);
    writeClipboard(JSON.stringify(payload, null, 2), button);
  });
})();
