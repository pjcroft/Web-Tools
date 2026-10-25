// Calendar arithmetic is UTC-only: daylight-saving changes never shift task dates.
export const DAY = 86400000;
export function date(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw Error("Use a valid date.");
  const d = new Date(s + "T00:00:00Z");
  if (!Number.isFinite(+d) || iso(d) !== s) throw Error("Use a valid date.");
  return d;
}
export const iso = (d) => d.toISOString().slice(0, 10);
export function plus(s, n) {
  return iso(new Date(+date(s) + n * DAY));
}
export const weekday = (s) => ![0, 6].includes(date(s).getUTCDay());
export function workday(s) {
  while (!weekday(s)) s = plus(s, 1);
  return s;
}
export function shift(s, n) {
  s = workday(s);
  while (n !== 0) {
    s = plus(s, Math.sign(n));
    if (weekday(s)) n -= Math.sign(n);
  }
  return s;
}
export function durationBetween(a, b) {
  if (b < a) throw Error("Finish must be on or after start.");
  let n = 0;
  for (let s = a; s <= b; s = plus(s, 1)) if (weekday(s)) n++;
  return Math.max(1, n);
}
export function validate(p) {
  if (
    !p ||
    p.format !== "linux-desktop-planner" ||
    p.version !== 1 ||
    typeof p.name !== "string" ||
    !p.name.trim() ||
    p.name.length > 200 ||
    !Array.isArray(p.tasks) ||
    p.tasks.length > 1000
  )
    throw Error("This is not a supported planner project (version 1).");
  date(p.start);
  const seen = new Set();
  let previous = -1;
  for (const t of p.tasks) {
    if (!Number.isInteger(t.id) || t.id < 1 || seen.has(t.id))
      throw Error("Task IDs must be unique positive numbers.");
    seen.add(t.id);
    if (
      !Number.isInteger(t.level) ||
      t.level < 0 ||
      t.level > 12 ||
      t.level > previous + 1
    )
      throw Error("Invalid task outline.");
    previous = t.level;
    if (
      !["task", "phase", "milestone"].includes(t.kind) ||
      typeof t.name !== "string" ||
      t.name.length > 300 ||
      typeof t.owner !== "string" ||
      t.owner.length > 150 ||
      !/^#[0-9a-f]{6}$/i.test(t.color)
    )
      throw Error("Invalid task details.");
    if (t.mode !== undefined && !["auto", "manual"].includes(t.mode))
      throw Error("Invalid scheduling mode.");
    date(t.start);
    if (
      !Number.isFinite(t.duration) ||
      t.duration < 0 ||
      t.duration > 10000 ||
      (t.kind === "task" && t.duration <= 0)
    )
      throw Error(
        "Duration must be greater than 0 and at most 10,000 working days (0 for milestones).",
      );
    if (t.mode === "manual") {
      date(t.finish);
      if (t.finish < t.start) throw Error("Finish must be on or after start.");
    }
    if (
      !Array.isArray(t.deps) ||
      t.deps.some((x) => !Number.isInteger(x)) ||
      new Set(t.deps).size !== t.deps.length
    )
      throw Error("Predecessors must be distinct task IDs.");
  }
  for (let i = 0; i < p.tasks.length; i++)
    if (
      i + 1 < p.tasks.length &&
      p.tasks[i + 1].level > p.tasks[i].level &&
      p.tasks[i].kind !== "phase"
    )
      throw Error("Only phases can contain tasks.");
  return p;
}
export function schedule(project) {
  validate(project);
  const tasks = structuredClone(project.tasks),
    byId = new Map(tasks.map((t) => [t.id, t]));
  const state = new Map();
  const children = new Map(tasks.map((t) => [t.id, []]));
  const stack = [];
  for (const t of tasks) {
    while (stack.length && stack.at(-1).level >= t.level) stack.pop();
    if (stack.length) children.get(stack.at(-1).id).push(t);
    stack.push(t);
  }
  function calc(t) {
    if (state.get(t.id) === 1)
      throw Error("These dependencies create a cycle.");
    if (state.get(t.id) === 2) return;
    state.set(t.id, 1);
    const kids = children.get(t.id);
    if (t.kind === "phase" && t.deps.length)
      throw Error("Put predecessors on individual tasks, not phases.");
    if (kids.length) {
      kids.forEach(calc);
      t.start = kids.reduce(
        (a, k) => (a < k.start ? a : k.start),
        kids[0].start,
      );
      t.finish = kids.reduce(
        (a, k) => (a > k.finish ? a : k.finish),
        kids[0].finish,
      );
      t.duration = durationBetween(t.start, t.finish);
    } else if (t.mode === "manual") {
      for (const id of t.deps) {
        const pred = byId.get(id);
        if (!pred) throw Error(`Predecessor ${id} does not exist.`);
        if (pred.kind === "phase")
          throw Error("Use a task or milestone as predecessor, not a phase.");
        calc(pred);
      }
      if (t.kind === "milestone") {
        t.duration = 0;
        t.finish = t.start;
      }
    } else {
      t.start = workday(t.start);
      for (const id of t.deps) {
        const pred = byId.get(id);
        if (!pred) throw Error(`Predecessor ${id} does not exist.`);
        if (pred.kind === "phase")
          throw Error("Use a task or milestone as predecessor, not a phase.");
        calc(pred);
        const earliest = workday(plus(pred.finish, 1));
        if (earliest > t.start) t.start = earliest;
      }
      t.duration = t.kind === "milestone" ? 0 : t.duration;
      t.finish = shift(t.start, Math.max(0, Math.ceil(t.duration) - 1));
    }
    state.set(t.id, 2);
  }
  tasks.forEach(calc);
  return tasks;
}
export function visible(tasks, collapsed) {
  let hidden = -1;
  return tasks.filter((t) => {
    if (hidden >= 0 && t.level > hidden) return false;
    hidden = -1;
    if (collapsed.has(t.id)) hidden = t.level;
    return true;
  });
}
export function blank(name = "Untitled project", start = iso(new Date())) {
  return {
    format: "linux-desktop-planner",
    version: 1,
    name,
    start: workday(start),
    tasks: [],
  };
}
export function demo() {
  const p = blank("Northstar · Office fit-out", "2026-10-05");
  p.tasks = [
    [1, "Discovery & design", "phase", 0, "2026-10-05", 1, [], ""],
    [2, "Site survey & requirements", "task", 1, "2026-10-05", 3, [], "Alex"],
    [3, "Concept design", "task", 1, "2026-10-05", 5, [2], "Morgan"],
    [4, "Design approved", "milestone", 1, "2026-10-05", 0, [3], "Customer"],
    [5, "Procurement & delivery", "phase", 0, "2026-10-05", 1, [], ""],
    [
      6,
      "Order furniture & equipment",
      "task",
      1,
      "2026-10-05",
      8,
      [4],
      "Jamie",
    ],
    [7, "Prepare the workspace", "task", 1, "2026-10-05", 5, [4], "Alex"],
    [8, "Installation", "task", 1, "2026-10-05", 4, [6, 7], "Team"],
    [9, "Handover", "milestone", 0, "2026-10-05", 0, [8], "Customer"],
  ].map(([id, name, kind, level, start, duration, deps, owner]) => ({
    id,
    name,
    kind,
    level,
    start,
    duration,
    deps,
    owner,
    color: id < 5 ? "#22d3ee" : "#f59e0b",
  }));
  return p;
}
