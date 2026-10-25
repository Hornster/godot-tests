# GLSL dependency findings (workstream A)

Source: `glsl.py` → `glsl.json` (run: `python3 -I glsl.py <repo_root> glsl.json`). Tracked files only, `thirdparty/` excluded as a source.

## How the build resolves shaders (from `SConstruct:1193-1210`, `glsl_builders.py`, `gles3_builders.py`)
- Three SCons builders, all with `suffix="glsl.gen.h"`: `X.glsl` → `X.glsl.gen.h` **next to the source**. `RD_GLSL` (83 files) emits a `*ShaderRD` class; `GLSL_HEADER` (23, mostly `*_inc.glsl`) emits a raw string; `GLES3_GLSL` (14) emits a GLES3 shader class.
- `#include "x"` is inlined by the builder, relative to the including file's directory; paths starting with `thirdparty/` resolve from the repo root. The builder matches `#include ` anywhere on a line, but no commented-out includes exist.
- Section markers: `#[vertex]` 48, `#[fragment]` 48, `#[compute]` 62, `#[modes]`/`#[specializations]` 15 (GLES3 only). `#[versions]` (7, betsy/lightmapper) is **not** handled by the builders. It is parsed at runtime by `RDShaderFile` (`servers/rendering/rendering_device_binds.cpp:74`), which is a runtime coupling that the include graph can't see.

## Shader → shader graph
| Metric | Value |
|---|---:|
| `.glsl` files | 147 (renderer_rd 105, gles3 24, betsy 5, lightmapper_rd 5, tests/python_build fixtures 8) |
| Include edges (resolved) | 83; **0 unresolved** |
| Includes into `thirdparty/` | 10 (amd-fsr, amd-fsr2), all exist |
| Cycles | **0** |
| Cross-component edges | **0**: modules never include `servers/` shaders, and gles3 and RD never share an include |
| Cross-folder edges (all inside one component) | `renderer_rd/shaders/{environment,forward_clustered,forward_mobile,effects}` → `shaders/` 12/12/10/8; `effects/fsr2` → `effects` 5; `gles3/shaders/effects` → `shaders` 4 |

Hubs (fan-in): `renderer_rd/shaders/oct_inc.glsl` 13 · `effects/motion_vector_inc.glsl` 7 · `samplers_inc.glsl` 5 · `gles3/stdlib_inc.glsl` 4 · `area_lights_inc.glsl` 4 · `light_data_inc.glsl` 4 · `gles3/tonemap_inc.glsl` 3 · `lightmapper_rd/lm_common_inc.glsl` 3.
Deepest transitive closure: `forward_clustered/scene_forward_clustered.glsl` 14 files, `forward_mobile/scene_forward_mobile.glsl` 12.

**Parallel renderers, duplicated rather than shared:** 12 shader basenames exist in **both** `drivers/gles3/shaders` and `renderer_rd/shaders` (`canvas`, `canvas_occlusion`, `canvas_sdf`, `canvas_uniforms_inc`, `area_lights_inc`, `copy`, `cube_to_dp`, `particles`, `particles_copy`, `skeleton`, `sky`, `tex_blit`), and no include is shared between the two. This gives a structural reason for the gles3 ↔ renderer_rd co-change (artifact 1, P = 0.57) at shader level.

Likely dead: `drivers/gles3/shaders/{cube_to_dp,effect_blur,lens_distorted}.glsl`. No SCsub builds them, nothing includes them, and no C++ references them. (The `cube_to_dp` in `copy_effects.cpp` is the RD one.)

## C++ → shader (recovered from dropped `*.glsl.gen.h` includes)
| Metric | Value |
|---|---:|
| `#include "*.gen.*"` lines in C/C++/ObjC | 328 |
| … of which `*.glsl.gen.h` | **107** (32.6 %), from 40 C++ files to 106 shader sources, 0 unresolved |
| Component edges | renderer_rd → renderer_rd 84 · gles3 → gles3 15 · betsy → betsy 5 · lightmapper_rd → lightmapper_rd 3 |
| Layer-crossing / new vs `full.dot` | **0 / 0**: every C++ → shader edge stays inside its own component |

Result: the 107 file-level edges are recovered, but **none changes the component graph or the SCC conclusions** in artifact 2.

## Non-shader generated headers (221 includes, 84 families; still absent in an unbuilt tree)
| Family | Includes | Includer components / note |
|---|---:|---|
| `modules/modules_enabled.gen.h` | 57 | 28 components incl. core.config, servers.rendering(.renderer_rd), scene.3d, scene.resources, drivers.metal: **build-config header (`MODULE_*_ENABLED`)** |
| `core/object/gdvirtual.gen.h` | 36 | 23 components; core-owned, downward only |
| `core/extension/ext_wrappers.gen.h` | 10 | core, scene.main, servers.physics_*, text_server_* |
| Wayland `protocol/*.gen.h` + `wayland*.gen.h` | ~50 | platform.linuxbsd only (local) |
| `logo_svg` / `run_icon_svg.gen.h` | 7 / 7 | each platform, local |
| `core/extension/gdextension_interface(.._dump).gen.h` | 7+2 | core.extension, core.object, modules, main |
| `core/version_generated`, `authors`/`donors`/`license`, `certs_compressed`, `main/splash*`, `editor/doc/*`, `editor/translations/*`, `editor/themes/{editor_icons,builtin_fonts}`, `editor/script_templates/templates`, `ltc_lut`, `icudata`, … | 1–5 each | mostly local |

With paths resolved from the repo root, these families imply **32 component edges missing from `full.dot`**. 8 of them point upward:
`core.config`, `drivers.metal`, `servers.rendering`, `servers.rendering.renderer_rd`, `scene.3d`, `scene.resources` → `modules` (all via `modules_enabled.gen.h`). *(Correction: an earlier version also listed `modules.gdscript`, `modules.mono` → `editor.script_templates` via `templates.gen.h`. That came from resolving the path from the repo root. The header is generated module-locally in `modules/{gdscript,mono}/editor/script_templates/` (see their SCsub), so those 2 edges are internal to each module and **6** upward edges remain, not 8.)* The `modules_enabled` edges are compile-time configuration rather than code use. If counted, they would add `core → modules` to the back-edges in artifact 2 §4.3.

## Unknowns
- Whether the 12 same-named gles3/RD shader pairs have similar content. Only names were compared.
- Which shader variants and specializations are actually compiled or used at runtime (`#[modes]`, `#[specializations]`, `#[versions]`, defines injected by C++). The text graph is the union of all of them.
- Runtime shader loading (`RDShaderFile` reading raw `#[versions]` sources, user `.gdshader` → GLSL generation by `ShaderCompiler`) is outside any include graph.
- What the non-shader generated headers contain (and therefore their outgoing edges) is unknown until a build runs. Only the edges *into* them are recovered here.
