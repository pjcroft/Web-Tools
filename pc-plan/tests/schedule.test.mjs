import test from "node:test";
import assert from "node:assert/strict";
import {
  blank,
  demo,
  schedule,
  shift,
  durationBetween,
  visible,
  date,
} from "../app/schedule.mjs";
const task = (id, props = {}) => ({
  id,
  name: "Task " + id,
  kind: "task",
  level: 0,
  start: "2026-10-02",
  duration: 1,
  deps: [],
  owner: "",
  color: "#387f78",
  ...props,
});
const plan = (...tasks) => ({ ...blank("Test", "2026-10-01"), tasks });
test("Friday finish-to-start rolls into Monday, propagates through chains", () => {
  const rows = schedule(
    plan(
      task(1),
      task(2, { deps: [1], duration: 3 }),
      task(3, { deps: [2], kind: "milestone", duration: 0 }),
    ),
  );
  assert.equal(rows[1].start, "2026-10-05");
  assert.equal(rows[1].finish, "2026-10-07");
  assert.equal(rows[2].start, "2026-10-08");
});
test("calendar arithmetic crosses DST and year boundaries", () => {
  assert.equal(shift("2026-10-30", 1), "2026-11-02");
  assert.equal(shift("2026-12-31", 2), "2027-01-04");
  assert.equal(durationBetween("2026-10-02", "2026-10-05"), 2);
});
test("nested summaries derive their bounds from children", () => {
  const rows = schedule(
    plan(
      task(1, { kind: "phase" }),
      task(2, { kind: "phase", level: 1 }),
      task(3, { level: 2, duration: 5 }),
      task(4, { level: 1, start: "2026-10-20" }),
    ),
  );
  assert.equal(rows[0].finish, "2026-10-20");
  assert.equal(rows[1].finish, "2026-10-08");
  assert.equal(visible(rows, new Set([2])).length, 3);
  assert.equal(visible(rows, new Set([1])).length, 1);
});
test("cycles, missing predecessors, and ambiguous summary predecessors rejected", () => {
  assert.throws(
    () => schedule(plan(task(1, { deps: [2] }), task(2, { deps: [1] }))),
    /cycle/,
  );
  assert.throws(() => schedule(plan(task(1, { deps: [99] }))), /exist/);
  assert.throws(
    () => schedule(plan(task(1, { kind: "phase" }), task(2, { deps: [1] }))),
    /phase/,
  );
});
test("fixed dates preserve weekend finish and fractional duration", () => {
  const rows = schedule(
    plan(
      task(1, { mode: "manual", finish: "2026-10-03", duration: 1.4 }),
      task(2, { deps: [1] }),
    ),
  );
  assert.equal(rows[0].finish, "2026-10-03");
  assert.equal(rows[0].duration, 1.4);
  assert.equal(rows[1].start, "2026-10-05");
});
test("invalid dates and outlines rejected", () => {
  assert.throws(() => date("2026-02-30"));
  assert.throws(() => schedule(plan(task(1, { level: 1 }))), /outline/);
  assert.throws(() => schedule(plan(task(1), task(2, { level: 1 }))), /phases/);
});
test("scheduler does not mutate source project", () => {
  const p = demo(),
    copy = structuredClone(p);
  schedule(p);
  assert.deepEqual(p, copy);
});
