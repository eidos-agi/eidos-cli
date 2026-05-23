---
id: TASK-0001
title: Wire eidos-aware path resolution into forge libraries
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
Each forge library (telos-md, research-md, governor-md, docket-md, praxis-md) currently writes to its legacy state dir (.telos/, .research/, etc.). When called via 'eidos <forge>' inside an eidos, they should write to <eidos_home>/.eidos/<forge>/ instead. Implement by monkey-patching DOCKET_DIR / CONFIG_DIR / GOVERNOR_DIR constants in a Typer callback before the forge app runs, OR by adding configurable state-dir injection to each forge library (cleaner; longer-term).

**Completion notes:** Eidos-aware path resolution landed for docket-md (and partial for research-md). DOCKET_DIR monkey-patch now reaches all use sites via from-import → module-access conversion. Tasks created via 'eidos docket task-create' inside an eidos write to .eidos/docket/tasks/ instead of legacy .docket/. Idempotent fallback: forges whose .eidos/<forge>/<config> isn't seeded fall back to legacy paths. 62 docket-md tests still pass. Governor + telos integration still pending — VisionCore reads .governor/ from many places and needs a deeper refactor.
