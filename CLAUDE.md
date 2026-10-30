# Agent rules

Always-on rules for AI agents working in this repo.

## Rules

Write rules in plain sentences — concise, one line per concept.
Propose a rules edit after an agent failure. Only add it here after the user approves.

## User

Take the user's instructions literally — no reinterpretation or scope expansion.
When a new instruction conflicts with these rules, the docs, or an earlier agreement, raise the conflict with the user.
Ask clarifying questions one at a time.

## Process

Spec first: no code until the user says the spec is done.
Brainstorming stays in chat until the user says **persist**; then write the agreed result into `docs/`.
The spec is done when the docs agree with each other, every contract and edge case the brief needs is set, new terms are defined, the definition of done is stated, and the user agrees.
A spec review runs in a separate session that can only see the changes proposed.
Do not mark anything done without the user and cited evidence (test output, a run result).

## Decisions and AI usage

Agreed design decisions go in [`docs/decisions.md`](docs/decisions.md).
Each AI action goes in the AI-usage section of `README.md` as it happens.

## Docs

Show doc changes in chat as a quoted New line, not a diff.
Doc format: `# Title`, a scope paragraph, then `##` sections; no dates or status badges.
Prefer simple lists over tables when items fit on one line.

## Git

Do all work on a local branch.
Commit or push only when the user says.
