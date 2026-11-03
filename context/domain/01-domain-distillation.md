---
title: "Domain distillation: Materials and their persistence (Godot Engine, scene/resources)"
created: 2026-11-02
type: domain-distillation
scope: "Material resources: authoring model, generated shaders, persistence/compatibility, renderer hand-off, and the satellites that copy material logic (particles, 2D-in-3D, shader baker, navigation debug)"
git_commit: a27e041bc3
engine_source_identical_to: 0f30f7d853
status: complete
---

# Domain distillation: Materials and their persistence

**Legend.** **[E]** evidence observed at the cited `file:line`. **[I]** inference drawn from evidence. **[?]** unknown: not established, and not a claim of absence.
Every `file:line` below was re-read for this document at `a27e041bc3`. Engine source has not changed since `0f30f7d853` (`git diff --stat 0f30f7d853 HEAD` touches only `context/`, `ast-grep/`, `node_modules/`, `package*.json`, `CLAUDE.md`, `RefactoringUserNotes.txt`). So the anchors in the two earlier research reports still hold, and this document reuses them only where it re-checked them.

---

## 0. Project context (Step 0)

### 0.1 Source documents found

| Kind | What exists | Used as |
|---|---|---|
| PRD / vision | **None.** `context/foundation/` holds only `README.md` (conventions); no `prd.md`, no `tech-stack.md` anywhere in the repo. | — |
| README | `README.md:9-17` (product statement), `:19-26` (open source, community-driven) | Product vision |
| Requirements proxy | `doc/classes/*.xml`, the class reference. CI regenerates its skeleton and `default=` values from the bindings (`--doctool` diff), while descriptions are written by hand. It is the only place where the engine states the *intended* behaviour of each type. | **Specification** ("the document") |
| Narrative / change history | `CHANGELOG.md` (1776 lines, 4.7 release, organised by area); `context/map/repo-map.md`; `context/changes/material-resources-flow-analysis/research.md`; `context/changes/refactor-opportunities/{research,plan,plan-brief}.md`; `RefactoringUserNotes.txt` | Decision history and earlier analyses |

**Limitation.** There is no product requirements document. Where this report says "the document", it means the class reference plus README. "Product goals" (§0.3) are **derived proxies**, not stated success criteria. Decisions are taken from git and PR history as recorded in the earlier research. No ADRs exist.

**Scope.** Godot is a 1.7 M LOC engine (`repo-map.md` §1). A whole-engine distillation would be shallow. This one covers the **material domain** across repo-map risk zones 1 and 2 ("Saving and loading scenes and resources", "Look of materials, particles and environment"). That is the area every prior change in `context/changes/` analysed. Other subdomains appear only where materials leak into them.

### 0.2 Stack and where the domain logic lives

C++ engine built with SCons. The layers follow `main/main.cpp` boot order (`repo-map.md` §1). For materials:

| Layer | Location | Role for materials |
|---|---|---|
| Domain model (resources) | `scene/resources/material.{h,cpp}`, `canvas_item_material.*`, `particle_process_material.*`, `shader.*` | Material types, their properties, generated shader text, shader cache, legacy remaps |
| Reflection / persistence | `core/object/{object,class_db}.*`, `core/io/resource*.{h,cpp}`, `scene/resources/resource_format_text.cpp`, `scene/property_utils.cpp` | Property-list reflection *is* the file format |
| Rendering contract | `servers/rendering/rendering_server.h`; implementations `servers/rendering/renderer_rd/storage_rd/material_storage.cpp`, `drivers/gles3/storage/material_storage.cpp`; test stub `servers/rendering/dummy/` | RID-identified material records, uniform buffers, shader compilation |
| Consumers (nodes) | `scene/3d/visual_instance_3d.cpp`, `mesh_instance_3d.cpp`, `sprite_3d.cpp`, `label_3d.cpp`, `cpu_particles_*.cpp`, `gpu_particles_*.cpp` | Hold a material, push its RID |
| Editor (UI) | `editor/inspector/*`, `editor/scene/material_editor_plugin.cpp`, `editor/editor_node.cpp`, `core/object/undo_redo.cpp` | Edit, undo, preview, convert, save |
| Export | `editor/export/shader_baker/shader_baker_export_plugin.cpp` | Pre-compile the shaders nodes will request |

### 0.3 Product goals used for classification (derived)

| ID | Goal | Source |
|---|---|---|
| G1 | **Look without code.** Users get a wide range of rendering features "without the need to write shader code". | `doc/classes/BaseMaterial3D.xml:7` |
| G2 | **Pay only for what you use.** "The cost for using the feature is only incurred when specified." | `BaseMaterial3D.xml:39` |
| G3 | **One project, many platforms and renderers.** "Games can be exported with one click to a number of platforms". Features are documented per renderer method. | `README.md:14-17`; `BaseMaterial3D.xml:491` |
| G4 | **Full control when needed.** ShaderMaterial "gives deeper control over the generated shader code". Users can also inherit `Material` in script/GDExtension. | `ShaderMaterial.xml:7`; `Material.xml:8` |
| G5 | **Saved work keeps working.** Resources are "saved on disk". The engine warns users to re-save "in order for it to continue working in future versions" and keeps compatibility class names. | `Resource.xml:7`; `scene/resources/material.cpp:226`; `scene/register_scene_types.cpp:1190, 1202` |
| NG1 | **Non-goal: CPUParticles feature parity with GPU particles.** A rendering maintainer on #79527 (2023-10-11): "We aren't porting all GPUParticles features over the CPUParticles anymore". | `context/changes/refactor-opportunities/research.md:303` |
| NG2 | **Non-goal (de facto): versioned per-type file migrations.** Default-skip saving is deliberate (f2e54057ae, 2018). Maintainers enforce "don't change defaults" case by case. | `refactor-opportunities/research.md:264-265` |

