---
id: TASK-0005
title: Wire eidos tick (praxis tick at current eidos)
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
Reads the eidos's telos three _when triggers, checks against current state and praxis drift_category library, emits arrived / dead / drifting / on-course. Depends on praxis-md being renamed from hone and on praxis library providing drift classification API.

**Completion notes:** eidos tick verb landed in eidos_cli/cli/scope.py. Reads telos triggers + docket task counts from .eidos/docket/ + recent praxis turns from .eidos/praxis/turns/. Emits human-readable or JSON snapshot. --record flag writes a turn entry to .eidos/praxis/notebook.md. Per the doctrine: this is the STRUCTURAL tick (surfaces data for classification). The COGNITIVE tick (Pod auto-classifies against telos triggers) is a follow-on that ships when Rhea-class substrate makes the latency affordable. Tested against eidos-cli's own eidos; verb fires cleanly. Docket counts read .eidos/docket/ only — eidos migrate (TASK-0003) is what moves legacy .docket/ tasks into .eidos/docket/.
