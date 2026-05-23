---
id: TASK-0003
title: Build eidos migrate (consumer migration verb)
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
Consolidates legacy .telos/.research/.governor/.docket/.hone/ directories into single .eidos/ with manifest. Idempotent. Dry-run by default. Handles single-repo (in-place home) and multi-repo (declare home + write .eidos-pointer in member repos).

**Completion notes:** eidos migrate verb landed. Consolidates legacy state directories at the eidos home into .eidos/<forge>/. Idempotent; dry-run by default. Recursive merge handles empty placeholder subdirs. Auto-activates forges in the manifest if migrate finds their legacy dirs. Dogfood proof: migrated eidos-cli-v1's own .docket/ → .eidos/docket/; eidos tick now reports 5 To Do, 1 In Progress, 4 Done instead of zero.
