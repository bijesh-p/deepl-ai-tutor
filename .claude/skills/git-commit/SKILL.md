# Skill: git-commit

---
name: git-commit
description: Stage and commit changes in the MNIST repo with an auto-generated message that references model or training loop changes.
allowed-tools:
  - Bash
---

## Dynamic Context
- Status: !`git status`
- Diff:   !`git diff HEAD 2>/dev/null || git diff --cached`
- Branch: !`git branch --show-current`
- Recent: !`git log --oneline -5 2>/dev/null || echo "(no commits yet)"`

You are committing changes in the MNIST spec-driven project. Follow these steps exactly.

## Instructions
## Step 1 — Gather context

Run these commands to understand what has changed:

```
git status
git diff HEAD 2>/dev/null || git diff --cached
```

If the repo has no commits yet, `git diff HEAD` will fail — `git diff --cached` shows staged changes instead.

## Step 2 — Analyse the diff

Identify which files changed and what kind of change each represents:


## Step 3 — Write the commit message

Rules:
- First line: imperative mood, ≤72 chars, specific to what changed (e.g. "Add dropout to MNISTDenseNet hidden layers", not "Update files").
- If more than one area changed, list them as bullet points in the body.
- Do NOT mention this skill or Claude in the message.

## Step 4 — Stage and commit

Stage only the files visible in `git status` that are part of this change (do not use `git add -A` blindly — exclude `.env`, secrets, or large binaries if any appear). 
Wait for confirmation.Then run  `git add -A && git commit -m "<message>"`
Report commit message.

## Hard constraints

- NEVER run `git push` or any remote-touching git command.
- NEVER use `--no-verify` or any flag that skips hooks.
- NEVER amend a previous commit; always create a new one.
- Only use the Bash tool. No file reads, edits, or writes.