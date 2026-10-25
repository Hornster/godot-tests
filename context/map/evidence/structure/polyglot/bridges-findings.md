# Polyglot B: cross-language bridges into the C++ engine

Source: `bridges.py` → `bridges.json` (stdlib-only, text-only; `thirdparty/` and the vendored `com/android/apksig` are excluded). Components use the same folder naming as artifact 2.

## Headline

| Bridge | Mechanism | Pairs found | Matched | Unmatched | C++ side lives in |
|---|---|---:|---:|---:|---|
| Java/Kotlin → C++ | JNI `native`/`external fun` ↔ `JNIEXPORT Java_org_godotengine_*` | 77 ↔ 77 | **77** | 0 / 0 | `platform.android` (6 files) |
| C++ → Java/Kotlin | `Get[Static]{Method,Field}ID(cls,"name","sig")` | 175 call sites | 100 resolved to a class | 28 ambiguous, 47 JDK/Android SDK | `platform.android` (9 files) |
| C# → C++ | `godotsharp_*` function-pointer table (`runtime_interop.cpp:1586` `unmanaged_callbacks[]` ↔ `NativeFuncs.cs` `[GenerateUnmanagedCallbacks]`) | 226 ↔ 226 | **226, same order** | 0 / 0 | `modules.mono` |
| C# editor → C++ | `godot_icall_*` table (`editor/editor_internal_calls.cpp:259` ↔ `GodotTools/Internals/Internal.cs`) | 33 ↔ 33 | **33, same order** | 0 / 0 | `modules.mono` |
| C++ → C# | `GDMonoCache::ManagedCallbacks` struct (`gd_mono_cache.h:71`) ↔ `Bridge/ManagedCallbacks.cs` | 43 ↔ 43 | **43, same order** | 0 / 0; all 43 called from C++ | `modules.mono` |
| C++ → JS | Emscripten `--js-library` exports (`mergeInto(LibraryManager.library, …)`) ↔ `extern "C"` declarations | 182 ↔ 182 | **182**, all called from C++ | 0 / 0 | `platform.web`, `modules.{webxr,webrtc,websocket}`, see below |
| JS → C++ | C function pointers passed into JS, invoked via `GodotRuntime.get_func()` | 59 sites | — | — | callbacks in the same files |
| Swift → ObjC++ | SwiftUI `@main` + `@UIApplicationDelegateAdaptor` + bridging headers | 2 entry points | — | — | `platform.{ios,visionos}`, `drivers.apple_embedded` |

