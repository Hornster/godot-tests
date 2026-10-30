# Refactor Opportunities (C1, C8, C10) Implementation Plan

## Overview

This plan carries out the three refactors ranked in `context/changes/refactor-opportunities/research.md` §3, in the order the user accepted (`RefactoringUserNotes.txt`):

1. **C1**: extract the duplicated "generated shader → refcounted `shader_map`" machinery shared by BaseMaterial3D and ParticleProcessMaterial.
2. **C8**: give Sprite3D, Label3D and the shader baker one typed source for `get_material_for_2d` arguments. This closes the drift path that #98122 already exercised.
3. **C10**: cut `servers/navigation_3d/navigation_server_3d.h → scene/resources/material.h`. Then move all 3D navigation "how to draw" state (colors, toggles, point size, project-setting registration, debug materials) out of NavigationServer3D into a scene-side owner.

Every phase keeps observable behaviour unchanged (CLAUDE.md hard rule). Each refactor starts with a guard phase of characterization tests. Every phase can be reverted on its own.

## Current State Analysis

- **No local toolchain.** The machine has no `scons`, `gcc`, `clang` or `bin/`. Fork CI (`Hornster/godot-tests`, Actions enabled, `runner.yml` on push) has never run. Phase 1 creates both verification channels.
- **C1.** These blocks are structurally identical in BaseMaterial3D and PPM, but not token-identical:
  - the release-old/lookup-new critical section (`material.cpp:669-695`, `particle_process_material.cpp:170-190`);
  - the race-safe create-outside-lock + insert-or-adopt block (`material.cpp:2088-2113`, `particle_process_material.cpp:1360-1381`);
  - the destructor release (`material.cpp:4042-4056`, `particle_process_material.cpp:2842-2855`).

  Verified divergences, all kept as they are by this plan:
  - **D-a (release order).** BaseMaterial3D resets `shader_rid = RID()` *before* `free_rid` (`material.cpp:675`). PPM resets it *after* `erase` (`particle_process_material.cpp:179`).
  - **D-b (lookup hit).** BaseMaterial3D does `users++` and then calls `material_set_shader` behind `_get_material().is_valid()`. PPM calls `material_set_shader` unguarded, *before* `users++`. The create block has the same `is_valid()` difference.
  - **D-c (destructor lock scope).** BaseMaterial3D releases in a scoped lock and calls `material_set_shader(…, RID())` *outside* it, behind `is_valid()`. PPM holds the lock for the whole destructor and calls `material_set_shader(…, RID())` *inside* it, only when `shader_map.has(current_key)`.

  `ShaderData`, `shader_map` and `shader_map_mutex` are declared per class (`material.h:411-417`, `particle_process_material.h:153-158`). Dirty lists and flush policies differ, and they stay as they are. CanvasItemMaterial (CIM) differs: it has no race handling, a single mutex, and unlocked `shader_map` access at `canvas_item_material.cpp:64-77, 148, 235-237`.
- **C8.** The alpha-cut → Transparency mapping exists 3× (`sprite_3d.cpp:289-299`, `label_3d.cpp:388-395`, `shader_baker_export_plugin.cpp:333-346`).
  - The baker also hand-copies 9 defaults (`:313-321`) and overlays node properties by name (`:323-331`).
  - It calls `get_material_for_2d` with 10 positional arguments (`:349, :354`), so `p_texture_repeat` is always `false`.
  - The two `AlphaCutMode` enums are numerically identical (`label_3d.h:50-56`, `sprite_3d.h:53-59`).
- **C10.**
  - `navigation_server_3d.h:36` is the header's only `scene/` include.
  - Inside `#ifdef DEBUG_ENABLED` (`:354-522`) the server holds: 14 colors, 12 toggles, a point size, 15 lazily built `Ref<StandardMaterial3D>`, and their setters and getters.
  - Its constructor registers 27 `debug/shapes/{navigation,avoidance}/3d/*` project settings plus `MOVE_PROJECT_SETTING_*` compat (`navigation_server_3d.cpp:262-343`).
  - None of this is script-bound; only `set/get_debug_enabled` is (`:222-223`). The bound signals `navigation_debug_changed` / `avoidance_debug_changed` (`:227-228`) are fired by toggle setters and by enable/map changes.
  - 10 files call the draw-config API: `editor/editor_node.cpp`, `modules/gridmap/grid_map.cpp`, `modules/navigation_3d/editor/{navigation_link_3d_gizmo_plugin,navigation_obstacle_3d_editor_plugin,navigation_region_3d_gizmo_plugin}.cpp`, `scene/3d/navigation/{navigation_link_3d,navigation_agent_3d,navigation_obstacle_3d,navigation_region_3d}.cpp`, `scene/resources/navigation_mesh.cpp`.

## Desired End State

- One templated cache unit backs the shader maps of BaseMaterial3D and PPM, with each class's lock scopes unchanged. CIM is unchanged, but its behaviour is pinned by tests.
- `StandardMaterial3D` exposes a params struct, a struct-taking `get_material_for_2d` overload and the alpha-cut mapping. Sprite3D, Label3D and the baker derive their materials from it. The baker no longer has a default table, a by-name overlay or "must match" comments.
- `navigation_server_3d.h` includes no `scene/` header and holds no draw configuration. A scene-side `NavigationDebug3D` owns colors, toggles, point size, settings registration and materials. The server keeps the debug enabled flags, the bound signals and an unbound notify hook.
- New characterization tests pin each area, and they pass locally and in fork CI. The doctool diff and the GDExtension API check show no change.

### Key Discoveries:

- The test harness compiles shader code for real through the dummy RS (`servers/rendering/dummy/storage/material_storage.cpp:191`). Failures only print, so tests use `ErrorDetector` (`tests/test_tools.h:35`).
- `[SceneTree]`-tagged tests get a RenderingServer and navigation servers (`tests/test_main.cpp:182-232`). New `tests/scene/*.cpp` files are picked up automatically (`tests/SCsub:11`) and need `TEST_FORCE_LINK` (precedent: `tests/scene/test_sprite_2d.cpp`).
- Signal assertions: `tests/signal_watcher.h`. Deferred calls are flushed with `MessageQueue::get_singleton()->flush()` (precedent: `tests/scene/test_tab_container.cpp:49`).
- Init order: the navigation server is created before `register_scene_types()` and finalized after `unregister_scene_types()`, in both runtime and test setup (`main/main.cpp:781→787`, `:870→890`). In tests a second server may be created per suite (`tests/test_main.cpp:227, 266`).
- `navigation_server_3d.cpp` already includes other `scene/` headers (`:38-40`), so moving `material.h` into it follows the file's convention.
- Every property name the baker looks up exists on Sprite3D. Label3D has all of them except `transparent` (`sprite_3d.cpp`/`label_3d.cpp` `ADD_PROPERTY*`), and the baker's default for that one is `true`. So typed getters reproduce today's baker inputs exactly.