---

## 1. Ubiquitous Language (Step 1)

Code terms were collected from identifiers, enum names and comments, independently of the docs. "BRAK w kodzie" / "absent in docs" is stated only after the targeted search shown.

### 1.1 Shared terms (in documents and in code)

| Term | Definition (domain meaning) | Document source | Lives in code |
|---|---|---|---|
| **Resource** | Reference-counted, serializable data container. It can be nested and saved; loaded instances are cached by path. | `Resource.xml:7-9` | `core/io/resource.h:52` |
| **Material** | Abstract resource that colours and shades geometry. It carries `next_pass` and `render_priority`. | `Material.xml:4-7` | `scene/resources/material.h:38` |
| **ShaderMaterial** | Material defined by a user `Shader` plus per-material values for its uniforms. | `ShaderMaterial.xml:4-8` | `material.h:95` |
| **Shader** (resource) | User-authored shader program, with a **mode** (spatial, canvas_item, particles, sky, fog, texture_blit). | `ShaderMaterial.xml:35` | `scene/resources/shader.h:39`, modes `:45-53` |
| **Shader parameter** (uniform) | Named per-material value of a shader uniform. Exposed as property `shader_parameter/<name>`. | `ShaderMaterial.xml:15-30` | `material.cpp:208-212` (property path), `:422-454` (`set_shader_parameter`), cache `material.h:100` |
| **BaseMaterial3D / StandardMaterial3D / ORMMaterial3D** | The "no-code" 3D material. Standard uses separate AO/roughness/metallic textures; ORM packs them into one texture. | `BaseMaterial3D.xml:4-7`; `StandardMaterial3D.xml:4-7`; `ORMMaterial3D.xml:4` | `material.h:140, 913, 926` |
| **Feature** | Opt-in capability of BaseMaterial3D (e.g. height mapping). It costs GPU time only when enabled. | `BaseMaterial3D.xml:39` | `enum Feature` `material.h:209`; `set_feature` `material.cpp:2541-2549` |
| **Flag** | Optional on/off behaviour of BaseMaterial3D. One flag per `set_flag` call; flags are not bit-maskable. | `BaseMaterial3D.xml:47` | `enum Flags` `material.h:256`; `set_flag` `material.cpp:2507-2534` |
| **Texture slot** | A named texture input of BaseMaterial3D (albedo, normal, ORM, …). | `BaseMaterial3D.xml:316` (ORM) | `enum TextureParam` `material.h:147`; `set_texture` `material.cpp:2556-2569` |
| **Render priority** | Sort key for 3D materials, range −128…127. Higher draws in front, but never across the opaque/transparent split. | `Material.xml:58-69` | `material.cpp:73-82` |
| **Next pass** | A further material that renders the same object again. Draw order is not guaranteed. | `Material.xml:53-56` | `material.cpp:48-67` |
| **Stencil mode / stencil preset** | Outline/X-ray presets that automatically create and manage a next-pass material. | `BaseMaterial3D.xml:862-876` | `enum StencilMode` `material.h:331`; `_prepare_stencil_effect` `material.cpp:3185-3244`; marker meta `"_stencil_owned"` `:3189, 3199` |
| **CanvasItemMaterial** | Material for 2D canvas items; blend and lighting behaviour for textures. | `CanvasItemMaterial.xml:4-7` | `scene/resources/canvas_item_material.h:35` |
| **ParticleProcessMaterial** | The particle configuration (process shader) for GPU particles. Each **parameter** has min/max ranges and optional curves. | `ParticleProcessMaterial.xml:4-7` | `particle_process_material.h:46`; `enum Parameter` `:50-69`; `set_param_min/max/texture` `:417-423` |
| **CPUParticles** | CPU-simulated particle node, convertible from GPU particles. | `CPUParticles3D.xml:4-8` | `scene/3d/cpu_particles_3d.h:40`; `convert_from_particles` `cpu_particles_3d.cpp:1460` |
| **PlaceholderMaterial** | Stand-in material with no render path (`Material.create_placeholder`). | `Material.xml:39-43` | `material.h:933` (empty shader RID `:936`) |
| **Material override / overlay / surface override** | Per-node slots that replace or add a material on geometry. | `BaseMaterial3D.xml:866` (`material_overlay`) | `visual_instance_3d.h:181, 184`; `mesh_instance_3d.h:98` |
| **Local to scene** | The resource is duplicated for each scene instance. | `Resource.xml:162-165` | `core/io/resource.h:161` |
| **changed** (signal) | "Emitted when the resource changes, usually when one of its properties is modified." | `Resource.xml:182-184` | `emit_changed()`; in materials only at `material.cpp:415` |
| **Default value** | The value a property has on a fresh instance. Shown as `default=` in the class reference. | e.g. `BaseMaterial3D.xml:250` (`default="false"`) | `PropertyUtils::get_property_default_value` `scene/property_utils.cpp:80`; used to **skip saving** at `resource_format_text.cpp:2099-2103`, `resource_format_binary.cpp:2218-2222` |
| **Compatibility (legacy names)** | Old class and property names still load. | `material.cpp:226` (user-facing warning text) | `ClassDB::add_compatibility_class` `class_db.h:520`, uses `register_scene_types.cpp:1190, 1202`; `StandardMaterial3D::_set` `material.cpp:4062-4155`; ShaderMaterial prefixes `:214-231` |

