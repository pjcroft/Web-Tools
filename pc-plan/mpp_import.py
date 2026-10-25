"""MPXJ bridge. Runs in an isolated process with a project-local Java runtime."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".runtime/python"))


def read_mpp(path):
    import jpype
    import mpxj  # Registers bundled MPXJ jars with JPype.

    if not jpype.isJVMStarted():
        jvm = ROOT / ".runtime/java/lib/server/libjvm.so"
        jpype.startJVM(
            str(jvm) if jvm.exists() else jpype.getDefaultJVMPath(), "-Xmx512m", convertStrings=True
        )
    from org.mpxj.reader import UniversalProjectReader
    from org.mpxj import TimeUnit

    source = UniversalProjectReader().read(str(path))
    source_tasks = [
        t
        for t in source.getTasks()
        if t.getName() and t.getStart() and t.getFinish() and int(t.getID() or 0) > 0
    ]
    warnings = [
        "Imported tasks use fixed dates. Custom calendars, working hours, constraints, and fractional durations are not recalculated. Automatic mode uses Monday–Friday and rounds durations up to whole days.",
        "Blank spacer rows are omitted. Summary spans are calculated from their children. Bar colors use an app palette; Microsoft Project formatting is not imported.",
    ]
    palette = ["#245883", "#7551a2", "#087cbc", "#20a16b", "#be703d", "#be549a"]
    tasks = []
    group = -1
    uids = {int(t.getUniqueID()): int(t.getID()) for t in source_tasks}
    base = min(int(t.getOutlineLevel() or 1) for t in source_tasks)
    for src in source_tasks:
        level = max(0, int(src.getOutlineLevel() or 1) - base)
        if tasks:
            level = min(level, tasks[-1]["level"] + int(tasks[-1]["kind"] == "phase"))
        else:
            level = 0
        if level == 0:
            group += 1
        start = str(src.getStart().toLocalDate())
        finish = str(src.getFinish().toLocalDate())
        kind = "phase" if src.getSummary() else "milestone" if src.getMilestone() else "task"
        dur = src.getDuration()
        duration = (
            float(dur.convertUnits(TimeUnit.DAYS, source.getProjectProperties()).getDuration())
            if dur
            else 1
        )
        if kind == "milestone":
            duration = 0
        else:
            duration = max(0.01, round(duration, 4))
        owners = []
        for assignment in src.getResourceAssignments():
            resource = assignment.getResource()
            if resource and resource.getName() and resource.getName() not in owners:
                owners.append(str(resource.getName()))
        deps = []
        source_links = []
        for rel in src.getPredecessors():
            predecessor = rel.getPredecessorTask()
            uid = int(predecessor.getUniqueID())
            pid = uids.get(uid)
            rtype = str(rel.getType())
            lag = str(rel.getLag())
            source_links.append({"predecessor": pid, "type": rtype, "lag": lag})
            if pid and rtype == "FS" and not predecessor.getSummary() and kind != "phase":
                deps.append(pid)
            elif pid:
                warnings.append(
                    f"Task {int(src.getID())}: {rtype} link from {pid} is recorded as source metadata, but not used by automatic scheduling."
                )
            if rel.getLag() and float(rel.getLag().getDuration()) != 0:
                warnings.append(
                    f"Task {int(src.getID())}: predecessor lag {lag} is recorded but not applied by automatic scheduling."
                )
        tasks.append(
            {
                "id": int(src.getID()),
                "name": str(src.getName()),
                "kind": kind,
                "level": level,
                "start": start,
                "finish": finish,
                "duration": duration,
                "deps": list(dict.fromkeys(deps)),
                "owner": ", ".join(owners),
                "color": palette[group % len(palette)],
                "mode": "manual",
                "source": {
                    "uniqueId": int(src.getUniqueID()),
                    "outline": str(src.getOutlineNumber()),
                    "duration": str(dur),
                    "links": source_links,
                },
            }
        )
    if not tasks:
        raise ValueError("No dated tasks found in this MPP file.")
    name = source.getProjectProperties().getProjectTitle() or Path(path).stem
    p = {
        "format": "linux-desktop-planner",
        "version": 1,
        "name": str(name)[:200],
        "start": min(t["start"] for t in tasks),
        "tasks": tasks,
        "import": {"source": Path(path).name, "warnings": warnings, "reader": "MPXJ 16.9.0"},
    }
    return {"project": p, "warnings": warnings}


if __name__ == "__main__":
    try:
        print(json.dumps(read_mpp(sys.argv[1]), ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
