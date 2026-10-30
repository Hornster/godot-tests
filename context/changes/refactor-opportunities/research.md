---
date: 2026-10-30T11:16:45+01:00
researcher: Claude (Opus 5.5) for Hornster
git_commit: 5ed1824a23c40298fe01da8dde2cb89ae7e2fe38
branch: master
repository: godot-tests (Godot Engine fork, origin github.com/Hornster/godot-tests)
topic: "Refactor opportunities from the material resources flow analysis: which recorded problems are structural, why they have their shape, and what an incremental path would cost"
tags: [research, refactor, ranking, scene-resources, material, particle-process-material, canvas-item-material, material-storage, shader-baker, navigation-server, characterization-tests]
status: complete
last_updated: 2026-10-30
last_updated_by: Claude (Opus 5.5) for Hornster
---

# Research: Refactor opportunities from the material resources flow analysis

**Date**: 2026-10-30T11:16:45+01:00
**Researcher**: Claude (Opus 5.5) for Hornster
**Git Commit**: `5ed1824a23`. Engine source is byte-identical to `0f30f7d853`, the commit the source analysis was written at: `git diff --stat 0f30f7d853 HEAD` touches only `.claude/`, `ast-grep/`, `node_modules/`, `package*.json`, `CLAUDE.md` and `context/`. So every line anchor in the source analysis still holds.
**Branch**: master
**Repository**: godot-tests (Godot Engine)

**Legend**:
- **[E]** evidence: observed at the cited `file:line`, or in git/GitHub output.
- **[I]** inference drawn from evidence.
- **[?]** unknown: not established. This is not a claim of absence.

## Research Question

The source is `context/changes/material-resources-flow-analysis/research.md`; the user's prompt wrote it as `material-resource-flow-analysis`, but the folder that exists is `material-resources-flow-analysis`. Its priors are `context/map/repo-map.md` and the `artifact-*` files it cites.

1. List every problem the source records, under any label: debt, risk, hotspot or finding.
2. Classify each one. A **candidate** is a problem whose fix would change code structure. Everything else is input for judging feasibility and cost.
3. For each candidate, establish three things:
   - its current shape;
   - its history and intentionality;
   - its migration feasibility.
4. Close with a ranking of 2–3 refactor opportunities plus the candidates rejected.

This research ranks only. It decides nothing and changes no code.

---

## 0. Problem inventory and classification (for audit)

IDs `D1`–`D14` are the source's own Technical Debt rows (source §2). `F*` are findings recorded elsewhere in the source (§1.4–§1.6, §3, Open Questions) that have no D number.

### 0.1 Candidates (fixing them would change code structure)

| Cand. | Source problem(s) | Why it is structural |
|---|---|---|
| **C1** | D1: three copies of the "generated shader, global `shader_map`, static dirty list, idle flush" pattern, with differing lock and init semantics | The fix moves duplicated machinery into a shared unit. |
| **C2** | D2: generated-shader render-mode string contract. F1: generated uniform names are copied by the conversion plugins (`material_editor_plugin.cpp:66-76, 571-582`; `material_3d_conversion_plugins.cpp:55-65, 88-98`) | It might be fixed by a shared mode registry. After research it **turns out not to be a refactor**; see §1.C2. |
| **C3** | D3: two hand-kept renderer material storages (RD and GLES3) | The fix moves shared bookkeeping into a common base or helper. |
| **C4** | D4, structural part only: per-class ad-hoc legacy remaps in `_set`, with a duplicate and a self-map entry | The fix moves the remaps into a data table or compat unit. |
| **C5** | D5: default-skip serialization makes a default change a silent migration | It would change the persistence mechanism. After research it is **a format-contract question, so stopped**. |
| **C6** | D6: `_validate_property` mixes "hide in the editor" with "don't store" | The fix separates two responsibilities in one function. |
| **C7** | D9: CPUParticles ↔ ParticleProcessMaterial hand parity | It might be fixed by a shared parameter model. After research it is **a domain question, so stopped**. |
| **C8** | D10: the shader baker hand-copies Sprite3D/Label3D logic | The fix extracts one shared function. |
| **C9** | D12: string-keyed coupling in the editor plugins. F2: the `"BaseMaterial3D,ShaderMaterial"` hint string, repeated 11× in 5 files | The fix introduces named constants and a shared parser. |
| **C10** | D13: backward include `servers/navigation_3d/navigation_server_3d.h:36` → `scene/resources/material.h` | The fix changes the include graph and possibly ownership of the debug materials. |

### 0.2 Not candidates (kept as feasibility and cost input)

| Source problem | Classification | How it is used here |
|---|---|---|
| D7: the dummy RS makes the value channel unobservable | Test infrastructure | It limits which guards are possible (§2). |
| D8: test holes on the whole path | Missing tests | It is the prerequisite cost of every candidate. |
| D11: value edits don't emit `changed` | **Behaviour.** Adding emission changes observable signals. | Out of scope for a refactor. |
| D14: MaterialKey bit budget (7 flag bits left) | Latent capacity limit with no current defect | Input to C1: a shared cache must not fix the key layout. |
| D3 drift items: RD locks `shader->mutex`, GLES3 range-checks priority | Behaviour. Aligning them changes behaviour. | Input to C3. History shows the lock difference is justified (§1.C3). |
| D4 behaviour items: an unknown legacy name returns `true`; ShaderMaterial `_set` requires a valid shader | Behaviour | Input to C4. |
| D10 behaviour items: the baker never pre-bakes `texture_repeat` variants and skips AnimatedSprite3D [I] | Behaviour | Input to C8. They are a separate change. |
| D12 behaviour item: the undo hook excludes ORMMaterial3D | Behaviour, and likely moot [I] | Input to C9. |
| F3: `modules/visual_shader/tests/test_visual_shader.cpp` is never compiled | Build/test gap | Guard input. |
| F4: `ErrorDetector` is opt-in | Test infrastructure | It decides whether a compile-matrix guard can fail (§2). |
| F5: no material `*.compat.inc` exists | Observation, not a defect | Input to C4. |
| F6: overlay and surface overrides connect no signal (`visual_instance_3d.cpp:240`, `mesh_instance_3d.cpp:381`) | Behaviour | Not used. |
| F7: the source's Open Questions and unknowns | Unknowns | Carried in §5 where still open. |

