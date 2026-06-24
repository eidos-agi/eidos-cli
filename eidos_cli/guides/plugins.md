# Plugins — the recursive layer

Per ADR-009, the engine is small; plugins are how the system extends
itself. A plugin is a reusable pattern lifted out of a praxis turn:
descriptive ("here's what happened") refined into prescriptive ("when
this situation recurs, do this").

## Why this exists

The CLI ships four verbs of plugin runtime. Everything else
plugin-related is itself implementable as a plugin. This boundary keeps
the engine fixed-cost while letting the *quality of plugins* improve
over time. Running `eidos learn` against praxis turns about
plugin-promotion sessions can emit a better `learn` plugin. The system
becomes self-improving at the plugin layer.

## The four verbs

```
eidos plugin list [--candidates]    — installed plugins; ledger if --candidates
eidos plugin install <path> [--scope local|global] [--force]
eidos plugin run <slug> [--arg k=v...]
  eidos plugin run --continue <slug> --work-dir <path>   ← runs verify.py
eidos plugin show <slug>            — manifest + playbook head
```

## Top-level aliases

A plugin's `plugin.yaml` can declare `alias: <name>`. At CLI startup the
engine scans both stores and registers each alias as a top-level
command that dispatches to `eidos plugin run <slug>`. Aliases colliding
with engine primitives are rejected — primitives win.

`eidos learn` is first-class because promotion is the common path. It
wraps the bundled `learn` plugin so operators can start, inspect,
verify, and finish a draft without remembering the lower-level plugin
runtime commands:

```
eidos learn --arg from_praxis=<tick-id>
eidos learn --status
eidos learn --continue --work-dir <path>
eidos learn --finish --work-dir <path> --scope global
```

## Two-tier store

```
<eidos_home>/.eidos/plugins/<slug>/   ← local; applies to this eidos only
~/.eidos/plugins/<slug>/               ← user-global; applies across every eidos
```

Lookup is local-first. The user-global store IS the cross-eidos
propagation mechanism. A learning earned in one eidos becomes available
to every other eidos this user operates.

## Plugin shape

```
<slug>/
  plugin.yaml      — slug, version, description, alias, when_to_fire,
                     owner_forge, tags, required_evidence, faculty
  playbook.md      — substrate-readable procedure (the prompt)
  verify.py        — optional; verify(work_dir, draft_dir) → dict
  examples/        — optional sample inputs + outputs
```

Optional `faculty` metadata turns a matched plugin into an explicit
specialist recommendation for the substrate:

```yaml
faculty:
  role: foresight research subagent
  invoke_as: zoltar
  handoff: decide what is likely to be regretted before ACT
```

Use `faculty` when the plugin represents a judgment mode or subagent,
not merely a command. Eidos still does not perform the specialist work;
it routes the substrate toward the right intelligence and preserves the
evidence requirements.

## How `eidos do` reads them

PERCEIVE matches installed plugins against the task via four paths:

1. Task frontmatter `required_plugins: [<slug>]` → REQUIRED match.
2. Task `owner_forge` equals the plugin's `owner_forge`.
3. Task `tags` overlap with plugin `tags`.
4. Token-overlap between task title+body and plugin `when_to_fire`
   (conservative threshold to keep noise low).

Matched playbooks are copied into the context bundle under
`contexts/<task-id>/plugins/<slug>.md` with a REQUIRED/advisory marker
and the match reasons.

If a matched plugin declares `faculty`, PERCEIVE also writes a
`recommended_faculties` list into the context bundle and `eidos do
--json` output. Each entry names the specialist to invoke, why it
matched, what handoff it needs, and which evidence the checker should
expect.

## Converge

`converge` is the installed plugin for measurable software completion. Use it
when a task asks whether software is complete, reliable, production-ready, or
at 100%, or when the work has target/probe comparisons, drift monitors,
regression memory, or repeated repair/re-score loops.

The boundary is:

- Converge adapters emit rows.
- Converge aggregators summarize rows.
- Codex repairs rows.
- Eidos preserves the outer evidence, continuation, learning, and closeout loop.

Useful checks:

```
eidos plugin show converge
eidos plugin run converge
```

## Eidos Skills Hub

`eidos-skills-hub` is the installed plugin for skill discovery. Use it when a
task depends on finding the right Codex skill, skills.sh entry, or first-party
Eidos skill hub before implementation.

The boundary is:

- Eidos Skills Hub searches and identifies skill sources.
- Codex reads and follows the selected skill.
- Eidos preserves the outer evidence, continuation, learning, and closeout loop.

Useful checks:

```
eidos plugin show eidos-skills-hub
eidos route "find and apply the right Codex skill for a task"
```