## What We're NOT Doing

- **CIM:**
  - We don't migrate CIM to the shared cache.
  - We don't fix its unlocked `shader_map` access. That is a separate change, guarded by the Phase 2 tests.
- **C1 policies:** we don't unify lock-during-flush, init (`_mark_ready` vs `_mark_initialized`) or eager/lazy RID policy across materials.
- **C8 behaviour changes:**
  - We don't pre-bake `texture_repeat` variants.
  - We don't make the baker handle AnimatedSprite3D. It keeps `cast_to<Sprite3D>`.
  - We don't change Label3D's literal `false` for `p_texture_repeat`.
- **NavigationServer2D:** we don't move its debug color/toggle cluster. That is a follow-up change reusing this pattern.
- **Server signals and settings:**
  - We don't move or rename the bound signals `navigation_debug_changed` / `avoidance_debug_changed`.
  - We don't change any project-setting name or default, or the deprecated `MOVE_PROJECT_SETTING_*` behaviour.
  - We don't change the `debug_dirty` quirk in `set_debug_navigation_enable_agent_paths` (see Critical Implementation Details).
- **Unranked candidates:** we don't touch C2–C7 or C9 (research §3, "Considered and not ranked").
- **Unrelated behaviour:** no change of any kind outside the files listed per phase.

## Implementation Approach

The work is a Mikado-ordered sequence of three independent refactors. Each one starts with a guard phase. Characterization tests pin current behaviour against today's code and must pass **before** any structural edit. Structural phases then move code in steps that each compile and pass the guard.

- **C1** uses an extract-and-switch per class. It touches PPM first because its shape already matches the race-safe path, then BaseMaterial3D.
- **C8** extracts the shared params at the factory. It switches the nodes first, then the baker.
- **C10** uses Strangler Fig / Branch by Abstraction, in four steps:
  1. a compile-only include cut;
  2. a new scene-side owner that **delegates** to the server (scene→server is the allowed direction);
  3. callers migrate to the owner;
  4. the state moves into the owner and the server's draw API is deleted.

  If the later C10 phases are abandoned, the include cut alone still stands.

Verification uses two channels:

- **Per phase, locally:** an editor dev build with tests, plus the targeted test suite.
- **Per refactor group, on the fork:** a push after Phases 4, 7 and 12. This gets TSan/ASan/UBSan runs, the minimal `disable_3d` template, doctool, the GDExtension API check, and Windows/macOS.

Phase 1 records the baseline CI result. A later phase passes CI when no job that was green at baseline turns red.

Common commands (defined once, referenced by phases):

- **Build:** `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8` → `bin/godot.linuxbsd.editor.dev.x86_64` (below: `$GODOT`).
- **Targeted tests:** `$GODOT --test --test-case="*<tag>*"`. **Full suite:** `$GODOT --test`.
- **Format:** `pre-commit run --files <changed files>` (`.pre-commit-config.yaml`).
- **Doctool diff:** `$GODOT --doctool --headless; git diff --exit-code` (mirrors `linux_builds.yml:250-258`).
- **Minimal template:** `scons target=template_release` with the flags from `linux_builds.yml:105-118` (includes `disable_3d=yes`, `deprecated=no`).
- **Debug no-3D template:** `scons platform=linuxbsd target=template_debug disable_3d=yes -j8`. This is the only check that compiles `DEBUG_ENABLED` code with `NAVIGATION_3D_DISABLED`; the minimal template is a release build, so `DEBUG_ENABLED` is off there.

## Critical Implementation Details

**C1 lock scope (timing & lifecycle).** The deadlock fix #105138 depends on `shader_create_from_code` running *outside* the map lock, and on `material_set_shader` running *inside* the same critical sections as today. The cache unit must therefore expose its mutex and non-locking "release / find / insert-or-adopt" primitives, so that each caller keeps its exact `MutexLock` scopes. It must not wrap them in self-locking calls that would move RS calls in or out of the lock. The `shader_rid = RID()` reset on last release in `_update_shader` (`material.cpp:675`) stays with the caller.

**C10 signal sequencing (state sequencing).** Today's setters have four distinct semantics, and the owner must reproduce each one through the server hook:

| Setter kind | Behaviour today |
|---|---|
| Colors, xray toggles, point size | Only patch an already-built material: `set_albedo`, `set_flag(FLAG_DISABLE_DEPTH_TEST)`, `set_point_size`. No signal. |
| Navigation toggles: `edge_connections`, `edge_lines`, `geometry_face_random_color`, `link_connections` | Set `navigation_debug_dirty` and defer `_emit_navigation_debug_changed_signal`. |
| Avoidance toggles | Set `avoidance_debug_dirty` and defer `_emit_avoidance_debug_changed_signal`. |
| `enable_agent_paths` | Defers the navigation emit **without** marking `navigation_debug_dirty`. `debug_dirty` is never reset, so the `if` is always true (`navigation_server_3d.cpp:986-996`). The emitter fires only if `navigation_debug_dirty` is set, and it resets the flag (`:423-428`). That flag starts `true` (`navigation_server_3d.h:358`). Result: 1 emit on a fresh server whose initial flag hasn't been used yet; 0 when called alone after that; 1 in total when coalesced with a navigation toggle before the flush. |

The hook therefore needs a "queue navigation emit, mark dirty: yes/no" form and a "queue avoidance emit" form. These are unbound C++ members on NavigationServer3D.