### 1.2 Code-only terms (the model the code has but the documents never name)

Searched in `doc/classes/*.xml` for each identifier and for its plain-English paraphrase ("cache", "dirty", "key", "pending"). None of them is documented. They are the real mechanics of G2 and of synchronisation with the renderer.

| Code term | What it means | Code |
|---|---|---|
| **MaterialKey** | Bit-packed identity of a generated shader variant. Modes, stencil settings, a 32-bit feature mask and a 32-bit flag mask (BaseMaterial3D). PPM and CIM each define their own shape. | `material.h:359-409`; `particle_process_material.h:114-151`; `canvas_item_material.h:55-71` (a `union`) |
| **shader_map / ShaderData {shader, users}** | Process-wide, refcounted cache: one compiled shader per distinct MaterialKey. | `material.h:411-417`; `particle_process_material.h:153`; `canvas_item_material.h:81` |
| **dirty_materials / _queue_shader_change / flush_changes** | Deferred regeneration. Shader-key edits enqueue the material, and a SceneTree idle callback drains the queue. | `material.cpp:2134-2160`; registration `register_scene_types.cpp:807, 894, 927` |
| **Two channels: value vs shader-key** | A *value* edit (e.g. albedo) goes straight to the renderer as a uniform. A *shader-key* edit (feature, flag, mode, texture presence) regenerates the shader. | value `material.cpp:2162-2168`; key `:2533, 2548, 2568` |
| **init_state (UNINITIALIZED / INITIALIZING / READY)** | While a material is still loading, shader updates are suppressed. The first `get_rid()` promotes it to READY. | `material.h:47-51`; `material.cpp:100-124, 659-662, 3179-3183` |
| **pending_params** | Uniform values buffered until the renderer RID exists. | `material.h:537`; `material.cpp:2162-2168` |
| **param_cache / remap_cache** | ShaderMaterial's local store of uniform values and property-name → uniform-name map. | `material.h:99-100` |
| **materials_for_2d / get_material_for_2d** | Cache of StandardMaterial3Ds generated for 2D-in-3D nodes (Sprite3D, Label3D). | `material.h:637, 880`; `material.cpp:3047` |
| **Conversion (to ShaderMaterial)** | Turning a generated material into an editable ShaderMaterial by copying shader code and uniforms. | `editor/scene/material_editor_plugin.cpp:57`; `editor/plugins/editor_resource_conversion_plugin.h:36` |
| **Shader baking** | Export-time pre-compilation of shaders that nodes will request at runtime. | `shader_baker_export_plugin.h:51`; `.cpp:305-356` |
| **edited** | Editor flag set on a resource by every undoable property change; it drives "needs saving". | `core/object/undo_redo.cpp:399-407`; `core/object/object.h:763` |
| **PROPERTY_USAGE_STORAGE** | Marks a property as part of the saved file. | `core/object/property_info.h:94` |
| **Built-in resource** | A resource embedded in a scene file (empty path or `scene::id`), as opposed to a separate `.tres`. It decides which undo history and which save path apply. | `core/io/resource.h:147`; `editor/editor_undo_redo_manager.cpp:82`; `editor/editor_node.cpp:1867` |

### 1.3 Document terms absent in code

| Doc term | Doc source | Search | Finding |
|---|---|---|---|
| **PBR** ("Physically Based Rendering") | `StandardMaterial3D.xml:4`, `ORMMaterial3D.xml:4` | `grep -rniw PBR` and `physically.based` over `scene servers drivers` (`*.cpp`, `*.h`) | **BRAK w kodzie.** The model is implicit in parameter names (`metallic`, `roughness`). |
| **Transparent pipeline** | `BaseMaterial3D.xml:141` | `pipeline` in `material.cpp`: 0; renderer: `RENDER_LIST_ALPHA` `render_forward_clustered.h:81` ("used for transparent objects") | Same concept under a different name. In the renderer, "pipeline" means a GPU pipeline object (`pipeline_cache_rd.h:36`). See §1.4. |
| **(Shader) variants** | `Material.xml:48` ("including all variants") | `variant` in `material.cpp`: 0 as a shader concept; RD uses `ShaderVersion` (`scene_shader_forward_clustered.h:55`) | The scene side calls a variant a **MaterialKey**; the renderer calls it a **version**. |

### 1.4 Words that mean different things in different places (probable context boundaries)

