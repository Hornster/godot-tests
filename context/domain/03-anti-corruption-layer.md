---
title: "Anti-corruption layer: polygon clipping (Clipper2) behind a PolygonSet2D value object and a narrow port (refactor plan)"
created: 2026-11-02
type: refactor-plan
git_commit: a27e041bc3
builds_on: context/domain/01-domain-distillation.md
status: proposed
---

# Anti-corruption layer for polygon clipping (Clipper2)

**Legend.** **[E]** = evidence seen at the cited `file:line` (each one re-read for this document at `a27e041bc3`). **[I]** = inference drawn from evidence. **[?]** = unknown; not a claim that the thing is absent.

This is a **plan**. No production code was changed. Code blocks below are signatures and pseudocode for the plan interview (`/10x-plan`), not an implementation.

---

## 0. Context (Step 0)

### 0.1 Source documents

| Kind | What exists | Used as |
|---|---|---|
| PRD / tech-stack | **None.** `context/foundation/` holds only `README.md`. No `prd.md` or `tech-stack.md` anywhere (same finding as `01-domain-distillation.md` §0.1). | — |
| README | `README.md:9-17` (product statement) | Product vision |
| Specification proxy | `doc/classes/*.xml`. For this topic: `doc/classes/Geometry2D.xml` (polygon boolean ops, offsetting) | The public, library-neutral contract |
| Dependency manifest | Godot vendors its dependencies. The manifest is `thirdparty/README.md` (one `##` section per library, with version and patches), plus the `builtin_<lib>` options in `SConstruct:334-…` and their `pkg-config` fallbacks in `platform/*/detect.py`. | List of external dependencies, and the **declared** replaceability |
| Earlier analyses | `context/domain/01-…`, `02-…`, `context/changes/refactor-opportunities/{research,plan}.md`, `context/map/repo-map.md` | Phase conventions; none of them covers third-party dependencies |

**Declarations of replaceability.** No prose document says "X is isolated so it can be swapped". The engine states replaceability in its build system instead:

- **[E]** `SConstruct:336`: `opts.Add(BoolVariable("builtin_clipper2", "Use the built-in Clipper2 library", True))`. Every `builtin_<lib>` option is a promise to distro packagers: "you may swap the vendored copy for a system copy".
- **[E]** For other libraries that promise is kept. `platform/linuxbsd/detect.py:275` (`builtin_libpng` → `pkg-config libpng16`), `:284-285` (`builtin_zstd` → `pkg-config libzstd`), `:441-442` (`builtin_zlib` → `pkg-config zlib`).
- **[E]** `thirdparty/README.md:120-134` records Clipper2 2.0.1 with two Godot patches. The library has been upgraded five times (§3.4) and **replaced once**: Clipper1 → Clipper2 in `8a28f816d0` (2024-04-02).
- **[E]** The public contract is library-neutral. `doc/classes/Geometry2D.xml:32` says holes are distinguished "by calling [method is_polygon_clockwise]", which is a Godot function, not a Clipper concept.

### 0.2 Stack and layers

C++17 engine built with SCons. Layer order (`main/main.cpp` boot order; `repo-map.md` §1):

| Layer | Directory | May depend on |
|---|---|---|
| Core (math, I/O, types) | `core/` | thirdparty only |
| Servers (low-level APIs) | `servers/` | core |
| Scene (nodes, resources) | `scene/` | core, servers |
| Modules (optional features, server implementations) | `modules/<name>/` | core, servers, scene |
| Editor (UI) | `editor/` | everything |
| Drivers / platform | `drivers/`, `platform/` | core, servers |

Third-party libraries are compiled by the SCsub of the layer that owns them. The engine's own convention is that one wrapper class owns a library: `Compression` for zlib/zstd/brotli, `Geometry2D` for Clipper2 and polypartition, `drivers/png` for libpng.

---

## 1. Leaking dependencies (Step 1)

Method: for every directory in `thirdparty/`, list engine source files (`*.cpp`, `*.h`, `*.mm`) outside the library's own wrapper that include it. Then grep the headers that are included without a `thirdparty/` prefix (`zlib.h`, `zstd.h`, `png.h`, `mbedtls/…`). Libraries that only one module or driver includes (enet, openxr, glslang, meshoptimizer, …) are **not leaks**: the module *is* the wrapper.

### 1.1 Clipper2 (polygon boolean operations, offsetting, rect clipping)

**Wrapper that exists:** `Geometry2D` (`core/math/geometry_2d.{h,cpp}`). Its header is clean: it includes only Godot math headers (`geometry_2d.h:33-40`) and exposes Godot enums (`PolyBooleanOperation`, `PolyJoinType`, `PolyEndType`, `:288-305`).

**Every file that knows Clipper2 today:**

| # | File:line | Layer | What it knows |
|---|---|---|---|
| K1 | `core/math/geometry_2d.cpp:36` (include), `:42` (`clipper_precision = 5`), `:44-76` (`merge_many_polygons`: `Union` `:57`, `SimplifyPaths` `:58`, `IsPositive` `:70`), `:250-310` (`_polypaths_do_operation`: `ClipperD` `:279`, `Execute` `:292, 294`), `:312-372` (`_polypath_offset`: `InflatePaths` `:355`) | core | The wrapper. 21 Clipper2 references. |
| K2 | `scene/2d/mesh_instance_2d.cpp:41` (include), `:157-215` (`PathsD` `:159`, `PathD` `:170`, `PointD` `:189, 194`, `Union` `:203`, back-conversion `:207-211`) | scene | `navmesh_parse_source_geometry` builds Clipper paths itself. |
| K3 | `scene/2d/multimesh_instance_2d.cpp:41` (include), `:161-227` (`Union` `:205`, back-conversion `:219-224`) | scene | Same block as K2, copied. |
| K4 | `editor/scene/2d/sprite_2d_editor_plugin.cpp:55` (include), `:57` (`#define PRECISION 1`), `:66-103` (`expand`: `InflatePaths` `:75`, `RectD` `:82`, `RectClip` `:86`, back-conversion `:93-101`) | editor | Outline growth for "Convert to Polygon2D / Collision / Occluder". |
| K5 | `modules/navigation_2d/2d/nav_mesh_generator_2d.cpp:42` (include), `:275-300` (recursion over `PolyPathD`), `:317-477` (`RectClip` `:399, 400, 457`; `Union` `:405, 407`; `Difference` `:409, 440`; `InflatePaths` `:413`; `IsPositive` `:371, 434`; `ClipperD` `:470`; `Execute` `:473`) | module | The whole 2D navmesh baking pipeline, written directly in Clipper2. |
| K6 | `servers/navigation_2d/navigation_server_2d.h:44-46` (`#ifdef CLIPPER2_ENABLED` around `class NavMeshGenerator2D;`) | servers | The library's **build flag** in a server interface header. |
| K7 | `modules/navigation_2d/2d/godot_navigation_server_2d.h:60-62, 88-90`; `godot_navigation_server_2d.cpp:39-41, 83-145, 1202, 1388`; `nav_mesh_generator_2d.h:33, 104`; `nav_mesh_generator_2d.cpp:31, 531` | module | `CLIPPER2_ENABLED` decides whether navmesh baking exists at all. |
| K8 | `core/SCsub:111-127`. Note `:122` `env.Prepend(CPPPATH=[…clipper2/include])` and `:125` `env.Append(CPPDEFINES=["CLIPPER2_ENABLED"])` on the **global** `env`, not on `env_thirdparty` | build | This is what makes the leak possible. Every later SCsub, including modules and the editor, inherits the include path and the define. |
| K9 | `SConstruct:336` (`builtin_clipper2`) | build | The replaceability promise. |

