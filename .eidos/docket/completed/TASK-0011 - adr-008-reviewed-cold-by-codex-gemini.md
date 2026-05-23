---
id: TASK-0011
title: ADR-008 reviewed cold by Codex + Gemini
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
Before implementing eidos do, send ADR-008 to codex exec and gemini -y -p for adversarial review. Same pattern as THE-EIDOS doctrine review: where does it contradict? where does it overclaim? where would a careful reader get stuck? what's the strongest pushback? Use findings to tighten ADR-008 before any orchestrator code lands.

**Completion notes:** Codex + Gemini both verdict TIGHTEN; both converged on the same critiques. Tightened ADR-008:

(1) Phases now use THE-LOOP's canonical names (PERCEIVE/DECOMPOSE/SPECIALIZE/ACT/COMPRESS/VERIFY/LEARN/RETRY). Dropped the parallel STUDY/RESEARCH/ADVERSARIAL/PLAN/DOCUMENT/META vocabulary that obscured the doctrine. Both reviewers correctly flagged this as the headline issue.

(2) CARDINALITY moved from post-PLAN to PREFLIGHT after PERCEIVE. Phase-local upward override allowed; downward override never. Fixes the 'Solo agent does the heavy lifting then asks for help' antipattern Gemini called the 'Hallucination Trap.'

(3) COMPRESS now explicit between ACT and VERIFY — the missing fix-for-context-degradation step from THE-LOOP. RECONCILE noted as implicit pre-VERIFY behavior.

(4) RETRY now explicit per THE-LOOP's rotation-on-retry rule.

(5) Continuation envelope spec'd for --continue safety: hashed bundle (eidos id, task version, plan hash, SOR routing hash, member repo SHAs, substrate label, evidence ref). Stale-state refuses explicitly. Fixes Codex's split-brain critique.

(6) Five durable artifacts revised: plan, EVIDENCE BUNDLE (the missing one both reviewers flagged), praxis turn, completed task, SOR update. Plugin candidate is conditional/sixth, not counted as core.

(7) SOR routing keyed on artifact class + owner forge + target + required evidence + fallback. Tags downgraded to selectors. Fixes Codex's 'tags-as-authority is too weak.'

(8) Plugin promotion threshold tightened: ≥3 obs + ≥2 verified successes + ≥1 failure analysis, per-eidos overridable. Fixes both reviewers' 'noise vs signal' concern.

(9) High-stakes VERIFY fails closed: for Solo-never-floor operations, semantic uncertainty escalates to Pair or human review rather than passing on Solo judgment. Fixes Codex's accountability-chain contradiction.

(10) Implementation order rewritten to match new phase names. ADR-008 now 8 explicit phases (matching THE-LOOP) + cardinality preflight.