| Word | Meaning A (context) | Meaning B (context) | Evidence |
|---|---|---|---|
| **Material** | Authoring resource with properties, saved to disk (**Material Authoring**) | Renderer record keyed by RID: shader pointer, params, uniform buffer (**Rendering**) | `material.h:38` vs `struct Material` in RD `material_storage.h:291` and GLES3 `material_storage.h:117` |
| **Shader / ShaderData** | `Shader` = user-authored program resource; scene-side `ShaderData` = cache entry `{RID, users}` (**Authoring**) | `Shader`/`ShaderData` = compiled program state inside the renderer (**Rendering**) | `shader.h:39`, `material.h:411` vs RD `material_storage.h:59, 268`; GLES3 `:52, 76` |
| **Parameter / param** | Shader uniform value, set immediately on the RID (**Authoring**, BaseMaterial3D/ShaderMaterial) | Particle simulation quantity with min/max range and curve (**Particle Simulation**) | `material.cpp:2162`, `:422` vs `particle_process_material.h:50-69, 417-423` |
| **Default** | ClassDB constructor value, which is also the persistence baseline: equal values are **not saved** (**Persistence**) | Shader uniform default from the shader code, used for revert, with no ClassDB default (**Authoring / ShaderMaterial**) | `resource_format_text.cpp:2099-2103` vs `material.cpp:362-385` (revert via `shader_get_parameter_default`, per the source research §1.4) |
| **Built-in** | Embedded in a scene file (**Persistence / Editor**) | Built-in shader variables and fragments (**Shading language**) | `resource.h:147` vs `ShaderIncludeDB.xml:16`; earlier research also calls BaseMaterial3D a "built-in material" (`refactor-opportunities/research.md:179`), a third meaning |
| **Variant** | Dynamic value type of the engine (**Core**) | Shader variant, i.e. compiled permutation (**Rendering**) | `core/variant/variant.h:94` vs `Material.xml:48` |
| **Pipeline** | Opaque vs transparent render pass ordering (**Docs / Rendering semantics**) | GPU pipeline-state object (**RenderingDevice**) | `BaseMaterial3D.xml:141` vs `pipeline_cache_rd.h:36` |
| **Flags** | BaseMaterial3D behaviour flags in the shader key | Sprite3D/Label3D *draw flags*; PPM *particle flags*; renderer *render_mode flags* | `material.h:256`; `sprite_3d.cpp:690-694`; `particle_process_material.h:73`; `shader_compiler.h:51-62` (per the refactor research §C2) |
| **changed** | Public `Resource.changed` signal (**Resource contract**) | `property_list_changed` (inspector refresh), `_shader_changed` (editor-only re-list), "dirty" (shader-key queue) | `Resource.xml:184`; `visual_instance_3d.cpp:225, 229`; `material.cpp:404-406, 464-466, 2150-2160` |

### 1.5 Bounded contexts that follow from §1.4

1. **Material Authoring:** material resources, properties, features/flags, stencil presets, conversion.
2. **Shader Variant Generation:** MaterialKey → generated text → refcounted shader cache, with deferred flush. A context inside Authoring that the code never names.
3. **Persistence & Compatibility:** property reflection as the file format, default-skip, legacy remaps, compatibility classes.
4. **Rendering (Material Storage):** RID records, uniform buffers, compilation, render modes. One implementation per graphics API.
5. **Editor Workflow:** inspector, undo/redo, the edited flag, preview, save routing (built-in vs external).
6. **Particle Simulation:** GPU process material vs CPU simulation, which has a deliberately smaller feature set.
7. **Export / Shader Baking:** pre-compiles the variants other contexts will request.
8. **Navigation Debug Visualisation** (outside the domain): owns 15 debug `StandardMaterial3D`s through the server header (`servers/navigation_3d/navigation_server_3d.h:36, 398-414`).

---

## 2. Subdomain classification (Step 2)

| Area | Class | Justification (goal) |
|---|---|---|
| Material Authoring model (BaseMaterial3D features/flags/modes, texture slots) | **Core** | It *is* G1. The reason the engine has a "no-code" material. |
| Shader Variant Generation (MaterialKey, generated text, shared cache) | **Core** | It delivers G2: a feature costs nothing unless it changes the key, and equal keys share one compiled shader. Without it G1 would cost a shader per material. |
| ShaderMaterial (custom shader + parameters) | **Core** | G4, the escape hatch. Conversion from BaseMaterial3D keeps G1 and G4 on one path. |
| Persistence & Compatibility of material files | **Supporting** (critical) | G5. It must be right, but it is engine-wide reflection, not material-specific advantage. Repo-map zone 1 says it is where breakage is silent. |
| Editor Workflow (inspector, undo, preview, save routing) | **Supporting** | Makes G1 usable. Generic UndoRedo is underneath it. |
| Rendering material storage (RD, GLES3) | **Supporting** | Realises G3 (same material on several renderers). Users never touch it. The per-API split is deliberate (`refactor-opportunities/research.md:204`). |
| Particle process material | **Supporting** | A specialised material for one node family. CPU parity is a non-goal (NG1). |
| 2D-in-3D materials + Shader baking | **Supporting** | G3 (export-time performance). It copies Core logic rather than owning any. |
| RID handles, refcounting, `SelfList`, mutexes, ClassDB reflection, UndoRedo | **Generic** | Infrastructure. Nothing material-specific. |
| Navigation debug materials | **Generic** (misplaced) | Debug visualisation. It reaches into the material domain only through an include (`navigation_server_3d.h:36`). |

---

## 3. Aggregate candidates and invariants (Step 3)

Status values: **Enforced** (the code makes the rule true), **Declared** (stated in a comment or doc, not checked), **Ignored** (the code does nothing about it), **Contradicted** (code does the opposite).

