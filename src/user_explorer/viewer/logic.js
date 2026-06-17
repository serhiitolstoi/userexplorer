/* User Explorer — pure analytics helpers.
 *
 * DOM-free, dependency-free functions shared by the viewer's render code.
 * Kept in their own module so the analytics that matter most (cohort indexing,
 * flow transitions, activity classification, duration stats) can be unit-tested
 * with `node --test` instead of only being smoke-checked as HTML substrings.
 *
 * At render time this file is inlined into the single-file report (render.py
 * substitutes it for the logic sentinel), so the shipped output stays one file.
 * In Node it is required as a CommonJS module.
 *
 * Session shape (as embedded in DATA): [sid, ts, events]
 *   events: [[hhmm, name, family, k1, v1, ...], ...]
 */
var ULLogic = (function () {
  "use strict";

  // Duration of a session in minutes, from its first/last "HH:MM" stamps.
  function sessDurMin(evs) {
    if (!evs || evs.length < 2) return 0;
    var a = String(evs[0][0]).split(":").map(Number);
    var b = String(evs[evs.length - 1][0]).split(":").map(Number);
    var m = (b[0] * 60 + b[1]) - (a[0] * 60 + a[1]);
    if (m < 0) m += 1440; // crossed midnight
    return m;
  }

  // Share-indexed cohort comparison for one event.
  //   userShare = this user's share of the event among their own events
  //   baseCnt   = peers' count of the event (current user excluded)
  //   baseGrand = peers' total event count (current user excluded)
  // Returns { idx, label, cls, leftW, rightW } for the diverging index bar.
  function cohortIndex(userShare, baseCnt, baseGrand) {
    var cohShare = (baseCnt / baseGrand) || (0.25 / baseGrand);
    var idx = cohShare > 0 ? userShare / cohShare : 0;
    var capped = Math.min(idx, 4);
    var label, cls;
    if (idx >= 1.15) {
      cls = "ov-idx-hi";
      label = (idx >= 9.95 ? "9.9+" : idx.toFixed(1)) + "×";
    } else if (idx <= 0.85) {
      cls = "ov-idx-lo";
      label = idx.toFixed(1) + "×";
    } else {
      cls = "ov-idx-mid";
      label = "1.0×";
    }
    var rightW = idx > 1 ? Math.min((capped - 1) / 3 * 50, 50) : 0;
    var leftW = idx < 1 ? (1 - idx) * 50 : 0;
    return { idx: idx, label: label, cls: cls, leftW: leftW, rightW: rightW };
  }

  // Build the next-event transition map + entry/exit/loop counts from sessions.
  function buildTransitions(sessions) {
    var trans = {}, entryCount = {}, exitCount = {}, loopCount = {};
    sessions.forEach(function (s) {
      var evs = s[2];
      if (!evs || !evs.length) return;
      var entry = evs[0][1], exit = evs[evs.length - 1][1];
      entryCount[entry] = (entryCount[entry] || 0) + 1;
      exitCount[exit] = (exitCount[exit] || 0) + 1;
      for (var i = 0; i < evs.length - 1; i++) {
        var from = evs[i][1], to = evs[i + 1][1];
        if (!trans[from]) trans[from] = {};
        trans[from][to] = (trans[from][to] || 0) + 1;
        if (from === to) loopCount[from] = (loopCount[from] || 0) + 1;
      }
    });
    return {
      trans: trans,
      entryCount: entryCount,
      exitCount: exitCount,
      loopCount: loopCount,
      totalSess: sessions.length,
    };
  }

  // Percentage of sessions whose ordered event-name sequence is unique.
  // 100 = every session is a unique sequence; low = repeated patterns.
  function pathDiversity(sessions) {
    var sigs = new Set();
    sessions.forEach(function (s) {
      var evs = s[2];
      if (evs && evs.length) {
        sigs.add(evs.map(function (e) { return e[1]; }).join(""));
      }
    });
    var n = sessions.length;
    return n > 1 ? Math.round(sigs.size / n * 100) : 100;
  }

  // Classify when a user is active: time-of-day band totals, day-of-week
  // totals, weekday/weekend split, dominant band and peak weekday.
  function classifyActivity(sessions) {
    function bandOf(h) { return h < 6 ? 0 : h < 12 ? 1 : h < 18 ? 2 : 3; }
    var bandCount = [0, 0, 0, 0];
    var dayCount = [0, 0, 0, 0, 0, 0, 0]; // 0 = Monday
    var hourCount = new Array(24).fill(0);
    var weekdayN = 0, weekendN = 0;
    sessions.forEach(function (s) {
      var d = new Date(String(s[1]).replace(" ", "T"));
      if (isNaN(d)) return;
      var dow = (d.getDay() + 6) % 7, hr = d.getHours();
      bandCount[bandOf(hr)]++;
      dayCount[dow]++;
      hourCount[hr]++;
      if (dow < 5) weekdayN++; else weekendN++;
    });
    var total = weekdayN + weekendN;
    return {
      bandCount: bandCount,
      dayCount: dayCount,
      hourCount: hourCount,
      weekdayN: weekdayN,
      weekendN: weekendN,
      total: total,
      topBand: bandCount.indexOf(Math.max.apply(null, bandCount)),
      peakDay: dayCount.indexOf(Math.max.apply(null, dayCount)),
    };
  }

  // Bucket session durations (minutes) and compute avg / p50 / p90.
  function durationStats(durs) {
    var buckets = [
      { lbl: "<1m", lo: 0, hi: 1, n: 0 },
      { lbl: "1–5m", lo: 1, hi: 5, n: 0 },
      { lbl: "5–15m", lo: 5, hi: 15, n: 0 },
      { lbl: "15–30m", lo: 15, hi: 30, n: 0 },
      { lbl: "30–60m", lo: 30, hi: 60, n: 0 },
      { lbl: "1h+", lo: 60, hi: Infinity, n: 0 },
    ];
    durs.forEach(function (m) {
      for (var i = 0; i < buckets.length; i++) {
        if (m >= buckets[i].lo && m < buckets[i].hi) { buckets[i].n++; break; }
      }
    });
    var sorted = durs.slice().sort(function (a, b) { return a - b; });
    var avg = sorted.length
      ? Math.round(sorted.reduce(function (a, b) { return a + b; }, 0) / sorted.length)
      : 0;
    var p50 = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
    var p90 = sorted.length ? sorted[Math.floor(sorted.length * 0.9)] : 0;
    return { buckets: buckets, avg: avg, p50: p50, p90: p90 };
  }

  return {
    sessDurMin: sessDurMin,
    cohortIndex: cohortIndex,
    buildTransitions: buildTransitions,
    pathDiversity: pathDiversity,
    classifyActivity: classifyActivity,
    durationStats: durationStats,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ULLogic;
}
