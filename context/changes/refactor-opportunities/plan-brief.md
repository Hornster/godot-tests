# Refactor Opportunities (C1, C8, C10): Plan Brief

> Full plan: `context/changes/refactor-opportunities/plan.md`
> Research: `context/changes/refactor-opportunities/research.md`

## What & Why

This plan carries out the three refactors the research ranked and the user accepted (`RefactoringUserNotes.txt`), in this order:

1. **C1:** one shared shader cache for BaseMaterial3D and ParticleProcessMaterial.
2. **C8:** one typed source of `get_material_for_2d` arguments for Sprite3D, Label3D and the shader baker.
3. **C10:** NavigationServer3D stops including and owning scene-level debug materials and colors.

All three are accidental duplication or coupling. Two have already drifted: C8 through #98122, and C1 through fixes hand-ported per class. The drift gets worse with every class-scoped fix.

## Starting Point

- **C1:** the race-safe create, release and lookup blocks are structurally identical in `material.cpp` and `particle_process_material.cpp`. Three small per-class differences in order and lock scope (D-a to D-c in the plan) are kept as they are.
- **C8:** the baker hand-copies Sprite3D/Label3D defaults and the alpha-cut mapping, and calls the factory with a stale 10-argument list.
- **C10:** `navigation_server_3d.h:36` includes `scene/resources/material.h` for 15 debug-only materials. Next to them sit 14 colors, 12 toggles and 27 project settings.
- **Tooling:** this machine has no compiler and fork CI has never run.

## Desired End State

- One templated cache unit backs both materials' shader maps. Lock scopes are unchanged, and CIM is pinned by tests but not migrated.
- `StandardMaterial3D::Material2DParams` and a shared mapping feed Sprite3D, Label3D and the baker. The baker has no default table and no "must match" comments.
- `navigation_server_3d.h` has no `scene/` include and no draw configuration. A scene-side `NavigationDebug3D` owns it all, while the server keeps its enabled flags and its bound signals.
- All guards are green locally and in fork CI, with an empty doctool diff and an unchanged GDExtension API.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Which candidates, in what order | C1 → C8 → C10 | Accidental, guardable, reversible; the user agreed with the ranking. | Research + user notes |
| C2–C7, C9 | Not touched | Each is deliberate, a behaviour change, or not guardable cheaply. | Research |
| Verification | Local toolchain + fork CI | Fast local loop; CI adds TSan/ASan, `disable_3d`, doctool and other OSes. | Plan |
| CanvasItemMaterial | Pin in tests, don't migrate | Migrating it changes behaviour; the guard is ready for the follow-up. | Plan |
| C8 depth | Mapping + typed params | Removes the default table and by-name overlay, where #98122 drifted. | Plan |
| C8 home | Struct + mapping next to `get_material_for_2d` | A new factory parameter becomes a struct field that every caller sees. | Plan |
| C10 depth | Forward-declare, then move materials **and** colors out | User: "NavigationServer does not sound like something that should need colors in its ownership." | Plan (user-proposed) |
| C10 scope | 3D now, 2D as a follow-up | Bounds the plan to the server that has the `scene/` include. | Plan |
| C10 home | New `NavigationDebug3D` scene-side singleton | Single responsibility; doesn't just undo #62601 by putting it back on SceneTree. | Plan |
| C10 what moves | All draw config (colors, toggles, settings, materials) | Materials and the toggles they read stay together; the server keeps no "how to draw" state. | Plan |

## Scope

**In scope:**
- Characterization tests for all three areas.
- The C1 cache unit, with PPM and BaseMaterial3D migrated.
- The C8 params struct, mapping, nodes and baker.
- The C10 include cut, the owner, caller migration and the state move.

**Out of scope:**
- CIM migration and its unlocked-access fix.
- Unifying lock, init or RID policies.
- Baking `texture_repeat` variants and handling AnimatedSprite3D in the baker.
- NavigationServer2D.
- Any change to signal or project-setting names or defaults.
- C2–C7 and C9.

## Architecture / Approach

The plan is Mikado-ordered: each refactor starts with a guard phase, followed by small structural phases that can each be reverted.

- **C1:** an extract-and-switch per class (PPM, then BaseMaterial3D). The cache exposes non-locking primitives so that every `RS::` call keeps its current lock state, which is what the #105138 deadlock fix depends on.
- **C8:** the factory params come first, then the nodes, then the baker.
- **C10:** Strangler Fig in four steps. A compile-only include cut comes first. Then an owner that **delegates** to the server, then the callers migrate to it, then the state moves and the server's draw API is deleted. Toggle setters reach the server's bound signals through an unbound notify hook that reproduces today's four setter semantics exactly.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Verification baseline | Toolchain, branch, local and CI baseline | Fork-only CI failures muddy the baseline |
| 2. C1 guard | Shader-cache tests for 3 materials | Release is only observable indirectly (RID freshness, LSan) |
| 3. C1 helper + PPM | Cache unit; PPM migrated | Moving an RS call across the lock boundary |
| 4. C1 BaseMaterial3D | Second migration; CI incl. TSan | `material.h` rebuild cost; lock scope |
| 5. C8 guard | Mapping + material `Ref` identity tests | Choosing an observable path to the node material |
| 6. C8 factory params | Struct, mapping, Sprite3D/Label3D switched | Label3D "at least ALPHA" rule |
| 7. C8 baker | Typed params in the baker; CI | Export variant set must stay identical |
| 8. C10 guard | Debug-cluster tests incl. signal sequencing | Pinning the `enable_agent_paths` quirk correctly |
| 9. C10 include cut | Forward declaration + explicit includes | Unknown set of TUs that break |
| 10. C10 owner | `NavigationDebug3D` delegating facade | Lifecycle vs per-suite test servers |
| 11. C10 callers | 10 files migrated | Missed alias call sites |
| 12. C10 move state | Server sheds draw config; CI | Settings registration order and timing |

**Prerequisites:** sudo access to install the build dependencies; push access to `Hornster/godot-tests`; about 5 GB of free disk (90 GB available).
**Estimated effort:** about 6–9 sessions. Phase 1 is dominated by the first build (~30–60 min). C1 and C10 are about 2–3 sessions each, C8 about 1–2.

## Open Risks & Assumptions

- Assumes the dummy RS creates and frees shader RIDs observably enough for C1's release assertions. If it doesn't, the release check falls back to the LSan leak check in CI.
- Moving `GLOBAL_DEF` from the server constructor to `register_scene_types()` could reorder the settings in the editor. The Phase 12 doctool diff and a Project Settings check gate this.
- Fork CI may have jobs that are red for fork-only reasons (secrets, runners). Phase 1 records them as excluded.

## Success Criteria (Summary)

- Each of the three areas has one implementation instead of copies, and the server no longer depends on `scene/`.
- Behaviour is unchanged: guards, the full suite, the doctool diff, the GDExtension API check and baseline-green CI jobs all stay green.
- Each phase is its own commit and can be reverted on its own.
