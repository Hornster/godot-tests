<!-- BEGIN @przeprogramowani/10x-cli -->

## 10xDevs AI Toolkit - Module 4, Lesson 2 (Project Map)

Get up to speed in an unfamiliar or legacy repo from evidence, not from directory trees: **Wide Scan first, Deep Focus later.**

```
git history + dependency graph + contributors -> context/map/repo-map.md -> focused /10x-research
```

### Task Router - Where to start

| Skill / prompt | Use it when |
| --- | --- |
| `/10x-repo-map` | One-run Project Map. It ranks business capabilities by criticality × buzz, keeps its evidence in `context/map/evidence/`, and writes `context/map/repo-map.md` with risk zones, a first-day reading list and explicit unknowns. Use `--replace` to refresh; the previous run moves to `context/archive/`. |
| `m4l2-1-territory-git-history` -> `m4l2-2-structure-dependency-cruiser` -> `m4l2-3-contributors-git` -> `m4l2-repo-map-synthesis` | The same map built step by step, one artifact at a time, so you can see what each evidence source adds. |
| `/10x-research` | A question about one feature or area. The map covers breadth and takes no target; depth belongs to research. |

### Hard rules

- **Let tools collect evidence outside the context window.** Use git, the forge and graph tools to gather data, then interpret only their condensed output. Never read the repo file by file.
- **Exclude the noise.** Leave out lockfiles, generated code, bulk formatting commits, bot commits and agent-authored commits when ranking activity.
- **Unknowns are part of the map.** Mark what the evidence can't show as unknown instead of filling the gap with a guess.

<!-- END @przeprogramowani/10x-cli -->
