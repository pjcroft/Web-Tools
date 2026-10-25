function validateLocalProject(p) {
  if (!p || p.format !== "linux-desktop-planner" || p.version !== 1 || typeof p.name !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(p.start) || !Array.isArray(p.tasks) || p.tasks.length > 1000) throw Error("Unsupported or invalid project file.");
  const ids = new Set(); let previous = -1;
  p.tasks.forEach((t,i) => {
    if (!t || !Number.isInteger(t.id) || t.id < 1 || ids.has(t.id) || !Number.isInteger(t.level) || t.level < 0 || t.level > 12 || t.level > previous+1 || (i && t.level > previous && p.tasks[i-1].kind !== "phase") || !["task","phase","milestone"].includes(t.kind) || typeof t.name !== "string" || typeof t.owner !== "string" || !/^#[a-f0-9]{6}$/i.test(t.color) || !/^\d{4}-\d{2}-\d{2}$/.test(t.start) || !Number.isFinite(t.duration) || t.duration < 0 || t.duration > 10000 || !Array.isArray(t.deps)) throw Error("Invalid task in project file.");
    ids.add(t.id); previous = t.level;
  });
  p.tasks.forEach(t => { if(t.deps.some(id => !ids.has(id) || id === t.id)) throw Error("Invalid dependency."); });
  schedule(p);
}
import {
  DAY,
  date,
  iso,
  plus,
  shift,
  workday,
  durationBetween,
  schedule,
  visible,
  blank,
} from "./schedule.mjs";
const $ = (s) => document.querySelector(s),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    ),
  dayAbbr = (s) =>
    date(s).toLocaleDateString("en", { weekday: "short", timeZone: "UTC" });
let project = blank(),
  filename = null,
  dirty = false,
  selected = null,
  selectedIds = new Set(),
  selectionAnchor = null,
  collapsed = new Set(),
  history = [],
  scale = "fit",
  timelineZoom = 1,
  timelineUnit = 1,
  details = false,
  savedRevision = null,
  nativeProjectPath = null;
