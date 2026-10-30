---
date: 2026-10-30T11:16:45+01:00
researcher: Claude (Opus 5.5) for Hornster
git_commit: 5ed1824a23c40298fe01da8dde2cb89ae7e2fe38
branch: master
repository: godot-tests (Godot Engine fork, origin github.com/Hornster/godot-tests)
topic: "Refactor opportunities from the material resources flow analysis: which recorded problems are structural, why they have their shape, and what an incremental path would cost"
tags: [research, refactor, ranking, scene-resources, material, particle-process-material, canvas-item-material, material-storage, shader-baker, navigation-server, characterization-tests, verified]
status: complete
last_updated: 2026-10-30
last_updated_by: Claude (Opus 5.5) for Hornster
last_updated_note: "Structural claims verified with ast-grep 0.50.0 (m4l4-3); corrected figures are marked inline as 'N (report: M)'; see 'Claim verification (ast-grep)'"
verification_commit: d42f2deede5823a72834b6f89db8ea2e5136f0d8
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
  - CanvasItemMaterial touches its static `shader_map` without a lock in `_update_shader` (`canvas_item_material.cpp:58-151` (report: 58-80); the accesses are at `:64-77` and `:148`) and in `get_shader_rid` (`:235-237`), and has no separate map mutex (`canvas_item_material.h:99`) [E]. A race on the deferred load path is [I].
  - The baker's missing `texture_repeat` is a dated drift [E]:
    - The baker (#102552) merged 2025-05-28 (`de37627404`).
    - `p_texture_repeat` (#98122) merged later, on 2025-12-02 (`44bc2da147`). It touched `label_3d.cpp`, `sprite_3d.cpp`, `material.cpp` and `material.h` only (`git show --stat fc9ea462ca`).

---

## 1. Per-candidate findings

### C1: three copies of the generated-shader cache, dirty list and idle flush

**Current shape**
- Identical across all three classes [E]:
  - `struct ShaderData { RID shader; int users = 0; }` (`material.h:411`, `particle_process_material.h:153`, `canvas_item_material.h:81`).
  - The `_queue_shader_change` body (`material.cpp:2150-2160` (report: 2149-2158), `particle_process_material.cpp:1395-1405`, `canvas_item_material.cpp:162-172` (report: 152-162)).
  - `finish_shaders`: clear the list, `memdelete(shader_names)`.
- Shared only by BaseMaterial3D and PPM [E]: `hash_djb2_buffer`/`memcmp` key ops, and shader creation **outside** the map lock with race resolution (`material.cpp:2088-2113`; `particle_process_material.cpp:1360-1381`).
- Different in each [E]:
  - **Keys.** BaseMaterial3D uses a 25-field (report: ~20) bitfield plus two `uint32_t` masks (`material.h:359-409`). PPM uses a bitfield struct kept ≤ 64 bits (`particle_process_material.h:114-151`). CIM uses a `union` with `uint32_t key` and a murmur3 hash (`canvas_item_material.h:55-71` (report: 53-70)).
  - **Flush.** BaseMaterial3D copies the list under the lock and updates outside it (`material.cpp:2134-2148` (report: 2134-2147)). PPM (`:1386-1393`) and CIM (`canvas_item_material.cpp:153-160` (report: 143-150)) update while holding the lock.
  - **Mutexes.** BaseMaterial3D has `shader_map_mutex` (`material.h:417`) plus `material_mutex` (`:524`). PPM has `shader_map_mutex` (`:158`) plus `dirty_materials_mutex` (`:204`). CIM has a single `material_mutex` (`:99`).
  - **Create path.** CIM uses `shader_create()` + `shader_set_code`, `users = 1`, with no race handling.
  - **Init.** Only CIM calls `_mark_initialized` (`canvas_item_material.cpp:292`). BaseMaterial3D and PPM self-promote with `_mark_ready()` inside `_update_shader` (`material.cpp:661`, `particle_process_material.cpp:162`; the definition is at `material.cpp:100`).
  - **RID creation.** CIM and PPM create their RID eagerly (`canvas_item_material.cpp:284`, `particle_process_material.cpp:2759`). BaseMaterial3D creates it lazily (`material.cpp:3179-3183`).
- New [E]: CIM `_update_shader` (`canvas_item_material.cpp:58-151` (report: 58-80); `shader_map` accesses at `:64-77`, `:148`) and `get_shader_rid` (`:235-237`) read and write `shader_map` with no lock. When it runs from the deferred `_mark_initialized` path (`material.cpp:113-115`) it is outside the flush lock. [I]: a possible race. This is a **bug fix**, separate from the refactor.
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
  - `scene_shader_forward_clustered.cpp`, 64 (report: ~71) assignment lines;
  - `scene_shader_forward_mobile.cpp`, 64 (report: ~69);
  - GLES3 `material_storage.cpp`, 120 (report: ~126): 89 across the 5 `ShaderData::set_code` kinds (Scene 46, Sky 24, Canvas 11, TexBlit 6, Particles 2) plus 31 in the `MaterialStorage` constructor.

  These counts originally came from a grep by the worker. The figures above were re-counted with ast-grep in the verification pass (see "Claim verification (ast-grep)").
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
  - MATERIAL API: RD `:2430-2698` (report: ~2702) (269 (report: ~273) LOC, 17 functions) vs GLES3 `:2434-2661` (report: ~2650) (228 (report: ~217) LOC, 16 functions: 15 `material_*`/queue functions plus the `get_texture_uniform_data` helper).
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
- The `_set` + `DISABLE_DEPRECATED` convention is used across 35 (report: 41) files under `scene/`. 35 files have the guard inside or around a `::_set` definition; 41 is the file-level count of "`::_set` and `DISABLE_DEPRECATED` in the same file". No written policy was found [?].

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
  - 23× `PROPERTY_USAGE_NONE`, of which 21 (report: 23) are not editor-gated (`:2664-2778` (report: 2663-2778)). The other two are `:2597` (ProjectSetting gate) and `:2604` (`#ifndef DISABLE_DEPRECATED` particles billboard);
  - 16× `NO_EDITOR`, behind `is_editor_hint()` (`:2611, 2689`);
  - `emission_intensity` gated on a ProjectSetting (`:2596-2597`).
- `PROPERTY_USAGE_NO_EDITOR == PROPERTY_USAGE_STORAGE` (`core/object/property_info.h:125`) [E]. So the codebase already has "editor-hidden but stored". Environment uses only that form (`environment.cpp:1107-1113+`).
- PPM mixes the same way: 29 (report: ~26) NONE (15 of them inside `is_editor_hint()`), 3 NO_EDITOR (`particle_process_material.cpp:2156-2289` (report: 2157-2286)). CIM has 1 NONE (`canvas_item_material.cpp:229-231`).
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
- The source's `cpu_particles_2d.cpp:1400-1470` is `convert_from_particles` (a property copy; the function spans `:1400-1486`), **not** the simulation. The simulation is `_particles_process`:
  - `cpu_particles_2d.cpp:805-1198` (report: 805-1199) (~395 LOC);
  - `cpu_particles_3d.cpp:759-1268` (report: 759-1269) (~510 LOC).
- PPM's GPU path is GLSL text generation (`particle_process_material.cpp:160-1384`).
- CPUParticles redeclare their own enums (`cpu_particles_2d.h:44-81` (report: 65-75), `cpu_particles_3d.h:45-84` (report: 52-80); 4 enums each). Mapping between the two sides works by name through `CONVERT_PARAM` in both directions: `gpu_particles_2d.cpp:590` (report: 524), `gpu_particles_3d.cpp:746` (report: 683); 524/683 are the enclosing `convert_from_particles` definitions. The reverse direction is at `cpu_particles_2d.cpp:1463` and `cpu_particles_3d.cpp:1523`.

**History: deliberate** [E]. The three missing flags came from #79527, #112184 and #120764, none of which touched CPUParticles. clayjohn on #79527 (2023-10-11): "We aren't porting all GPUParticles features over the CPUParticles anymore … CPUParticles are now the ultra-light alternative". `doc/classes/CPUParticles3D.xml` does not state that policy (a docs gap).

**Feasibility: stop.**
- The two sides are execution targets (C++ simulation vs generated GLSL) with a deliberately diverging feature set. Sharing could only reach the enums and parameter model, which is a domain decision.
- Guard input: no tests exist. A `convert_from_particles` mapping test is feasible. The simulation output is private (`cpu_particles_2d.h:112-115`).

### C8: shader baker hand-copies Sprite3D/Label3D logic

**Current shape** [E]
- What the baker does (`editor/export/shader_baker/shader_baker_export_plugin.cpp`):
  - hard-codes 9 default values (`:313-321` (report: 312-321));
  - overlays each node property by name (`:323-331`);
  - re-implements the alpha-cut → Transparency mapping (`:333-346`).
- That mapping now exists **3 times** (`sprite_3d.cpp:289-299`, in `SpriteBase3D::draw_texture_rect`; `label_3d.cpp:388-395` (report: 387-397); baker `:334-345`). Label3D's copy differs: it is always at least ALPHA.
- The baker calls `get_material_for_2d` with 10 positional arguments (`:349, :354`). The signature has 11 value parameters plus `r_shader_rid` (`material.h:880`), so `p_texture_repeat` is always the default `false`. Sprite3D derives it at runtime (`sprite_3d.cpp:167, 303`).
- The baker casts to `Sprite3D` only (`:307`); [I] AnimatedSprite3D is skipped. It also uses `SpriteBase3D::AlphaCutMode` for Label3D, which declares its own enum (`label_3d.h:50`).
- `StandardMaterial3D::get_material_for_2d` is already the shared factory. It has 5 call sites in 4 files: `root_motion_view.cpp:87`, Sprite3D `sprite_3d.cpp:303`, Label3D `label_3d.cpp:398`, baker `:349, :354`. `material.cpp:3047` is its definition (report: listed as a caller). No helper exists for "parameters from node".

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
  - The `CanvasItemMaterial,ShaderMaterial` set is at `modules/tilemap/tile_set.cpp:7188`, `canvas_item.cpp:1591` and `mesh.cpp:1791`; `ParticleProcessMaterial,ShaderMaterial` at `gpu_particles_2d.cpp:984` and `gpu_particles_3d.cpp:903`. This corrects the locations the source gave.
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
- NavigationServer2D keeps `Color`s only (14 fields) and includes only core headers (`navigation_server_2d.h:333-350` (report: 333-345)).
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
- How many of the 30 (report: 31) includers rely on `material.h` transitively is unknown without a build [?]. The 30 are 29 full-path includers, 27 (report: 29) non-test plus 2 test, and the server's own `navigation_server_3d.cpp`. 12 of the 30 use material types without a direct `material.h` include; one of those 12 is `navigation_server_3d.cpp` itself.
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

## Claim verification (ast-grep)

**Pass:** m4l4-3, 2026-10-30, at `d42f2deede`. Engine source is byte-identical to `5ed1824a23`, the commit this report was written at: `git diff --stat 5ed1824a23 HEAD` touches only `context/`.

**Tool:** ast-grep 0.50.0, run as `ast-grep scan -r <inline rule> -c sgconfig.yml`.

**Tooling caveat.** By default ast-grep parses `*.h` as **C**, so C++ class bodies in headers do not match. The first header query (`struct ShaderData`) returned 0 even though `grep` finds 3. Every header query below therefore ran with a session config:

```yaml
languageGlobs:
  cpp: ["*.h", "*.inc", "*.cpp"]
```

Anyone re-running these rules needs the same mapping.

**Scope.** The structural claims the ranking rests on: method and field counts, "has X but not Y", call-site counts, mirrored type pairs. Git-history claims (PR numbers, dates, `--stat`) are not structural. They were re-checked only where they bear on a structural claim (V15).

**Verdicts.**
- **Confirmed:** the claim holds as written; any line shift is ≤ 1.
- **Refined:** the substance holds, but a count, range or qualifier was wrong or incomplete. It was corrected inline as `N (report: M)` outside §3.
- **Refuted:** the claim as written is false.

§3 "Refactor opportunities (ranked)" and the intentionality verdicts are deliberately left unchanged. Where §3 repeats a corrected figure, the correction is listed under "Findings that bear on the ranking" below.

### Results

| # | Claim (section) | Verdict | Evidence (file:line) | Method (pattern / rule) |
|---|---|---|---|---|
| V1 | `struct ShaderData { RID shader; int users = 0; }` identical in the 3 classes (C1) | Confirmed | `material.h:411-414`, `particle_process_material.h:153-156`, `canvas_item_material.h:81-84`; these are the only 3 in `scene/` | `kind: struct_specifier` + `has: {field: name, regex: ^ShaderData$}` |
| V2 | `_queue_shader_change` body identical ×3 (C1) | Confirmed; lines refined | `material.cpp:2150-2160` (report: 2149-2158), `particle_process_material.cpp:1395-1405`, `canvas_item_material.cpp:162-172` (report: 152-162). Bodies are token-identical apart from the mutex name (`material_mutex` / `dirty_materials_mutex` / `material_mutex`) | `kind: function_definition` + declarator `qualified_identifier` regex `_queue_shader_change$`; normalised full text compared |
| V3 | `finish_shaders` = clear list + `memdelete(shader_names)` ×3 (C1) | Refined | PPM `:153-158` and CIM `:51-56` match. BaseMaterial3D (`material.cpp:650-657`) also clears `materials_for_2d` | same rule, regex `::finish_shaders$` |
| V4 | `hash_djb2_buffer` / `memcmp` key ops only in BaseMaterial3D and PPM; CIM uses murmur3 (C1) | Confirmed | `material.h:400, 403, 407`; `particle_process_material.h:143, 146, 149`; CIM `canvas_item_material.h:66` (`hash_murmur3_one_32`) | `kind: call_expression` + function regex `^(hash_djb2_buffer\|memcmp\|hash_murmur3_one_32)$` |
| V5 | BaseMaterial3D and PPM create the shader outside the map lock and resolve races; CIM does not (C1) | Confirmed | `shader_create_from_code` at `material.cpp:2091` before `MutexLock(shader_map_mutex)` at `:2093`; PPM `:1363` before `:1365`. CIM: `shader_create()` `:143`, `users = 1` `:144`, `shader_set_code` `:146`, `shader_map[mk] =` `:148`, no lock | `kind: call_expression` regex `(shader_create\|shader_create_from_code\|shader_set_code\|material_create)$`; `kind: declaration` + type `^MutexLock$` |
| V6 | Flush: BaseMaterial3D copies under the lock and updates outside it; PPM and CIM update under the lock (C1) | Confirmed; lines refined | `material.cpp:2134-2148` (report: 2134-2147); `particle_process_material.cpp:1386-1393`; `canvas_item_material.cpp:153-160` (report: 143-150) | `kind: function_definition`, regex `::flush_changes$`, full text read |
| V7 | Mutexes: BaseMaterial3D `shader_map_mutex` + `material_mutex`; PPM `shader_map_mutex` + `dirty_materials_mutex`; CIM a single `material_mutex` (C1) | Confirmed | `material.h:417, 524`; `particle_process_material.h:158, 204`; `canvas_item_material.h:99`. Also found: per-instance `material_rid_mutex` (`material.h:101, 144`), not cache-related | `kind: field_declaration` + `has: {field: type, regex: ^Mutex$}` |
| V8 | Only CIM calls `_mark_initialized`; BaseMaterial3D and PPM call `_mark_ready()` in `_update_shader`; defined at `material.cpp:100` (C1) | Confirmed | `canvas_item_material.cpp:292`; `material.cpp:661`; `particle_process_material.cpp:162`; definition `material.cpp:100-102`; these are the only 3 calls in `scene/` | `kind: call_expression` + function regex `^(_mark_initialized\|_mark_ready)$` over `scene/` |
| V9 | RID created eagerly by CIM and PPM, lazily by BaseMaterial3D (C1) | Confirmed | `material_create()` `canvas_item_material.cpp:284`, `particle_process_material.cpp:2759`. The ast-grep count of `material_create` calls in `material.cpp` is 0; `grep` confirms and finds only `material_create_from_shader` (`:477`, `:2124`, in `_check_material_rid` under `material_rid_mutex` `:2117`), reached from `get_rid` `:3179-3183` | call rule regex `material_create$`; zero re-checked with `grep -n material_create` |
| V10 | CIM `_update_shader` and `get_shader_rid` touch `shader_map` with no lock (C1, new evidence) | Confirmed; range refined | `_update_shader` is `canvas_item_material.cpp:58-151` (report: 58-80); `shader_map` at `:64-69, 75-77, 148`; `get_shader_rid` `:235-238`, `shader_map` at `:236-237`. CIM's only `MutexLock`s are at `:154, :167, :296`. The ast-grep zero for a lock in both ranges was confirmed with `grep -c 'MutexLock\|.lock()'` = 0 / 0 | `kind: identifier` regex `^shader_map$`; `kind: declaration` type `^MutexLock$` |
| V11 | The three `flush_changes()` are public statics (C1) | Confirmed | `material.h:878`, `particle_process_material.h:537`, `canvas_item_material.h:139`, all under `public:` | `kind: field_declaration` regex `^static void flush_changes`; access specifier located by an `awk` scan |
| V12 | `get_rid()` / `get_shader_rid()` run `_update_shader()` synchronously (C1 guard) | Confirmed | `material.cpp:3180, 3371`; `particle_process_material.cpp:2147, 2152` | call `_update_shader$` `inside` function_definition with declarator regex `::get_(shader_)?rid` |
| V13 | `material.h`: 37 direct includers, 150 within two hops; `particle_process_material.h`: 10 (C1 blast radius) | Confirmed | 37 / 150 / 10. Also: `canvas_item_material.h` 4, `sprite_3d.h` 7, `label_3d.h` 3 | `kind: preproc_include` + `has: {field: path, regex: ^"…"$}`; `grep -rl` gives the same counts; two-hop set by a `grep` closure over the 22 direct-includer headers |
| V14 | MaterialKey shapes: BaseMaterial3D bitfield plus 2 masks; PPM ≤ 64-bit bitfield; CIM `union` (C1) | Refined | BaseMaterial3D has 25 (report: ~20) bitfields plus `uint32_t feature_mask`, `flags` (`material.h:359-409`); PPM 20 `uint64_t` bitfields (`:114-151`); CIM `union MaterialKey` at `canvas_item_material.h:55-71` (report: 53-70). The ast-grep zero for `struct MaterialKey` in CIM is explained: `grep` shows it is a `union` | `kind: field_declaration` + `has: {kind: bitfield_clause}` inside `struct_specifier` `^MaterialKey$`; `kind: union_specifier` |
| V15 | "A concurrency fix has landed in one copy only: #105138 changed `material.cpp`, not PPM or CIM" (§1.C1, §3 #1) | **Refined.** It bears on the ranking; see below | The race-safe block is identical in BaseMaterial3D (`material.cpp:2088-2113`, blamed to `09282c316a` / #105138) and PPM (`particle_process_material.cpp:1360-1381`, blamed to `5a30a7e7cd` "Add shader baker to project exporter" / #102552). The fix reached 2 of 3 copies through two separate PRs. Only CIM lacks it | V5 rule + `git blame -L` on both blocks |
| V16 | Baker: 9 hard-coded defaults, then a by-name overlay, then the alpha-cut mapping (C8) | Confirmed | 9 `properties[…] =` at `shader_baker_export_plugin.cpp:313-321` (report: 312-321); overlay loop `:323-331`; mapping `:333-346` | `kind: assignment_expression` + left `subscript_expression` regex `^properties\[` |
| V17 | Alpha-cut → Transparency mapping exists 3 times; Label3D's is at least ALPHA (C8) | Confirmed; lines refined | `mat_transparency` is declared in exactly 3 places repo-wide: `sprite_3d.cpp:289` (in `SpriteBase3D::draw_texture_rect` `:99-318`, so it is shared with AnimatedSprite3D), `label_3d.cpp:388` (initialised to `TRANSPARENCY_ALPHA`; if-chain `:389-395`; report: 387-397), baker `:334` (if-chain `:337-345`) | `kind: declaration` + `init_declarator` regex `^mat_transparency$` over `.`; `kind: if_statement` with an alpha-cut condition |
| V18 | Baker calls `get_material_for_2d` with 10 positional args; the signature has 11 value params + `r_shader_rid` (C8) | Confirmed | `:349` → 10, `:354` → 10; `sprite_3d.cpp:303` → 12; `label_3d.cpp:398` → 12; `root_motion_view.cpp:87` → 3; declaration `material.h:880` (12 params) | `kind: argument_list` `inside` call regex `get_material_for_2d$`; top-level commas counted |
| V19 | Sprite3D derives `p_texture_repeat` at runtime; the baker's stale call drops it (C8 drift) | Confirmed; refined | `sprite_3d.cpp:167` (computed), `:303` (passed). **Label3D passes a literal `false`** (`label_3d.cpp:398`), so the baker's defaulted `false` matches Label3D. The realised drift concerns the SpriteBase3D path only | `kind: identifier` regex `^texture_repeat$`; V18 argument dump |
| V20 | `get_material_for_2d` callers include `material.cpp:3047` (§1.C8; repeated in §3 #2) | **Refuted** (for that anchor) | `material.cpp:3047` is the **definition**. There are 5 call sites in 4 files: `root_motion_view.cpp:87`, `sprite_3d.cpp:303`, `label_3d.cpp:398`, baker `:349, :354`. The ast-grep zero for calls in `material.cpp` was confirmed by `grep -n get_material_for_2d(`, which finds only `:3047` | `kind: call_expression` + function regex `get_material_for_2d$` over `.` |
| V21 | Baker casts to `Sprite3D` only; AnimatedSprite3D is skipped [I] (C8) | Confirmed (structural basis) | `cast_to<Label3D>` `:306`, `cast_to<Sprite3D>` `:307`; `AnimatedSprite3D : public SpriteBase3D` (`sprite_3d.h:228`), not `Sprite3D` (`:182`) | `kind: base_class_clause` inside `class_specifier` |
| V22 | Label3D declares its own `AlphaCutMode` (C8) | Confirmed | `label_3d.h:50-56` vs `sprite_3d.h:53-59` | `kind: enum_specifier` regex `^AlphaCutMode$` |
| V23 | Baker already includes `sprite_3d.h` / `label_3d.h` (C8 layering) | Confirmed | `shader_baker_export_plugin.cpp:39` (`label_3d.h`), `:40` (`sprite_3d.h`) | `kind: preproc_include` + path regex |
| V24 | `navigation_server_3d.h:36` is the header's only `scene/` include (C10) | Confirmed | Includes `:33-36`; only `:36` is outside `core/` | `kind: preproc_include` |
| V25 | 15 `Ref<StandardMaterial3D>` fields (`:398-414`) and 15 getters (`:504-521`), all in `#ifdef DEBUG_ENABLED` (`:354`) (C10) | Confirmed | 15 fields `:398-414`, 15 getters `:504-521`, all inside `preproc_ifdef` `:354-522`; `grep -c 'Ref<StandardMaterial3D>'` = 30 = 15 + 15 | `kind: field_declaration` + type `^Ref<StandardMaterial3D>$` ± `function_declarator`; `kind: preproc_ifdef` name `^DEBUG_ENABLED$` |
| V26 | 154 `bind_method` calls in `navigation_server_3d.cpp`; none binds a debug-material getter (C10) | Confirmed | 154 (ast-grep) = 154 (`grep -c`). The ast-grep 0 for getter bindings was confirmed by `grep -cE 'bind_method.*(<15 getter names>)'` = 0 | `kind: call_expression` function `^ClassDB::bind_method$` + `regex` on the 15 names |
| V27 | Getter callers span 7 files: 7 / 4 / 3 / 2 / 2 / 2 / 1 (C10) | Confirmed | 21 calls: `navigation_region_3d.cpp` 7, `navigation_link_3d.cpp` 4, `navigation_obstacle_3d.cpp` 3, `navigation_mesh.cpp` 2, `navigation_agent_3d.cpp` 2, `navigation_obstacle_3d_editor_plugin.cpp` 2, `grid_map.cpp` 1 (`:2205`). A plain `grep get_debug_*_material(` also hits `shape_3d.cpp:126, 135` and `grid_map.cpp:1001`, but those are `SceneTree::get_debug_collision_material` | `kind: call_expression` + `field_expression` field regex `^(<15 getter names>)$` |
| V28 | NavigationServer2D keeps Colors only and includes core only (C10) | Confirmed; range refined | 14 `Color` fields at `navigation_server_2d.h:333-350` (report: 333-345); includes `:33-36`, all `core/` | `kind: field_declaration` type `^(Ref<.*Material.*>\|Color)$` (0 material refs) |
| V29 | Forward-declaration idioms at `scene_tree.h:48, 215-216`, `navigation_agent_3d.h:40, 118-119`; server ctor/dtor out of line at `:248, :355` (C10) | Confirmed | `class Material;` `scene_tree.h:48`, `Ref<Material>` `:215-216`; `class StandardMaterial3D;` `navigation_agent_3d.h:40`, `Ref<StandardMaterial3D>` `:118-119`; ctor `navigation_server_3d.cpp:248-353`, dtor `:355-363` | `kind: class_specifier` + `not: {has: {field: body, kind: field_declaration_list}}`; `kind: function_definition` |
| V30 | 31 includers of `navigation_server_3d.h` (29 non-test + 2 test) (§1.C10; "31" repeated in §3 #3) | **Refuted** (count) | 29 full-path includers **including** 2 tests (`tests/test_main.cpp`, `tests/servers/test_navigation_server_3d.cpp`), so 27 are non-test, plus the server's own `.cpp` (relative include): **30**. The other relative hits (`"3d/godot_navigation_server_3d.h"`, `"godot_navigation_server_3d.h"`) are a different header | `kind: preproc_include` path regex `^"servers/navigation_3d/navigation_server_3d.h"$`; `grep -rnE '#include ".*navigation_server_3d\.h"'` sweep |
| V31 | At least 12 includers use material types without a direct include (§3 #3, worker grep) | Confirmed; refined | 12, one of which is `navigation_server_3d.cpp` itself, the file that receives the include in the plan. 11 others: `csg_shape.cpp`, `grid_map.cpp`, 3 navigation editor plugins, `mesh_instance_3d.cpp`, 4 `scene/3d/navigation/*.cpp`, `navigation_mesh.cpp`. Whether they reach `material.h` another way is still only knowable by a build [?] | `kind: type_identifier` regex `^(Material\|BaseMaterial3D\|StandardMaterial3D\|ORMMaterial3D\|ShaderMaterial\|CanvasItemMaterial\|PlaceholderMaterial)$` minus files matching `preproc_include` `scene/resources/material\.h` |
| V32 | `RendererMaterialStorage` is pure-virtual with no `.cpp` (C3) | Confirmed | `servers/rendering/storage/material_storage.h:37-104`: 39 `virtual … = 0;` + virtual dtor. No `storage/material_storage.cpp`; the 8 `RendererMaterialStorage::` hits in `.cpp` files only name the nested `InstanceShaderParam` | `kind: field_declaration` regex `^virtual.*= 0;$` `inside` class `^RendererMaterialStorage$`; zero `.cpp` confirmed with `find` + `grep` |
| V33 | RD and GLES3 `Material` structs field-for-field identical except `shader_type` / `shader_mode`; RD `Shader` adds `mutex`, `embedded` (C3) | Confirmed | RD `material_storage.h:291-309`, GLES3 `:117-135`: 12 member declarations each, and `diff` of the extracted members gives exactly 1 line (`:296` `ShaderType shader_type` vs `:122` `RSE::ShaderMode shader_mode`). `Shader`: RD `:268-277` vs GLES3 `:76-83`; RD adds `Mutex *mutex`, `bool embedded`; `ShaderType type` vs `RSE::ShaderMode mode` | `kind: field_declaration` inside `struct_specifier` `^Material$`, then `diff` |
| V34 | MATERIAL API: RD 17 functions vs GLES3 16 (C3) | Confirmed; ranges refined | RD `:2432-2698` (17; `samplers_rd_*` and `*_data_request_function` follow up to `:2803`); GLES3 `:2436-2661` (16 = 15 + `get_texture_uniform_data`). RD-only: `_material_uniform_set_erased`, `material_get_shader_data` | top-level `kind: function_definition`, filtered by section markers |
| V35 | GLOBAL SHADER UNIFORM API: 619 vs 620 lines, 37 differing lines after namespace normalisation (C3) | Confirmed | RD `:1574-2192`, GLES3 `:1626-2245`; `diff` = 37 `<`/`>` lines in 16 hunks. Function sets: 18 vs 18; RD-only `global_shader_uniforms_get_storage_buffer`, GLES3-only `global_shader_parameters_get_texture` | text `diff` (not structural) + top-level `function_definition` names |
| V36 | `can_create_resources_async()`: GLES3 `false`, RD `true` (C3) | Confirmed | `rasterizer_gles3.h:125` (non-virtual inline, `false`); `renderer_compositor_rd.h:149` (`override`, `true`) | `kind: function_definition` declarator regex `^can_create_resources_async$` |
| V37 | `update_textures` signatures differ (RD `:96` vs GLES3 `:89`) (C3) | Confirmed | `renderer_rd/storage_rd/material_storage.h:96` (in `MaterialData` `:93-123`); `gles3/storage/material_storage.h:89` | `kind: field_declaration` + `function_declarator` `^update_textures$` |
| V38 | `RendererMeshStorage` template-method precedent (`mesh_storage.cpp:36+`; `mesh_storage.h:131` vs `171`) (C3) | Confirmed | 29 public `RendererMeshStorage::multimesh_*` definitions call `_multimesh_*`, starting at `mesh_storage.cpp:36`; `mesh_storage.h:131` `multimesh_allocate()` vs `:171` `_multimesh_allocate() = 0` | `kind: function_definition` with `all: [declarator regex ^RendererMeshStorage::multimesh_, has call ^_multimesh_]` |
| V39 | `remaps[]` `:4108-4142`; identical duplicate `:4109-4110`; self-map `:4121` unreachable (handled at `:4094`); unknown name → `WARN_PRINT` + `return true` `:4153-4154` (C4) | Confirmed | All anchors hold, inside `StandardMaterial3D::_set` (`material.cpp:4063-4156`). `uniq -d` over the table entries returns only the `flags_use_shadow_to_opacity` pair | `kind: declaration` with declarator regex `remaps`; `kind: initializer_list` entries; `kind: string_literal` `"params_depth_draw_mode"` (`:4094`, `:4121`) |
| V40 | 79 `*.compat.inc` files (C4) | Confirmed | 79 | `find -name '*.compat.inc'` (file count, not structural) |
| V41 | `_set` + `DISABLE_DEPRECATED` convention across 41 `scene/` files (C4; "41" repeated in §3 table) | Refined | 35 (report: 41) files have a `#if…DISABLE_DEPRECATED` block inside or around a `::_set` definition. 41 is the co-occurrence count. The extra 6 (`mesh_instance_3d.cpp`, `physical_bone_3d.cpp`, `animation_blend_space_{1d,2d}.cpp`, `control.cpp`, `window.cpp`) guard other code. 83 `scene/` files define `::_set` | `kind: function_definition` declarator regex `::_set\(` + `any: [has / inside preproc_ifdef\|preproc_if regex DISABLE_DEPRECATED]`; `grep -q DISABLE_DEPRECATED` for the 41 |
| V42 | BaseMaterial3D `_validate_property` (`:2595-2781`): 23× NONE unconditional (`:2663-2778`), 16× NO_EDITOR behind `is_editor_hint()` (`:2611, 2689`) (C6) | Refined | 23 NONE in total, but 21 (report: 23) are in `:2664-2778`. The others are `:2597` (ProjectSetting) and `:2604` (`DISABLE_DEPRECATED`). None is editor-gated (the ast-grep 0 was confirmed by `grep` over `:2611-2655, 2689-2709` = 0). 16 NO_EDITOR, all inside the `is_editor_hint()` blocks `:2611-2655`, `:2689-2709` | `kind: identifier` regex `^PROPERTY_USAGE_(NONE\|NO_EDITOR)$` ± `inside: if_statement` with condition regex `is_editor_hint`; `grep -o` count per range |
| V43 | `PROPERTY_USAGE_NO_EDITOR == PROPERTY_USAGE_STORAGE` (C6) | Confirmed | `core/object/property_info.h:125` (`STORAGE = 1 << 1` at `:94`) | `kind: enumerator` name regex |
| V44 | PPM: ~26 NONE, 3 NO_EDITOR (`:2157-2286`); CIM 1 NONE (`:229-231`) (C6) | Refined | PPM: 29 (report: ~26) NONE, 15 of them inside `is_editor_hint()`; 3 NO_EDITOR; `_validate_property` is `:2156-2289`. CIM: 1 NONE at `:231` (function `:229-233`); its NO_EDITOR count of 0 was confirmed by `grep` | same as V42 |
| V45 | Render-mode map assignments ~71 / ~69 / ~126 across 5 shader kinds (C2) | Refined | `scene_shader_forward_clustered.cpp` 64, `scene_shader_forward_mobile.cpp` 64, GLES3 `material_storage.cpp` 120 = 89 in 5 `ShaderData::set_code` (Scene 46, Sky 24, Canvas 11, TexBlit 6, Particles 2) + 31 in `MaterialStorage::MaterialStorage()` (`:1147`). The `grep -c '…['` counts agree | `kind: assignment_expression` + left `subscript_expression` regex `(render_mode_values\|render_mode_flags\|usage_flag_pointers\|render_mode_defines)$` |
| V46 | Generators emit 32 (BaseMaterial3D), 8 (CIM, `:86-116`) and 2 (PPM, `:200-202`) mode literals (C2) | Confirmed | BaseMaterial3D: 32 distinct `code +=` literals between `render_mode ` (`material.cpp:753`) and `;\n` (`:893`); CIM `:89-115` (8); PPM `:200`, `:202` | `kind: string_literal` `inside` `assignment_expression` regex `^code \+=`, filtered by range |
| V47 | `_particles_process` ranges; `:1400` is `convert_from_particles` (C7) | Confirmed (end lines off by 1) | `cpu_particles_2d.cpp:805-1198` (report: 805-1199), `cpu_particles_3d.cpp:759-1268` (report: 759-1269); `convert_from_particles` at `cpu_particles_2d.cpp:1400-1486` and `cpu_particles_3d.cpp:1460-1546` | `kind: function_definition` declarator regex `::(_particles_process\|convert_from_particles)$` |
| V48 | Enums and `CONVERT_PARAM` anchors (C7) | Refined | Enums `cpu_particles_2d.h:44-81` (report: 65-75), `cpu_particles_3d.h:45-84` (report: 52-80). `#define CONVERT_PARAM` at `gpu_particles_2d.cpp:590` (report: 524) and `gpu_particles_3d.cpp:746` (report: 683); the report cited the enclosing `convert_from_particles`. Reverse direction at `cpu_particles_2d.cpp:1463`, `cpu_particles_3d.cpp:1523` | `kind: enum_specifier` inside class `^CPUParticles(2D\|3D)$`; `kind: preproc_function_def` name `^CONVERT_PARAM$` |
| V49 | `material_editor_plugin.cpp:473-506`: 8 literals, `cast_to<StandardMaterial3D>` at `:479` (C9) | Confirmed | Literals at `:483-500` (`roughness_texture`, `roughness` ×3, `metallic_texture`, `metallic` ×3); cast `:479` | `kind: string_literal` in range; `kind: call_expression` regex `cast_to` |
| V50 | `"BaseMaterial3D,ShaderMaterial"` 11× in 5 files (C9) | Confirmed | `csg_shape.cpp` 6, `visual_instance_3d.cpp` 2, `mesh_instance_3d.cpp` 1, `primitive_meshes.cpp` 1, `mesh.cpp` 1; `grep` = 11 | `kind: string_literal` regex `^"BaseMaterial3D,ShaderMaterial"$` |
| V51 | Sibling hint strings at `tile_set.cpp:7188`, `canvas_item.cpp:1591`, `mesh.cpp:1791`, `gpu_particles_2d.cpp:984`, `gpu_particles_3d.cpp:903` (C9) | Confirmed; path refined | `tile_set.cpp` is `modules/tilemap/tile_set.cpp:7188`. A `scene/`-only ast-grep scan gives 4; `grep -rn` over the whole repo gives the 5th | `kind: string_literal` regex `^"(CanvasItemMaterial\|ParticleProcessMaterial),ShaderMaterial"$` |
| V52 | `_parse_range_hint` is file-static at `editor_properties.cpp:3901`; the PPM editor hand-parses (`:458-464`) (C9) | Confirmed | `static EditorPropertyRangeHint _parse_range_hint(…)` `editor/inspector/editor_properties.cpp:3901-3966`; `split(",")` `particle_process_material_editor_plugin.cpp:458`, `to_float()` `:459-461` | `kind: function_definition` declarator regex `^_parse_range_hint`; call regex `split\|to_float` |

### Findings that bear on the ranking (to be decided at the planning stage)

No result removes a candidate's structural basis. All three ranked candidates (C1, C8, C10) keep their current shape as described, and the reasons for C3 stay as recorded. The points below qualify arguments or figures quoted in §3. That section is deliberately left unchanged, so the planning session must weigh them.

1. **C1 (#1), "a concurrency fix has already landed in one copy only" (V15). To be decided at the planning stage.** Structurally, the race-safe "create outside the map lock, free the loser" block is identical in BaseMaterial3D and PPM. PPM's copy did not come from #105138. It came separately, via `5a30a7e7cd` (#102552, the shader baker PR). The "fixed in one copy only" argument therefore narrows to **CIM only**. Two readings:
   - **Weaker for C1:** the two in-scope copies (BaseMaterial3D, PPM) are already in sync on the concurrency fix.
   - **Stronger for C1:** the sync was achieved by hand-porting in an unrelated PR. That is the mechanism §Architecture Insights describes, and the two blocks are textually identical, so steps 2–3 of the incremental path are more mechanical than "M" suggests.
2. **C8 (#2), `texture_repeat` drift scope (V19, V20). To be decided at the planning stage.**
   - Label3D itself passes a literal `false` for `p_texture_repeat`, so the stale baker call diverges only from the SpriteBase3D path. The realised drift is narrower than "Sprite3D and Label3D", though still real.
   - §3 #2 lists `material.cpp:3047` as an "other caller"; it is the definition. The callers that need not change are just `root_motion_view.cpp:87`.
   - The mapping copy lives in `SpriteBase3D::draw_texture_rect`, shared with AnimatedSprite3D. A `SpriteBase3D`-level helper would therefore cover AnimatedSprite3D as well, which matters for the separate behaviour change §3 mentions.
3. **C10 (#3), includer count (V30, V31). To be decided at the planning stage.** §3 #3 says "31 includers". The verified figure is 30 (29 full-path including 2 tests, plus the server's own `.cpp`). Of the "at least 12" TUs that use material types without a direct include, one is `navigation_server_3d.cpp`, which receives the include anyway. So at most 11 other TUs can break, which slightly lowers the already-small cost. This does not change the order.
4. **C4 (not ranked), "41 files" in the §3 table (V41).** The structural count is 35. This does not affect its non-ranking.

### Not verified here

- Git and GitHub history claims (PR numbers, merge dates, review quotes) other than V15.
- CI-workflow line anchors (`linux_builds.yml`, `SConstruct`), the source's own counts that this report only cites, and the transitive-include question for C10, which still needs a build.

---

## Code References

- `scene/resources/material.cpp:100-124`: `_mark_ready` / `_mark_initialized`
- `scene/resources/material.cpp:2088-2113, 2134-2160 (report: 2134-2158)`: BaseMaterial3D race-safe shader create, flush outside the lock, `_queue_shader_change`
- `scene/resources/particle_process_material.cpp:1360-1405`: PPM create, flush under the lock, queue
- `scene/resources/canvas_item_material.cpp:58-151 (report: 58-80), 153-172 (report: 143-162), 235-237`: CIM unlocked `shader_map` access, flush, `get_shader_rid`
- `scene/resources/material.h:411, 417, 524`; `particle_process_material.h:153, 158, 204`; `canvas_item_material.h:81, 99`: `ShaderData` and mutexes
- `servers/rendering/dummy/storage/material_storage.cpp:40-41, 191-192`: the dummy compiler (empty actions) and its compile-error path
- `servers/rendering/renderer_rd/storage_rd/material_storage.cpp:1574-2192, 2430-2698 (report: 2430-2702)` vs `drivers/gles3/storage/material_storage.cpp:1626-2245, 2434-2661 (report: 2434-2650)`: twin sections
- `servers/rendering/storage/mesh_storage.cpp:36+`: the template-method precedent for shared renderer storage code
- `drivers/gles3/rasterizer_gles3.h:125`, `servers/rendering/renderer_rd/renderer_compositor_rd.h:149`: async resource creation, false vs true
- `scene/resources/material.cpp:4108-4156`: remaps table, duplicate, unreachable self-map, `return true`
- `core/object/property_info.h:125`: `NO_EDITOR == STORAGE`
- `editor/export/shader_baker/shader_baker_export_plugin.cpp:307-354`: baker defaults, alpha-cut copy, 10-argument calls
- `scene/3d/sprite_3d.cpp:167, 289-303`; `scene/3d/label_3d.cpp:388-398 (report: 387-398)`; `scene/resources/material.h:880`: the other copies and the factory signature
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
  | D9 / §1.6 "`cpu_particles_2d.cpp:1400-1470` re-implements PPM" | **Contradicted on the anchor.** That range is `convert_from_particles`; the simulation is `:805-1198` (report: 805-1199). The parity gap is deliberate (#79527), which answers the source's Open Question "Is the CPUParticles3D flag gap intentional?" |
  | D10 "Sprite3D/Label3D pass 12 arguments" | **Precised.** 11 value parameters plus `r_shader_rid`; the baker passes 10. |
  | D12 / §1.6 hint-string sibling locations | **Precised.** Locations corrected in §1.C9. The count of 11× in 5 files is supported. |
  | D13 "29 includers" | Supported: 29 full-path, of which 27 (report: 29) are non-test and 2 are tests; 30 (report: 31) including the server's own `.cpp`. |

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
- **Not verified with ast-grep in this pass:** the worker counts (C2 map-assignment lines, C6 PPM usage counts, the C4 compat-line heuristic, 12 transitive C10 includers) are grep-based. The ranking's structural claims are planned for `m4l4-3` ast-grep verification. *(Done at `d42f2deede`; see "Claim verification (ast-grep)". Corrected figures are marked `N (report: M)`.)*
- Nothing was built or run. No ADRs or design docs exist in the repo; all rationale comes from commits, PR bodies and review comments.
