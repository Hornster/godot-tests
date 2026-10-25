# Artifact 1 — Territory (git history, last 6 months)

> Draft evidence report for the Project Map. Not the final map — see `repo-map.md` (not yet written).

| | |
|---|---|
| Repository | Godot Engine (`master`, HEAD `6765a18ca8`, 2026-10-22) |
| Window | 2026-04-22 → 2026-10-22 (6 months back from HEAD) |
| Volume | 2018 merged PRs · 1942 non-merge commits · 371 distinct authors of meaningful commits |
| Raw evidence | `context/map/evidence/territory.json`, `territory-agent-prs.txt`, `territory.py` (re-runnable: `python3 -I context/map/evidence/territory.py <since> <out.json>`) |

## 1. How commits were grouped

Every non-merge commit in the window was assigned to exactly one group. Only **Meaningful** feeds the hotspot and co-change rankings below; the rest is reported separately in §2.

| Group | Commits | Rule |
|---|---:|---|
| **Meaningful (human)** | **1851** | Everything not matched below. Noise paths (see next row) are stripped out *inside* these commits before counting. |
| Vendored thirdparty updates | 41 | ≥60 % of files under `thirdparty/`, or "`<lib>: Update to …`" subject. |
| Housekeeping / CI | 22 | `CI:` subjects, AUTHORS/DONORS updates, touching no engine source dirs. |
| Style / mass formatting | 20 | `Style:` prefix, clang-format/clang-tidy rule application, typo sweeps. |
| Mass mechanical refactor | 5 | ≥40 files **and** move/split/rename/apply wording (e.g. PhysicsServer enum split, AudioServer split, `RETURN_IF_ERROR` sweep). |
| Translation sync | 3 | "Sync translations with Weblate" (bot-driven pipeline, committed by a maintainer). |
| Bot-authored | 0 | No `[bot]`/dependabot/renovate/github-actions authors exist in the window. |

**Noise paths** excluded even inside meaningful commits: `thirdparty/**`, `*.po`/`*.pot`, `*/translations/*`, `misc/extension_api_validation/**` (API-compat validation data), `*.gen.*`, AUTHORS/DONORS/CHANGELOG.

**Agent group.** Godot commits carry **no** agent trailers (0 hits for Claude/Copilot/Codex/etc. co-author lines). Since 2026, though, `CONTRIBUTING.md` and the PR template require an AI disclosure in the **PR description**. Merged-PR bodies were therefore searched on GitHub (`gh search prs`, 17 queries, 171 candidates, read manually) and mapped back to their merge commits. Two agent sub-groups:

| Agent group | PRs | Meaning |
|---|---:|---|
| **Agent-authored code** | 17 | Disclosure says AI wrote/drafted/proposed part of the merged code (human reviewed). |
| **Agent-assisted only** | 49 (+3 on release branches) | AI used for diagnosis, navigation, review, benchmarks or PR text; code written by the human. |

These PRs are *also* inside the 1851 meaningful commits (they are real edits); they are listed separately in §5 rather than subtracted, because the disclosure is partial (see Unknowns).

## 2. What was filtered out (for the record)

- **Thirdparty updates (41)** — biggest: mbedTLS 4.1.0 + PSA Crypto (515 files), SDL 3.4.16 (300), HarfBuzz 14.4.0 (193), Jolt 5.6.0 (154), ThorVG 1.1.3, OpenXR 1.1.60/1.1.63, manifold, pcre2, libpng. ⚠ One commit misfiled here: `b8ee63b9f5` "[GDExtension] Remove redundant PR numbers from validation files" (190 files) — it is API-validation data cleanup, still noise.
- **Style (20)** — almost all by one maintainer (Thaddeus Crews): `readability-identifier-naming` (144 files), null-`memdelete` trim (70), `rp_`→`p_` (61), left-qualifier alignment (26), Ruff/pyupgrade.
- **Mass mechanical (5)** — PhysicsServer enums/structs moved to dedicated files (198), AudioServer split (96), `RETURN_IF_ERROR` sweep (57), `[[gnu::warn_unused]]` on core collections (45) and `String` (40).
- **Still inside "meaningful" but churn-distorting** (large moves that the subject filter did not catch — read their line counts with care):
  - *Convert TileMap(Layer) to a module* — `modules/tilemap` +33 971 lines, `editor/scene/2d` −16 943, `scene/2d` −6 062.
  - `node_3d_editor_plugin.cpp` → `node_3d_editor_viewport.cpp` split — ~8 000 lines churn each.
  - `editor/shader` (−5 227) and `modules/visual_shader` (+5 747) — visual shader editor relocation.