### A1. BaseMaterial3D: root of the "no-code material" (owns its stencil-managed next pass)

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A1.1 | After a shader-key edit settles, the material's shader corresponds to its current features/flags/modes. | `BaseMaterial3D.xml:39, 47` | **Enforced (eventually).** It goes through the dirty list and idle flush, or synchronously on `get_rid()`. | `material.cpp:2533, 2548, 2150-2160, 2134-2148, 3179-3183, 664-667` |
| A1.2 | Height mapping is ignored when UV1 triplanar is on. | `BaseMaterial3D.xml:252` | **Enforced** | `material.cpp:1510, 1525` |
| A1.3 | `uv1/uv2_triplanar_sharpness` ∈ [0, 150]. | `BaseMaterial3D.xml:468, 484` | **Enforced** (clamp) | `material.cpp:2810-2814` (uv1), `:2838` (uv2) |
| A1.4 | `particles_anim_enabled` is "always enabled" with `BILLBOARD_PARTICLES`. | `BaseMaterial3D.xml:320` | **Enforced only when `DISABLE_DEPRECATED` is not defined.** The doc says "always". | `material.cpp:742-745` |
| A1.5 | The stencil-owned next pass renders at `owner.render_priority + 1`, so the owner must be below `RENDER_PRIORITY_MAX`. | `BaseMaterial3D.xml:866, 870` ("automatically applied"); the rule itself is in code `material.cpp:3262-3265` | **Contradicted after setup.** It is computed only in `set_stencil_mode` (the only caller of `_prepare_stencil_effect`, `:3268`). `Material::set_render_priority` is non-virtual (`material.h:82`) and never refreshes the stencil pass (`material.cpp:73-82`). Raising the owner's priority afterwards, including to 127, leaves the pass stale and is not rejected. | `material.cpp:3212, 3227, 3262-3268, 73-82` |
| A1.6 | Unknown property names are not accepted: `_set` returns `false` "if the property should be handled normally". | `Object.xml:301` | **Contradicted** for StandardMaterial3D. With deprecated code compiled in, *any* unmatched name hits `WARN_PRINT(...) ; return true;`. | `material.cpp:4062, 4153-4154` |
| A1.7 | A property edit emits `changed`. | `Resource.xml:184` | **Ignored.** BaseMaterial3D never calls `emit_changed`. Renderer sync relies on the shared RID only. | `grep emit_changed scene/resources/material.{h,cpp}` → only `material.cpp:415` (ShaderMaterial) |

### A2. ShaderMaterial: custom shader plus its parameter values

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A2.1 | Each material holds its own uniform values; the shader may be shared. | `ShaderMaterial.xml:8` | **Enforced** | `param_cache` per instance, `material.h:100`; `material.cpp:422-454` |
| A2.2 | A parameter name must match a uniform exactly. | `ShaderMaterial.xml:28` | **Declared, not validated.** Any name is cached and pushed. | `material.cpp:430-434` |
| A2.3 | A stored parameter value survives loading. | `Resource.xml:7` (resources are saved and reloaded) | **Contradicted when the shader is not yet set.** The property path `shader_parameter/<x>` is rejected (`return false`) unless `shader.is_valid()`. The method path `set_shader_parameter` accepts the same value without a shader. Loading uses the property path. | `material.cpp:200-201, 234` vs `:422-454`; load = `Object::set` per property (source research §1.2 step 30) |
| A2.4 | `changed` fires for `shader` changes only in the editor. | `ShaderMaterial.xml:9` | **Contradicted.** `emit_changed()` is unconditional. Only the *signal connection* is editor-gated. | `material.cpp:394-406` vs `:415` |

### A3. Material (base): pass chain and priority

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A3.1 | The next-pass chain is acyclic. | `material.cpp:50` (error message); doc implies a finite chain, `Material.xml:54` | **Enforced** | `material.cpp:49-51` |
| A3.2 | `render_priority` ∈ [−128, 127]. | `Material.xml:65-69` | **Enforced at the resource.** At the renderer boundary it is **inconsistent**: GLES3 range-checks, RD does not. | `material.cpp:74-75`; `drivers/gles3/storage/material_storage.cpp:2579-2580` vs `servers/rendering/renderer_rd/storage_rd/material_storage.cpp:2619-2627` |

### A4. Generated Shader Cache (one per material family): the unnamed Core aggregate

Consistency boundary: the static `shader_map` of a material family. Its consistency is shared by every instance of that family.

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A4.1 | Exactly one compiled shader per distinct MaterialKey; `users` equals the number of materials on that key; freed at 0. | Code only: comments `material.cpp:2088-2104`, `:675`. Doc proxy G2 (`BaseMaterial3D.xml:39`) | **Enforced** in BaseMaterial3D (`material.cpp:669-695, 2088-2113, 4039-4056`) and PPM (`particle_process_material.cpp:174-177, 1360-1381, 2847-2850`) | — |
| A4.2 | Cache access is thread-safe (materials are created on loader/worker threads). | `material.cpp:2088-2090` (deadlock comment) | **Enforced** in BaseMaterial3D and PPM. **Ignored** in CanvasItemMaterial, which reads and writes `shader_map` with no lock and creates with `users = 1` and no race handling. | `canvas_item_material.cpp:58-79, 142-148, 235-237` |
| A4.3 | All families follow the same cache rules. | #91630 "consistent across material types" (`refactor-opportunities/research.md:139`) | **Declared, drifting.** There are three hand-kept copies with different lock scope (`material.cpp:2134-2148` vs `particle_process_material.cpp:1386-1393` vs CIM), different init (`canvas_item_material.cpp:292` vs `material.cpp:661`, `particle_process_material.cpp:162`) and different RID creation (eager `canvas_item_material.cpp:284`, `particle_process_material.cpp:2759`; lazy `material.cpp:3179-3183`). | as cited |
| A4.4 | The key never overflows its layout. | `particle_process_material.h:72` ("make sure not to overflow the size of the MaterialKey") | **Declared only.** No `static_assert` in any of the three headers (grep: 0). BaseMaterial3D has 7 flag bits left (source research D14). | `particle_process_material.h:72`; `material.h:392-393` |

