---
title: "Invariant guard: the stencil preset as a BaseMaterial3D aggregate (refactor plan)"
created: 2026-11-02
type: refactor-plan
git_commit: a27e041bc3
builds_on: context/domain/01-domain-distillation.md
status: proposed
---

# Invariant guard: the stencil preset as a BaseMaterial3D aggregate

**Legend.** **[E]** = evidence seen at the cited `file:line` (each one re-read for this document at `a27e041bc3`). **[I]** = inference drawn from evidence. **[?]** = unknown; not a claim that the thing is absent.

**This document is a plan, not an implementation.** No production code was changed. The pseudocode in §4 shows the shape of the design, not a patch.

---

## 0. Context (Step 0)

### 0.1 Requirement sources

| Kind | Found | Used for |
|---|---|---|
| PRD / tech-stack | **None.** `context/foundation/` holds only `README.md`. There is no `prd.md` or `tech-stack.md` anywhere. | — |
| Product statement | `README.md:9-17` ("2D and 3D cross-platform game engine", one-click export) | Vision |
| Behaviour specification | `doc/classes/*.xml`, the class reference. Descriptions are written by hand; skeletons and defaults are CI-generated. | Rules ("business logic") |
| Derived goals | `01-domain-distillation.md` §0.3, goals G1–G5 and non-goals NG1–NG2 | Classification axis (a) |
| Decision history | `git log` of `scene/resources/material.cpp`, plus the earlier research in `context/changes/*` | "Deliberate or accidental?" |

The goals used below (re-checked):

- **G1, look without code:** "a wide variety of rendering features and properties without the need to write shader code" (`doc/classes/BaseMaterial3D.xml:7`).
- **G2, pay only for what you use:** "the cost for using the feature is only incurred when specified" (`BaseMaterial3D.xml:39`).
- **G4, full control when needed:** ShaderMaterial.
- **G5, saved work keeps working:** resources are saved and reloaded.

### 0.2 Stack and the layers where material rules live

C++17 engine built with SCons. **Exceptions are compiled out:** `disable_exceptions` defaults to `True` (`SConstruct:277`), which adds `-fno-exceptions` (`SConstruct:938-942`). A "named domain error" therefore has to be a named error value plus an early return that leaves the state unchanged. It cannot be a `throw`.

The prompt's generic layers map onto Godot as follows:

| Generic layer | Godot equivalent for materials | Location |
|---|---|---|
| API / route | ClassDB-bound setters, reached from GDScript, C# and GDExtension, and the `Object::set` property path, which the loader, the inspector, undo/redo, `duplicate()` and animation tracks all use | `material.cpp:164-176` (Material bindings), `:3595-3611` (stencil bindings), `:3802-3809` (stencil properties) |
| Domain | `Material` → `BaseMaterial3D` → `StandardMaterial3D` / `ORMMaterial3D` | `scene/resources/material.{h,cpp}` |
| UI (client) | Editor inspector; it decides what to show through `_validate_property` | `material.cpp:2595-2709` |
| Persistence (repository) | Reflection-driven `ResourceLoader` / `ResourceSaver`: each stored property is written, then re-applied one at a time through `Object::set` | `scene/resources/resource_format_text.cpp:670`, `:2099-2103` |
| Downstream consumer | RenderingServer material records, addressed by RID | `servers/rendering/renderer_rd/storage_rd/material_storage.cpp`, `drivers/gles3/storage/material_storage.cpp` |

There is no service layer. The resource object *is* the domain object, and the generic reflection machinery is its API and its repository.

---

## 1. Invariant inventory (Step 1)

Rules that must always hold for materials. They come from the documents and from code. Rows I1–I14 rely on `01-domain-distillation.md` §3, and every anchor cited here was re-read. **I1 is new in this document:** 01 recorded only one facet of it (A1.5). Here it is written out in full, because §2 selects it.

| ID | Invariant (must always be true) | Source (doc / code) |
|---|---|---|
| **I1** | **Stencil preset integrity.** While `stencil_mode` is `OUTLINE` or `XRAY`, the material's `next_pass` is a stencil-owned pass that belongs to **this** material only, and all of its preset-managed settings are derived from the owner (render priority = owner + 1, colour, thickness, reference, read/compare). In `DISABLED` or `CUSTOM` mode no stencil-owned pass is attached. The state survives save → reload. | Doc: `BaseMaterial3D.xml:864-870` ("Requires a `next_pass` material which will be automatically applied"). Code: `material.cpp:3185-3244` (`_prepare_stencil_effect`), `:3262-3265` (priority ceiling) |
| I2 | The next-pass chain is acyclic. | `material.cpp:49-51` |
| I3 | `render_priority` ∈ [−128, 127]. | `Material.xml:65-69`; `material.cpp:74-75`; `rendering_server_enums.h:120-121` |
| I4 | There is one compiled shader per distinct MaterialKey, and `users` equals the number of materials on that key. | `material.cpp:669-676`; `particle_process_material.cpp:172-178` |
| I5 | Access to the shader cache is race-free. Materials are created on worker threads. | `material.cpp:2088-2090` (comment) vs. `canvas_item_material.cpp:58-66` (no lock) |
| I6 | A stored ShaderMaterial parameter value survives loading. | `Resource.xml:7`; `material.cpp:200-201, 234` vs. `:422-454` |
| I7 | A shader parameter name matches a uniform. | `ShaderMaterial.xml:28`; `material.cpp:430-434` |
| I8 | Save → load reproduces the material. | `Resource.xml:7`; `resource_format_text.cpp:2099-2103` (default-skip) |
| I9 | What is saved depends only on the material. | `material.cpp:2596-2597` (`emission_intensity` loses `STORAGE` because of a project setting) |
| I10 | Unknown property names are rejected (`_set` returns `false`). | `Object.xml:301`; `material.cpp:4153-4154` |
| I11 | The export shader baker pre-builds exactly the 2D-in-3D variants that nodes request. | `shader_baker_export_plugin.cpp:312, 349, 354` |
| I12 | Triplanar sharpness is clamped; height mapping is ignored under triplanar. | 01 §3 A1.2–A1.3 |
| I13 | `particles_anim` is "always enabled" with `BILLBOARD_PARTICLES`. | 01 §3 A1.4 |
| I14 | CPUParticles offers "the same functionality" as GPU particles. | 01 §3 A7.1 (non-goal NG1) |

