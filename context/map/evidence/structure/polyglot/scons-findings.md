# Workstream C: SCons / Python build graph

Static parse only (Python `ast` over 221 `SCsub`/`SConstruct` + 59 `modules/*/config.py`; SCons not run). Script: `scons.py` (stdlib-only, ~1 s). Output: `scons.json` (tree, can_build, declared deps, per-TU build class, 418 classified upward includes, 73 generator calls, Python import graph). Source-pattern rules match 1 897 of 1 900 own TUs.

## 1. Build tree and discovery
- `SConstruct` → `core`, `servers`, `scene`, `drivers`, `platform`, `modules`, `main` always; `editor/SCsub` only if `env.editor_build`; `tests/SCsub` only if `env["tests"]`; then `platform/<selected>/SCsub`.
- Discovery is dynamic. Platforms = `platform/*` with `detect.py` (8). Exporters = platforms with `export/export.cpp` (compiled from `editor/SCsub`, editor only). Platform APIs = platforms with `api/api.cpp` (compiled in all builds from `platform/SCsub`). Modules = `methods.detect_modules()`: a dir with `register_types.h` + `SCsub` + `config.py` (59), filtered by `module_<name>_enabled` → `config.can_build(env, platform)` → `module_check_dependencies`. Then `modules/SCsub` loops over `env.module_list`.
- 219 of 221 scripts are reachable. **`modules/tilemap/editor/SCsub` is dead**: it is never SConscript'ed, because `modules/tilemap/SCsub` globs `editor/*.cpp` itself (leftover from the 2026-07-19 move into a module, commit 48e6acc65b). `tests/compatibility_test/SConstruct` is a standalone project.
- 51 SCsubs reference `#thirdparty/*` (modules 32, drivers 8, servers 3, platform 3, core 2, scene 2, editor 1).
- Build class of the 1 900 own TUs: always 448 · module-gated (module on by default / `disable_*` off) 586 · platform/feature-conditional 267 · editor-only 413 · tests-only 183 · not in any rule 3.
- **Orphan test:** `modules/visual_shader/tests/test_visual_shader.cpp` (uses `TEST_FORCE_LINK`) matches no SCons rule. `modules/SCsub` only collects `tests/*.h`, `tests/SCsub` only force-links `tests/**`, and the module SCsub never adds `tests/*.cpp` (gdscript, mbedtls and others do). It is likely never compiled or run.

## 2. Module dependencies: declared vs. observed
Declared in `can_build` (14 edges; required ★):

| Module | Depends on |
|---|---|
| basis_universal | tinyexr★ (editor only) |
| fbx | gltf★ |
| gdscript | jsonrpc, websocket |
| gltf | csg, gridmap |
| ktx | basis_universal★ |
| msdfgen | freetype★ |
| navigation_3d | csg, gridmap. **Declared under the key `"navigation"`, so it is never matched** (dead declaration; affects only sort order) |
| svg | jpg, webp |
| text_server_adv / _fb | freetype, msdfgen, svg |
| theora | ogg★, vorbis★ |
| vorbis | ogg★ |
| *editor (SConstruct)* | freetype★, svg★ |

Observed C++ `#include` edges between modules: only 7. Declared and present: fbx→gltf (12), gdscript→jsonrpc (1, `language_server/` only, which SCons gates on both modules being enabled), gltf→csg/gridmap (guarded), vorbis→ogg.
- **Undeclared:** `objectdb_profiler → gdscript` (`#if MODULE_GDSCRIPT_ENABLED && DEBUG_ENABLED`) and `openxr → gltf` (guarded). Both are soft and preprocessor-guarded, never declared in `config.py`.
- Most declared dependencies are **realized through thirdparty headers, not module headers**. A module's SCsub puts another module's `#thirdparty/<lib>` on CPPPATH: theora→libogg/libvorbis, ktx→basis_universal, msdfgen/text_server_*→freetype, text_server_*→thorvg (svg). Include-graph tools (artifact 2) cannot see these edges.
- **Undeclared reverse coupling:** `modules/freetype/SCsub:75` adds `#thirdparty/harfbuzz` (built by text_server_adv) when `"text_server_adv" in env.module_list`, while text_server_adv declares freetype. That makes a soft build-level cycle freetype ↔ text_server_adv.
- Cross-layer thirdparty sharing: freetype and svg use libpng built by `drivers/png`; ktx uses `drivers/vulkan` headers; openxr uses `drivers/gl_context`'s glad; `modules/mbedtls` relies on mbedtls, which `core/crypto` builds when the module is off.
- Restricted `can_build`: editor-only `lightmapper_rd`, `xatlas_unwrap`; platform-only `camera`, `visionos_xr`, `webxr`, `raycast`; feature flags `disable_3d/2d/physics_*/navigation_*/xr`, `rendering_device`, `vulkan|d3d12|metal`. 32 modules always build.

