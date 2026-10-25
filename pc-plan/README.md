# PC Plan Web

A self-contained, stateless browser version of PC Plan, for a home server running other apps. Retains the green/gold task grid, linked Gantt chart, phases, dependencies, PDF layout and MPP import.

## Run

Install Docker Engine and Docker Compose on your server. Extract this folder, then run from it:

```sh
docker compose up -d --build
```

Open `http://YOUR-SERVER-IP:8088`. To choose a different host port:

```sh
PC_PLAN_PORT=8090 docker compose up -d --build
```

The container includes Python, Java, the MPP reader, fonts, PDF renderer and production HTTP service. It has no database, persistent volumes, host folders or external application services. Building the image needs internet access; normal operation does not. It runs independently alongside your other Docker apps. To stop: `docker compose down`.

To move to an offline server after building, use `docker save pc-plan-web:local -o pc-plan-web-image.tar`, transfer it and this folder, then run `docker load -i pc-plan-web-image.tar` and `docker compose up -d --no-build`.

## Selecting tasks

Click a task to select it. Ctrl-click (or Cmd-click) adds tasks one by one. **Shift-click** a task below (or above) the one you clicked to select the whole range between them. With more than one task selected, change the colour of any selected row — or use the “Colour selected” picker in the footer — and the new colour applies to every selected task at once. Undo reverts the whole colour change in one step.

## Timeline controls

Use the − / + buttons beside the timeline scale to zoom in 25% steps. The percentage shows zoom relative to the selected Fit/Day/Week/Month scale; selecting a scale resets it to 100%. The task grid stays fixed on the left while the timeline scrolls horizontally. More columns also remain fixed.

## Files and privacy

- Editing and .pln opening/saving happen in browser memory. Save downloads a file; Open reads the user's selected local file. Nothing is automatically saved. Keep your .pln before closing the tab. Browser download settings control its destination and may add a suffix for duplicate filenames.
- MPP uploads and PDF generation are processed on your server. Each request uses an isolated temporary directory, deleted before responding. Docker places these temporary files in memory-backed /tmp; no user files are retained on persistent storage. Server administrators still control the processing environment.
- Each browser tab has its own schedule; there is no shared workspace or simultaneous collaboration. Users may exchange .pln files themselves.
- PDF preview retains the existing export settings; Create PDF downloads the rendered PDF. Previews are limited to 40 pages; exports to 150. Projects are limited to 1,000 activities; MPP files to 30 MB.
- Export Project XML downloads Microsoft Project MSPDI .xml, including task outline, dates, duration, milestones, finish-to-start links and basic named owners. Open it in Microsoft Project and Save As .mpp if needed. Advanced source calendars, lag, non-FS relations, resource leveling and original formatting are not exported. Microsoft Project may recalculate automatic tasks. Validate important exchanged schedules in Microsoft Project.

## Access from outside your home

Serve this app at the root of its own hostname behind your existing HTTPS reverse proxy, pointing to port 8088. This release has no built-in user accounts. Use your proxy's access controls or VPN for private access. Public visitors can create their own plans but cannot access other sessions through a saved-project endpoint because none exists. Limit request size to 42 MB or slightly above and allow up to 150 seconds for conversion. Do not configure request-body logging or disk buffering for uploads if strict transient processing is required. OS swap/crash dumps can also affect a memory-only policy.

## Validation

Run `node --test tests/schedule.test.mjs` and `python3 -m unittest discover -s tests -p 'test_*.py'`. XML output was parsed successfully with MPXJ 16.9.0, including dates, durations and a dependency. Browser checks passed for task editing, local .pln download, PDF preview/download and XML download. The Docker build and a real Microsoft Project XML round-trip still need validation on a machine with Docker and Microsoft Project. A real MPP fixture is not included.

Original source: https://github.com/pjcroft/LinuxProjectPlanner (snapshot 6eb4a4a). Desktop GTK components are not required.