The ordered tables (C# → C++, C++ → C#) are ABI-by-position, so reordering or skipping an entry would break them silently. The text check finds all three pairs aligned at HEAD.

## 1. JNI (Android), 101 Godot Java/Kotlin files, 134 classes
- **Downcalls by C++ file:** `java_godot_lib_jni.cpp` 50 (→ `GodotLib`, the engine lifecycle: initialize/setup/step/input), `editor/game_menu_utils_jni.cpp` 15 (→ `GameMenuUtils`), `plugin/godot_plugin_jni.cpp` 4, `variant/callable_jni.cpp` 4, `editor/editor_utils_jni.cpp` 2, `dialog_utils_jni.cpp` 2.
- **Upcalls by C++ file:** `java_godot_wrapper.cpp` 53, `java_class_wrapper.cpp` 36 (reflection: mostly `java.lang.*`), `jni_utils.cpp` 22, `java_godot_io_wrapper.cpp` 19, `file_access_filesystem_jandroid.cpp` 16, `dir_access_jandroid.cpp` 13, `tts_android.cpp` 9, `java_godot_view_wrapper.cpp` 5, `net_socket_android.cpp` 2.
- **Java-side hubs (resolved upcalls):** `org.godotengine.godot.nativeapi.GodotNativeBridge` **53** (the single façade the engine calls), `GodotIO` 16, `io.file.FileAccessHandler` 12, `tts.GodotTTS` 8, `plugin.SignalInfo` 4.
- **Ambiguous (28):** almost all are polymorphic dispatch over one interface. In `io.directory` 11 (`DirectoryAccessHandler` vs `Assets/FilesystemDirectoryAccess`), `io.file` 3, render views (`GodotGLRenderView` / `GodotVulkanRenderView`) and `GodotIO`/`GodotEditText` 9. These are true runtime polymorphism, not resolution errors.
- **Include reach of the 15 JNI C++ files:** `platform.android` 44, `core.os` 6, `core.config` 4, `editor` 3, `editor.{debugger,run,settings}` 2 each, `main` 2, `servers.display` 2, plus `servers.{camera,rendering,xr}`. The editor reach comes from the Android **editor** build (`platform/android/editor/*_jni.cpp`).

## 2. C# ↔ C++ (modules/mono)
- **C# → C++:** 226 `godotsharp_*` functions. 24 hand-written C# files consume them; the heaviest are `VariantUtils.cs` 75, `Array.cs` 46, `Dictionary.cs` 43, `ScriptManagerBridge.cs` 32, `GD.cs` 26, `Marshaling.cs` 21.
- **13 functions are declared but never referenced in hand-written C#**, among them `godotsharp_method_bind_ptrcall` / `_call` and the typed-dictionary getters. They are used by the **generated** API (`GodotSharp/Generated`, gitignored), see Unknowns.
- **C++ → C#:** 43 managed callbacks, implemented by `ScriptManagerBridge` 20, `CSharpInstanceBridge` 11, `DelegateUtils` 6, `GCHandleBridge` 2, and 4 others. The C++ call sites are concentrated in **`csharp_script.cpp` (44 of 55)**, then `managed_callable.cpp` 5.
- **API generation:** `editor/bindings_generator.cpp` (5,306 lines, 53 `ClassDB::` references) walks ClassDB at editor runtime and writes `Generated/`, `Generated/GodotObjects`, `GeneratedIncludes.props`. Its static include reach is small (`core.io`, `core.config`, `core.os`, `main`). Its real reach is **every class registered in ClassDB**, which is invisible to an include graph.
- **Include reach:** of the 2 interop tables: `modules.mono` 13, `core.*` 17, `editor.*` 9 (`editor.file_system`, `export`, `run`, `script`, `settings`, …), `main` 1. Of all `modules/mono` C++: `core.*` 112, `editor.*` 20, `scene.*` 4, `servers.text` 1, `main` 2.
- **.csproj graph (16 projects):** `GodotSharp` → `Godot.SourceGenerators.Internal`. `GodotSharpEditor` and `GodotPlugins` → `GodotSharp`. `GodotTools` → 6 projects (BuildLogger, Core, IdeMessaging, ProjectEditor, both SourceGenerators). The graph is acyclic.

## 3. Web (Emscripten), 15 JS library files, 30 library objects
- **Exports by library → C++ component:** `GodotDisplay` 40 exports / 48 call sites, `GodotAudio` 26, `GodotWebXR` 18 (→ `modules.webxr`), `GodotInput` 16, `GodotRTCDataChannel` 13 + `GodotRTCPeerConnection` 8 (→ `modules.webrtc`), `GodotJSWrapper` 12, `GodotOS` 11, `GodotFetch` 7, `GodotWebSocket` 5 (→ `modules.websocket`), `GodotWebGL2` 3 (→ `drivers.gles3` + `platform.web`).
- **C++ files that hold the bridge:** `display_server_web.cpp` 65, `audio_driver_web.cpp` 38, `webxr_interface_js.cpp` 23, `javascript_bridge_singleton.cpp` 15, `os_web.cpp` 14, `webrtc_data_channel_js.cpp` 13, `http_client_web.cpp` 10.
- **Calls from outside the web platform and modules:**
  - `editor/editor_node.cpp:229,3824` and `editor/docks/filesystem_dock.cpp:85,2326,2337` declare their own local `extern void godot_js_os_download_buffer(...)` under `#ifdef WEB_ENABLED`. **editor → JS directly, bypassing `platform/web` headers.**
  - `drivers/gles3/storage/{utilities,particles_storage}.cpp` call `godot_webgl2_glGetBufferSubData` under `__EMSCRIPTEN__`.
- **JS-internal graph** (`$X__deps`): no cycles. Fan-in: `GodotRuntime` 22, `GodotConfig` 8, `IDHandler` 7, `GodotEventListeners` 6, `GodotOS` 4. 6 libraries use another library without declaring it (e.g. `GodotAudio` → `GodotConfig`); all 6 are covered transitively, so this is implicit coupling, not a broken link. External deps: Emscripten `FS`/`IDBFS`/`GL`/`MainLoop`.
- **Other channels:** EM_ASM/EM_JS **0**. `EMSCRIPTEN_KEEPALIVE` 3 (`web_main.cpp:134`, `webxr_interface_js.cpp:99,109`).

## 4. Swift (iOS / visionOS)
| Hop | iOS | visionOS |
|---|---|---|
| `@main struct SwiftUIApp: App` | `platform/ios/app_ios.swift:33` | `platform/visionos/app_visionos.swift:302` |
| `@UIApplicationDelegateAdaptor` → ObjC delegate | `GDTAppDelegateIOS` (`godot_app_delegate_ios.mm:35`) | `GDTAppDelegateVisionOS` (`godot_app_delegate_visionos.mm:35`) |
| `addService:` | `GDTAppDelegateService` (`…_ios.mm:38`) | `GDTAppDelegateServiceVisionOS : GDTAppDelegateService` (`…_visionos.mm:38`) |
| `didFinishLaunchingWithOptions` → `apple_embedded_main()` | `drivers/apple_embedded/godot_app_delegate_service_apple_embedded.mm:72/86` (shared) | same |
| `apple_embedded_main` → `Main::setup` | `platform/ios/main_ios.mm:44 → :62` | `platform/visionos/main_visionos.mm:44 → :57` |

- **Reverse direction (ObjC++ → Swift):** visionOS ObjC++ reads `@objc GDTSwiftBridge` (`godot_app_delegate_service_visionos.mm:103–123`, 8 references) for immersion and overlay settings. `drivers/apple_embedded/godot_swiftui_view_controller.swift` hosts `GDTViewController` in SwiftUI. `misc/dist/.../dummy.swift` is a placeholder.
- **Bridging headers:** `platform/ios/bridging_header_ios.h` and `platform/visionos/bridging_header_visionos.h` → `drivers/apple_embedded/bridging_header_apple_embedded.h`, which exposes 3 headers to Swift.

## Unknowns
- **C# generated API:** `GodotSharp/Generated` (gitignored) is produced by `bindings_generator.cpp` and is the main consumer of `godotsharp_method_bind_*`. Its size and its coupling to ClassDB can't be measured from source.
- **Ambiguous JNI upcalls (28):** the target class is fixed at runtime by the `jobject` C++ receives, not by text. `java_class_wrapper.cpp` adds reflection-based calls to *arbitrary* Java classes (plugins), which are unbounded by design.
- **JS → C++ callbacks (59 `get_func`):** counted, not mapped per function; the target is whatever function pointer C++ passed in.
- **Build guards:** only the out-of-platform JS callers were guard-checked. JNI/Web/mono bridge files are build-selected by SCons per platform and not evaluated here.
- **Heuristic method index:** Java/Kotlin methods are indexed by regex. Kotlin top-level functions are mapped to `<File>Kt`; nested classes are tracked by brace depth. A miss would show up as JNI unmatched (there are 0).
