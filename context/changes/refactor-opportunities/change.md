---
change_id: refactor-opportunities
title: Rank refactoring opportunities from the material resources flow analysis
status: preparing
created: 2026-10-30
updated: 2026-10-30
archived_at: null
---

## Notes

### Source

`context/changes/material-resources-flow-analysis/research.md` analyses this repo and records its technical debt and structural risks (mainly §2 Technical Debt, §1.6 Blast radius, §3 Evidence/inference/unknowns, §4 Structural verification, Open Questions).

### Intention

This change picks up the questions `material-resources-flow-analysis` left open: **which** of the recorded issues are worth fixing, **how**, and **in what order**. We will look at every recorded problem in the code and in git history, then rank them as refactoring opportunities.

### Phases

1. **Exploration (research)**: read-only. No refactoring and **no decision**. The output is `research.md` for this change, ending with a **ranking of options and their trade-offs**. The user reads the report before anything else happens.
2. **Decision and planning**: the choice of what to work on is made here, in `/10x-plan`, not in research.
3. **Implementation**: begins only after the plan is done, reviewed and accepted, and follows that plan.

### Rules for the exploration phase

- Rank, don't decide. Present options with trade-offs and leave the recommendation open.
- Don't change code or run structural edits. ast-grep and git may be used for verification only.