---

## 2. Classification and choice (Step 2)

Axes: **(a) core:** 3 = directly delivers G1/G2/G4, 2 = Core but in an experimental or partial feature, 1 = supporting. **(b) spread:** the number of layers from §0.2 (plus docs) in which the rule lives. **(c) enforcement:** **E** = enforced everywhere, **P** = enforced at some entry points, **D** = declared only, **C** = contradicted, **UI** = only the editor guards it.

| ID | (a) core | (b) spread | (c) enforcement | Already covered? | Fits one aggregate? |
|---|---|---|---|---|---|
| **I1** | **2.5:** G1. Outline and X-ray "without shader code". The members are marked `experimental` (`BaseMaterial3D.xml:388-405`). | **6:** domain, base class, UI, persistence, duplication, docs | **C / P / UI.** Enforced only in `set_stencil_mode`. Contradicted by four other entry points. One sub-rule is guarded only by the UI. One error is logged and execution goes on. (§3) | **No.** 01 lists A1.5 as a "behaviour change" with no plan. | **Yes:** a root (owner) and a child it owns (the stencil pass) |
| I2 | 2 | 1 | E | — | Yes, already guarded |
| I3 | 2 | 3 (resource, GLES3, RD) | P (RD does not check) | No | Renderer contract: a decision (01 Q5) |
| I4 | 3 (G2) | 3 copies | E in BaseMaterial3D and PPM | **Yes:** `refactor-opportunities` C1 | It is a cache, not a per-material aggregate |
| I5 | 3 | 1 file | C in CanvasItemMaterial | Out of scope of C1 (bug fix) | Yes, but it is a thread-safety fix |
| I6 | 3 (G4) | 2 | C, only if the saver can write `shader_parameter/*` before `shader` [?] | No | Depends on 01 Q3 |
| I7 | 3 | 1 | D | No | A decision: is it a user warning or a contract? |
| I8 | 3 (G5) | engine-wide | D (convention + CI) | No | **No:** a file-format contract (NG2) |
| I9 | 2 | 2 | C | No | A decision (01 Q7) |
| I10 | 2 | 1 | C | No | A one-line behaviour fix |
| I11 | 1 (export) | 3 | C | **Yes:** C8 (partly) | — |
| I12 | 2 | 1 | E | — | — |
| I13 | 2 | 1 | P (build flag) | No | A decision (01 Q6) |
| I14 | 1 | 2 | C (deliberately) | No | Doc fix only |

### Choice: I1, stencil preset integrity

The selection criterion is to be as close to Core as possible **and** as weakly enforced as possible. The tie-break is that **one aggregate can be made responsible for it**.

