# Plugin runtime — the four-verb engine

The runtime is the minimum the engine needs to load and run plugins.
Anything beyond these four verbs is itself implementable as a plugin.

## `eidos plugin list [--candidates] [--json]`

Returns installed plugins de-duped by slug (local wins over global).
Adds `--candidates` to surface the plugin-candidate ledger from the
current eidos's `praxis/plugin_candidates.jsonl`.

## `eidos plugin install <path> [--scope local|global] [--force]`

Copies a plugin directory into the chosen store. The destination
directory name is the plugin's `slug` from `plugin.yaml`, NOT the source
directory name. This means `eidos plugin install /tmp/draft` where
`/tmp/draft/plugin.yaml` declares `slug: my-pattern` installs to
`~/.eidos/plugins/my-pattern/`, not `~/.eidos/plugins/draft/`.

## `eidos plugin run <slug> [--arg k=v...]`

Emits a context bundle under
`<eidos_home>/.eidos/praxis/plugin_runs/<slug>-<timestamp>/` (or
`~/.eidos/plugin_runs/` outside an eidos):

```
<work_dir>/
  context.json        — args + plugin metadata + eidos location
  playbook.md         — copy of the plugin's playbook
  draft/              — substrate writes outputs here
```

The substrate reads playbook.md + context.json, writes outputs to
draft/, then invokes `--continue`.

## `eidos plugin run --continue <slug> --work-dir <path>`

Loads the plugin's `verify.py` and calls
`verify(work_dir, draft_dir) → dict`. Plugins without `verify.py` pass
trivially. Exit code 0 on pass, 2 on fail.

## `eidos plugin show <slug>`

Prints the full `plugin.yaml` plus the first 40 lines of `playbook.md`.
Use this to inspect a plugin before installing or invoking.

## First-run bootstrap

On first CLI invocation, the runtime copies every plugin bundled in the
wheel (under `eidos_cli/plugins/`) into `~/.eidos/plugins/`. Idempotent
— subsequent invocations skip existing slugs. Subsequent `eidos-cli`
upgrades do not overwrite user edits.

## Top-level alias registration

At CLI startup, `discover_aliases` scans both stores and registers each
plugin's declared `alias` as a top-level command that dispatches to
`eidos plugin run <slug>`. Conflicts with reserved primitives (`do`,
`spawn`, `define`, etc.) are silently rejected — primitives win.
