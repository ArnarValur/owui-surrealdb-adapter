---
description: Boots a conductor session — reads the hot set (pulse, last relay entry, tracks, workflow, rules, glossary) and reports where things stand. Use when the user wants to start or resume a session in a repo with a conductor/ folder, or asks where things stand, what's next, or what happened last session.
---


# Conductor — Boot

When the user invokes `/conductor`, restore working context from `conductor/` and report status. Boot is a **read ceremony** — it writes nothing.

---

## Step 0: Pre-flight

- If `conductor/` does not exist, halt:
  > "`conductor/` is missing — recover it from git history: `git log --oneline --all -- conductor/`, then `git checkout <sha> -- conductor/`."
- If `conductor/pulse.md` does not exist, halt:
  > "`conductor/pulse.md` is missing — recover it from git history: `git log --oneline --all -- conductor/pulse.md`, then `git checkout <sha> -- conductor/pulse.md`."
- **Halt on nothing else.** Every other file is optional — skip what's absent, silently.

---

## Step 1: Freshness — shared state comes from origin/main

`pulse.md`, `relay.md`, and `tracks.md` are shared across sessions and machines; `/checkpoint`'s fold-to-main flow keeps their truth on `main`.

1. `git fetch origin main` — skip silently if there is no remote named `origin`. If the fetch fails (no network, no credentials), don't retry: read the working tree and add the offline warning in Step 4.
2. If `origin/main` is ahead of the local copies, read the three shared files from it (`git show origin/main:conductor/pulse.md`, etc.). Otherwise read the working tree.

**Own-repo conductor:** if `conductor/.git` exists, `conductor/` is its own repo — run both steps inside it (`git -C conductor fetch origin main`, then `git -C conductor show origin/main:pulse.md`, etc.).

---

## Step 2: Load the hot set — and nothing else

| Read | How much |
|------|----------|
| `conductor/pulse.md` | whole file (~60 lines) |
| `conductor/relay.md` | **last entry only** |
| `conductor/tracks.md` | the one-liners |
| `conductor/workflow.md` | whole file |
| `conductor/agent-rules/behavioral.md` | whole file, when present |
| `conductor/context.md` (glossary) | whole file, when present |

Budget: the hot set should land around **300–400 lines total**. If it balloons past that, a state file is breaking its cap — flag it in the status report.

**Do NOT read at boot:** track plans, ADRs, `docs/`, `project-context.md`, `prd.md`, `agent-rules/technical.md`, archives. Those are warm loads (Step 3).

---

## Step 3: Warm loads — triggered by work, never by boot

| When work enters… | Load |
|-------------------|------|
| A specific track | the `plan.md` its `tracks.md` one-liner points to (+ `spec.md` beside it, when present) |
| An architecture or design question in a domain | the `conductor/adr/` entries for that domain, when any exist |
| Hands-on technical work in an area with rules | `conductor/agent-rules/technical.md`, when present |
| Product identity, guidelines, or tech-stack questions | `conductor/project-context.md` (+ `prd.md` when present) |
| Long-form background | the specific file in `conductor/docs/` |
| History ("when/why did we…") | older `relay.md` entries, then `conductor/pulse-archive/` |

---

## Step 4: Status report (~10 lines)

```text
🎵 Conductor online — {project}

📍 Now: {one line from pulse § Now}
🚀 Tracks: {N active} — {one-liners, max 3}
⚠️ Blockers: {count, or "none"}
📋 Next: {top of pulse § Next queue}
🧠 Last session: {relay last entry — one-line what + status}

Ready. What's our heading?
```

Add a warning line only when true — one per condition:

- Hot set over budget, or `origin/main` ahead of the working tree.
- **Offline** — the Step 1 fetch failed: *"⚠️ Couldn't reach origin — showing local state, which may be behind."*
- **Pulse stale** — the `> **Updated:**` date in `pulse.md` is more than **14 days** before today (check with `date +%F`): *"⚠️ Pulse last updated {date} ({N} days ago) — § Now and § Next may be stale; verify before acting, and end with `/checkpoint`."*

---

## Session behavior

- The two laws in `conductor/workflow.md` govern every write: one fact one home; a ruling binds only when it lands in a repo file.
- **Only `/checkpoint` writes `pulse.md` and `relay.md`, and only when the human asks for it.** Never patch the pulse or add a relay entry mid-session — carry live state to the checkpoint.
- When a decision crystallizes mid-session, put it where it lives **now** (propose an ADR for approval, add a D-number to the track plan, or note live state for the pulse rewrite) — don't hold it for checkpoint.
- At the end of a session, offer to run `/checkpoint`. Run it whenever the human asks, in any wording; never on your own.
