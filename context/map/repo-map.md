# Repo Map — Godot Engine

> Decision map for working in this repo. It covers **where change is risky, where it is cheap, what to read first and who to ask**. It is not a description of the engine.
> Built from three evidence artifacts. Each claim cites one: **[T]** `artifact-1-territory.md` (git, 6 mo), **[S]** `artifact-2-structure.md` (include/build graph), **[C]** `artifact-3-contributors.md` (people in `scene/resources`, 12 mo). Raw data is in `evidence/`.

| | |
|---|---|
| Snapshot | `master` @ `6765a18ca8`, 2026-10-22 |
| Activity | 1851 meaningful commits, 371 authors, ~300 commits/month, no freeze visible [T] |
| Shape | Layered by boot order: core < drivers ≈ servers < scene < modules < editor < platform (`main/main.cpp:984`). In practice each layer is one tangled unit, and ~24 back-edges in shipped builds tie them into one cycle [S §4, §10.4] |
| Test signal | Only ~3 % of commits touch `tests/` [T §4.1] — **expect to verify by hand** |

## 1. Risk zones (criticality × buzz)

Criticality comes from structure (fan-in, back-edges, silent-failure modes). Buzz comes from activity (commits, fix share, reverts, author concentration).

| # | Capability / zone | Criticality — why | Buzz — why | What it means for a change |
|---|---|---|---|---|
| 1 | **Scene save/load & shared resources** — `scene/resources` (`packed_scene.cpp`, `resource_format_text.cpp`, `material.cpp`) | **High.** Fan-in 73. Servers include it without guards (16 includes) and so does core (`resource_format_binary.cpp`). It is a foundation that sits in the wrong layer [S §4.3, §8.1] | **Med.** 65 commits in 6 mo, net −6.6 k lines from moves into modules [T]. All 3 reverts in 12 mo were in materials and particles, plus 2 default-value regressions [C §3] | `.tscn` output, property storage and default values are a **compatibility surface**. Read the PRs in §3 first. Materials, particles and environment have **0 unit tests** [C §4] |
| 2 | **Scripting contract** — `core/object/script_language.h`, `editor_language.h`, `class_db.h` ↔ `modules/gdscript` ↔ `modules/mono` | **High.** `class_db.h` has 797 includers across all layers. A change to the interface ripples through the GDExtension wrapper, GDScript and C# in the same commit (Jaccard 0.36–1.0) [T §6.2, S §5.2] | **Med, structural.** Refactors in progress: `ScriptLanguage`→`EditorLanguage`, `ClassDB`→`GDType`. Few authors (4 on `script_language.h`), mostly one series [T §4.3, §7.4] | Coordinate with the refactor authors before touching it. Plan for edits in core + gdscript + mono together |
| 3 | **Editor UI widgets** — `scene/gui` (`tree.cpp`, `rich_text_label.cpp`, `text_edit.cpp`) | **Med-High.** Over 20 kLOC, fan-in 49. It is the editor's widget toolkit (`box_container.h` has 115 includers) [S §5, §7] | **Highest.** 182 commits, **47 % fixes**. `Tree` has 19 fixes out of 26 commits [T §4.2–4.3] | The least stable code in the repo. A widget fix can surface anywhere in the editor. Add a unit test: `tests/scene` already has a widget-test series [T §5] |
| 4 | **Editor core** — `editor/editor_node.cpp`, `docks/scene_tree_dock.cpp`, `script/script_editor_plugin.cpp` | **Med.** `editor_node.h` has 226 includers, including guarded ones from `scene/`. `editor` root has the highest fan-out (50) [S §5] | **High.** `editor_node.cpp` is the #1 file (69 commits). `scene_tree_dock.cpp` is the most fix-heavy file (26 of 48) [T §4.3] | Expect merge conflicts. Keep changes out of `editor_node` where a dock or plugin can hold them |
| 5 | **Rendering** — `drivers/gles3` ↔ `servers/rendering/renderer_rd`, Forward+ ↔ Mobile | **Med-High.** Both components are oversized and maintained as **parallel copies**: 12 duplicated shader basenames with no shared include [S §10.1] | **High.** GLES3 commits also touch RD 57 % of the time. Forward+/Mobile Jaccard is 0.43. renderer_rd: 107 commits, 44 % fixes, 48 authors [T §6] | Budget 2–3 edits per fix (GLES3 + RD clustered + RD mobile, plus shader twins). Test the Compatibility renderer too |
| 6 | **C# interop** — `modules/mono/glue/runtime_interop.cpp` ↔ `NativeFuncs.cs` (226), `editor_internal_calls.cpp` ↔ `Internal.cs` (33), `ManagedCallbacks` (43) | **High.** Tables are **bound by position**. If one entry is reordered or skipped, the link breaks at runtime with no error [S §8.6] | **Low.** 14 commits, 7 authors [S §10] | Low traffic means nobody will catch a mistake soon. Diff both sides of a table in the same PR |
| 7 | **Android port** — `platform/android/java`, JNI | **Med.** 77 JNI downcalls and 175 upcalls. `GodotNativeBridge` handles 53 of them. 13 of 19 `:lib` packages form one cycle [S §10.2–10.3] | **Med, bus factor.** 76 commits on the C++ side, but only **7 authors** on Java/Kotlin [T, S §8.8] | Few reviewers. Get one of the 7 involved early |

