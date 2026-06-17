// Unit tests for the viewer's pure analytics module (src/.../viewer/logic.js).
// Run with: node --test   (Node >= 18)
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ULLogic = require("../src/user_explorer/viewer/logic.js");

// ── sessDurMin ──────────────────────────────────────────────────────────────
test("sessDurMin: minutes between first and last stamp", () => {
  assert.equal(ULLogic.sessDurMin([["09:00"], ["09:30"]]), 30);
  assert.equal(ULLogic.sessDurMin([["09:00"]]), 0); // single event
  assert.equal(ULLogic.sessDurMin([]), 0);
});

test("sessDurMin: wraps across midnight", () => {
  assert.equal(ULLogic.sessDurMin([["23:50"], ["00:10"]]), 20);
});

// ── cohortIndex ─────────────────────────────────────────────────────────────
test("cohortIndex: equal share is typical (1.0x, centered)", () => {
  const r = ULLogic.cohortIndex(0.25, 25, 100); // cohShare 0.25 -> idx 1.0
  assert.equal(r.cls, "ov-idx-mid");
  assert.equal(r.label, "1.0×");
  assert.equal(r.leftW, 0);
  assert.equal(r.rightW, 0);
});

test("cohortIndex: 2x over-index extends the right bar", () => {
  const r = ULLogic.cohortIndex(0.5, 25, 100); // idx 2.0
  assert.equal(r.cls, "ov-idx-hi");
  assert.equal(r.label, "2.0×");
  assert.equal(r.leftW, 0);
  assert.ok(Math.abs(r.rightW - (1 / 3) * 50) < 1e-9); // (capped-1)/3*50
});

test("cohortIndex: under-index extends the left bar", () => {
  const r = ULLogic.cohortIndex(0.05, 25, 100); // idx 0.2
  assert.equal(r.cls, "ov-idx-lo");
  assert.equal(r.label, "0.2×");
  assert.ok(Math.abs(r.leftW - 0.8 * 50) < 1e-9);
  assert.equal(r.rightW, 0);
});

test("cohortIndex: zero peer count uses the smoothing floor (no divide-by-zero)", () => {
  const r = ULLogic.cohortIndex(0.0025, 0, 100); // cohShare = 0.25/100
  assert.ok(Number.isFinite(r.idx));
  assert.equal(r.cls, "ov-idx-mid");
});

test("cohortIndex: extreme over-index is clamped to a 9.9+ label", () => {
  const r = ULLogic.cohortIndex(0.5, 1, 1000); // idx huge
  assert.equal(r.label, "9.9+×");
  assert.equal(r.rightW, 50); // clamped
});

// ── buildTransitions ────────────────────────────────────────────────────────
test("buildTransitions: counts edges, entries, exits, self-loops", () => {
  const sessions = [
    ["s1", "2024-01-01 09:00", [["09:00", "a"], ["09:01", "b"], ["09:02", "b"], ["09:03", "a"]]],
  ];
  const r = ULLogic.buildTransitions(sessions);
  assert.equal(r.trans.a.b, 1);
  assert.equal(r.trans.b.b, 1);
  assert.equal(r.trans.b.a, 1);
  assert.equal(r.entryCount.a, 1);
  assert.equal(r.exitCount.a, 1);
  assert.equal(r.loopCount.b, 1);
  assert.equal(r.totalSess, 1);
});

test("buildTransitions: empty sessions are skipped", () => {
  const r = ULLogic.buildTransitions([["s1", "2024-01-01 09:00", []]]);
  assert.deepEqual(r.trans, {});
  assert.equal(r.totalSess, 1);
});

// ── pathDiversity ───────────────────────────────────────────────────────────
test("pathDiversity: identical paths score low, distinct score high", () => {
  const path = (names) => ["s", "2024-01-01 09:00", names.map((n) => ["09:00", n])];
  assert.equal(ULLogic.pathDiversity([path(["a", "b"]), path(["a", "b"])]), 50);
  assert.equal(ULLogic.pathDiversity([path(["a", "b"]), path(["b", "a"])]), 100);
  assert.equal(ULLogic.pathDiversity([path(["a"])]), 100); // single session
});

test("pathDiversity: separator avoids name-boundary collisions", () => {
  const path = (names) => ["s", "2024-01-01 09:00", names.map((n) => ["09:00", n])];
  // ['ab','c'] vs ['a','bc'] must be treated as distinct paths -> 100%
  assert.equal(ULLogic.pathDiversity([path(["ab", "c"]), path(["a", "bc"])]), 100);
});

// ── classifyActivity ────────────────────────────────────────────────────────
test("classifyActivity: weekday/weekend split + bands + peak day", () => {
  const sessions = [
    ["s1", "2024-01-01 10:00", []], // Monday, morning
    ["s2", "2024-01-06 20:00", []], // Saturday, evening
  ];
  const r = ULLogic.classifyActivity(sessions);
  assert.equal(r.total, 2);
  assert.equal(r.weekdayN, 1);
  assert.equal(r.weekendN, 1);
  assert.equal(r.bandCount[1], 1); // morning
  assert.equal(r.bandCount[3], 1); // evening
  assert.equal(r.dayCount[0], 1); // Monday (index 0)
  assert.equal(r.dayCount[5], 1); // Saturday (index 5)
  assert.equal(r.peakDay, 0); // tie -> first max (Monday)
});

// ── durationStats ───────────────────────────────────────────────────────────
test("durationStats: buckets and avg/p50/p90", () => {
  const r = ULLogic.durationStats([0, 3, 10, 45, 90]);
  const byLabel = Object.fromEntries(r.buckets.map((b) => [b.lbl, b.n]));
  assert.equal(byLabel["<1m"], 1); // 0
  assert.equal(byLabel["1–5m"], 1); // 3
  assert.equal(byLabel["5–15m"], 1); // 10
  assert.equal(byLabel["15–30m"], 0);
  assert.equal(byLabel["30–60m"], 1); // 45
  assert.equal(byLabel["1h+"], 1); // 90
  assert.equal(r.avg, 30); // 29.6 -> 30
  assert.equal(r.p50, 10);
  assert.equal(r.p90, 90);
});

test("durationStats: empty input is all-zero", () => {
  const r = ULLogic.durationStats([]);
  assert.equal(r.avg, 0);
  assert.equal(r.p50, 0);
  assert.equal(r.p90, 0);
  assert.ok(r.buckets.every((b) => b.n === 0));
});
