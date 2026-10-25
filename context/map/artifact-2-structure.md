# Artifact 2 — Structure (dependencies, entry points, cycles, local centers)

> Draft evidence report for the Project Map. Not the final map — see `repo-map.md` (not yet written).

| | |
|---|---|
| Repository | Godot Engine (`master`, HEAD `6765a18ca8`) |
| Primary tool | [`tomtom-international/cpp-dependencies`](https://github.com/tomtom-international/cpp-dependencies) @ `fe61df0` (2026-01-13), built from source in a throwaway `gcc:14` podman container, run offline (`--network=none`) against a read-only mirror |
| Scope | 3 843 C/C++/ObjC files in `core/ scene/ servers/ editor/ modules/ platform/ drivers/ main/ tests/`; `thirdparty/` excluded (vendored) |
| Raw evidence | `context/map/evidence/structure/` — `full.dot` (component graph), `cycles.dot`, `outliers.txt`, `ambiguous.txt`, `structure.json` + `structure.py` (SCC / layering / fan-in), `upward.json` + `upward.py` (file-level upward includes with their `#if` guards, header fan-in) |
| Polyglot evidence (§10) | `context/map/evidence/structure/polyglot/` — `glsl.*` (shader graph), `bridges.*` (JNI / C# interop / Emscripten / Swift), `scons.*` (build graph, SCons guards, generators), `managed.*` (Java/Kotlin + C# internal graphs), `lang_activity.*` (per-language activity in the artifact-1 window). Each `*.py` is stdlib-only, re-runnable as `python3 -I <script> <repo_root> <out.json>`; each has a `*-findings.md` |

## 1. Method and its limits

**Components.** `cpp-dependencies` treats every folder with a `CMakeLists.txt` as a component. Godot builds with SCons, so I made a scratchpad copy of the source files and added a stub `add_library()` at the **same folder level as artifact 1**: each top-level dir, each of its subfolders, and one level deeper for `servers/rendering/*`, `editor/scene/*`, `editor/inspector/*`, `scene/gui/*`. The result has **164 components** (named `core.object`, `scene.gui`, `servers.rendering.renderer_rd`, …). The repo itself was not modified.

**What an edge means.** A→B means some file in A `#include`s a file in B. Godot always includes from the repo root (`#include "core/object/object.h"`), so resolution is unambiguous. The only 4 ambiguous includes (`platform_config.h`, `platform_egl.h`, `platform_gl.h`, …) are picked by the build per platform, which is by design.

**Limits (important for reading the numbers):**
- The scan is **textual and preprocessor-blind**: includes inside `#ifdef TOOLS_ENABLED`, `#ifdef DEBUG_ENABLED` or platform guards count as edges, and so do files that SCons only compiles in editor builds (e.g. `modules/gdscript/language_server/`). I added my own guard-aware pass (`upward.py`) to classify each upward include; see §4.
- Generated headers (`*.gen.h`, shader `.glsl.gen.h`, `register_module_types`, doc data) don't exist in an unbuilt tree, so includes of them are silently dropped (328 includes). *Update (§10.1, §10.4):* the 107 shader includes were recovered and all stay inside their component; the other 221 were attributed to their generator families, but what those headers depend on is still **unknown**.
- Only compile-time (`#include`) coupling is captured. Runtime coupling through `ClassDB`, singletons (`Engine::get_singleton()->...`), signals and `Callable` is invisible here, and it is a large part of how Godot actually wires itself.

## 2. Intended architecture (from the code, not assumed)

The intended layering is spelled out in the engine's boot sequence in `main/main.cpp` (`Main::setup`, line 984ff):

```
register_core_types()            :704   → initialize_modules(CORE)
register_server_types()          :755   → initialize_modules(SERVERS)
register_scene_types()           :787
register_driver_types()          :788   → initialize_modules(SCENE)
register_editor_types()          :797   → initialize_modules(EDITOR)
register_platform_apis()         :804
```

This document therefore assumes the rank **core < drivers ≈ servers < scene < modules < editor < platform < main/tests**. Drivers *implement* interfaces declared in servers (`RenderingDeviceDriver`, `AudioDriver`, `DisplayServer`), so `drivers → servers` is expected. Modules plug in at **four initialization levels** (core / servers / scene / editor) and may legitimately reach up to the level they register at.

## 3. Entry points

| Kind | Entry | File |
|---|---|---|
| Desktop executable | `main()` | `platform/linuxbsd/godot_linuxbsd.cpp:70`, `platform/macos/godot_main_macos.mm:41`, `platform/windows/godot_windows.cpp:138` (→ `widechar_main` :68), `platform/windows/console_wrapper_windows.cpp:42` |
| Mobile / XR | Swift `@main` → ObjC `GDTAppDelegate*` → `addService:` → shared `godot_app_delegate_service_apple_embedded.mm:86` → `apple_embedded_main()` | `platform/ios/app_ios.swift:33`, `platform/visionos/app_visionos.swift:302` → `platform/ios/main_ios.mm:44`, `platform/visionos/main_visionos.mm:44` (full chain in §10.2) |
| Android | Java/Kotlin host (`:app` / `:editor` Gradle projects on top of `:lib`) → JNI `GodotLib_initialize / _setup / _step` | `platform/android/java_godot_lib_jni.cpp:172 / 199 / 344`; 77 JNI downcalls, 175 upcalls (§10.2) |
| Web | `godot_web_main()` (Emscripten), `main()` | `platform/web/web_main.cpp:134`, `platform/web/web_runtime.cpp:33` |
| Embedding (LibGodot) | `libgodot_create_godot_instance()` | `core/extension/libgodot.h:60`, `core/extension/godot_instance.cpp` |
| Engine lifecycle (called by all the above) | `Main::setup` → `setup2` → `start` → `iteration` (per frame) → `cleanup` | `main/main.cpp:984 / 3123 / 4050 / 4961 / 5260` |
| Plug-in surfaces | 56 × `modules/*/register_types.cpp`; GDExtension loader | `core/extension/gdextension*.{h,cpp}`, `core/extension/gdextension_interface*` |

All 7 platform components depend on `main` (`platform.* → main`). `main` itself has the 2nd-highest fan-out in the graph (46 components): it is the composition root.

## 4. Cycles

### 4.1 Headline

`cpp-dependencies --stats`: **164 components, 611 public + 1 654 private dependencies; 101 components are part of cycles.** All 101 form **one strongly connected component** that spans every layer:

| Layer | Components in the big SCC |
|---|---:|
| editor | 27 |
| drivers | 17 |
| servers | 17 |
| core | 15 (all of core) |
| modules | 10 (gdscript, mono, visual_shader, tilemap, jsonrpc, glslang, svg, zip, texture_streaming, visionos_xr) |
| scene | 10 (all of scene) |
| platform | 3 (android, windows, visionos) |
| main, tests | 1 each |

### 4.2 What actually holds it together (edge-removal experiment)

| Edges removed from the graph | Resulting SCC sizes |
|---|---|
| none | **101** |
| only the 11 upward edges *out of `core`* | 82 + 15 — **core separates from everything else** |
| all upward edges between layers (keeping `drivers → servers`) | 27 (editor) · 17 (servers + 3 drivers) · 15 (core) · 10 (scene) |
| keep only edges inside a layer | 27 · 15 · 14 · 10 |

Reading: **the cross-layer cycle comes from a handful of back-edges, not from systematic misuse.** Inside each layer, though, components are fully entangled: every subfolder of `core`, `scene`, `servers` and `editor` reaches every other one in its layer. At folder level each layer behaves as one unit.

### 4.3 The back-edges, file by file

Classified by `upward.py` according to the preprocessor guard around each include. "Unguarded" means the edge exists in **every** build configuration.

**core → upper layers (11 component edges; 5 unguarded includes)**

| Include | Guard | Note |
|---|---|---|
| `core/io/resource.cpp:39` → `scene/main/node.h` | none | `Resource` knows about `Node` (local-to-scene resources). |
| `core/io/resource_format_binary.cpp:41-42` → `scene/property_utils.h`, `scene/resources/packed_scene.h` | none | Binary resource format understands `PackedScene`. |
| `core/io/resource_loader.cpp:50` → `servers/rendering/rendering_server.h` | none | |
| `core/debugger/remote_debugger.cpp:45` → `servers/display/display_server.h` | none | |
| `core/extension/godot_instance.cpp:37-38` → `main/main.h`, `servers/display/display_server.h` | none | LibGodot embedding drives `Main` directly. Inherent to its role. |
| `core/config/engine.cpp:42` → `servers/rendering/rendering_device.h` | `RD_ENABLED` | |
| `core/error/error_macros.cpp:45` → `scene/main/node.h` | `DEBUG_ENABLED && TOOLS_ENABLED` | |
| `core/extension/extension_api_dump.cpp:43` → `editor/doc/editor_help.h` | `TOOLS_ENABLED` | |
| `core/profiling/profiling.h:102` → `main/performance.h` | `GODOT_USE_PERFETTO` | |

**servers → scene (16 unguarded includes, 1 `DEV_ENABLED`)** — the largest unguarded inversion:
- Navigation servers 2D/3D → `scene/main/node.h`, navigation mesh/polygon resources, `scene/resources/material.h` (8 includes).
- Audio server → `scene/resources/audio/audio_stream*.h`, `scene/scene_string_names.h` (5).
- Display server / native menu → `scene/resources/texture.h` (2).
- `servers/movie_writer/movie_writer.cpp` → `scene/main/window.h`; `servers/rendering/shader_preprocessor.h` → `scene/resources/shader_include.h`.

So in practice **servers consume scene-level resource types** (Texture, AudioStream, NavigationMesh, Material). The resource classes act as a shared vocabulary sitting *below* servers in practice, even though they live in `scene/resources/`.

**servers / scene → modules (7, all guarded by `MODULE_*_ENABLED`)**: `servers/rendering` → `modules/glslang`, `modules/texture_streaming` (new this window); `scene/resources` → `modules/svg`, `texture_streaming`. These are optional modules hooked into lower layers with compile-time switches.

**scene → editor (12 includes, all `TOOLS_ENABLED`)**: `scene/2d` 3, `scene/gui` 3, `scene/resources` 3, `scene/3d` 1 (`occluder_instance_3d.cpp` → `editor/editor_node.h`), `scene/animation` 1, `scene/property_utils.cpp` 1. Absent from export templates, but in editor builds the runtime node layer calls into `EditorNode` / `EditorSettings`.

**drivers → scene (1 unguarded)**: `drivers/png/resource_saver_png.cpp:36` → `scene/resources/image_texture.h`.

**modules → editor (319 includes)**: 256 come from `modules/*/editor/` subfolders, 44 sit under `#ifdef TOOLS_ENABLED`, and 19 are unguarded: 17 in `modules/gdscript/language_server/` and 2 in `lightmapper_rd`. `language_server/*.cpp` and `editor/*.cpp` are added only when `env.editor_build` (`modules/gdscript/SCsub:11-18`), and `lightmapper_rd`'s `can_build` requires an editor build. So all 19 are build-guarded. Checked against the SCons build rules, **none of the 319 reaches a template build** (§10.4).

*Correction to an earlier draft, which said 354 = 256 + 79 + 19.* That number counted raw `#include "editor/…"` lines in `modules/` without resolving them. 35 of those lines don't point at the editor layer. A quoted include resolves relative to the including file first, so 33 of them hit the module's **own** `editor/` subfolder (e.g. `modules/gltf/register_types.cpp` → `modules/gltf/editor/editor_scene_importer_gltf.h`). The other 2 are the module-local generated `editor/script_templates/templates.gen.h` in gdscript and mono. All 35 sat in the TOOLS_ENABLED bucket (79 − 35 = 44). The draft also listed `gdscript.cpp`, `gdscript_analyzer.cpp`, `gdscript_tokenizer.cpp` and `gdscript_editor.cpp` as unguarded. Their editor includes are in fact under `#if defined(TOOLS_ENABLED) …` or module-local. Evidence: `polyglot/recount_modules_editor.{py,txt}`.

## 5. Local centers (hubs)

### 5.1 Component level (from `full.dot`)

| Fan-in (depended on by N components) | | Fan-out (depends on N components) | |
|---|---:|---|---:|
| `core.os` | 124 | `editor` (root: `editor_node`, …) | 50 |
| `core.object` | 121 | `main` | 46 |
| `core.io` | 120 | `platform.macos` | 44 |
| `core.config` | 115 | `platform.android` | 39 |
| `core.templates` | 106 | `platform.windows` | 38 |
| `core.variant` | 76 | `platform.linuxbsd` | 36 |
| `core.string` | 75 | `editor.scene.3d`, `editor.scene`, `editor.settings`, `modules.openxr` | 34 each |
| **`scene.resources`** | **73** | `editor.inspector` | 33 |
| `core.math` | 71 | `modules.gdscript` | 32 |
| `servers.rendering` | 66 | `editor.animation` | 31 |
| `scene.main` | 59 | `editor.script`, `editor.export`, `editor.debugger`, `scene.resources`, `editor.import`, `editor.docks` | 30 each |
| `editor` (root) | 55 | | |
| `servers.display` | 53 | | |
| `editor.settings` | 52 | | |
| `scene.gui` | 49 | | |

`cpp-dependencies --outliers` flags as **too many outward links** (>30): `editor`, `editor.animation`, `editor.inspector`, `editor.scene`, `editor.scene.3d`, `editor.settings`, `main`, `modules.gdscript`, `modules.openxr`, `platform.{android,linuxbsd,macos,windows}`. It flags as **too much code** (>20 kLOC per component): `drivers.gles3`, `modules.gdscript`, `modules.tilemap`, `platform.linuxbsd`, `scene.3d`, `scene.gui`, `scene.main`, `scene.resources`, `servers.rendering`, `servers.rendering.renderer_rd`.

### 5.2 Header level (direct `#include` count, all layers)

| Header | Included by | From layers | Role |
|---|---:|---|---|
| `core/object/class_db.h` | **797** files | all 9 | Reflection/binding registry — the single most central header. |
| `core/object/callable_mp.h` | 464 | 7 | Signal/method-pointer glue. |
| `core/config/project_settings.h` | 334 | all 9 | Global configuration. |
| `core/os/os.h` | 298 | all 9 | |
| `core/config/engine.h` | 254 | all 9 | Singleton registry. |
| **`editor/editor_node.h`** | **226** | editor, main, modules, platform, **scene** | Editor hub; scene (guarded) and platform include it too. |
| `editor/settings/editor_settings.h` | 213 | editor, main, modules, platform, scene, tests | |
| `servers/rendering/rendering_server.h` | 210 | all 9 (including core) | |
| `scene/main/scene_tree.h` | 194 | 6 | |
| `editor/themes/editor_scale.h` | 177 | 4 | |
| `editor/editor_string_names.h` | 163 | 3 | |
| `core/io/file_access.h`, `core/io/resource_loader.h` | 157 each | all 9 | |
| `scene/gui/box_container.h` | 115 | 4 | The editor UI is built out of `scene/gui` widgets. |
| `editor/editor_undo_redo_manager.h` | 104 | editor, modules, scene | |
| `servers/display/display_server.h` | 101 | 8 (including core and drivers) | |

### 5.3 Large files (tool limit: 2 000 LOC)

114 files exceed the limit. The ones that are also **hot in artifact 1** are: `editor/editor_node.cpp`, `editor/script/script_editor_plugin.cpp`, `editor/docks/scene_tree_dock.cpp`, `editor/docks/filesystem_dock.cpp`, `editor/scene/canvas_item_editor_plugin.cpp`, `editor/scene/3d/node_3d_editor_plugin.cpp` + `node_3d_editor_viewport.cpp`, `editor/script/script_text_editor.cpp`, `editor/settings/editor_settings.cpp`, `editor/themes/theme_classic.cpp` + `theme_modern.cpp`, `main/main.cpp`, `modules/gdscript/{gdscript,gdscript_analyzer,gdscript_editor,gdscript_parser}.cpp`, `scene/gui/{rich_text_label,text_edit,popup_menu}.cpp`, `servers/rendering/renderer_rd/forward_{clustered,mobile}/render_forward_*.cpp`, `servers/rendering/rendering_device.cpp`, `drivers/gles3/rasterizer_scene_gles3.cpp`, `platform/android/export/export_plugin.cpp`. Full list in `outliers.txt`.

## 6. Modules: leaves vs. entangled

- **Leaf modules** (nothing includes them): 44 of 59 module folders (56 have a `register_types.cpp`). They plug in only through `register_types.cpp`. Examples: physics backends (`godot_physics_2d/3d`, `jolt_physics`), `openxr`, `webxr`, `text_server_adv/fb`, image and audio codecs, networking (`enet`, `webrtc`, `websocket`, `multiplayer`), `navigation_3d`, `lightmapper_rd`. These are the cleanly pluggable parts.
- **Entangled modules** (inside the big SCC): `gdscript`, `mono`, `jsonrpc` (the LSP depends on it), `visual_shader`, `tilemap` (just extracted from scene, artifact 1), `glslang`, `svg`, `zip`, `texture_streaming`, `visionos_xr`. Lower layers or the editor include their headers directly, mostly under `MODULE_*_ENABLED` guards.
- `modules.gdscript` has 32 outgoing component links. It reaches into `core.object` (script-language contract), the editor (script editor, LSP) and `tests`.

## 7. How structure lines up with activity (cross-check with artifact 1)

| Artifact 1 signal | Structural explanation |
|---|---|
| `editor/editor_node.cpp` is the most-changed file (69 commits) | `editor` root has the highest component fan-out (50); `editor_node.h` is included by 226 files across 5 layers. A god object at the composition point of the editor. |
| `drivers/gles3 ↔ servers/rendering` co-change (P = 0.57) | `servers.rendering` + 3 driver components form one SCC once cross-layer back-edges are removed; drivers implement server interfaces. |
| Script-language contract cluster (`core/object/script_language.h` ↔ gdscript ↔ mono) | `core.object` has fan-in 121; `gdscript` and `mono` are entangled modules in the SCC. |
| `scene/gui` most fix-heavy | `scene.gui` is oversized (>20 kLOC), has fan-in 49, and is the editor's widget toolkit (`box_container.h` included by 115 files). Widget fixes are pulled in by editor needs. |
| Core refactors (`ClassDB` → `GDType`, `ScriptLanguage` → `EditorLanguage`) | `class_db.h` is included by 797 files; changing it touches every layer. |
| `scene/resources` moves/splits | `scene.resources` has fan-in 73 and is consumed by **servers** (audio, display, navigation) and core (binary format). It already works as a shared layer below servers. |

## 8. Candidate risk zones (structural, for synthesis)

1. **`scene/resources` is a misplaced foundation**: it is consumed by servers and core, so any change there is cross-layer.
2. **The core → scene/servers back-edges** in `core/io/{resource,resource_format_binary,resource_loader}.cpp` and `core/debugger/remote_debugger.cpp` are what make the whole engine one SCC. They are few, specific and documented above.
3. **Editor hubs**: `editor_node.h`, `editor_settings.h`, `editor_scale.h`, `editor_undo_redo_manager.h`, each with 100–226 includers, some of them in `scene/` (guarded).
4. **Big parallel renderers**: `drivers.gles3` and `servers.rendering.renderer_rd` are both oversized and change together.
5. **`modules/gdscript`**: oversized, high fan-out. *(Downgraded by §10.4: all of its editor includes are excluded from template builds.)*
6. **C# ↔ C++ interop tables bound by position** (`runtime_interop.cpp:1584` ↔ `NativeFuncs.cs`, `editor_internal_calls.cpp` ↔ `Internal.cs`, `gd_mono_cache.h:71` ↔ `ManagedCallbacks.cs`; 226 + 33 + 43 entries). Reordering or skipping one entry breaks the link at runtime without any error. They are aligned at HEAD.
7. **Hidden platform coupling**: `editor/editor_node.cpp` and `editor/docks/filesystem_dock.cpp` declare their own `extern godot_js_os_download_buffer` (`#ifdef WEB_ENABLED`). `drivers/gles3` calls `godot_webgl2_*` directly. Neither goes through `platform/web` headers.
8. **Android/Java concentration**: 101 first-party Java/Kotlin files, 40 meaningful commits from only **7 authors** in the artifact-1 window. `:lib` packages form one cycle around `org.godotengine.godot`, and `GodotNativeBridge` alone takes 53 of the C++ → Java calls.

## 9. Unknowns

- **Runtime coupling** (ClassDB lookups, singletons, signals, `Callable`, GDExtension calls) is not in an include graph. The true dependency web is denser than shown.
- **Build-configuration reality**: the graph is the union of all configurations (editor + template, every platform, every `MODULE_*_ENABLED`). Guards were classified by a simple preprocessor-stack pass that doesn't evaluate expressions or follow macros defined elsewhere. *Partly resolved (§10.4):* SCons build classes are now known for 1,897 of 1,900 C++ files. `MODULE_*_ENABLED` guards are still not evaluated, and compound SCons conditions are classified approximately.
- **Generated headers** are missing from an unbuilt tree. *Partly resolved (§10.1, §10.4):* the shader edges were recovered and the other families were attributed to their generators. What the non-shader headers themselves include is still unknown.
- **Granularity choice**: different component boundaries (e.g. one component per top-level dir, or per file) would give different SCC counts. Folder level was chosen to match artifact 1.
- ~~Android/Java, C#, Web JS sources were not scanned.~~ Now covered in §10, with these limits still open:
  - **Generated C# API** (`GodotSharp/Generated`, gitignored): produced by `bindings_generator.cpp` from ClassDB at editor runtime. Its size and coupling are unknown, and 19 of 35 `GodotTools` files depend on it.
  - **Runtime-dispatched bridges**: 28 JNI upcalls whose target is a polymorphic interface; reflection on any Java class through `java_class_wrapper.cpp` (plugins, unbounded); 59 JS → C++ callbacks through function pointers, counted but not mapped.
  - **Same-package / same-namespace coupling** in Java/Kotlin and C# needs no import. About 40% of Java/Kotlin file-level coupling (heuristic) is missing from the package graph.
  - **Shader variants** (`#[modes]`, `#[specializations]`, `#[versions]` read at runtime by `RDShaderFile`) are a union in the text graph.
- `upward.py` scans `.h/.cpp/.hpp/.mm/.c/.m/.cc` but not the 92 `.inc` fragment files (7.9k LOC in `core/math`, `scene/*`). Their outgoing includes are not classified by guard.
- `cpp-dependencies` reports test headers under `modules/*/tests/` as "never used". They are pulled in through generated test registration, which is a tool artifact, not dead code. (Exception: `modules/visual_shader/tests/test_visual_shader.cpp` matches no SCons rule at all; see §10.4.)

## 10. Addendum: non-C++ code, cross-language bridges and the build graph

The scan above covered C/C++/ObjC only. The repo has 7 more languages, about 201k LOC in all (≈12 % of the 1.70M C/C++/ObjC LOC; ≈10 % without the vendored apksig). None of the usual graph tools fit:
- **dependency-cruiser** would find nothing: Godot's web JS uses none of the ES6, CommonJS or AMD module syntax it detects.
- **pydeps** reads bytecode imports, so it can't see SCsubs, which SCons runs via `Import("env")`.
- **jdeps** and **Roslyn** both need compiled code: an Android SDK build for jdeps, a mono glue build for Roslyn.

So every graph below was built by stdlib Python parsing the text. The scripts and full outputs are in `evidence/structure/polyglot/`.

| Language | Files | LOC | Where | Activity, artifact-1 window (commits · authors · fix-commits) |
|---|---:|---:|---|---|
| C/C++/ObjC (§1–§8) | 3 843 scanned (+92 `.inc`) | 1 696k | everywhere | 1 641 · 345 · 671 (87 %) |
| Python / SCons | 132 `.py` + 221 `SCsub`/`SConstruct` | 24.3k | everywhere | 86 · 36 · 12 |
| GLSL | 147 | 40.3k | `servers/rendering/renderer_rd`, `drivers/gles3/shaders`, `modules/{lightmapper_rd,betsy}` | 49 · 27 · 24 |
| Java + Kotlin | 219 (**118 vendored `com.android.apksig`**, 30.9k LOC; 101 first-party, 22.6k) | 53.5k | `platform/android/java` | 40 · **7** · 15 |
| GDScript | 718 (703 test fixtures + `.out` expectations, 10 script templates, 5 Android test scripts) | 14.0k | `modules/gdscript/tests` | 31 · 14 · 5 |
| C# | 314 (221 compiled, 84 generator test fixtures, 9 templates) | 58.1k | `modules/mono` | 14 · 7 · 5 (churn 6.1k) |
| JavaScript | 28 | 10.6k | `platform/web/js`, `modules/{webxr,webrtc,websocket}` | 9 · 3 · 2 |
| Swift | 4 | 0.45k | `platform/{ios,visionos}`, `drivers/apple_embedded` | 3 · 2 · 0 |

Activity uses non-merge commits, excluding thirdparty, apksig and `*.gen.*`, with noise filtered by commit subject. That filter approximates artifact 1's groups but is not identical to them (`lang_activity.py`).

### 10.1 GLSL (shaders)
- **Shader → shader:** 83 `#include` edges, all resolved, **0 cycles, 0 cross-component edges**. The builders inline includes relative to the including file. Hubs: `renderer_rd/shaders/oct_inc.glsl` (13 includers), `effects/motion_vector_inc.glsl` (7), `samplers_inc.glsl` (5).
- **C++ → shader:** `X.glsl` is built into `X.glsl.gen.h` (3 builders, `SConstruct:1193-1210`). That recovers **107 of the 328 dropped generated-header includes**, and every one stays inside its own component (renderer_rd 84, gles3 15, betsy 5, lightmapper_rd 3). **The component graph and SCC findings above are unchanged.**
- **The two renderers are duplicated, not shared:** 12 shader basenames exist in both `drivers/gles3/shaders` and `renderer_rd/shaders`, and no include is shared between them. This is a shader-level reason for the gles3 ↔ rendering co-change (artifact 1, P = 0.57).
- **Likely dead:** `drivers/gles3/shaders/{cube_to_dp,effect_blur,lens_distorted}.glsl`. They are not built, included or referenced.

### 10.2 Cross-language bridges into the C++ engine
All bridges match one-to-one by name, with 0 orphans on either side.

| Bridge | Size | Concentrated in |
|---|---|---|
| Java/Kotlin → C++ (JNI exports) | 77 ↔ 77 | `platform/android/java_godot_lib_jni.cpp` 50 (→ `GodotLib`: engine lifecycle), `editor/game_menu_utils_jni.cpp` 15 |
| C++ → Java/Kotlin (`Get*MethodID`) | 175 sites: 100 resolve to one class, 28 polymorphic, 47 JDK/SDK | `java_godot_wrapper.cpp` 53 → `nativeapi.GodotNativeBridge` (single façade), `java_class_wrapper.cpp` 36 (reflection) |
| C# → C++ (`godotsharp_*` table) | 226 ↔ 226, **same order** | `modules/mono/glue/runtime_interop.cpp` ↔ `NativeFuncs.cs`; 13 entries used only by the generated API |
| C# editor → C++ (`godot_icall_*`) | 33 ↔ 33, same order | `editor/editor_internal_calls.cpp` ↔ `GodotTools/Internals/Internal.cs` |
| C++ → C# (`ManagedCallbacks`) | 43 ↔ 43, same order | `csharp_script.cpp` (44 of 55 call sites) |
| C++ → JS (Emscripten libraries) | 182 ↔ 182 | `display_server_web.cpp` 65, `audio_driver_web.cpp` 38, `webxr_interface_js.cpp` 23 |
| JS → C++ | 59 function-pointer callbacks | same files |
| Swift → ObjC++ | 2 `@main` entry points | chain in §3; visionOS calls back into Swift through `GDTSwiftBridge` |

- **The C# API is generated at editor runtime.** `editor/bindings_generator.cpp` (5.3k LOC) walks ClassDB and writes `GodotSharp/Generated`. Its include reach is small, but its real reach is every registered class.
- **Edges that bypass the platform layer:** the editor → JS calls and `drivers/gles3` → `godot_webgl2_*` (risk zone 7).
- **Emscripten JS-internal graph** (`$X__deps`): 30 library objects, no cycles, hub `GodotRuntime` (fan-in 22). 6 libraries use another library without declaring it; transitive declarations cover all of them.

### 10.3 Managed-language internal graphs
- **Android Gradle graph:** `:app → :lib, :dataLib, :fusedDepsLib`; `:dataLib →(compileOnly) :lib`; `:fusedDepsLib → :dataLib`; `:editor → :lib`; `:editor:macrobenchmark → :editor`.
  - The imports confirm every edge, and `:lib` imports nothing from `:app` or `:editor`, so **there are no layering violations**.
  - Package graph: 28 packages, 70 edges. **13 of the 19 `:lib` packages form one cycle** through the root `org.godotengine.godot`, the same "layer = one unit" pattern as C++.
  - Misplaced code: `org.godotengine.godot.editor.utils` lives in `:lib`, but only `:editor` uses it.
- **C# project graph** (16 `.csproj`, acyclic):
  - `GodotSharp ─analyzer→ SourceGenerators.Internal`; `GodotSharpEditor`, `GodotPlugins → GodotSharp`.
  - `GodotTools → {BuildLogger, IdeMessaging, ProjectEditor, Core}`. It links `GodotSharp`/`GodotSharpEditor` as **built DLLs**, so it is effectively an editor plugin written against the generated API.
  - Namespace graph: 28 namespaces, 59 edges. Every cross-project use is backed by a reference. One cycle: `Godot ↔ Godot.Bridge ↔ Godot.Collections ↔ Godot.NativeInterop` (the GodotSharp interop core).

### 10.4 Build graph (SCons)
- **Discovery is dynamic:**
  - Platforms: any dir with `detect.py`.
  - Exporters: any platform with `export/export.cpp`, built only in editor builds.
  - Modules: `detect_modules()`, then filtered by `module_X_enabled` → `can_build` → `module_check_dependencies`.
- **Build class of the 1,900 own C++ files:** always 448, module-gated 586, platform/feature-conditional 267, **editor-only 413**, tests-only 183, no rule 3.
- **Back-edges present in shipped (template) builds:** only **core → scene/servers/main (7 includes)**, **servers → scene (16)** and `drivers/png` → scene (1). Every modules → editor and scene → editor edge is editor-only. This narrows risk zones 1 and 2 to a known set of about 24 includes.
- **Declared vs. observed module dependencies** (14 declared edges, 7 module → module include edges):
  - **Undeclared:** `objectdb_profiler → gdscript`, `openxr → gltf` (both preprocessor-guarded).
  - **Broken declaration:** `navigation_3d/config.py:5` declares under the key `"navigation"`, so it never matches.
  - **Soft build cycle:** `freetype ↔ text_server_adv`, because `modules/freetype/SCsub:75` pulls in harfbuzz.
  - Most declared dependencies work through another module's **thirdparty include paths**, not module headers (theora → libogg, text_server_* → freetype/thorvg, ktx → basis_universal), and `drivers/png` libpng is shared with freetype and svg. An include graph can't see any of these.
- **Dead build artifacts:**
  - `modules/tilemap/editor/SCsub`: never called, left over from the module extraction in `48e6acc65b`.
  - **`modules/visual_shader/tests/test_visual_shader.cpp`:** matches no SCons rule, so it is likely never compiled. The module's SCsub, unlike gdscript's or mbedtls's, has no `env["tests"]` clause.
- **Generator families** (73 calls, 84 generated files, 327 includes):
  - GLSL (§10.1).
  - Module registry: `modules_enabled.gen.h` (57 includes). It is included by core.config, servers and scene, so if build-configuration edges count, it adds a **`core → modules` edge**.
  - GDExtension glue: `gdvirtual.gen.h` (36), `ext_wrappers`.
  - Core data, editor docs/icons/translations, platform registry/icons, theme/splash/LUT, script templates, test force-link.
