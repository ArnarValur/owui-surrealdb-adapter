---
description: Save session state — rewrite pulse, append one relay entry, graduate lessons, fold to main
---


# Checkpoint — Save Session State

When the user invokes `/checkpoint`, persist the session in five writes and a git fold. Each fact lands in exactly one home — never retell, point.

---

## Step 0: Pre-flight

- If `conductor/` does not exist, halt:
  > "`conductor/` is missing — recover it from git history: `git log --oneline --all -- conductor/`, then `git checkout <sha> -- conductor/`."
- If `conductor/pulse.md` does not exist, halt:
  > "`conductor/pulse.md` is missing — recover it from git history: `git log --oneline --all -- conductor/pulse.md`, then `git checkout <sha> -- conductor/pulse.md`."

---

## Step 1: REWRITE `conductor/pulse.md` — never append

Rewrite the file from scratch. **State only, cap ~60 lines.** Exactly these sections:

```markdown
# Pulse — {project}

> **Updated:** {YYYY-MM-DD HH:MM} by checkpoint

## 📍 Now — what runs where
## 🚀 Active tracks
## ⚠️ Blockers
## 📋 Next queue
## 📌 Parked
```

- **📍 Now:** enumerate live at write time — services, environments, branches in flight. Never copy the previous pulse's claims forward unverified.
- **🚀 Active tracks:** one line each + pointer to the track plan.
- **⚠️ Blockers:** real and current only. Empty is healthy.
- **📋 Next queue:** ordered, actionable — include any ADR candidates the human deferred this session (they exist nowhere else).
- **📌 Parked:** one pointer line per item.

**Forbidden:** Session Focus, Session Memory, Recently Completed, or any narrative/history section. The story goes to relay (Step 2), lessons to rules files (Step 3), decisions to ADRs or track plans (Steps 4–5).

---

## Step 2: Append ONE relay entry — ≤10 lines

Add one entry to `conductor/relay.md`, newest first:

```markdown
## {YYYY-MM-DD} — {short title}
- **What happened:** {plain language — and what it means for the human}
- **Status:** {where things stand}
- **Decisions:** {ADR titles / track-plan D-numbers, or "none"}
- **Next:** {suggested next moves}
```

**Guardrail:** if relay now exceeds **12 entries**, keep the newest **8** and move the rest to `conductor/pulse-archive/relay-pre-{YYYYMMDD}.md` (create the file; append if it exists).

---

## Step 3: Graduate lessons to permanent rules files

A lesson that stays in the transcript is lost — only repo files bind.

- **Technical lesson** (about the code, stack, or tooling): append to `conductor/agent-rules/technical.md` — create the file on first use. **Automatic, no confirmation needed.**
- **Behavioral lesson** (how the human wants the agent to work): **ask the human first**, one lesson at a time. On yes, append to `conductor/agent-rules/behavioral.md` — create the file on first use.

No lessons this session → skip silently.

---

## Step 4: Track upkeep

For each track touched this session:

1. Update its `plan.md` — check off completed tasks, note real deviations.
2. Refresh its one-liner in `conductor/tracks.md` (move to **Done** when finished).

**Do NOT create or update `metadata.json`** — it is retired. Never write one, even if old tracks still carry them.

---

## Step 5: ADRs — only proposed-and-approved in-session

Write `conductor/adr/{NNNN}-{slug}.md` **only** for decisions that were explicitly proposed as an ADR *and* approved by the human during this session. Number from the highest existing ADR.

No sweep, no batch quiz, no "while we're here". Nothing proposed → skip.

---

## Step 6: Fold to main

1. Stage the state: `git add conductor/`
2. Commit: `checkpoint: {≤50-char summary}`
3. If on a work branch, bring the checkpoint commit to `main` (merge or cherry-pick per repo convention) — shared truth lives on `main`.
4. `git push origin main` when a remote exists; skip silently otherwise. If the push fails (no network, no credentials), don't retry and don't touch the remote config — report it in Step 7 and leave the push to the human.

**Own-repo conductor:** if `conductor/.git` exists, `conductor/` is its own (usually private) repo and the parent repo ignores it. Run steps 1–2 inside it (`git -C conductor add -A`, `git -C conductor commit`), skip step 3, and push with `git -C conductor push` when it has a remote (same rule if it fails).

---

## Step 7: Confirm — ≤6 lines

```text
✅ Checkpoint {YYYY-MM-DD HH:MM}
- pulse rewritten ({N} lines) · relay +1 ({M} entries)
- lessons graduated: {T technical / B behavioral, or "none"}
- ADRs: {titles, or "none"} · tracks: {ids, or "none"}
- folded to main: {yes/no} · pushed: {yes / no remote / failed — run `git push`}
```
