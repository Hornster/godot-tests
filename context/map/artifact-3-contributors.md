# Artifact 3 — Contributors: `scene/resources` (git + GitHub, last 12 months)

> Draft evidence report for the Project Map. Not the final map; see `repo-map.md` (not yet written).
> Scope: `scene/resources/**`, including `2d/`, `3d/` and `audio/`. Chosen because artifact 2 (§7–§8) names it the main cross-layer risk zone: fan-in 73, and servers and core consume it.

| | |
|---|---|
| Repository | Godot Engine (`master`, HEAD `6765a18ca8`, 2026-10-22) |
| Window | 2025-10-22 → 2026-10-22 (12 months, by **commit** date, so it shows what landed in that period) |
| Volume | 191 non-merge commits → **184 meaningful**, **72 people**, **180 PRs** (all mapped through their merge commit) |
| Raw evidence | `context/map/evidence/contributors/`: `scene-resources.json` (commits), `summary.json` (topics and people), `prs.json` (GitHub reviews, labels and bodies) |
| Re-run | `python3 -I context/map/evidence/contributors/contributors.py 6765a18ca8 2025-10-22 scene/resources <out>.json` → `topics.py <in> <summary>.json` → `prs.py <summary> <prs>.json` |

## 1. Filtering and identity merge

| Removed | Commits | Detail |
|---|---:|---|
| Style / formatting | 5 | Thaddeus Crews (3: `rp_`→`p_`, `class_db.h` includes, `*.gen.inc`→`*.gen.h`) and Rémi Verschelde (2: include hook, clang-format grouping). |
| Mass mechanical | 1 | Rémi Verschelde, RenderingServer enums moved to `RSE` (49 files). |
| Agent-authored | 1 | `Claude <noreply@anthropic.com>` is the commit author on #112471, *Fix glow visual compatibility regression*. It was submitted by GitHub user Rudra-ravi and approved by clayjohn. It is excluded from the rankings, but the decision behind it is kept in §5. |
| Bots | 0 | None in this path. |
| Agent co-author trailers | 0 | No `Co-authored-by: <agent>` trailers exist, so no human+agent commits needed special handling. Two PRs in this window carry an *AI-assisted* disclosure in their PR text: #119819 (KoBeWi, re-submitting a contributor's AI-drafted fix) and #123602. Both are kept, because a human led them. |

**Identity merge.** Identities come from `.mailmap` (`%aN`). One case was merged by hand: **Rindbee** and **风青山** share one address, so they are one person. GitHub handles were taken from the authors of the merged PRs. The main ones: KoBeWi = Tomasz Chabora, TokageItLab = Silc 'Tokage' Renew, bruvzg = Pāvels Nadtočajevs, Ivorforce = Lukas Tenbrink, akien-mga = Rémi Verschelde, Repiteo = Thaddeus Crews, Calinou = Hugo Locurcio, YeldhamDev = Michael Alexsander, QbieShay = Ilaria Cislaghi, StarryWorm = Enzo Novoselic, clayjohn = Clay John, tdaven = Trevor Davenport, allenwp = Allen Pestaluky, zeux = Arseny Kapoulkine.

**Commit kinds** (in `topics.py`): 55 **cross-cutting** (include trimming, core type and API sweeps, build switches, moves into modules), 88 **feature/change**, 41 **fix**. Topic ownership (§3) counts only feature and fix commits. Without that rule, core refactorers would show up as "owners" of resources they only touched in passing.

⚠ Several PRs merged in the window were opened years earlier: #47054 (2021), #64487 (2022), #92102 (2024), #105701 (Apr 2025). Their authors were active on *that* problem, not necessarily during these 12 months.

## 2. Who worked here

### 2.1 Authors (≥ 3 meaningful commits, plus notable 2-commit domain owners)