1. **Core enough.** Outline and X-ray are the only "no-code" path to a stencil effect. Without the preset, users write two shaders and wire them through `next_pass` by hand. The preset exists to remove exactly that work, which is G1. The `experimental` tag lowers its weight a little. It also makes behaviour fixes acceptable without a deprecation cycle [I].
2. **The weakest enforcement of any Core rule in the inventory.** The rule is written once (`_prepare_stencil_effect`) and checked at one entry point (`set_stencil_mode`). Four other public entry points mutate the same state without knowing the rule (§3.3, V1–V4). The editor is the only guard for one sub-rule (V3). The loader logs a violation and finishes with an inconsistent object (V5). No test anywhere mentions stencil: `grep -rn stencil tests/` returns 0 hits.
3. **The rule has been patched one entry point at a time.** That is the pattern an aggregate root prevents. Three follow-up fixes were each scoped to the function where the symptom appeared:
   - `8ce3011ae6` (2025-06-21, merged in #107807): pass priority `-1` → `get_render_priority() + 1`, in `_prepare_stencil_effect` only.
   - `b0947003e0` (2025-06-21, #107808): the preset pass reads only; `set_stencil_flags` gained normalisation rules.
   - `cd737eed2f` (2025-07-28, #109052, "Fix overflowing render priority for stencil mode outline and xray"): added the ceiling check in `set_stencil_mode`. The same commit touched `Material::set_render_priority` with a whitespace-only change and added no reverse check there.
4. **Why not the stronger-looking alternatives.** I4 (shader cache) is more Core but is mostly enforced and already planned (C1). I8 (persistence) is weaker, but enforcing it is a file-format decision (NG2) that no single aggregate can own. I1 is where I8 is broken concretely *and* fixably (sub-rule S6).

---

## 3. Diagnosis of I1 (Step 3)

### 3.1 The invariant, stated precisely

The **aggregate** is a `BaseMaterial3D` (the *owner*, the root) plus the `StandardMaterial3D` it creates as its stencil-owned pass (the *child*), which is marked by the metadata key `_stencil_owned` (`material.cpp:3199`). A preset mode is `OUTLINE` or `XRAY`.

| Sub-rule | Statement | Today |
|---|---|---|
| **S1 Presence** | A preset mode ⇔ `next_pass` is a stencil-owned pass. `DISABLED` / `CUSTOM` ⇒ no stencil-owned pass at `next_pass`. | Enforced in `set_stencil_mode` (`:3185-3203`). Broken by V2 and V5. |
| **S2 Priority** | `child.render_priority == owner.render_priority + 1`, so `owner.render_priority < RENDER_PRIORITY_MAX` while a preset is active. | Enforced in `set_stencil_mode` (`:3212, 3227, 3262-3265`). Broken by V1. |
| **S3 Preset-owned state** | The owner has `stencil_flags = WRITE` and `stencil_compare = ALWAYS`. The child has mode `CUSTOM`, flags `READ`, compare `NOT_EQUAL`, the same reference, albedo = `stencil_color`, unshaded and alpha transparency. OUTLINE: depth test on, grow on, grow = thickness. XRAY: depth test off, grow off, grow 0. | Written in `:3209-3238`. Broken by V3 (UI-only guard), V6 and V7. |
| **S4 Exclusive ownership** | A stencil-owned pass is the `next_pass` of exactly one owner. | **Not enforced at all.** Broken by V4. |
| **S5 User chain preserved** | A `next_pass` the user set earlier sits behind the child and is restored when the preset is disabled. | **Enforced** (`:3188-3191, 3197-3201`) |
| **S6 Persistence** | Save → reload yields the same S1–S5 state. | Contradicted (V1 makes the reloaded state differ; V5) |

### 3.2 Where the rule lives today (all layers)

| Layer | Location | What it does with the rule |
|---|---|---|
| Domain: owner | `material.cpp:3257-3271` `set_stencil_mode` | The **only** precondition (`:3262-3265`), then the full preset application (`:3268`) |
| Domain: preset table | `material.cpp:3185-3244` `_prepare_stencil_effect` | Writes S1, S2 and S3 in one pass. Called **only** from `:3268`. |
| Domain: propagation | `material.cpp:3318-3330` (reference), `:3336-3347` (colour), `:3353-3364` (thickness) | Each setter copies **one** field to the child if the child exists (`_get_stencil_next_pass()`, `:3246-3255`). Priority is not among them. |
| Domain: owner stencil state | `material.cpp:3277-3299` `set_stencil_flags`, `:3305-3312` `set_stencil_compare` | Accept any value in every mode |
| Base class | `material.cpp:48-67` `set_next_pass` (checks cycles only, `:49-51`); `:73-82` `set_render_priority` (checks range only, `:74-75`) | Unaware of stencil. Both are **non-virtual** (`material.h:79, 82`) and bound directly (`material.cpp:164, 167`), so no subclass can intercept them. |
| UI (editor) | `material.cpp:2689-2709` | Inside `is_editor_hint()` only, it hides `stencil_flags` / `stencil_compare` unless the mode is `CUSTOM` (`:2698-2700`), using `PROPERTY_USAGE_NO_EDITOR`, so the values are still stored. The `render_priority` hint allows the full range up to 127 (`:175`). `next_pass` stays visible and editable (`Material::_validate_property`, `:92-98`, hides it only when `!_can_do_next_pass()`, and BaseMaterial3D returns `true`, `material.h:642`). |
| Persistence: marker | `object.cpp:607-619` | Metadata is listed as `metadata/<key>` with default usage (`property_info.h:134, 150`: `PROPERTY_USAGE_DEFAULT`). So `_stencil_owned` is **saved** with the child. |
| Persistence: load order | `object.h:319-323` (parent class first); `material.cpp:175-176` (`render_priority`, `next_pass` in Material), `:3803-3809` (stencil props in BaseMaterial3D); `resource_format_text.cpp:670` (`res->set(assign, value)` per property) | The aggregate is rebuilt by about 8 separate setter calls in a fixed order: priority → next_pass → … → stencil_mode → stencil_flags → … No step sees the whole aggregate. |
| Duplication | `resource.cpp:408-424` (copy stored props via `set`), `:289-305` (share sub-resources unless `ALWAYS_DUPLICATE`, deep+built-in, or local-to-scene) | `next_pass` has no `ALWAYS_DUPLICATE` flag (`material.cpp:176`) |
| Shader generation | `material.h:379-382, 445-448` (stencil fields in MaterialKey); `material.cpp:895` (stencil code emitted only if mode ≠ DISABLED and flags ≠ 0) | A consumer of S3. It does not check anything. |
| Renderer | RD `material_storage.cpp:2619-2627` (no range check); GLES3 `material_storage.cpp:2578-2580` (range check) | Receives the child's priority as given |
| Docs | `BaseMaterial3D.xml:866, 870` | "automatically applied … Any manual changes made to `next_pass` will be lost when the stencil properties are modified or the scene is reloaded … use `material_overlay` instead" |
| Tests | — | `grep -rn stencil tests/` → 0 |

### 3.3 Violations

**V1: the priority bypass (S2). The second entry point does not enforce the rule.**
`Material::set_render_priority` (`material.cpp:73-82`) only range-checks and stores. With a preset active:
- `mat.render_priority = 10` leaves the child at the old owner+1. Nothing reports it.
- `mat.render_priority = 127` is accepted (`:75` allows it). `set_stencil_mode` refuses exactly this state (`:3263-3264`), so the same state is rejected through one entry point and accepted through the other.

The consequence is [I]: the `+1` only affects ordering when both passes sort in the same list. Transparent objects are always drawn after opaque ones (`Material.xml:61`) and the child is alpha-transparent (`:3214`), so the stale priority matters when the owner itself is transparent. That is the situation #107806/#107807 fixed in `_prepare_stencil_effect` only.

**V2: the next-pass bypass (S1). Not enforced, and the error is silent.**
`Material::set_next_pass` (`:48-67`) accepts any acyclic material. Replacing or clearing the child, from the inspector (`next_pass` is visible) or from a script, leaves `stencil_mode == OUTLINE` with no stencil-owned pass. Afterwards:
- `set_stencil_effect_color`, `set_stencil_effect_outline_thickness` and `set_stencil_reference` update the owner field and silently skip the child (`:3344, 3361, 3327` `if (stencil_next_pass.is_valid())`). The user sees the change accepted and nothing rendered.
- Selecting `OUTLINE` again is a no-op because of `:3258-3259` (same mode). The only way back is DISABLED → OUTLINE.

**V3: the preset-owned owner state (S3). The UI is the only guard.**
In `OUTLINE`/`XRAY` the preset sets the owner to `WRITE` / `ALWAYS` (`:3210-3211, 3225-3226`). `set_stencil_flags` and `set_stencil_compare` (`:3277-3312`) accept any value in any mode. The only thing that stops a user is that the inspector **hides** the two properties when the mode is not `CUSTOM`, and only in the editor (`:2689, 2698-2700`). A script, GDExtension, an AnimationPlayer track or a loaded file sets them freely. Example: `mat.stencil_flags = READ` under `OUTLINE` makes the owner read the stencil instead of writing it, so the outline has no mask to compare against [I]. On reload, `stencil_mode` is applied first (`:3803`) and re-sets `WRITE`. Then `stencil_flags = READ` from the file is applied (`:3804`), and the normalisation at `:3283-3285` keeps `READ`. **The broken state is saved and restored.**

**V4: the owned child is shared after `duplicate()` (S4). Not enforced.**
`Resource::_duplicate` copies every stored property through `set` (`resource.cpp:408-424`). A sub-resource is shared unless the property is `ALWAYS_DUPLICATE`, the copy is deep and the sub-resource is built-in, or it is a local-to-scene copy of a local-to-scene resource (`:289-305`). `next_pass` is none of these (`material.cpp:176`), and the child is not local-to-scene. On the copy, `set_stencil_mode(OUTLINE)` finds a `next_pass` that carries `_stencil_owned` and **adopts it** (`:3197, 3203-3204`). Two owners now drive one child. `copy.stencil_color = RED` recolours the original's outline [I, to be pinned by test T-X6]. Per-instance highlighting through `material.duplicate()` is a common game pattern [I], so this is the user-visible face of the bug.

**V5: the load path logs and carries on (S1, S6). The error is swallowed.**
A file that V1 can produce has `render_priority = 127`, `next_pass = <child with _stencil_owned>` and `stencil_mode = 1`. Loading applies the properties in order (`resource_format_text.cpp:670`):
1. Priority 127 is accepted.
2. The child is attached as `next_pass`.
3. `set_stencil_mode(OUTLINE)` hits `ERR_FAIL_COND_EDMSG` (`:3263-3264`). That macro prints and returns (`core/error/error_macros.h:453-458`). **The load continues.**

The result is `stencil_mode == DISABLED` with a stencil-owned child still attached, which violates S1. `_get_stencil_next_pass()` checks only the marker, not the mode (`:3246-3255`), so later colour, thickness and reference edits keep driving an orphaned pass. The orphan pass still renders with `READ / NOT_EQUAL` while the owner no longer writes the stencil (`:895` emits no stencil code when the mode is DISABLED) [I: visual result not verified]. Nothing ever cleans it up: `DISABLED` is the default, so it is not saved and `set_stencil_mode` is not called during load.

**V6: direct edits to the child (S3). Declared, not enforced.**
`get_next_pass()` returns a mutable reference to the child (`:69-71`). Any edit to a preset-managed field stays in effect until the next stencil-mode change or reload. The docs declare this outcome ("manual changes … will be lost", `BaseMaterial3D.xml:866`). This is the one place where the current contract is *eventual* by design. §4.7 keeps it and makes it truthful.

**V7: the preset rule is written twice and the copies disagree (S3, S6). Enforcement is inconsistent.**
The preset values live in the table at `:3209-3238`, and three setters propagate a subset of them again (`:3326-3329, 3343-3346, 3360-3363`). Thickness propagates in `XRAY` too, although the XRAY preset sets grow to 0 (`:3224-3238`). Before reload, `child.grow == thickness`; after reload, it is `0`. Each new preset field needs two edits, which is the drift that #107807 and #109052 each fixed in one place only.

### 3.4 Summary of the failure modes the prompt asks for

| Asked for | Where in I1 |
|---|---|
| Layers that don't enforce | Base class `set_render_priority` / `set_next_pass` (V1, V2); duplication (V4); renderer (passive) |
| Inconsistent enforcement | Priority ceiling enforced in `set_stencil_mode`, not in `set_render_priority` (V1); preset written in the table and in 3 setters (V7) |
| UI is the only guard | Preset-owned `stencil_flags` / `stencil_compare` (V3) |
| Error swallowed instead of stopping | Load-time `ERR_FAIL_COND_EDMSG` leaves an orphan (V5); propagation silently skipped after the child is replaced (V2) |

---

## 4. Aggregate design (Step 4)

### 4.1 Boundary

```
          ┌──────────────── Aggregate: StencilPreset of one BaseMaterial3D ────────────────┐
          │                                                                                 │
 API ───► │  ROOT  BaseMaterial3D (owner)                                                   │
 (bound   │    stencil_mode, stencil_color, stencil_outline_thickness, stencil_reference,   │
 setters, │    render_priority*, next_pass*, stencil_flags†, stencil_compare†                │
 Object:: │        │ owns exclusively (S4)                                                  │
 set)     │        ▼                                                                        │
          │  CHILD  StandardMaterial3D, meta "_stencil_owned"                                │
          │    every preset-managed field = StencilPassSpec(owner)   (S2, S3)                │
          │        │ user chain (S5, outside the boundary)                                  │
          └────────┼────────────────────────────────────────────────────────────────────────┘
                   ▼
            user's next_pass (any Material)

 * inherited from Material, intercepted through hooks (4.4)
 † preset-owned while the mode is OUTLINE/XRAY, user-owned in CUSTOM
```

**The root stays `BaseMaterial3D`.** There is no new public class and no new saved class name, so files keep loading (G5). The child keeps its class and its marker for the same reason. What changes is that **every mutation of aggregate state goes through one root-owned check-then-apply path.**

### 4.2 Value object and named errors

```cpp
// scene/resources/material.h — BaseMaterial3D, private section (C++ only, not bound)

static inline const StringName META_STENCIL_OWNED = "_stencil_owned"; // persisted string: never change

// The preset rule, written once. Pure: no RS calls, no side effects.
struct StencilPassSpec {
	int render_priority;      // owner + 1
	bool disable_depth_test;  // XRAY
	bool grow_enabled;        // OUTLINE
	float grow;               // OUTLINE ? thickness : 0
	Color albedo;
	int reference;
	// constants, kept here so one table is the source: UNSHADED, ALPHA, CUSTOM, READ, NOT_EQUAL
};
static bool _is_stencil_preset(StencilMode p_mode);  // OUTLINE || XRAY
StencilPassSpec _stencil_pass_spec(int p_owner_priority) const;

// Named domain errors. No exceptions in this build (SConstruct:277, :942).
enum class StencilViolation : uint8_t {
	NONE,
	PRIORITY_CEILING,           // a preset needs owner render_priority < RENDER_PRIORITY_MAX
	OWNED_PASS_REPLACED,        // next_pass would detach the stencil-owned pass
	PRESET_OWNS_STENCIL_STATE,  // stencil_flags/compare are preset-managed outside CUSTOM
	INCONSISTENT_ON_LOAD,       // a loaded file holds a state S1–S4 forbid
};
static String _stencil_violation_message(StencilViolation p_v, const BaseMaterial3D *p_self);
// Message format: "[StencilViolation::PRIORITY_CEILING] <resource path or class>: <explanation>"
```

### 4.3 Root domain methods (public signatures unchanged)

The public setters keep their `void` signatures and bindings, so the GDExtension API and the docs skeleton stay the same. Each one becomes **check → apply → sync**, and every check runs before the first mutation.

```cpp
void BaseMaterial3D::set_stencil_mode(StencilMode p_mode) {
	if (stencil_mode == p_mode) return;
	const StencilViolation v = _check_stencil_mode(p_mode, get_render_priority());
	if (v != StencilViolation::NONE) {
		if (ResourceLoader::is_within_load()) { _reject_stencil_on_load(v); return; }  // 4.5
		ERR_FAIL_MSG(_stencil_violation_message(v, this));                             // state unchanged
	}
	stencil_mode = p_mode;
	_apply_stencil_preset();          // the only writer of S1/S3; replaces _prepare_stencil_effect
	_queue_shader_change();
	notify_property_list_changed();
}

// pre:  none (callers checked)
// post: S1, S2, S3 hold, or the mode is not a preset and no owned pass is attached (S5 respected)
void BaseMaterial3D::_apply_stencil_preset() {
	PresetWriteScope scope(this);     // sets applying_stencil_preset = true; internal writes pass the guards
	if (!_is_stencil_preset(stencil_mode)) { _detach_owned_pass(); return; }      // S1, S5
	Ref<BaseMaterial3D> pass = _adopt_or_create_owned_pass();                      // S1, S4, S5
	_write_owner_stencil_state(STENCIL_FLAG_WRITE, STENCIL_COMPARE_ALWAYS);       // S3 owner
	_write_pass(pass, _stencil_pass_spec(get_render_priority()));                 // S2, S3 child
}

void BaseMaterial3D::set_stencil_flags(int p_flags) {           // same shape for set_stencil_compare
	if (stencil_flags == p_flags) return;
	if (_is_stencil_preset(stencil_mode) && !applying_stencil_preset) {
		ERR_FAIL_MSG(_stencil_violation_message(StencilViolation::PRESET_OWNS_STENCIL_STATE, this));
	}
	/* existing normalisation (material.cpp:3281-3295) unchanged */
	stencil_flags = p_flags;
	_queue_shader_change();
}

void BaseMaterial3D::set_stencil_effect_color(const Color &p_color) {   // also thickness, reference
	if (stencil_effect_color == p_color) return;
	stencil_effect_color = p_color;
	_sync_owned_pass();               // re-applies the full spec; no per-field copy (fixes V7)
}

void BaseMaterial3D::_sync_owned_pass() {
	if (!_is_stencil_preset(stencil_mode)) return;          // an orphan is never driven (V5)
	Ref<BaseMaterial3D> pass = _get_stencil_next_pass();
	ERR_FAIL_COND_MSG(pass.is_null(), "S1 broken: preset active without owned pass");  // unreachable after B3
	PresetWriteScope scope(this);
	_write_pass(pass, _stencil_pass_spec(get_render_priority()));
}
```

### 4.4 Hooks in the base class, so the root sees inherited entry points

`Material::set_render_priority` and `set_next_pass` stay non-virtual and keep their bindings. They gain protected C++ hooks with no-op defaults (Template Method). The hooks are **not** `GDVIRTUAL`s, so the extension API does not change.

```cpp
// Material (material.h) — protected
virtual bool _can_set_render_priority(int p_priority, String &r_reason) const { return true; }
virtual void _render_priority_changed() {}
virtual bool _can_set_next_pass(const Ref<Material> &p_pass, String &r_reason) const { return true; }

void Material::set_render_priority(int p_priority) {
	ERR_FAIL_COND(p_priority < RENDER_PRIORITY_MIN);
	ERR_FAIL_COND(p_priority > RENDER_PRIORITY_MAX);
	String reason;
	ERR_FAIL_COND_MSG(!_can_set_render_priority(p_priority, reason), reason);   // fail-fast, state unchanged
	render_priority = p_priority;
	if (material.is_valid()) RS::get_singleton()->material_set_render_priority(material, p_priority);
	_render_priority_changed();
}
// set_next_pass: cycle check (:49-51) → _can_set_next_pass → assign → RS (unchanged order otherwise)

// BaseMaterial3D overrides
bool BaseMaterial3D::_can_set_render_priority(int p, String &r) const {
	if (_is_stencil_preset(stencil_mode) && p >= RENDER_PRIORITY_MAX) {
		r = _stencil_violation_message(StencilViolation::PRIORITY_CEILING, this); return false;   // V1
	}
	return true;
}
void BaseMaterial3D::_render_priority_changed() { _sync_owned_pass(); }                         // V1: S2 follows
bool BaseMaterial3D::_can_set_next_pass(const Ref<Material> &p, String &r) const {
	if (applying_stencil_preset || !_is_stencil_preset(stencil_mode)) return true;
	if (p != _get_stencil_next_pass()) {
		r = _stencil_violation_message(StencilViolation::OWNED_PASS_REPLACED, this); return false;  // V2
	}
	return true;
}
```

There is a legal alternative to V2. To add a pass behind the preset, set `next_pass` on the child (that chain is S5 and outside the boundary), or use `GeometryInstance3D.material_overlay` as the docs already advise (`BaseMaterial3D.xml:866`).

### 4.5 Repository and atomicity: the load as one transaction

Godot has no per-type repository. `ResourceLoader` / `ResourceSaver` reflect over stored properties (`resource_format_text.cpp:670, 2099-2103`). Adding a type-specific repository would fork the file-format path and put G5 at risk. So **the aggregate makes its own load atomic** instead:

- **Commit point.** Load order puts `render_priority` and `next_pass` before `stencil_mode` (verified in §3.2). So `set_stencil_mode` is the first moment at which the whole aggregate is visible. It is the commit.
- **All or nothing.** If the commit check fails while `ResourceLoader::is_within_load()`, `_reject_stencil_on_load(v)` rolls back to a consistent state: the mode stays `DISABLED`, the owned pass is detached and the user chain is restored (S5). It prints `INCONSISTENT_ON_LOAD` with the resource path. The material is never half-applied. Failing the whole load was rejected because it would break G5 for files that today's engine can write (decision D3).
- **Orphans.** When a stencil-owned pass arrives through `set_next_pass` during load, the root schedules `_reconcile_stencil_after_load()` with `call_deferred`. That is the same load-safe mechanism `Material::_mark_initialized` already uses (`material.cpp:108-114`). The reconcile detaches an owned pass whose owner ended the load in a non-preset mode (V5).
- **Preset-owned fields in the file.** `stencil_flags` and `stencil_compare` are stored after `stencil_mode` (`:3803-3805`). Under a preset, a stored value equal to the preset value is a no-op. A different value is rejected through `PRESET_OWNS_STENCIL_STATE`, the preset value is kept and the file is repaired on the next save (V3).
- **Runtime atomicity.** Every root method runs all its checks before its first write, and the writes of one call (`_apply_stencil_preset`, `_sync_owned_pass`) complete before it returns. No intermediate S1–S3 state is observable from another call on the same thread. The design adds no lock: concurrent mutation of a single material from several threads is outside this invariant, and today's material setters are not designed for it either [I].

### 4.6 Exclusive ownership on duplication (S4)

`BaseMaterial3D::_validate_property` adds `PROPERTY_USAGE_ALWAYS_DUPLICATE` to `next_pass` while it holds a stencil-owned pass. `Resource::_duplicate_recursive` honours that flag first (`resource.cpp:289-290`), for shallow, deep and local-to-scene copies alike. Every copy then gets its own child.

**Fallback,** if the duplication property list turns out not to pass through `_validate_property` [?, pinned by T-X6]: give the child a non-persistent `ObjectID stencil_owner`. In `_adopt_or_create_owned_pass`, a pass whose live owner is not `this` gets cloned instead of adopted.

### 4.7 What stays eventual on purpose (V6)

The child remains a reachable, mutable `Material`, and Godot offers no read-only reference. Edits to its preset-managed fields are **overwritten at the next root operation**, which now includes priority, colour, thickness, reference, mode and load, not only mode and reload. This matches the documented contract ("will be lost"). Rejecting child edits outright would need the `stencil_owner` back-reference in a dozen child setters. That is decision D4 and is not part of this plan.

### 4.8 Thin API: input → root method → error mapping

| Entry (route) | Parse | Root method | Violation → response |
|---|---|---|---|
| GDScript / C# / GDExtension `mat.render_priority = p` | ClassDB variant → `int` (unchanged) | `Material::set_render_priority` → hooks | `PRIORITY_CEILING` → `ERR_FAIL_COND_MSG` prints the named message with the script stack; the debugger breaks on the error in debug builds [I]; the value is unchanged |
| `mat.next_pass = m` | → `Ref<Material>` | `set_next_pass` → `_can_set_next_pass` | `OWNED_PASS_REPLACED` → same mapping |
| `mat.stencil_flags = f` / `stencil_compare` | → `int` | setter guard | `PRESET_OWNS_STENCIL_STATE` |
| `mat.stencil_mode = OUTLINE` | → enum | `set_stencil_mode` | `PRIORITY_CEILING` (existing rule, now named) |
| Inspector edit (EditorUndoRedo → `Object::set`) | same as above | same | Same message in the editor Output panel; the property shows the unchanged value. The UI hiding (`:2689-2709`) **stays, as UX only**; enforcement no longer depends on it. |
| Loader (`resource_format_text.cpp:670`, binary equivalent) | stored Variant | same setters, commit at `set_stencil_mode` | Within a load: atomic rollback plus `INCONSISTENT_ON_LOAD`, and the load completes (4.5) |
| `duplicate()` (`resource.cpp:423`) | stored Variant | same setters | No violation, because the copy receives its own child (4.6) |

---

## 5. Before / after, phases, tests, names (Step 5)

### 5.1 Before / after per location

| Location today | Before | After |
|---|---|---|
| `material.cpp:3185-3244` `_prepare_stencil_effect` | Preset table plus attach/detach mixed together, two copies of the switch arms | `_apply_stencil_preset()` → `_detach_owned_pass` / `_adopt_or_create_owned_pass` / `_write_pass(spec)`; the table lives once in `_stencil_pass_spec` |
| `material.cpp:3257-3271` `set_stencil_mode` | Only entry point with a precondition; `ERR_FAIL_COND_EDMSG` also used during load | `_check_stencil_mode` → named `PRIORITY_CEILING`; load path → atomic rollback |
| `material.cpp:3318-3364` reference / colour / thickness | Per-field copy, skipped silently when the child is gone; thickness copied in XRAY | Assign, then `_sync_owned_pass()` (full spec; never drives an orphan) |
| `material.cpp:3277-3312` flags / compare | Accept anything in any mode | Rejected under a preset unless the write is internal (`applying_stencil_preset`) |
| `material.cpp:73-82` `Material::set_render_priority` | Range check only | Range check → `_can_set_render_priority` → assign → `_render_priority_changed` |
| `material.cpp:48-67` `Material::set_next_pass` | Cycle check only | Cycle check → `_can_set_next_pass` → assign |
| `material.cpp:2689-2709` editor `_validate_property` | Sole guard for flags/compare | Unchanged (UX); plus `ALWAYS_DUPLICATE` on `next_pass` when owned (outside the editor-hint block) |
| `material.cpp:176` `next_pass` property | Shared on `duplicate()` | Duplicated when it holds an owned pass |
| Load (`resource_format_text.cpp:670` order) | 8 independent setter calls; failure is logged and execution goes on | Commit at `set_stencil_mode`; rollback or deferred reconcile; never half-applied |
| `BaseMaterial3D.xml:866, 870` | "manual changes … will be lost when the stencil properties are modified or the scene is reloaded" | States the rules: priority follows (+1, max 126); `next_pass` is locked while a preset is active (use the child's `next_pass` or `material_overlay`); flags/compare are preset-managed |
| `tests/` | 0 stencil tests | `tests/scene/test_base_material_3d_stencil.cpp` |

### 5.2 Phases

The repo's hard rules apply: guard first, every phase reversible on its own, and a refactor phase does not change behaviour. So the work is **two changes**:

- **Change A, `stencil-aggregate-structure`:** behaviour-neutral refactor.
- **Change B, `stencil-aggregate-enforcement`:** behaviour change; every phase test-first (red → green).

Both run through `/10x-new` → `/10x-plan` → `/10x-implement` (or `/10x-tdd` for B), with this document as the research input.

**Prerequisite:** the toolchain and baseline from `refactor-opportunities` Phase 1. This machine has no compiler (`plan-brief.md`, "Tooling"). Change A touches `material.cpp` in regions disjoint from C1's cache code (`:669-695, 2088-2113, 4039-4056`), so the order between the two is free. Rebasing after C1 Phase 4 is the cheaper option.

| Phase | Change | Test-first? | Delivers | Revert unit |
|---|---|---|---|---|
| **A0 Guard** | A | **Yes (characterization):** the tests are written first and pass against today's code | `test_base_material_3d_stencil.cpp`, tag `[SceneTree][Material][Stencil]`. `[SceneTree]` brings up the RenderingServer (`tests/test_main.cpp:182-203`), which `~BaseMaterial3D` requires (`material.cpp:4039-4040`, `ERR_FAIL_NULL(RS::get_singleton())`). Pins T-L1…T-L7 plus today's behaviour for V1–V5 as "current behaviour" cases (CHECK on today's values, named `[current] …`). | Delete the file |
| A1 Name the marker | A | — (A0 covers it) | `META_STENCIL_OWNED`, `_is_stencil_preset()`; same string, so the file format is unchanged | 1 commit |
| A2 One preset table | A | **Yes:** a spec test asserts `_stencil_pass_spec` values equal today's table before `_prepare_stencil_effect` is switched to it | `StencilPassSpec`, `_stencil_pass_spec`, `_write_pass`; `_prepare_stencil_effect` → `_apply_stencil_preset`; the three propagating setters **keep** their per-field copies (V7 behaviour stays) | 1 commit |
| A3 Hooks | A | — | Material hooks with no-op defaults, `PresetWriteScope`; no override yet. Check: `--dump-extension-api` is identical, and the doctool diff is empty. | 1 commit |
| A4 Named errors | A | — | `StencilViolation` + message builder; the `:3262-3265` check routed through `_check_stencil_mode` with **identical message text** | 1 commit |
| **B1 Priority follows** (V1) | B | **Yes:** flip `[current] priority stale` → T-L8, T-L9, T-X2 red, then green | `_can_set_render_priority`, `_render_priority_changed` overrides | 1 commit |
| **B2 Preset owns stencil state** (V3) | B | **Yes:** T-X3, T-L10 | Guards in `set_stencil_flags` / `set_stencil_compare` | 1 commit |
| **B3 Owned pass locked** (V2) | B | **Yes:** T-X4, T-X5 | `_can_set_next_pass` override; `_sync_owned_pass` replaces the per-field copies (fixes V7 → T-L11) | 1 commit (depends on A3) |
| **B4 Exclusive ownership** (V4) | B | **Yes:** T-X6 | `ALWAYS_DUPLICATE` in `_validate_property`; fallback `stencil_owner` if T-X6 stays red | 1 commit |
| **B5 Atomic load** (V5) | B | **Yes:** T-X7, T-X8, T-L12 using `.tres` fixtures written to `TestUtils::get_temp_path` (pattern: `tests/core/io/test_resource.cpp:530-560`) | `_reject_stencil_on_load`, `_reconcile_stencil_after_load` | 1 commit (depends on B1) |
| B6 Docs | B | — | `BaseMaterial3D.xml:866, 870`, `Material.xml` `render_priority` note; doctool CI green | 1 commit |

Verification for every phase: build with `tests=yes`, then run `bin/godot.<platform>.editor.dev.<arch> --test --test-case="*[Stencil]*"` and the full suite. Change A also requires an identical `--dump-extension-api` and an empty doctool diff. Change B requires an identical extension API (no bound signature changes) and a doctool diff limited to the B6 descriptions.

### 5.3 Test cases for the invariant

"Today" is the expected result on `a27e041bc3`. A0 pins this column. B flips the rows marked ✗.

**Legal operations**

| ID | Setup → action | Expected after the change | Today |
|---|---|---|---|
| T-L1 | Fresh StandardMaterial3D, priority 0 → `stencil_mode = OUTLINE` | `next_pass` has `_stencil_owned`; child priority 1; owner flags `WRITE`, compare `ALWAYS`; child mode `CUSTOM`, flags `READ`, compare `NOT_EQUAL`, grow on, grow = thickness, albedo = `stencil_color`, depth test on | ✓ |
| T-L2 | → `XRAY` | Child depth test off, grow off, grow 0 | ✓ |
| T-L3 | OUTLINE → XRAY | The same child object is reused (identity) | ✓ |
| T-L4 | User pass U set first → OUTLINE → DISABLED | While OUTLINE: `child.next_pass == U`; after DISABLED: `next_pass == U` (S5) | ✓ |
| T-L5 | OUTLINE → set colour, thickness, reference | Child albedo, grow and reference follow | ✓ |
| T-L6 | Priority 126 → OUTLINE | Accepted; child priority 127 | ✓ |
| T-L7 | `CUSTOM` → `stencil_flags = READ` | Accepted (user-owned) | ✓ |
| T-L8 | OUTLINE at 0 → `render_priority = 5` | Child priority 6 | ✗ (stays 1) |
| T-L9 | OUTLINE → `render_priority = -128` | Child priority −127 | ✗ |
| T-L10 | OUTLINE → `stencil_flags = WRITE` (equal to the preset) | No-op, no error | ✓ (no-op by `:3278`) |
| T-L11 | XRAY → `stencil_outline_thickness = 0.5` | Child grow stays 0 | ✗ (becomes 0.5) |
| T-L12 | OUTLINE material saved to `.tres` and `.res` → reload | Mode, priority+1, colour, chain and marker are identical; one child per material | ✓ for a clean file |

**Illegal operations: rejected, error printed, state unchanged**

| ID | Setup → action | Expected after the change | Today |
|---|---|---|---|
| T-X1 | Priority 127 → `stencil_mode = OUTLINE` | `PRIORITY_CEILING`; mode DISABLED; `next_pass` unchanged | ✓ (unnamed message) |
| T-X2 | OUTLINE at 0 → `render_priority = 127` | `PRIORITY_CEILING`; priority stays 0; child stays 1 | ✗ (accepted) |
| T-X3 | OUTLINE → `stencil_flags = READ` / `stencil_compare = LESS` | `PRESET_OWNS_STENCIL_STATE`; owner stays `WRITE` / `ALWAYS` | ✗ (accepted) |
| T-X4 | OUTLINE → `next_pass = other` | `OWNED_PASS_REPLACED`; `next_pass` is still the child | ✗ (replaced; later colour edits silently dropped) |
| T-X5 | OUTLINE → `next_pass = null` | `OWNED_PASS_REPLACED` | ✗ |
| T-X6 | OUTLINE → `copy = duplicate()` (shallow, and also `duplicate_deep`) → `copy.stencil_color = RED` | `copy.next_pass != original.next_pass`; the original's child albedo is unchanged | ✗ for shallow (shared) [I]; deep: ✓ [I] (`resource.cpp:301-302`) |
| T-X7 | Load a `.tres` with `render_priority = 127`, `stencil_mode = 1` and an owned child | Load succeeds; mode DISABLED; no owned pass attached; user chain restored; `INCONSISTENT_ON_LOAD` printed once | ✗ (orphan child stays) |
| T-X8 | Load a `.tres` with mode DISABLED (omitted) and an owned child at `next_pass` | After the deferred reconcile: owned pass detached | ✗ |
| T-X9 | Load a `.tres` with OUTLINE and stored `stencil_flags = 1` (READ) | Owner flags `WRITE`; `PRESET_OWNS_STENCIL_STATE` printed | ✗ (READ restored) |
| T-X10 | `next_pass` cycle through the child (`child.next_pass = owner`) | Rejected by the existing cycle check (`:49-51`) | ✓ (regression guard) |

### 5.4 New load-bearing names

The project has no formal contract registry. The equivalents are `context/domain/glossary.md` (naming) plus, for anything public, `doc/classes/*.xml` and `misc/extension_api_validation/`. This plan adds **no** bound or public API.

| Name | Kind | Why it is load-bearing | Register in |
|---|---|---|---|
| `"_stencil_owned"` (`META_STENCIL_OWNED`) | Persisted metadata key (already exists) | Written into users' `.tres`/`.scn` files; renaming it breaks every saved preset | glossary ("Stencil-owned pass": add "persisted key, never rename") |
| `StencilViolation::{PRIORITY_CEILING, OWNED_PASS_REPLACED, PRESET_OWNS_STENCIL_STATE, INCONSISTENT_ON_LOAD}` | Named domain errors; the tag appears in error text | Tests and users search for these strings | glossary (new term "Stencil violation") |
| `StencilPassSpec`, `_stencil_pass_spec()` | The single source of the preset rule | A new preset field must be added here, and only here | glossary ("Stencil pass spec") |
| `_apply_stencil_preset()`, `_sync_owned_pass()` | The root's only writers of the child | Any new stencil setter must call `_sync_owned_pass()` | glossary note under "Stencil-owned pass" |
| `Material::_can_set_render_priority`, `_render_priority_changed`, `_can_set_next_pass` | C++ extension points in the base class | Other subclasses can now guard inherited setters; must not become `GDVIRTUAL` without an API review | glossary ("Material guard hooks") |
| "Stencil preset owner" | Domain term | Names the root; not "parent material" (clashes with the next-pass chain) | glossary |

### 5.5 Decisions the plan needs, with recommendations

| # | Decision | Recommendation | Who |
|---|---|---|---|
| D1 (= 01 Q2) | Under a preset, should `render_priority` be **followed** (+1, max 126) or **locked**? | **Follow, and reject at 127.** That matches the intent of #107807 ("priority + 1") and #109052 (ceiling). Locking would surprise users who reorder transparent objects. | Stencil feature author / materials maintainer |
| D2 | Under a preset, should `next_pass` assignment be rejected, or the new pass silently chained behind the child? | **Reject.** Silent re-chaining hides intent. The docs already point to `material_overlay`. | Materials maintainer |
| D3 | Loading an inconsistent file: roll back the preset, clamp the priority to 126, or fail the load? | **Roll back with a named error.** It never invents data, and the file still loads (G5). | Resource-format maintainer |
| D4 | Should direct edits to the child be rejected (owner back-reference in every child setter)? | **Not now.** Keep the documented "lost" semantics; §4.7 makes them hold at every root operation. | Materials maintainer |
| D5 | Should `duplicate()` give the copy its own child? | **Yes.** The current sharing contradicts per-instance use and has no recorded rationale [?: no commit or PR found that chose it]. | Materials maintainer |

### 5.6 Risks

- **The editor inspector after a rejection.** Undo/redo records the attempted value [?]. It must be verified that undo does not replay a rejected write. Manual check in B1/B3: try to set priority 127 in the inspector, then press Ctrl+Z.
- **Projects relying on V3.** A user may drive `stencil_flags` from a script while in OUTLINE. After B2 this prints an error. The `experimental` tag (`BaseMaterial3D.xml:388-405`) covers this, but B6 must say so in the changelog entry.
- **Deferred reconcile timing (B5).** Code that reads `next_pass` in the same frame as the load still sees the orphan. This is accepted because the renderer first reads the material after the deferred queue has run [I].
- **`ALWAYS_DUPLICATE` reach (B4).** If the duplication property list skips `_validate_property`, use the §4.6 fallback. T-X6 decides.

---

## Method and coverage

- **Read for this document:** `01-domain-distillation.md`, `glossary.md`, `refactor-opportunities/{change,plan-brief}.md`, the progress headings of `plan.md`, `RefactoringUserNotes.txt`, `README.md:9-17`.
- **Code re-read for every anchor cited here:** `material.cpp` (`48-123, 164-176, 195-236, 420-456, 650-676, 895, 2088-2092, 2136-2170, 2595-2709, 3185-3372, 3595-3611, 3802-3809, 4020-4045, 4151-4155`); `material.h` (stencil fields and helpers, `79, 82, 642`); `object.cpp:596-621, 1097-1122`; `object.h:319-330`; `property_info.h:134, 150`; `resource.cpp:278-330, 376-426`; `resource_format_text.cpp:660-676, 2080-2110`; `error_macros.h:453-458`; both `material_storage.cpp` priority setters; `canvas_item_material.cpp:56-66`; `particle_process_material.cpp:172-178`; `shader_baker_export_plugin.cpp:305-355`; `SConstruct:277, 938-942`; `tests/test_main.cpp:182-203`; `tests/core/io/test_resource.cpp:530-560`.
- **Docs read:** `BaseMaterial3D.xml:7, 39, 388-405, 860-871`; `Material.xml:15-26, 53-70`.
- **History:** `git log -S"_stencil_owned"` → `d674c9e289`. The `-L` history of `material.cpp:3185-3271` gives `8ce3011ae6`, `b0947003e0`, `cd737eed2f` and their merges (#107807, #107808, #109052), all read as diffs.
- **Not done:** nothing was built or run, so every runtime consequence above is marked [I] and is pinned by a named test. The upstream issue threads (#107806, #108905) were not fetched. The binary loader's property order is assumed to match the text loader's [I]: both iterate the saved property list.
