---
id: TASK-0007
title: Retire governor.vision in favor of Telos forge
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
ADR-007 commits to governor.vision retiring; the four-field telos contract owns the destination artifact. governor-md needs vision-set / vision-view to emit deprecation notice and direct users to eidos define / eidos telos. eidos migrate should move any existing governor vision content into the eidos's telos.md.

**Completion notes:** Soft-deprecation landed in governor-md/_logic/vision.py: vision_view and vision_set print a deprecation notice to stderr pointing users at 'eidos telos view' / 'eidos telos supersede'. Hard removal deferred to a future governor-md major version bump (once consumers migrate). The four-field telos contract (statement + 3 _when triggers) is now unambiguously owned by the Telos forge. Per ADR-007, governor-md continues to own goals, guardrails, SOPs, ADRs — those stay first-class.