**Reclassification after research:** C2, C5 and C7 stay listed as candidates for auditability. The evidence shows, though, that their adequate fix is a guard (C2) or a domain/format decision (C5, C7), not a structural refactor. See §4.

---

## Summary

- **Ranked opportunities** (§3):
  1. **C1**: extract the shared refcounted shader cache used by BaseMaterial3D and ParticleProcessMaterial.
  2. **C8**: extract one "2D-material parameters from node" helper used by Sprite3D, Label3D and the shader baker.
  3. **C10**: cut the `navigation_server_3d.h → material.h` include.

  All three have these properties:
  - **Accidental complexity, or an accidental side effect.** History shows no decision that would carry the current shape (§1).
  - **Behaviour can be pinned before the change.** The current test harness can do it, or for C10 the CI compile matrix can.
  - **Reversible in small commits.**
- **Largest debt, not ranked: C3, the RD/GLES3 storage twins.** Beyond the material API, the global shader uniform API is a near-copy. The RD section is 619 lines and the GLES3 one 620, and `diff` reports 37 changed lines [E] (`renderer_rd/storage_rd/material_storage.cpp:1574-2192` vs `drivers/gles3/storage/material_storage.cpp:1626-2245`). No characterization test can run either backend in the harness. Its only runtime guard is a CI smoke import/run that fails on crashes, sanitizer reports and leaks, not on rendering (§1.C3). The hard rule "guard first" cannot be met cheaply, so it stays out of the top 3.
- **Stopped as non-structural:**
  - **C5** default-skip: a file-format contract. The skip is deliberate since f2e54057ae (2018), and maintainers enforce "don't change defaults" case by case.
  - **C7** CPUParticles parity: a deliberate product decision. clayjohn on #79527: "We aren't porting all GPUParticles features over the CPUParticles anymore".
  - **C2**, backend half: a deliberate per-renderer design. Its scene half needs a guard test, not a refactor.
