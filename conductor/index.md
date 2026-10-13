# Conductor Index — owui-surrealdb-adapter

> Static map of the conductor. Hot is read at every boot; Warm is loaded when
> work enters the domain; Cold only on explicit request. Lazy files appear as
> plain paths until created — turn them into links when they land.
> Each entry names who writes it; nothing else writes that file. This map itself: written by init;
> `/grill` and `/new-track` only turn a lazy entry into a link.

## Hot — every boot

- [Pulse](./pulse.md) — live state · written by `/checkpoint` only, rewritten whole (init creates it)
- [Relay](./relay.md) — session story; boot reads the last entry · written by `/checkpoint` only, one entry per session (init writes the first)
- [Tracks](./tracks.md) — one line per track · written by `/new-track` (adds) and `/checkpoint` (refreshes, moves to Done) (init creates it)
- [Workflow](./workflow.md) — the two laws + task lifecycle · written by the human (init creates it; an upgrade may insert the two laws)
- Behavioral rules — `agent-rules/behavioral.md` _(lazy)_ · written by `/checkpoint`, only with the human's approval
- [Glossary](./context.md) · written by `/grill` and `/new-track`, approved terms only (a brownfield init may seed it)

## Warm — when work enters the domain

- Track plans — `tracks/<domain>/<track-id>/plan.md` (+ `spec.md`) · written by `/new-track` (creates), the working session (ticks tasks), `/checkpoint` (updates)
- [Decisions](./adr/) (load by domain, never wholesale) · written by `/grill`, `/new-track` and `/checkpoint`, only for decisions proposed and approved in-session
- Technical rules — `agent-rules/technical.md` _(lazy)_ · written by `/checkpoint`
- [Project Context](./project-context.md) — identity, guidelines, tech stack · written by the human (init creates it)
- [Product requirements](./prd.md) · written by `/grill`
- [Long-form docs](./docs/) (load specific files only) · written by the human
- [Code Style Guides](./code_styleguides/) · copied in by init, then written by the human

## Cold — explicit request only

- Archives — `pulse-archive/` (trimmed relay entries, old state) · written by `/checkpoint`
- [Scratchpad](./scratchpad.md) — notes · written by the human; the conductor never writes here