## 3. SCons guards on upward includes (resolves the §9 unknown)
418 upward includes (core/drivers/servers/scene/**modules** → higher layer), each classified by preprocessor guard × the SCons build class of the source TU. For headers: reachability from template-build TUs through includes that are not TOOLS/TESTS-guarded.

| Unguarded upward includes | Count | Verdict |
|---|---:|---|
| modules → editor/main/platform/tests in `editor/`, `language_server/`, `lightmapper_rd`, `xatlas_unwrap` | 217 | **SCons editor-only** |
| modules headers reached only from editor/tests TUs | 81 | SCons editor/tests-only |
| modules → tests | 3 + 1 orphan | tests-only |
| core → scene/servers/main | 7 | **compiled in every build** |
| servers → scene | 16 | **compiled in every build** (navigation: unless `disable_navigation_*`) |
| drivers → scene (`png/resource_saver_png.cpp`) | 1 | every build |
| drivers/apple_embedded → main | 3 | iOS/visionOS only |
| modules → platform | 5 | camera_android (Android); openxr → `platform/android/api/java_class_wrapper.h` (a cross-platform API header, every build) |

- **modules → editor: 0 of 319 includes reach a template build.** 214 are SCons editor-only, 59 are headers only reachable from editor TUs, and 46 are preprocessor-guarded.
- The 17 unguarded gdscript includes are all in `language_server/*` and `editor/*`, which are SCons editor-only. The 2 in lightmapper_rd are editor-only through `can_build` (`editor_build and rendering_device`).
- **Correction to artifact 2 §4.3:** the editor includes in `gdscript.cpp`, `gdscript_analyzer.cpp`, `gdscript_tokenizer.cpp`, `gdscript_editor.cpp` and `register_types.cpp` are under `#ifdef TOOLS_ENABLED`. They are not unguarded. There are 319 modules→editor includes here, not the 354 the artifact counted; the difference comes from the counting method and is unexplained.
- So **the only back-edges present in shipped game builds are the 7 in core and 16 in servers** (plus drivers/png), which supports risk zones 1 and 2.

## 4. Code generators (map of the "generated headers" unknown)
73 generator calls. 84 distinct `*.gen.*` files are `#include`d 327 times; 273 of those includes match a builder statically. The 54 unmatched ones are the wayland `protocol/*.gen.h` (built by `wayland-scanner` through a custom `WAYLAND_API_HEADER` Builder) and the editor translations (target name computed at run time).

| Family | Builder | Output → included by |
|---|---|---|
| GLSL shaders (workstream B) | `glsl_builders.py` `RD_GLSL`/`GLSL_HEADER`, `gles3_builders.py` `GLES3_GLSL` | `*.glsl.gen.h` (107 includes) |
| Module registry | `modules/modules_builders.py` | `modules_enabled.gen.h` (57 includes, defines `MODULE_*_ENABLED`), `register_module_types.gen.cpp`, `modules_tests.gen.h` |
| GDExtension / binding glue | `core/extension/make_{wrappers,interface_header,interface_dumper}.py`, `core/object/make_virtuals.py` | `gdvirtual.gen.h` (36), `ext_wrappers.gen.h`, `gdextension_interface.gen.h` |
| Core data | `core/core_builders.py` | version, hash, encryption key, certs, authors/donors/license, `disabled_classes.gen.h` |
| Editor data | `editor/editor_builders.py`, `editor/icons`, `editor/themes` | doc XML → `doc_data_compressed.gen.h`, class doc paths, exporters registry, translations, icons, fonts |
| Platform | `platform/platform_builders.py` | `register_platform_apis.gen.cpp`, export icons `*_svg.gen.h` (14) |
| Scene/main/render data | `scene/theme/*_builders`, `main/main_builders.py`, `servers/rendering/storage/make_ltc_lut.py`, SMAA textures | default theme, splash, app icon, LUT, area/search textures |
| Script templates | `modules/{gdscript,mono}/editor/script_templates/build_template_*.py` | `templates.gen.h` |
| Tests | `tests/test_builders.py` | `force_link.gen.h` |

## 5. Python import graph (build helpers)
In-degree: `misc/utility/scons_hints.py` 220 (IDE type hints only, `from … import *`), `methods.py` 43, `platform_methods.py` 16, `misc/utility/color.py` 8, `version.py` 5; each `*_builders.py` 1–3. A star around `methods.py`, with no cycles worth noting.

## Unknowns
- Conditions are classified with regexes over `ast.unparse` text. Compound expressions are approximate, and `can_build` flags that are on by default are counted as "module-gated" (built by default). Custom modules and `custom.py` profiles are not modelled.
- Header reachability ignores non-TOOLS/TESTS `#if`s, so it over-approximates. Generated headers (`modules_enabled.gen.h`) are missing, so `MODULE_*_ENABLED` guards count as "guarded" without being evaluated.
- Source lists built at run time are not resolved: the thirdparty source lists in core/drivers, and `str(Path(...))` paths in `core/profiling`.
- The 54 generated includes are matched by name only, by hand. Wayland and translations are attributed manually.
- Shared thirdparty dependencies are inferred from `#thirdparty/<lib>` strings in SCsub. System libraries (`builtin_*=no`, pkg-config) are invisible.