**C10 lifecycle.** The owner must look up `NavigationServer3D::get_singleton()` on every call and never cache it, because tests can replace the server per suite (`tests/test_main.cpp:266`). Moving `GLOBAL_DEF` registration from the server constructor (`main.cpp:781`) into the owner's construction in `register_scene_types()` (`:787`) shifts registration slightly later. Registration and seeding are one statement per member (`member = GLOBAL_DEF(...)`, `navigation_server_3d.cpp:314-343`), and they move together. The `MOVE_PROJECT_SETTING_*` migrations (`:261-312`) do **not** move. `MOVE_PROJECT_SETTING_2` writes the old shared key into both the `2d/` and `3d/` keys, and NavigationServer2D, which is constructed right after and has no migration of its own, seeds from the migrated 2D values. Moving the block later would change NavigationServer2D's behaviour for legacy projects. The block touches only ProjectSettings, so keeping it in the server constructor costs no `scene/` dependency. Phase 12 confirms with the doctool diff and a Project Settings check that nothing reads these settings in between. Test-lifetime change: today each per-case server re-seeds draw state from settings; after Phase 12 the owner lives once per test run. That is why Phase 8 cases restore every value they mutate.

---

## Phase 1: Verification baseline

### Overview

Create both verification channels and record a green (or known) baseline before any code changes.

### Changes Required:

#### 1. Toolchain

**File**: none (machine setup)

**Intent**: Install SCons, a C++ toolchain and Godot's Linux build dependencies, following Godot's "Compiling for Linux/*BSD" documentation (Fedora section), plus `pre-commit`.

**Contract**: `scons --version` and `g++ --version` succeed. `pre-commit` is on PATH.

#### 2. Branch

**File**: git

**Intent**: Do all work on a branch, not `master`. The branch starts from the commit that contains this plan.

**Contract**: branch `refactor/refactor-opportunities`, pushed to `origin` (`Hornster/godot-tests`).

#### 3. Baseline record

**File**: `context/changes/refactor-opportunities/baseline.md` (new)

**Intent**: Record the baseline facts every later phase compares against:
- the local full-suite result (pass/fail count);
- the CI run URL and which jobs are green;
- the first-build duration.

**Contract**: one short Markdown file listing the commit SHA, the local test summary line and the per-job CI status.

### Success Criteria:

#### Automated Verification:

- Local editor dev build with tests completes: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- Full test suite runs and its summary is recorded in `baseline.md`: `$GODOT --test`
- Minimal template build completes locally with the `linux_builds.yml:105-118` flags
- Fork CI run triggered by the branch push completes, and its per-job status is recorded in `baseline.md`: `gh run list -R Hornster/godot-tests -b refactor/refactor-opportunities`

#### Manual Verification:

- Baseline jobs that are red for fork-only reasons (missing secrets, platform runners) are identified and marked as excluded in `baseline.md`

**Implementation Note**: After automated verification passes, pause for human confirmation before Phase 2.

---

## Phase 2: C1 guard: shader-cache characterization tests

### Overview

Pin the observable cache behaviour of all three generated materials (BaseMaterial3D, ParticleProcessMaterial, CanvasItemMaterial) against today's code.

### Changes Required:

#### 1. Characterization tests

**File**: `tests/scene/test_material_shader_cache.cpp` (new)

**Intent**: For each of StandardMaterial3D, ParticleProcessMaterial and CanvasItemMaterial, assert:
- two instances with equal settings share one shader RID;
- different settings yield distinct RIDs;
- changing a setting moves an instance to the other key's RID while a second instance keeps the old one valid;
- after every user of a key is freed, a new instance with that key gets a fresh RID;
- `flush_changes()` applies queued changes;
- no shader compile error is reported.

**Contract**:
- test cases tagged `[SceneTree][Material]`, using `TEST_FORCE_LINK(test_material_shader_cache)`;
- RIDs observed through public `get_shader_rid()` / `get_rid()` (`material.cpp:3179-3183, 3370-3373`; `particle_process_material.cpp:2146-2154`; CIM `get_shader_rid`);
- the `ErrorDetector` from `tests/test_tools.h` is active around each case.

Tests must not reach private members such as the dirty list or the map.

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- New tests pass on unmodified engine code: `$GODOT --test --test-case="*[Material]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Formatting clean: `pre-commit run --files tests/scene/test_material_shader_cache.cpp`

#### Manual Verification:

- Temporarily breaking the refcount (e.g. skipping one `users++` locally, not committed) makes at least one new test fail, which confirms the guard actually guards

**Implementation Note**: Pause for human confirmation before Phase 3.

---

## Phase 3: C1: cache helper + ParticleProcessMaterial migration

### Overview

Introduce the shared cache unit and switch PPM to it, keeping every lock scope where it is.

### Changes Required:

#### 1. Shared cache unit

**File**: `scene/resources/generated_shader_cache.h` (new, header-only)

**Intent**: Hold the `{key → (shader RID, users)}` map and its mutex once, for any material key type. It replaces the per-class `ShaderData` / `shader_map` / `shader_map_mutex` triple.

**Contract**: a class template over the key type, using the key's own hasher as today (`HashMap<K, ShaderData, K>`). It exposes:
- the mutex, for callers' `MutexLock`;
- a non-locking "release one user of key; return whether the shader was freed" primitive;
- a non-locking "find key → RID and add a user" primitive;
- a non-locking "insert-or-adopt" primitive: given a freshly created RID, free it if the key exists, otherwise insert it; either way add a user and return the winning RID.

Callers must hold the mutex for all of these (see Critical Implementation Details). The only RS call inside the primitives is `free_rid`, on last release and on a lost insert race, and both classes already make that call under the lock today. `material_set_shader` and the `shader_rid` reset stay at the call sites, so divergences D-a to D-c in Current State Analysis can be kept per caller.

#### 2. PPM switch

**File**: `scene/resources/particle_process_material.h`, `scene/resources/particle_process_material.cpp`

**Intent**: Replace PPM's `ShaderData`, `shader_map` and `shader_map_mutex` with one static cache instance. Rewrite the three blocks (`:170-190`, `:1360-1381`, `:2842-2855`) to call the primitives within the same lock scopes.

**Contract**: These stay byte-for-byte in behaviour:
- `dirty_materials_mutex`, `flush_changes()` (still updating under the lock), `_queue_shader_change()`;
- eager `material_create()` (`:2759`), `_mark_ready()` (`:162`);
- PPM's side of D-a to D-c: the `shader_rid` reset after `erase`, the unguarded `material_set_shader` before the user count is added, and the whole-destructor lock with `material_set_shader(…, RID())` inside it. Do not normalize these to BaseMaterial3D's shape.

`particle_process_material.h` includes the new header.

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- C1 guard passes: `$GODOT --test --test-case="*[Material]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- No `shader_map_mutex` or `ShaderData` declaration remains in PPM: `grep -nE "shader_map_mutex|struct ShaderData" scene/resources/particle_process_material.h` returns nothing
- Formatting clean: `pre-commit run --files scene/resources/generated_shader_cache.h scene/resources/particle_process_material.h scene/resources/particle_process_material.cpp`