## 3. Activity over time (meaningful commits)

| 2026-04 (from 22nd) | 05 | 06 | 07 | 08 | 09 | 10 (to 22nd) |
|---:|---:|---:|---:|---:|---:|---:|
| 88 | 239 | 281 | **378** | 338 | 317 | 210 |

Steady ~300/month, peaking in July. October partial. No sign of a freeze period in this window (exact release-cycle phases: **unknown** from git alone).

## 4. Active territory

### 4.1 By application layer

Commits = meaningful commits touching the layer (one commit may count in several layers).

| Layer | Commits | Authors | Churn (lines) | Notes |
|---|---:|---:|---:|---|
| **Editor** (`editor/`) | **701** | 168 | 82.5 k | ~38 % of all meaningful commits. Docks, script editor, scene editors, inspector, settings, themes. |
| **Scene / nodes** (`scene/`) | 363 | 134 | 38.5 k | Dominated by `scene/gui` (Control widgets). |
| **API: class reference** (`doc/classes`, `modules/*/doc_classes`) | 252 | 109 | 11.1 k | Proxy for *public scripting API change* — see §4.4. |
| Platform ports (`platform/`) | 206 | 60 | 20.5 k | Android ≫ LinuxBSD > macOS > Windows > Web > iOS. |
| **Core** (`core/`) | 203 | 71 | 11.2 k | `core/object` (ClassDB, ScriptLanguage), `core/io`, `core/variant`, `core/string`, `core/templates`. |
| Servers (`servers/`) | 199 | 87 | 11.8 k | Mostly `servers/rendering` (RD renderer). |
| Drivers (`drivers/`) | 141 | 68 | 9.9 k | GLES3 (Compatibility renderer), Metal, Vulkan, Apple embedded. |
| Module: GDScript | 119 | 33 | 9.9 k | Highest-activity module by far. |
| Tests (`tests/`) | 56 | 34 | 6.2 k | Only ~3 % of meaningful commits touch tests. |
| Module: XR (OpenXR/WebXR/visionOS) | 49 | 20 | 7.9 k | New `visionos_xr` module this window. |
| Module: C#/.NET (`mono`) | 47 | 18 | 7.2 k | |
| Build root / CI / main | 42 / 27 / 30 | — | small | `main/main.cpp` is a frequent touch point (28 commits). |
| Other modules | ≤20 each | | | gltf 20, jolt_physics 19, gridmap 17, visual_shader 16, tilemap 15 (new), csg 12, text_server_* 20 combined. |
| API: GDExtension interface (`core/extension`) | 10 | 8 | 0.1 k | Low activity; ABI surface is changing rarely. |

### 4.2 Hot areas (folder level)

`fix%` = share of commits whose subject says fix/crash/regression — a rough stability signal. `api` = commits in that area that also changed the class reference.

