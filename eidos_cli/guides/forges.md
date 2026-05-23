# Forges — the operational layers

A forge is one operational layer of an eidos. Each forge has its own
contracts (artifact shapes, validation rules) and its own state on disk.
An eidos activates the forges it needs and leaves the rest dormant.

## The five forges

| Forge | Purpose | State dir | Library |
|-------|---------|-----------|---------|
| Telos | The four-field contract that *defines* the eidos | `.eidos/telos.md` | `telos-md` |
| Research | Earned, evidence-graded decisions | `.eidos/research/` | `research-md` |
| Governor | Vision, goals, guardrails, SOPs, ADRs | `.eidos/governor/` | `governor-md` |
| Docket | Tasks, milestones, documents, Definition of Done | `.eidos/docket/` | `docket-md` |
| Praxis | Steering ticks, write-turn, notebook, drift snapshots | `.eidos/praxis/` | `praxis-md` |

Telos is special — it defines the eidos itself. Without Telos, no eidos.
The other four activate per-eidos based on what the work needs.

## CLI namespaces

Each forge has a top-level namespace that exposes its library's verbs:

```
eidos telos    [view | supersede | ...]
eidos research [project_init | finding_create | research_brief | ...]
eidos governor [vision-set | guardrail_create | sop_create | adr ...]
eidos docket   [task-create | task-list | milestone-create | ...]
eidos praxis   [tick | write-turn | notebook | status]
```

The forge libraries are PyPI-published packages consumed by eidos-cli
as libraries (not subprocesses). Their internal `_logic/` is called
directly per ADR-007.

## Activation

`eidos define` activates the forge set named via `--forges`. Default
when omitted: `governor,docket,praxis`. Activate later via
`eidos activate <forge>`. Activation is scaffold + seed:

```
.eidos/<forge>/                   ← created
.eidos/<forge>/<config-file>      ← seeded with eidos id + name
```

Manifest's `active_forges` list is the authoritative record.

## Path resolution

When CWD is inside an eidos, the CLI monkey-patches each forge
library's state-dir constant to point at `<eidos_home>/.eidos/<forge>/`
instead of the legacy `.<forge>/` location. Outside an eidos, the
libraries use their legacy paths and operate as standalone tools.

## The trilogy flow (research → governor → docket)

1. **Research** earns a decision with evidence.
2. **Governor** records the decision as an ADR + any contracts (goals,
   guardrails, SOPs) the decision implies.
3. **Docket** executes within those contracts — tasks must respect the
   governor's contracts; PERCEIVE loads them as guardrails.

The flow is one-way. A decision skipped in Research is a contract that
was never earned.