#### Manual Verification:

- Side-by-side review confirms that every `RS::` call in the three rewritten PPM blocks sits in the same lock state (inside/outside `MutexLock`) as before

**Implementation Note**: Pause for human confirmation before Phase 4.

---

## Phase 4: C1: BaseMaterial3D migration

### Overview

Switch BaseMaterial3D to the same cache unit. CIM stays as it is.

### Changes Required:

#### 1. BaseMaterial3D switch

**File**: `scene/resources/material.h`, `scene/resources/material.cpp`

**Intent**: Replace `ShaderData`, `shader_map` and `shader_map_mutex` (`material.h:411-417`, `material.cpp:557-558`) with one static cache instance. Rewrite the three blocks (`:669-695`, `:2088-2113`, `:4042-4056`) to use the primitives within the same lock scopes.

**Contract**: These stay unchanged:
- `material_mutex`, `flush_changes()` (copy under lock, update outside), `_queue_shader_change()`;
- lazy RID creation (`_check_material_rid`, `material_rid_mutex`), the `shader_rid = RID()` reset;
- the `_get_material().is_valid()` guard before `material_set_shader`;
- BaseMaterial3D's side of D-a to D-c: the `shader_rid` reset before `free_rid`, the user count added before the guarded `material_set_shader`, and the scoped destructor lock with `material_set_shader(…, RID())` outside it.

`material.h` includes the new header. `MaterialKey` layout is unchanged (research D14).

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- C1 guard passes, including the untouched CIM cases: `$GODOT --test --test-case="*[Material]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Exactly one `struct ShaderData` remains under `scene/resources/` (CIM's): `grep -rn "struct ShaderData" scene/resources/` lists only `canvas_item_material.h`
- Fork CI on push: no job green in `baseline.md` turns red, including Linux TSan and ASan/UBSan test runs

#### Manual Verification:

- Side-by-side review confirms that every `RS::` call in the three rewritten BaseMaterial3D blocks keeps its lock state
- Open a 3D scene with several StandardMaterial3D variants in the editor built in this phase: materials render, and changing a material feature live updates the viewport

**Implementation Note**: Pause for human confirmation before Phase 5.

---

## Phase 5: C8 guard: 2D-material characterization tests

### Overview

Pin what Sprite3D and Label3D derive for `get_material_for_2d` today, and the alpha-cut mapping table.

### Changes Required:

#### 1. Characterization tests

**File**: `tests/scene/test_material_for_2d.cpp` (new)

**Intent**: Assert three things:
- For each `AlphaCutMode` × `transparent` on/off, plus shaded, double-sided, billboard, no-depth, fixed-size, filter and alpha-antialiasing variations, a Sprite3D's resulting material `Ref` is identical to a direct `StandardMaterial3D::get_material_for_2d(...)` call with the expected arguments. That includes the `ALPHA_CUT_DISABLED` + transparent → `TRANSPARENCY_ALPHA` and not-transparent → `TRANSPARENCY_DISABLED` rows.
- Label3D behaves the same way with its "at least `TRANSPARENCY_ALPHA`" rule.
- No shader compile errors occur.

**Contract**: test cases tagged `[SceneTree][Material2D]`, with `ErrorDetector` active. After one draw/update, the test reads the shader assigned to the node's material RID (Sprite3D: `get_material()`; Label3D: each surface material) through the seam below, and compares it with `r_shader_rid` from a direct `get_material_for_2d` call with the expected arguments. The `get_material_for_2d` cache returns the same `Ref` for equal keys (`material.cpp:3047-3060`).

#### 2. Test seam in the dummy renderer

**File**: `servers/rendering/dummy/storage/material_storage.h`

**Intent**: Nodes keep no public handle to the shader they assign (`sprite_3d.cpp:305-307`, private `last_shader`), and RenderingServer has no `material_get_shader`. Add a read-only accessor next to `owns_material` (`:114`) that returns `DummyMaterial::shader`. It is the only engine change in this phase and changes no behaviour.

**Contract**: `RID material_get_shader(RID p_material) const`, non-virtual, inline in the dummy `MaterialStorage`, returning `RID()` for unknown RIDs. Not part of the RenderingServer API.

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- New tests pass on unmodified code: `$GODOT --test --test-case="*[Material2D]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Formatting clean: `pre-commit run --files tests/scene/test_material_for_2d.cpp servers/rendering/dummy/storage/material_storage.h`

#### Manual Verification:

- Swapping two branches of the Sprite3D alpha-cut mapping locally (not committed) makes a new test fail

**Implementation Note**: Pause for human confirmation before Phase 6.

---

## Phase 6: C8: factory params struct + node migration

### Overview

Make the `get_material_for_2d` parameter list a struct that lives with the factory, add the shared alpha-cut mapping, and have Sprite3D and Label3D build that struct.

### Changes Required:

#### 1. Factory params and mapping

**File**: `scene/resources/material.h`, `scene/resources/material.cpp`

**Intent**: Add a struct with one field per `get_material_for_2d` value parameter, with the same defaults, and an overload that takes it. Add a static mapping from `(transparent, alpha-cut mode as int)` to `Transparency`. The existing positional signature stays, for `root_motion_view.cpp:87`, and forwards to the struct overload so there is one implementation.

**Contract**: The struct, the overload and the mapping are declared in `BaseMaterial3D`, next to the existing `get_material_for_2d` (`material.h:880`, defined at `material.cpp:3047`). Callers spell them `StandardMaterial3D::…` through inheritance, as today's callers already do. `Material2DParams` has 11 fields mirroring `material.h:880`. `static Ref<Material> get_material_for_2d(const Material2DParams &, RID *r_shader_rid = nullptr)`. `static Transparency get_transparency_for_2d(bool p_transparent, int p_alpha_cut_mode)` encodes the mapping currently at `sprite_3d.cpp:289-299`. None of these is bound with `ClassDB`.

#### 2. Sprite3D / AnimatedSprite3D

**File**: `scene/3d/sprite_3d.h`, `scene/3d/sprite_3d.cpp`