const notify = (s) => {
  $("#notice").textContent = s;
  $("#notice").style.display = "block";
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => ($("#notice").style.display = "none"), 6500);
};
async function api(path, data) {
  const r = await fetch(path, {
    method: data ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-PC-Plan": "1" },
    body: data ? JSON.stringify(data) : undefined,
  });
  const j = await r.json();
  if (!r.ok) throw Error(j.error || "Unable to complete request.");
  return j;
}
function mutate(fn) {
  const old = structuredClone(project);
  try {
    fn();
    schedule(project);
    history.push(old);
    if (history.length > 60) history.shift();
    dirty = true;
    render();
  } catch (e) {
    project = old;
    notify(e.message);
    render();
  }
}
function moveDependentTasks(taskId, calendarDays, scheduledTasks) {
  if (!calendarDays) return;
  const scheduled = new Map(scheduledTasks.map((task) => [task.id, task]));
  const moved = new Set([taskId]);
  const moveSuccessors = (predecessorId) => {
    for (const successor of project.tasks.filter((task) =>
      task.deps.includes(predecessorId),
    )) {
      if (moved.has(successor.id)) continue;
      moved.add(successor.id);
      const beforeMove = scheduled.get(successor.id);
      successor.start = plus(beforeMove.start, calendarDays);
      if (successor.mode === "manual")
        successor.finish = plus(beforeMove.finish, calendarDays);
      moveSuccessors(successor.id);
    }
  };
  moveSuccessors(taskId);
}
function modal(html) {
  replaceModal(html);
  $("#dialog").showModal();
  $("#dialog")
    .querySelectorAll("[data-close]")
    .forEach((b) => (b.onclick = () => $("#dialog").close()));
}
function replaceModal(html) {
  $("#dialogContent").innerHTML = html;
  $("#dialog")
    .querySelectorAll("[data-close]")
    .forEach((b) => (b.onclick = () => $("#dialog").close()));
}
const close = () => $("#dialog").close();
async function abandon() {
  if (!dirty) return true;
  return new Promise((resolve) => {
    modal(
      '<h2>Keep your changes?</h2><p>This project has unsaved changes. Save it before switching, or discard those changes.</p><div class="buttons"><button id="keep">Keep editing</button><button id="discard">Discard changes</button><button class="primary" id="saveSwitch">Save & continue</button></div>',
    );
    const dlg = $("#dialog");
    const cancel = (e) => {
      e.preventDefault();
      close();
      resolve(false);
    };
    dlg.addEventListener("cancel", cancel, { once: true });
    const done = (v) => {
      dlg.removeEventListener("cancel", cancel);
      close();
      resolve(v);
    };
    $("#keep").onclick = () => done(false);
    $("#discard").onclick = () => done(true);
    $("#saveSwitch").onclick = async () => {
      if (await save()) done(true);
    };
  });
}
function load(p, file = null, revision = null) {
  schedule(p);
  project = p;
  filename = file;
  nativeProjectPath = null;
  savedRevision = revision;
  selected = null;
  selectedIds.clear();
  selectionAnchor = null;
  history = [];
  collapsed.clear();
  dirty = false;
  render();
}
function selectionText() {
  if (!selected) return "No row selected";
  if (selectedIds.size === 2)
    return `2 tasks selected · right-click to make the second task dependent on the first, or change a colour to colour both`;
  if (selectedIds.size > 1)
    return `${selectedIds.size} tasks selected · change a colour to colour them all`;
  return `Selected task ${selected} · ${project.tasks.find((t) => t.id === selected)?.mode === "manual" ? "Fixed dates" : "Automatic scheduling"}`;
}
function updateBulkColor() {
  const bulk = $("#bulkColor");
  if (!bulk) return;
  bulk.disabled = selectedIds.size < 2;
  if (selectedIds.size >= 2) {
    const first = project.tasks.find((t) => selectedIds.has(t.id));
    if (first) bulk.value = first.color;
  }
}
function refreshSelection() {
  document.querySelectorAll("#schedule tr[data-id]").forEach((row) => {
    row.classList.toggle("selected", selectedIds.has(+row.dataset.id));
  });
  $("#selection").textContent = selectionText();
  updateBulkColor();
  ["delete", "indent", "outdent"].forEach((id) => {
    $("#" + id).disabled = !selected;
  });
}
function selectTask(id, additive = false, range = false) {
  if (range && selectionAnchor !== null && selectionAnchor !== id) {
    const visible = [...document.querySelectorAll("#schedule tr[data-id]")].map(
      (row) => +row.dataset.id,
    );
    const from = visible.indexOf(selectionAnchor);
    const to = visible.indexOf(id);
    if (from >= 0 && to >= 0) {
      selectedIds.clear();
      visible
        .slice(Math.min(from, to), Math.max(from, to) + 1)
        .forEach((taskId) => selectedIds.add(taskId));
      selected = id;
      refreshSelection();
      return;
    }
  }
  if (!additive) selectedIds.clear();
  selectedIds.add(id);
  selected = id;
  selectionAnchor = id;
  refreshSelection();
}
function hideContextMenu() {
  $("#contextMenu").hidden = true;
}
function makeDependent() {
  const [predecessorId, successorId] = [...selectedIds];
  const predecessor = project.tasks.find((task) => task.id === predecessorId);
  const successor = project.tasks.find((task) => task.id === successorId);
  if (!predecessor || !successor || selectedIds.size !== 2)
    return notify("Select two tasks first.");
  if (predecessor.kind === "phase" || successor.kind === "phase")
    return notify("Choose tasks or milestones, not phases, for a dependency.");
  if (successor.deps.includes(predecessorId))
    return notify(`${successor.name} already depends on ${predecessor.name}.`);
  hideContextMenu();
  mutate(() => {
    successor.deps.push(predecessorId);
    if (successor.mode === "manual") {
      const scheduled = new Map(schedule(project).map((task) => [task.id, task]));
      const earliest = successor.deps.reduce((start, dependencyId) => {
        const dependency = scheduled.get(dependencyId);
        const nextStart = workday(plus(dependency.finish, 1));
        return nextStart > start ? nextStart : start;
      }, successor.start);
      if (earliest > successor.start) {
        const calendarDays = Math.round(
          (+date(successor.finish) - +date(successor.start)) / DAY,
        );
        successor.start = earliest;
        successor.finish = plus(earliest, calendarDays);
      }
    }
  });
}
function breakDependency(successorId, predecessorId) {
  const successor = project.tasks.find((task) => task.id === successorId);
  const predecessor = project.tasks.find((task) => task.id === predecessorId);
  if (!successor || !predecessor) return;
  hideContextMenu();
  mutate(() => {
    successor.deps = successor.deps.filter((id) => id !== predecessorId);
  });
  notify(`Removed ${successor.name}'s dependency on ${predecessor.name}.`);
}
function showContextMenu(event, contextTaskId) {
  event.preventDefault();
  const menu = $("#contextMenu");
  const [predecessorId, successorId] = [...selectedIds];
  const predecessor = project.tasks.find((task) => task.id === predecessorId);
  const successor = project.tasks.find((task) => task.id === successorId);
  const ready =
    selectedIds.size === 2 &&
    predecessor?.kind !== "phase" &&
    successor?.kind !== "phase" &&
    !successor?.deps.includes(predecessorId);
  const contextTask = project.tasks.find((task) => task.id === contextTaskId);
  const actions = [];
  if (ready)
    actions.push(
      `<button id="makeDependent" role="menuitem">Make “${esc(successor.name)}” dependent on “${esc(predecessor.name)}”</button>`,
    );
  if (contextTask?.deps.length)
    for (const dependencyId of contextTask.deps) {
      const dependency = project.tasks.find((task) => task.id === dependencyId);
      if (dependency)
        actions.push(
          `<button data-break-dependency="${dependency.id}" role="menuitem">Break dependency on “${esc(dependency.name)}”</button>`,
        );
    }
  menu.innerHTML = actions.length
    ? actions.join("")
    : '<span>Select a task, Ctrl-click its successor, then right-click.</span>';
  menu.style.left = `${Math.min(event.clientX, window.innerWidth - 360)}px`;
  menu.style.top = `${Math.min(event.clientY, window.innerHeight - 72)}px`;
  menu.hidden = false;
  $("#makeDependent")?.addEventListener("click", makeDependent);
  menu.querySelectorAll("[data-break-dependency]").forEach((button) => {
    button.addEventListener("click", () =>
      breakDependency(contextTaskId, +button.dataset.breakDependency),
    );
  });
}
function render() {
  const all = schedule(project),
    rows = visible(all, collapsed);
  $("#projectName").value = project.name;
  $("#projectStart").value = project.start;
  $("#status").textContent = dirty
    ? "Unsaved changes"
    : nativeProjectPath
      ? "Downloaded · " + nativeProjectPath
      : filename
      ? "Local file · " + filename
      : "New project · choose Save project to keep it";
  $("#selection").textContent = selectionText();
  updateBulkColor();
  $("#undo").disabled = !history.length;
  ["delete", "indent", "outdent", "mode"].forEach((id) => {
    if ($("#" + id)) $("#" + id).disabled = !selected;
  });
  const container = $("#schedule"),
    scroll = [container.scrollLeft, container.scrollTop];
  if (!rows.length) {
    container.innerHTML =
      '<div class="empty"><strong>Your next project starts here.</strong>Add a phase, task, or milestone using the toolbar above.</div>';
    $("#zoomOut").disabled = true;
    $("#zoomIn").disabled = true;
    $("#zoomLevel").textContent = "100%";
    return;
  }
  const colWidths = details
    ? [36, 255, 65, 106, 106, 104, 43, 90]
    : [36, 255, 65, 106, 106, 0, 0, 0];
  container.innerHTML = `<div class="schedule-inner"><table class="${details ? "expanded" : "compact"}" style="width:${colWidths.reduce((a, b) => a + b, 0)}px"><colgroup>${colWidths.map((w) => `<col style="width:${w}px">`).join("")}</colgroup><thead><tr>${["ID", "Task name", "Days", "Start", "Finish", "Owner", "Color", "Scheduling"].map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.map((t) => `<tr data-id="${t.id}" class="${t.kind === "phase" ? "phase " : ""}${selectedIds.has(t.id) ? "selected" : ""}"><td>${t.id}</td><td><div class="task-name" style="padding-left:${t.level * 14}px">${t.kind === "phase" ? `<button class="collapse" data-collapse="${t.id}" aria-label="${collapsed.has(t.id) ? "Expand" : "Collapse"} ${esc(t.name)}">${collapsed.has(t.id) ? "▸" : "▾"}</button>` : `<span class="task-icon">${t.kind === "milestone" ? "◆" : "—"}</span>`}<input data-key="name" aria-label="Task ${t.id} name" value="${esc(t.name)}"></div></td><td><input data-key="duration" aria-label="Task ${t.id} duration" type="number" min="0.01" max="10000" step="any" value="${t.duration}" ${t.kind !== "task" ? "disabled" : ""}></td><td><div class="date-cell"><small>${dayAbbr(t.start)}</small><input data-key="start" aria-label="Task ${t.id} start" type="date" value="${t.start}" ${t.kind === "phase" ? "disabled" : ""}></div></td><td><div class="date-cell"><small>${dayAbbr(t.finish)}</small><input data-key="finish" aria-label="Task ${t.id} finish" type="date" value="${t.finish}" ${t.kind !== "task" ? "disabled" : ""}></div></td><td><input data-key="owner" aria-label="Task ${t.id} owner" value="${esc(t.owner)}"></td><td><input data-key="color" aria-label="Task ${t.id} color" type="color" value="${t.color}"></td><td><select data-key="mode" aria-label="Task ${t.id} scheduling" ${t.kind === "phase" ? "disabled" : ""}><option value="auto" ${t.mode !== "manual" ? "selected" : ""}>Auto</option><option value="manual" ${t.mode === "manual" ? "selected" : ""}>Fixed dates</option></select></td></tr>`).join("")}</tbody></table><div class="gantt">${gantt(rows, all)}</div></div>`;
  container.scrollLeft = scroll[0];
  container.scrollTop = scroll[1];
  container.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", (event) => {
      if (event.target.dataset.key === "color") return;
      if (event.shiftKey) selectTask(+tr.dataset.id, false, true);
      else selectTask(+tr.dataset.id, event.ctrlKey || event.metaKey);
    });
    tr.addEventListener("contextmenu", (event) => {
      if (!selectedIds.has(+tr.dataset.id)) selectTask(+tr.dataset.id);
      showContextMenu(event, +tr.dataset.id);
    });
    tr.querySelectorAll("[data-key]").forEach(
      (input) =>
        (input.onchange = () => {
          const k = input.dataset.key,
            v = input.value,
            rowId = +tr.dataset.id,
            bulkColor =
              k === "color" &&
              selectedIds.size > 1 &&
              selectedIds.has(rowId);
          if (!bulkColor) {
            selected = rowId;
            selectedIds.clear();
            selectedIds.add(selected);
          } else {
            selected = rowId;
          }
          mutate(() => {
            if (bulkColor) {
              selectedIds.forEach((taskId) => {
                const task = project.tasks.find((t) => t.id === taskId);
                if (task) task.color = v;
              });
              return;
            }
            const t = project.tasks.find((t) => t.id === selected),
              computed = all.find((t) => t.id === selected);
            if (k === "duration") {
              t.duration = Number(v);
              if (t.mode === "manual")
                t.finish = shift(
                  t.start,
                  Math.max(0, Math.ceil(t.duration) - 1),
                );
            } else if (k === "finish") {
              date(v);
              t.duration = durationBetween(computed.start, v);
              if (t.mode === "manual") t.finish = v;
            } else if (k === "start") {
              date(v);
              const calendarDays = Math.round(
                (+date(v) - +date(computed.start)) / DAY,
              );
              t.start = v;
              if (t.mode === "manual")
                t.finish =
                  t.kind === "milestone"
                    ? v
                    : shift(v, Math.max(0, Math.ceil(t.duration) - 1));
              moveDependentTasks(selected, calendarDays, all);
            } else if (k === "mode") {
              t.mode = v;
              t.start = computed.start;
              t.finish = computed.finish;
            } else t[k] = v;
          });
        }),
    );
  });
  container.querySelectorAll("[data-collapse]").forEach(
    (b) =>
      (b.onclick = (e) => {
        e.stopPropagation();
        const id = +b.dataset.collapse;
        collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id);
        render();
      }),
  );
  container.querySelectorAll("[data-bar]").forEach((el) => {
    el.style.cursor = "ew-resize";
    el.onpointerdown = (e) => {
      if (e.button !== 0) return;
      const id = +el.dataset.bar,
        t = all.find((t) => t.id === id),
        x = e.clientX,
        unit = +el.dataset.unit;
      el.setPointerCapture(e.pointerId);
      el.onpointerup = (up) => {
        const days = Math.round((up.clientX - x) / unit);
        if (days)
          mutate(() => {
            const raw = project.tasks.find((r) => r.id === id);
            raw.start = plus(t.start, days);
            if (raw.mode === "manual") raw.finish = plus(t.finish, days);
            moveDependentTasks(id, days, all);
          });
        el.onpointerup = null;
      };
    };
  });
}
function gantt(rows, all) {
  const earliest = all.reduce(
      (a, t) => (a < t.start ? a : t.start),
      all[0].start,
    ),
    latest = all.reduce((a, t) => (a > t.finish ? a : t.finish), all[0].finish),
    start = plus(earliest, -3),
    end = plus(latest, 14),
    count = Math.round((date(end) - date(start)) / DAY) + 1;
  const available = Math.max(
    440,
    $("#schedule").clientWidth - (details ? 805 : 568),
  );
  const baseUnit = scale === "fit"
    ? (available - 90) / count
    : { day: 32, week: 15, month: 5 }[scale];
  const unit = Math.min(baseUnit * timelineZoom, 16000 / count),
    width = Math.max(available, count * unit + 90),
    height = 58 + rows.length * 42,
    x = (s) => ((date(s) - date(start)) / DAY) * unit;
  timelineUnit = unit;
  $("#zoomLevel").textContent = Math.round(timelineZoom * 100) + "%";
  $("#zoomOut").disabled = timelineZoom <= 0.125;
  $("#zoomIn").disabled = timelineZoom >= 8 || unit >= 16000 / count;
  let grid = "",
    ticks = "",
    months = "";
  let monthStart = 0;
  for (let i = 0; i < count; i++) {
    const s = plus(start, i),
      d = date(s),
      px = i * unit;
    if (d.getUTCDay() === 0 || d.getUTCDay() === 6)
      grid += `<rect x="${px}" y="58" width="${unit}" height="${height - 58}" fill="#f6f8f5"/>`;
    if (
      (scale === "day" && unit >= 20) ||
      (scale === "week" && d.getUTCDay() === 1) ||
      ((scale === "month" || scale === "fit") && d.getUTCDate() === 1)
    ) {
      ticks += `<path d="M${px} 31V${height}" stroke="#e5ebe5"/><text x="${px + 4}" y="48" fill="#849487" font-size="10">${scale === "month" || scale === "fit" ? "Q" + (Math.floor(d.getUTCMonth() / 3) + 1) : d.getUTCDate()}</text>`;
    }
    if (i === 0 || d.getUTCDate() === 1) {
      monthStart = px;
      const nextMonth = new Date(
        Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1),
      );
      if (((nextMonth - d) / DAY) * unit > 58)
        months += `<text x="${monthStart + 7}" y="20" fill="#5e7769" font-size="11" font-weight="600">${d.toLocaleDateString("en", { month: "short", year: "numeric", timeZone: "UTC" })}</text>`;
    }
  }
  let lines = "",
    bars = "",
    arrows = "";
  const pos = new Map(rows.map((t, i) => [t.id, i]));
  rows.forEach((t, i) => {
    const y = 58 + i * 42,
      xx = x(t.start),
      w = Math.max(4, x(t.finish) + unit - xx);
    lines += `<path d="M0 ${y + 42}H${width}" stroke="#edf1ed"/>`;
    if (t.kind === "phase") {
      bars += `<path d="M${xx} ${y + 17}h${w}v8l-4 -4H${xx + 4}l-4 4Z" fill="#f59e0b"/>`;
    } else if (t.kind === "milestone") {
      bars += `<path data-bar="${t.id}" data-unit="${unit}" d="M${xx + unit / 2} ${y + 14}l7 7 -7 7 -7 -7Z" fill="${t.color}"/><text x="${xx + unit / 2 + 12}" y="${y + 24}" font-size="10" fill="#849487">${t.start.slice(5)}</text>`;
    } else {
      bars += `<rect data-bar="${t.id}" data-unit="${unit}" x="${xx}" y="${y + 13}" width="${w}" height="16" rx="3" fill="${t.color}"/><text x="${xx + w + 6}" y="${y + 24}" font-size="11" fill="#849487">${esc(t.owner || t.name)}</text>`;
    }
    for (const dep of t.deps) {
      if (!pos.has(dep)) continue;
      const p = all.find((a) => a.id === dep),
        sx = x(p.finish) + unit,
        sy = 58 + pos.get(dep) * 42 + 21,
        ex = xx,
        ey = y + 21,
        mid = Math.max(sx + 7, ex - 8);
      arrows += `<path d="M${sx} ${sy}H${mid}V${ey}H${ex}" fill="none" stroke="#9aaca0" stroke-width="1" marker-end="url(#arrow)"/>`;
    }
  });
  return `<svg class="chart-header" width="${width}" height="58" aria-hidden="true"><rect width="${width}" height="58" fill="#f7f9f7"/>${ticks}<rect width="${width}" height="31" fill="#f7f9f7"/>${months}<path d="M0 58H${width}" stroke="#dce4df"/></svg><svg width="${width}" height="${height - 58}" role="img" aria-label="Project Gantt timeline"><defs><marker id="arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0 0L5 2.5L0 5Z" fill="#849487"/></marker></defs><g transform="translate(0,-58)">${grid}${ticks}${lines}${arrows}${bars}</g></svg>`;
}
function add(kind) {
  mutate(() => {
    const id = Math.max(0, ...project.tasks.map((t) => t.id)) + 1;
    const current = project.tasks.findIndex((t) => t.id === selected);
    let index = project.tasks.length,
      level = 0;
    if (current >= 0) {
      const t = project.tasks[current];
      level = t.kind === "phase" ? t.level + 1 : t.level;
      index = current + 1;
      if (t.kind === "phase")
        while (
          index < project.tasks.length &&
          project.tasks[index].level > t.level
        )
          index++;
    }
    project.tasks.splice(index, 0, {
      id,
      name:
        kind === "phase"
          ? "New phase"
          : kind === "milestone"
            ? "New milestone"
            : "New task",
      kind,
      level,
      start: project.start,
      duration: kind === "milestone" ? 0 : 1,
      deps: [],
      owner: "",
      color: "#22d3ee",
    });
    selected = id;
    selectedIds.clear();
    selectedIds.add(id);
    selectionAnchor = id;
  });
}
function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = name;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
const safeName = (name) => name.replace(/[\\/:*?"<>|]/g, "-").trim() || "project";
async function save() {
  filename = safeName(project.name) + ".pln";
  downloadBlob(new Blob([JSON.stringify(project, null, 2)], {type:"application/json"}), filename);
  dirty = false; render();
  notify("Download started. Keep the .pln file to continue later.");
  return true;
}
function saveAsProject() { return save(); }
$("#save").onclick = save;
$("#saveAs").onclick = saveAsProject;
$("#exportXml").onclick = async () => {
  try {
    const tasks = schedule(project);
    if (!tasks.length) throw Error("Add a task before exporting.");
    const r = await fetch("/api/xml", {method:"POST", headers:{"Content-Type":"application/json", "X-PC-Plan":"1"}, body:JSON.stringify({project:{...project,tasks}})});
    if (!r.ok) throw Error((await r.json()).error);
    downloadBlob(await r.blob(), safeName(project.name)+".xml");
    notify("Project XML downloaded. Open it in Microsoft Project. Advanced source settings are not included.");
  } catch(e) { notify(e.message); }
};

$("#undo").onclick = () => {
  if (history.length) {
    project = history.pop();
    if (!project.tasks.some((t) => t.id === selected)) selected = null;
    dirty = true;
    render();
  }
};
$("#projectName").onchange = (e) =>
  mutate(() => {
    project.name = e.target.value.trim() || "Untitled project";
  });
$("#projectStart").onchange = (e) =>
  mutate(() => {
    date(e.target.value);
    project.start = workday(e.target.value);
    notify("Project start updated. Existing task dates are kept.");
  });
$("#addTask").onclick = () => add("task");
$("#addPhase").onclick = () => add("phase");
$("#addMilestone").onclick = () => add("milestone");
$("#scale").onchange = (e) => {
  scale = e.target.value;
  timelineZoom = 1;
  $("#schedule").scrollLeft = 0;
  render();
};
function zoomTimeline(factor) {
  const container = $("#schedule");
  const oldUnit = timelineUnit;
  const tableWidth = container.querySelector("table")?.getBoundingClientRect().width || 568;
  const viewport = Math.max(0, container.clientWidth - tableWidth);
  const anchor = container.scrollLeft + viewport / 2;
  timelineZoom = Math.max(0.125, Math.min(8, timelineZoom * factor));
  render();
  container.scrollLeft = Math.max(0, anchor * timelineUnit / oldUnit - viewport / 2);
}
$("#zoomOut").onclick = () => zoomTimeline(1 / 1.25);
$("#zoomIn").onclick = () => zoomTimeline(1.25);
let resizeTimer;
window.addEventListener("resize", () => {
  if (scale !== "fit") return;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(render, 80);
});
$("#bulkColor").onchange = (e) => {
  if (selectedIds.size < 2) return;
  const color = e.target.value;
  mutate(() => {
    selectedIds.forEach((taskId) => {
      const task = project.tasks.find((t) => t.id === taskId);
      if (task) task.color = color;
    });
  });
};
$("#details").onclick = () => {
  details = !details;
  $("#details").textContent = details ? "Fewer columns" : "More columns";
  render();
};
function subtree(index) {
  let end = index + 1;
  while (
    end < project.tasks.length &&
    project.tasks[end].level > project.tasks[index].level
  )
    end++;
  return end;
}
$("#indent").onclick = () =>
  mutate(() => {
    const i = project.tasks.findIndex((t) => t.id === selected);
    if (i <= 0) throw Error("Select a task after a phase to indent it.");
    let prev = i - 1;
    while (prev >= 0 && project.tasks[prev].level > project.tasks[i].level)
      prev--;
    if (
      prev < 0 ||
      project.tasks[prev].kind !== "phase" ||
      project.tasks[prev].level !== project.tasks[i].level
    )
      throw Error("The previous item at this level must be a phase.");
    const end = subtree(i);
    for (let j = i; j < end; j++) project.tasks[j].level++;
  });
$("#outdent").onclick = () =>
  mutate(() => {
    const i = project.tasks.findIndex((t) => t.id === selected);
    if (i < 0 || project.tasks[i].level === 0)
      throw Error("This task is already at the top level.");
    const end = subtree(i);
    if (
      end < project.tasks.length &&
      project.tasks[end].level === project.tasks[i].level
    )
      throw Error(
        "Outdent the last item in a phase first, to keep later tasks in their phase.",
      );
    for (let j = i; j < end; j++) project.tasks[j].level--;
  });
$("#delete").onclick = () => {
  const i = project.tasks.findIndex((t) => t.id === selected);
  if (i < 0) return;
  const end = subtree(i),
    count = end - i;
  modal(
    `<h2>Delete ${count === 1 ? "this task" : count + " tasks"}?</h2><p>${esc(project.tasks[i].name)}${count > 1 ? " and its children" : ""} will be removed. Predecessor links to these tasks will also be removed. You can undo this change.</p><div class="buttons"><button data-close>Cancel</button><button id="confirmDelete" class="primary">Delete</button></div>`,
  );
  $("#confirmDelete").onclick = () => {
    close();
    mutate(() => {
      const removed = new Set(project.tasks.splice(i, count).map((t) => t.id));
      for (const t of project.tasks)
        t.deps = t.deps.filter((id) => !removed.has(id));
      selected = null;
      selectedIds.clear();
      selectionAnchor = null;
    });
  };
};
$("#new").onclick = async () => {
  if (!(await abandon())) return;
  modal(
    `<h2>A fresh start.</h2><p>Give your project a name and its first working day.</p><label>Project name</label><input id="newName" value="Untitled project" maxlength="200"><label>Start date</label><input id="newStart" type="date" value="${iso(new Date())}"><div class="buttons"><button data-close>Cancel</button><button id="create" class="primary">Create project</button></div>`,
  );
  $("#create").onclick = async () => {
    try {
      load(
        blank(
          $("#newName").value.trim() || "Untitled project",
          $("#newStart").value,
        ),
      );
      dirty = true;
      close();
      render();
      notify("Project created. Save downloads a .pln copy to your computer.");
    } catch (e) {
      notify(e.message);
    }
  };
};
$("#open").onclick = async () => {
  if (!(await abandon())) return;
  $("#file").accept = ".json,.pln,.fieldplan";
  $("#file").dataset.action = "open";
  $("#file").click();
};
$("#import").onclick = async () => {
  if (!(await abandon())) return;
  modal(
    '<h2>Reuse a Microsoft Project plan</h2><p>Upload an MPP file to edit in your browser. The server processes it temporarily and does not keep it. Dates, outline, durations, milestones, and owner names are preserved. Tasks start in <b>Fixed dates</b> mode; choose Auto to use weekday scheduling.</p><p>Unsupported link types and calendar differences are listed after import. The source file is never changed.</p><div class="buttons"><button data-close>Cancel</button><button id="chooseMpp" class="primary">Choose MPP file…</button></div>',
  );
  $("#chooseMpp").onclick = () => {
    $("#file").accept = ".mpp";
    $("#file").dataset.action = "import";
    $("#file").click();
  };
};
$("#file").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    if (e.target.dataset.action === "import") {
      notify("Reading Microsoft Project file…");
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.length > 30 * 1024 * 1024)
        throw Error("Maximum MPP size is 30 MB.");
      let b = "";
      for (let i = 0; i < bytes.length; i += 8192)
        b += String.fromCharCode(...bytes.subarray(i, i + 8192));
      const r = await api("/api/import", { name: file.name, content: btoa(b) });
      load(r.project);
      dirty = true;
      close();
      modal(
        `<h2>Imported ${r.project.tasks.length} activities</h2><p>Source dates are preserved. Review the plan before switching any tasks to Auto.</p><div style="max-height:260px;overflow:auto">${r.warnings.map((w) => `<p>• ${esc(w)}</p>`).join("")}</div><div class="buttons"><button data-close class="primary">Review schedule</button></div>`,
      );
    } else {
      if (file.size > 10 * 1024 * 1024) throw Error("Maximum project size is 10 MB.");
      const opened = JSON.parse(await file.text());
      validateLocalProject(opened);
      load(opened, file.name);
      dirty = false;
      close();
      notify("Project opened. Save downloads an updated .pln file.");
    }
    render();
  } catch (err) {
    notify(err.message);
  }
  e.target.value = "";
};
function exportOptionsFromDialog() {
  const name = $("#pdfName").value.trim();
  const start = $("#pdfStart").value;
  const end = $("#pdfEnd").value;
  if (!name) throw Error("Enter a PDF name.");
  date(start);
  date(end);
  if (end < start) throw Error("Export end must be after its start.");
  return {
    name,
    start,
    end,
    scale: $("#pdfScale").value,
    paper: $("#pdfPaper").value,
    orientation: $("#pdfOrientation").value,
    density: $("#pdfDensity").value,
    columns: [...document.querySelectorAll("[data-column]:checked")].map(
      (element) => element.dataset.column,
    ),
    mono: $("#pdfMono").checked,
    milestoneDates: $("#pdfDates").checked,
  };
}
function exportPayload(tasks, options) {
  const { name, ...settings } = options;
  return {
    project: { ...project, name, tasks },
    filename: name,
    settings,
  };
}
async function createPdf(tasks, options, button) {
  button.disabled = true;
  try {
    const result = await api("/api/export", exportPayload(tasks, options));
    const bytes = Uint8Array.from(atob(result.content), c => c.charCodeAt(0));
    downloadBlob(new Blob([bytes], {type:"application/pdf"}), result.filename);
    close(); notify("PDF download started.");
  } catch(e) { notify(e.message); }
  finally { button.disabled = false; }
}
function showPdfPreview(tasks, options) {
  replaceModal(
    `<h2>Preparing preview…</h2><p>Rendering your current paper and layout settings.</p>`,
  );
  api("/api/preview", exportPayload(tasks, options))
    .then((result) => {
      replaceModal(
        `<h2>PDF preview</h2><p>${result.pages.length} page${result.pages.length === 1 ? "" : "s"}. This preview is temporary. Create PDF downloads a copy to your computer.</p><div class="pdf-preview-pages">${result.pages.map((page, index) => `<figure><figcaption>Page ${index + 1}</figcaption><img src="${page}" alt="PDF preview page ${index + 1}"></figure>`).join("")}</div><div class="buttons"><button id="backToExport">Back to options</button><button id="createFromPreview" class="primary">Create PDF</button></div>`,
      );
      $("#backToExport").onclick = () => openExportDialog(tasks, options, true);
      $("#createFromPreview").onclick = (event) =>
        createPdf(tasks, options, event.currentTarget);
    })
    .catch((error) => {
      notify(error.message);
      openExportDialog(tasks, options, true);
    });
}
function openExportDialog(tasks, options, replace = false) {
  const min = tasks.reduce(
      (a, t) => (a < t.start ? a : t.start),
      tasks[0].start,
    ),
    max = tasks.reduce(
      (a, t) => (a > t.finish ? a : t.finish),
      tasks[0].finish,
    );
  const values = options || {
    name: project.name,
    start: min,
    end: plus(max, 7),
    scale: "week",
    paper: "tabloid",
    orientation: "landscape",
    density: "compact",
    columns: ["duration", "start", "finish"],
    mono: false,
    milestoneDates: true,
  };
  const selected = (value, current) => (value === current ? "selected" : "");
  const checked = (value) => (value ? "checked" : "");
  const content = `<h2>A schedule ready to share.</h2><p>Preview the exact paper and layout before you save the PDF.</p><label>PDF name</label><input id="pdfName" value="${esc(values.name)}" maxlength="200"><p>This name appears on the PDF and is used for the file name.</p><label>From</label><input id="pdfStart" type="date" value="${values.start}"><label>Through</label><input id="pdfEnd" type="date" value="${values.end}"><label>Timeline scale</label><select id="pdfScale"><option value="week" ${selected("week", values.scale)}>Weeks</option><option value="day" ${selected("day", values.scale)}>Days</option><option value="month" ${selected("month", values.scale)}>Months</option></select><label>Paper</label><select id="pdfPaper"><option value="tabloid" ${selected("tabloid", values.paper)}>11 × 17 in (Tabloid)</option><option value="legal" ${selected("legal", values.paper)}>8.5 × 14 in (Legal)</option><option value="a3" ${selected("a3", values.paper)}>A3</option><option value="a4" ${selected("a4", values.paper)}>A4</option></select><label>Row spacing</label><select id="pdfDensity"><option value="compact" ${selected("compact", values.density)}>Compact · more tasks per page</option><option value="comfortable" ${selected("comfortable", values.density)}>Comfortable</option></select><label>Orientation</label><select id="pdfOrientation"><option value="landscape" ${selected("landscape", values.orientation)}>Landscape</option><option value="portrait" ${selected("portrait", values.orientation)}>Portrait</option></select><label>Visible columns</label>${["duration", "start", "finish", "owner"].map((column) => `<label class="check"><input type="checkbox" data-column="${column}" ${checked(values.columns.includes(column))}>${column}</label>`).join("")}<label class="check"><input id="pdfMono" type="checkbox" ${checked(values.mono)}>Grayscale</label><label class="check"><input id="pdfDates" type="checkbox" ${checked(values.milestoneDates)}>Milestone dates</label><div class="buttons"><button data-close>Cancel</button><button id="previewPdf">Preview PDF</button><button id="makePdf" class="primary">Create PDF</button></div>`;
  if (replace) replaceModal(content);
  else modal(content);
  $("#previewPdf").onclick = () => {
    try {
      showPdfPreview(tasks, exportOptionsFromDialog());
    } catch (error) {
      notify(error.message);
    }
  };
  $("#makePdf").onclick = (event) => {
    try {
      createPdf(tasks, exportOptionsFromDialog(), event.currentTarget);
    } catch (error) {
      notify(error.message);
    }
  };
}
$("#export").onclick = () => {
  const tasks = schedule(project);
  if (!tasks.length) return notify("Add a task before exporting.");
  openExportDialog(tasks);
};
document.addEventListener("click", (event) => {
  if (!$("#contextMenu").contains(event.target)) hideContextMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hideContextMenu();
});
window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    e.preventDefault();
    save();
  }
  if (
    (e.ctrlKey || e.metaKey) &&
    e.key === "z" &&
    !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
  ) {
    e.preventDefault();
    $("#undo").click();
  }
});
render();