| # | Area | Commits | Authors | fix% | api | Comment |
|---:|---|---:|---:|---:|---:|---|
| 1 | `scene/gui` | **182** | 65 | **47 %** | 44 | Control widgets (`Tree`, `RichTextLabel`, `TextEdit`, `PopupMenu`). Most-fixed area. |
| 2 | `modules/gdscript` | 121 | 34 | 20 % | 17 | Mostly feature/refactor work (EditorLanguage split, LSP, analyzer). |
| 3 | `editor/docks` | 109 | 33 | 45 % | 13 | Scene tree dock, FileSystem dock; "main screen plugins → docks" migration. |
| 4 | `servers/rendering/renderer_rd` | 107 | 48 | 44 % | 17 | Forward+ / Mobile renderers. Many hands. |
| 5 | `editor/` (root) | 88 | 40 | 23 % | 14 | `editor_node.cpp` — the editor's god object. |
| 6 | `editor/script` | 84 | 25 | 33 % | 16 | Script editor, find-in-files, script text editor. |
| 7 | `platform/android` | 76 | 21 | 34 % | 13 | Android editor, AAR export, export plugin. |
| 8 | `servers/rendering` (root) | 76 | 44 | 41 % | 16 | `rendering_device.cpp`, `rendering_server`. |
| 9 | `editor/scene` | 74 | 36 | 43 % | 10 | Scene-level editors; plus `editor/scene/3d` (50) and `editor/scene/2d` (33). |
| 10 | `drivers/gles3` | 69 | 37 | 35 % | 12 | Compatibility renderer catch-up/parity fixes. |
| 11 | `editor/inspector` | 69 | 35 | 35 % | 7 | |
| 12 | `editor/settings` | 68 | 33 | 25 % | 15 | |
| 13 | `scene/resources` | 65 | 34 | 22 % | 18 | Net −6.6 k lines (moves out to modules). |
| 14 | `core/object` | 57 | 19 | 16 % | 8 | ClassDB → `GDType`, `ScriptLanguage` → `EditorLanguage`. Architectural churn, few fixes. |
| 15 | `editor/gui` | 53 | 28 | 43 % | 9 | |
| 16 | `editor/export` | 51 | 26 | 31 % | 11 | Apple embedded / Android export. |
| 17 | `platform/linuxbsd` | 50 | 21 | 36 % | 6 | Wayland + X11. |
| 18 | `modules/mono` | 47 | 18 | 19 % | 7 | C# trampolines / interop. |
| 19 | `scene/main` | 44 | 26 | 36 % | 10 | `Node`, `Viewport`, `Window`. |
| 20 | `scene/3d` | 43 | 24 | 23 % | **21** | Most API-touching relative to size (new nodes, e.g. `Trail3D`). |
| 21 | `modules/openxr` | 39 | 17 | 41 % | 13 | |
| 22 | `core/io` | 38 | 25 | 34 % | 5 | |
| 23 | `platform/macos` | 40 | 15 | 45 % | 5 | |
| 24 | `core/variant` | 36 | 13 | 11 % | 4 | Performance work (Array/Dictionary type checks). |
| 25 | `scene/debugger` | 32 | 17 | 47 % | 3 | Game view / remote debugging (+4.2 k lines). |

### 4.3 Hot files (code only, class-reference XML excluded)

