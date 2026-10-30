<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Refactor Opportunities (C1, C8, C10)

- **Plan**: context/changes/refactor-opportunities/plan.md
- **Mode**: Deep
- **Date**: 2026-10-30
- **Verdict**: REVISE → SOUND after triage
- **Findings**: 2 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | WARNING |
| Blind Spots | FAIL |
| Plan Completeness | WARNING |

## Grounding
18/18 existing paths ✓ (2 new files absent, as expected), 8/8 symbols ✓, brief↔plan ✓, Progress↔Phase ✓ (12/12)

## Findings

### F1 — C8 guard (Phase 5) cannot see what it is supposed to pin

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 5 — Contract
- **Detail**: Sprite3D/Label3D only call `material_set_shader(get_material(), shader_rid)` (`sprite_3d.cpp:305-307`), and `last_shader` is private. RenderingServer has no `material_get_shader`, and `DummyMaterial::shader` sits in a private `material_owner` (`servers/rendering/dummy/storage/material_storage.h:58-63`). The suggested observable path does not exist.
- **Fix A ⭐ Recommended**: Add a non-virtual read accessor `material_get_shader(RID) const` to the dummy MaterialStorage, as an explicit behaviour-neutral seam.
  - Strength: One place; covers every node.
  - Tradeoff: Touches servers/rendering/dummy.
  - Confidence: HIGH — owns_material/owns_shader are precedent.
  - Blind spot: Label3D surface material RIDs must be reachable.
- **Fix B**: Per-node accessors under `#ifdef TESTS_ENABLED`.
  - Strength: No server change.
  - Tradeoff: Seams in two node classes.
  - Confidence: MED.
  - Blind spot: Whether such seams are accepted in scene/.
- **Decision**: FIXED (Fix A). Phase 5 gains change item §2 (dummy storage seam) and a precise Contract.

### F2 — NavigationDebug3D guard breaks template_debug + disable_3d, and no check catches it

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phases 10–12
- **Detail**: `scene/resources/navigation_mesh.cpp` is built even with `disable_3d=yes`, and its debug block is guarded only by DEBUG_ENABLED. After Phase 11 it calls NavigationDebug3D, which is compiled only under !NAVIGATION_3D_DISABLED in `scene/3d/` (not built with disable_3d). The only disable_3d gate was template_release, where DEBUG_ENABLED is off.
- **Fix**: Wrap navigation_mesh.cpp's NavigationDebug3D include and calls in `#ifndef NAVIGATION_3D_DISABLED`, and add a `template_debug disable_3d=yes` build to Phases 10–12.
- **Decision**: FIXED. Added the "Debug no-3D template" common command, the Phase 11 §1 Contract guard, a new criterion in Phases 10–12 (Progress renumbered) and a Testing Strategy line.

### F3 — Phase 12 moves more than "registration"; per-test server reset semantics change

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Critical Implementation Details (C10 lifecycle); Phases 8, 12
- **Detail**: Seeding is `member = GLOBAL_DEF(...)` (`navigation_server_3d.cpp:314-343`). Tests create a fresh server per case, so after Phase 12 the owner's state would leak between cases. Found during triage: the `MOVE_PROJECT_SETTING_*` block (`:261-312`) also migrates the 2D keys, and NavigationServer2D (constructed right after) depends on it. Moving it would change 2D behaviour.
- **Fix**: Registration and seeding move into the owner, the migration block stays in the server constructor, and Phase 8 cases restore every value they mutate.
- **Decision**: FIXED (with the user-chosen amendment: keep the migration in the server). The Phase 12 manual check now also verifies 2D migration in the same session.

### F4 — C1 blocks are not token-identical

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architectural Fitness
- **Location**: Current State Analysis (C1); Phases 3–4 Contracts
- **Detail**: Three divergences: the `shader_rid` reset order, the `is_valid()` guard and set_shader/users++ order on a lookup hit, and the destructor lock scope (PPM calls set_shader inside the lock). Normalizing them would risk the #105138 deadlock.
- **Fix**: Document D-a to D-c, preserve each per caller in the Phase 3/4 Contracts, and keep `material_set_shader` out of the primitives.
- **Decision**: FIXED. Destructor line ranges were corrected; plan-brief updated.

### F5 — Phase 11 grep criterion can never pass

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 11 — Automated Verification
- **Detail**: `(…|enable)` matched `set/get_debug_navigation_enabled`, which stays on the server: 10 hits.
- **Fix**: Use `enable_`. Verified: 48 hits today, 0 of them enabled-flag calls.
- **Decision**: FIXED

### F6 — Material2DParams' real home is BaseMaterial3D

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 6 §1 Contract
- **Detail**: `get_material_for_2d` is a BaseMaterial3D static (`material.cpp:3047`).
- **Fix**: State the declaring class.
- **Decision**: FIXED

### F7 — enable_agent_paths expected emission count left implicit

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 8 — Signal sequencing
- **Detail**: The emitter checks and resets `navigation_debug_dirty`, which starts `true` (`navigation_server_3d.h:358`).
- **Fix**: Pin the counts: 1 on a fresh server, 0 alone after the initial flag is used up, 1 when coalesced with a nav toggle.
- **Decision**: FIXED (Phase 8 and the Critical Implementation Details table)