**Lower-priority traps** (small, but they bite):
- `editor/themes/theme_classic.cpp` ↔ `theme_modern.cpp` — 95 % of edits to classic also hit modern [T §6.2].
- Web code that bypasses `platform/web`: `editor_node.cpp` and `filesystem_dock.cpp` declare their own `extern godot_js_*`, and `drivers/gles3` calls `godot_webgl2_*` directly [S §8.7].
- Export code lives in two places: `editor/export/editor_export_platform_apple_embedded.cpp` ↔ `platform/ios/export` [T §6.1].
- 2D/3D twin nodes in `scene/2d` ↔ `scene/3d` are edited together 65 % of the time. The physics backends `godot_physics_3d` ↔ `jolt_physics` are edited together 64 % of the time [T §6.1].

## 2. Where change is cheap

- **Leaf modules (44 of 59)**: physics backends, `openxr`/`webxr`, `text_server_*`, codecs, networking, `navigation_3d`, `lightmapper_rd`. Nothing includes them. They plug in only through `register_types.cpp` [S §6].
- **GDExtension interface** (`core/extension/`): 10 commits in 6 mo, a stable surface [T §4.4].
- **Editor-only code**: 413 files never reach export templates. All modules → editor and scene → editor back-edges are editor-only [S §10.4].
- **Shaders, Gradle graph, C# project graph**: no cycles and no layering violations [S §10.1, §10.3].

## 3. First-day reading list

| Read | Why |
|---|---|
| `main/main.cpp:984` (`Main::setup` → `setup2` → `start` → `iteration`) | The real layer order and the composition root [S §2–3] |
| `core/object/class_db.h`, then `core/object/script_language.h` + `editor_language.h` | The most central header and the contract under active refactor (zone 2) |
| One leaf `modules/*/register_types.cpp` | How plug-ins attach at the 4 init levels [S §2] |
| `core/io/resource_format_binary.cpp:41`, `servers/audio` / `servers/navigation_*` includes of `scene/resources` | The back-edges that make `scene/resources` a hidden foundation (zone 1) [S §4.3] |
| `editor/editor_node.cpp` (skim) | The editor's god object (zone 4) |
| PRs **#121920**, **#114844**, **#103352** | Decisions about the `.tscn` format: byte-identical output, AnimationLibrary compat, no `load_steps` [C §5] |
| PRs **#115163**, **#118373**, **#116140** (reverts) and **#112471** | What breaks in materials and particles, and why [C §5] |
| PR **#113429** | The texture streaming architecture (114 comments) [C §5] |

## 4. Who to ask

Mapped **only for `scene/resources`** [C §6]. Other areas: unknown, apart from the authorship signals in [T].

| Topic | First contact | Backup | Note |
|---|---|---|---|
| `.tscn`/`.tres`, `PackedScene` | KoBeWi | YeldhamDev, Repiteo | Many authors, but approval is concentrated |
| Materials, environment, textures, render defaults | clayjohn | Calinou, BastiaanOlij, BlueCube3310 | Owner through review. Drive-by authors, revert cluster |
| Animation / IK | TokageItLab | lyuma, fire | **Bus factor**: writes 57 % and approves it |
| Particles | QbieShay | paddy-exe | **Bus factor**: writes 60 % and approves it |
| Fonts / text shaping | bruvzg | akien-mga | **Bus factor**: writes 59 % |
| Core types, includes, module boundaries | Ivorforce, akien-mga | Repiteo, smix8 | Cross-cutting. Ask about structure, not behaviour |
| Script-language refactor (outside [C]) | HolonProduction (10 of 16 commits on `script_language.h`) [T §6.2] | — | Inferred from authorship only |

## 5. Unknowns

- **Runtime coupling** through ClassDB, singletons, signals, `Callable` and GDExtension is invisible to the include graph. Real coupling is denser than shown [S §9].
- **People outside `scene/resources`**, including ownership of editor, rendering, GDScript and platforms, was not measured. Approval counts do not separate deep review from sign-off [C §7].
- **Open PRs and in-flight work** were not collected. Check them before you change zone 1 (e.g. #101456, tracker #111218) [C §7].
- **Release-cycle phase** (freeze or not) can't be read from git [T §3].
- **Undisclosed AI use**: the ~3.4 % disclosed rate is a lower bound [T §8].
- **Generated code** was not analysed: the C# API (`GodotSharp/Generated`) and non-shader `*.gen.h` dependencies. `MODULE_*_ENABLED` guards were not evaluated [S §9].
- **Fix share** is detected from commit subjects only. Churn from moved code (TileMap, visual shader, node_3d split) inflates line counts [T §8].
- **Windows differ**: [T]/[S] cover 6 months, [C] covers 12 months.
