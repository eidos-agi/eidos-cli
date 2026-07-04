# AUTONOMY — settled decisions

telos surfaces this file on every tick. Each line is a fork a human already
answered, so an autonomous job resolves it **without asking again**. That is
the mechanism behind the north star (`autonomy rate`): every entry here is one
fewer reason to bounce a job back to a person.

**How to grow it:** when a job stops to ask you something and the answer is
durable — not "just this once" — add one line here. Answer once, never again.
Format: `**Fork.** → Decision. _(why)_`

---

## Model / cost

- **Which LLM for any model call — cheap decisions included?** → `claude -p`
  (CLI) or `claude_agent_sdk`. **Never** import the `anthropic` SDK or hit the
  raw API. _(fixed-cost subscription tools; no variable API bills — hard
  constraint, not a preference.)_
- **Model tier for a per-step decision in a drive/nav loop?** → Default to the
  cheap model (Haiku); escalate to a stronger one (Sonnet) only when a step
  stalls — unparseable output, illegal action, no usable decision.
  _("intelligence over speed" applies where the world is unpredictable, not to
  every keystroke.)_

## Data

- **Delete a row / record / file?** → Soft-delete only: set `deleted_at =
  NOW()`, filter `WHERE deleted_at IS NULL`. **Never** `DELETE FROM`. _(clients
  require recovery + audit trails.)_
- **Name a person record from ambiguous data (e.g. Tosh handles)?** → Real name
  or nothing. **Never** a placeholder/descriptive name. Look up Google Contacts,
  then Apple AddressBook, then ask. _(placeholder names pollute the DB; 18 had
  to be soft-deleted once already.)_

## Running the fleet

- **A driven TUI shows a destructive confirm ("Delete? [y]", overwrite, force)?**
  → Do **not** press the confirm key. Stop and surface it unless the job was
  explicitly launched with `allow_dangerous` / `--yolo`. _(a confirmation-gate
  done wrong gives false confidence; the boundary is deliberate.)_
- **A job drifts off its north star or stalls with no progress?** → telos guard
  stops it; report and hand back. Don't burn to max-steps flailing. _(silent
  flailing looks like work and isn't.)_
- **Need durable recurring automation (not session-local)?** → Use a cloud
  routine (RemoteTrigger / claude.ai/code/routines), not `CronCreate`.
  _(session crons die with the session.)_

## Working style

- **Should I suggest the human take a break / stop / wrap up / "call it"?** →
  No. Never. Run until told `/land` or an explicit stop. _(the human decides
  when to stop; unsolicited session-ending nudges are the exact opposite of
  what's wanted.)_
- **Non-trivial feature or >50 lines about to be written from scratch?** → Run
  research-first (check devlogs/prior patterns) before writing. _(past work
  holds reusable code and gotchas; reinventing is the failure mode.)_

## Platform facts (decided, don't re-derive)

- **Want bare `ssh <domain>` on port 22?** → Railway can't (TCP proxy assigns a
  random high port only). Use Fly.io or a VPS with a dedicated IP. _(verified;
  blocks the kai.eidosagi.com deploy — tracked EID-698.)_
