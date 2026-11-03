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

## ast-grep verification in this repo (applies to `m4l4-3-ranking-ast-grep-verification`)

Godot is C++, but ast-grep parses `.h` as **C** by default. Unless you handle that, its counts can be wrong without any warning.

- **Headers are parsed as C++.** The root `sgconfig.yml` maps `*.h` to `cpp`, so run ast-grep from the repo root, or the config won't be picked up. `--lang c` no longer works on `.h` files, because the config has taken them away from C.
- **Match classes by node kind, not by writing a class pattern.** `class $N : public X { $$$ }` doesn't parse, so it matches nothing. Use `kind: class_specifier` plus `has: { field: name, ... }` / `kind: base_class_clause`.
- **Watch out for Godot macros** (`GDCLASS`, `GDVIRTUAL*`, `ERR_FAIL_*`, ...). As C++, they often don't parse the way a pattern expects. For example, the pattern `GDCLASS($A, $B)` finds nothing in headers. Inside a class body, `GDCLASS(X, Y);` is parsed as a `function_declarator`, so match it with a rule: `{kind: function_declarator, has: {field: declarator, regex: "^GDCLASS$"}}`. That rule finds 172 matches in `scene/resources`, the same as `rg`. Check other macro counts against `rg` before relying on them.
- **A zero count is not evidence until the pattern is proven.** Run it once with `--debug-query=ast`. If the output contains `ERROR`, or the pattern doesn't match one known example, fix the pattern before recording the count.
- **Record the command with every figure.** For each corrected number in the report, include the exact `ast-grep` invocation and parser language. The earlier figure stays visible next to it.
- For one-word searches with no structure involved, `rg` is fine. Use ast-grep where the claim depends on code structure (call arguments, inheritance, scope).