| Person (handle) | Commits / PRs | Role here | Repeating topics | Active (commit dates) |
|---|---:|---|---|---|
| Lukas Tenbrink (Ivorforce) | 16 / 16 | **Cross-cutting core refactorer**: all 16 commits are core-type sweeps. | `memnew`→`Ref`, `cast_to` guards, `LocalVector`/`RBMap`/`HashMap` explicit ctors, `CowData` lifetimes, `RETURN_IF_ERROR`, `ContainerType` dedup, `ClassDB`→`GDType`, include trimming. Touches `packed_scene.cpp` and `resource_format_text.cpp` most often. | 2025-11 → 2026-09 |
| Pāvels Nadtočajevs (bruvzg) | 13 / 13 | **Domain owner: text and fonts.** | `font.cpp`, `text_line`/`text_paragraph`, HarfBuzz `hb-raster`, `DPITexture` importer, fuzzer-hardening of `Font*`, BOM in `.tres`. | 2025-10 → 2026-07 |
| Rémi Verschelde (akien-mga) | 11 / 10 | **Release manager / decoupler.** 9 of 11 commits are cross-cutting; the other 2 are reverts. | RenderingServer decoupling, explicit includes, clangd-tidy cleanup, **reverting regressions before release** (#115163, #118373). | 2026-01 → 2026-04 |
| Tomasz Chabora (KoBeWi) | 9 / 9 | **Generalist maintainer**, the author of `PropertyListHelper` on curves. | `_validate_property` cleanup, resource type hints, curve fixes, `.tscn` node-path regression, theme defaults from `ThemeDB`. | 2025-11 → 2026-10 |
| Silc 'Tokage' Renew (TokageItLab) | 9 / 9 | **Domain owner: animation and IK.** | `animation.cpp`/`.h` performance rewrite, `AnimationLibrary` storage, `IKModifier3D` + joint limitations, makima interpolation, compressed-track and slerp fixes. Largest domain author (+1164/−323). | 2025-11 → 2026-09 |
| Aaron Franke (aaronfranke) | 7 / 6 | Build modularity and `ImporterMesh`. | Visual shaders moved to a module (−21 k lines), disabling 2D in templates, `ImporterMesh` merge/convert, `world_*.h` include decoupling. | 2025-10 → 2026-08 |
| Hugo Locurcio (Calinou) | 6 / 6 | Usability / editor-facing defaults. | Theme sound items, auto-created default resources, `BaseMaterial3D` inspector groups and proximity-fade fix, hiding no-op `Shape3D` props. | 2025-12 → 2026-09 |
| Michael Alexsander (YeldhamDev) | 6 / 6 | **Domain owner: `MeshLibrary`.** | MeshLibrary editor, categories, `PropertyListHelper` port, `disable_physics_3d` builds, `RenderingDevice`-off builds. | 2025-10 → 2026-08 |
| Ilaria Cislaghi (QbieShay) | 6 / 6 | **Domain owner: particles.** | `ParticleProcessMaterial`: 3D scale/rotation, billboarding, preserve color, velocity in userdata, angular-velocity fix (breaks compat), sub-emitter velocity. | 2026-03 → 2026-06 |
| Leandro Benedet Garcia (leandro-benedet-garcia) | 5 / 5 | **Burst contributor on the text scene format**: 5 PRs in Aug 2026. | Metadata in `.tscn`, crash on a missing node name, `_printerr`→`ERR_PRINT`, more specific load errors. | 2026-08 only |
| kleonc | 5 / 5 | Precise fixer. | Curve regressions caused by #92282, TileSet transformed tiles and navigation winding, signal-connection flag in `PackedScene`. | 2025-12 → 2026-06 |
| Chaosus (Yuri Rubinsky) | 5 / 5 | **Domain owner: visual shaders.** | New VS inputs (`in_shadow_pass`, `specular_amount`, `instance_index`), reroute fix, shader-material subgroups. | 2025-10 → 2026-04 |
| smix8 | 5 / 5 | **Mass mover.** 4 of 5 commits are cross-cutting. | AudioServer split (+3.8 k/−2.1 k), TileMap(Layer) moved to a module (−8.3 k), Physics enums moved to their own files, WAV parse speed. | 2026-06 → 2026-07 |
| HolonProduction | 5 / 5 | Cross-cutting (`_WARN_UNUSED_` sweeps, `EditorLanguage`). | One or two lines per file. Not a domain contact. | 2026-07 → 2026-09 |
| Rindbee | 3 / 2 | **Domain specialist: scene instancing.** | `resource_local_to_scene` on duplicated and inherited scenes, "Editable Children". | 2025-11 → 2026-01 |
| DeeJayLSP | 3 / 3 | Audio streams (WAV/QOA). | `AudioStreamWAV` tags, data length, `qoa.h` update. | 2026-02 → 2026-05 |
| Arseny Kapoulkine (zeux) | 3 / 3 | Mesh processing (meshoptimizer author). | Tangent generation with vertex splitting replaces mikktspace in `SurfaceTool`. | 2026-05 → 2026-07 |
| Enzo Novoselic (StarryWorm) | 3 / 2 | Structural. | Split `ResourceFormat*` out of texture classes (#117774, +534/−340). | 2026-02 → 2026-03 |
| Allen Pestaluky (allenwp) | 3 / 3 | Tonemapping / color. | AgX white/contrast, `Environment` brightness/HDR, LinearToSRGB clamping. | 2025-10 → 2026-02 |
| Ryan (Ryan-000) | 3 / 3 | Animation performance. | `_track_update_hash`, AnimationTree internals, "Inherit Emitter Scale". | 2025-10 → 2026-03 |
| Trevor Davenport (tdaven) | 2 / 2 | **Texture mip streaming** (#113429, +832). | `streamed_texture.*`, streaming feedback in `material.cpp`. | 2026-08 → 2026-09 |
| nikitalita | 2 / 2 | Godot 3.x → 4 mesh conversion. | v3 normals and tangents, 65536-vertex edge case. | 2026-06 → 2026-10 |

46 of the 72 people made exactly one commit here (drive-by fixes and features).

### 2.2 Reviewers / gatekeepers (approvals on the 180 PRs, excluding self)

| Handle | Approvals | Any review | Where they approve most |
|---|---:|---:|---|
| akien-mga | 26 | 36 | Text/fonts (8), regressions near release |
| Ivorforce | 25 | 25 | Core-type sweeps, audio streams |
| clayjohn | 22 | 23 | **Materials, textures, mesh, environment**: the rendering gate |
| KoBeWi | 21 | 28 | **Scene serialization (6)**, curves, mesh |
| Repiteo | 20 | 23 | Build, style, serialization |
| Calinou | 19 | 24 | Materials, usability |
| AThousandShips | 14 | **45** | Broad style/code review; most active reviewer by volume |
| YeldhamDev | 12 | 12 | Scene serialization (5) |
| TokageItLab | 11 | 11 | Animation (6), the only animation approver besides lyuma and fire |
| QbieShay / paddy-exe | 8 / 7 | 8 / 7 | Particles; paddy-exe also visual shaders (5) |
| fire / lyuma | 9 / 7 | 12 / 7 | Animation, IK, mesh import |
| BlueCube3310 | 7 | 8 | Textures, compression, mesh conversion |
| groud | 3 | 3 | TileSet: the original TileMap author, still the TileSet gate |

107 of 180 PRs (59 %) carry an approval from at least one of the six core maintainers (akien-mga, Ivorforce, clayjohn, KoBeWi, Repiteo, Calinou). Only 1 PR merged without any approval: the release revert #115163.

## 3. Repeating topics: who owns what

Counted from feature and fix commits only. "Top-1" is the share of the most active author.

| Topic (files) | Commits | Authors | Top-1 | Author core | Approval core | Pattern |
|---|---:|---:|---:|---|---|---|
| Scene serialization (`packed_scene`, `resource_format_text`) | 17 | 11 | 29 % | Leandro Benedet Garcia, Rindbee, kleonc, Raul Santos, KoBeWi | KoBeWi, YeldhamDev, Repiteo | Spread among authors, **approval concentrated**. Also the target of most core sweeps (Ivorforce). |
| Materials & shaders (`material`, `shader*`, sky/fog) | 17 | **14** | 12 % | No owner: Trevor Davenport, Hugo Locurcio, Bastiaan Olij, GameBeast… | **clayjohn**, Calinou, BastiaanOlij | **Drive-by heavy, one rendering gate.** 2 of the 3 reverts in this window happened here. |
| Text, fonts & UI theme | 17 | 8 | **59 %** | **Pāvels Nadtočajevs** | akien-mga, bruvzg | **Single expert.** |
| Animation & IK | 14 | 6 | **57 %** | **Silc 'Tokage' Renew**, Ryan, M. Sadık Uğursoy, chocola-mint | **TokageItLab**, lyuma, fire | **Single expert, who is also the main approver.** |
| Textures & streaming | 13 | 12 | 15 % | Enzo Novoselic, Trevor Davenport, Johanna Lindquist, BlueCube3310 | clayjohn, BlueCube3310, KoBeWi | Spread out; streaming is new (#113429). |
| Mesh & geometry | 13 | 8 | 23 % | Michael Alexsander (MeshLibrary), nikitalita (3.x convert), Arseny Kapoulkine (SurfaceTool), Aaron Franke (ImporterMesh) | clayjohn, KoBeWi, fire | Split by sub-component: one person per class. |
| Visual shaders | 11 | 8 | 36 % | **Chaosus** | paddy-exe, clayjohn | Single expert, but the code is now in `modules/visual_shader` (#64596). |
| Particles (`particle_process_material`) | 10 | 5 | **60 %** | **Ilaria Cislaghi** | **QbieShay**, paddy-exe | **Single expert who is also the approver.** |
| Curves & gradients | 6 | 4 | 33 % | kleonc, KoBeWi | AThousandShips, KoBeWi | Fix tail of KoBeWi's #92282. |
| TileSet & 2D navigation | 6 | 5 | 33 % | kleonc | groud | Code moved to `modules/tilemap` (#121548). |
| Environment & camera | 5 | 4 | 40 % | Allen Pestaluky, Clay John | clayjohn | |
| Audio streams | 5 | 3 | 60 % | DeeJayLSP | Ivorforce | Small volume; AudioServer split by smix8. |
| 2D skeleton mods, shapes, SpriteFrames | 5 | 5 | — | One-off contributors | TokageItLab, lyuma | No owner. |

### Themes that recur across people

1. **Serialization compatibility.** Changes in *how a property is stored* break old files, and different people fix them months later.
   - KoBeWi's `PropertyListHelper` for curves (#92282) → kleonc fixes storage flags (#116331) and `Curve3D` control points (#120684) → KoBeWi fixes point-count expansion (#119819).
   - AnimationLibrary `libraries` → `libraries/<name>` (TokageItLab #112692/#116394) → Joshua Bordelon's 4.5-compat fix in `packed_scene.cpp` (#114844).
   - Also: removing `load_steps` (#103352), restoring the `./` node-path prefix (#115231), metadata in `.tscn` (#121920), 3.x mesh conversion (#119595, #124412).
2. **Reverts and changed defaults in rendering-facing resources.** Three reverts, all in materials or particles: #115163 (stereo fixed size), #116140 (particle curve ranges), #118373 (particle-shader uniforms). There are two default-value regressions: glow threshold (#110077 → #112471) and particle curve range (#91556 → reverted → narrowed re-do #123959). One fix was explicitly labelled *breaks compat* (#117861 angular velocity).
3. **`resource_local_to_scene` and inherited scenes.** Rindbee (#64487, #115557) and Raul Santos (#118822, a C# script-attach ordering issue) changed the same instancing code in `packed_scene.cpp`.
4. **Fuzzer-driven hardening.** These came from fuzzer issues filed in summer 2026: `FontFile` index checks (#121357), `Animation::track_move_up` (#121265), and a crash on a `.tscn` node without a name (#122578).
5. **Moving code out of `scene/resources`.** Visual shaders → module (#64596), TileSet → `modules/tilemap` (#121548), AudioServer split (#121547), `ResourceFormat*` split from texture classes (#117774), RenderingServer decoupling (#116454, #116976). This explains the net −6.6 k lines in artifact 1.

## 4. Spread or focused? Verdict

**Authorship of the folder overall is spread out. Expertise in the sub-domains is concentrated, and the right to merge is concentrated in a small maintainer group.**

- **Folder level:** 72 authors. The top 3 hold only 22 % of commits, 11 people produce half of them, and 46 people committed once. No single person is a bottleneck for "`scene/resources`" as a whole.
- **Sub-domain level:** for a project of Godot's size (371 authors in 6 months, artifact 1), one person owning a sub-domain is a real **bus-factor risk**, not a normal small-team pattern:
  - **Animation**: Silc 'Tokage' Renew writes about 57 % *and* approves most of it. The only other approvers are lyuma and fire.
  - **Particles**: Ilaria Cislaghi writes 60 % and is the main approver (paddy-exe is the backup).
  - **Text/fonts**: Pāvels Nadtočajevs writes 59 %. Reviews mostly come from akien-mga, who is a release manager, not a text expert.
  - **Visual shaders**: Chaosus. This is now mostly a module concern.
- **No-owner zones** (many drive-by authors, held together by a reviewer): **Materials & shaders** and **Textures**. clayjohn is the de-facto owner through review rather than authorship. This is also where the reverts cluster (§3, theme 2). These sub-areas have **no unit tests** for `BaseMaterial3D`/`StandardMaterial3D`, `ParticleProcessMaterial`, `VisualShader` or `Environment` (0 references under `tests/`).
- **Serialization** has several authors, but the knowledge of *why* the format looks the way it does sits with KoBeWi, YeldhamDev and Repiteo as approvers. Leandro Benedet Garcia's 5-PR burst in August 2026 is recent and fresh. `ResourceFormatLoaderText` has no direct tests; `.tscn` round-trips are covered only indirectly (6 test files reference `.tscn`; `test_packed_scene.cpp` exists).
- **Cross-cutting authors** (Lukas Tenbrink, Rémi Verschelde, HolonProduction, smix8, StarryWorm): ask them about *structure* (includes, module boundaries, core types), not about resource behaviour.

## 5. Worth validating before you change anything

Grouped by where you would make the change. Each item lists the PR to read and what to check.

### Scene serialization (`packed_scene.cpp`, `resource_format_text.cpp`)
| PR | Why read it | Check before changing |
|---|---|---|
| #114844 (4.5→4.6 AnimationLibrary compat, approved by TokageItLab and akien-mga) | `packed_scene.cpp` now contains a compatibility branch for the old `libraries` dictionary. | Any change to how a resource exposes properties can make imported scenes with *editable children* write full data into `.tscn`. |
| #121920 (metadata in text scenes; supersedes #82532) | Decision: `[resource]` header only when metadata exists, so old scenes stay byte-identical. Embedded `PackedScene`s are saved as resources with a node list. | Keep `.tscn` output unchanged for scenes without metadata. |
| #103352 (`load_steps` removed) | Decision: a stable diff matters more than a load progress bar. Known drawback: progress is not exact. | Don't reintroduce counters into the header. |
| #115231 (restore `./` in node paths) | A "probably accidental" change broke `SceneState.get_node_path()` (#115223). | Node-path string form is part of the API. |
| #122578, #122773–#122863 | A node without a name breaks the `names` pairing → out-of-bounds access. The error macros were reworked. | `SceneState.names` must stay paired; corrupt files must fail with an error, not crash. |
| #64487, #115557 (Rindbee) | `resource_local_to_scene` across duplicated and inherited scenes. Arrays are handled; **dictionary keys are explicitly unsupported**. | Inherited and instanced scenes with local-to-scene resources inside `Array`/`Dictionary`. |
| #118822 (Raul Santos) | Node-path properties are resolved *after* the inherited scene is fully instantiated, because C# script attachment disposed the earlier instances. | Ordering inside `instantiate()` matters for C#. |
| #111965 (Ivorforce, label `discussion`) | `memnew(RefCounted)` now returns `Ref`. Ownership rules changed in loaders. | Raw `RefCounted*` in loader code will now fail to compile or behave differently. |

### Materials, particles, shaders
| PR | Why read it | Check before changing |
|---|---|---|
| #110410 → #115163 (revert) → #115147 | The stereo fixed-size fix broke mono rendering. The redo switches on `USE_MULTIVIEW`. | Test mono **and** stereo (XR) for any billboard or fixed-size shader path in `material.cpp`. |
| #110287 → #118373 (revert) | A one-line uniform fix ("not sure of ramifications") caused `material is null` errors and an invisible gizmo. **#101456 is still open.** | Changes to `ShaderMaterial` parameter handling reach editor gizmos. |
| #91556 → #116140 (revert) → #123959 | A global curve-range change broke blank directional-velocity axes. The redo touches angles only. | Default ranges on `ParticleProcessMaterial` curves are user-visible behaviour. |
| #117861 (`breaks compat`) | Angular velocity was knowingly fixed even though existing workarounds break ("needs to be communicated"). | Particle behaviour fixes need a release-note decision. |
| #110077 → #112471 | The mobile glow overhaul changed the `glow_hdr_threshold` default from 1.0 to 0.0 and broke existing projects. It was restored to 1.0. | Treat default values in `environment.h` as compatibility surface. |
| #120786 (KoBeWi) | Particle animation was separated from billboard mode in `BaseMaterial3D`. | Shader-generation flags in `material.cpp` are combinatorial; #124201 fixed duplicate variables (refraction + proximity fade). |

### Animation
| PR | Why read it | Check before changing |
|---|---|---|
| #117030 (TrackCache IDs) | The hash-collision saga (#110439 → this). It rejected `StringName` hashing for performance reasons and uses pointer IDs instead. | Don't reintroduce hashed track keys. |
| #116394, #112692 | `AnimationLibrary` switched to `RBMap` (stable order) and the resource was optimized. | Ordering is now deterministic; serialization relies on it (see #114844). |
| #123835 (makima + key-retrieval refactor) | Looped-key retrieval was refactored. It closes old cubic-overshoot issues. | Looped animations with keys at the start or end. |
| #116046 | `track_get_key_indices_in_range()` ignored animation sections. | Section-aware playback (`play_section_with_markers`). |
| #120403 | Fold state is read from `.cfg` only at project save and load. The earlier behaviour froze the editor. | Don't touch the editor cfg from resource code paths. |

### Textures, mesh, curves
| PR | Why read it | Check before changing |
|---|---|---|
| #113429 (texture mip streaming: 114 comments, 66 review threads) | A new streaming architecture, approved by clayjohn, BastiaanOlij and others. The old `CompressedTexture` streaming was removed (#122940). | Read the discussion before touching `streamed_texture.*` or texture feedback in `material.cpp`. Follow-up fix: #123662. |
| #115003 (`breaks compat`, ASTC profiles) | The Image API block-size argument was replaced by compression profiles. | Portable compressed texture formats. |
| #119595, #124412 (cherry-picked to 4.6/4.7) | 3.x mesh conversion: normal/tangent mix-up, and `< 65536` vs `<= 65536` 16-bit index boundary. #124729 then fixed a `deprecated=no` build. | Keep `DISABLE_DEPRECATED` builds compiling. |
| #92282 + #116331 + #120684 + #119819 | Curve per-point properties must be **editor-only**; real data lives in `_data`. `Curve3D` has a different filter condition. | Property usage flags on `PropertyListHelper`-based resources. |
| #117774 (StarryWorm) | `ResourceFormat*` classes were split into `*_resource_format.*` files (part of tracker #111218, **open**). | Where loaders now live. |

## 6. Who to ask (routing)

| Question about… | First contact | Backup / reviewer |
|---|---|---|
| `.tscn`/`.tres` format, `PackedScene` | KoBeWi | YeldhamDev, Repiteo; Leandro Benedet Garcia (recent work) |
| Local-to-scene, inherited scene instancing | Rindbee | Raul Santos (C# angle), KoBeWi |
| Animation, AnimationLibrary, IK | TokageItLab | lyuma, fire |
| Particles | QbieShay | paddy-exe |
| Materials, environment, textures, rendering defaults | clayjohn | Calinou, BastiaanOlij (XR), BlueCube3310 (compression) |
| Texture streaming | tdaven | clayjohn |
| Fonts, text shaping | bruvzg | akien-mga |
| Visual shaders | Chaosus | paddy-exe |
| MeshLibrary | YeldhamDev | — |
| SurfaceTool / mesh processing | zeux | clayjohn |
| Curves | kleonc | KoBeWi |
| Includes, core types, module boundaries | Ivorforce, akien-mga | Repiteo, smix8 |

## 7. Unknowns

- **Reviewer knowledge vs. rubber-stamping.** Approval counts show *who gates*, not who understands. They can't separate deep review from a release-manager sign-off (akien-mga's approvals on text/fonts are an example).
- **Activity outside this path.** People who moved with code into modules (TileSet → `modules/tilemap`, visual shaders → `modules/visual_shader`, AudioServer) are under-counted here. Their current involvement in the moved code was not measured.
- **Open PRs and in-flight work** touching `scene/resources` were not collected. Before changing anything, check what is pending: for example, the deferred stereo work behind #115163/#115147, open #101456, and tracker #111218.
- **Partial AI disclosure.** Disclosures in PR bodies are self-reported. One agent-authored commit was found by its author field; others may be unlabelled.
- **Contributor status** (maintainer team membership, availability, timezone) is not visible from git or the PR data.
- **Topic regexes** are path-based. Commits touching `material.cpp` for particle or streaming reasons count as "Materials & shaders". The per-commit list is in `summary.json` if a finer split is needed.