| File | Commits | Authors | fix-commits | Note |
|---|---:|---:|---:|---|
| `editor/editor_node.cpp` | **69** | 32 | 14 | Touched by every editor feature; 21 of 69 by one author (kobewi). |
| `editor/script/script_editor_plugin.cpp` | 48 | 21 | 15 | Highest churn (5.6 k lines) among top files. |
| `editor/docks/scene_tree_dock.cpp` | 48 | 19 | **26** | Most fix-heavy single file. |
| `modules/gdscript/gdscript_editor.cpp` | 33 | 11 | 7 | Completion / code tooling. |
| `editor/docks/filesystem_dock.cpp` | 33 | 16 | 14 | |
| `editor/scene/canvas_item_editor_plugin.cpp` | 31 | 14 | 11 | 2D editor viewport. |
| `editor/script/script_text_editor.cpp` | 31 | 10 | 6 | |
| `editor/inspector/editor_inspector.cpp` | 31 | 17 | 10 | |
| `editor/themes/theme_modern.cpp` | 28 | 15 | 11 | Almost always changed with `theme_classic.cpp`. |
| `main/main.cpp` | 28 | 16 | 4 | Bootstrap; touched for cross-cutting features. |
| `editor/settings/editor_settings.cpp` | 28 | 16 | 4 | |
| `modules/gdscript/gdscript_analyzer.cpp` | 27 | 10 | 5 | |
| `scene/gui/tree.cpp` | 26 | 18 | **19** | 73 % fix-commits — the least stable widget. |
| `editor/asset_library/asset_library_editor_plugin.cpp` | 26 | 10 | 11 | |
| `servers/rendering/renderer_rd/forward_clustered/render_forward_clustered.cpp` | 25 | 19 | 6 | |
| `drivers/gles3/rasterizer_scene_gles3.cpp` | 24 | 15 | 5 | |
| `editor/scene/3d/node_3d_editor_plugin.cpp` | 22 | 15 | 8 | Split into `node_3d_editor_viewport.cpp` (8 k churn). |
| `servers/rendering/rendering_device.cpp` | 22 | 12 | 5 | |
| `scene/gui/rich_text_label.cpp` | 19 | 9 | 9 | |
| `core/object/script_language.h` | 16 | 4 | 2 | Few authors, high coupling — see §6. |

### 4.4 Which layers the active work touches (API reach)

- **Public scripting API** (class reference XML changed in the same commit): **252 of 1851 meaningful commits (13.6 %)**. Those API changes travel mostly with **Scene** (83 commits), **Editor** (72), **Core** (31), **Servers** (30), Platform (21), Drivers (16). Exposed editor API (EditorPlugin, EditorInterface etc.) is a large share of this.
- **GDExtension binary interface** (`core/extension/`): only 10 commits — stable surface. Validation data under `misc/extension_api_validation/` was excluded as noise but its presence in a commit signals a compat-relevant API change.
- **Cross-layer pairs** (commits touching both layers): Editor ↔ Scene 76, Drivers ↔ Servers 50, Core ↔ Editor 41, Editor ↔ Platform 33, Scene ↔ Servers 26, Core ↔ GDScript 24, Editor ↔ GDScript 20, Core ↔ Tests 19, Scene ↔ Tests 17, Core ↔ C# 16.

## 5. Agent group (disclosed AI involvement)

**Agent-authored code — 17 PRs.** Small, spread out, mostly fixes by experienced contributors:

| Layer | PRs | Examples |
|---|---:|---|
| Core | 5 | `ClassDB` default-value race (#123546), `StringName::Table` zero-fill (#123960), Perfetto `thread_local` (#123549), Image rounding helper (#112541), **`EditorLanguage` introduction (#117946, Copilot for refactor boilerplate — core/object + editor/script + gdscript + mono)** |
| Drivers | 4 | Metal depth resolve (#120231), GLES3 multiview emulation (#120558), Vulkan `use_volk=no` (#120362), iOS AccessKit (#119750) |
| Editor | 3 | Export Options filter (#118898), AccessKit export, EditorLanguage |
| Platform | 3 | macOS mouse warp (#119756), LinuxBSD FontConfig leak (#121810), iOS AccessKit |
| Tests / CI | 2 / 2 | Desired-size tests (#123689), prek CI fix (#121819) |
| Thirdparty patches | 1 | SPIR-V reflection lookup table (#121835, only `thirdparty/spirv-reflect`) |

**Agent-assisted only — 49 PRs** (diagnosis, navigation, review, benchmarks). Concentrated in: `servers/rendering` (6), `tests/scene` (5 — one contributor's widget unit-test series), `drivers/gles3` (4), `doc/classes` (4), `editor/debugger` (3), `editor/docks` (3). Notable: `ClassDB`→`GDType` property maps (#122596, AI only for benchmarks); a string of sanitizer/leak fixes (aaronfranke) found by AI on a downstream fork and then verified by hand.

Takeaway: disclosed agent involvement is **~3.4 % of merged PRs** (69 of 2018), with no hot spot of its own. It follows the same territory as human work (rendering, Compatibility renderer, editor, tests) and never shows up in bulk/mass commits. Explicit "No AI was used" statements are common (67 PRs among the search hits; a lower bound, since the search terms were aimed at AI use), which shows the disclosure norm is followed.

## 6. Change coupling (what changes together)

Computed on meaningful commits with ≤25 non-noise files (bulk commits excluded); `.h`/`.cpp` twins of the same stem removed. `together` = commits containing both; `P(B|A)` / `P(A|B)` = conditional probability.

### 6.1 Folder pairs

| Together | A ↔ B | P(B\|A) / P(A\|B) | Reading |
|---:|---|---|---|
| 36 | `drivers/gles3` ↔ `servers/rendering` | 0.57 / 0.24 | **Renderer parity**: >half of GLES3 commits also touch the RD/server side. |
| 20 | `core/object` ↔ `modules/gdscript` | 0.37 / 0.18 | ScriptLanguage / EditorLanguage contract. |
| 14 | `core/object` ↔ `modules/mono` | 0.26 / 0.33 | Same contract, C# side. |
| 13 | `scene/2d` ↔ `scene/3d` | 0.65 / 0.27 | 2D/3D twin nodes (particles, physics bodies) edited in pairs. |
| 13 | `editor/script` ↔ `modules/gdscript` | 0.17 / 0.12 | Script editor ↔ GDScript tooling. |
| 12 | `modules/gdscript` ↔ `modules/mono` | 0.11 / 0.29 | Both implement the script-language interface. |
| 12 | `core/object` ↔ `editor/script` | 0.22 / 0.16 | |
| 15 / 12 / 12 | `editor/docks` ↔ `editor/scene` / `editor/` root / `editor/inspector` ↔ `editor/scene` | ≤0.19 | Editor internally intertwined, but weakly per pair. |
| 11 / 9 / 8 | `platform/linuxbsd` ↔ `windows` / ↔ `macos` / `macos` ↔ `windows` | 0.2–0.3 | Desktop-port parity edits (DisplayServer features). |
| 10 | `editor/themes` ↔ `scene/gui` | 0.28 / 0.06 | Theme items follow new GUI features. |
| 8 / 7 | `editor/export` ↔ `platform/android` / ↔ `platform/ios` | P(export\|ios) = 0.5 | Export pipeline owned in two places. |
| 7 | `modules/godot_physics_3d` ↔ `modules/jolt_physics` | **0.64** / 0.39 | Physics backends changed in lock-step. |
| 7 | `core/variant` ↔ `tests/core` | 0.21 / 0.30 | Core is where tests accompany change. |

### 6.2 File pairs (strongest logical coupling)

| Together | Files | Jaccard | Reading |
|---:|---|---:|---|
| 18 | `editor/themes/theme_classic.cpp` ↔ `theme_modern.cpp` | 0.67 | Two theme definitions maintained by hand in parallel (95 % of classic edits hit modern). |
| 12 | `render_forward_clustered.cpp` ↔ `render_forward_mobile.cpp` | 0.43 | Forward+ / Mobile renderer duplication; shader twins `scene_forward_clustered.glsl` ↔ `scene_forward_mobile.glsl` (6, J 0.46). |
| 11–12 | `core/object/script_language.h` ↔ `script_language_extension.h` ↔ `modules/gdscript/gdscript.h` / `gdscript_editor.cpp` ↔ `modules/mono/csharp_script.h` | 0.36–0.75 | **The script-language contract cluster.** Change in the core interface ripples through the GDExtension wrapper, GDScript and C# in the same commit. Mostly one series (HolonProduction's `EditorLanguage` extraction, 10 of 16 commits on `script_language.h`). |
| 8 | `core/object/editor_language.h` ↔ `modules/gdscript/editor/gdscript_editor_language.h` | 1.00 | New interface (this window) and its only implementation. |
| 7–8 | `gdscript_analyzer.cpp` ↔ `gdscript_parser.h/.cpp` ↔ `language_server/gdscript_extend_parser.cpp` | 0.28–0.47 | Parser changes require LSP adapter updates. |
| 12 / 7 | `script_editor_plugin.cpp` ↔ `script_text_editor.cpp` / `script_editor_base.cpp` | 0.16–0.20 | Script editor internals. |
| 7 | `animation_blend_space_1d_editor.cpp` ↔ `_2d_editor.cpp` | 0.88 | Copy-paste twins. |
| 7 | `node_3d_editor_plugin.cpp` ↔ `node_3d_editor_viewport.cpp` | 0.23 | Recent split, still coupled. |
| 6 | `core/templates/local_vector.h` ↔ `vector.h` | 0.55 | Container API kept symmetric. |
| 6 | `editor/export/editor_export_platform_apple_embedded.cpp` ↔ `platform/ios/export/export_plugin.cpp` | 0.35 | Apple export split across editor and platform. |
| 6 | `drivers/metal/metal_objects_shared.h` ↔ `rendering_device_driver_metal.cpp` | 0.50 | |

## 7. Early signals (for synthesis, not conclusions)

1. **The editor is the main stage** — 38 % of commits, 168 authors, the most-touched file (`editor_node.cpp`) and the most fix-heavy dock (`scene_tree_dock.cpp`).
2. **GUI widgets are the stability hot spot** — `scene/gui` has the most commits and ~half are fixes; `Tree` stands out (19 of 26 commits are fixes).
3. **The rendering stack is maintained in parallel copies** — GLES3 ↔ RD, Forward+ ↔ Mobile, clustered ↔ mobile shaders. Each feature or fix costs 2–3 edits.
4. **Active architectural refactors in core**: `ScriptLanguage` → `EditorLanguage`, `ClassDB` → `GDType`, TileMap/visual shader moved out into modules, server headers split. These have few authors and wide reach (core ↔ gdscript ↔ mono ↔ editor).
5. **Low test co-change** — about 3 % of meaningful commits touch `tests/`, mostly in `core/` and `scene/gui` widget unit tests.
6. **Desktop/export parity** couples platform folders and editor export code.

## 8. Unknowns

- **Undisclosed AI use.** Disclosure lives in PR text, not commits, and the reminder was only added mid-window (#118855). GitHub search returned ≤200 per query and keyword matches were reviewed by hand. Agent counts are a **lower bound**; the authored/assisted split relies on the contributors' own wording.
- **Bot activity** is invisible in the git history (translation sync and CI bumps are committed by humans). Bot *reviews* and labels on GitHub were not examined.
- **Fix detection** uses the commit subject only. "Improve…" commits that are really fixes, and reverts (7 in the window: WorkerThreadPool deadlock fix, GDScript Quick Fix actions, text draw presort, locale fallback, wasm64, HDR EXR screenshots, Android minSdk), are not weighted separately.
- **Churn of moved code** (TileMap, node_3d viewport split, visual shader) is counted as edits. Line totals for `editor/scene/*`, `scene/2d`, `modules/tilemap`, `modules/visual_shader` are inflated.
- **Merged-PR granularity**: Godot asks contributors to squash PRs, and the window has 2018 merges against 1942 non-merge commits, so commit counts ≈ PR counts. (Some merges bring in commits dated before the window, so the two numbers don't match exactly.) Review effort and discussion intensity are not measured here (that belongs to a discussion / people artifact).
- **Release branches** (`4.x`, `3.x` backports) are outside `master` and not counted.