**Intent**: `SpriteBase3D` gets a public, unbound C++ accessor returning its `Material2DParams`, built from its draw flags, billboard, filter, alpha AA and the mapping. `texture_repeat` is left at its default. `draw_texture_rect` uses the accessor, sets `texture_repeat` from the UVs as today (`:167`), and calls the struct overload. The inline mapping (`:289-299`) is removed.

**Contract**: `Material2DParams SpriteBase3D::get_material_for_2d_params() const`.

#### 3. Label3D

**File**: `scene/3d/label_3d.h`, `scene/3d/label_3d.cpp`

**Intent**: The same kind of accessor. It builds the mapping with `transparent = true`, which reproduces "at least ALPHA". The glyph path sets `msdf` per glyph, keeps `texture_repeat = false` and calls the struct overload. The inline mapping (`:388-395`) is removed. This lands as its own commit after the Sprite3D commit.

**Contract**: `Material2DParams Label3D::get_material_for_2d_params() const`.

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- C8 guard passes: `$GODOT --test --test-case="*[Material2D]*"`
- C1 guard still passes: `$GODOT --test --test-case="*[Material]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- `mat_transparency` no longer appears in `scene/3d/`: `grep -rn mat_transparency scene/3d/` returns nothing
- Doctool diff is empty (nothing bound): `$GODOT --doctool --headless; git diff --exit-code`
- Formatting clean: `pre-commit run --files scene/resources/material.h scene/resources/material.cpp scene/3d/sprite_3d.h scene/3d/sprite_3d.cpp scene/3d/label_3d.h scene/3d/label_3d.cpp`

#### Manual Verification:

- In the editor: Sprite3D, AnimatedSprite3D and Label3D in each alpha-cut mode look the same as on the Phase 1 baseline build

**Implementation Note**: Pause for human confirmation before Phase 7.

---

## Phase 7: C8: shader baker uses typed node params

### Overview

Replace the baker's hand-copied defaults, by-name property overlay and inline mapping with the nodes' accessors.

### Changes Required:

#### 1. Baker

**File**: `editor/export/shader_baker/shader_baker_export_plugin.cpp`

**Intent**: For a `Sprite3D` node, take `get_material_for_2d_params()`. For a `Label3D` node, take its accessor and generate the msdf-off and msdf-on variants as today. Delete the 9-entry default table (`:313-321`), the property overlay loop (`:323-331`), the inline mapping (`:333-346`) and the two "must match" comments.

**Contract**: The node detection stays `cast_to<Label3D>` / `cast_to<Sprite3D>` (`:306-307`), so AnimatedSprite3D is still not handled. `texture_repeat` stays `false` in every baked variant. The set of `_customize_resource` calls per node (sprite variant for both kinds, plus the msdf variant for Label3D) is unchanged.

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- C8 and C1 guards pass: `$GODOT --test --test-case="*[Material2D]*"` and `$GODOT --test --test-case="*[Material]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- No by-name lookups remain in the baker: `grep -n 'properties\["' editor/export/shader_baker/shader_baker_export_plugin.cpp` returns nothing
- Formatting clean: `pre-commit run --files editor/export/shader_baker/shader_baker_export_plugin.cpp`
- Fork CI on push: no job green in `baseline.md` turns red

#### Manual Verification:

- Export a test project containing a Sprite3D (non-default alpha cut and billboard) and a Label3D, with the shader baker enabled, from the Phase 1 baseline build and from this build. The number of baked shader variants is the same.

**Implementation Note**: Pause for human confirmation before Phase 8.

---

## Phase 8: C10 guard: NavigationServer3D debug-cluster characterization tests

### Overview

Pin the server's current debug draw behaviour, which the owner must reproduce in Phases 10–12.

### Changes Required:

#### 1. Characterization tests

**File**: `tests/scene/test_navigation_debug_3d.cpp` (new; all cases inside `#ifdef DEBUG_ENABLED`)

**Intent**: Through the current NavigationServer3D API, assert:
- **Settings.** All 27 `debug/shapes/{navigation,avoidance}/3d/*` project settings exist with their current defaults, and each color/toggle getter returns its setting's default.
- **Materials.** Each of the 15 material getters returns the same `Ref` on repeated calls, with its current shading, transparency, albedo (from its color), cull, flags and `FLAG_DISABLE_DEPTH_TEST` (from its xray toggle, where it has one).
- **Material patching.** Setting a color or xray toggle after a material exists patches that material in place, with the same `Ref`. The point size patches the point material.
- **Signal sequencing.** After `MessageQueue` flushes, these fire exactly once:
  - `navigation_debug_changed` after each navigation toggle setter;
  - `avoidance_debug_changed` after each avoidance toggle setter;
  - and color setters fire neither.

  `set_debug_navigation_enable_agent_paths` follows today's sequencing (see the Critical Implementation Details table). Pin three counts:
  - 1 on a fresh server before any flush;
  - 0 when called alone after a flushed navigation toggle has used up the initial dirty flag;
  - 1 in total when called together with a navigation toggle before one flush.

  These counts describe what the current code does, not what it "should" do.

**Contract**: test cases tagged `[SceneTree][Navigation3D][NavigationDebug]`, using `tests/signal_watcher.h` and `MessageQueue::get_singleton()->flush()`. Assertions go through a small local accessor so that Phase 10 can retarget the same cases to the owner without rewriting them. Each case restores every color, toggle and point size it mutates before it ends, so no case relies on the per-case server re-creation in `tests/test_main.cpp:227, 266` (see Critical Implementation Details, C10 lifecycle).

### Success Criteria:

#### Automated Verification:

- Build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- New tests pass on unmodified code: `$GODOT --test --test-case="*[NavigationDebug]*"`
- Existing navigation tests still pass: `$GODOT --test --test-case="*[Navigation3D]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Formatting clean: `pre-commit run --files tests/scene/test_navigation_debug_3d.cpp`

#### Manual Verification:

- The reviewer confirms that the pinned `enable_agent_paths` emission count matches the code reading in Critical Implementation Details

**Implementation Note**: Pause for human confirmation before Phase 9.

---

## Phase 9: C10: forward-declare cut of the material.h include

### Overview

Compile-only: the server header stops including `scene/resources/material.h`.

### Changes Required:

#### 1. Server header and source

**File**: `servers/navigation_3d/navigation_server_3d.h`, `servers/navigation_3d/navigation_server_3d.cpp`

**Intent**: Replace `#include "scene/resources/material.h"` (`:36`) with a `class StandardMaterial3D;` forward declaration, following the precedent in `navigation_agent_3d.h:40`. Include `material.h` in the `.cpp`, in its existing `scene/` include group (`:38-40`).