### A5. Persisted Material (the saved file as a contract)

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A5.1 | Saving and reloading reproduces the material. | `Resource.xml:7`; G5 | **Enforced only by convention.** Properties equal to the *current* ClassDB default are not written, so a later default change silently alters old files. The guard is the CI `--doctool` diff plus maintainer review (NG2). | `resource_format_text.cpp:2099-2103`; `resource_format_binary.cpp:2218-2222` |
| A5.2 | What is saved depends only on the material. | — (implied by A5.1) | **Contradicted.** `emission_intensity` loses `STORAGE` when a *project setting* is off. The doc says only "available when" the setting is on. | `material.cpp:2596-2597`; `BaseMaterial3D.xml:222` |
| A5.3 | Legacy names migrate or fail visibly. | `material.cpp:226` (warn + re-save) | **Partially.** ShaderMaterial prefixes warn and remap (`:214-231`). StandardMaterial3D swallows unknown names (A1.6). The remap table has a duplicate entry (`:4109-4110`) and an unreachable self-map (`:4121`, already handled at `:4094`). PPM and CIM have no remap path at all (source research D4). | as cited |
| A5.4 | No material test pins any of the above. | — | **Ignored.** 0 files in `tests/` mention any concrete material class (grep re-run: 0). | `grep -rl "StandardMaterial3D\|ShaderMaterial\|…" tests/` → 0 |

### A6. 2D-in-3D material request (Sprite3D / Label3D → `get_material_for_2d`)

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A6.1 | The export baker pre-builds exactly the variants that nodes request at runtime. | `shader_baker_export_plugin.cpp:312` ("These must match the defaults set by Sprite3D/Label3D"), `:333` ("must follow the logic in Sprite3D::draw_texture_rect()") | **Contradicted.** The baker calls the factory with 10 arguments, so `p_texture_repeat` is always `false`. Sprite3D computes and passes it, while Label3D passes literal `false`. The baker casts only `Sprite3D`, so AnimatedSprite3D (also a `SpriteBase3D`) is skipped [I]. Node properties are read by string name. | baker `:307, 313-321, 323-331, 349, 354`; `sprite_3d.cpp:167, 303`; `label_3d.cpp:398`; signature `material.h:880` |
| A6.2 | The alpha-cut → transparency mapping is a single rule. | Same comments | **Declared; 3 copies.** Label3D's copy is deliberately "at least ALPHA". | `sprite_3d.cpp:289-299`; `label_3d.cpp:388-395`; baker `:334-345` |

### A7. Particle process material vs CPUParticles

| # | Invariant | Source | Status | Evidence |
|---|---|---|---|---|
| A7.1 | CPUParticles provides "the same functionality" as GPU particles. | `CPUParticles3D.xml:8`, `CPUParticles2D.xml:8` | **Contradicted, deliberately** (NG1). PPM has 6 particle flags, CPUParticles3D has 3. | `particle_process_material.h:73-81` vs `cpu_particles_3d.h:68-73` |

---

## 4. Model vs code divergences (Step 4)

"Fix" column: **code**, **document**, or **decision** (owner must say which side is right). "Document" is used only where a later decision can be cited.

