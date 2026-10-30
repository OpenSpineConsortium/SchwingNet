/*
 * The pipeline sandbox's page script (docs/research/pipeline-sandbox/README.md). It runs after
 * tools/sandbox/engine.js in one script element, with SANDBOX_DATA (the contract, the blocks, the
 * templates and the experiment route's words) and window.SandboxEngine both defined, and it asks the
 * engine every question about types, jobs, routes and predictions: this file draws the board and
 * handles the pointer, the keys and the panel. Nothing here sends a job or fetches anything; a
 * request is a link to a prefilled GitHub issue, and the owner's word and job count decide every run.
 *
 * Speed. Holding the pointer to the right of a block must feel instant, so a pointermove only notes
 * where the pointer is and the work is done once an animation frame; the cards' rectangles live in a
 * cache that is rebuilt when the layout changes, never read back from the page inside a move; and a
 * commit rewrites only the cards, edges and panel parts whose text or place changed.
 *
 * Text that comes from the data or from the viewer reaches the page through textContent alone;
 * innerHTML is used only for the glyph library's own SVG strings below.
 */
(function () {
  "use strict";

  var SB = window.SandboxEngine;
  var RAW = typeof SANDBOX_DATA !== "undefined" ? SANDBOX_DATA : null;
  var mainEl = document.querySelector("main.sb");
  if (!SB || !RAW || !RAW.contract || !mainEl) {
    if (mainEl) {
      var warn = document.createElement("p");
      warn.className = "note warn";
      warn.textContent = "The sandbox could not start: its engine or its data is missing from this page.";
      mainEl.insertBefore(warn, mainEl.firstChild);
    }
    return;
  }

  // ---------------------------------------------------------------------------------------------
  // Sizes and timings. page.css draws a card at W x H, so the script can place and hit-test cards
  // from the layout alone.

  var W = 232, H = 112, GRID = 20, COL = 300, ROW = 150, ORIGIN = 40;
  var ZONE_GAP = 6, ZONE_REACH = 260, ZONE_PAD = 30, GHOST_DX = 72, HANDLE_R = 13;
  var MOVE_PX = 6, DRAG_PX = 4, DWELL_MS = 140, RING_MS = 480, TAP_MS = 250;
  var RING_C = 2 * Math.PI * 14;
  var STRIP_W = 272, SUG_H = 46, STRIP_GAP = 12;
  var STORE_KEY = "schwingnet.sandbox.v1", UNDO_MOST = 200, LINK_MOST = 7500, LABEL_MOST = 36;
  var SVGNS = "http://www.w3.org/2000/svg";
  var HELD_SHORT = "an imported block is on the board; it runs only after its pull request merges";
  var HELD_TEXT = "An imported block is on the board. The experiment workflow runs only the repository's blocks, " +
    "so these requests are held back until the block's pull request merges.";
  var ASK_TEXT = "Each opens a prefilled issue; the experiment workflow checks it and answers with the gate word; " +
    "nothing runs until you click that word with its job count.";

  // ---------------------------------------------------------------------------------------------
  // The glyph library: each block's operation drawn in a 120 x 72 box, in the stroke classes of
  // bordercall's pipeline.html (s, sf, m, dash, a, af, mf, pf, w, wf), whose helpers arrow, c and
  // vertebra are copied here unchanged.

  function arrow(x1, y1, x2, y2, cls) {
    cls = cls || "s";
    var dx = x2 - x1, dy = y2 - y1, L = Math.sqrt(dx * dx + dy * dy), ux = dx / L, uy = dy / L;
    var bx = x2 - ux * 6, by = y2 - uy * 6, px = -uy * 3.4, py = ux * 3.4;
    var head = cls === "a" ? "af" : (cls === "m" ? "mf" : "sf");
    return '<line class="' + cls + '" x1="' + x1 + '" y1="' + y1 + '" x2="' + bx.toFixed(1) + '" y2="' + by.toFixed(1) + '"/>' +
      '<polygon class="' + head + '" points="' + x2 + ',' + y2 + ' ' + (bx + px).toFixed(1) + ',' + (by + py).toFixed(1) + ' ' +
      (bx - px).toFixed(1) + ',' + (by - py).toFixed(1) + '"/>';
  }
  function c(x, y, r, cls, style) {
    return '<circle class="' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"' + (style ? ' style="' + style + '"' : "") + '/>';
  }
  function vertebra(x, y, cls) {
    return '<rect class="' + cls + '" x="' + x + '" y="' + y + '" width="34" height="30" rx="6"/>' +
      '<path class="' + cls + '" d="M' + (x + 34) + ' ' + (y + 7) + ' q16 -1 18 8 q-2 9 -18 8"/>';
  }
  function bars(x0, base, step, width, heights, accentAt, cls) {
    var out = "";
    heights.forEach(function (v, i) {
      out += '<rect class="' + (i === accentAt ? (cls || "af") : "mf") + '" x="' + (x0 + i * step) + '" y="' + (base - v) +
        '" width="' + width + '" height="' + v + '"/>';
    });
    return out;
  }

  var GLYPHS = {
    // sources
    catalog: function () {
      return '<rect class="m" x="20" y="6" width="38" height="38" rx="3"/><rect class="m" x="14" y="12" width="38" height="38" rx="3"/>' +
        '<rect class="s pf" x="8" y="18" width="38" height="38" rx="3"/>' +
        '<rect class="af" x="20" y="24" width="14" height="8" rx="2"/><rect class="af" x="20" y="35" width="14" height="8" rx="2" style="opacity:.6"/>' +
        '<rect class="af" x="20" y="46" width="14" height="6" rx="2" style="opacity:.3"/>' + arrow(52, 37, 66, 37) +
        '<rect class="s" x="70" y="14" width="42" height="46" rx="2"/><line class="m" x1="70" y1="25" x2="112" y2="25"/>' +
        '<line class="m" x1="70" y1="36" x2="112" y2="36"/><line class="m" x1="70" y1="47" x2="112" y2="47"/><line class="m" x1="84" y1="14" x2="84" y2="60"/>';
    },
    ct: function () {
      return '<rect class="s" x="6" y="26" width="36" height="36"/><path class="s" d="M6 26 L20 12 H56 V48 L42 62 M42 26 L56 12"/>' +
        '<path class="m dash" d="M14 26 L28 12 M22 26 L36 12 M30 26 L44 12"/>' + vertebra(66, 22, "a");
    },
    video: function () {
      var out = '<rect class="s" x="4" y="12" width="112" height="48" rx="3"/>';
      for (var i = 0; i < 10; i++) {
        var x = 8 + i * 11;
        out += '<rect class="mf" x="' + x + '" y="15" width="5" height="4" rx="1"/><rect class="mf" x="' + x + '" y="53" width="5" height="4" rx="1"/>';
      }
      for (var k = 0; k < 3; k++) {
        var fx = 9 + k * 36;
        out += '<rect class="m" x="' + fx + '" y="22" width="32" height="28" rx="2"/>';
        out += '<rect class="' + (k === 2 ? "af" : "mf") + '" x="' + (fx + 6 + k * 4) + '" y="29" width="14" height="12" rx="3"' +
          (k < 2 ? ' style="opacity:' + (0.35 + k * 0.25) + '"' : "") + '/>';
      }
      return out;
    },
    folder: function () {
      var out = '<path class="s" d="M8 16 H40 L46 22 H112 V62 H8 Z"/>';
      for (var i = 0; i < 4; i++) {
        out += '<rect class="' + (i === 3 ? "a dash" : "m") + '" x="' + (16 + i * 24) + '" y="30" width="18" height="24" rx="2"/>';
      }
      return out;
    },
    synthetic: function () {
      return '<rect class="s" x="8" y="20" width="32" height="32" rx="6"/>' + c(16, 28, 2.4, "sf") + c(24, 36, 2.4, "sf") + c(32, 44, 2.4, "sf") +
        arrow(46, 36, 62, 36) +
        '<rect class="m dash" x="76" y="6" width="34" height="16" rx="5"/><rect class="m dash" x="74" y="28" width="34" height="16" rx="5"/>' +
        '<rect class="a dash" x="72" y="50" width="34" height="16" rx="5"/>';
    },
    // prepare
    recipe: function () {
      var out = '<path class="s" d="M12 24 H68 L48 46 V64 H32 V46 Z"/>';
      [[18, 12, "mf"], [28, 8, "af"], [40, 13, "wf"], [52, 9, "af"], [62, 14, "wf"]].forEach(function (d) { out += c(d[0], d[1], 3, d[2]); });
      return out + arrow(54, 56, 74, 56, "a") + c(84, 56, 3, "af") + c(96, 56, 3, "af") + c(108, 56, 3, "af");
    },
    samples: function () {
      var out = "";
      for (var r = 0; r < 4; r++) {
        for (var k = 0; k < 9; k++) {
          var inside = k >= 2 && k <= 5 && r >= 1 && r <= 2;
          out += c(14 + k * 12, 14 + r * 14, 3, inside ? "af" : "mf");
        }
      }
      return out + '<rect class="s dash" x="30" y="21" width="49" height="28" rx="4"/>';
    },
    normalise: function () {
      var h = [10, 26, 34, 22, 14, 9, 6, 4], out = '<path class="s" d="M6 62 H54"/>';
      h.forEach(function (v, i) {
        out += '<rect class="mf" x="' + (8 + i * 5.6).toFixed(1) + '" y="' + (62 - v) + '" width="4.4" height="' + v + '"/>';
      });
      return out + arrow(58, 40, 72, 40) + '<path class="s" d="M74 62 H116"/>' +
        '<path class="a" d="M76 61 C 86 60, 88 22, 95 22 C 102 22, 104 60, 114 61"/>';
    },
    denoise: function () {
      return '<polyline class="s" points="6,40 10,30 14,46 18,28 22,44 26,24 30,42 34,30 38,48 42,34 46,40"/>' + arrow(52, 38, 66, 38) +
        '<path class="a" d="M72 42 C 82 26, 92 26, 100 36 S 112 44, 116 34"/>';
    },
    crop: function () {
      var out = '<rect class="m" x="8" y="4" width="48" height="64" rx="3"/>';
      for (var i = 0; i < 5; i++) out += '<rect class="s" x="20" y="' + (8 + i * 12) + '" width="24" height="9" rx="3"/>';
      return out + '<rect class="a dash" x="15" y="29" width="34" height="14" rx="3"/>' + arrow(60, 40, 76, 40) +
        '<rect class="s" x="82" y="22" width="34" height="34" rx="2"/><rect class="af" x="91" y="32" width="16" height="14" rx="4"/>';
    },
    segment: function () {
      var out = "";
      for (var i = 0; i < 3; i++) {
        var y = 10 + i * 20, fill = i === 2 ? "wf" : "af", fade = i === 1 ? ' style="opacity:.6"' : "";
        out += '<rect class="s" x="10" y="' + y + '" width="26" height="14" rx="4"/><path class="s" d="M36 ' + (y + 3) + ' q10 0 11 4 q-1 4 -11 4"/>';
        out += '<rect class="' + fill + '" x="72" y="' + y + '" width="26" height="14" rx="4"' + fade + '/><path class="' + fill + '" d="M98 ' +
          (y + 3) + ' q10 0 11 4 q-1 4 -11 4 z"' + fade + '/>';
      }
      return out + arrow(52, 37, 66, 37);
    },
    render: function () {
      return c(10, 36, 3.4, "wf") +
        '<line class="m dash" x1="12" y1="35" x2="100" y2="10"/><line class="m dash" x1="12" y1="37" x2="100" y2="62"/>' +
        '<line class="m dash" x1="13" y1="36" x2="100" y2="36"/>' +
        '<rect class="s pf" x="42" y="24" width="22" height="22"/><path class="s" d="M42 24 L50 17 H72 V39 L64 46 M64 24 L72 17"/>' +
        '<rect class="a" x="100" y="8" width="8" height="56" rx="1"/>';
    },
    realism: function () {
      var out = '<rect class="s" x="6" y="14" width="40" height="44" rx="3"/>' +
        '<rect class="mf" x="16" y="24" width="20" height="10" rx="3" style="opacity:.5"/><rect class="mf" x="16" y="38" width="20" height="10" rx="3" style="opacity:.5"/>' +
        '<path class="a" d="M60 26 V46 M50 36 H70 M53 29 L67 43 M67 29 L53 43"/>' +
        '<rect class="s" x="74" y="14" width="40" height="44" rx="3"/>';
      [[80, 20], [92, 18], [104, 24], [84, 52], [100, 53], [108, 42], [78, 37]].forEach(function (p) { out += c(p[0], p[1], 1.4, "mf"); });
      return out + '<rect class="af" x="84" y="24" width="20" height="10" rx="3"/><rect class="af" x="84" y="38" width="20" height="10" rx="3" style="opacity:.7"/>';
    },
    features: function () {
      var out = '<path class="s" d="M12 8 V62 H112"/>';
      [[30, 48], [36, 53], [27, 42], [41, 46], [34, 40], [44, 54]].forEach(function (p) { out += c(p[0], p[1], 3, "s"); });
      [[70, 24], [78, 19], [84, 28], [74, 31], [90, 22], [96, 30]].forEach(function (p) { out += c(p[0], p[1], 3, "af"); });
      return out + '<line class="m dash" x1="30" y1="12" x2="98" y2="62"/>';
    },
    // split (pipeline.html's plan and planFamilies)
    split: function () {
      var out = "";
      for (var r = 0; r < 4; r++) {
        for (var k = 0; k < 10; k++) {
          var x = (14 + k * 10.4).toFixed(1), y = 14 + r * 13;
          if (k <= 6) out += c(x, y, 3.2, "mf");
          else if (k === 7) out += c(x, y, 3.2, "af");
          else out += c(x, y, 3, "w");
        }
      }
      return out + '<rect class="s dash" x="7.5" y="7.5" width="23.4" height="39" rx="4"/>';
    },
    splitFamilies: function () {
      var out = "";
      for (var r = 0; r < 3; r++) {
        for (var k = 0; k < 10; k++) {
          var x = (14 + k * 10.4).toFixed(1), y = 10 + r * 11;
          if (k <= 6) out += c(x, y, 3, "mf");
          else if (k === 7) out += c(x, y, 3, "af");
          else out += c(x, y, 2.8, "w");
        }
      }
      out += '<rect class="s dash" x="7.5" y="4.5" width="23.4" height="33" rx="4"/>';
      out += '<line class="m dash" x1="6" y1="46" x2="114" y2="46"/>';
      for (var j = 0; j < 10; j++) {
        out += '<rect class="' + (j < 6 ? "mf" : "w") + '" x="' + (10.5 + j * 10.4).toFixed(1) + '" y="53" width="7" height="7" rx="1"/>';
      }
      return out;
    },
    augment: function () {
      var out = '<rect class="s" x="6" y="18" width="34" height="34" rx="3"/><rect class="af" x="15" y="27" width="16" height="16" rx="4"/>' +
        arrow(46, 35, 60, 35);
      [[66, 6, 0], [92, 6, 12], [66, 38, -10], [92, 38, 0]].forEach(function (t, i) {
        out += '<g transform="rotate(' + t[2] + ' ' + (t[0] + 11) + ' ' + (t[1] + 14) + ')"><rect class="s" x="' + t[0] + '" y="' + t[1] +
          '" width="22" height="28" rx="3"/><rect class="af" x="' + (t[0] + 5) + '" y="' + (t[1] + 8) + '" width="12" height="12" rx="3"' +
          (i === 3 ? ' style="opacity:.45"' : "") + '/></g>';
      });
      return out;
    },
    // model
    network: function () {
      return '<path class="s" d="M8 10 L50 24 V48 L8 62 Z"/>' + arrow(54, 36, 68, 36) + '<path class="s" d="M72 62 H116"/>' +
        bars(75, 62, 8, 6, [10, 18, 40, 14, 8], 2);
    },
    unet: function () {
      return '<rect class="s" x="8" y="8" width="12" height="20" rx="2"/><rect class="s" x="22" y="28" width="12" height="16" rx="2"/>' +
        '<rect class="s" x="36" y="46" width="12" height="14" rx="2"/><rect class="af" x="54" y="54" width="12" height="12" rx="2"/>' +
        '<rect class="s" x="72" y="46" width="12" height="14" rx="2"/><rect class="s" x="86" y="28" width="12" height="16" rx="2"/>' +
        '<rect class="s" x="100" y="8" width="12" height="20" rx="2"/>' +
        '<line class="a dash" x1="20" y1="18" x2="100" y2="18"/><line class="a dash" x1="34" y1="36" x2="86" y2="36"/>' +
        '<line class="a dash" x1="48" y1="52" x2="72" y2="52"/>';
    },
    prior: function () {
      return '<rect class="m dash" x="28" y="12" width="44" height="46" rx="10"/><rect class="m dash" x="38" y="22" width="24" height="26" rx="5"/>' +
        '<rect class="a" x="33" y="17" width="34" height="36" rx="8"/><path class="a" d="M67 25 q14 0 14 10 q0 10 -14 10"/>' +
        c(104, 10, 3.4, "w") + arrow(101, 13, 84, 25, "a");
    },
    // train, calibrate, select, evaluate
    train: function () {
      return '<path class="s" d="M12 8 V62 H112"/><path class="a" d="M16 14 C 30 44, 48 52, 108 56"/>' +
        '<rect class="af" x="76" y="10" width="9" height="9" style="opacity:.85"/><rect class="af" x="89" y="10" width="9" height="9" style="opacity:.45"/>' +
        '<rect class="af" x="102" y="10" width="9" height="9" style="opacity:.12"/>';
    },
    calibrate: function () {
      return '<rect class="m" x="30" y="6" width="60" height="60"/><line class="m dash" x1="30" y1="66" x2="90" y2="6"/>' +
        '<path class="s" d="M30 66 Q 76 62 90 6" style="opacity:.5"/><path class="a" d="M30 66 L48 47 L62 34 L76 19 L90 6"/>';
    },
    select: function () {
      var out = "", lens = [62, 50, 56, 26, 46, 42], marks = [1, 1, 1, 0, 1, 1];
      for (var r = 0; r < 6; r++) {
        var y = 10 + r * 10.4;
        out += '<rect class="mf" x="14" y="' + (y - 2).toFixed(1) + '" width="' + lens[r] + '" height="4" rx="1"/>';
        out += marks[r] ? '<path class="a" d="M92 ' + y.toFixed(1) + ' l4 4 l9 -9"/>' :
          '<path class="w" d="M93 ' + (y - 4).toFixed(1) + ' l8 8 M101 ' + (y - 4).toFixed(1) + ' l-8 8"/>';
      }
      return out;
    },
    evaluate: function () {
      return '<path class="s" d="M12 8 V62 H112"/>' +
        '<rect class="af" x="22" y="26" width="14" height="36"/><rect class="af" x="42" y="36" width="14" height="26"/>' +
        '<rect class="s" x="66" y="20" width="14" height="42"/><rect class="s" x="86" y="32" width="14" height="30"/>';
    },
    latency: function () {
      return c(28, 40, 20, "s") + '<rect class="s" x="24" y="13" width="8" height="5" rx="1"/><line class="s" x1="28" y1="18" x2="28" y2="20"/>' +
        '<line class="a" x1="28" y1="40" x2="38" y2="30"/>' + c(28, 40, 2.4, "af") +
        '<path class="s" d="M58 64 H116"/>' + bars(62, 64, 10, 7, [26, 30, 22, 36, 28], 3, "wf") +
        '<line class="w dash" x1="58" y1="32" x2="116" y2="32"/>';
    },
    gap: function () {
      return '<path class="s" d="M6 62 H114"/>' +
        '<path class="m" d="M8 61 C 22 60, 26 20, 38 20 C 50 20, 54 60, 68 61"/>' +
        '<path class="a" d="M52 61 C 66 60, 70 20, 82 20 C 94 20, 98 60, 112 61"/>' +
        '<line class="w" x1="38" y1="12" x2="82" y2="12"/><line class="w" x1="38" y1="8" x2="38" y2="16"/><line class="w" x1="82" y1="8" x2="82" y2="16"/>';
    },
    // analyse (pipeline.html's export and ruleExact)
    morphometry: function () {
      return vertebra(8, 22, "s") +
        '<line class="a" x1="12" y1="37" x2="38" y2="37"/>' + c(12, 37, 2.6, "af") + c(38, 37, 2.6, "af") +
        '<line class="a" x1="17" y1="26" x2="17" y2="48"/>' + c(17, 26, 2.2, "af") + c(17, 48, 2.2, "af") +
        arrow(64, 37, 80, 37) +
        '<rect class="s" x="84" y="16" width="28" height="42" rx="2"/><line class="m" x1="84" y1="27" x2="112" y2="27"/>' +
        '<line class="m" x1="84" y1="37" x2="112" y2="37"/><line class="m" x1="84" y1="47" x2="112" y2="47"/><line class="m" x1="96" y1="16" x2="96" y2="58"/>';
    },
    naming: function () {
      var xs = [16, 38, 60, 82, 104], ys = [14, 29, 44, 59], out = "", path = [3, 2, 2, 1, 0], k, r;
      for (k = 0; k < 4; k++) {
        for (r = 0; r < 4; r++) {
          for (var r2 = Math.max(0, r - 1); r2 <= Math.min(3, r + 1); r2++) {
            out += '<line class="m" style="opacity:.45" x1="' + xs[k] + '" y1="' + ys[r] + '" x2="' + xs[k + 1] + '" y2="' + ys[r2] + '"/>';
          }
        }
      }
      out += '<polyline class="a" points="' + path.map(function (row, i) { return xs[i] + "," + ys[row]; }).join(" ") + '"/>';
      for (k = 0; k < 5; k++) for (r = 0; r < 4; r++) out += c(xs[k], ys[r], 3.2, path[k] === r ? "af" : "s pf");
      return out;
    },
    // report
    report: function () {
      return '<rect class="s" x="8" y="10" width="48" height="52" rx="3"/><rect class="af" x="16" y="40" width="8" height="16"/>' +
        '<rect class="mf" x="28" y="30" width="8" height="26"/><rect class="af" x="40" y="22" width="8" height="34"/>' +
        '<rect class="s" x="64" y="10" width="48" height="52" rx="3"/><path class="a" d="M70 52 L80 40 L90 44 L100 26 L106 22"/>';
    },
    wandb: function () {
      return '<path class="s" d="M8 8 V62 H70"/>' +
        '<path class="m" d="M12 20 C 26 44, 40 52, 66 56"/><path class="m" d="M12 30 C 28 46, 44 50, 66 52" style="opacity:.6"/>' +
        '<path class="a" d="M12 14 C 24 40, 40 48, 66 50"/>' +
        '<path class="s" d="M82 40 h26 a8 8 0 0 0 -2 -16 a11 11 0 0 0 -21 -2 a8 8 0 0 0 -3 18 z"/>' + arrow(95, 64, 95, 46, "a");
    },
    card: function () {
      return '<path class="s" d="M30 6 H80 L92 18 V66 H30 Z"/><path class="m" d="M80 6 V18 H92"/>' +
        '<rect class="af" x="36" y="22" width="48" height="8" rx="2"/>' +
        '<line class="m" x1="36" y1="38" x2="84" y2="38"/><line class="m" x1="36" y1="46" x2="78" y2="46"/><line class="m" x1="36" y1="54" x2="70" y2="54"/>' +
        '<path class="a" d="M98 46 l6 6 l12 -14"/>';
    },
    fallback: function () {
      return '<path class="m dash" d="M36 14 H54 a6 6 0 1 1 12 0 H84 V32 a6 6 0 1 1 0 12 V60 H36 Z"/>' +
        '<text x="60" y="45" text-anchor="middle" style="font-size:20px">?</text>';
    }
  };

  var glyphCache = new Map();
  // draw(name) never throws: an unknown name, or a drawing that fails, gives the fallback.
  function draw(name) {
    var key = typeof name === "string" && Object.prototype.hasOwnProperty.call(GLYPHS, name) ? name : "fallback";
    if (glyphCache.has(key)) return glyphCache.get(key);
    var body;
    try {
      body = GLYPHS[key]();
    } catch (e) {
      body = GLYPHS.fallback();
    }
    var svg = '<svg class="g" viewBox="0 0 120 72" aria-hidden="true" focusable="false">' + body + "</svg>";
    glyphCache.set(key, svg);
    return svg;
  }

  // ---------------------------------------------------------------------------------------------
  // Small helpers.

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function button(cls, text, onClick, title) {
    var b = el("button", cls, text);
    b.type = "button";
    if (title) b.title = title;
    if (onClick) b.addEventListener("click", onClick);
    return b;
  }
  function svgEl(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function glyphEl(name, cls) {
    var s = el("span", cls || "glyph");
    s.setAttribute("aria-hidden", "true");
    s.innerHTML = draw(name);
    return s;
  }
  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return typeof v === "string" ? v : ""; }
  function clone(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }
  function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
  function safe(fn, fallback) {
    try {
      return fn();
    } catch (e) {
      return fallback;
    }
  }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
  function now() { return window.performance && performance.now ? performance.now() : Date.now(); }
  function snap(v) { return Math.round(v / GRID) * GRID; }
  function r1(v) { return Math.round(v * 10) / 10; }
  function num(v) { return safe(function () { return SB.formatNumber(v); }, String(v)); }
  function hoursText(v) { return safe(function () { return SB.hoursWord(v); }, String(v)); }
  function summaryOf(type) { return safe(function () { return SB.typeSummary(type); }, "no type"); }
  function shorten(text, most) { return text.length > most ? text.slice(0, most - 3) + "..." : text; }
  function inRect(r, x, y) { return !!r && x >= r.x && x <= r.r && y >= r.y && y <= r.b; }
  function splitList(text, sep) {
    return String(text).split(sep).map(function (s) { return s.trim(); }).filter(function (s) { return s !== ""; });
  }
  // Any form field keeps Delete, Backspace and Ctrl+Z for itself; only a field that takes text keeps the
  // digits, Enter and the arrows from the ghost, since a checkbox or a button does nothing with them.
  var TEXT_INPUTS = {"": true, text: true, search: true, number: true, email: true, url: true, tel: true, password: true};
  function isTyping(t) {
    if (!t || !t.tagName) return false;
    var tag = t.tagName.toUpperCase();
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable === true;
  }
  function takesText(t) {
    if (!isTyping(t)) return false;
    return t.tagName.toUpperCase() !== "INPUT" || TEXT_INPUTS[String(t.type || "").toLowerCase()] === true;
  }
  var framed = (function () {
    try {
      return window.parent && window.parent !== window;
    } catch (e) {
      return true;
    }
  }());
  function post(payload) {
    try {
      if (framed) window.parent.postMessage(payload, "*");
    } catch (e) { /* a host that does not listen loses nothing */ }
  }

  // Durations, kept for the status line and for the test hooks.
  var timing = {move: [], frame: [], commit: [], recompute: []};
  function record(list, ms) {
    list.push(ms);
    if (list.length > 500) list.shift();
  }
  function stats(list) {
    if (!list.length) return {count: 0, mean: 0, p95: 0, max: 0};
    var s = list.slice().sort(function (a, b) { return a - b; }), sum = 0;
    s.forEach(function (v) { sum += v; });
    return {count: s.length, mean: sum / s.length, p95: s[Math.floor(0.95 * (s.length - 1))], max: s[s.length - 1]};
  }

  // ---------------------------------------------------------------------------------------------
  // The data: the repository's blocks, plus the viewer's imported ones, as one DATA object the
  // engine reads.

  var ID_RE = /^n[1-9][0-9]{0,3}$/;
  var BLOCK_RE = /^[a-z][a-z0-9_]{1,39}$/;
  var CONTRACT = RAW.contract;
  var STAGES = arr(CONTRACT.stages).filter(function (s) { return isObj(s) && typeof s.id === "string"; });
  var STAGE_TITLE = new Map(STAGES.map(function (s) { return [s.id, str(s.title) || s.id]; }));
  var TEMPLATES = arr(RAW.templates).filter(function (t) { return isObj(t) && typeof t.id === "string"; });
  var EXPERIMENT = isObj(RAW.experiment) ? RAW.experiment : {};
  var REPO = str(RAW.repo) || str(EXPERIMENT.repo) || "OpenSpineConsortium/SchwingNet";
  var NEW_ISSUE = str(EXPERIMENT["new"]) || "https://github.com/" + REPO + "/issues/new";
  var BUILTIN = arr(RAW.blocks).filter(function (m) { return isObj(m) && typeof m.id === "string"; });
  var BUILTIN_IDS = new Set(BUILTIN.map(function (m) { return m.id; }));
  var STATS = safe(function () { return SB.transitionStats(TEMPLATES); }, {});

  var imported = [], importRev = 0;
  var DATA = null, BLOCKS = new Map(), IMPORTED_IDS = new Set();
  function rebuildData() {
    DATA = {contract: CONTRACT, blocks: BUILTIN.concat(imported), templates: TEMPLATES, experiment: EXPERIMENT, repo: REPO};
    BLOCKS = new Map();
    DATA.blocks.forEach(function (m) { if (!BLOCKS.has(m.id)) BLOCKS.set(m.id, m); });
    IMPORTED_IDS = new Set(imported.map(function (m) { return m.id; }));
  }
  function stageTitle(id) { return STAGE_TITLE.get(id) || String(id); }
  function templateById(id) {
    for (var i = 0; i < TEMPLATES.length; i++) if (TEMPLATES[i].id === id) return TEMPLATES[i];
    return null;
  }
  function accepts(pattern, type) {
    return !!type && safe(function () { return SB.matches(pattern, type, CONTRACT).length === 0; }, false);
  }

  // ---------------------------------------------------------------------------------------------
  // State: the spec on the board (with its layout), the selection, the viewer's history of
  // transitions, and the undo steps. Everything but the undo steps is saved in localStorage.

  var spec = {sandbox: 1, name: "new pipeline", nodes: [], edges: [], layout: {}};
  var selected = null, sheetOpen = false, template = null;
  var history = {};
  var undoStack = [], redoStack = [], lastUndoKey = null, lastUndoAt = 0;
  var prop = null, comp = null, version = 0;
  var nodeIndex = new Map();
  var problemsByNode = new Map(), badPorts = new Set(), planByNode = new Map();

  function readStore() {
    try {
      var raw = window.localStorage.getItem(STORE_KEY);
      var v = raw ? JSON.parse(raw) : null;
      return isObj(v) && v.v === 1 ? v : null;
    } catch (e) {
      return null;
    }
  }
  var saveTimer = 0;
  function saveSoon() {
    if (!saveTimer) saveTimer = setTimeout(saveNow, 150);
  }
  function saveNow() {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = 0;
    }
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify({v: 1, spec: spec, imported: imported, history: history, template: template}));
    } catch (e) { /* the page works without storage */ }
  }
  // A board read back from storage keeps only what the page could have written: unique node ids of the
  // n<number> form, edges between kept nodes, and a layout of two numbers per kept node. An unknown block
  // stays, so the board shows it as unknown rather than losing it.
  function cleanSpec(s) {
    if (!isObj(s) || !Array.isArray(s.nodes) || !Array.isArray(s.edges)) return null;
    var ids = new Set(), nodes = [], edges = [], layout = {};
    s.nodes.forEach(function (n) {
      if (!isObj(n) || typeof n.id !== "string" || !ID_RE.test(n.id) || ids.has(n.id) || typeof n.block !== "string") return;
      ids.add(n.id);
      var c = clone(n);
      if (!isObj(c.params)) c.params = {};
      nodes.push(c);
    });
    s.edges.forEach(function (e) {
      if (!isObj(e) || !ids.has(e.from) || !ids.has(e.to) || typeof e.out !== "string" || typeof e["in"] !== "string") return;
      edges.push(clone(e));
    });
    if (isObj(s.layout)) {
      Object.keys(s.layout).forEach(function (id) {
        var q = s.layout[id];
        if (!ids.has(id) || !Array.isArray(q) || q.length !== 2) return;
        if (typeof q[0] === "number" && typeof q[1] === "number" && isFinite(q[0]) && isFinite(q[1])) layout[id] = [q[0], q[1]];
      });
    }
    return {sandbox: 1, name: typeof s.name === "string" ? s.name.slice(0, 200) : "pipeline", nodes: nodes, edges: edges, layout: layout};
  }
  function cleanHistory(h) {
    var out = {};
    if (!isObj(h)) return out;
    Object.keys(h).forEach(function (a) {
      if (!BLOCK_RE.test(a) || !isObj(h[a])) return;
      Object.keys(h[a]).forEach(function (b) {
        var n = h[a][b];
        if (!BLOCK_RE.test(b) || typeof n !== "number" || !(n >= 1) || Math.floor(n) !== n) return;
        if (!out[a]) out[a] = {};
        out[a][b] = Math.min(n, 999);
      });
    });
    return out;
  }
  function cleanImported(list) {
    var seen = new Set();
    return arr(list).filter(function (m) {
      if (!isObj(m) || typeof m.id !== "string" || BUILTIN_IDS.has(m.id) || seen.has(m.id)) return false;
      var ok = safe(function () { return SB.checkManifest(m, CONTRACT).length === 0; }, false);
      if (ok) seen.add(m.id);
      return ok;
    });
  }
  function learn(a, b) {
    if (typeof a !== "string" || typeof b !== "string") return;
    if (!isObj(history[a])) history[a] = {};
    history[a][b] = Math.min(999, (history[a][b] || 0) + 1);
  }

  // Undo steps are whole snapshots of the spec, its layout included.
  function snapshot() {
    return JSON.stringify({name: spec.name, nodes: spec.nodes, edges: spec.edges, layout: spec.layout});
  }
  function pushUndo() {
    undoStack.push(snapshot());
    if (undoStack.length > UNDO_MOST) undoStack.shift();
    redoStack.length = 0;
    lastUndoKey = null;
  }
  // A run of edits to one field (typing a number, a name) is one undo step.
  function pushUndoFor(key) {
    var t = now();
    if (key !== lastUndoKey || t - lastUndoAt > 1500) {
      pushUndo();
      lastUndoKey = key;
    }
    lastUndoAt = t;
  }
  function restore(text) {
    var s = safe(function () { return JSON.parse(text); }, null);
    if (!isObj(s)) return;
    spec = {sandbox: 1, name: str(s.name), nodes: arr(s.nodes), edges: arr(s.edges), layout: isObj(s.layout) ? s.layout : {}};
    afterReplace();
  }
  function undo() {
    if (!undoStack.length) return;
    redoStack.push(snapshot());
    restore(undoStack.pop());
    lastUndoKey = null;
    note("Undone.");
  }
  function redo() {
    if (!redoStack.length) return;
    undoStack.push(snapshot());
    restore(redoStack.pop());
    lastUndoKey = null;
    note("Redone.");
  }

  // ---------------------------------------------------------------------------------------------
  // The page's fixed parts (shell.html).

  var board = $("sb-board"), stage = $("sb-stage"), edgeSvg = $("sb-edges"), edgeLayer = $("sb-edge-layer");
  var previewPath = $("sb-preview"), wirePath = $("sb-wire"), emptyEl = $("sb-empty");
  var ghostEl = $("sb-ghost"), ghostGlyph = $("sb-ghost-glyph"), ghostStage = $("sb-ghost-stage");
  var ghostTitle = $("sb-ghost-title"), ghostWhy = $("sb-ghost-why"), ringEl = $("sb-ring"), stripEl = $("sb-strip");
  var detail = $("sb-detail"), statusEl = $("sb-status");
  var statusMsg = el("span", "msg");

  // ---------------------------------------------------------------------------------------------
  // Geometry. Cards sit on the stage at spec.layout's places; rects caches their rectangles and
  // handle positions, rebuilt only when the layout changes, so a pointer move reads no page.

  var rects = [], rectById = new Map(), layoutDirty = true;
  var geo = {left: 0, top: 0, sl: 0, st: 0, cw: 0, ch: 0, dirty: true};

  function refreshGeo() {
    var r = board.getBoundingClientRect();
    geo.left = r.left + board.clientLeft;
    geo.top = r.top + board.clientTop;
    geo.sl = board.scrollLeft;
    geo.st = board.scrollTop;
    geo.cw = board.clientWidth;
    geo.ch = board.clientHeight;
    geo.dirty = false;
  }
  function toStage(cx, cy) {
    if (geo.dirty) refreshGeo();
    return {x: cx - geo.left + geo.sl, y: cy - geo.top + geo.st};
  }
  function posOf(id) {
    var p = isObj(spec.layout) ? spec.layout[id] : null;
    return Array.isArray(p) && p.length === 2 && typeof p[0] === "number" && typeof p[1] === "number" &&
      isFinite(p[0]) && isFinite(p[1]) ? p : null;
  }
  function setPos(id, x, y) {
    if (!isObj(spec.layout)) spec.layout = {};
    spec.layout[id] = [Math.max(0, Math.round(x)), Math.max(0, Math.round(y))];
    layoutDirty = true;
  }
  function handleY(i, n) { return Math.round(H * (i + 1) / (n + 1)); }
  function manifestOf(id) {
    var n = nodeIndex.get(id);
    return n && typeof n.block === "string" ? BLOCKS.get(n.block) : undefined;
  }
  function blockOfNode(id) {
    var n = nodeIndex.get(id);
    return n ? n.block : undefined;
  }
  function rectFor(id, x, y) {
    var m = manifestOf(id), ins = m ? arr(m.inputs) : [], outs = m ? arr(m.outputs) : [];
    return {
      id: id, x: x, y: y, r: x + W, b: y + H,
      ins: ins.map(function (p, i) { return {port: p.name, y: y + handleY(i, ins.length)}; }),
      outs: outs.map(function (p, i) { return {port: p.name, y: y + handleY(i, outs.length)}; })
    };
  }
  function moveRect(r, x, y) {
    var dy = y - r.y;
    r.x = x;
    r.y = y;
    r.r = x + W;
    r.b = y + H;
    r.ins.forEach(function (h) { h.y += dy; });
    r.outs.forEach(function (h) { h.y += dy; });
  }
  function rebuildRects() {
    rects = [];
    rectById = new Map();
    var missing = [];
    nodeIndex.forEach(function (n, id) {
      var p = posOf(id);
      if (!p) {
        missing.push(id);
        return;
      }
      var r = rectFor(id, p[0], p[1]);
      rects.push(r);
      rectById.set(id, r);
    });
    missing.forEach(function (id) {
      var spot = firstFreeSpot();
      setPos(id, spot.x, spot.y);
      var r = rectFor(id, spot.x, spot.y);
      rects.push(r);
      rectById.set(id, r);
    });
    layoutDirty = false;
  }
  function isFree(x, y, pad) {
    for (var i = 0; i < rects.length; i++) {
      var a = rects[i];
      if (x < a.r + pad && x + W > a.x - pad && y < a.b + pad && y + H > a.y - pad) return false;
    }
    return true;
  }
  function firstFreeSpot() {
    for (var col = 0; col < 80; col++) {
      for (var row = 0; row < 6; row++) {
        var x = ORIGIN + col * COL, y = ORIGIN + row * ROW;
        if (isFree(x, y, 10)) return {x: x, y: y};
      }
    }
    return {x: ORIGIN, y: ORIGIN};
  }
  // Where a block grown from r goes: one column to the right on the 20px grid, at r's height or in
  // the first free slot below it.
  function placeRightOf(r) {
    var x = snap(r.r + GHOST_DX), y = r.y;
    for (var i = 0; i < 80; i++, y += GRID) if (isFree(x, y, 18)) return {x: x, y: y};
    return {x: x, y: r.y};
  }
  function portY(list, port, r) {
    for (var i = 0; i < list.length; i++) if (list[i].port === port) return list[i].y;
    return r.y + H / 2;
  }
  function nearHandle(r, px, py) {
    var i;
    if (Math.abs(px - (r.r + 1)) <= HANDLE_R) {
      for (i = 0; i < r.outs.length; i++) if (Math.abs(py - r.outs[i].y) <= HANDLE_R) return true;
    }
    if (Math.abs(px - (r.x - 1)) <= HANDLE_R) {
      for (i = 0; i < r.ins.length; i++) if (Math.abs(py - r.ins[i].y) <= HANDLE_R) return true;
    }
    return false;
  }
  // The grow zone's anchor at a stage point: among the cards whose zone (right edge + 6 to + 260,
  // top - 30 to bottom + 30) holds the point, the one whose right-edge middle is nearest; none when
  // the point is on a card or a handle.
  function zoneAnchor(px, py) {
    var best = null, bestD = Infinity;
    for (var i = 0; i < rects.length; i++) {
      var r = rects[i];
      if (px >= r.x && px <= r.r && py >= r.y && py <= r.b) return null;
      if (nearHandle(r, px, py)) return null;
      if (px < r.r + ZONE_GAP || px > r.r + ZONE_REACH || py < r.y - ZONE_PAD || py > r.b + ZONE_PAD) continue;
      var dx = px - r.r, dy = py - (r.y + H / 2), d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = r.id;
      }
    }
    return best;
  }

  var stageW = 0, stageH = 0;
  function sizeStage() {
    var mx = 0, my = 0;
    rects.forEach(function (r) {
      if (r.r > mx) mx = r.r;
      if (r.b > my) my = r.b;
    });
    var w = Math.ceil(mx + 400), h = Math.ceil(my + 400);
    if (w !== stageW) {
      stageW = w;
      stage.style.width = w + "px";
      edgeSvg.setAttribute("width", String(w));
    }
    if (h !== stageH) {
      stageH = h;
      stage.style.height = h + "px";
      edgeSvg.setAttribute("height", String(h));
    }
  }
  function scrollIntoView(id) {
    var r = rectById.get(id);
    if (!r) return;
    refreshGeo();
    if (r.x < geo.sl || r.r + 20 > geo.sl + geo.cw) board.scrollLeft = Math.max(0, r.x - 40);
    if (r.y < geo.st || r.b + 20 > geo.st + geo.ch) board.scrollTop = Math.max(0, r.y - 40);
  }

  // ---------------------------------------------------------------------------------------------
  // Cards. One element per node, kept across redraws; v caches what was last written to it.

  var cards = new Map();

  function makeCard(id) {
    var e = el("div", "ncard");
    e.tabIndex = 0;
    e.setAttribute("role", "group");
    e.setAttribute("data-id", id);
    var glyph = el("span", "glyph");
    glyph.setAttribute("aria-hidden", "true");
    var text = el("span", "ntext"), row = el("span", "nrow");
    var step = el("span", "step"), job = el("span", "job none");
    var title = el("span", "ntitle"), short = el("span", "nshort");
    var err = el("span", "badge err"), fan = el("span", "badge fan");
    err.hidden = true;
    fan.hidden = true;
    row.appendChild(step);
    row.appendChild(job);
    text.appendChild(row);
    text.appendChild(title);
    text.appendChild(short);
    e.appendChild(glyph);
    e.appendChild(text);
    e.appendChild(err);
    e.appendChild(fan);
    return {el: e, glyph: glyph, step: step, job: job, title: title, short: short, err: err, fan: fan, ins: [], outs: [], blockKey: null, v: {}};
  }
  function fillCard(card, n, m) {
    card.glyph.innerHTML = draw(m ? m.glyph : "fallback");
    card.title.textContent = m ? m.title : String(n.block);
    card.short.textContent = m ? str(m.summary) : "This page has no block of that id: import it, or remove the node.";
    card.el.setAttribute("aria-label", m ? m.title : "unknown block " + String(n.block));
    var status = m && isObj(m.today) ? m.today.status : "";
    card.el.classList.toggle("planned", !!m && (status === "planned" || status === "pending") && !IMPORTED_IDS.has(m.id));
    card.el.classList.toggle("imported", !!m && IMPORTED_IDS.has(m.id));
    card.el.classList.toggle("unknown", !m);
    card.ins.concat(card.outs).forEach(function (h) { h.remove(); });
    card.ins = handles(card, m ? arr(m.inputs) : [], "hin");
    card.outs = handles(card, m ? arr(m.outputs) : [], "hout");
    card.v = {};
  }
  function handles(card, ports, cls) {
    return ports.map(function (p, i) {
      var h = el("span", cls + (p.optional ? " opt" : ""));
      h.setAttribute("data-port", p.name);
      h.title = p.name + (p.optional ? " (optional)" : "") + (p.what ? ": " + p.what : "");
      h.style.top = handleY(i, ports.length) + "px";
      card.el.appendChild(h);
      return h;
    });
  }
  function jobTag(id, m) {
    if (!m) return ["none", "unknown block"];
    if (m.stage === "source") return ["file", "data"];
    var row = planByNode.get(id);
    if (!row) return ["none", "no job"];
    if (row.rides_with) return ["phase", "in " + row.rides_with + "'s job"];
    if (row["class"] === "gpu" || row["class"] === "cpu") return [row["class"], row["class"].toUpperCase() + " " + hoursText(row.hours) + " h"];
    return ["none", "no job"];
  }
  function setOnce(card, key, value, apply) {
    if (card.v[key] !== value) {
      card.v[key] = value;
      apply(value);
    }
  }
  function updateCard(card, id, m) {
    var r = rectById.get(id);
    if (r) setOnce(card, "pos", r.x + "," + r.y, function () { card.el.style.transform = "translate(" + r.x + "px," + r.y + "px)"; });
    setOnce(card, "sel", id === selected, function (on) {
      if (on) card.el.setAttribute("aria-current", "true");
      else card.el.removeAttribute("aria-current");
    });
    setOnce(card, "step", id + " " + (m ? stageTitle(m.stage).toLowerCase() : "unknown"), function (t) { card.step.textContent = t; });
    var tag = jobTag(id, m);
    setOnce(card, "job", tag.join("|"), function () {
      card.job.className = "job " + tag[0];
      card.job.textContent = tag[1];
    });
    var errors = 0;
    (problemsByNode.get(id) || []).forEach(function (q) { if (q.level === "error") errors += 1; });
    setOnce(card, "err", errors, function (n) {
      card.err.hidden = n === 0;
      card.err.textContent = plural(n, "error");
    });
    var info = prop && isObj(prop.nodes) ? prop.nodes[id] : null;
    var fan = info ? info.fan || 1 : 1, combos = info ? info.combinations || 1 : 1;
    var many = Math.max(fan, combos);
    setOnce(card, "fan", many, function (k) {
      card.fan.hidden = k <= 1;
      card.fan.textContent = "x" + k;
      card.el.classList.toggle("deck", k > 1);
    });
  }
  function renderCards() {
    var seen = new Set();
    nodeIndex.forEach(function (n, id) {
      seen.add(id);
      var card = cards.get(id);
      if (!card) {
        card = makeCard(id);
        cards.set(id, card);
        stage.appendChild(card.el);
      }
      var m = typeof n.block === "string" ? BLOCKS.get(n.block) : undefined;
      var key = m ? m.id + ":" + (IMPORTED_IDS.has(m.id) ? "imported" + importRev : "repository") : "unknown:" + String(n.block);
      if (card.blockKey !== key) {
        card.blockKey = key;
        fillCard(card, n, m);
      }
      updateCard(card, id, m);
    });
    cards.forEach(function (card, id) {
      if (!seen.has(id)) {
        card.el.remove();
        cards.delete(id);
      }
    });
  }
  function markSelection() {
    cards.forEach(function (card, id) {
      setOnce(card, "sel", id === selected, function (on) {
        if (on) card.el.setAttribute("aria-current", "true");
        else card.el.removeAttribute("aria-current");
      });
    });
  }
  function focusCard(id) {
    var card = cards.get(id);
    if (card) card.el.focus();
  }

  // ---------------------------------------------------------------------------------------------
  // Edges: a cubic curve from the output handle to the input handle with an arrowhead, and the
  // type on it as a short label, at the curve's middle when that is clear of every card, else above
  // the higher of the two cards with a dotted leader down to the curve.

  var edgeEls = new Map(), edgesByNode = new Map();

  function edgeKey(e) { return e.from + "|" + e.out + "|" + e.to + "|" + e["in"]; }
  function curve(sx, sy, ex, ey) {
    var dx = Math.max(36, Math.abs(ex - sx) / 2);
    if (ex < sx + 24) dx = Math.max(dx, 90);
    return "M" + r1(sx) + " " + r1(sy) + " C" + r1(sx + dx) + " " + r1(sy) + " " + r1(ex - dx) + " " + r1(ey) + " " + r1(ex) + " " + r1(ey);
  }
  function outType(id, port) {
    var info = prop && isObj(prop.nodes) ? prop.nodes[id] : null;
    return info && isObj(info.outputs) && isObj(info.outputs[port]) ? info.outputs[port] : null;
  }
  function boxHitsCard(x, y, r, b) {
    for (var i = 0; i < rects.length; i++) {
      var a = rects[i];
      if (x < a.r + 8 && r > a.x - 8 && y < a.b + 2 && b > a.y - 2) return true;
    }
    return false;
  }
  function makeEdge() {
    var g = svgEl("g", {});
    var path = svgEl("path", {"class": "ep", "marker-end": "url(#sb-arrow)"});
    var lead = svgEl("path", {"class": "lead", d: "M0 0", visibility: "hidden"});
    var text = svgEl("text", {"class": "el", "text-anchor": "middle"});
    var title = svgEl("title", {});
    var words = document.createTextNode("");
    text.appendChild(title);
    text.appendChild(words);
    g.appendChild(path);
    g.appendChild(lead);
    g.appendChild(text);
    edgeLayer.appendChild(g);
    return {g: g, path: path, lead: lead, text: text, title: title, words: words, v: {}};
  }
  function drawEdge(item) {
    var e = item.e, a = rectById.get(e.from), b = rectById.get(e.to);
    if (!a || !b) return;
    var sx = a.r + 7, sy = portY(a.outs, e.out, a), ex = b.x - 7, ey = portY(b.ins, e["in"], b);
    var bad = badPorts.has(e.to + "|" + e["in"]);
    var type = outType(e.from, e.out);
    var full = type ? summaryOf(type) : "no type";
    var label = shorten(full, LABEL_MOST);
    var mx = (sx + ex) / 2, my = (sy + ey) / 2, w = label.length * 6.4 + 8;
    var lx = mx, ly = my - 4, lead = "";
    if (boxHitsCard(mx - w / 2, my - 15, mx + w / 2, my)) {
      ly = Math.min(a.y, b.y) - 13;
      lead = "M" + r1(mx) + " " + r1(ly + 4) + " V" + r1(my);
    }
    var v = item.v;
    var d = curve(sx, sy, ex, ey);
    if (v.d !== d) {
      v.d = d;
      item.path.setAttribute("d", d);
    }
    if (v.bad !== bad) {
      v.bad = bad;
      item.path.setAttribute("class", bad ? "ep bad" : "ep");
      item.path.setAttribute("marker-end", bad ? "url(#sb-arrow-bad)" : "url(#sb-arrow)");
      item.text.setAttribute("class", bad ? "el bad" : "el");
    }
    if (v.full !== full) {
      v.full = full;
      item.title.textContent = full;
      item.words.nodeValue = label;
    }
    var at = r1(lx) + "," + r1(ly);
    if (v.at !== at) {
      v.at = at;
      item.text.setAttribute("x", String(r1(lx)));
      item.text.setAttribute("y", String(r1(ly)));
    }
    if (v.lead !== lead) {
      v.lead = lead;
      if (lead) {
        item.lead.setAttribute("d", lead);
        item.lead.setAttribute("visibility", "visible");
      } else {
        item.lead.setAttribute("visibility", "hidden");
      }
    }
  }
  function renderEdges() {
    var seen = new Set();
    edgesByNode = new Map();
    spec.edges.forEach(function (e) {
      if (!isObj(e) || !rectById.has(e.from) || !rectById.has(e.to)) return;
      var key = edgeKey(e);
      if (seen.has(key)) return;
      seen.add(key);
      var item = edgeEls.get(key);
      if (!item) {
        item = makeEdge();
        edgeEls.set(key, item);
      }
      item.e = e;
      [e.from, e.to].forEach(function (id) {
        if (!edgesByNode.has(id)) edgesByNode.set(id, []);
        edgesByNode.get(id).push(key);
      });
      drawEdge(item);
    });
    edgeEls.forEach(function (item, key) {
      if (!seen.has(key)) {
        item.g.remove();
        edgeEls.delete(key);
      }
    });
  }
  function redrawEdgesOf(id) {
    (edgesByNode.get(id) || []).forEach(function (key) {
      var item = edgeEls.get(key);
      if (item) drawEdge(item);
    });
  }
  function edgeInto(id, port) {
    for (var i = 0; i < spec.edges.length; i++) {
      var e = spec.edges[i];
      if (isObj(e) && e.to === id && e["in"] === port) return e;
    }
    return null;
  }

  // ---------------------------------------------------------------------------------------------
  // Recomputing and redrawing. recompute asks the engine (propagate, then compile with the same
  // propagation) and redraws; redraw alone serves a change of layout, which no type depends on.

  var lastRecompute = 0;

  function indexNodes() {
    nodeIndex = new Map();
    spec.nodes.forEach(function (n) {
      if (isObj(n) && typeof n.id === "string" && !nodeIndex.has(n.id)) nodeIndex.set(n.id, n);
    });
  }
  function recompute() {
    var t0 = now();
    hideGhost();
    clearDwell();
    hov.anchor = null;
    indexNodes();
    prop = safe(function () { return SB.propagate(spec, DATA); }, null);
    if (!prop || !Array.isArray(prop.order)) prop = {order: [], nodes: {}, problems: []};
    comp = safe(function () { return SB.compile(spec, DATA, prop); }, null);
    if (!comp) {
      comp = {digest: "", route: "pipeline", ready: false, why: [{code: "engine", text: "the engine could not compile this spec"}],
        requests: [], plan: [], jobs: {cpu: {submissions: 0, tasks: 0, hours: 0}, gpu: {submissions: 0, tasks: 0, hours: 0}},
        pipeline_issue: {title: "Pipeline", body: ""}, problems: prop.problems.slice()};
    }
    version += 1;
    problemsByNode = new Map();
    badPorts = new Set();
    arr(comp.problems).forEach(function (q) {
      if (!q || q.node === null || q.node === undefined) return;
      if (!problemsByNode.has(q.node)) problemsByNode.set(q.node, []);
      problemsByNode.get(q.node).push(q);
      if (q.port && (q.code === "type" || q.code === "parts" || q.code === "port")) badPorts.add(q.node + "|" + q.port);
    });
    planByNode = new Map();
    arr(comp.plan).forEach(function (r) { planByNode.set(r.node, r); });
    redraw(true);
    maybePost();
    saveSoon();
    lastRecompute = now() - t0;
    record(timing.recompute, lastRecompute);
  }
  function redraw(engineChanged) {
    if (!engineChanged) indexNodes();
    rebuildRects();
    renderCards();
    renderEdges();
    sizeStage();
    emptyEl.hidden = nodeIndex.size > 0;
    renderToolbar();
    renderStatus();
    renderPanel(false);
    if (!engineChanged) saveSoon();
  }
  // After undo, redo, a template or New: the panel is built afresh.
  function afterReplace() {
    if (selected && !spec.nodes.some(function (n) { return isObj(n) && n.id === selected; })) selected = null;
    panelKey = "";
    recompute();
  }

  // ---------------------------------------------------------------------------------------------
  // Holding to the right of a block. The pointer resting in a block's grow zone for DWELL_MS shows
  // a ghost of the likeliest next block (SandboxEngine.predict) with a ring that fills in RING_MS;
  // a full ring adds the block, piped from the anchor's first output. hov is the hover's state.

  var hov = {x: -1e9, y: -1e9, ox: 0, oy: 0, anchor: null, blocked: null, suppressed: null, overStrip: false};
  var ghost = null, ghostRect = null, stripRect = null;
  var dwellTimer = 0, ringTimer = 0, ringAnim = null;
  var predCache = {version: -1, map: new Map()};
  var sugEls = [];

  function predictionsFor(id) {
    if (predCache.version !== version) predCache = {version: version, map: new Map()};
    if (!predCache.map.has(id)) {
      var list = safe(function () { return SB.predict(spec, id, DATA, STATS, history); }, []);
      predCache.map.set(id, arr(list).filter(function (p) { return isObj(p) && BLOCKS.has(p.block); }));
    }
    return predCache.map.get(id);
  }
  function noneReason(id) {
    var m = manifestOf(id), out = m && arr(m.outputs)[0];
    if (!m) return "this node's block is unknown here";
    if (!out) return "this block gives nothing to pipe on";
    var type = outType(id, out.name);
    if (!type) return "its output has no type yet; fix its inputs first";
    if (type.kind === "report") return "a report ends the pipeline";
    return "no block takes " + summaryOf(type);
  }
  function makeStrip() {
    for (var i = 0; i < 5; i++) {
      var b = el("button", "sug");
      b.type = "button";
      b.setAttribute("data-index", String(i));
      var glyph = el("span", "glyph"), text = el("span", "stext"), title = el("span", "stitle"), why = el("span", "swhy");
      glyph.setAttribute("aria-hidden", "true");
      text.appendChild(title);
      text.appendChild(why);
      b.appendChild(el("span", "key", String(i + 1)));
      b.appendChild(glyph);
      b.appendChild(text);
      stripEl.appendChild(b);
      sugEls.push({el: b, glyph: glyph, title: title, why: why});
    }
  }
  function fillGhost() {
    if (ghost.none) {
      ghostGlyph.hidden = true;
      ghostStage.textContent = "";
      ghostTitle.textContent = "nothing follows here";
      ghostWhy.textContent = noneReason(ghost.anchor);
      return;
    }
    var pred = ghost.preds[ghost.index], m = BLOCKS.get(pred.block);
    ghostGlyph.hidden = false;
    ghostGlyph.innerHTML = draw(m.glyph);
    ghostStage.textContent = stageTitle(m.stage).toLowerCase();
    ghostTitle.textContent = m.title;
    ghostWhy.textContent = pred.why;
    sugEls.forEach(function (s, i) {
      if (i < ghost.preds.length) s.el.setAttribute("aria-current", i === ghost.index ? "true" : "false");
    });
  }
  function fillStrip() {
    sugEls.forEach(function (s, i) {
      var pred = ghost.preds[i];
      s.el.hidden = !pred;
      if (!pred) return;
      var m = BLOCKS.get(pred.block);
      s.glyph.innerHTML = draw(m.glyph);
      s.title.textContent = m.title;
      s.why.textContent = pred.why;
      s.el.setAttribute("aria-label", (i + 1) + ": " + m.title + ", " + pred.why);
    });
  }
  // The strip goes right of the ghost when that is in view, else below it, else above it.
  // The strip goes right of the ghost, else below it, else above it. Under a mouse it must fit the
  // board's view as it stands; when the board will scroll to it (a finger, the keys), the view's size.
  function placeStrip(bring) {
    if (geo.dirty) refreshGeo();
    var n = ghost.preds.length, h = n * SUG_H + (n - 1) * 2 + 10, room = 32;
    var x = ghostRect.r + STRIP_GAP, y = ghostRect.y;
    var right = bring ? W + STRIP_GAP + STRIP_W + room <= geo.cw : x + STRIP_W <= geo.sl + geo.cw;
    if (!right) {
      var tall = H + STRIP_GAP + h + room <= geo.ch;
      var below = bring ? tall : ghostRect.b + STRIP_GAP + h <= geo.st + geo.ch;
      var above = ghostRect.y - STRIP_GAP - h >= (bring ? 0 : geo.st) && (!bring || tall);
      x = ghostRect.x;
      if (below) y = ghostRect.b + STRIP_GAP;
      else if (above) y = ghostRect.y - STRIP_GAP - h;
      else {
        x = ghostRect.r + STRIP_GAP;
        y = ghostRect.y;
      }
    }
    stripRect = {x: x, y: y, r: x + STRIP_W, b: y + h};
    stripEl.style.transform = "translate(" + x + "px," + y + "px)";
    stripEl.hidden = false;
  }
  function openGhost(anchorId, mode) {
    var r = rectById.get(anchorId);
    if (!r) return false;
    var preds = predictionsFor(anchorId), spot = placeRightOf(r);
    ghost = {anchor: anchorId, x: spot.x, y: spot.y, preds: preds, index: 0, mode: mode, none: preds.length === 0, kx: -1e9, ky: -1e9};
    ghostRect = {x: spot.x, y: spot.y, r: spot.x + W, b: spot.y + H};
    // A finger or the keys have no hover to find the ghost with, so the board brings it into view
    // (a mouse's ghost grows where the pointer already is, and scrolling under it would move it).
    var bring = mode === "key" || (mode === "press" && ptr && ptr.type === "touch");
    if (bring) reveal(ghostRect);
    ghostEl.style.transform = "translate(" + spot.x + "px," + spot.y + "px)";
    ghostEl.classList.toggle("none", ghost.none);
    fillGhost();
    if (ghost.none) {
      stripEl.hidden = true;
      stripRect = null;
      previewPath.setAttribute("visibility", "hidden");
    } else {
      fillStrip();
      fillGhost();
      placeStrip(bring);
      if (bring && stripRect) {
        reveal({x: Math.min(ghostRect.x, stripRect.x), y: Math.min(ghostRect.y, stripRect.y), r: Math.max(ghostRect.r, stripRect.r), b: Math.max(ghostRect.b, stripRect.b)});
        reveal(ghostRect);
      }
      var out = r.outs[0];
      previewPath.setAttribute("d", curve(r.r + 7, out ? out.y : r.y + H / 2, spot.x - 7, spot.y + H / 2));
      previewPath.setAttribute("visibility", "visible");
    }
    ghostEl.hidden = false;
    announce();
    return true;
  }
  // Scrolls the board so a rectangle of the stage is in view; when it cannot all fit, its top left wins.
  function reveal(r) {
    if (geo.dirty) refreshGeo();
    var pad = 16, sl = geo.sl, st = geo.st;
    if (r.r + pad > sl + geo.cw) sl = r.r + pad - geo.cw;
    if (r.x - pad < sl) sl = r.x - pad;
    if (r.b + pad > st + geo.ch) st = r.b + pad - geo.ch;
    if (r.y - pad < st) st = r.y - pad;
    sl = Math.max(0, Math.round(sl));
    st = Math.max(0, Math.round(st));
    if (sl !== geo.sl) board.scrollLeft = sl;
    if (st !== geo.st) board.scrollTop = st;
    geo.sl = board.scrollLeft;
    geo.st = board.scrollTop;
  }
  function announce() {
    if (!ghost) return;
    if (ghost.none) {
      note("Nothing follows " + ghost.anchor + ": " + noneReason(ghost.anchor) + ".");
      return;
    }
    var m = BLOCKS.get(ghost.preds[ghost.index].block);
    note("Next after " + ghost.anchor + ": " + m.title + " (" + (ghost.index + 1) + " of " + ghost.preds.length +
      "). Enter or a full ring adds it, the wheel or the arrows pick another, Escape cancels.");
  }
  function hideGhost() {
    stopRing();
    if (!ghost) return;
    ghost = null;
    ghostRect = null;
    stripRect = null;
    ghostEl.hidden = true;
    stripEl.hidden = true;
    previewPath.setAttribute("visibility", "hidden");
  }
  function startRing() {
    stopRing();
    if (!ghost || ghost.none) return;
    var full = RING_C.toFixed(2);
    if (typeof ringEl.animate === "function") {
      ringAnim = ringEl.animate([{strokeDashoffset: full}, {strokeDashoffset: "0"}], {duration: RING_MS, easing: "linear", fill: "forwards"});
    } else {
      ringEl.style.transition = "stroke-dashoffset " + RING_MS + "ms linear";
      ringEl.style.strokeDashoffset = "0";
    }
    ringTimer = setTimeout(function () {
      ringTimer = 0;
      commitGhost();
    }, RING_MS);
  }
  function stopRing() {
    if (ringTimer) {
      clearTimeout(ringTimer);
      ringTimer = 0;
    }
    if (ringAnim) {
      ringAnim.cancel();
      ringAnim = null;
    }
    if (ringEl.style.transition) {
      ringEl.style.transition = "";
      ringEl.style.strokeDashoffset = RING_C.toFixed(2);
    }
  }
  function clearDwell() {
    if (dwellTimer) {
      clearTimeout(dwellTimer);
      dwellTimer = 0;
    }
  }
  function startDwell() {
    clearDwell();
    dwellTimer = setTimeout(function () {
      dwellTimer = 0;
      if (ptr || !hov.anchor) return;
      if (!ghost || ghost.anchor !== hov.anchor) {
        hideGhost();
        if (!openGhost(hov.anchor, "hover")) return;
      }
      startRing();
    }, DWELL_MS);
  }
  function cycle(step) {
    if (!ghost || ghost.none) return;
    var n = ghost.preds.length;
    ghost.index = (ghost.index + step + n) % n;
    fillGhost();
    announce();
    startRing();
  }
  function cancelGhost() {
    if (!ghost) return;
    hov.suppressed = ghost.anchor;
    hov.anchor = null;
    clearDwell();
    hideGhost();
    note("Cancelled; move away from the block to start again.");
  }

  // The hover machine, run once a frame with the pointer's stage point.
  function hoverAt(px, py) {
    hov.x = px;
    hov.y = py;
    if (stripRect && inRect(stripRect, px, py)) {
      if (!hov.overStrip) {
        hov.overStrip = true;
        clearDwell();
        stopRing();
      }
      return;
    }
    var back = hov.overStrip;
    hov.overStrip = false;
    var anchor = ghostRect && inRect(ghostRect, px, py) ? ghost.anchor : zoneAnchor(px, py);
    if (hov.blocked && anchor !== hov.blocked) hov.blocked = null;
    if (hov.suppressed && anchor !== hov.suppressed) hov.suppressed = null;
    if (!anchor || anchor === hov.blocked || anchor === hov.suppressed) {
      if (hov.anchor || ghost) {
        hov.anchor = null;
        clearDwell();
        hideGhost();
      }
      return;
    }
    if (anchor !== hov.anchor) {
      hov.anchor = anchor;
      hov.ox = px;
      hov.oy = py;
      if (ghost && ghost.anchor !== anchor) hideGhost();
      stopRing();
      startDwell();
      return;
    }
    if (back || Math.abs(px - hov.ox) > MOVE_PX || Math.abs(py - hov.oy) > MOVE_PX) {
      hov.ox = px;
      hov.oy = py;
      stopRing();
      startDwell();
    }
  }

  // Adding the ghost's block (or the strip's index-th), then holding the anchor back until the
  // pointer leaves its zone: one card per hold.
  function commitGhost(index) {
    if (!ghost || ghost.none) return null;
    var pred = ghost.preds[index === undefined ? ghost.index : index];
    if (!pred) return null;
    var g = ghost;
    hideGhost();
    clearDwell();
    var id = growAt(g.anchor, pred.block, g.x, g.y);
    hov.blocked = g.anchor;
    hov.anchor = null;
    if (id && g.mode === "key") focusCard(id);
    return id;
  }
  function linkTo(anchorId, m, anyInput) {
    var am = manifestOf(anchorId), out = am && arr(am.outputs)[0], ins = arr(m.inputs);
    if (!out || !ins.length) return null;
    var type = outType(anchorId, out.name), port = null;
    for (var i = 0; i < ins.length && !port; i++) if (accepts(ins[i].accepts, type)) port = ins[i];
    if (!port && anyInput) port = ins[0];
    return port ? {from: anchorId, out: out.name, "in": port.name} : null;
  }
  function addNode(m, x, y, link) {
    var id = nextNodeId();
    if (!id) {
      note("The board holds the nodes n1 to n9999 at most.");
      return null;
    }
    pushUndo();
    spec.nodes.push({id: id, block: m.id, version: m.version, params: {}});
    setPos(id, x, y);
    if (link) {
      spec.edges.push({from: link.from, out: link.out, to: id, "in": link["in"]});
      learn(blockOfNode(link.from), m.id);
    }
    selected = id;
    recompute();
    return id;
  }
  function growAt(anchorId, blockId, x, y) {
    var t0 = now();
    var m = BLOCKS.get(blockId);
    if (!m || !nodeIndex.has(anchorId)) return null;
    var id = addNode(m, x, y, linkTo(anchorId, m, true));
    if (!id) return null;
    var ms = now() - t0;
    record(timing.commit, ms);
    note("Added " + m.title + " (" + id + ") after " + anchorId + " in " + ms.toFixed(1) + " ms.");
    return id;
  }
  function nodeNumber(id) { return ID_RE.test(String(id)) ? Number(String(id).slice(1)) : 0; }
  function nextNodeId() {
    var most = 0;
    spec.nodes.forEach(function (n) { if (isObj(n)) most = Math.max(most, nodeNumber(n.id)); });
    return most < 9999 ? "n" + (most + 1) : null;
  }

  // ---------------------------------------------------------------------------------------------
  // The pointer on the board. A pointermove only notes the point; frame() does the work once an
  // animation frame. ptr is the press in progress: press (in a grow zone or on the ghost), card (a
  // card pressed, a click until it moves), drag, connect, empty (a click until it moves) and pan.

  var ptr = null, lastMove = null, rafId = 0;

  function begin(e, mode) {
    var p = toStage(e.clientX, e.clientY);
    ptr = {id: e.pointerId, type: e.pointerType, mode: mode, cx: e.clientX, cy: e.clientY, x: p.x, y: p.y, t: now()};
    try {
      stage.setPointerCapture(e.pointerId);
    } catch (err) { /* capture is a convenience */ }
    clearDwell();
    if (mode !== "press") hideGhost();
    return p;
  }
  function onPointerDown(e) {
    if ((e.pointerType === "mouse" && e.button !== 0) || ptr) return;
    var t = e.target;
    if (!t || !t.closest || t.closest(".strip")) return;
    // A press on the board takes the keys back from a field left focused (the search box, a param),
    // so Escape, the digits, Delete and Ctrl+Z act on the board; a param's change lands on the blur.
    var active = document.activeElement;
    if (active && active !== document.body && isTyping(active) && typeof active.blur === "function") active.blur();
    refreshGeo();
    var handle = t.closest(".hin, .hout"), cardEl = t.closest(".ncard");
    if (handle && cardEl) {
      var nid = cardEl.getAttribute("data-id"), port = handle.getAttribute("data-port");
      if (handle.classList.contains("hout")) {
        begin(e, "connect");
        startConnect(nid, port, false);
        e.preventDefault();
        return;
      }
      var into = edgeInto(nid, port);
      if (into) {
        begin(e, "connect");
        pushUndo();
        spec.edges = spec.edges.filter(function (x) { return x !== into; });
        recompute();
        startConnect(into.from, into.out, true);
        e.preventDefault();
        return;
      }
    }
    if (cardEl) {
      begin(e, "card");
      ptr.node = cardEl.getAttribute("data-id");
      return;
    }
    if (ghost && t.closest(".ghost")) {
      begin(e, "press");
      ghost.mode = "press";
      if (!ringTimer && !ghost.none) startRing();
      e.preventDefault();
      return;
    }
    var p = toStage(e.clientX, e.clientY), anchor = zoneAnchor(p.x, p.y);
    if (anchor) {
      // A press is a fresh intent: it overrides an earlier Escape and the one-card-per-hold block,
      // which only keep a resting pointer from growing again.
      hov.suppressed = null;
      hov.blocked = null;
      begin(e, "press");
      hov.x = p.x;
      hov.y = p.y;
      if (!ghost || ghost.anchor !== anchor) {
        hideGhost();
        openGhost(anchor, "press");
      } else {
        ghost.mode = "press";
      }
      if (!ringTimer && ghost && !ghost.none) startRing();
      e.preventDefault();
      return;
    }
    begin(e, "empty");
  }
  function onPointerMove(e) {
    var t0 = now();
    lastMove = {cx: e.clientX, cy: e.clientY, type: e.pointerType, id: e.pointerId};
    if (!rafId) rafId = requestAnimationFrame(frame);
    record(timing.move, now() - t0);
  }
  function frame() {
    rafId = 0;
    var mv = lastMove;
    if (!mv) return;
    var t0 = now(), p = toStage(mv.cx, mv.cy);
    if (!ptr) {
      // A ghost the keys opened stays until the pointer itself moves; a scroll moves the stage under
      // a resting pointer, so the test is in the page's coordinates, not the stage's.
      if (ghost && ghost.mode === "key") {
        if (Math.abs(mv.cx - ghost.kx) <= MOVE_PX && Math.abs(mv.cy - ghost.ky) <= MOVE_PX) return;
        hideGhost();
      }
      // A chip carried over the board is a drop, not a hover: no ghost may grow under it.
      if (mv.type !== "touch" && !importOpen() && !chipDrag) hoverAt(p.x, p.y);
    } else if (mv.id === ptr.id) {
      pressFrame(p, mv);
    }
    record(timing.frame, now() - t0);
  }
  function pressFrame(p, mv) {
    var dx = Math.abs(mv.cx - ptr.cx), dy = Math.abs(mv.cy - ptr.cy);
    switch (ptr.mode) {
      case "press":
        if (dx > MOVE_PX || dy > MOVE_PX) {
          hideGhost();
          startPan();
          panTo(mv);
        }
        break;
      case "card":
        if (dx > DRAG_PX || dy > DRAG_PX) startDrag(p);
        break;
      case "drag":
        dragTo(p);
        break;
      case "connect":
        wirePath.setAttribute("d", curve(ptr.sx, ptr.sy, p.x, p.y));
        break;
      case "empty":
        if (dx > DRAG_PX || dy > DRAG_PX) {
          startPan();
          panTo(mv);
        }
        break;
      case "pan":
        panTo(mv);
        break;
    }
  }
  function onPointerUp(e) {
    if (!ptr || e.pointerId !== ptr.id) return;
    var P = ptr, p = toStage(e.clientX, e.clientY);
    ptr = null;
    try {
      stage.releasePointerCapture(e.pointerId);
    } catch (err) { /* already released */ }
    switch (P.mode) {
      case "press":
        if (!ghost) break;
        if (now() - P.t < TAP_MS) {
          commitGhost();
        } else if (P.type === "touch") {
          hov.anchor = null;
          hideGhost();
          note("Lifted before the ring filled: nothing added.");
        } else {
          ghost.mode = "hover";
          hov.anchor = ghost.anchor;
          hov.ox = p.x;
          hov.oy = p.y;
        }
        break;
      case "card":
        select(P.node, true);
        break;
      case "drag":
        endDrag(P);
        break;
      case "connect":
        endConnect(P, p);
        break;
      case "empty":
        select(null, false);
        break;
      case "pan":
        board.classList.remove("panning");
        break;
    }
  }
  function onPointerCancel(e) {
    if (!ptr || e.pointerId !== ptr.id) return;
    var P = ptr;
    ptr = null;
    if (P.mode === "press") hideGhost();
    else if (P.mode === "drag") endDrag(P);
    else if (P.mode === "connect") endConnect(P, null);
    board.classList.remove("panning");
  }

  function startPan() {
    ptr.mode = "pan";
    ptr.sl = board.scrollLeft;
    ptr.st = board.scrollTop;
    board.classList.add("panning");
  }
  function panTo(mv) {
    board.scrollLeft = ptr.sl - (mv.cx - ptr.cx);
    board.scrollTop = ptr.st - (mv.cy - ptr.cy);
  }

  // Dragging a card: it snaps to the 20px grid and only its own edges are redrawn as it moves.
  function startDrag(p) {
    var r = rectById.get(ptr.node), card = cards.get(ptr.node);
    if (!r || !card) {
      ptr.mode = "done";
      return;
    }
    ptr.mode = "drag";
    ptr.dx = ptr.x - r.x;
    ptr.dy = ptr.y - r.y;
    ptr.x0 = r.x;
    ptr.y0 = r.y;
    ptr.pushed = false;
    card.el.classList.add("dragging");
    dragTo(p);
  }
  function dragTo(p) {
    var r = rectById.get(ptr.node);
    if (!r) return;
    var x = Math.max(0, snap(p.x - ptr.dx)), y = Math.max(0, snap(p.y - ptr.dy));
    if (x === r.x && y === r.y) return;
    if (!ptr.pushed) {
      pushUndo();
      ptr.pushed = true;
    }
    moveRect(r, x, y);
    spec.layout[ptr.node] = [x, y];
    var card = cards.get(ptr.node);
    if (card) {
      card.v.pos = x + "," + y;
      card.el.style.transform = "translate(" + x + "px," + y + "px)";
    }
    redrawEdgesOf(ptr.node);
  }
  function endDrag(P) {
    var card = cards.get(P.node);
    if (card) card.el.classList.remove("dragging");
    if (!P.pushed) return;
    sizeStage();
    renderEdges();
    renderToolbar();
    saveSoon();
    note("Moved " + P.node + ".");
  }

  // Connecting: from an output handle to an input handle. Inputs that accept the type glow; a drop
  // on any input connects (a refused one then shows its problem); a drop on empty board cancels.
  function startConnect(from, out, picked) {
    var type = outType(from, out), r = rectById.get(from);
    ptr.mode = "connect";
    ptr.from = from;
    ptr.out = out;
    ptr.picked = picked;
    ptr.sx = r ? r.r + 7 : ptr.x;
    ptr.sy = r ? portY(r.outs, out, r) : ptr.y;
    board.classList.add("connecting");
    cards.forEach(function (card, id) {
      var m = manifestOf(id), ins = m ? arr(m.inputs) : [];
      card.ins.forEach(function (h, i) {
        var ok = id !== from && !!ins[i] && accepts(ins[i].accepts, type);
        h.classList.toggle("ok", ok);
        h.classList.toggle("no", !ok);
      });
    });
    wirePath.setAttribute("d", curve(ptr.sx, ptr.sy, ptr.x, ptr.y));
    wirePath.setAttribute("visibility", "visible");
  }
  function dropTarget(p) {
    var i, k, r;
    for (i = 0; i < rects.length; i++) {
      r = rects[i];
      for (k = 0; k < r.ins.length; k++) {
        if (Math.abs(p.x - (r.x - 1)) <= HANDLE_R + 3 && Math.abs(p.y - r.ins[k].y) <= HANDLE_R + 3) return {node: r.id, port: r.ins[k].port};
      }
    }
    for (i = 0; i < rects.length; i++) {
      r = rects[i];
      if (!inRect(r, p.x, p.y) || !r.ins.length) continue;
      var card = cards.get(r.id), at = 0;
      if (card) {
        for (k = 0; k < card.ins.length; k++) {
          if (card.ins[k].classList.contains("ok")) {
            at = k;
            break;
          }
        }
      }
      return {node: r.id, port: r.ins[at].port};
    }
    return null;
  }
  function endConnect(P, p) {
    var target = p ? dropTarget(p) : null;
    board.classList.remove("connecting");
    cards.forEach(function (card) {
      card.ins.forEach(function (h) {
        h.classList.remove("ok");
        h.classList.remove("no");
      });
    });
    wirePath.setAttribute("visibility", "hidden");
    if (!target || target.node === P.from) {
      if (P.picked) note("Disconnected.");
      return;
    }
    if (!P.picked) pushUndo();
    spec.edges = spec.edges.filter(function (x) { return !(isObj(x) && x.to === target.node && x["in"] === target.port); });
    spec.edges.push({from: P.from, out: P.out, to: target.node, "in": target.port});
    learn(blockOfNode(P.from), blockOfNode(target.node));
    recompute();
    note("Connected " + P.from + "." + P.out + " to " + target.node + "." + target.port + ".");
  }

  // The wheel picks another suggestion while a ghost is up, and scrolls the board otherwise.
  var wheelSum = 0, wheelAt = 0, wheelStep = 0;
  function onWheel(e) {
    if (!ghost || ghost.none) return;
    e.preventDefault();
    var t = now();
    if (t - wheelAt > 300) wheelSum = 0;
    wheelAt = t;
    var unit = e.deltaMode === 1 ? 40 : (e.deltaMode === 2 ? 400 : 1);
    var d = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
    wheelSum += d * unit;
    if (Math.abs(wheelSum) >= 40 && t - wheelStep >= 90) {
      cycle(wheelSum > 0 ? 1 : -1);
      wheelSum = 0;
      wheelStep = t;
    }
  }

  // ---------------------------------------------------------------------------------------------
  // Keys. With a ghost up: arrows pick, 1-5 add at once, Enter adds, Escape cancels. A focused card
  // takes Enter (select) and Shift+ArrowRight (the ghost for it); Delete removes the selection.

  function onKeyDown(e) {
    var typing = isTyping(e.target), plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if (ghost && plain && e.key === "Escape") {
      // Escape cancels a ghost wherever the focus is: a search box left focused must not keep it alive.
      e.preventDefault();
      cancelGhost();
      return;
    }
    if (ghost && plain && !takesText(e.target)) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        cycle(e.key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (/^[1-5]$/.test(e.key) && !e.shiftKey) {
        e.preventDefault();
        commitGhost(Number(e.key) - 1);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        commitGhost();
        return;
      }
    }
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "z" || e.key === "Z" || e.key === "y")) {
      if (typing) return;
      e.preventDefault();
      if (e.shiftKey || e.key === "y") redo();
      else undo();
      return;
    }
    if (e.key === "Escape") {
      if (importOpen()) closeImport();
      else if (ptr && ptr.mode === "connect") onPointerCancel({pointerId: ptr.id});
      else if (selected || sheetOpen) closeSheet();
      return;
    }
    if (typing || !plain) return;
    var cardEl = e.target && e.target.closest ? e.target.closest(".ncard") : null;
    if (cardEl) {
      var id = cardEl.getAttribute("data-id");
      if (e.key === "ArrowRight" && e.shiftKey) {
        e.preventDefault();
        hideGhost();
        if (openGhost(id, "key")) {
          ghost.kx = lastMove ? lastMove.cx : -1e9;
          ghost.ky = lastMove ? lastMove.cy : -1e9;
          startRing();
        }
        return;
      }
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        select(id, true);
        return;
      }
    }
    if ((e.key === "Delete" || e.key === "Backspace") && selected && !e.shiftKey) {
      e.preventDefault();
      removeNode(selected);
    }
  }

  // ---------------------------------------------------------------------------------------------
  // The detail panel: the selected node, or the whole pipeline when nothing is selected. A node's
  // panel is built once and its changing parts refreshed in place, so an edit in the params editor
  // keeps its field and its focus while the engine re-runs on every keystroke.

  var panelKey = "", np = null, sum = null, dispatchNote = "";

  var panelScrolled = false;
  detail.addEventListener("scroll", function () { panelScrolled = detail.scrollTop > 0; }, {passive: true});
  function renderPanel(force) {
    var id = selected && nodeIndex.has(selected) ? selected : null;
    if (!id) selected = null;
    var card = id ? cards.get(id) : null;
    var key = id ? "node:" + id + ":" + (card ? card.blockKey : "") : "summary";
    if (force || key !== panelKey) {
      // Another node (or the summary) starts at its top; a forced rebuild of the same one keeps the place.
      // Only a panel the viewer scrolled is reset, and on the next frame, so a commit forces no layout.
      if (key !== panelKey && panelScrolled) {
        panelScrolled = false;
        requestAnimationFrame(function () { detail.scrollTop = 0; });
      }
      panelKey = key;
      clear(detail);
      np = null;
      sum = null;
      if (id) buildNodePanel(id);
      else buildSummary();
    } else if (id) {
      refreshNodePanel();
    } else {
      refreshSummary();
    }
    detail.classList.toggle("open", sheetOpen);
    document.body.classList.toggle("sheet-open", sheetOpen);
  }
  function select(id, open) {
    selected = id && nodeIndex.has(id) ? id : null;
    if (open !== undefined) sheetOpen = !!open;
    markSelection();
    renderPanel(false);
  }
  function closeSheet() {
    sheetOpen = false;
    select(null);
  }
  function section(title, parent) {
    var s = el("div", "dsec"), body = el("div", "dsec");
    s.appendChild(el("div", "eyebrow", title));
    s.appendChild(body);
    (parent || detail).appendChild(s);
    return body;
  }
  function kv(rows) {
    var d = el("div", "kv");
    rows.forEach(function (r) {
      d.appendChild(el("div", "k", r[0]));
      d.appendChild(el("div", null, r[1]));
    });
    return d;
  }
  function problemsOf(id) { return problemsByNode.get(id) || []; }
  function fillProblems(body, list, linkNodes) {
    clear(body);
    if (!list.length) {
      body.appendChild(el("div", "small", "none"));
      return;
    }
    var ul = el("ul", "probs");
    list.forEach(function (q) {
      var li = el("li", "prob" + (q.level === "warn" ? " warn" : ""));
      if (linkNodes && q.node && nodeIndex.has(q.node)) li.appendChild(button("linkbtn", q.node, function () { select(q.node, true); }));
      li.appendChild(el("span", "code", q.code + (q.port ? " " + q.port : "") + (q.field ? " " + q.field : "")));
      li.appendChild(document.createTextNode(str(q.text)));
      ul.appendChild(li);
    });
    body.appendChild(ul);
  }
  function patternWords(p) {
    if (!isObj(p)) return "nothing (no pattern)";
    var bits = [arr(p.kind).join(" or ") || "no kind"];
    if (Array.isArray(p.rank)) bits.push(p.rank.join(" or ") + "-D");
    if (p.time === "yes") bits.push("with a time axis");
    if (p.time === "no") bits.push("no time axis");
    if (arr(p.has_axes).length) bits.push("with " + p.has_axes.join(", "));
    if (Array.isArray(p.dtype)) bits.push(p.dtype.join(" or "));
    if (Array.isArray(p.targets)) bits.push("targets " + p.targets.join(" or "));
    if (p.parts === "split") bits.push("split");
    if (p.parts === "unsplit") bits.push("unsplit");
    if (arr(p.needs_parts).length) bits.push("with the parts " + p.needs_parts.join(", "));
    if (Array.isArray(p.modality)) bits.push(p.modality.join(" or "));
    if (p.trained === true) bits.push("trained");
    if (p.trained === false) bits.push("untrained");
    return bits.join(", ");
  }
  function todayWords(m) {
    if (IMPORTED_IDS.has(m.id)) return "imported: not in the repository";
    var t = isObj(m.today) ? m.today : {};
    switch (t.status) {
      case "live": return "requestable now (experiment route)";
      case "word": return "the gate word " + str(t.word) + " runs it";
      case "flow": return "runs inside " + str(t.flow);
      case "pending":
        var pr = /#[0-9]+/.exec(str(t.note));
        return "built on " + (pr ? pr[0] : str(t.note)) + ", not merged";
      case "planned": return "not built yet; waits for the pipeline route";
      default: return "not recorded";
    }
  }
  function todayShort(m, today) {
    if (m && IMPORTED_IDS.has(m.id)) return "imported: not in the repository";
    var t = isObj(today) ? today : {};
    if (t.status === "word") return "word: " + str(t.word);
    if (t.status === "flow") return "flow: " + str(t.flow);
    if (t.status === "pending") {
      var pr = /#[0-9]+/.exec(str(t.note));
      return "pending" + (pr ? " " + pr[0] : "");
    }
    return str(t.status) || "not recorded";
  }

  function buildNodePanel(id) {
    var n = nodeIndex.get(id), m = manifestOf(id);
    var head = el("div", "dhead"), left = el("div"), right = el("div", "row");
    left.appendChild(el("div", "eyebrow", (m ? stageTitle(m.stage) : "unknown block") + " / " + id));
    left.appendChild(el("div", "dtitle", m ? m.title : String(n.block)));
    right.appendChild(button("linkbtn", "The pipeline", function () { select(null, true); }));
    right.appendChild(button("sheet-close", "Close", closeSheet));
    head.appendChild(left);
    head.appendChild(right);
    detail.appendChild(head);
    np = {id: id, prms: []};
    var jobRow = el("div", "row");
    np.job = el("span", "job none");
    np.fan = el("span", "small");
    jobRow.appendChild(np.job);
    jobRow.appendChild(np.fan);
    detail.appendChild(jobRow);
    var big = el("div", "big");
    big.innerHTML = draw(m ? m.glyph : "fallback");
    var svg = big.firstChild;
    svg.removeAttribute("aria-hidden");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", m ? m.title : "an unknown block");
    detail.appendChild(big);
    if (!m) {
      detail.appendChild(el("p", "note warn", "This node names the block " + String(n.block) +
        ", which this page does not have: import its manifest with Import a block, or remove the node."));
    } else {
      if (IMPORTED_IDS.has(m.id)) detail.appendChild(el("p", "note warn", "Imported, not in the repository: a pipeline that uses it runs only after its pull request merges."));
      detail.appendChild(el("p", null, m.does));
      np.takes = section("takes");
      np.gives = section("gives");
      np.adapt = el("div", "adapt");
      np.adapt.hidden = true;
      detail.appendChild(np.adapt);
      if (arr(m.params).length) {
        var box = el("div", "params");
        section("params").appendChild(box);
        m.params.forEach(function (p) {
          if (!isObj(p) || typeof p.name !== "string") return;
          var row = paramRow(id, p);
          box.appendChild(row.el);
          np.prms.push(row);
        });
      }
      if (m.stage === "source" && isObj(m.card)) {
        var cd = m.card;
        section("the data").appendChild(kv([["origin", str(cd.origin)], ["where", str(cd.where)], ["count", str(cd.count)],
          ["persons", str(cd.persons)], ["split", str(cd.split)], ["held out", str(cd.held_out)], ["licence", str(cd.licence)],
          ["from", arr(cd.from).join(", ")]]));
      }
      np.lineage = section("lineage");
      np.resources = section("resources");
    }
    np.problems = section("problems");
    var rr = el("div", "row");
    rr.appendChild(button("tb", "Remove this block", function () { removeNode(id); }));
    detail.appendChild(rr);
    refreshNodePanel();
  }
  function refreshNodePanel() {
    if (!np) return;
    var id = np.id, n = nodeIndex.get(id), m = manifestOf(id);
    if (!n) return;
    var tag = jobTag(id, m), info = prop && isObj(prop.nodes) ? prop.nodes[id] : null;
    np.job.className = "job " + tag[0];
    np.job.textContent = tag[1];
    var fan = info ? info.fan || 1 : 1, combos = info ? info.combinations || 1 : 1;
    np.fan.textContent = fan > 1 || combos > 1 ? "fan " + fan + ", " + plural(combos, "combination") + " of its own" : "one run";
    if (m) {
      fillTakes(np.takes, id, m, info);
      fillGives(np.gives, m, info);
      var first = arr(m.outputs)[0], type = first && info && isObj(info.outputs) ? info.outputs[first.name] : null;
      var adapt = type && (type.kind === "model" || type.kind === "checkpoint") && typeof m.resolve === "string" ?
        safe(function () { return SB.resolveText(m, type); }, "") : "";
      np.adapt.hidden = !adapt;
      np.adapt.textContent = adapt ? "adapts to the data: " + adapt : "";
      var eff = safe(function () { return SB.effectiveParams(n, m); }, {});
      np.prms.forEach(function (row) { row.update(eff, n); });
      fillLineage(np.lineage, type);
      fillResources(np.resources, id, m, info);
    }
    fillProblems(np.problems, problemsOf(id), false);
  }
  function fillTakes(body, id, m, info) {
    clear(body);
    var ins = arr(m.inputs);
    if (!ins.length) {
      body.appendChild(el("div", "small", "nothing: a source starts a pipeline"));
      return;
    }
    ins.forEach(function (p) {
      var e = edgeInto(id, p.name), type = info && isObj(info.inputs) ? info.inputs[p.name] : null;
      var probs = problemsOf(id).filter(function (q) { return q.port === p.name && q.code !== "op"; });
      var bad = probs.some(function (q) { return q.level === "error"; });
      var box = el("div", "port" + (bad ? " bad" : (e ? " ok" : "")));
      box.appendChild(el("span", "pn", p.name + (p.optional ? " (optional)" : "") + (e ? ", from " + e.from + "." + e.out : "")));
      box.appendChild(el("span", "pt", "takes " + patternWords(p.accepts)));
      box.appendChild(el("span", "pt", e ? (type ? summaryOf(type) : "no type yet") : "not connected"));
      probs.forEach(function (q) { box.appendChild(el("span", "prm-bad", str(q.text))); });
      if (e) {
        box.appendChild(button("linkbtn", "Disconnect", function () {
          pushUndo();
          spec.edges = spec.edges.filter(function (x) { return x !== e; });
          recompute();
        }));
      }
      body.appendChild(box);
    });
  }
  function fillGives(body, m, info) {
    clear(body);
    arr(m.outputs).forEach(function (o) {
      var type = info && isObj(info.outputs) ? info.outputs[o.name] : null;
      var box = el("div", "port ok");
      box.appendChild(el("span", "pn", o.name));
      box.appendChild(el("span", "pt", type ? summaryOf(type) : "no type"));
      if (o.what) box.appendChild(el("span", "small", o.what));
      body.appendChild(box);
    });
  }
  function fillLineage(body, t) {
    clear(body);
    if (!isObj(t)) {
      body.appendChild(el("div", "small", "no type yet"));
      return;
    }
    body.appendChild(kv([
      ["sources", arr(t.sources).join(", ") || "none"],
      ["licence", str(t.licence)],
      ["persons", t.persons ? "the person key rides along" : "no person key"],
      ["parts", arr(t.parts).join(", ") || "unsplit"],
      ["modality", str(t.modality)]
    ]));
  }
  function fillResources(body, id, m, info) {
    clear(body);
    var job = isObj(m.job) ? m.job : {}, row = planByNode.get(id), cls = str(job["class"]) || "none";
    var subs = row ? (row.rides_with ? "0: it rides in " + row.rides_with + "'s job" : String(row.submissions)) : "0";
    var rows = [
      ["job", cls === "none" ? "none of its own" : cls.toUpperCase() + (job.with_upstream ? ", inside its upstream job when that is " + cls.toUpperCase() : "") +
        (job.array ? ", one array job" : "")],
      ["hours", row ? hoursText(row.hours) + " h a task" : (cls === "none" ? "none" : "not planned")],
      ["fan", String(info ? info.fan || 1 : 1)],
      ["submissions", subs]
    ];
    if (cls !== "none") rows.push(["machine", job.cpus + " CPUs, " + job.memory_gb + " GB"]);
    rows.push(["today", todayWords(m)]);
    var t = isObj(m.today) ? m.today : {};
    if (str(t.note)) rows.push(["note", str(t.note)]);
    rows.push(["code", arr(m.implemented_by).join(", ") || str(m.code)]);
    body.appendChild(kv(rows));
  }

  // The params editor: choices as segmented buttons, numbers as number inputs, a bool as a
  // checkbox, a set as checkboxes in option order and names as text; a param with vary true has a
  // vary toggle that turns its editor into a list of values separated by "/".
  function paramRow(id, p) {
    var row = el("div", "prm"), head = el("div", "prm-head");
    head.appendChild(el("span", "prm-name", p.name));
    var varyBtn = null;
    if (p.vary === true) {
      varyBtn = button("vary", "vary", null, "Sweep " + p.name + " over several values, one run each");
      varyBtn.setAttribute("aria-pressed", "false");
      head.appendChild(varyBtn);
    }
    row.appendChild(head);
    if (p.what) row.appendChild(el("div", "prm-what", p.what));
    var box = el("div"), bad = el("div", "prm-bad");
    bad.hidden = true;
    row.appendChild(box);
    row.appendChild(bad);
    var ctl = null, varied = null;
    function build(isVaried) {
      varied = isVaried;
      clear(box);
      ctl = isVaried ? varyControl(id, p) : valueControl(id, p);
      box.appendChild(ctl.el);
      if (varyBtn) varyBtn.setAttribute("aria-pressed", isVaried ? "true" : "false");
    }
    if (varyBtn) varyBtn.addEventListener("click", function () { toggleVary(id, p, !varied); });
    return {
      el: row,
      name: p.name,
      focus: function () { if (ctl && ctl.focus) ctl.focus(); },
      update: function (eff, node) {
        var list = isObj(node.vary) && Array.isArray(node.vary[p.name]) ? node.vary[p.name] : null;
        if (varied !== (list !== null)) build(list !== null);
        ctl.set(list !== null ? list : eff[p.name]);
        var probs = problemsOf(id).filter(function (q) { return q.field === p.name && (q.code === "param" || q.code === "vary"); });
        bad.hidden = !probs.length;
        bad.textContent = probs.map(function (q) { return str(q.text); }).join("; ");
      }
    };
  }
  function valueControl(id, p) {
    if (p.kind === "choice") {
      var segs = el("div", "segs");
      segs.setAttribute("role", "group");
      segs.setAttribute("aria-label", p.name);
      var choices = arr(p.choices);
      var buttons = choices.map(function (choice) {
        var b = button("seg", choice, function () { setParam(id, p, choice); });
        b.setAttribute("aria-pressed", "false");
        segs.appendChild(b);
        return b;
      });
      return {el: segs, set: function (v) { buttons.forEach(function (b, i) { b.setAttribute("aria-pressed", choices[i] === v ? "true" : "false"); }); }};
    }
    if (p.kind === "int" || p.kind === "float") {
      var input = el("input", "field");
      input.type = "number";
      input.setAttribute("aria-label", p.name);
      if (typeof p.low === "number") input.min = String(p.low);
      if (typeof p.high === "number") input.max = String(p.high);
      input.step = p.kind === "int" ? "1" : "any";
      input.addEventListener("input", function () {
        var text = input.value.trim(), v = Number(text);
        if (text !== "" && isFinite(v)) setParam(id, p, v);
      });
      return {el: input, focus: function () { input.focus(); }, set: function (v) {
        if (document.activeElement !== input) input.value = typeof v === "number" ? String(v) : "";
      }};
    }
    if (p.kind === "bool") {
      var lab = el("label", "checks"), cb = el("input");
      cb.type = "checkbox";
      lab.appendChild(cb);
      lab.appendChild(el("span", null, "on"));
      cb.addEventListener("change", function () { setParam(id, p, cb.checked); });
      return {el: lab, set: function (v) { cb.checked = v === true; }};
    }
    if (p.kind === "set") {
      var wrap = el("div", "checks"), options = arr(p.options), boxes = [];
      wrap.setAttribute("role", "group");
      wrap.setAttribute("aria-label", p.name);
      options.forEach(function (opt) {
        var l = el("label"), b = el("input");
        b.type = "checkbox";
        l.appendChild(b);
        l.appendChild(el("span", null, opt));
        wrap.appendChild(l);
        b.addEventListener("change", function () {
          setParam(id, p, options.filter(function (o, i) { return boxes[i].checked; }));
        });
        boxes.push(b);
      });
      return {el: wrap, set: function (v) { var list = arr(v); boxes.forEach(function (b, i) { b.checked = list.indexOf(options[i]) >= 0; }); }};
    }
    var text = el("input", "field wide");
    text.type = "text";
    text.autocomplete = "off";
    text.spellcheck = false;
    text.setAttribute("aria-label", p.name);
    if (p.kind === "names") text.placeholder = "names separated by commas";
    text.addEventListener("input", function () { setParam(id, p, p.kind === "names" ? splitList(text.value, ",") : text.value); });
    return {el: text, focus: function () { text.focus(); }, set: function (v) {
      if (document.activeElement !== text) text.value = Array.isArray(v) ? v.join(", ") : (v === undefined || v === null ? "" : String(v));
    }};
  }
  function valueText(v) {
    if (Array.isArray(v)) return v.length ? v.join(",") : "none";
    return String(v);
  }
  function parseOne(s, p) {
    if (p.kind === "int" || p.kind === "float") return /^[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)$/.test(s) ? Number(s) : s;
    if (p.kind === "bool") return s === "true" || s === "on" ? true : (s === "false" || s === "off" ? false : s);
    if (p.kind === "set" || p.kind === "names") return s === "none" ? [] : splitList(s, ",");
    return s;
  }
  function varyControl(id, p) {
    var input = el("input", "field wide");
    input.type = "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = "values separated by /";
    input.setAttribute("aria-label", p.name + ": values separated by /");
    input.addEventListener("input", function () {
      var values = splitList(input.value, "/").map(function (s) { return parseOne(s, p); });
      var n = nodeIndex.get(id);
      if (!n) return;
      pushUndoFor(id + ".vary." + p.name);
      if (!isObj(n.vary)) n.vary = {};
      n.vary[p.name] = values;
      recompute();
    });
    return {el: input, focus: function () { input.focus(); }, set: function (list) {
      if (document.activeElement !== input) input.value = arr(list).map(valueText).join(" / ");
    }};
  }
  function setParam(id, p, value) {
    var n = nodeIndex.get(id);
    if (!n) return;
    pushUndoFor(id + "." + p.name);
    if (!isObj(n.params)) n.params = {};
    if (same(p["default"], value)) delete n.params[p.name];
    else n.params[p.name] = value;
    recompute();
  }
  function toggleVary(id, p, on) {
    var n = nodeIndex.get(id), m = manifestOf(id);
    if (!n || !m) return;
    pushUndo();
    if (on) {
      var eff = safe(function () { return SB.effectiveParams(n, m); }, {});
      if (!isObj(n.vary)) n.vary = {};
      n.vary[p.name] = [clone(eff[p.name])];
    } else if (isObj(n.vary)) {
      delete n.vary[p.name];
      if (!Object.keys(n.vary).length) delete n.vary;
    }
    recompute();
    if (on && np) np.prms.forEach(function (row) { if (row.name === p.name) row.focus(); });
  }
  function removeNode(id) {
    if (!nodeIndex.has(id)) return;
    pushUndo();
    spec.nodes = spec.nodes.filter(function (n) { return !(isObj(n) && n.id === id); });
    spec.edges = spec.edges.filter(function (e) { return !(isObj(e) && (e.from === id || e.to === id)); });
    if (isObj(spec.layout)) delete spec.layout[id];
    if (selected === id) selected = null;
    recompute();
    note("Removed " + id + ".");
  }

  // The summary: the name, the digest, the route's verdict, the totals, the plan, the problems
  // and the requests. Everything below the name is rebuilt on each change.
  function buildSummary() {
    var head = el("div", "dhead"), left = el("div");
    left.appendChild(el("div", "eyebrow", "the whole pipeline"));
    left.appendChild(el("div", "dtitle", "Pipeline"));
    head.appendChild(left);
    head.appendChild(button("sheet-close", "Close", closeSheet));
    detail.appendChild(head);
    var nameBox = el("div", "dsec"), label = el("label", "small", "Name"), name = el("input", "field wide");
    name.id = "sb-name";
    label.htmlFor = "sb-name";
    name.type = "text";
    name.maxLength = 120;
    name.autocomplete = "off";
    name.spellcheck = false;
    name.addEventListener("input", function () {
      pushUndoFor("name");
      spec.name = name.value;
      recompute();
    });
    nameBox.appendChild(label);
    nameBox.appendChild(name);
    detail.appendChild(nameBox);
    sum = {name: name, parts: []};
    refreshSummary();
  }
  function refreshSummary() {
    if (!sum) return;
    if (document.activeElement !== sum.name) sum.name.value = str(spec.name);
    sum.parts.forEach(function (part) { part.remove(); });
    sum.parts = [];
    function add(node) {
      detail.appendChild(node);
      sum.parts.push(node);
    }
    var t = templateById(template);
    if (t && t.about) add(el("p", "small", "Started from the template " + t.name + ": " + t.about));
    var dg = el("div", "digest"), copied = el("span", "small");
    dg.appendChild(el("span", "small", "digest"));
    dg.appendChild(el("code", null, comp.digest ? comp.digest.slice(0, 12) : "none"));
    dg.appendChild(button("tb", "Copy", function () {
      var hex = comp.digest;
      copyText(hex, function (ok) {
        copied.textContent = ok ? "copied" : "";
        if (!ok) showCopyBox(hex, "The digest");
      });
    }, "Copy the whole SHA-256 digest of the canonical spec"));
    dg.appendChild(copied);
    add(dg);
    add(verdictEl());
    add(tilesEl());
    add(planEl());
    var ps = el("div", "dsec"), pb = el("div");
    ps.appendChild(el("div", "eyebrow", "problems"));
    ps.appendChild(pb);
    fillProblems(pb, arr(comp.problems), true);
    add(ps);
    add(requestsEl());
  }
  function verdictEl() {
    var v;
    if (comp.route === "experiment") {
      v = el("div", "verdict ok");
      v.appendChild(el("b", null, "Experiment route: ready, " + plural(comp.requests.length, "request")));
      v.appendChild(el("span", "small", "Each request is one GPU job that trains and evaluates; the owner's word and job count decide whether it runs."));
    } else {
      v = el("div", "verdict plan");
      v.appendChild(el("b", null, "Plan only:"));
      arr(comp.why).forEach(function (w) { v.appendChild(el("span", "small", str(w.text))); });
    }
    return v;
  }
  function tilesEl() {
    var tiles = el("div", "tiles"), g = isObj(comp.jobs) && isObj(comp.jobs.gpu) ? comp.jobs.gpu : {}, cpu = isObj(comp.jobs) && isObj(comp.jobs.cpu) ? comp.jobs.cpu : {};
    [[g.submissions || 0, "GPU submissions"], [g.tasks || 0, "GPU tasks"], [num(g.hours || 0), "GPU-hours"],
      [cpu.submissions || 0, "CPU submissions"], [nodeIndex.size, "nodes"]].forEach(function (x) {
      var tile = el("div", "tile");
      tile.appendChild(el("b", null, String(x[0])));
      tile.appendChild(document.createTextNode(x[1]));
      tiles.appendChild(tile);
    });
    return tiles;
  }
  function planEl() {
    var s = el("div", "dsec");
    s.appendChild(el("div", "eyebrow", "the job plan"));
    if (!arr(comp.plan).length) {
      s.appendChild(el("div", "small", "No block here runs a grid job of its own."));
      return s;
    }
    var wrap = el("div", "plan-wrap"), table = el("table", "plan"), thead = el("thead"), hr = el("tr"), tb = el("tbody");
    ["node", "block", "class", "subs x tasks", "hours", "today"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
    thead.appendChild(hr);
    table.appendChild(thead);
    comp.plan.forEach(function (r) {
      var tr = el("tr"), m = BLOCKS.get(r.block), td = el("td");
      td.appendChild(button("linkbtn nid", r.node, function () { select(r.node, true); }));
      tr.appendChild(td);
      tr.appendChild(el("td", null, m ? m.title : r.block));
      tr.appendChild(el("td", null, r["class"] + (r.rides_with ? ", in " + r.rides_with : "")));
      tr.appendChild(el("td", "num", r.submissions + " x " + r.tasks));
      tr.appendChild(el("td", "num", hoursText(r.hours)));
      tr.appendChild(el("td", null, todayShort(m, r.today)));
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    wrap.appendChild(table);
    s.appendChild(wrap);
    if (comp.route === "experiment") {
      s.appendChild(el("div", "small", "The rows count jobs as the pipeline route would, a rider's hours added to its host's; on the " +
        "experiment route each request is one GPU job of the hours it names, so the tiles count requests."));
    }
    return s;
  }

  // ---------------------------------------------------------------------------------------------
  // Requests: links to prefilled issues, never a job. When the page is framed, a click is also
  // posted to the page that embeds it (schwingnet.open), and a change of the first experiment
  // request is posted in the shape tools/experiments_panel.py posts (schwingnet.experiment).

  var reqCache = {version: -1, info: null}, lastPosted = null, firstDraw = true;

  function importedOnBoard() {
    var found = false;
    nodeIndex.forEach(function (n) { if (IMPORTED_IDS.has(n.block)) found = true; });
    return found;
  }
  function pipelineLink() {
    var issue = isObj(comp.pipeline_issue) ? comp.pipeline_issue : {title: "Pipeline", body: ""};
    var url = NEW_ISSUE + "?" + new URLSearchParams({title: str(issue.title), body: str(issue.body)}).toString();
    if (url.length <= LINK_MOST) return {url: url, cut: false, title: str(issue.title)};
    var body = str(issue.body).split("\n").slice(0, 3).join("\n") + "\nThe spec is too long for a link; paste it from the page's Copy spec.\n";
    return {url: NEW_ISSUE + "?" + new URLSearchParams({title: str(issue.title), body: body}).toString(), cut: true, title: str(issue.title)};
  }
  function requestInfo() {
    if (reqCache.version === version && reqCache.info) return reqCache.info;
    var info;
    if (comp.route === "experiment" && arr(comp.requests).length) {
      info = {kind: "experiment", held: importedOnBoard(), requests: comp.requests};
    } else {
      info = {kind: "pipeline", errors: arr(comp.problems).some(function (q) { return q.level === "error"; }), link: pipelineLink()};
    }
    reqCache = {version: version, info: info};
    return info;
  }
  function requestsEl() {
    var s = el("div", "dsec"), info = requestInfo();
    s.id = "sb-requests-sec";
    s.appendChild(el("div", "eyebrow", "requests"));
    if (info.kind === "experiment") {
      s.appendChild(el("p", info.held ? "note warn" : "note", info.held ? HELD_TEXT : ASK_TEXT));
      var list = el("div", "reqs");
      info.requests.forEach(function (r, i) {
        var box = el("div", "req" + (info.held ? " off" : ""));
        if (info.held) {
          box.appendChild(el("span", null, r.title));
        } else {
          var a = el("a", null, r.title);
          a.href = r.url;
          a.target = "_blank";
          a.rel = "noopener";
          a.setAttribute("data-req", String(i));
          box.appendChild(a);
        }
        box.appendChild(el("div", "lines", arr(r.lines).join("  ")));
        list.appendChild(box);
      });
      s.appendChild(list);
    } else {
      var row = el("div", "row");
      if (info.errors) {
        var off = el("span", "tb primary", "Request this pipeline");
        off.setAttribute("aria-disabled", "true");
        row.appendChild(off);
        s.appendChild(row);
        s.appendChild(el("p", "note warn", "Fix the errors first: a pipeline with an error is not recorded as a request."));
      } else {
        var link = el("a", "tb primary", "Request this pipeline");
        link.href = info.link.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.setAttribute("data-req", "pipeline");
        row.appendChild(link);
        if (info.link.cut) row.appendChild(button("tb", "Copy spec", copySpec));
        s.appendChild(row);
        if (info.link.cut) s.appendChild(el("p", "small", "The spec is too long for a link: the issue opens with its first lines, and Copy spec gives the whole spec to paste."));
      }
      s.appendChild(el("p", "small", "Nothing answers this issue yet; the pipeline route waits on the owner's word."));
    }
    if (dispatchNote) s.appendChild(el("p", "note", dispatchNote));
    return s;
  }
  function experimentPayload(r, held) {
    var hours = typeof r.hours_word === "string" ? r.hours_word : String(r.hours);
    return {
      type: "schwingnet.experiment", command: r.command, recipe: r.recipe, blocks: clone(r.blocks), named: clone(r.named),
      epochs: r.epochs, seed: r.seed, hours: r.hours, issueUrl: r.url, title: r.title, body: r.body,
      ok: !held, problems: held ? [HELD_SHORT] : [], repo: REPO, workflow: "experiment.yml", ref: "main",
      inputs: {recipe: String(r.recipe), epochs: String(r.epochs), seed: String(r.seed), hours: hours, blocks: arr(r.named).join(" ")},
      label: r.title, fallbackUrl: r.url
    };
  }
  // Posted on a change of the first request, never on the first draw, so a host offers nothing
  // until the viewer changes something.
  function maybePost() {
    var info = requestInfo(), r = info.kind === "experiment" ? info.requests[0] : null;
    var key = r ? r.url + (info.held ? " held" : "") : "";
    if (key === lastPosted) return;
    lastPosted = key;
    if (firstDraw || !framed || !r) return;
    post(experimentPayload(r, info.held));
  }
  function postOpen(href, label) {
    if (framed && /^https:\/\//.test(href)) post({type: "schwingnet.open", href: href, label: label});
  }
  function onMessage(e) {
    var d = e.data;
    if (!framed || e.source !== window.parent || !isObj(d) || d.type !== "schwingnet.dispatch.result") return;
    var why = typeof d.error === "string" && d.error ? d.error.slice(0, 300) : "no reason given";
    dispatchNote = d.ok ? "Dispatched as you: the workflow opens the issue, checks the lines and answers with the gate word." :
      "Not dispatched (" + why + "); the request links still work.";
    note(dispatchNote);
    if (!selected) renderPanel(false);
  }

  // ---------------------------------------------------------------------------------------------
  // The toolbar and the status line.

  var reqLink = $("sb-request"), reqMany = $("sb-requests"), undoBtn = $("sb-undo"), redoBtn = $("sb-redo");

  function renderToolbar() {
    var info = requestInfo(), label, href = null, title;
    reqMany.hidden = true;
    reqLink.hidden = false;
    if (info.kind === "experiment") {
      var n = info.requests.length;
      label = n > 1 ? "Request these " + n + " runs" : "Request this run";
      if (info.held) {
        title = HELD_SHORT;
      } else if (n > 1) {
        reqLink.hidden = true;
        reqMany.hidden = false;
        if (reqMany.textContent !== label) reqMany.textContent = label;
      } else {
        href = info.requests[0].url;
        title = info.requests[0].title;
      }
    } else {
      label = "Request this pipeline";
      if (info.errors) title = "Fix the errors first";
      else {
        href = info.link.url;
        title = info.link.title;
      }
    }
    if (!reqLink.hidden) {
      if (reqLink.textContent !== label) reqLink.textContent = label;
      if (href) {
        if (reqLink.getAttribute("href") !== href) reqLink.setAttribute("href", href);
        reqLink.setAttribute("aria-disabled", "false");
      } else {
        reqLink.removeAttribute("href");
        reqLink.setAttribute("aria-disabled", "true");
      }
      reqLink.title = title || "";
    }
    undoBtn.disabled = !undoStack.length;
    redoBtn.disabled = !redoStack.length;
  }
  function renderStatus() {
    var keep = statusMsg.textContent;
    clear(statusEl);
    function item(text, cls) { statusEl.appendChild(el("span", cls, text)); }
    var errors = arr(comp.problems).filter(function (q) { return q.level === "error"; }).length;
    var g = isObj(comp.jobs) && isObj(comp.jobs.gpu) ? comp.jobs.gpu : {}, cpu = isObj(comp.jobs) && isObj(comp.jobs.cpu) ? comp.jobs.cpu : {};
    item(plural(nodeIndex.size, "node") + ", " + plural(spec.edges.length, "edge"));
    item(comp.route === "experiment" ? "experiment route, " + plural(comp.requests.length, "request") : "pipeline route: a plan", comp.route === "experiment" ? "ok" : null);
    item(errors ? plural(errors, "error") : "no errors", errors ? "warn" : "ok");
    item("GPU " + plural(g.submissions || 0, "submission") + ", " + num(g.hours || 0) + " h; CPU " + plural(cpu.submissions || 0, "submission"));
    item("digest " + (comp.digest ? comp.digest.slice(0, 12) : "none"));
    statusEl.appendChild(button("linkbtn", "the pipeline", function () { select(null, true); }));
    statusMsg.textContent = keep;
    statusEl.appendChild(statusMsg);
  }
  function note(text) { statusMsg.textContent = text; }

  // ---------------------------------------------------------------------------------------------
  // Copying: the clipboard inside the click, or the text selected in the panel when it refuses.

  function copyText(text, done) {
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
        return;
      }
    } catch (e) { /* fall through to the text box */ }
    done(false);
  }
  function showCopyBox(text, what) {
    var box = el("div", "dsec"), ta = el("textarea", "copybox");
    box.appendChild(el("div", "eyebrow", what + ": select it and copy"));
    ta.readOnly = true;
    ta.value = text;
    box.appendChild(ta);
    box.appendChild(button("linkbtn", "Hide", function () { box.remove(); }));
    detail.insertBefore(box, detail.children[1] || null);
    sheetOpen = true;
    detail.classList.add("open");
    document.body.classList.add("sheet-open");
    ta.focus();
    ta.select();
  }
  function canonicalSpec() {
    return safe(function () { return SB.canonical(SB.specOf(spec, DATA)); }, null);
  }
  function copySpec() {
    var text = canonicalSpec();
    if (text === null) {
      note("The spec holds a character canonical JSON cannot write; the problems name it.");
      return;
    }
    copyText(text, function (ok) {
      if (ok) note("Copied the canonical spec (" + text.length + " characters).");
      else showCopyBox(text, "The canonical spec");
    });
  }

  // ---------------------------------------------------------------------------------------------
  // The palette: one tab per stage, the blocks as chips; a search looks through every block. A
  // click adds the block to the right of the selected node, piped from it when it takes that
  // node's first output, else at the first free spot; a chip can be dragged onto the board too.

  var tabsEl = $("sb-tabs"), chipsEl = $("sb-chips"), searchEl = $("sb-search");
  var currentTab = STAGES.length ? STAGES[0].id : "source";
  var chipDrag = null, chipDragEnd = 0;

  function renderTabs() {
    clear(tabsEl);
    STAGES.forEach(function (s) {
      var b = button("seg", stageTitle(s.id), function () {
        currentTab = s.id;
        searchEl.value = "";
        renderTabs();
        renderChips();
      }, str(s.what));
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", s.id === currentTab && !searchEl.value.trim() ? "true" : "false");
      tabsEl.appendChild(b);
    });
  }
  function chipTag(m) {
    if (IMPORTED_IDS.has(m.id)) {
      var t = el("span", "ctag imported", "imported");
      t.title = "imported, not in the repository";
      return t;
    }
    var today = isObj(m.today) ? m.today : {};
    if (today.status === "planned") return el("span", "ctag", "planned");
    if (today.status === "pending") {
      var pr = /#[0-9]+/.exec(str(today.note));
      return el("span", "ctag", "pending" + (pr ? " " + pr[0] : ""));
    }
    return null;
  }
  function renderChips() {
    clear(chipsEl);
    var q = searchEl.value.trim().toLowerCase();
    var list = DATA.blocks.filter(function (m) {
      if (q) return (str(m.title) + " " + m.id + " " + str(m.summary)).toLowerCase().indexOf(q) >= 0;
      return m.stage === currentTab;
    });
    if (!list.length) chipsEl.appendChild(el("div", "nochips", q ? "No block matches." : "No block in this stage yet."));
    list.forEach(function (m) {
      var b = button("bchip", null, null, str(m.summary));
      b.setAttribute("data-block", m.id);
      b.appendChild(glyphEl(m.glyph));
      b.appendChild(el("span", "ctitle", m.title));
      var tag = chipTag(m);
      if (tag) b.appendChild(tag);
      chipsEl.appendChild(b);
    });
    geo.dirty = true;
  }
  function addBlock(blockId) {
    var m = BLOCKS.get(blockId);
    if (!m) return;
    var anchor = selected && rectById.has(selected) ? selected : null;
    var link = anchor ? linkTo(anchor, m, false) : null;
    var spot = link ? placeRightOf(rectById.get(anchor)) : firstFreeSpot();
    var id = addNode(m, spot.x, spot.y, link);
    if (id) {
      scrollIntoView(id);
      note("Added " + m.title + " (" + id + ")" + (link ? ", piped from " + anchor : "") + ".");
    }
  }
  function dropBlock(blockId, p) {
    var m = BLOCKS.get(blockId);
    if (!m) return;
    var anchor = zoneAnchor(p.x, p.y), link = anchor ? linkTo(anchor, m, false) : null;
    var id = addNode(m, Math.max(0, snap(p.x - W / 2)), Math.max(0, snap(p.y - H / 2)), link);
    if (id) note("Added " + m.title + " (" + id + ")" + (link ? ", piped from " + anchor : "") + ".");
  }
  function onChipClick(e) {
    var chip = e.target.closest ? e.target.closest(".bchip") : null;
    if (!chip || now() - chipDragEnd < 300) return;
    addBlock(chip.getAttribute("data-block"));
  }
  function onChipDown(e) {
    var chip = e.target.closest ? e.target.closest(".bchip") : null;
    if (!chip || e.pointerType === "touch" || e.button !== 0) return;
    chipDrag = {id: e.pointerId, block: chip.getAttribute("data-block"), cx: e.clientX, cy: e.clientY, chip: chip, ghost: null};
    window.addEventListener("pointermove", onChipMove);
    window.addEventListener("pointerup", onChipUp);
    window.addEventListener("pointercancel", onChipUp);
  }
  function onChipMove(e) {
    if (!chipDrag || e.pointerId !== chipDrag.id) return;
    if (!chipDrag.ghost) {
      if (Math.abs(e.clientX - chipDrag.cx) + Math.abs(e.clientY - chipDrag.cy) < 8) return;
      hov.anchor = null;
      clearDwell();
      hideGhost();
      chipDrag.ghost = chipDrag.chip.cloneNode(true);
      chipDrag.ghost.classList.add("dragchip");
      chipDrag.ghost.removeAttribute("data-block");
      document.body.appendChild(chipDrag.ghost);
    }
    chipDrag.ghost.style.transform = "translate(" + (e.clientX + 10) + "px," + (e.clientY + 10) + "px)";
  }
  function onChipUp(e) {
    if (!chipDrag || e.pointerId !== chipDrag.id) return;
    var d = chipDrag;
    chipDrag = null;
    window.removeEventListener("pointermove", onChipMove);
    window.removeEventListener("pointerup", onChipUp);
    window.removeEventListener("pointercancel", onChipUp);
    if (!d.ghost) return;
    d.ghost.remove();
    chipDragEnd = now();
    if (e.type !== "pointerup") return;
    var br = board.getBoundingClientRect();
    if (e.clientX < br.left || e.clientX > br.right || e.clientY < br.top || e.clientY > br.bottom) return;
    refreshGeo();
    dropBlock(d.block, toStage(e.clientX, e.clientY));
  }

  // ---------------------------------------------------------------------------------------------
  // Import a block: the viewer's own block.json, checked here by the engine against R1-R13, kept
  // in this browser only and marked imported until its pull request merges.

  var imp = {
    dlg: $("sb-import-dlg"), text: $("sb-import-text"), file: $("sb-import-file"), check: $("sb-import-check"),
    add: $("sb-import-add"), result: $("sb-import-result"), how: $("sb-import-how"), copyHow: $("sb-import-copyhow"),
    copied: $("sb-import-copied"), mine: $("sb-import-mine"), reqs: $("sb-import-reqs"), close: $("sb-import-close")
  };
  var pendingBlock = null;

  function importOpen() { return !imp.dlg.hidden; }
  function howText(id) {
    var b = id || "<id>";
    return "Put block.json as tools/sandbox/blocks/" + b + ".json, its code as tools/sandbox/blocks/" + b +
      ".py (a module docstring and def run(inputs, params, context)), its test as tests/test_sandbox_block_" + b +
      ".py, then run python3 tools/pipeline_sandbox.py check-block tools/sandbox/blocks/" + b +
      ".json and open a pull request; a pipeline that uses it runs only after that pull request merges.";
  }
  function openImport() {
    hideGhost();
    imp.dlg.hidden = false;
    geo.dirty = true;
    renderImported();
    imp.how.textContent = howText(pendingBlock ? pendingBlock.id : null);
    imp.text.focus();
  }
  function closeImport() {
    imp.dlg.hidden = true;
    geo.dirty = true;
    $("sb-import").focus();
  }
  function problemItem(code, text) {
    var li = el("li", "prob");
    li.appendChild(el("span", "code", code));
    li.appendChild(document.createTextNode(text));
    return li;
  }
  function checkImport() {
    pendingBlock = null;
    imp.add.disabled = true;
    clear(imp.result);
    var m;
    try {
      m = JSON.parse(imp.text.value);
    } catch (e) {
      imp.result.appendChild(el("p", "note warn", "This is not JSON: " + String(e && e.message ? e.message : e)));
      return;
    }
    var problems = safe(function () { return arr(SB.checkManifest(m, CONTRACT)); },
      [{code: "field", field: null, text: "the check could not read this manifest"}]);
    var refusals = [];
    if (isObj(m) && typeof m.id === "string" && BUILTIN_IDS.has(m.id)) {
      refusals.push("the repository already has a block " + m.id + "; give yours another id");
    }
    var id = isObj(m) && typeof m.id === "string" && BLOCK_RE.test(m.id) ? m.id : null;
    imp.how.textContent = howText(id);
    if (!problems.length && !refusals.length) {
      pendingBlock = m;
      imp.add.disabled = false;
      imp.result.appendChild(el("p", "note", "No problem: " + m.id + " meets every requirement." +
        (IMPORTED_IDS.has(m.id) ? " Adding it replaces your imported " + m.id + "." : "")));
      return;
    }
    var ul = el("ul", "probs");
    refusals.forEach(function (t) { ul.appendChild(problemItem("id", t)); });
    problems.forEach(function (q) { ul.appendChild(problemItem(str(q.code) + (q.field ? " " + q.field : ""), str(q.text))); });
    imp.result.appendChild(el("p", "small", plural(problems.length + refusals.length, "problem") + " to fix:"));
    imp.result.appendChild(ul);
  }
  function addImport() {
    if (!pendingBlock) return;
    var m = clone(pendingBlock);
    imported = imported.filter(function (x) { return x.id !== m.id; }).concat([m]);
    importRev += 1;
    pendingBlock = null;
    imp.add.disabled = true;
    rebuildData();
    currentTab = m.stage;
    searchEl.value = "";
    renderTabs();
    renderChips();
    recompute();
    renderImported();
    clear(imp.result);
    imp.result.appendChild(el("p", "note", "Added " + m.id + " to the palette, under " + stageTitle(m.stage) + "."));
    saveNow();
  }
  function removeImport(id) {
    imported = imported.filter(function (x) { return x.id !== id; });
    importRev += 1;
    rebuildData();
    renderChips();
    recompute();
    renderImported();
    saveNow();
  }
  function renderImported() {
    clear(imp.mine);
    imp.mine.appendChild(el("div", "eyebrow", "your imported blocks"));
    if (!imported.length) {
      imp.mine.appendChild(el("div", "small", "none yet"));
      return;
    }
    var list = el("div", "imported-list");
    imported.forEach(function (m) {
      var row = el("div", "row");
      row.appendChild(el("span", null, m.title + " (" + m.id + ")"));
      row.appendChild(el("span", "ctag imported", "imported, not in the repository"));
      row.appendChild(button("linkbtn", "Remove", function () { removeImport(m.id); }));
      list.appendChild(row);
    });
    imp.mine.appendChild(list);
  }
  function renderRequirements() {
    clear(imp.reqs);
    arr(CONTRACT.requirements).forEach(function (r) {
      if (!isObj(r)) return;
      var li = el("li");
      li.appendChild(el("b", null, str(r.id)));
      li.appendChild(document.createTextNode(str(r.title) + ": " + str(r.rule)));
      imp.reqs.appendChild(li);
    });
  }
  function readImportFile() {
    var f = imp.file.files && imp.file.files[0];
    if (!f) return;
    var reader = new FileReader();
    reader.onload = function () {
      imp.text.value = String(reader.result || "");
      checkImport();
    };
    reader.onerror = function () {
      clear(imp.result);
      imp.result.appendChild(el("p", "note warn", "The file could not be read."));
    };
    reader.readAsText(f);
  }

  // ---------------------------------------------------------------------------------------------
  // Whole-board actions: New, a template, Auto-layout.

  function loadTemplate(id, keepUndo) {
    var t = templateById(id);
    if (!t) return false;
    if (keepUndo) pushUndo();
    spec = {sandbox: 1, name: str(t.name) || t.id, nodes: clone(arr(t.nodes)), edges: clone(arr(t.edges)), layout: isObj(t.layout) ? clone(t.layout) : {}};
    template = t.id;
    selected = null;
    afterReplace();
    board.scrollLeft = 0;
    board.scrollTop = 0;
    note("Loaded the template " + str(t.name) + ".");
    return true;
  }
  function newBoard() {
    pushUndo();
    spec = {sandbox: 1, name: "new pipeline", nodes: [], edges: [], layout: {}};
    template = null;
    selected = null;
    afterReplace();
    note("An empty board: pick a source from the palette, then hold the pointer to the right of it.");
  }
  // Columns by the longest path from a source, rows in node order, on the 300 x 150 grid.
  function autoLayout() {
    if (!nodeIndex.size) return;
    pushUndo();
    var incoming = new Map(), col = new Map(), rowsUsed = new Map();
    spec.edges.forEach(function (e) {
      if (!isObj(e)) return;
      if (!incoming.has(e.to)) incoming.set(e.to, []);
      incoming.get(e.to).push(e.from);
    });
    arr(prop.order).forEach(function (id) {
      var k = 0;
      (incoming.get(id) || []).forEach(function (f) { if (col.has(f)) k = Math.max(k, col.get(f) + 1); });
      col.set(id, k);
    });
    Array.from(nodeIndex.keys()).sort(function (a, b) { return nodeNumber(a) - nodeNumber(b) || (a < b ? -1 : 1); }).forEach(function (id) {
      var k = col.has(id) ? col.get(id) : 0, r = rowsUsed.get(k) || 0;
      rowsUsed.set(k, r + 1);
      setPos(id, ORIGIN + k * COL, ORIGIN + r * ROW);
    });
    redraw(false);
    note("Laid out by the longest path from a source.");
  }

  // ---------------------------------------------------------------------------------------------
  // Test hooks: the browser test drives the page through these as well as through real pointer
  // events.

  window.sandbox = {
    graph: function () { return clone(spec); },
    load: function (id) { return loadTemplate(id, true); },
    grow: function (anchorId, blockId) {
      var r = rectById.get(anchorId);
      if (!r) return null;
      var block = blockId;
      if (!block) {
        var preds = predictionsFor(anchorId);
        if (!preds.length) return null;
        block = preds[0].block;
      }
      var spot = placeRightOf(r);
      return growAt(anchorId, block, spot.x, spot.y);
    },
    suggestions: function (anchorId) { return clone(predictionsFor(anchorId)); },
    compile: function () { return clone(comp); },
    digest: function () { return comp.digest; },
    problems: function () { return clone(arr(comp.problems)); },
    reset: function () {
      try {
        window.localStorage.removeItem(STORE_KEY);
      } catch (e) { /* nothing stored */ }
      imported = [];
      importRev += 1;
      history = {};
      undoStack = [];
      redoStack = [];
      rebuildData();
      renderChips();
      if (!loadTemplate("experiment_v1", false)) {
        spec = {sandbox: 1, name: "new pipeline", nodes: [], edges: [], layout: {}};
        afterReplace();
      }
      undoStack = [];
      renderToolbar();
      return true;
    },
    select: function (id) {
      select(id || null, true);
      return selected;
    },
    timings: function (clear) {
      var out = {move: stats(timing.move), frame: stats(timing.frame), commit: stats(timing.commit), recompute: stats(timing.recompute)};
      if (clear === true) Object.keys(timing).forEach(function (k) { timing[k].length = 0; });
      return out;
    }
  };

  // ---------------------------------------------------------------------------------------------
  // Start: the template the address names, else the saved board, else version 1's template.

  function wire() {
    stage.addEventListener("pointerdown", onPointerDown);
    stage.addEventListener("pointermove", onPointerMove);
    stage.addEventListener("pointerup", onPointerUp);
    stage.addEventListener("pointercancel", onPointerCancel);
    stage.addEventListener("lostpointercapture", function (e) { if (ptr && e.pointerId === ptr.id) onPointerCancel(e); });
    board.addEventListener("wheel", onWheel, {passive: false});
    board.addEventListener("pointerenter", function () { geo.dirty = true; });
    board.addEventListener("pointerleave", function () {
      if (ptr || (ghost && ghost.mode === "key")) return;
      lastMove = null;
      hov.anchor = null;
      hov.blocked = null;
      hov.suppressed = null;
      hov.overStrip = false;
      clearDwell();
      hideGhost();
    });
    board.addEventListener("scroll", function () {
      geo.sl = board.scrollLeft;
      geo.st = board.scrollTop;
      if (lastMove && !ptr && !rafId) rafId = requestAnimationFrame(frame);
    }, {passive: true});
    window.addEventListener("scroll", function () { geo.dirty = true; }, {passive: true});
    window.addEventListener("resize", function () { geo.dirty = true; });
    if (typeof ResizeObserver === "function") new ResizeObserver(function () { geo.dirty = true; }).observe(board);
    stripEl.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest(".sug") : null;
      if (b && ghost) commitGhost(Number(b.getAttribute("data-index")));
    });
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("click", function (e) {
      var a = e.target && e.target.closest ? e.target.closest("a[data-req]") : null;
      if (!a || !a.getAttribute("href")) return;
      var which = a.getAttribute("data-req");
      postOpen(a.href, which === "pipeline" ? "Request this pipeline: " + str(comp.pipeline_issue && comp.pipeline_issue.title) :
        "Request this run: " + a.textContent);
    });
    window.addEventListener("message", onMessage);
    window.addEventListener("pagehide", saveNow);
    window.addEventListener("hashchange", function () {
      var id = location.hash.replace(/^#/, "");
      if (templateById(id)) loadTemplate(id, true);
    });

    $("sb-new").addEventListener("click", newBoard);
    var sel = $("sb-templates");
    TEMPLATES.forEach(function (t) {
      var o = el("option", null, str(t.name) || t.id);
      o.value = t.id;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () {
      var id = sel.value;
      sel.value = "";
      if (id) loadTemplate(id, true);
    });
    $("sb-layout").addEventListener("click", autoLayout);
    undoBtn.addEventListener("click", undo);
    redoBtn.addEventListener("click", redo);
    $("sb-import").addEventListener("click", openImport);
    $("sb-copy").addEventListener("click", copySpec);
    reqLink.addEventListener("click", function () {
      var href = reqLink.getAttribute("href");
      if (href) postOpen(href, (reqLink.textContent || "Request") + ": " + reqLink.title);
    });
    reqMany.addEventListener("click", function () {
      select(null, true);
      var sec = $("sb-requests-sec");
      if (sec) {
        sec.scrollIntoView({block: "nearest"});
        var first = sec.querySelector("a");
        if (first) first.focus();
      }
    });

    tabsEl.setAttribute("aria-label", "Stages");
    chipsEl.addEventListener("click", onChipClick);
    chipsEl.addEventListener("pointerdown", onChipDown);
    searchEl.addEventListener("input", function () {
      renderTabs();
      renderChips();
    });

    imp.close.addEventListener("click", closeImport);
    imp.check.addEventListener("click", checkImport);
    imp.add.addEventListener("click", addImport);
    imp.file.addEventListener("change", readImportFile);
    imp.text.addEventListener("input", function () {
      pendingBlock = null;
      imp.add.disabled = true;
    });
    imp.copyHow.addEventListener("click", function () {
      var text = imp.how.textContent;
      copyText(text, function (ok) {
        imp.copied.textContent = ok ? "copied" : "the clipboard refused: select the text above and copy it";
      });
    });
  }

  function init() {
    var saved = readStore();
    imported = cleanImported(saved && saved.imported);
    history = cleanHistory(saved && saved.history);
    rebuildData();
    ringEl.style.strokeDasharray = RING_C.toFixed(2);
    ringEl.style.strokeDashoffset = RING_C.toFixed(2);
    makeStrip();
    renderTabs();
    renderChips();
    renderRequirements();
    wire();
    var fromHash = templateById(location.hash.replace(/^#/, ""));
    var savedSpec = saved ? cleanSpec(saved.spec) : null;
    if (fromHash) {
      loadTemplate(fromHash.id, false);
    } else if (savedSpec) {
      spec = savedSpec;
      template = saved && typeof saved.template === "string" ? saved.template : null;
      afterReplace();
    } else if (!loadTemplate("experiment_v1", false) && !(TEMPLATES[0] && loadTemplate(TEMPLATES[0].id, false))) {
      afterReplace();
    }
    undoStack = [];
    redoStack = [];
    renderToolbar();
    note("");
    firstDraw = false;
  }

  init();
}());