Callers that **do** go through the wrapper: `core/core_bind.cpp` (24 calls to Geometry2D polygon ops, the script API), `modules/tilemap/tile_map_layer.cpp:932, 935` (`merge_many_polygons`, `decompose_many_polygons_in_convex`), `modules/tilemap/editor/tile_data_editors.cpp` (4 calls). The wrapper works when people use it.

Structural count (ast-grep 0.50, `-l cpp`, over K1–K5): `Union(…)` 5 sites, `Difference(…)` 2, `InflatePaths(…)` 2 unqualified + 1 qualified in K4, `RectClip(…)` 3 unqualified + 1 qualified in K4, `ClipperD` objects 2. The qualified `Clipper2Lib::…` calls in K4 did not match an ast-grep pattern, so they were confirmed with grep (`sprite_2d_editor_plugin.cpp:75, 86`).

### 1.2 Other candidates found

| ID | Library | Files that know it, outside its wrapper | Layers |
|---|---|---|---|
| L2 | **polypartition** (`thirdparty/misc/polypartition.h`) | `core/math/geometry_2d.cpp:38` (wrapper), `scene/resources/2d/navigation_polygon.cpp:37`, `scene/resources/3d/primitive_meshes.cpp:44`, `modules/navigation_2d/2d/nav_mesh_generator_2d.cpp:43` | core, scene, module |
| L3 | **zlib** | Wrapper `core/io/compression.cpp:37`, `core/io/stream_peer_gzip.cpp:36`. Outside it: `drivers/d3d12/rendering_shader_container_d3d12.cpp:40` (`crc32` `:773-774`), `drivers/metal/sha256_digest.h:38` (`crc32` `:46`), `modules/objectdb_profiler/editor/snapshot_data.cpp:44` (compares a `Compression::decompress_dynamic` result with `Z_OK`, `:354-355`). `modules/tinyexr/*` is legitimate (tinyexr needs zlib). | core, drivers, module/editor |
| L4 | **zstd** | Wrapper `core/io/compression.cpp:38`; also `core/io/delta_encoding.cpp:37`; `editor/export/project_export.cpp:68` (UI range from `ZSTD_minCLevel()` `:1856`) | core, editor |
| L5 | **spirv-reflect** | `servers/rendering/rendering_shader_container.cpp:36`, `drivers/metal/rendering_shader_container_metal.cpp:39` | servers, drivers |
| L6 | **libpng** | Wrapper `drivers/png/png_driver_common.cpp:37`; `platform/web/display_server_web.cpp:55` (`png_image` `:536-539`) | drivers, platform |
| L7 | **mbedtls** | `core/crypto/crypto_core.cpp:36` plus `modules/mbedtls/*` | core, module |

---

## 2. Classification and choice (Step 2)

Axes: **(a)** files and layers that know the library, outside its wrapper. **(b)** Risk and cost of a swap or upgrade *today*. **(c)** Gap between the declared replaceability and the code.

| ID | (a) files / layers | (b) swap or upgrade cost | (c) intent vs code | Verdict |
|---|---|---|---|---|
| **L1 Clipper2** | **4 files outside the wrapper, in 3 layers (scene, editor, module), plus a build flag in a 4th (servers)**; 9 locations K1–K9 | **High, and demonstrated.** The 1→2 swap had to edit the editor bypass (`8a28f816d0`: `sprite_2d_editor_plugin.cpp` 63 lines). A *minor* upgrade had to edit the module (`973448ec4c`, 1.3.0: `RectClip` → `RectClip64` in `nav_mesh_generator_2d.cpp`). The leak has since grown: scene got two copies in `0ed2cb0439` (2024-12-28). There is also hidden semantic drift: precision differs per site (§3.2). | **Broken.** `builtin_clipper2` exists (`SConstruct:336`) but no `detect.py` has a system-Clipper2 branch. The include is repo-rooted (`<thirdparty/clipper2/…>`), and `CLIPPER2_ENABLED` is only defined on the builtin path (`core/SCsub:112, 125`). | **#1** |
| L2 polypartition | 3 outside the wrapper / 3 layers | Medium; no version churn (`misc/`) | No `builtin_` option, so nothing is promised | #2. It is coupled to L1 in K5 (`PolyPathD` → `TPPLPoly`, `nav_mesh_generator_2d.cpp:275-300`). Natural follow-up. |
| L3 zlib | 3 outside / 3 layers; mostly `crc32` | Low (`crc32` is stable) | Promise kept (`detect.py:441-442`) | #3. The `Z_OK` leak through `Compression`'s return value is the interesting part. |
| L4 zstd | 2 outside / 2 layers | Low | Promise kept (`detect.py:284-285`) | #4 |
| L5 spirv-reflect | 2 / server + driver | Medium | No `builtin_` option | #5. It sits on one side of a server→driver boundary that is meant to share code. |
| L6 libpng | 1 outside / platform | Low | Promise kept (`detect.py:275`) | #6 |
| L7 mbedtls | 1 outside / core | Low | — | #7. Core crypto primitives; deliberate. |

**Choice: L1, Clipper2.** It is the only candidate that scores worst on all three axes. It crosses the most layers, including the editor (UI) and a server header. Its swap and upgrade costs are on record, not hypothetical. And it is the one library whose `builtin_` promise the code breaks. A wrapper already exists and has a clean header (§1.1), so the fix is a Strangler Fig around a working seam, not a new abstraction from nothing.

---

## 3. Diagnosis (Step 3)

### 3.1 Duplication of the Godot ↔ Clipper2 mapping

The same two conversions are written out by hand **13 times**:

| Conversion | Sites |
|---|---|
| `Vector<Vector2>` → `PathD` | `geometry_2d.cpp:49-53, 270-277, 349-352`; `mesh_instance_2d.cpp:186-196`; `multimesh_instance_2d.cpp:190-200`; `sprite_2d_editor_plugin.cpp:70-73`; `nav_mesh_generator_2d.cpp:339-345, 348-354, 366-369, 379-384, 429-432` |
| `PathD` → `Vector<Vector2>` | `geometry_2d.cpp:65-68, 299-308, 359-368`; `mesh_instance_2d.cpp:207-211`; `multimesh_instance_2d.cpp:219-224`; `sprite_2d_editor_plugin.cpp:93-101`; `nav_mesh_generator_2d.cpp:283-286` |

K2 and K3 are the same 45-line block (`mesh_instance_2d.cpp:157-203` ≈ `multimesh_instance_2d.cpp:161-205`): surface filter, index/non-index branch, one path per surface, `Union` with an empty clip set. Only the variable names differ.

Orientation is also duplicated: `nav_mesh_generator_2d.cpp:371-373` and `:434-436` both do "if `!IsPositive`, reverse".

### 3.2 Semantic drift: the precision rule lives in library defaults

Per the Clipper2 docs (Context7 `/websites/angusj_clipper2`: Union, Difference, InflatePaths, ClipperD constructor), `precision` / `decimalPrec` on `PathsD` APIs is **the number of decimal places kept** when coordinates are scaled to int64 internally. It defaults to 2 and is capped at 8. The vendored header confirms the defaults (`clipper.h:87, 101, 118, 147, 216, 231`; `clipper.engine.h:529`) and the cap (`clipper.core.h:65`). An out-of-range value is **silently clamped** (`clipper.core.h:686-692`; with Godot's `0001-disable-exceptions.patch`, `DoError` "does nothing").

Effective precision, site by site:

| Site | Op | Precision | Where it comes from |
|---|---|---|---|
| `geometry_2d.cpp:279, 355` | boolean ops, offset | **5** | `clipper_precision` `:42` ("Based on CMP_EPSILON") |
| `geometry_2d.cpp:57` (`merge_many_polygons`) | Union | **2** | library default. Drift *inside* the wrapper: `clipper_precision` is in scope but not passed. |
| `mesh_instance_2d.cpp:203`, `multimesh_instance_2d.cpp:205` | Union | **2** | library default |
| `nav_mesh_generator_2d.cpp:399-473` (all) | RectClip, Union, Difference, InflatePaths, ClipperD | **2** | library default. History: integer `Paths64` (0 decimals) until `6a4d8d4b5c` (2024-03-27, "use floating point coordinates") |
| `sprite_2d_editor_plugin.cpp:75, 86` | InflatePaths, RectClip | **1** | local `#define PRECISION 1` `:57` |

[I] Some of these values may be deliberate (navmesh vertices are in pixels; sprite outlines are snapped to pixels). But no site says so except `geometry_2d.cpp:42`. Four of the five values come from whatever the library's default happens to be. A replacement library has no "default precision 2", so a swap would silently change navmesh output unless someone reverse-engineered these defaults. **This is the knowledge the ACL must make explicit.**

### 3.3 Leaks across boundaries

1. **Editor (UI) → library.** `Sprite2DEditor` constructs `Clipper2Lib::RectD` and calls `RectClip` (`sprite_2d_editor_plugin.cpp:82-86`). The UI layer receives raw `PathsD`, indexes `solution[0]` (`:79, 86`) and `out[0]` (`:91`), and converts back by hand (`:93-101`).
2. **Scene → library.** `MeshInstance2D` and `MultiMeshInstance2D` are runtime nodes. They include a vendored header from `thirdparty/` (`:41` in both) that core put on the global include path (`core/SCsub:122`). Scene never asked for it.
3. **Library build flag → server interface.** `servers/navigation_2d/navigation_server_2d.h:44-46` uses `CLIPPER2_ENABLED`. The server API is meant to be backend-neutral; it now names a vendored library.
4. **Library build flag → feature availability.** With `builtin_clipper2=no`, `CLIPPER2_ENABLED` is undefined (`core/SCsub:112, 125`), so `NavMeshGenerator2D` is compiled out and `bake_from_source_geometry_data*` return silently (`godot_navigation_server_2d.cpp:118-141`), and `is_baking_navigation_polygon` returns `false` (`:145-149`). Meanwhile K1–K4 still include Clipper2 unconditionally through the repo-rooted path. [I] Not built in this session: such a build would most likely fail to link (no `clipper.engine.cpp` is compiled, `core/SCsub:114-127`, and `ClipperD`/`ClipperBase` are not header-only). Even if it linked, 2D baking would be disabled without a word.

### 3.4 Declared replaceability vs code

- **Declared:** `SConstruct:336`, *"Use the built-in Clipper2 library"* (default `True`; `False` means "use a system copy").
- **Convention for keeping the promise:** a `pkg-config` branch in `platform/*/detect.py`, as for libpng (`:275`), zstd (`:284-285`) and zlib (`:441-442`).
- **Code:** no `detect.py` mentions Clipper2 (grep over `platform/*/detect.py`, `methods.py`, `SConstruct`, all `config.py`/`SCsub`: only `SConstruct:336` and `core/SCsub:112-125`). All five consumers hard-code the vendored path. **The option cannot be honoured.**
- **Cost on record:**

| Commit | Event | Engine files outside `thirdparty/` that had to change |
|---|---|---|
| `8a28f816d0` (2024-04-02) | Replace Clipper1 → Clipper2 | `core/math/geometry_2d.cpp` (111 lines), `editor/plugins/sprite_2d_editor_plugin.cpp` (63), `tests/core/math/test_geometry_2d.h` (8: vertex order of results changed, see §5.3 Q2) |
| `973448ec4c` (2024-03-01) | Upgrade to 1.3.0 | `modules/navigation/2d/nav_mesh_generator_2d.cpp` (`RectClip` → `RectClip64`) |
| `0ed2cb0439` (2024-12-28) | Nodes parse their own nav geometry | Leak spreads to `scene/2d/mesh_instance_2d.cpp`, `scene/2d/multimesh_instance_2d.cpp` |
| `1bd52fed76`, `100225c081`, `256fa39e51`, `0a04aa9186` | Upgrades 1.4.0 → 2.0.1 | none outside `thirdparty/`, `COPYRIGHT.txt`, `thirdparty/README.md`. API stable by luck, not by design. |

### 3.5 Guard coverage today

- Geometry2D boolean ops are pinned: `tests/core/math/test_geometry_2d.cpp:449` (merge), `:516` (clip), `:573` (exclude), `:620` (intersect polyline), `:672` (clip polyline), plus `:370` (polygon intersection).
- **Not pinned:** `offset_polygon` and `offset_polyline` (grep of `tests/`: 0). `merge_many_polygons` and `decompose_many_polygons_in_convex` (0). `Sprite2DEditor::expand` (0).
- Nav baking is pinned only through `Polygon2D`. `tests/servers/test_navigation_server_2d.cpp:545, 595` cover parse and bake, and both carry `// TODO: Use MeshInstance2D as well?` (`:555, 605`). So K2, K3, and K5's obstruction, carve, agent-radius and border paths have no guard.

---

## 4. ACL design (Step 4)

### 4.1 Boundary and location

```
core/math/polygon_clipping/            ← the ONLY place that knows Clipper2
├── polygon_set_2d.h / .cpp            value object (library-free header)
├── clip_precision.h                   named precision policy (library-free)
├── polygon_clipper_2d.h               the port (library-free header)
├── polygon_clipper_2d_clipper2.cpp    the adapter (only file that includes clipper.h)
└── clipper2_codec.h                   private: PolygonSet2D <-> PathsD, included only by the adapter
```

Why `core/`: Clipper2 is already a core dependency (`core/SCsub:111-127`) and `Geometry2D` lives there. Scene, editor and modules may all depend on core. Why a sub-directory: the success criterion (§6.1) becomes one `grep` with one allowed path, and the SCsub can give *only this directory* the Clipper2 include path.

**Port style: link-time, not virtual.** Godot builds exactly one polygon backend per binary, chosen by SCons. A static-method port with one adapter `.cpp` selected by the build costs nothing at runtime, matches how `Compression` is built, and still allows a second adapter (or a fake in tests) by compiling a different `.cpp`. Branch by Abstraction happens at build level. A virtual interface would add an indirection on a hot baking path and has no second runtime implementation to justify it. (Decision D1, §5.6.)

### 4.2 Value objects

```cpp
// clip_precision.h — no third-party include.
// Decimal places kept when coordinates are snapped internally (Clipper2 contract: 0..8).
class ClipPrecision {
	uint8_t decimals;
	constexpr explicit ClipPrecision(uint8_t p_decimals) : decimals(p_decimals) {}
public:
	static constexpr uint8_t MAX = 8;
	template <uint8_t D> static constexpr ClipPrecision of() { static_assert(D <= MAX); return ClipPrecision(D); }
	constexpr uint8_t get_decimals() const { return decimals; }

	// Today's values, named. Changing any of them is a behaviour change (separate change).
	static constexpr ClipPrecision GEOMETRY_API();      // 5  — geometry_2d.cpp:42
	static constexpr ClipPrecision MERGE_MANY_LEGACY(); // 2  — geometry_2d.cpp:57 (library default)
	static constexpr ClipPrecision NAV_BAKE_2D();       // 2  — nav_mesh_generator_2d.cpp (library default)
	static constexpr ClipPrecision NAV_PARSE_MESH_2D(); // 2  — mesh_instance_2d.cpp:203, multimesh_instance_2d.cpp:205
	static constexpr ClipPrecision SPRITE_OUTLINE();    // 1  — sprite_2d_editor_plugin.cpp:57
};
```

The clamp that Clipper2 does silently (`clipper.core.h:686-692`) becomes a compile-time error here. There is no default argument anywhere in the ACL: every call names its policy.

```cpp
// polygon_set_2d.h — no third-party include. Engine-native data only.
class PolygonSet2D {
public:
	struct Outline {
		Vector<Vector2> points;
		bool is_hole = false;   // set by the adapter from the library's orientation rule (§5.3 Q3)
	};
	enum class FillRule { EVEN_ODD, NON_ZERO, POSITIVE, NEGATIVE };
	enum class JoinType { SQUARE, ROUND, MITER };          // = Geometry2D::PolyJoinType
	enum class EndType  { POLYGON, JOINED, BUTT, SQUARE, ROUND }; // = Geometry2D::PolyEndType

	// --- mapping from/to the engine's stored shapes (the "persistence" side) ---
	static PolygonSet2D from_outlines(const Vector<Vector<Vector2>> &p_outlines);
	static PolygonSet2D from_outline(const Vector<Vector2> &p_outline);
	static PolygonSet2D from_flat_xy(const Vector<float> &p_xy);            // ProjectedObstruction.vertices
	Vector<Vector<Vector2>> to_outlines() const;                             // what NavigationPolygon / Geometry2D return
	void split_by_hole(Vector<Vector<Vector2>> &r_outer, Vector<Vector<Vector2>> &r_holes) const;
	PolygonSet2D transformed(const Transform2D &p_xform) const;

	// --- domain operations (each delegates to the port; no library type crosses) ---
	PolygonSet2D united(FillRule, ClipPrecision) const;                                   // Union with empty clip
	PolygonSet2D minus(const PolygonSet2D &p_clip, FillRule, ClipPrecision) const;       // Difference
	PolygonSet2D offset(real_t p_delta, JoinType, EndType, double p_miter_limit, double p_arc_tolerance, ClipPrecision) const;
	PolygonSet2D clipped_to(const Rect2 &p_rect, ClipPrecision) const;                   // RectClip
	PolygonSet2D simplified(double p_epsilon) const;
	PolygonSet2D with_positive_winding() const;                                           // replaces "if !IsPositive reverse"
	Vector<Outline> hierarchy(FillRule, ClipPrecision) const;  // depth-first outer→holes→islands (PolyTree flattened)

	bool is_empty() const;
	int size() const;
	const Outline &operator[](int) const;

private:
	Vector<Outline> outlines;
	friend struct Clipper2Codec;   // the only code allowed to build/read the raw form
};
```

`PolygonSet2D` is the single place that knows *what shape the dependency needs*: a set of closed outlines, a fill rule, a precision, and an orientation convention. The *byte layout* of `PathsD` / `PolyTreeD` is in `clipper2_codec.h`, which sits next to it in the ACL directory and is included only by the adapter.

### 4.3 The port

```cpp
// polygon_clipper_2d.h — no third-party include.
// Contract (holds for any backend; see §5.3 for how each point was decided):
//  - Output order of outlines and start vertex of each outline are UNSPECIFIED.
//  - Outer outlines have positive winding, holes negative; Outline::is_hole reflects that.
//  - Coordinates are snapped to ClipPrecision decimals.
//  - Errors never throw; an empty set is returned on failure.
class PolygonClipper2D {
public:
	enum class Op { UNION, DIFFERENCE, INTERSECTION, XOR };

	static PolygonSet2D boolean_closed(Op, const PolygonSet2D &p_subject, const PolygonSet2D &p_clip, PolygonSet2D::FillRule, ClipPrecision, bool p_preserve_collinear);
	static Vector<Vector<Vector2>> boolean_open(Op, const Vector<Vector2> &p_polyline, const PolygonSet2D &p_clip, PolygonSet2D::FillRule, ClipPrecision);
	static PolygonSet2D offset(const PolygonSet2D &, real_t p_delta, PolygonSet2D::JoinType, PolygonSet2D::EndType, double p_miter_limit, double p_arc_tolerance, ClipPrecision);
	static PolygonSet2D rect_clip(const PolygonSet2D &, const Rect2 &, ClipPrecision);
	static PolygonSet2D simplify(const PolygonSet2D &, double p_epsilon);
	static Vector<PolygonSet2D::Outline> hierarchy(const PolygonSet2D &, PolygonSet2D::FillRule, ClipPrecision);
	static bool has_positive_winding(const Vector<Vector2> &);
};
```

Seven operations, and each one has a caller today (K1–K5). Nothing else in Clipper2 (Minkowski, triangulation, `RectClipLines`, `Paths64`, export API) is reachable from engine code.

### 4.4 The adapter (pseudocode)

```cpp
// polygon_clipper_2d_clipper2.cpp — the only #include <…clipper2/clipper.h> in the engine.
#include "clipper2_codec.h"

PolygonSet2D PolygonClipper2D::boolean_closed(Op op, subj, clip, fill, prec, preserve_collinear) {
	Clipper2Lib::ClipperD c(prec.get_decimals());
	c.PreserveCollinear(preserve_collinear);          // geometry_2d.cpp:280 passes false
	c.AddSubject(Clipper2Codec::to_paths(subj));
	c.AddClip(Clipper2Codec::to_paths(clip));
	Clipper2Lib::PathsD out;
	c.Execute(Clipper2Codec::to_clip_type(op), Clipper2Codec::to_fill(fill), out);
	return Clipper2Codec::from_paths(out);            // sets Outline::is_hole = !IsPositive(path)
}

Vector<Vector<Vector2>> PolygonClipper2D::boolean_open(...) {
	// Clipper2 docs: open subjects need ClipperD + PolyTreeD (the PathsD overloads are closed-only).
	// Mirrors geometry_2d.cpp:281-292 exactly.
}

PolygonSet2D PolygonClipper2D::offset(set, delta, jt, et, miter, arc, prec) {
	return Clipper2Codec::from_paths(Clipper2Lib::InflatePaths(Clipper2Codec::to_paths(set), delta,
			Clipper2Codec::to_join(jt), Clipper2Codec::to_end(et), miter, prec.get_decimals(), arc));
}

PolygonSet2D PolygonClipper2D::rect_clip(set, rect, prec) {
	Clipper2Lib::RectD r(rect.position.x, rect.position.y, rect.get_end().x, rect.get_end().y);
	return Clipper2Codec::from_paths(Clipper2Lib::RectClip(r, Clipper2Codec::to_paths(set), prec.get_decimals()));
}

Vector<PolygonSet2D::Outline> PolygonClipper2D::hierarchy(set, fill, prec) {
	Clipper2Lib::ClipperD c(prec.get_decimals()); Clipper2Lib::PolyTreeD tree;
	c.AddSubject(Clipper2Codec::to_paths(set));
	c.Execute(Clipper2Lib::ClipType::Union, Clipper2Codec::to_fill(fill), tree);
	return Clipper2Codec::flatten_depth_first(tree);   // same visit order as nav_mesh_generator_2d.cpp:275-300
}
```

`Clipper2Codec` (private header) holds the 13 hand-written loops from §3.1 as two functions plus four enum maps (the switch tables now at `geometry_2d.cpp:253-268, 315-347`).

### 4.5 Build wiring (part of the ACL)

- `core/SCsub:121-125`: keep the Clipper2 include path and define on `env_thirdparty` and on a cloned `env_polygon_clipping` used only for `core/math/polygon_clipping/`. **Stop** prepending to the global `env` (`:122`) and stop defining `CLIPPER2_ENABLED` globally (`:125`).
- Replace `CLIPPER2_ENABLED` with a **capability** define named for the domain, `POLYGON_CLIPPING_ENABLED`. It is defined when *an* adapter is built, whichever library it uses. K6 and K7 switch to it: same `#ifdef` structure, new name.
- Honour `builtin_clipper2=no`: add the missing `pkg-config Clipper2` branch to `platform/linuxbsd/detect.py`. [?] The upstream pkg-config module name was not verified in this session; check it in the plan. The adapter includes `<clipper2/clipper.h>`, which resolves to either copy. **This is a build-behaviour change (it fixes a broken option), so it is its own phase (P7) and can be dropped without affecting the rest.**

---

## 5. Isolation proof and before/after (Step 5)

### 5.1 What a library swap touches after the refactor

Scenario: replace Clipper2 with another polygon library (or a system Clipper2 3.x with a renamed API, as `973448ec4c` was for 1.3.0).

| Must change | Must NOT change |
|---|---|
| `core/math/polygon_clipping/polygon_clipper_2d_clipper2.cpp` → new adapter `.cpp` | `core/math/geometry_2d.h`, `.cpp` (delegate to `PolygonSet2D`) |
| `core/math/polygon_clipping/clipper2_codec.h` → new codec | `core/core_bind.cpp` (script API), and therefore `doc/classes/Geometry2D.xml` and the GDExtension API dump |
| `core/SCsub` (sources, include path), `SConstruct` option, `platform/*/detect.py` | `scene/2d/mesh_instance_2d.cpp`, `scene/2d/multimesh_instance_2d.cpp` |
| `thirdparty/<lib>/`, `thirdparty/README.md`, `COPYRIGHT.txt` | `editor/scene/2d/sprite_2d_editor_plugin.cpp` |
| (if the new library lacks a capability, e.g. rect clip) a fallback *inside* the adapter | `modules/navigation_2d/**`, `servers/navigation_2d/navigation_server_2d.h` |
| | `NavigationPolygon` resources on disk, `NavigationServer2D` API, tile map, all tests except an optional adapter-specific test |

The behaviour a new adapter must reproduce is fixed by the port contract (§4.3), the named precisions (§4.2), and the guard tests (P0). Nothing has to be reverse-engineered from library defaults any more.

### 5.2 Before / after per location

**K2 + K3: `MeshInstance2D` / `MultiMeshInstance2D` nav parsing (scene)**

```cpp
// BEFORE (mesh_instance_2d.cpp:157-213; multimesh copy :161-225)
using namespace Clipper2Lib;
PathsD subject_paths, dummy_clip_paths;
… PathD subject_path; … subject_path.push_back(PointD(vertex.x, vertex.y)); …
path_solution = Union(subject_paths, dummy_clip_paths, FillRule::NonZero);   // precision 2 by default
for (const PathD &scaled_path : path_solution) { … Point2(static_cast<real_t>(p.x), …) … }

// AFTER
Vector<Vector<Vector2>> surface_paths = …;   // same surface/index loop, collecting Vector2
PolygonSet2D outlines = PolygonSet2D::from_outlines(surface_paths)
		.united(PolygonSet2D::FillRule::NON_ZERO, ClipPrecision::NAV_PARSE_MESH_2D());
for (const Vector<Vector2> &o : outlines.transformed(xform).to_outlines()) {
	p_source_geometry_data->add_obstruction_outline(o);
}
```

The node now receives `Vector<Vector2>` outlines, the type it already stores. It no longer includes anything from `thirdparty/`. The "one path per surface" quirk (`mesh_instance_2d.cpp:170, 186-199`: every triangle vertex of a surface goes into a single path) is kept on purpose and pinned in P0. Extracting the duplicated surface loop into one helper is a separate, optional cleanup (§5.6 D3).

**K4: `Sprite2DEditor::expand` (editor / UI)**

```cpp
// BEFORE (sprite_2d_editor_plugin.cpp:66-103)
Clipper2Lib::PathD subj(points.size()); …
Clipper2Lib::PathsD solution = Clipper2Lib::InflatePaths({ subj }, epsilon, Clipper2Lib::JoinType::Miter,
		Clipper2Lib::EndType::Polygon, 2.0, PRECISION, 0.0);
Clipper2Lib::RectD clamp(…);
Clipper2Lib::PathsD out = Clipper2Lib::RectClip(clamp, solution[0], PRECISION);
const Clipper2Lib::PathD &p2 = out[0]; … manual conversion …

// AFTER
const ClipPrecision prec = ClipPrecision::SPRITE_OUTLINE();
PolygonSet2D grown = PolygonSet2D::from_outline(points).offset(epsilon,
		PolygonSet2D::JoinType::MITER, PolygonSet2D::EndType::POLYGON, 2.0, 0.0, prec);
ERR_FAIL_COND_V(grown.is_empty(), points);
PolygonSet2D clamped = PolygonSet2D::from_outline(grown[0].points).clipped_to(Rect2(rect), prec);
ERR_FAIL_COND_V(clamped.is_empty(), points);
const Vector<Vector2> &p2 = clamped[0].points;   // the 0.5 px de-dup loop (:95-101) stays in the editor
```

The UI receives ready engine-native outlines. The editor-specific step (dropping vertices closer than 0.5 px) stays in the editor, because it is UI policy and not library knowledge.

**K5: `NavMeshGenerator2D::generator_bake_from_source_geometry_data` (module)**

```cpp
// BEFORE (nav_mesh_generator_2d.cpp:317-477): PathsD/PathD/RectD/ClipperD/PolyTreeD/IsPositive throughout
// AFTER (pseudocode; every step keeps today's op, fill rule and precision 2)
const ClipPrecision prec = ClipPrecision::NAV_BAKE_2D();
PolygonSet2D traversable = PolygonSet2D::from_outlines(nav_outlines + traversable_outlines);
PolygonSet2D obstruction = PolygonSet2D::from_outlines(obstruction_outlines)
		+ PolygonSet2D::from_flat_xy_each(non_carving).with_positive_winding();
if (baking_rect.has_area()) { traversable = traversable.clipped_to(int_rect, prec); obstruction = obstruction.clipped_to(int_rect, prec); }
PolygonSet2D solution = traversable.united(NON_ZERO, prec).minus(obstruction.united(NON_ZERO, prec), NON_ZERO, prec);
if (agent_radius > 0) solution = solution.offset(-agent_radius, MITER, POLYGON, /*miter*/ 2.0, /*arc*/ 0.0, prec);
if (has_carving) solution = solution.minus(carving.with_positive_winding(), NON_ZERO, prec);
if (baking_rect.has_area() && border > 0) solution = solution.clipped_to(border_rect, prec);
if (solution.is_empty()) { p_navigation_mesh->clear(); return; }
for (const PolygonSet2D::Outline &o : solution.hierarchy(NON_ZERO, prec)) { /* → TPPLPoly, as :278-293 */ }
```

The integer truncation of the first baking rect (`nav_mesh_generator_2d.cpp:392-395`, `const int`) versus the `double` border rect (`:450-453`) is today's behaviour and is kept: the caller builds the `Rect2` the same way. The `InflatePaths` call at `:413` relies on the library defaults `miter_limit = 2.0` and `arc_tolerance = 0.0` (`clipper.h:145-147`). The ACL makes them explicit arguments.

**K1: `Geometry2D` (core wrapper)**

`_polypaths_do_operation` (`:250-310`) becomes `PolygonClipper2D::boolean_closed` / `boolean_open` with `ClipPrecision::GEOMETRY_API()` and `preserve_collinear = false`. `_polypath_offset` (`:312-372`) becomes `offset(…, 2.0, 0.25, GEOMETRY_API())`. `merge_many_polygons` (`:44-76`) becomes `united(NON_ZERO, MERGE_MANY_LEGACY()).simplified(0.01).split_by_hole(…)`. Public signatures in `geometry_2d.h` are unchanged, and `geometry_2d.cpp` keeps only the polypartition and stb_rect_pack includes (`:38-40`).

**K6 + K7: build flag**

`#ifdef CLIPPER2_ENABLED` becomes `#ifdef POLYGON_CLIPPING_ENABLED` in `servers/navigation_2d/navigation_server_2d.h:44` and the nav module. The server header stops naming a library.

### 5.3 Open questions that depend on the library's contract, resolved

Source: Clipper2 documentation via Context7 (`/websites/angusj_clipper2`) and the vendored 2.0.1 headers.

| # | Question | What the library guarantees | Decision, and where it is encoded |
|---|---|---|---|
| Q1 | What does "precision" mean, and is it safe to leave it implicit? | Decimal places kept when scaled to int64. Default 2, max 8. Out-of-range values are clamped silently (`clipper.core.h:686-692`). | **In `ClipPrecision`** (ACL): no defaults, a named constant per use, `static_assert(≤ 8)`. Today's values are preserved exactly (§3.2). Unifying them is a behaviour change, a separate change (D2). |
| Q2 | Is the order of output polygons and vertices stable? | No. Docs, `ClipperD.Execute`: "In PathsD, polygons appear in no particular order". The 1→2 swap flipped vertex order in `test_geometry_2d.h` (`8a28f816d0`). | **In the port contract** (`polygon_clipper_2d.h` comment): order and start vertex are unspecified. New guard tests compare outline *sets* up to cyclic rotation. The adapter does **not** normalise, because that would change `Geometry2D`'s observable output. |
| Q3 | How are holes identified? | Docs: "Polygon holes always wind in a negative direction in both PathsD and PolyTreeD". `IsPositive` ⇔ `Area ≥ 0` (`clipper.core.h:881-888`), where `Area = ½·Σ (yᵢ₋₁+yᵢ)(xᵢ₋₁−xᵢ)` (`:849-866`). | **In the adapter/codec**: `Outline::is_hole = !IsPositive(path)`. Note for the public contract (`Geometry2D.xml:32`): Godot's `is_polygon_clockwise` computes `Σ (xᵢ₊₁−xᵢ)(yᵢ₊₁+yᵢ) > 0` (`geometry_2d.h:365-379`). That is `−2·Area > 0`, so `is_polygon_clockwise(p) ≡ !IsPositive(p)`, up to `real_t` vs `double` rounding near zero area. Holes therefore report `is_polygon_clockwise == true`, as documented. `has_positive_winding` stays in the adapter (double arithmetic) so the navmesh reorientation (`:371, 434`) is bit-identical. |
| Q4 | Open polylines? | Docs, Difference: "For complex operations involving open paths, the Clipper64 or ClipperD classes should be used". Open results come back only via the `PolyTreeD` overload. | **In the adapter** (`boolean_open`), as `geometry_2d.cpp:281-292` does today. Not visible to callers. |
| Q5 | Errors? | Exceptions are disabled by Godot patch `0001-disable-exceptions.patch` (`thirdparty/README.md:133`). Errors only set `error_code`, and the free functions drop it. | **In the adapter**: keep today's silent behaviour (return what the library returns). Surfacing errors with `ERR_PRINT` would be a behaviour change and goes in the separate change (D2). |
| Q6 | Default `miter_limit` / `arc_tolerance` | `InflatePaths(…, miter_limit = 2.0, precision = 2, arc_tolerance = 0.0)` (`clipper.h:145-147`) | **In the call sites' policy**: they become explicit port arguments with today's values (nav `2.0 / 0.0`; Geometry2D `2.0 / 0.25`; Sprite editor `2.0 / 0.0`). |

### 5.4 Phases

The repo's hard rules apply (`CLAUDE.md`): guard first, every phase reversible on its own, no behaviour change in a refactor phase. Run as change `clipper2-acl` via `/10x-new` → `/10x-plan` → `/10x-implement`, with this document as the research input. **Prerequisite:** the toolchain and baseline from `refactor-opportunities` Phase 1 (`plan.md:121`). The ACL touches no file that C1, C8 or C10 touch, so order is free.

| Phase | Delivers | Test-first? | Behaviour | Revert unit |
|---|---|---|---|---|
| **P0 Guard** | Characterization tests, tag `[PolygonClipping]`: (a) `offset_polygon` / `offset_polyline` for all join/end types; `merge_many_polygons` with holes. (b) `test_navigation_server_2d.cpp`: resolve both `TODO: Use MeshInstance2D` (`:555, 605`) with MeshInstance2D and MultiMeshInstance2D sources, plus bakes with `agent_radius > 0`, a carving obstruction, baking rect, and border size. (c) A test-only entry to `expand()` (it is a free function in the `.cpp`; expose it via a test header, or pin through `Sprite2DEditor` if a `[SceneTree][Editor]` fixture exists — decide in plan). All compare outlines as sets up to rotation (Q2). Golden values are recorded from today's binary. | **Yes**, written first and passing against today's code | none | delete test files |
| P1 ACL skeleton | `core/math/polygon_clipping/*` (VO, precision, port, adapter, codec). Dedicated SCsub env. **No caller switched yet.** Adapter unit tests compare port output against the direct Clipper2 calls used today, for the same inputs. | Yes (adapter equivalence) | none (dead code) | 1 commit |
| P2 Geometry2D on the port | `geometry_2d.cpp` delegates; Clipper2 include removed there | P0(a) + existing `test_geometry_2d.cpp` | none | 1 commit |
| P3 Scene on the port | K2, K3 switched; `thirdparty/clipper2` include removed from `scene/` | P0(b) | none | 1 commit |
| P4 Editor on the port | K4 switched | P0(c) | none | 1 commit |
| P5 Nav module on the port | K5 switched; `PolyPathD` recursion → `hierarchy()` | P0(b) | none | 1 commit |
| P6 Seal the boundary | `core/SCsub:122, 125` stop writing the global `env`; `CLIPPER2_ENABLED` → `POLYGON_CLIPPING_ENABLED` (K6, K7). From here on a new direct include fails to compile outside the ACL. | build + full suite; `--dump-extension-api` identical | none | 1 commit (reverting it alone reopens the door, but breaks nothing) |
| P7 (optional, separate change) Honour `builtin_clipper2=no` | `detect.py` pkg-config branch; adapter includes `<clipper2/clipper.h>` | build with `builtin_clipper2=no` on a distro with Clipper2 | **build-behaviour change** (fixes a broken option) | 1 commit |

Mikado order: P2 → P5 can go in any order after P1. P6 needs all of P2–P5. P7 needs P6.

Verification for every phase: build with `tests=yes`, then run `--test --test-case="*[Geometry2D]*,*[NavigationServer2D]*,*[PolygonClipping]*"` and the full suite. `--dump-extension-api` and the doctool diff must be identical in every phase, because no bound signature changes.

### 5.5 New names

`PolygonSet2D`, `PolygonSet2D::Outline`, `ClipPrecision` (+5 named policies), `PolygonClipper2D`, `Clipper2Codec`, `POLYGON_CLIPPING_ENABLED`, directory `core/math/polygon_clipping/`. Add them to `context/domain/glossary.md` when the plan is accepted.

### 5.6 Decisions for the plan interview (with recommendations)

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Port style: link-time static vs virtual interface | **Link-time** (§4.1). Revisit only if a runtime-selectable backend is ever wanted. |
| D2 | Unify precision (e.g. everything to 5) and surface library errors | **Not in this change.** It changes navmesh output and editor polygons. Open a separate behaviour change after P6, with before/after navmesh diffs. |
| D3 | Extract the duplicated mesh-surface → path loop shared by K2/K3 | Optional P3b inside this change (pure extraction, guarded by P0(b)), or leave it. It is scene duplication, not library knowledge. |
| D4 | Fold polypartition (L2) into the same ACL | **Next change.** Same directory pattern (`core/math/polygon_partition/`). K5 is its main external user, and after P5 the `hierarchy()` output is the natural input. |
| D5 | Keep `ClipPrecision::MERGE_MANY_LEGACY` at 2 although `clipper_precision = 5` is in scope | Keep it (no behaviour change). Flag it in D2's change as a probable oversight [I]. |

### 5.7 Risks

- **Bit-exactness.** The adapter must reproduce today's float→double→float round trips (`static_cast<real_t>` at every back-conversion). Mitigation: P1 equivalence tests on the raw coordinates, not only on the set comparison.
- **Hot path.** Nav baking runs on worker threads. `PolygonSet2D` adds one intermediate `Vector<Outline>` per step. [I] The cost is small next to the int64 scaling Clipper2 already does, but measure it once in P5 with a large `TileMapLayer` bake.
- **Hidden includers.** Third-party code compiled with the global `env` might have relied on the global include path (`core/SCsub:122`). P6 surfaces that as a compile error, which is the intended failure mode.

---

## 6. Verification and plan (Step 6)

### 6.1 Success criterion

```bash
# source files only; build manifests and vendored files are excluded by design
grep -rlE 'clipper2|Clipper2Lib|CLIPPER2_ENABLED' \
     --include='*.cpp' --include='*.h' --include='*.mm' --include='*.inc' \
     core scene servers editor modules drivers platform main tests
```

**Must return only** files under `core/math/polygon_clipping/` (and, if P1 adds them, `tests/core/math/polygon_clipping/` adapter tests).
Allowed outside source (the manifest): `SConstruct`, `core/SCsub`, `platform/*/detect.py`, `thirdparty/**`, `COPYRIGHT.txt`.

Second, structural check (ast-grep, `-l cpp`): patterns `Union($$$)`, `Difference($$$)`, `InflatePaths($$$)`, `RectClip($$$)`, `ClipperD $V($$$);` and `ClipperD $V;` match only inside `core/math/polygon_clipping/`.

### 6.2 Files that know the dependency: today vs after

| File | Today | After P6 |
|---|---|---|
| `core/math/geometry_2d.cpp` | knows (include `:36`, 21 refs) | **no** (uses `PolygonSet2D`) |
| `scene/2d/mesh_instance_2d.cpp` | knows (`:41`, `:157-211`) | **no** |
| `scene/2d/multimesh_instance_2d.cpp` | knows (`:41`, `:161-224`) | **no** |
| `editor/scene/2d/sprite_2d_editor_plugin.cpp` | knows (`:55-101`) | **no** |
| `modules/navigation_2d/2d/nav_mesh_generator_2d.cpp` | knows (`:31, 42, 275-477, 531`) | **no** (keeps polypartition until D4) |
| `modules/navigation_2d/2d/nav_mesh_generator_2d.h` | knows the flag (`:33, 104`) | **no** (`POLYGON_CLIPPING_ENABLED`) |
| `modules/navigation_2d/2d/godot_navigation_server_2d.{h,cpp}` | knows the flag (K7) | **no** |
| `servers/navigation_2d/navigation_server_2d.h` | knows the flag (`:44-46`) | **no** |
| `core/math/polygon_clipping/polygon_clipper_2d_clipper2.cpp` | — | **yes** (the adapter) |
| `core/math/polygon_clipping/clipper2_codec.h` | — | **yes** (private codec) |
| `core/math/polygon_clipping/{polygon_set_2d,clip_precision,polygon_clipper_2d}.h` | — | no (library-free headers) |
| `core/SCsub`, `SConstruct`, `platform/linuxbsd/detect.py` (P7) | manifest | manifest (local env only) |

From 9 knowing locations in 4 code layers (core, scene, editor, module) plus a server header, down to **2 files in one directory**.

### 6.3 Plan

1. `/10x-new clipper2-acl` with the intention "behaviour-neutral ACL for polygon clipping; research input = this document".
2. `/10x-plan`: settle D1–D5 and the P0(c) fixture question. Confirm the pkg-config name for P7 or drop P7.
3. `/10x-plan-review`, then `/10x-implement` in the order P0 → P1 → (P2 | P3 | P4 | P5) → P6 → [P7 as its own change].
4. After P6: open `polypartition-acl` (D4) and the precision-unification behaviour change (D2).

---

## Method and coverage

- **Read for this document:** `01-domain-distillation.md` §0, `02-invariant-aggregate-refactor.md` (structure and §5.2 phase convention), `refactor-opportunities/plan.md` phase headings, `CLAUDE.md`, `thirdparty/README.md:120-134`.
- **Code re-read for every anchor:** `core/math/geometry_2d.cpp:36-76, 245-372`; `geometry_2d.h:33-40, 288-338, 365-379, 502-512`; `scene/2d/mesh_instance_2d.cpp:140-215`; `scene/2d/multimesh_instance_2d.cpp:150-227`; `editor/scene/2d/sprite_2d_editor_plugin.cpp:55-103`; `modules/navigation_2d/2d/nav_mesh_generator_2d.cpp:30-45, 270-500`; `godot_navigation_server_2d.{h,cpp}` (`CLIPPER2_ENABLED` blocks); `servers/navigation_2d/navigation_server_2d.h:40-48`; `core/SCsub:1-12, 105-130`; `SConstruct:334-338`; `platform/linuxbsd/detect.py:275-285, 441-442`; vendored `clipper.h:45-263`, `clipper.engine.h:529`, `clipper.core.h:63-65, 686-692, 849-888`, `clipper.version.h:4`; the include sites for L2–L7.
- **Docs:** `doc/classes/Geometry2D.xml:30-33, 180-195`. Clipper2 docs via Context7 `/websites/angusj_clipper2` (precision semantics, `Execute` ordering and hole winding, `IsPositive`, open paths).
- **History:** `git log` for `thirdparty/clipper2`; `-S ClipperLib` and `-S Clipper2Lib` over the consumers; `git show --stat` of `8a28f816d0`, `0ed2cb0439`, `4765bc883c`, `0ee7e3102b`, `973448ec4c`, and the four later upgrades; `-S PathsD` for the nav generator (`6a4d8d4b5c`).
- **Tools:** grep for includes per `thirdparty/` directory; ast-grep 0.50 for call-site counts (§1.1).
- **Not done:** nothing was built or run. The link failure under `builtin_clipper2=no` (§3.3 item 4) is [I]. The upstream PR threads for `8a28f816d0` and `0ed2cb0439` were not fetched. The pkg-config module name for a system Clipper2 is [?].
