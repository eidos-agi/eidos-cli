---
id: TASK-0010
title: system-of-record routing config for eidos do DOCUMENT step
status: To Do
created: '2026-05-14'
---
When eidos do completes a task, the DOCUMENT step writes back to whichever system of record the task improved (docs, ADRs, external APIs, etc.). The routing rules live in .eidos/governor/sops/ — e.g., 'tasks tagged docs → update README.md or eidos-philosophy/'; 'tasks tagged infra → update Pulumi state'; 'tasks tagged research → write finding to research forge'. SOP-based, so per-eidos configurable. Initial rules: task tagged 'docs' → update relevant .md; task tagged 'governance' → write ADR; default → write to docket completed/ only.