| # | The document says (X) | The code does (Y) | Evidence | Fix |
|---|---|---|---|---|
| M1 | `changed` is emitted for `shader` changes "only in editor" (`ShaderMaterial.xml:9`). | Emits on every `set_shader`, in any build. Only the connection to `shader->changed` is editor-gated. | `material.cpp:394-406, 415` | **Decision.** The comment at `:391-393` explains the editor gate for the *connection* only. No source says which behaviour of `emit_changed` is intended. |
| M2 | A resource emits `changed` "usually when one of its properties is modified" (`Resource.xml:184`). ShaderMaterial documents its exception "for performance reasons" (`ShaderMaterial.xml:9`). | BaseMaterial3D, CanvasItemMaterial and ParticleProcessMaterial emit `changed` for no property. Their docs mention no exception. | `material.cpp:415` is the only `emit_changed` in `material.cpp`, and the other two files have none (grep) | **Decision.** Either document the same performance exception for these classes or emit. Adding emission is a behaviour change. |
| M3 | CPUParticles "provides the same functionality" as GPU particles (`CPUParticles3D.xml:8`, `CPUParticles2D.xml:8`). | Deliberately a lighter subset: 3 vs 6 particle flags. | `cpu_particles_3d.h:68-73` vs `particle_process_material.h:73-81` | **Document.** Later decision: #79527 (2023-10-11), "We aren't porting all GPUParticles features over the CPUParticles anymore" (`refactor-opportunities/research.md:303`). |
| M4 | The stencil next pass is "automatically applied" (`BaseMaterial3D.xml:866, 870`). The code's own rule is "priority + 1, so the owner must be below MAX" (`material.cpp:3262-3265`). | The +1 is applied only when `stencil_mode` is set. Later owner priority changes don't propagate and aren't rejected. | `material.cpp:73-82, 3212, 3227, 3268`; `material.h:82` (non-virtual) | **Code.** The rule is already written in code and is broken by a second entry point. It is a behaviour change, so it is its own change, not a refactor. |
| M5 | `particles_anim_enabled` is "always enabled" with `BILLBOARD_PARTICLES` (`BaseMaterial3D.xml:320`). | Only when `DISABLE_DEPRECATED` is undefined. | `material.cpp:743-745` | **Decision.** Whether `deprecated=no` builds are meant to drop this. |
| M6 | `_set` returns `false` for properties it does not handle (`Object.xml:301`). The user-facing compatibility promise is to warn and keep working (`material.cpp:226`). | `StandardMaterial3D::_set` returns `true` for **any** unmatched name, with a misleading "3.x remapped parameter not found" warning. | `material.cpp:4153-4154` | **Code.** It contradicts the Object contract it overrides. Earlier research classifies it as accidental [I] (`refactor-opportunities/research.md:242`). Behaviour change, so a separate change. |
| M7 | Resources are saved and reloaded (`Resource.xml:7`). ShaderMaterial parameter values belong to the material (`ShaderMaterial.xml:8`). | `shader_parameter/*` set through `Object::set` before `shader` is valid is dropped, while `set_shader_parameter` accepts it. | `material.cpp:200-201, 234` vs `:422-454` | **Decision.** It matters only if a saved file can list parameters before `shader` [?]. See Q3. |
| M8 | A parameter name "must match the name of the uniform in the code exactly" (`ShaderMaterial.xml:28`). | Not validated: unknown names are cached and pushed to the renderer silently. | `material.cpp:430-434, 450-451` | **Decision.** Is the note a user warning, or a contract the setter should check? |
| M9 | `render_priority` range −128…127 (`Material.xml:65-69`). | Checked by `Material` and GLES3; not by RD storage. | `material.cpp:74-75`; GLES3 `material_storage.cpp:2579-2580`; RD `:2619-2627` | **Decision** (renderer owner). Is the RS API a public contract that must check, or is the resource the only gate? |
| M10 | `emission_intensity` is "only available when" physical light units are on (`BaseMaterial3D.xml:222`). | It also stops being **saved** when the setting is off. The stored file depends on project settings. | `material.cpp:2596-2597` | **Decision.** Is "unavailable" meant to include "not persisted"? |
| M11 | The baker's defaults and mapping "must match" Sprite3D/Label3D (`shader_baker_export_plugin.cpp:312, 333`). | They don't: `texture_repeat` is dropped and AnimatedSprite3D is skipped [I]. | `:307, 349, 354`; `sprite_3d.cpp:167, 303` | **Code.** The drift is dated: the baker merged 2025-05-28 and #98122 added `p_texture_repeat` on 2025-12-02 without touching it (`refactor-opportunities/research.md:105-107`). The plan's C8 covers the refactor. Pre-baking the missing variant is a behaviour change. |
| M12 | Material families behave "consistently" (#91630, `refactor-opportunities/research.md:139`). Cache access must avoid races (`material.cpp:2088-2090`). | The CanvasItemMaterial cache is unlocked and has no race handling. | `canvas_item_material.cpp:58-79, 142-148, 235-237` | **Code.** Bug fix, out of scope for the C1 refactor per `plan-brief.md` "Out of scope". |
| M13 | The stencil next pass: "Any manual changes made to `next_pass` will be lost" (`BaseMaterial3D.xml:866`). | A user-set `next_pass` is **preserved**, chained behind the stencil pass (`material.cpp:3197-3201`) and restored on disable (`:3188-3191`). Only edits to the stencil-owned pass's own properties are overwritten (`:3209-3237`). | as cited | **Decision / clarify.** The doc may mean the owned pass. Ask before rewording. |

---

## 5. Refactor ranking (Step 5)

**Value** = how close the invariant is to Core goals G1/G2/G4. **Risk** = how weakly it is enforced today, with no tests anywhere (A5.4). **Kind** says whether the adequate fix is a structural refactor (behaviour unchanged), a behaviour change, or a decision. That matters because the repo's hard rule keeps refactors behaviour-neutral.

| Rank | Candidate | Value | Risk (enforcement) | Kind | Done when… |
|---|---|---|---|---|---|
| **#1** | **A4 Generated Shader Cache** | High: Core (G2). Every BaseMaterial3D/PPM/CIM instance depends on it. | High: 3 hand-kept copies; drifting lock, init and RID policy; one copy unlocked; 0 tests; fixes reached copies by separate PRs (#105138, #102552). | **Refactor** (extract one cache unit), then a separate CIM bug fix | `grep -rn "users--" scene/resources/` finds the refcount-release code in **one** file (today: `material.cpp:673, 4045`, `particle_process_material.cpp:174, 2847`, `canvas_item_material.cpp:65, 301`), **and** a `tests/scene/test_material_shader_cache.cpp` that asserts equal keys → same shader RID passes in the TSan CI job. |
| #2 | **A1 BaseMaterial3D** (stencil pass A1.5, unknown names A1.6) | Highest: Core (G1) | Medium: most rules are enforced; two are contradicted | **Behaviour change** (two small, separate changes) | A test that sets `stencil_mode = OUTLINE`, then `render_priority = 5`, reads `next_pass.render_priority == 6`. A second test asserts `StandardMaterial3D.set("no_such_property", 1)` reports `valid == false`. |
| #3 | **A2 ShaderMaterial** (load order A2.3, `changed` A2.4) | High: Core (G4) | Medium: two paths disagree; the doc contradicts the code | **Decision**, then a behaviour change or a doc fix | A `.tres` with `shader_parameter/x` written **before** `shader` loads with `get_shader_parameter("x") == value`. If Q3 shows that order is never produced, a test proves the saver always writes `shader` first. |
| #4 | **A6 2D-in-3D material request** | Medium: Supporting (G3, export) | High: contradicted and dated drift | **Refactor** (one typed params source; plan's C8), then a separate behaviour change for missing variants | `grep -c 'properties\["' editor/export/shader_baker/shader_baker_export_plugin.cpp` returns 0 (today: 9 hard-coded defaults at `:313-321` plus by-name reads), and every `get_material_for_2d` call outside `root_motion_view.cpp` passes the same params type. |
| #5 | **A5 Persisted Material** | High: G5 | Highest: convention-only; silent migrations; setting-dependent storage | **Decision** (file-format contract, NG2). Not refactorable without changing saved files. | A save → load round-trip test over every `STORAGE` property of StandardMaterial3D, ORMMaterial3D, ShaderMaterial, CanvasItemMaterial and ParticleProcessMaterial passes for both values of `use_physical_light_units` (0 such tests today). |
| #6 | **A3 Material base** | Medium | Low: enforced at the resource; only the RS boundary differs | **Decision** (renderer contract) | `RS.material_set_render_priority(rid, 128)` produces the same result (error and unchanged priority) on RD and on GLES3. |
| #7 | **A7 CPUParticles parity** | Low: non-goal NG1 | — (doc stale) | **Document** | `grep -n "same functionality" doc/classes/CPUParticles*.xml` returns nothing. |

### Why #1 is A4 (Generated Shader Cache)

- **It is the Core concept the model does not name.** G2 ("cost only when specified") is delivered entirely by MaterialKey → shared, refcounted shader. Yet the concept appears nowhere in the documents (§1.2). It exists as three differently shaped copies (§3 A4.3). The domain has one rule and the code has three implementations of it.
- **It is the weakest-enforced Core invariant that can be fixed without changing behaviour.** A1 has higher value but is mostly enforced, and its two broken rules are behaviour changes. A5 is weaker, but its fix is a file-format decision (NG2). A4's two in-sync copies (BaseMaterial3D, PPM) can merge with identical semantics. The CIM gap is a separately scoped bug fix.
- **It can be guarded first.** `get_rid()` / `get_shader_rid()` run `_update_shader()` synchronously (`material.cpp:3179-3183`). All three `flush_changes()` are public statics (`register_scene_types.cpp:807, 894, 927`). The dummy renderer really compiles generated code (`refactor-opportunities/research.md:102`). So a characterization test can pin RID sharing and release before the first structural edit.
- **This agrees with the existing plan's C1** (`plan-brief.md`), which was reached from a debt inventory, not from the domain model. This distillation adds two things the plan does not state. First, A1.5, A1.6, A2.3 and A2.4 are contradicted invariants with no plan; they should become their own behaviour changes. Second, the persistence contract (A5) carries the highest risk on the map but needs an owner's decision, not a refactor.

### Open questions (each answerable in minutes by the named role)

| # | Question | Who knows |
|---|---|---|
| Q1 | Is `emit_changed()` in `ShaderMaterial::set_shader` meant to fire outside the editor (code), or only inside it (doc)? (M1) | Materials/rendering maintainer (repo-map zone 2 first contact) |
| Q2 | Should the stencil-owned next pass follow later `render_priority` changes, or should `render_priority` be locked while a stencil preset is active? (M4) | Author/reviewer of the stencil presets feature (materials maintainer) |
| Q3 | Can `ResourceFormatSaverText` / binary ever write `shader_parameter/*` before `shader` for a ShaderMaterial? (M7) | Resource-format maintainer (repo-map zone 1 first contact) |
| Q4 | Is not emitting `changed` on BaseMaterial3D/CIM/PPM value edits the same deliberate performance trade-off as ShaderMaterial's? (M2) | Materials/rendering maintainer |
| Q5 | Is the RenderingServer material API a contract that must range-check `render_priority`, or is `Material` the only gate? (M9) | Renderer maintainer (repo-map zone 3 first contact) |
| Q6 | In `deprecated=no` builds, is dropping the forced `particles_anim` for `BILLBOARD_PARTICLES` intended? (M5) | Build/release maintainer |
| Q7 | Does "only available when `use_physical_light_units` is enabled" intend "not saved" as well? (M10) | Materials/rendering maintainer |
| Q8 | Does "manual changes to `next_pass` will be lost" refer to the stencil-owned pass's own properties? (M13) | Docs writer for BaseMaterial3D / stencil feature author |

---

## Method and coverage

- **Read in full:** `README.md`; `context/map/repo-map.md`; both research reports and the plan brief under `context/changes/`; `RefactoringUserNotes.txt`; `doc/classes/{Material,ShaderMaterial}.xml`.
- **Read in part (targeted):** `BaseMaterial3D.xml`, `Resource.xml`, `Object.xml`, `CPUParticles{2D,3D}.xml`, `StandardMaterial3D.xml`, `ORMMaterial3D.xml`, `CanvasItemMaterial.xml`, `ParticleProcessMaterial.xml`, `ResourceSaver.xml`.
- **Code re-read for every anchor cited:** `material.{h,cpp}`, `canvas_item_material.{h,cpp}`, `particle_process_material.{h,cpp}`, `resource_format_text.cpp`, `resource_format_binary.cpp`, `undo_redo.cpp`, `register_scene_types.cpp`, `visual_instance_3d.{h,cpp}`, `sprite_3d.cpp`, `label_3d.cpp`, `shader_baker_export_plugin.cpp`, both `material_storage.{h,cpp}`, `navigation_server_3d.h`, `cpu_particles_3d.h`.
- **Not done:** `CHANGELOG.md` was used only for structure, not mined entry by entry. Nothing was built or run. Git and PR history claims (PR numbers, dates, quotes) come from the earlier research and were not re-fetched. The shader code-generation body (`material.cpp:697-2085`) was not read beyond the lines cited.
