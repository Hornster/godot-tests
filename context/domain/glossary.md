---
title: "Glossary for agents: Materials domain"
created: 2026-11-02
type: glossary
companion_of: context/domain/01-domain-distillation.md
---

# Glossary for agents: Materials domain

Short rules for naming things in `scene/resources` material work. Evidence and sources are in `01-domain-distillation.md`.

| Term | What it means | Name in code | Do NOT call it |
|---|---|---|---|
| Material | Saveable resource that decides how geometry is coloured and shaded | `Material` (`scene/resources/material.h`) | "material" for the renderer-side record (that is the *material storage record*, `MaterialStorage::Material`) |
| Material storage record | Renderer-side state of a material, addressed by RID | `RendererRD::MaterialStorage::Material`, `GLES3::Material` | "Material" without a qualifier; "resource" |
| No-code material | The 3D material users configure without writing a shader | `BaseMaterial3D`, concrete `StandardMaterial3D` / `ORMMaterial3D` | "built-in material" (clashes with *built-in resource*); "SpatialMaterial" (3.x name, compatibility alias only) |
| Shader material | Material driven by a user-written `Shader` plus per-material uniform values | `ShaderMaterial` | "custom material" (scripts/GDExtension can also inherit `Material`) |
| Shader (resource) | User-authored shader program with a mode | `Shader`, `Shader::Mode` | "generated shader" |
| Generated shader | Shader text a no-code / canvas / particle material produces from its settings | `_update_shader()` output; `ShaderData::shader` | "Shader resource"; "the material's shader" when you mean a `Shader` object |
| Shader variant | One compiled permutation identified by the material's settings | scene side: `MaterialKey`; renderer side: `ShaderVersion` | "Variant" on its own (that is the engine's dynamic value type) |
| Shader cache | Per-family map from variant key to `{shader RID, users}`, refcounted and shared by all materials with the same key | `shader_map`, `ShaderData` | "pool", "registry", "ShaderData" when you mean the renderer's compiled data |
| Value edit | Edit that only changes a uniform value and goes straight to the renderer | `_material_set_param` / `RS::material_set_param` | "shader change"; "dirty" |
| Shader-key edit | Edit that changes which variant is needed (feature, flag, mode, texture presence) and is applied on the next flush | `_queue_shader_change` → `dirty_materials` → `flush_changes` | "value change"; "immediate" |
| Feature | Opt-in capability of a no-code material that costs GPU time only when enabled | `BaseMaterial3D::Feature`, `set_feature` | "flag" |
| Flag | On/off behaviour switch of a no-code material, one per call | `BaseMaterial3D::Flags`, `set_flag` | "feature"; "draw flag" (Sprite3D/Label3D); "particle flag" (PPM) |
| Texture slot | Named texture input of a no-code material | `BaseMaterial3D::TextureParam` | "texture parameter" (clashes with particle *parameter*) |
| Shader parameter | Per-material value of one shader uniform, property `shader_parameter/<name>` | `set_shader_parameter`, `param_cache` | "shader_param", "shader_uniform", "param/" (legacy prefixes, load-time remap only) |
| Particle parameter | Randomised particle quantity with min/max range and optional curve | `ParticleProcessMaterial::Parameter`, `set_param_min/max/texture` | "shader parameter"; "uniform" |
| Next pass | Extra material that renders the same object again | `Material::next_pass` | "render pass" (renderer concept); "overlay" (that is a node slot) |
| Stencil-owned pass | Next-pass material created and managed by a stencil preset | next pass with meta `_stencil_owned` | "next pass" without qualifier when you mean the managed one |
| Render priority | Sort key for 3D materials, −128…127, never crosses the opaque/transparent split | `render_priority` | "draw order" (not guaranteed by it) |
| Material override / overlay / surface override | Node slots that replace or add a material on geometry | `material_override`, `material_overlay`, `surface_override_material` | "material" on its own when the slot matters |
| Init state | Loading guard: no shader updates until the material is ready | `init_state`, `_mark_ready`, `_mark_initialized` | "initialized" when you mean READY (there is an intermediate INITIALIZING) |
| Pending params | Uniform values held until the renderer RID exists | `pending_params` | "cache" |
| Default value | Value a property has on a fresh instance. Values equal to it are **not saved**. | `PropertyUtils::get_property_default_value`; `default=` in class XML | "initial value" (shader uniform defaults are a different thing) |
| Uniform default | Default written in the shader code, used for revert in the inspector | `shader_get_parameter_default` | "default value" without qualifier |
| Stored property | Property written to `.tres` / `.res` | `PROPERTY_USAGE_STORAGE` | "visible", "exported" (editor visibility is a separate bit) |
| Built-in resource | Resource embedded inside a scene file rather than its own file | `Resource::is_built_in()` | "built-in material", "embedded shader" |
| External resource | Resource saved to its own `.tres` / `.res` path | non-built-in `resource_path` | "global resource" |
| Local to scene | Resource duplicated per scene instance | `resource_local_to_scene` | "unique", "instanced" |
| Edited | Editor-only "has unsaved changes" mark set by undoable edits | `set_edited`, `is_edited` | "dirty" (that is the shader-key queue) |
| changed | Public resource signal | `Resource::changed`, `emit_changed()` | "property_list_changed" (inspector re-layout); "dirty" |
| Compatibility class | Old class name that still loads as the new class | `ClassDB::add_compatibility_class` (`SpatialMaterial`, `ParticlesMaterial`) | "alias type", "deprecated class" |
| Legacy remap | Old property name translated on load | `StandardMaterial3D::_set`, ShaderMaterial prefix remaps, under `DISABLE_DEPRECATED` | "migration" (there is no versioned file migration) |
| Conversion | Turning a generated material into an editable ShaderMaterial | `EditorResourceConversionPlugin`, `MaterialEditor::make_shader_material` | "export", "bake" |
| 2D-in-3D material | Cached StandardMaterial3D generated for Sprite3D / Label3D | `get_material_for_2d`, `materials_for_2d` | "sprite material", "Label3D material" (one factory serves both) |
| Shader baking | Export-time pre-compilation of the variants nodes will request | `ShaderBakerExportPlugin` | "conversion"; "shader cache" (that is the runtime map) |
| CPUParticles | CPU-simulated particle node, deliberately a lighter subset of GPU particles | `CPUParticles2D/3D`, `convert_from_particles` | "same as GPU particles"; "ParticleProcessMaterial on CPU" |
| Placeholder material | Stand-in with no render path | `PlaceholderMaterial` | "empty material", "default material" |
