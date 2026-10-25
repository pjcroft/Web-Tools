from datetime import date
import re

def validate(p, scheduled=False):
    if (
        not isinstance(p, dict)
        or p.get("format") != "linux-desktop-planner"
        or p.get("version") != 1
    ):
        raise ValueError("Unsupported project format.")
    if not isinstance(p.get("name"), str) or not 1 <= len(p["name"].strip()) <= 200:
        raise ValueError("Project name must be 1–200 characters.")
    date.fromisoformat(p["start"])
    tasks = p["tasks"]
    if not isinstance(tasks, list) or len(tasks) > 1000:
        raise ValueError("Maximum 1,000 tasks per project.")
    ids = set()
    previous = -1
    for i, t in enumerate(tasks):
        if type(t.get("id")) != int or t["id"] < 1 or t["id"] in ids:
            raise ValueError("Invalid or duplicate task ID.")
        ids.add(t["id"])
        if type(t.get("level")) != int or not 0 <= t["level"] <= 12 or t["level"] > previous + 1:
            raise ValueError("Invalid outline.")
        if i and t["level"] > previous and tasks[i - 1]["kind"] != "phase":
            raise ValueError("Only phases can contain tasks.")
        previous = t["level"]
        if t.get("kind") not in ("task", "phase", "milestone"):
            raise ValueError("Invalid task kind.")
        for key, limit in [("name", 300), ("owner", 150)]:
            if not isinstance(t.get(key), str) or len(t[key]) > limit:
                raise ValueError("Invalid task text.")
        if not isinstance(t.get("color"), str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", t["color"]):
            raise ValueError("Invalid color.")
        date.fromisoformat(t["start"])
        if scheduled or t.get("mode") == "manual":
            date.fromisoformat(t["finish"])
            if t["finish"] < t["start"]:
                raise ValueError("Finish is before start.")
        if (
            type(t.get("duration")) not in (int, float)
            or not 0 <= t["duration"] <= 10000
            or (t["kind"] == "task" and t["duration"] <= 0)
        ):
            raise ValueError("Invalid duration.")
        if (
            not isinstance(t.get("deps"), list)
            or any(type(d) != int for d in t["deps"])
            or len(set(t["deps"])) != len(t["deps"])
        ):
            raise ValueError("Invalid predecessors.")
    byid = {t["id"]: t for t in tasks}
    states = {}

    def visit(t):
        if states.get(t["id"]) == 1:
            raise ValueError("Dependency cycle.")
        if states.get(t["id"]) == 2:
            return
        states[t["id"]] = 1
        if t["kind"] == "phase" and t["deps"]:
            raise ValueError("Phases cannot have predecessors.")
        for dep in t["deps"]:
            if dep not in ids or byid[dep]["kind"] == "phase":
                raise ValueError("Invalid predecessor.")
            visit(byid[dep])
        states[t["id"]] = 2

    for t in tasks:
        visit(t)
    return p