- **A harness fact that lowers every guard's cost** [E]: the dummy RS really compiles the shader code it receives, for the shader modes it supports. Dummy `shader_set_code` runs `ShaderCompiler::compile` (`servers/rendering/dummy/storage/material_storage.cpp:191`) against the real `ShaderTypes`, which is registered in the test binary (`servers/register_server_types.cpp:159` via `main/main.cpp:755`). It reports failures through `ERR_FAIL_COND_MSG` (`:192`), so a test sees them only with `ErrorDetector`. The source's "dummy RS is an untestable seam" (D7) is therefore partly superseded: the **shader-key channel** is testable, while the **value channel** still is not.
- **New evidence beyond the source:**
  - CanvasItemMaterial touches its static `shader_map` without a lock in `_update_shader` (`canvas_item_material.cpp:58-80`) and in `get_shader_rid` (`:235-237`), and has no separate map mutex (`canvas_item_material.h:99`) [E]. A race on the deferred load path is [I].
  - The baker's missing `texture_repeat` is a dated drift [E]:
    - The baker (#102552) merged 2025-05-28 (`de37627404`).
    - `p_texture_repeat` (#98122) merged later, on 2025-12-02 (`44bc2da147`). It touched `label_3d.cpp`, `sprite_3d.cpp`, `material.cpp` and `material.h` only (`git show --stat fc9ea462ca`).

---

## 1. Per-candidate findings

### C1: three copies of the generated-shader cache, dirty list and idle flush

**Current shape**
- Identical across all three classes [E]:
  - `struct ShaderData { RID shader; int users = 0; }` (`material.h:411`, `particle_process_material.h:153`, `canvas_item_material.h:81`).
  - The `_queue_shader_change` body (`material.cpp:2149-2158`, `particle_process_material.cpp:1395-1405`, `canvas_item_material.cpp:152-162`).
  - `finish_shaders`: clear the list, `memdelete(shader_names)`.
- Shared only by BaseMaterial3D and PPM [E]: `hash_djb2_buffer`/`memcmp` key ops, and shader creation **outside** the map lock with race resolution (`material.cpp:2088-2113`; `particle_process_material.cpp:1360-1381`).
- Different in each [E]:
  - **Keys.** BaseMaterial3D uses a ~20-field bitfield plus two `uint32_t` masks (`material.h:359-409`). PPM uses a bitfield struct kept ≤ 64 bits (`particle_process_material.h:114-151`). CIM uses a `union` with `uint32_t key` and a murmur3 hash (`canvas_item_material.h:53-70`).
  - **Flush.** BaseMaterial3D copies the list under the lock and updates outside it (`material.cpp:2134-2147`). PPM (`:1386-1393`) and CIM (`canvas_item_material.cpp:143-150`) update while holding the lock.
  - **Mutexes.** BaseMaterial3D has `shader_map_mutex` (`material.h:417`) plus `material_mutex` (`:524`). PPM has `shader_map_mutex` (`:158`) plus `dirty_materials_mutex` (`:204`). CIM has a single `material_mutex` (`:99`).
  - **Create path.** CIM uses `shader_create()` + `shader_set_code`, `users = 1`, with no race handling.
  - **Init.** Only CIM calls `_mark_initialized` (`canvas_item_material.cpp:292`). BaseMaterial3D and PPM self-promote with `_mark_ready()` inside `_update_shader` (`material.cpp:661`, `particle_process_material.cpp:162`; the definition is at `material.cpp:100`).
  - **RID creation.** CIM and PPM create their RID eagerly (`canvas_item_material.cpp:284`, `particle_process_material.cpp:2759`). BaseMaterial3D creates it lazily (`material.cpp:3179-3183`).
- New [E]: CIM `_update_shader` (`canvas_item_material.cpp:58-80`) and `get_shader_rid` (`:235-237`) read and write `shader_map` with no lock. When it runs from the deferred `_mark_initialized` path (`material.cpp:113-115`) it is outside the flush lock. [I]: a possible race. This is a **bug fix**, separate from the refactor.
- Other materials (Fog, sky, Blit) use a different, simpler static-RID/`shader_cache[]` scheme with no dirty list (`fog_material.h:50-52`, `sky_material.h:57-58, 131-132, 168-169`) [E]. They are not part of this candidate.
- Existing seams [E]: only `Material::init_state` / `_mark_ready` / `_mark_initialized` (`material.h:47-65`, `material.cpp:100-124`), plus the primitives `SelfList<T>::List` and `SceneTree::add_idle_callback` (`register_scene_types.cpp:807, 894, 927`). There is **no** shared cache abstraction.

**History and intentionality**
- Each copy was written as its class appeared [E]:
  - SpatialMaterial in 53d8f2b1ec (2016-10-27, reduz);
  - ParticlesMaterial in 74808ac4d9 (2017-04-06);
  - CanvasItemMaterial in 8ef1c41a4e (2017-06-23).

  No commit message discusses sharing the machinery.
- #91630 (2024-05, RandomShaper) changed all three together, "to make it more consistent across material types" [E]. So consistency was an intention as recently as 2024.
- The divergence comes from later, narrowly scoped fixes [E]:
  - #90400 (e2c6daf7ef, ubershaders) reworked BaseMaterial3D's lazy RID. CIM and PPM got a one-line eager `material_create()` each.
  - #99716 (34a19f07a4) restored the dirty list for BaseMaterial3D only: "a bit of a hacky solution … we don't have a much better way to do it for architectural reasons".
  - #105138 (09282c316a, deadlock #102877) reduced the lock scope in `material.cpp` and RD files only. That is verified with `git show --stat 09282c316a`: it touches `material.cpp`, `scene_shader_forward_clustered.cpp`, `shader_rd.*`, `storage_rd/material_storage.cpp` and `worker_thread_pool.cpp`; it does not touch `particle_process_material.cpp` or `canvas_item_material.cpp`.
- **Verdict: accidental complexity.** Copy-paste origin, divergence through fixes scoped to the bug at hand. No PR states that PPM or CIM were exempted on purpose [?].

**Feasibility**
- Reuse vs new: **new** abstraction, a shared refcounted shader cache (map, `users`, race-safe create). Each class must keep its own lock and init policy. Unifying those policies is a behaviour change.
- Blast radius:
  - A helper header included from the three `.cpp` files leaves `material.h` untouched [I].
  - Touching `material.h` recompiles 37 direct includers, 150 files within two hops (source §1.6).
  - Co-change: `material.cpp` co-changes with renderer files, not with the PPM or CIM files (source §1.6).
- Guards: none today. A characterization test is **feasible in part** [E]:
  - `get_shader_rid()` / `get_rid()` run `_update_shader()` synchronously (`material.cpp:3179-3183, 3370-3373`; `particle_process_material.cpp:2146-2154`).
  - All three `flush_changes()` are public statics (`material.h:878`, `particle_process_material.h:537`, `canvas_item_material.h:139`).
  - With those, a test can assert:
    - shared shader RIDs for equal keys;
    - distinct RIDs for different keys;
    - release when the last user is freed;
    - that a flush drains.
  - Not assertable: dirty-list membership (private) and lock ordering. Only the TSan CI job covers lock ordering, since unit tests run in every Linux job including the sanitizer ones (`.github/workflows/linux_builds.yml:240-244`).
- Cost: **M**.

### C2: render-mode string contract (and generated uniform names)

**Current shape**
- One validation registry exists [E]: `ShaderTypes`, with grouped `ModeInfo` entries (`servers/rendering/shader_types.cpp:241+`). It is consumed through `get_modes()` (`shader_language.cpp:11313, 11608`; `shader_compiler.cpp:1573`).
- Each backend fills its own string→pointer maps [E]: `render_mode_values`, `render_mode_flags`, `usage_flag_pointers` and `render_mode_defines` (`shader_compiler.h:51-62, 97`). These are set per backend in `ShaderData::set_code`:
  - `scene_shader_forward_clustered.cpp`, ~71 assignment lines;
  - `scene_shader_forward_mobile.cpp`, ~69;
  - GLES3 `material_storage.cpp`, ~126 across 5 shader kinds.

  These counts come from a grep by the worker, not from ast-grep.
- The three generators [E]:
  - BaseMaterial3D emits 32 literals (source §1.6).
  - CIM emits 8 literals, at most 2 per shader (`canvas_item_material.cpp:86-116`).
  - PPM emits 2 (`particle_process_material.cpp:200-202`).

**History and intentionality**
- "A built-in material is generated shader text, convertible to ShaderMaterial" is **deliberate** [E]: generation since 53d8f2b1ec (2016), conversion since 3237e05c36 (2017), and the header comment from #50159 so that converted shaders "can be regenerated".
- Per-renderer mode handling: no discussion found [?].
- The #115163 revert and its redo, #115147 (9 files), did not raise the duplication in the inspected threads [E].

**Feasibility**
- Scene half (generator → `ShaderTypes`): a guard is **feasible today**, at cost S [E]. Through the dummy compiler (`dummy/storage/material_storage.cpp:191`), a matrix over feature/flag combinations would surface "Invalid render mode" (`shader_language.cpp:11373`) and other compile errors. It needs `ErrorDetector`, because a failure only prints (`:192`).
- Snapshotting the generated text needs a seam: dummy `shader_get_code` returns `""` (`dummy/storage/material_storage.h:100`) [E].
- Backend half: the dummy compiler uses empty `DefaultIdentifierActions` (`dummy/storage/material_storage.cpp:40-41`). It cannot check how RD or GLES3 interpret a mode [E]. A shared backend mode registry would redesign how renderers declare mode handling.
- **Conclusion:** the adequate fix for the scene half is a test (not structural). The backend half is a renderer-architecture redesign: **stop**.

### C3: two hand-kept renderer material storages (RD and GLES3)

**Current shape**
- `RendererMaterialStorage` (`servers/rendering/storage/material_storage.h:37-104`) is pure-virtual and has no `.cpp` [E].
- The two `Material` structs are field-for-field identical [E] (RD `material_storage.h:291-309`, GLES3 `:117-135`). The one exception is `ShaderType shader_type` vs `RSE::ShaderMode shader_mode`. The RD `Shader` adds a `Mutex *mutex` and `embedded`.
- Section sizes [E]:
  - MATERIAL API: RD `:2430-~2702` (~273 LOC, 17 functions) vs GLES3 `:2434-~2650` (~217 LOC, 16 functions).
  - GLOBAL SHADER UNIFORM API: RD `:1574-2192` (619 lines) vs GLES3 `:1626-2245` (620 lines). After normalising the namespace qualifier, `diff` reports 37 changed lines. I re-ran this.
- Precedents for shared code between the two renderers [E]:
  - the template-method pattern in `RendererMeshStorage` (`storage/mesh_storage.cpp:36+`, public `multimesh_*` delegating to pure `_multimesh_*`, `mesh_storage.h:131 vs 171`);
  - the concrete shared `RendererEnvironmentStorage` (`renderer_scene_render.h:43`);
  - the header-only `storage/variant_converters.h`, included by both material storages;
  - `Dependency` / `DependencyTracker` (`storage/utilities.cpp:33-53`).

**History and intentionality**
- One implementation per backend behind an interface is **deliberate** [E]. BastiaanOlij's 2022 storage split (#59385, 36defd1179) created `RendererMaterialStorage` with per-driver implementations. GLES3 descends from the 3.x OpenGL lineage.
- The diverging lock is **justified by the threading model** [E]:
  - f379b84004 (Skyth, #116203, 2026-04-29) added `shader->mutex` in RD only (`git show --stat`: 2 RD files).
  - GLES3 `can_create_resources_async()` returns `false` (`drivers/gles3/rasterizer_gles3.h:125`); RD returns `true` (`renderer_compositor_rd.h:149`).
- The GLES3 priority range check dates to 8f30c52a37 (2017), carried over [I].
- Whether the backend-agnostic bookkeeping was ever meant to be shared: [?] No statement found.
- **Verdict:** the split is deliberate. The copied API-agnostic logic (material dirty queue, params, global uniform registry) is unknown, leaning accidental [I].

**Feasibility**
- Reuse: the `RendererMeshStorage` multimesh template-method pattern, or a header in `servers/rendering/storage/`.
  - Of the candidate homes inspected, it is the one compiled whether RD or GLES3 is disabled [E]: `servers/rendering/SCsub:41`.
  - `rendering_device` can be off (`SConstruct:199-203`), and is forced off on web (`:714-717`).
  - `opengl3` is a separate option (`:207`).
- The structs differ (`update_textures` signatures, `rd material_storage.h:96` vs `gles3 :89`), so sharing needs templates or a shared base struct. That is a **new** abstraction.
- Guards [E]:
  - No unit-level guard: neither backend can be instantiated in the harness (unit tests use the dummy RS, source §1.5).
  - Runtime coverage is the project test in the GCC sanitizer editor job only (`linux_builds.yml:63, 274-279`): headless, Vulkan and `opengl3` imports plus one default-driver run on mesa (`.github/actions/godot-project-test/action.yml:22-45`).
  - `check_ci_log.py` fails on crashes, sanitizer reports and leaks, not on wrong output.
  - Web templates build the GLES3-only configuration (`web_builds.yml:23-30`).
- **Characterization test: not possible** in the current harness.
- Cost: **L**.

### C4: per-class ad-hoc compatibility remaps

**Current shape**
- Anchors confirmed [E]:
  - `remaps[]` at `material.cpp:4108-4142`.
  - `flags_use_shadow_to_opacity` appears twice with the **identical** target (`:4109-4110`), so removing one is behaviour-neutral.
  - The self-map `params_depth_draw_mode` (`:4121`) is unreachable, because the name is handled earlier (`:4094`).
  - An unknown name gives `WARN_PRINT` + `return true` (`:4153-4154`).
- Other scene resources use the same ad-hoc `_set` idiom [E]. Examples: BoxShape3D `extents` (`box_shape_3d.cpp:81-94`), and similar code in mesh, font, animation, decal and others.
- No shared property-alias mechanism exists [I]:
  - `ClassDB::add_compatibility_class` handles class names only (`class_db.h:520`);
  - the 79 `*.compat.inc` files cover method bindings;
  - `renames_map_3_to_4.cpp` covers scripts and project text. It has no StandardMaterial3D property remaps; the one material-adjacent entry is the render-mode rename at `:1449`.

**History and intentionality**
- The remapping is **deliberate**: dd3682e5fe (reduz, 2019), guarded later by #36175 under `DISABLE_DEPRECATED`. The ShaderMaterial prefixes come from #71797 (2023): "Compatibility remaps are only needed here."
- `return true` for unknown names, the duplicate and the self-map: **accidental** [I]. The original branch only printed, and #55651 converted that to `WARN_PRINT`.
- The `_set` + `DISABLE_DEPRECATED` convention is used across 41 files under `scene/`. No written policy was found [?].

**Feasibility**
- A characterization test is **feasible** [E]:
  - StandardMaterial3D: `set("flags_transparent", true)` then `get_transparency()`.
  - ShaderMaterial: `_set` needs only `shader.is_valid()` (`:201`), and values land in `param_cache`, readable without the RS (`:422-462`).
  - A full `.tres` text load follows the precedent at `tests/core/io/test_resource.cpp:530-572`.
- The `deprecated=no` minimal template catches compile breaks (`linux_builds.yml:115`). The 3→4 converter test does not touch `_set` (`project_converter_3_to_4.cpp:482-492`).
- Cost: **S**. Structural value: **low** (see §4).

### C5: default-skip serialization

**Current shape**
- Both savers skip a property when `PropertyUtils::get_property_default_value` `==` the current value (`resource_format_text.cpp:2099-2103`, `resource_format_binary.cpp:2218-2222`) [E]. Defaults come from a cached instance per class (`class_db.cpp:1877-1912`).
- No "always write" usage flag exists. `STORE_IF_NULL` applies to null objects only [E].
- `FORMAT_VERSION` [E]:
  - binary 6 (`resource_format_binary.cpp:97`); text 4, compat 3 (`resource_format_text.h:46-48`);
  - it is used only to reject loads and to gate features;
  - there is no per-type migration hook.

**History and intentionality**
- **Deliberate, but undocumented** [E]: f2e54057ae (reduz, 2018, #23595) introduced it with no stated reason.
- Maintainers treat "don't change defaults" as a constraint, enforced case by case [E]. clayjohn on #112469 reverted the intentional glow default change. Calinou (proposal 4834) and dalexeev (proposal 9948) say the same.

**Feasibility: stop.**
- Changing what is skipped, or adding versioned per-class migration, changes the meaning of saved files that relied on a skipped default. Consumers span `packed_scene.cpp`, `class_db.cpp`, `doc_tools.cpp`, `editor_inspector.cpp` and others [E].
- This is a persistence-contract redesign, for a separate analysis.
- The existing guard is the `--doctool` diff of `default=` (`doc_tools.cpp:1768`, `linux_builds.yml:252-258`). It catches changed class defaults, not the skip logic.

### C6: `_validate_property` mixes "hide in the editor" with "do not store"

**Current shape**
- `material.cpp:2595-2781` [E]:
  - 23× `PROPERTY_USAGE_NONE`, unconditional (`:2663-2778`);
  - 16× `NO_EDITOR`, behind `is_editor_hint()` (`:2611, 2689`);
  - `emission_intensity` gated on a ProjectSetting (`:2596-2597`).
- `PROPERTY_USAGE_NO_EDITOR == PROPERTY_USAGE_STORAGE` (`core/object/property_info.h:125`) [E]. So the codebase already has "editor-hidden but stored". Environment uses only that form (`environment.cpp:1107-1113+`).
- PPM mixes the same way: ~26 NONE, 3 NO_EDITOR (`particle_process_material.cpp:2157-2286`). CIM has 1 NONE (`canvas_item_material.cpp:229-231`).
- [I] Some NONE drops lose authored values. Example: `blend_mode` under alpha AA (`:2681-2682`), while `_update_shader` always emits `blend_mode` (`:754`).

**History and intentionality**
- `usage = 0` comes from reduz-era code (2017–2019) and #22461 (2018) [E].
- NO_EDITOR arrived with #50539 (2021) and later PRs [E].
- No PR discusses the storage consequence [E: none found].
- **Verdict:** unknown, leaning accidental [I].

**Feasibility**
- A usage-matrix snapshot test is **feasible**. `get_property_list()` needs no RS, and the ProjectSetting is version-cached and settable (`project_settings.h:281-289`) [E].
- A table-driven rewrite with identical output is a pure refactor, but of low value.
- The adequate target (stop clearing STORAGE) **changes saved files**, so it is a behaviour change. Cost: S–M.

### C7: CPUParticles ↔ ParticleProcessMaterial parity

**Current shape** [E]
- The source's `cpu_particles_2d.cpp:1400-1470` is `convert_from_particles` (a property copy), **not** the simulation. The simulation is `_particles_process`:
  - `cpu_particles_2d.cpp:805-1199` (~395 LOC);
  - `cpu_particles_3d.cpp:759-1269` (~510 LOC).
- PPM's GPU path is GLSL text generation (`particle_process_material.cpp:160-1384`).
- CPUParticles redeclare their own enums (`cpu_particles_2d.h:65-75`, `cpu_particles_3d.h:52-80`). Mapping between the two sides works by name through `CONVERT_PARAM` in both directions (`gpu_particles_2d.cpp:524`, `gpu_particles_3d.cpp:683`).

**History: deliberate** [E]. The three missing flags came from #79527, #112184 and #120764, none of which touched CPUParticles. clayjohn on #79527 (2023-10-11): "We aren't porting all GPUParticles features over the CPUParticles anymore … CPUParticles are now the ultra-light alternative". `doc/classes/CPUParticles3D.xml` does not state that policy (a docs gap).

**Feasibility: stop.**
- The two sides are execution targets (C++ simulation vs generated GLSL) with a deliberately diverging feature set. Sharing could only reach the enums and parameter model, which is a domain decision.
- Guard input: no tests exist. A `convert_from_particles` mapping test is feasible. The simulation output is private (`cpu_particles_2d.h:112-115`).

### C8: shader baker hand-copies Sprite3D/Label3D logic

**Current shape** [E]
- What the baker does (`editor/export/shader_baker/shader_baker_export_plugin.cpp`):
  - hard-codes 9 default values (`:312-321`);
  - overlays each node property by name (`:323-331`);
  - re-implements the alpha-cut → Transparency mapping (`:333-346`).
- That mapping now exists **3 times** (`sprite_3d.cpp:289-299`, `label_3d.cpp:387-397`, baker). Label3D's copy differs: it is always at least ALPHA.
- The baker calls `get_material_for_2d` with 10 positional arguments (`:349, :354`). The signature has 11 value parameters plus `r_shader_rid` (`material.h:880`), so `p_texture_repeat` is always the default `false`. Sprite3D derives it at runtime (`sprite_3d.cpp:167, 303`).
- The baker casts to `Sprite3D` only (`:307`); [I] AnimatedSprite3D is skipped. It also uses `SpriteBase3D::AlphaCutMode` for Label3D, which declares its own enum (`label_3d.h:50`).
- `StandardMaterial3D::get_material_for_2d` is already the shared factory (callers: `material.cpp:3047`, `root_motion_view.cpp:87`, Sprite3D, Label3D, baker). No helper exists for "parameters from node".

**History: accidental drift** [E]
- #102552 (DarioSamo) introduced the copy with "must match" comments. None of the review comments the worker inspected on the export plugin mention them.
- #98122 (cadence-s) later added `p_texture_repeat`, touching only `label_3d.cpp`, `sprite_3d.cpp`, `material.cpp` and `material.h`.
- The merge order is verified: `de37627404` 2025-05-28 (baker) before `44bc2da147` 2025-12-02 (#98122). The defaulted parameter let the stale call compile silently.

**Feasibility** [E]
- Layering is fine: the baker already includes `scene/3d/sprite_3d.h` and `label_3d.h` (`:39-40`).
- A characterization test is **feasible**:
  - The `get_material_for_2d` cache key is pure arithmetic (`material.cpp:3047-3060`) and returns the same `Ref` for equal keys.
  - Its shader compiles through the dummy RS.
- No tests exist today for Sprite3D, Label3D or the baker.
- Cost: **S**.

### C9: string-keyed coupling in editor plugins and hint strings

**Current shape** [E]
- `material_editor_plugin.cpp:473-506`: 8 literals, `cast_to<StandardMaterial3D>` at `:479`.
- The PPM editor hand-parses a range hint (`particle_process_material_editor_plugin.cpp:458-464`). A file-static parser exists: `_parse_range_hint`, at `editor/inspector/editor_properties.cpp:3901`.
- Hint strings:
  - `"BaseMaterial3D,ShaderMaterial"` 11× in 5 files (confirmed).
  - The `CanvasItemMaterial,ShaderMaterial` set is at `tile_set.cpp:7188`, `canvas_item.cpp:1591` and `mesh.cpp:1791`; `ParticleProcessMaterial,ShaderMaterial` at `gpu_particles_2d.cpp:984` and `gpu_particles_3d.cpp:903`. This corrects the locations the source gave.
- Name-constant patterns exist: `SNAME`, `SceneStringName`, `CoreStringName` and `MAKE_RESOURCE_TYPE_HINT` (`object.h:68`). None of them holds these names.

**History** [E]: the undo hook (#56145, 2021) is deliberate. It moved out of the setter because the setter version broke glTF loads: "any changes to this factor will be lost". The literals and the cast type were incidental. ORMMaterial3D has no separate roughness or metallic texture, so excluding it is likely moot [I].

**Feasibility** [E/I]
- A constant with the identical value yields the same `extension_api.json` (`core/extension/extension_api_dump.cpp:79-80`) and the same doc XML.
- Exposing `_parse_range_hint` may parse differently, a behaviour risk [I].
- Cost: **S**. Value: **low**.

### C10: `navigation_server_3d.h` includes `scene/resources/material.h`

**Current shape** [E]
- Line `:36` is the header's only `scene/` include. The material type is used only in 15 `Ref<StandardMaterial3D>` fields and 15 getters (`:398-414`, `:504-521`), all inside `#ifdef DEBUG_ENABLED` (`:354`).
- The getters are **not** bound to scripts: of 154 `bind_method` calls in `navigation_server_3d.cpp`, none is a debug-material getter (re-checked). So there is no API or doc impact.
- Callers span 7 files: `navigation_region_3d.cpp` 7, `navigation_link_3d.cpp` 4, `navigation_obstacle_3d.cpp` 3, `navigation_agent_3d.cpp` 2, `navigation_mesh.cpp` 2, `navigation_obstacle_3d_editor_plugin.cpp` 2, `grid_map.cpp` 1.
- NavigationServer2D keeps `Color`s only and includes only core headers (`navigation_server_2d.h:333-345`).
- Idioms that make a forward declaration workable: `class Material;` + `Ref<>` in `scene_tree.h:48, 215-216` and `navigation_agent_3d.h:40, 118-119`. The constructor and destructor are out of line (`navigation_server_3d.cpp:248, 355`).

**History** [E]
- Debug drawing moved into the server on purpose: #62601 (smix8, 2022), "Majority of debug code moved from SceneTree to NavigationServer", implementing proposal #4507. #78276 then removed the legacy materials.
- The server→scene include is an unweighed side effect [I]; no issue proposing to move it was found [?].
- The 2026 RenderingServer decoupling series (akien-mga) does not cover navigation [E].
- **Verdict:** the placement is deliberate. The include coupling is accidental [I].

**Feasibility** [E]
- The guard is the CI compile matrix:
  - editor, templates, and the minimal `disable_3d` template (`linux_builds.yml:105-118`);
  - `disable_3d` forces `disable_navigation_3d` (`SConstruct:1094-1097, 1107-1108`).
- `tests/servers/test_navigation_server_3d.cpp` exists but does not touch the debug materials.
- How many of the 31 includers (29 non-test + 2 test) rely on `material.h` transitively is unknown without a build [?].
- `validate_includes.py` checks path format, not layering.
- Cost: **S**.

---

## 2. Guard and CI facts shared by all candidates

- Unit tests run in every Linux job, including ASan/UBSan and TSan (`linux_builds.yml:240-244`; `dev_mode=yes` → `tests=yes`, `linux_builds.yml:13-15`, `SConstruct:251, 687`). They also run on Windows (`windows_builds.yml:132-136`) and macOS (`macos_builds.yml:115-119`) [E]. A new characterization test therefore also gets leak and race checking at no extra cost [I].
- A new `tests/scene/test_*.cpp` is picked up automatically (`tests/SCsub:11`). Module tests must be `modules/*/tests/*.h` (`modules/SCsub:48`) [E].
- Shader-key channel: **testable** through the dummy compiler with `ErrorDetector` (§Summary). Value channel and generated text: **not observable** without a test-infrastructure seam (`dummy/storage/material_storage.h:100, 105, 120, 123, 124`) [E].
- The runtime renderer smoke runs only in the GCC sanitizer editor job, and fails only on crashes, sanitizer reports and leaks (`linux_builds.yml:63, 274-279`; `misc/scripts/check_ci_log.py:19-51`) [E].
- Other CI checks: the doctool `default=` diff (`linux_builds.yml:252-258`), `validate_extension_api.sh` (`:261-264`) and the 3→4 converter self-test (`:288-292`) [E].

---

## 3. Refactor opportunities (ranked proposal for the planning session)

The ranking weighs the cost of the debt (recurrence, realized drift, concurrency risk, reach) against the cost of the change (size, blast radius, availability of a behaviour-pinning guard, reversibility). It also weighs the intentionality verdict: a load-bearing decision lowers a candidate. The planning session makes the choice.

### #1: C1, shared refcounted shader cache for generated materials

- **Current → target.** Three hand-written copies of key → `{RID, users}` map, race-handling create and release, each with its own lock and init policy → one small cache unit (map + refcount + race-safe create/release). BaseMaterial3D and PPM call it; each class keeps its own dirty-list and lock policy.
- **Why this place.**
  - The debt is the most consequential of the cheap-to-guard candidates. A concurrency fix has already landed in one copy only: #105138 changed `material.cpp`, not PPM or CIM (verified `--stat`).
  - #91630 shows that consistency across the three was an intention as recently as 2024.
  - A third copy, CIM, has an unlocked `shader_map` access [E], [I] risk.
  - No history supports the duplication as a decision.
  - The change cost is moderate. The two copies that share a shape (BaseMaterial3D, PPM) can migrate without changing semantics. Guards are feasible today, and TSan runs them in CI.
- **Blast radius.**
  - `material.cpp`, `particle_process_material.cpp` and one new helper header. `material.h` (37 direct includers, 150 within two hops) and `particle_process_material.h` (10) change only if `ShaderData` / `shader_map` declarations move [I].
  - No API or doc impact: the members are private or protected static [I].
- **Incremental path.**
  1. Characterization tests: RID sharing for equal keys, distinct RIDs for different keys, release when the last user is freed (LSan), and `flush_changes()` draining, for each of the three classes.
  2. Introduce the cache helper and switch **PPM** to it. Of the two, PPM is the one whose shape already matches the race-safe path.
  3. Switch BaseMaterial3D, as its own commit.
  4. CIM: its create path (no race handling) and single mutex differ. Migrating it changes behaviour, so it is a **separate change** together with the unlocked-access fix. The planning session must decide whether it is in scope.

  Unifying lock-during-flush policy is likewise out of scope.
- **First prerequisite step.** `tests/scene/test_material_shader_cache.cpp`, pinning the cache behaviour above under the dummy RS. It must use `ErrorDetector` so that compile errors fail the test.

### #2: C8, one "2D-material parameters from node" helper

- **Current → target.** Alpha-cut → Transparency mapping in 3 copies, plus a hand-copied default table in the baker → one static helper, for example on `SpriteBase3D` / `Label3D`. Sprite3D, Label3D and the baker derive `get_material_for_2d` arguments through it.
- **Why this place.**
  - The drift is **already realized and dated**: #98122 merged after the baker and did not update it (its `--stat` lists no baker file).
  - The history shows no decision that would carry the copy. The authors themselves flagged it with "must match" comments.
  - The change cost is the lowest of all candidates (S). The test is pure arithmetic over `get_material_for_2d` `Ref` identity, and layering is already correct.
  - It ranks below C1 because the consequence is weaker. It concerns which shader variants the export pre-bakes [I: a missed variant is compiled at runtime instead], not correctness of the material pipeline.
- **Blast radius.** `sprite_3d.{h,cpp}`, `label_3d.{h,cpp}` and `shader_baker_export_plugin.cpp`. `get_material_for_2d` has other callers (`material.cpp:3047`, `root_motion_view.cpp:87`), which need not change [I]. How many files include `sprite_3d.h` / `label_3d.h` was not counted [?].
- **Incremental path.**
  1. Characterization test: for each alpha-cut mode and the relevant flags, Sprite3D and Label3D yield the same material `Ref` as a direct `get_material_for_2d` call with the expected arguments.
  2. Extract the helper and use it from Sprite3D only.
  3. Use it from Label3D, preserving its "at least ALPHA" rule.
  4. Use it from the baker.

  Pre-baking `texture_repeat` variants and covering AnimatedSprite3D are **behaviour changes**, so they are a separate change.
- **First prerequisite step.** The alpha-cut → Transparency / `Ref`-identity characterization test for Sprite3D and Label3D.

### #3: C10, cut the `navigation_server_3d.h → material.h` include

- **Current → target.** The server header includes a scene resource header for 15 debug-only `Ref<StandardMaterial3D>` members → a forward declaration in the header and the include in `navigation_server_3d.cpp`. A possible later step: the server keeps colors only, like NavigationServer2D, and the materials move scene-side, as `SceneTree` does with its own debug materials. That later step partly reverses the deliberate #62601 placement, so the plan would have to justify it on its own.
- **Why this place.**
  - The change cost is minimal (S). It is compile-only: no API or doc impact (the getters are unbound), and it is fully reversible in one commit.
  - It is guarded by the existing CI compile matrix, including the `disable_3d` minimal template.
  - It removes one of the servers→scene backward edges that the repo map identifies as the glue of the single 101-component cycle (`context/map/repo-map.md` §3).
  - Its debt cost is modest: compile coupling for 31 includers, not a correctness risk. That is why it ranks third.
- **Blast radius.** `navigation_server_3d.{h,cpp}`, plus an unknown number of the 31 includers that use material types only transitively [?]. At least 12 includers use material types without a direct include (worker grep). Whether they break is only known after a build.
- **Incremental path.**
  1. Forward-declare and move the include. Then add explicit includes in each translation unit that breaks, one commit.
  2. Optional, separate: move debug material ownership scene-side.
- **First prerequisite step.** A build (editor plus the `disable_3d` minimal template) listing the TUs that break once the include is removed. No characterization test is needed, because behaviour is not touched.

### Considered and not ranked

| Cand. | Why not ranked |
|---|---|
| **C3** RD/GLES3 storages | **Largest debt** in scope: material API twins, plus the 619/620-line global-uniform near-copy (37 differing lines), and repo-map zone 3. But the backend split is deliberate, the lock divergence is justified, the change cost is **L**, and **no characterization test can run either backend** in the harness. The only runtime guard is a crash/leak-only smoke run, so "guard first" cannot be met cheaply. Best treated as a follow-up whose own prerequisite is a renderer-level guard. |
| **C2** render-mode contract | The adequate fix for the scene half is a **test** (a compile matrix through the dummy compiler with `ErrorDetector`), not a structural change. The backend half is a renderer-architecture redesign: stop. The test is valuable as a guard and overlaps with C1's prerequisite. |
| **C4** compat remaps | The remapping is deliberate and follows a convention used across 41 `scene/` files. The structural move (table to compat unit) buys little. The two clear defects are trivial: the duplicate is behaviour-neutral and the self-map is unreachable. The remaining defect (`return true` for unknown names) is a behaviour change. |
| **C5** default-skip | A deliberate file-format contract. A fix would redesign persistence semantics: **stop, separate analysis**. |
| **C6** `_validate_property` | A table rewrite with identical output is low-value. The meaningful fix (stop dropping STORAGE) changes saved files, so it is a **behaviour change** for a separate analysis. |
| **C7** CPUParticles parity | A deliberate product decision (clayjohn, #79527). The sides are different execution targets. **Domain question: stop.** The remaining docs gap in `CPUParticles3D.xml` is not structural. |
| **C9** string literals / hint strings | Low debt cost: literals are guarded indirectly by doctool and API CI for hint strings, and the undo hook is deliberate. Exposing `_parse_range_hint` carries a parsing-behaviour risk. A possible opportunistic cleanup, not a ranked opportunity. |

---

## Code References

- `scene/resources/material.cpp:100-124`: `_mark_ready` / `_mark_initialized`
- `scene/resources/material.cpp:2088-2113, 2134-2158`: BaseMaterial3D race-safe shader create, flush outside the lock, `_queue_shader_change`
- `scene/resources/particle_process_material.cpp:1360-1405`: PPM create, flush under the lock, queue
- `scene/resources/canvas_item_material.cpp:58-80, 143-162, 235-237`: CIM unlocked `shader_map` access, flush, `get_shader_rid`
- `scene/resources/material.h:411, 417, 524`; `particle_process_material.h:153, 158, 204`; `canvas_item_material.h:81, 99`: `ShaderData` and mutexes
- `servers/rendering/dummy/storage/material_storage.cpp:40-41, 191-192`: the dummy compiler (empty actions) and its compile-error path
- `servers/rendering/renderer_rd/storage_rd/material_storage.cpp:1574-2192, 2430-2702` vs `drivers/gles3/storage/material_storage.cpp:1626-2245, 2434-2650`: twin sections
- `servers/rendering/storage/mesh_storage.cpp:36+`: the template-method precedent for shared renderer storage code
- `drivers/gles3/rasterizer_gles3.h:125`, `servers/rendering/renderer_rd/renderer_compositor_rd.h:149`: async resource creation, false vs true
- `scene/resources/material.cpp:4108-4156`: remaps table, duplicate, unreachable self-map, `return true`
- `core/object/property_info.h:125`: `NO_EDITOR == STORAGE`
- `editor/export/shader_baker/shader_baker_export_plugin.cpp:307-354`: baker defaults, alpha-cut copy, 10-argument calls
- `scene/3d/sprite_3d.cpp:167, 289-303`; `scene/3d/label_3d.cpp:387-398`; `scene/resources/material.h:880`: the other copies and the factory signature
- `servers/navigation_3d/navigation_server_3d.h:36, 354, 398-414, 504-521`: include and debug-only members
- `.github/workflows/linux_builds.yml:13-15, 63, 105-118, 240-244, 252-292`: the CI guards used above

## Architecture Insights

- Every candidate the research found **deliberate** is deliberate at the level of a concept:
  - "a material is generated shader text" (C2);
  - "one storage per graphics API" (C3);
  - "the saved file is a diff from class defaults" (C5);
  - "CPUParticles is a lightweight subset" (C7).

  Every candidate found **accidental** sits one level below, in mechanics copied to serve that concept: the cache (C1), the baker copy (C8), the include (C10). The ranking follows that boundary.
- Godot's fixes tend to be scoped to the class where the bug showed up (#90400, #99716, #105138, #98122, #116203). Without a shared unit or a test, the twins silently diverge after each fix. This is the mechanism behind C1, C3 and C8 [I, from those five PRs].
- The test harness is stronger than the source analysis suggested for the shader-key channel (real `ShaderCompiler` + `ShaderTypes`) and as weak as stated for the value channel.

## Historical Context (from prior changes)

- `context/changes/material-resources-flow-analysis/research.md`: the evidence base. Its claims, adjudicated individually:

  | Source claim | Verdict |
  |---|---|
  | D1 "three copies" | Supported. Precised: CIM has no separate map mutex; `_mark_ready` is defined at `material.cpp:100` (`:661` is the call). |
  | D3 "material_set_param etc. identical" | Supported. Extended: the global-uniform API is a larger near-copy. |
  | D3 "lock gap is drift" | **Partial.** History plus `can_create_resources_async` shows the gap is justified for GLES3. |
  | D7 "dummy RS makes the seam untestable" | **Partial.** True for the value channel and the generated text. False for shader-key compile errors, which the dummy compiler surfaces (needs `ErrorDetector`). |
  | D9 / §1.6 "`cpu_particles_2d.cpp:1400-1470` re-implements PPM" | **Contradicted on the anchor.** That range is `convert_from_particles`; the simulation is `:805-1199`. The parity gap is deliberate (#79527), which answers the source's Open Question "Is the CPUParticles3D flag gap intentional?" |
  | D10 "Sprite3D/Label3D pass 12 arguments" | **Precised.** 11 value parameters plus `r_shader_rid`; the baker passes 10. |
  | D12 / §1.6 hint-string sibling locations | **Precised.** Locations corrected in §1.C9. The count of 11× in 5 files is supported. |
  | D13 "29 includers" | Supported: 29 full-path non-test, 31 including tests. |

- `context/map/repo-map.md`: zone 2 (materials and particles, reverts, no tests) and zone 3 (two renderers) are supported by this research's history findings. The "~24 backward includes glue one cycle" claim was not re-checked here; it is used only as context for C10.
- No archived changes exist (`context/archive/` holds only README.md).

## Related Research

- `context/changes/material-resources-flow-analysis/research.md`

## Open Questions

- C1: Is the unlocked CIM `shader_map` access reachable concurrently in practice? This depends on which thread runs the deferred `_mark_initialized` callback during threaded loads. [?]
- C1: Whether CIM belongs in the refactor at all, given that its migration changes behaviour. This is a planning decision.
- C3: Was sharing backend-agnostic storage logic ever proposed or rejected upstream? No statement was found. GitHub search was coarse.
- C8: The practical impact of the never-pre-baked `texture_repeat` variant (a runtime compile on first use?). [?]
- C10: The exact set of TUs that rely on `material.h` transitively through `navigation_server_3d.h`. Only a build can tell.
- Carried from the source and still open: the D4 load-order dependency for ShaderMaterial parameters; whether anything listens for `Material.changed` on BaseMaterial3D (D11); which generated-shader combinations any CI run compiles on RD and GLES3.

## Research method and coverage

- The source analysis and the repo map were read in full in the main context. `context/foundation/lessons.md` does not exist.
- Three parallel read-only general-purpose workers each covered all ten candidates along one dimension: (1) current shape, (2) history and intentionality (git, `gh` against godotengine/godot), (3) migration feasibility and CI. None wrote files.
- The primary agent re-checked these decisive anchors:
  - CIM unlocked `_update_shader` / `get_shader_rid`;
  - the global-uniform `diff` (619/620 lines, 37 changed);
  - dummy `shader_set_code` compile and error path;
  - 0 bound navigation debug-material getters;
  - `--stat` of 09282c316a, f379b84004 and fc9ea462ca;
  - the merge dates of #102552 and #98122;
  - `can_create_resources_async` false/true;
  - the remaps duplicate (identical) and self-map.
- **Not verified with ast-grep in this pass:** the worker counts (C2 map-assignment lines, C6 PPM usage counts, the C4 compat-line heuristic, 12 transitive C10 includers) are grep-based. The ranking's structural claims are planned for `m4l4-3` ast-grep verification.
- Nothing was built or run. No ADRs or design docs exist in the repo; all rationale comes from commits, PR bodies and review comments.
