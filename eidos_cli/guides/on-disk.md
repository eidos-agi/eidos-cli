# On-disk shape

Everything an eidos knows lives in two places: the eidos home and the
user-global config dir. Member repos carry only a one-line pointer.

## The eidos home

```
<eidos_home>/
  .eidos/
    eidos.json                  ← manifest: id, name, members, active_forges, parent_id
    telos.md                    ← four-field telos contract
    pod.log                     ← Solo-never-floor operations append here

    governor/                   ← if active
      vision.md
      guardrails/
      sops/
      adr/

    docket/                     ← if active
      docket.json               ← project config (id, version, project_path)
      tasks/                    ← active tasks
      completed/                ← VERIFY-passed tasks
      promoted/                 ← tasks turned into child eidi
      archive/                  ← retired
      plans/<task>.md           ← substrate-written plan
      evidence/<task>/          ← substrate-written ACT output
      contexts/<task>/          ← PERCEIVE bundle for the task
        context.json
        plugins/<slug>.md       ← matched plugin playbooks (copies)
      envelopes/<task>.json     ← continuation envelope hashes

    research/                   ← if active
      candidates/  findings/  decisions/

    praxis/
      turns/<tick-id>.md        ← praxis turns (LEARN output)
      notebook/
      plugin_candidates.jsonl   ← plugin-promotion ledger
      plugin_runs/<invocation>/ ← `eidos plugin run` work dirs

    plugins/<slug>/             ← eidos-local plugins (local-first lookup)

    children/<child_id>/        ← child eidi
      .eidos/                   ← recursive — same layout
```

## Member repos

A code repository that an eidos works in carries:

```
<repo_root>/.eidos-pointer      ← one line: absolute path to <eidos_home>
```

Plus the same `.eidos-pointer` line in `.gitignore` so it never lands in
version control. The pointer is how `eidos enter` resolves from inside a
repo back to the eidos home.

## User-global config

```
~/.eidos/
  plugins/<slug>/               ← user-global plugin store (cross-eidos)
  plugin_runs/<invocation>/     ← when invoked outside any eidos
```

Per ADR-009, `~/.eidos/plugins/` is the cross-eidos compounding layer.

## Resolution rules

When `eidos` is invoked, the root callback walks up from CWD looking for
the first directory containing **`.eidos/eidos.json`** (just `.eidos/`
is not enough — must have the manifest). If found, that directory is
the eidos home and the forge libraries' state-dir constants are
monkey-patched accordingly. If not found, the libraries use their
legacy paths.

This rule is why `~/` is not mistaken for an eidos despite containing
`~/.eidos/plugins/` — no `eidos.json` in `~/.eidos/`.
