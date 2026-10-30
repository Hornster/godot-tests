<!-- BEGIN @przeprogramowani/10x-cli -->

## 10xDevs AI Toolkit - Module 4, Lesson 4 (Refactoring)

Go from recorded problems to a refactoring decision you can defend, then make the change in small steps you can reverse.

```
/10x-new (research-only intention) -> /10x-research (options, no decision) -> ast-grep verification -> /10x-plan (decide) -> /10x-implement
```

### Task Router - Where to start

| Skill / prompt | Use it when |
| --- | --- |
| `m4l4-1-new-change-intention` | Opening the change with `/10x-new` and an explicit intention: explore and rank, no refactor, no decision yet. |
| `m4l4-2-refactor-opportunities-research` | Running `/10x-research` over every recorded problem from three read-only angles: current shape, decision history (was it deliberate?), migration feasibility. Ends with ranked options and their trade-offs. |
| `m4l4-3-ranking-ast-grep-verification` | Checking the structural claims behind the ranking with ast-grep and correcting the report so the earlier figure stays visible. |
| `/10x-plan` -> `/10x-plan-review` -> `/10x-implement` | Defend the chosen option in the plan interview, then carry out the plan. |

### Hard rules

- **Research ranks; the plan decides.** No refactor and no final choice inside research.
- **Guard first.** Characterization tests that pin current behaviour come before the first structural change.
- **Every phase can be reverted on its own.** Prefer Strangler Fig, Branch by Abstraction and Mikado-style ordering over a big-bang rewrite.
- **Keep behaviour unchanged.** A refactor phase that changes observable behaviour is a separate change.

<!-- END @przeprogramowani/10x-cli -->