**Contract**: `Ref<StandardMaterial3D>` members and getters compile with the forward declaration. The constructor and destructor are already out of line (`:248, :355`).

#### 2. Translation units that relied on the transitive include

**File**: whichever of the 11 candidate TUs fail to build (research V31: `csg_shape.cpp`, `grid_map.cpp`, 3 navigation editor plugins, `mesh_instance_3d.cpp`, 4 `scene/3d/navigation/*.cpp`, `navigation_mesh.cpp`)

**Intent**: Add an explicit `#include "scene/resources/material.h"` only where the build breaks.

**Contract**: The include is added, nothing else changes. The list of touched TUs is recorded in the commit message.

### Success Criteria:

#### Automated Verification:

- Editor build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- Minimal template (`disable_3d=yes`) builds with the `linux_builds.yml:105-118` flags
- The header has no `scene/` include: `grep -n '#include "scene/' servers/navigation_3d/navigation_server_3d.h` returns nothing
- C10 guard and navigation tests pass: `$GODOT --test --test-case="*[Navigation3D]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Formatting clean: `pre-commit run --files <touched files>`

**Implementation Note**: Pause for human confirmation before Phase 10.

---

## Phase 10: C10: NavigationDebug3D owner, delegating to the server

### Overview

Introduce the scene-side owner as a pure facade over today's server API.

### Changes Required:

#### 1. Owner

**File**: `scene/3d/navigation/navigation_debug_3d.h`, `scene/3d/navigation/navigation_debug_3d.cpp` (new)

**Intent**: An unbound C++ singleton that exposes the full draw-config surface (14 colors, 12 toggles, point size and 15 material getters, with the same names minus the server prefix where that reads better). For now every method forwards to `NavigationServer3D::get_singleton()`.

**Contract**:
- `class NavigationDebug3D` with `static NavigationDebug3D *get_singleton()`;
- the whole class compiled only under `DEBUG_ENABLED` and `!NAVIGATION_3D_DISABLED`;
- it never caches the server pointer;
- not registered with `ClassDB`.

#### 2. Registration

**File**: `scene/register_scene_types.cpp`

**Intent**: Create the singleton in `register_scene_types()` and delete it in `unregister_scene_types()`, inside the existing `NAVIGATION_3D_DISABLED` guards (`:292-298`, `:787`).

**Contract**: The lifetime lies strictly within the server's lifetime (`main.cpp:781→787`, `:870→890`).

#### 3. Guard retarget

**File**: `tests/scene/test_navigation_debug_3d.cpp`

**Intent**: Run the Phase 8 cases against both the server and the owner through the local accessor.

**Contract**: Same assertions, two targets.

### Success Criteria:

#### Automated Verification:

- Editor build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- Minimal template (`disable_3d=yes`) builds with the `linux_builds.yml:105-118` flags
- Debug no-3D template builds: `scons platform=linuxbsd target=template_debug disable_3d=yes -j8`
- C10 guard passes for both targets: `$GODOT --test --test-case="*[NavigationDebug]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Doctool diff is empty: `$GODOT --doctool --headless; git diff --exit-code`
- Formatting clean: `pre-commit run --files scene/3d/navigation/navigation_debug_3d.h scene/3d/navigation/navigation_debug_3d.cpp scene/register_scene_types.cpp tests/scene/test_navigation_debug_3d.cpp`

**Implementation Note**: Pause for human confirmation before Phase 11.

---

## Phase 11: C10: migrate callers to the owner

### Overview

Every draw-config call site switches from NavigationServer3D to NavigationDebug3D. Calls to the server's enabled flags (`set/get_debug_enabled`, `set/get_debug_navigation_enabled`, `set/get_debug_avoidance_enabled`) stay on the server.

### Changes Required:

#### 1. Scene nodes and resources (commit 1)

**File**: `scene/3d/navigation/navigation_region_3d.cpp`, `navigation_link_3d.cpp`, `navigation_agent_3d.cpp`, `navigation_obstacle_3d.cpp`, `scene/resources/navigation_mesh.cpp`

**Intent**: Draw-config calls go through `NavigationDebug3D::get_singleton()`. Signal connections to `navigation_debug_changed` / `avoidance_debug_changed` stay on the server.

**Contract**: These files include `scene/3d/navigation/navigation_debug_3d.h`. Logic is unchanged. `scene/resources/navigation_mesh.cpp` is built even with `disable_3d=yes` (`scene/resources/SCsub` only gates `3d/`), so its include and its `NavigationDebug3D` calls inside the `DEBUG_ENABLED` block (`:390-483`) are additionally wrapped in `#ifndef NAVIGATION_3D_DISABLED`. This is behaviour-neutral, since those builds never create the 3D server (`main.cpp:780-782`).

#### 2. Modules (commit 2)

**File**: `modules/gridmap/grid_map.cpp`, `modules/navigation_3d/editor/navigation_region_3d_gizmo_plugin.cpp`, `navigation_link_3d_gizmo_plugin.cpp`, `navigation_obstacle_3d_editor_plugin.cpp`

**Intent**: Same switch. GridMap's server signal connection (`:1915, :2121`) is unchanged.

**Contract**: Same.

#### 3. Editor settings sync (commit 3)

**File**: `editor/editor_node.cpp`

**Intent**: The `NavigationServer3D` color/toggle setters fed from `GLOBAL_GET` (`:625-634`) call the owner instead. The NavigationServer2D block stays untouched.

**Contract**: Same.

### Success Criteria:

#### Automated Verification:

- Editor build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- Minimal template (`disable_3d=yes`) builds with the `linux_builds.yml:105-118` flags
- Debug no-3D template builds: `scons platform=linuxbsd target=template_debug disable_3d=yes -j8`
- No draw-config call to the server remains outside `servers/` and `tests/`: `grep -rnE "NavigationServer3D::get_singleton\(\)->(set|get)_debug_navigation_(edge|geometry|link|agent|avoidance|enable_)" --include=*.cpp . | grep -vE "^./(servers|tests)/"` returns nothing. `enable_` keeps the server's `set/get_debug_navigation_enabled` out of the match; on today's code the command returns 48 lines and 0 of them are enabled-flag calls. `ns3d->` aliases must be checked the same way, with the enabled-flag methods excluded.
- C10 guard and navigation tests pass: `$GODOT --test --test-case="*[Navigation3D]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Formatting clean: `pre-commit run --files <touched files>`

#### Manual Verification:

- In the editor with "Visible Navigation" on, a NavigationRegion3D, a NavigationLink3D, a NavigationObstacle3D and a GridMap with navigation show the same debug colors as the baseline build. Changing `debug/shapes/navigation/3d/geometry_face_color` in Project Settings updates the region's face color.

**Implementation Note**: Pause for human confirmation before Phase 12.

---

## Phase 12: C10: move state, settings and materials into the owner

### Overview

The owner stops delegating and becomes the single holder of 3D navigation draw configuration. The server's draw API is deleted.

### Changes Required:

#### 1. Owner takes the state

**File**: `scene/3d/navigation/navigation_debug_3d.h`, `scene/3d/navigation/navigation_debug_3d.cpp`

**Intent**: Move these out of the server and into the owner:
- the 14 colors, 12 toggles and point size, with defaults;
- the `member = GLOBAL_DEF(...)` registration and seeding of the 27 settings (`:314-343`), moved into the owner's constructor. The deprecated `MOVE_PROJECT_SETTING_*` block (`:261-312`) stays in the server constructor, because NavigationServer2D depends on it running first (see Critical Implementation Details, C10 lifecycle);
- the 15 lazy material builders;
- the per-setter material patching.

Toggle setters reproduce today's signal semantics through the server hook.

**Contract**: The four setter semantics in Critical Implementation Details hold exactly. Setting names, defaults and hints (e.g. the `agent_path_point_size` range hint) are identical.

#### 2. Server sheds the draw config

**File**: `servers/navigation_3d/navigation_server_3d.h`, `servers/navigation_3d/navigation_server_3d.cpp`

**Intent**: Delete the moved members, setters, getters, material builders and settings registration. Keep:
- `debug_enabled`, `debug_navigation_enabled`, `debug_avoidance_enabled` and their dirty flags, the deferred emit functions, and the bound signals;
- the editor-hint auto-enable in the constructor;
- the deprecated `MOVE_PROJECT_SETTING_*` migration block in the constructor, unchanged.

Add the unbound notify hook. Remove the `class StandardMaterial3D;` forward declaration and the `.cpp` `material.h` include, since they are no longer used.

**Contract**: The hook takes two forms, both unbound public C++:
- "queue navigation-debug-changed, marking dirty or not";
- "queue avoidance-debug-changed".

`_bind_methods` is unchanged.

#### 3. Guard retarget

**File**: `tests/scene/test_navigation_debug_3d.cpp`

**Intent**: Drop the server target, since its draw API is gone, and keep every assertion against the owner.

**Contract**: The assertion set is the same as in Phase 8.

### Success Criteria:

#### Automated Verification:

- Editor build succeeds: `scons platform=linuxbsd target=editor dev_build=yes tests=yes -j8`
- Minimal template (`disable_3d=yes`) builds with the `linux_builds.yml:105-118` flags
- Debug no-3D template builds: `scons platform=linuxbsd target=template_debug disable_3d=yes -j8`
- The server holds no material or color state: `grep -nE "StandardMaterial3D|Color debug_" servers/navigation_3d/navigation_server_3d.h` returns nothing
- C10 guard passes against the owner: `$GODOT --test --test-case="*[NavigationDebug]*"`
- Full suite shows no new failures against `baseline.md`: `$GODOT --test`
- Doctool diff is empty, including `doc/classes/ProjectSettings.xml` and `NavigationServer3D.xml`: `$GODOT --doctool --headless; git diff --exit-code`
- GDExtension API unchanged: `./misc/scripts/validate_extension_api.sh bin/godot.linuxbsd.editor.dev.x86_64`
- Formatting clean: `pre-commit run --files <touched files>`
- Fork CI on push: no job green in `baseline.md` turns red

#### Manual Verification:

- Project Settings → Debug → Shapes → Navigation/Avoidance 3D lists the same settings in the same order with the same defaults as the baseline build
- Running a project with `--debug-navigation --debug-avoidance` shows navigation meshes, links, agent paths and avoidance radii exactly as on the baseline build
- A project.godot with the deprecated pre-split `debug/shapes/navigation/*` keys still migrates to both the `2d/` and `3d/` keys on load (non-`deprecated=no` build), and a NavigationRegion2D shows the migrated 2D color in that same session

**Implementation Note**: Pause for final human confirmation. The change is then ready for `/10x-impl-review`.

---

## Testing Strategy

### Unit Tests:

- `tests/scene/test_material_shader_cache.cpp`: RID sharing, separation, key moves, release and flush for the three generated materials. CIM is pinned only.
- `tests/scene/test_material_for_2d.cpp`: the full alpha-cut × transparent table, plus flag variations, for Sprite3D and Label3D.
- `tests/scene/test_navigation_debug_3d.cpp`: settings and defaults, material properties and identity, in-place patching, signal sequencing (including the `enable_agent_paths` quirk).

All three run under `ErrorDetector` where shader compilation is involved. In CI they also run under ASan/UBSan and TSan at no extra cost (`linux_builds.yml:240-244`).

### Integration Tests:

- Minimal `disable_3d` template build after every C10 phase, plus a `template_debug disable_3d=yes` build after Phases 10–12.
- Doctool and GDExtension API checks after C8 and C10.

### Manual Testing Steps:

1. Phase 4: live material feature edits update the viewport.
2. Phase 6: Sprite3D, AnimatedSprite3D and Label3D look unchanged in every alpha-cut mode.
3. Phase 7: the shader baker exports the same variant count.
4. Phases 11–12: navigation debug visuals and Project Settings are unchanged, and the deprecated settings still migrate.

## Performance Considerations

- C1 adds no lock and no allocation, and the cache primitives sit within the existing critical sections. Touching `material.h` (Phases 4 and 6) only recompiles its 150 two-hop includers.
- C10 adds one singleton lookup per debug draw-config call, which only happens in `DEBUG_ENABLED` builds.

## Migration Notes

- No saved-file, API or project-setting changes.
- Each phase is one or more commits that can be reverted on their own. Revert order within a refactor is the reverse of phase order. Phase 9's include cut stands alone even if Phases 10–12 are reverted.

## References

- Research (ranking, evidence, ast-grep verification): `context/changes/refactor-opportunities/research.md`
- User decision on ranking and order: `RefactoringUserNotes.txt`
- Source analysis: `context/changes/material-resources-flow-analysis/research.md`
- Shared-code precedent between renderer twins: `servers/rendering/storage/mesh_storage.cpp:36`
- Forward-declaration precedent: `scene/3d/navigation/navigation_agent_3d.h:40, 118-119`
- Test harness setup: `tests/test_main.cpp:182-270`. Test precedent: `tests/scene/test_sprite_2d.cpp`.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Verification baseline

#### Automated

- [ ] 1.1 Local editor dev build with tests completes
- [ ] 1.2 Full test suite runs and its summary is recorded in baseline.md
- [ ] 1.3 Minimal template build completes locally
- [ ] 1.4 Fork CI run completes and per-job status is recorded in baseline.md

#### Manual

- [ ] 1.5 Fork-only red baseline jobs identified and marked excluded

### Phase 2: C1 guard: shader-cache characterization tests

#### Automated

- [ ] 2.1 Build succeeds
- [ ] 2.2 New tests pass on unmodified engine code
- [ ] 2.3 Full suite shows no new failures against baseline
- [ ] 2.4 Formatting clean

#### Manual

- [ ] 2.5 Deliberate refcount break makes a new test fail

### Phase 3: C1: cache helper + ParticleProcessMaterial migration

#### Automated

- [ ] 3.1 Build succeeds
- [ ] 3.2 C1 guard passes
- [ ] 3.3 Full suite shows no new failures against baseline
- [ ] 3.4 No shader_map_mutex or ShaderData declaration remains in PPM
- [ ] 3.5 Formatting clean

#### Manual

- [ ] 3.6 RS calls in rewritten PPM blocks keep their lock state

### Phase 4: C1: BaseMaterial3D migration

#### Automated

- [ ] 4.1 Build succeeds
- [ ] 4.2 C1 guard passes including untouched CIM cases
- [ ] 4.3 Full suite shows no new failures against baseline
- [ ] 4.4 Only CIM's struct ShaderData remains under scene/resources
- [ ] 4.5 Fork CI shows no baseline-green job turning red

#### Manual

- [ ] 4.6 RS calls in rewritten BaseMaterial3D blocks keep their lock state
- [ ] 4.7 Live material feature edits update the editor viewport

### Phase 5: C8 guard: 2D-material characterization tests

#### Automated

- [ ] 5.1 Build succeeds
- [ ] 5.2 New tests pass on unmodified code
- [ ] 5.3 Full suite shows no new failures against baseline
- [ ] 5.4 Formatting clean

#### Manual

- [ ] 5.5 Deliberate mapping swap makes a new test fail

### Phase 6: C8: factory params struct + node migration

#### Automated

- [ ] 6.1 Build succeeds
- [ ] 6.2 C8 guard passes
- [ ] 6.3 C1 guard still passes
- [ ] 6.4 Full suite shows no new failures against baseline
- [ ] 6.5 mat_transparency no longer appears in scene/3d
- [ ] 6.6 Doctool diff is empty
- [ ] 6.7 Formatting clean

#### Manual

- [ ] 6.8 Sprite3D, AnimatedSprite3D and Label3D look unchanged in every alpha-cut mode

### Phase 7: C8: shader baker uses typed node params

#### Automated

- [ ] 7.1 Build succeeds
- [ ] 7.2 C8 and C1 guards pass
- [ ] 7.3 Full suite shows no new failures against baseline
- [ ] 7.4 No by-name property lookups remain in the baker
- [ ] 7.5 Formatting clean
- [ ] 7.6 Fork CI shows no baseline-green job turning red

#### Manual

- [ ] 7.7 Shader-baker export yields the same baked variant count as baseline

### Phase 8: C10 guard: NavigationServer3D debug-cluster characterization tests

#### Automated

- [ ] 8.1 Build succeeds
- [ ] 8.2 New tests pass on unmodified code
- [ ] 8.3 Existing navigation tests still pass
- [ ] 8.4 Full suite shows no new failures against baseline
- [ ] 8.5 Formatting clean

#### Manual

- [ ] 8.6 Pinned enable_agent_paths emission count matches the code reading

### Phase 9: C10: forward-declare cut of the material.h include

#### Automated

- [ ] 9.1 Editor build succeeds
- [ ] 9.2 Minimal disable_3d template builds
- [ ] 9.3 Server header has no scene include
- [ ] 9.4 C10 guard and navigation tests pass
- [ ] 9.5 Full suite shows no new failures against baseline
- [ ] 9.6 Formatting clean

### Phase 10: C10: NavigationDebug3D owner, delegating to the server

#### Automated

- [ ] 10.1 Editor build succeeds
- [ ] 10.2 Minimal disable_3d template builds
- [ ] 10.3 Debug no-3D template builds
- [ ] 10.4 C10 guard passes for both server and owner
- [ ] 10.5 Full suite shows no new failures against baseline
- [ ] 10.6 Doctool diff is empty
- [ ] 10.7 Formatting clean

### Phase 11: C10: migrate callers to the owner

#### Automated

- [ ] 11.1 Editor build succeeds
- [ ] 11.2 Minimal disable_3d template builds
- [ ] 11.3 Debug no-3D template builds
- [ ] 11.4 No server draw-config call remains outside servers and tests
- [ ] 11.5 C10 guard and navigation tests pass
- [ ] 11.6 Full suite shows no new failures against baseline
- [ ] 11.7 Formatting clean

#### Manual

- [ ] 11.8 Editor navigation debug visuals and live color setting match baseline

### Phase 12: C10: move state, settings and materials into the owner

#### Automated

- [ ] 12.1 Editor build succeeds
- [ ] 12.2 Minimal disable_3d template builds
- [ ] 12.3 Debug no-3D template builds
- [ ] 12.4 Server holds no material or color state
- [ ] 12.5 C10 guard passes against the owner
- [ ] 12.6 Full suite shows no new failures against baseline
- [ ] 12.7 Doctool diff is empty
- [ ] 12.8 GDExtension API unchanged
- [ ] 12.9 Formatting clean
- [ ] 12.10 Fork CI shows no baseline-green job turning red

#### Manual

- [ ] 12.11 Project Settings navigation/avoidance 3D entries unchanged in order and defaults
- [ ] 12.12 Runtime debug-navigation and debug-avoidance visuals match baseline
- [ ] 12.13 Deprecated pre-split navigation settings still migrate on load
