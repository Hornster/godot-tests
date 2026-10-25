#!/usr/bin/env python3
"""Cross-language bridges into the C++ engine: JNI (Java/Kotlin), C# interop tables,
Emscripten JS libraries, Swift entry points. Text-only, stdlib-only.

Usage: python3 -I bridges.py <repo_root> <out.json>
Excludes thirdparty/ and the vendored com/android/apksig tree.
"""
import collections, json, os, re, subprocess, sys

ROOT = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
FILES = [f for f in subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True,
                                    check=True).stdout.splitlines()
         if not f.startswith("thirdparty/") and "/com/android/apksig/" not in f]
CPP_EXT = (".h", ".hpp", ".cpp", ".cc", ".c", ".mm", ".m", ".inc")
CPP = [f for f in FILES if f.endswith(CPP_EXT)]
DEEPER = {("servers", "rendering"), ("editor", "scene"), ("editor", "inspector"), ("scene", "gui")}

_cache = {}
def read(p):
    if p not in _cache:
        with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as fh:
            _cache[p] = fh.read()
    return _cache[p]

def component(path):
    """Same folder granularity as artifact 2 (cpp-dependencies stub components)."""
    d = path.split("/")[:-1]
    if not d: return "(root)"
    c = d[0]
    if len(d) >= 2: c += "." + d[1]
    if len(d) >= 3 and (d[0], d[1]) in DEEPER: c += "." + d[2]
    return c

def strip_c_comments(s):
    s = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)

def lineno(text, pos): return text.count("\n", 0, pos) + 1

def balanced_end(text, pos, open_ch, close_ch):
    """Index just past the bracket that closes the one opened right before `pos`."""
    depth = 1
    for i in range(pos, len(text)):
        if text[i] == open_ch: depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0: return i + 1
    return len(text)

INC_RE = re.compile(r'^\s*#\s*(?:include|import)\s+"([^"]+)"', re.M)
def include_reach(files):
    """Components reached by #include from a set of bridge files (repo-root includes only)."""
    reach = collections.Counter(); fileset = set(FILES)
    for f in files:
        for inc in INC_RE.findall(read(f)):
            if inc in fileset: reach[component(inc)] += 1
            else:
                rel = os.path.normpath(os.path.join(os.path.dirname(f), inc))
                if rel in fileset: reach[component(rel)] += 1
    return dict(reach.most_common())

# ----------------------------------------------------------------------------------------------
# 1. JNI
# ----------------------------------------------------------------------------------------------
JVM = [f for f in FILES if f.startswith("platform/android/java/") and f.endswith((".java", ".kt"))]

def jni_demangle(sym):
    """Java_pkg_Cls_method[__sig] -> ('pkg.Cls', 'method'). Handles _1 _0xxxx _00024 escapes."""
    body = sym[len("Java_"):].split("__")[0]
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == "_" and i + 1 < len(body) and body[i + 1] == "1": out.append("_"); i += 2
        elif ch == "_" and i + 1 < len(body) and body[i + 1] == "0": out.append(chr(int(body[i + 2:i + 6], 16))); i += 6
        elif ch == "_": out.append("."); i += 1
        else: out.append(ch); i += 1
    parts = "".join(out).split(".")
    return ".".join(parts[:-1]), parts[-1]

CLASS_RE = re.compile(r"\b(?:(companion)\s+object|(?:class|interface|object|enum\s+class|enum|record)\s+([A-Za-z_]\w*))")
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|static|final|synchronized|abstract|native|"
    r"default|strictfp)\s+)*(?:<[^>]+>\s+)?[\w<>\[\],.?]+(?:\s*\[\])*\s+(\w+)\s*\(", re.M)
KT_FUN_RE = re.compile(r"\bfun\s+(?:<[^>]+>\s*)?(?:[\w.<>?]+\.)?(\w+)\s*\(")
JAVA_FIELD_RE = re.compile(r"^\s*(?:(?:public|private|protected|static|final|volatile|transient)\s+)+"
                           r"[\w<>\[\],.?]+\s+(\w+)\s*[=;]", re.M)
KT_FIELD_RE = re.compile(r"\b(?:val|var)\s+(\w+)\s*[:=]")
JAVA_NATIVE_RE = re.compile(r"\bnative\b[^;{=]*?\b(\w+)\s*\([^;{]*\)\s*;", re.S)
KT_EXTERNAL_RE = re.compile(r"\bexternal\s+fun\s+(?:[\w.]+\.)?(\w+)\s*\(")
NOT_METHOD = {"if", "for", "while", "switch", "catch", "return", "new", "synchronized", "throw", "else"}

def jvm_scan():
    classes = {}           # fq class -> {file, package}
    methods = collections.defaultdict(set)   # name -> {fq class}
    fields = collections.defaultdict(set)
    natives = []           # {fq_class, method, file, line}
    for f in JVM:
        raw = read(f); text = strip_c_comments(raw)
        text = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
        pkg = (re.search(r"^\s*package\s+([\w.]+)", text, re.M) or [None, ""])[1]
        stem = os.path.splitext(os.path.basename(f))[0]
        is_kt = f.endswith(".kt")
        # walk the file tracking a class stack by brace depth
        stack = []  # (name or None for companion, depth_at_open)
        depth, pending = 0, None
        tokens = re.finditer(r"[{}]|" + CLASS_RE.pattern, text)
        events = []  # (pos, class_path) snapshot changes
        for m in tokens:
            t = m.group(0)
            if t == "{":
                depth += 1
                if pending is not None:
                    stack.append((pending, depth)); pending = None
                    events.append((m.start(), [n for n, _ in stack if n]))
            elif t == "}":
                if stack and stack[-1][1] == depth:
                    stack.pop(); events.append((m.start(), [n for n, _ in stack if n]))
                depth -= 1
            else:
                pending = "" if m.group(1) else m.group(2)   # companion: transparent
        def cls_at(pos):
            path = []
            for p, snap in events:
                if p > pos: break
                path = snap
            if not path: return f"{pkg}.{stem}Kt" if is_kt else f"{pkg}.{stem}"
            return pkg + "." + "$".join(path)
        for _, snap in events:
            if snap: classes.setdefault(pkg + "." + "$".join(snap), {"file": f, "package": pkg})
        for rx in ((KT_FUN_RE,) if is_kt else (JAVA_METHOD_RE,)):
            for m in rx.finditer(text):
                if m.group(1) not in NOT_METHOD: methods[m.group(1)].add(cls_at(m.start()))
        for rx in ((KT_FIELD_RE,) if is_kt else (JAVA_FIELD_RE,)):
            for m in rx.finditer(text): fields[m.group(1)].add(cls_at(m.start()))
        for rx in ((KT_EXTERNAL_RE,) if is_kt else (JAVA_NATIVE_RE,)):
            for m in rx.finditer(text):
                natives.append({"class": cls_at(m.start()), "method": m.group(1), "file": f,
                                "line": lineno(text, m.start())})
    return classes, methods, fields, natives

def jni():
    classes, methods, fields, natives = jvm_scan()
    exports = {}  # symbol -> {file, line}
    for f in CPP:
        if not f.startswith(("platform/android/", "modules/")): continue
        text = read(f)
        for m in re.finditer(r"\bJNIEXPORT\b[^;{]*?\b(Java_org_godotengine_\w+)\s*\(([^)]*)\)\s*\{", text):
            exports[m.group(1)] = {"file": f, "line": lineno(text, m.start(1))}
    exp_keys = {}
    for sym, loc in exports.items():
        c, meth = jni_demangle(sym)
        exp_keys[(c, meth)] = dict(loc, symbol=sym)
    nat_keys = {(n["class"], n["method"]): n for n in natives}
    matched = sorted(set(exp_keys) & set(nat_keys))
    only_cpp = sorted(set(exp_keys) - set(nat_keys)); only_jvm = sorted(set(nat_keys) - set(exp_keys))
    # C++ -> JVM upcalls
    call_re = re.compile(r"\b(Get(?:Static)?(?:Method|Field)ID)\s*\(\s*([^,]+?)\s*,\s*\"(\w+|<init>)\"\s*,\s*\"([^\"]*)\"")
    cls_lit_re = re.compile(r"(?:FindClass|jni_find_class)\s*\([^\"]*\"([\w/$]+)\"")
    upcalls = []
    for f in CPP:
        if not f.startswith(("platform/android/", "modules/")): continue
        text = read(f)
        if "MethodID" not in text and "FieldID" not in text: continue
        lits = {c.replace("/", ".") for c in cls_lit_re.findall(text)}
        godot_lits = {c for c in lits if c.startswith("org.godotengine")}
        for m in call_re.finditer(text):
            kind, _, name, sig = m.groups()
            idx = fields if "Field" in kind else methods
            cands = set(idx.get(name, ())) if name != "<init>" else set()
            narrowed = cands & godot_lits if cands & godot_lits else cands
            if len(narrowed) == 1: target, status = next(iter(narrowed)), "resolved"
            elif len(narrowed) > 1:
                # prefer the "main" class sharing the C++ wrapper stem
                pk = [c.rsplit(".", 1)[0].split(".") for c in narrowed]
                common = [x[0] for x in zip(*pk) if len(set(x)) == 1]
                target, status = {"candidates": sorted(narrowed), "common_package": ".".join(common)}, "ambiguous"
            elif name == "<init>" or any(not c.startswith("org.godotengine") for c in lits):
                target, status = None, "jdk_or_android_sdk"
            else: target, status = None, "unresolved"
            upcalls.append({"cpp_file": f, "line": lineno(text, m.start()), "kind": kind, "name": name,
                            "sig": sig, "status": status, "target": target})
    # aggregation
    edges = collections.Counter(); jvm_in = collections.Counter(); cpp_out = collections.Counter()
    for u in upcalls:
        if u["status"] == "resolved":
            edges[(u["cpp_file"], u["target"])] += 1; jvm_in[u["target"]] += 1; cpp_out[u["cpp_file"]] += 1
    down = collections.Counter(); down_files = collections.Counter(); down_cls = collections.Counter()
    for k in matched:
        down[(exp_keys[k]["file"], k[0])] += 1; down_files[exp_keys[k]["file"]] += 1; down_cls[k[0]] += 1
    jni_files = sorted({e["file"] for e in exports.values()} | {u["cpp_file"] for u in upcalls})
    pkg_of = lambda c: c.rsplit(".", 1)[0] if c else None
    return {
        "jvm_files_scanned": len(JVM), "jvm_classes": len(classes),
        "downcalls": {
            "cpp_exports": len(exports), "jvm_native_decls": len(natives), "matched": len(matched),
            "cpp_only": [exp_keys[k]["symbol"] for k in only_cpp],
            "jvm_only": [f"{k[0]}.{k[1]} ({nat_keys[k]['file']}:{nat_keys[k]['line']})" for k in only_jvm],
            "by_cpp_file": dict(down_files.most_common()), "by_jvm_class": dict(down_cls.most_common()),
            "edges": [{"cpp": a, "jvm": b, "n": n} for (a, b), n in down.most_common()]},
        "upcalls": {
            "total": len(upcalls),
            "status": dict(collections.Counter(u["status"] for u in upcalls)),
            "by_cpp_file": dict(collections.Counter(u["cpp_file"] for u in upcalls).most_common()),
            "resolved_by_jvm_class": dict(jvm_in.most_common()),
            "resolved_by_jvm_package": dict(collections.Counter(
                {p: sum(n for c, n in jvm_in.items() if pkg_of(c) == p) for p in {pkg_of(c) for c in jvm_in}}
            ).most_common()),
            "edges": [{"cpp": a, "jvm": b, "n": n} for (a, b), n in edges.most_common()],
            "ambiguous": [f"{u['cpp_file']}:{u['line']} {u['name']} -> {len(u['target']['candidates'])} classes "
                          f"in {u['target']['common_package'] or '(no common package)'}"
                          for u in upcalls if u["status"] == "ambiguous"],
            "ambiguous_by_common_package": dict(collections.Counter(
                u["target"]["common_package"] or "(none)" for u in upcalls if u["status"] == "ambiguous").most_common()),
            "unresolved": [f"{u['cpp_file']}:{u['line']} {u['name']}{u['sig']}" for u in upcalls
                           if u["status"] == "unresolved"]},
        "bridge_cpp_files": jni_files,
        "bridge_cpp_components": dict(collections.Counter(component(f) for f in jni_files)),
        "include_reach_of_bridge_files": include_reach(jni_files),
    }

# ----------------------------------------------------------------------------------------------
# 2. C# <-> C++
# ----------------------------------------------------------------------------------------------
def cpp_table(path, var="unmanaged_callbacks"):
    text = strip_c_comments(read(path))
    m = re.search(r"static\s+const\s+void\s*\*\s*" + var + r"\s*\[\]\s*\{(.*?)\};", text, re.S)
    return re.findall(r"\(void\s*\*\)\s*&?\s*(\w+)", m.group(1)) if m else []

def cs_partial_order(path, prefix):
    text = strip_c_comments(read(path))
    return re.findall(r"\bpartial\b[^;{()]*?\b(" + prefix + r"\w*)\s*\(", text)

def csharp():
    cs_files = [f for f in FILES if f.startswith("modules/mono/") and f.endswith(".cs")]
    # tables
    rt_cpp = cpp_table("modules/mono/glue/runtime_interop.cpp")
    rt_cs_file = "modules/mono/glue/GodotSharp/GodotSharp/Core/NativeInterop/NativeFuncs.cs"
    rt_cs = cs_partial_order(rt_cs_file, "godotsharp_")
    ed_cpp = cpp_table("modules/mono/editor/editor_internal_calls.cpp")
    ed_cs_file = "modules/mono/editor/GodotTools/GodotTools/Internals/Internal.cs"
    ed_cs = cs_partial_order(ed_cs_file, "godot_icall_")
    def compare(a, b):
        return {"cpp": len(a), "cs": len(b), "matched": len(set(a) & set(b)),
                "cpp_only": sorted(set(a) - set(b)), "cs_only": sorted(set(b) - set(a)),
                "same_order": a == b,
                "first_order_mismatch": next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)}
    # C# consumers of NativeFuncs (outside the declaring files)
    uses = collections.Counter(); use_files = collections.Counter()
    for f in cs_files:
        if "/NativeFuncs" in f: continue
        found = re.findall(r"\b(godotsharp_\w+)\b", strip_c_comments(read(f)))
        if found: use_files[f] = len(found); uses.update(set(found))
    ext = "modules/mono/glue/GodotSharp/GodotSharp/Core/NativeInterop/NativeFuncs.extended.cs"
    if ext in FILES: uses.update(set(re.findall(r"\b(godotsharp_\w+)\s*\(", strip_c_comments(read(ext)))))
    unused = sorted(set(rt_cs) - set(uses))
    # reverse direction: managed callbacks
    hdr = strip_c_comments(read("modules/mono/mono_gd/gd_mono_cache.h"))
    sm = re.search(r"struct\s+ManagedCallbacks\s*\{(.*?)\};", hdr, re.S)
    cb_cpp = re.findall(r"^\s*Func\w+\s+(\w+)\s*;", sm.group(1), re.M) if sm else []
    mc_cs = strip_c_comments(read("modules/mono/glue/GodotSharp/GodotSharp/Core/Bridge/ManagedCallbacks.cs"))
    cb_cs = []
    for m in re.finditer(r"public\s+delegate\*\s*unmanaged<", mc_cs):
        nm = re.match(r"\s*(\w+)\s*;", mc_cs[balanced_end(mc_cs, m.end(), "<", ">"):])
        if nm: cb_cs.append(nm.group(1))
    cb_impl = dict(re.findall(r"\b(\w+)\s*=\s*&([\w.]+)\s*,", mc_cs))
    cb_use = collections.Counter(); cb_files = collections.Counter()
    for f in CPP:
        if not f.startswith("modules/mono/"): continue
        hits = re.findall(r"managed_callbacks\.(\w+)", read(f))
        if hits: cb_files[f] = len(hits); cb_use.update(hits)
    cb_cs_class = collections.Counter(v.split(".")[0] for v in cb_impl.values())
    # bindings generator
    bg = "modules/mono/editor/bindings_generator.cpp"; bgt = read(bg)
    interop_files = ["modules/mono/glue/runtime_interop.cpp", "modules/mono/editor/editor_internal_calls.cpp"]
    mono_cpp = [f for f in CPP if f.startswith("modules/mono/")]
    csproj_refs = {}
    for f in FILES:
        if f.startswith("modules/mono/") and f.endswith(".csproj"):
            refs = re.findall(r'ProjectReference\s+Include="([^"]+)"', read(f))
            csproj_refs[os.path.basename(f)[:-7]] = sorted(
                os.path.basename(r.replace("\\", "/"))[:-7] for r in refs)
    return {
        "runtime_interop_table": compare(rt_cpp, rt_cs),
        "editor_icall_table": compare(ed_cpp, ed_cs),
        "godotsharp_cs_consumers": {"files": len(use_files), "top_files": dict(use_files.most_common(12)),
                                    "declared_but_unreferenced_in_cs": unused},
        "managed_callbacks": {"cpp_fields": len(cb_cpp), "cs_fields": len(cb_cs),
                              "same_order": cb_cpp == cb_cs,
                              "cpp_only": sorted(set(cb_cpp) - set(cb_cs)), "cs_only": sorted(set(cb_cs) - set(cb_cpp)),
                              "cs_impl_classes": dict(cb_cs_class.most_common()),
                              "cpp_call_sites_by_file": dict(cb_files.most_common()),
                              "never_called_from_cpp": sorted(set(cb_cpp) - set(cb_use))},
        "bindings_generator": {"file": bg, "lines": bgt.count("\n"),
                               "classdb_refs": len(re.findall(r"\bClassDB::", bgt)),
                               "writes_generated_dirs": sorted(set(re.findall(r'"(Generated[^"]*)"', bgt))),
                               "include_reach": include_reach([bg])},
        "include_reach_of_interop_files": include_reach(interop_files),
        "include_reach_of_all_mono_cpp": include_reach(mono_cpp),
        "csproj_graph": csproj_refs,
    }

# ----------------------------------------------------------------------------------------------
# 3. Web / Emscripten
# ----------------------------------------------------------------------------------------------
def web():
    js = [f for f in FILES if f.endswith(".js") and not f.endswith(".externs.js")
          and ("/libs/library_" in f or os.path.basename(f).startswith("library_"))]
    objects = {}   # name -> {file, exports[], declared_deps, used}
    for f in js:
        text = strip_c_comments(read(f))
        reg = set(re.findall(r"(?:mergeInto\(\s*LibraryManager\.library\s*,|addToLibrary\()\s*(\w+)\s*\)", text))
        for m in re.finditer(r"^(?:const|let|var)\s+(\w+)\s*=\s*\{(.*?)^\};", text, re.S | re.M):
            name, body = m.group(1), m.group(2)
            lib = re.search(r"^\t\$([A-Za-z0-9]+)\s*:", body, re.M)
            lib_name = lib.group(1) if lib else name.lstrip("_")
            exports = [e for e in re.findall(r"^\t(\w+)\s*:\s*(?:function\b|\(|async\b)", body, re.M)]
            deps = set()
            for d in re.findall(r"__deps\s*:\s*\[([^\]]*)\]", body):
                deps |= {x.strip("'\" $") for x in d.split(",") if x.strip()}
            objects[lib_name] = {"var": name, "file": f, "registered": name in reg, "exports": exports,
                                 "declared_deps": sorted(deps - {lib_name}), "body": body}
    libnames = set(objects)
    for o in objects.values():
        used = {n for n in libnames if re.search(r"\b" + re.escape(n) + r"\.", o["body"])}
        o["used_libs"] = sorted(used)
    export_owner = {e: n for n, o in objects.items() for e in o["exports"]}
    # C++ side: declarations inside extern "C" headers/files, and call sites anywhere
    decl, calls = {}, collections.defaultdict(list)
    names = set(export_owner)
    tok = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b") if names else None
    decl_re = re.compile(r"^\s*(?:extern\s+)?(?:(?:const|unsigned|signed|long|short|struct)\s+)*(?!return\b)[A-Za-z_]\w*(?:\s*\*+\s*|\s+)\**\s*(\w+)\s*\(", re.M)
    cpp_decl_only = []
    for f in CPP:
        text = strip_c_comments(read(f))
        if 'extern "C"' in text and f.startswith(("platform/web/", "modules/")):
            for m in decl_re.finditer(text):
                n = m.group(1)
                end = balanced_end(text, m.end(), "(", ")")
                after = text[end:end + 40].lstrip()
                if after.startswith(";") and (n in names or re.match(r"godot_(js|audio|webxr|webmidi|webrtc|websocket)\w*$", n)):
                    decl.setdefault(n, set()).add(f"{f}:{lineno(text, m.start(1))}")
        if tok:
            decl_lines = set()
            for m in tok.finditer(text):
                ln = lineno(text, m.start())
                n = m.group(1)
                if f"{f}:{ln}" in decl.get(n, ()): continue
                calls[n].append(f"{f}:{ln}")
    exported, declared = set(export_owner), set(decl)
    called = {n for n, v in calls.items() if v}
    by_lib_comp = collections.defaultdict(collections.Counter)
    for n, sites in calls.items():
        for s in sites: by_lib_comp[export_owner[n]][component(s.split(":")[0])] += 1
    cpp_files = sorted({s.split(":")[0] for v in calls.values() for s in v})
    home = ("platform/web/", "modules/webxr/", "modules/webrtc/", "modules/websocket/")
    foreign = sorted(f"{s} {n}" for n, v in calls.items() for s in v if not s.startswith(home))
    # JS-internal graph
    graph = {n: sorted(set(o["declared_deps"]) & libnames) for n, o in objects.items()}
    ext_deps = {n: sorted(set(o["declared_deps"]) - libnames) for n, o in objects.items()}
    fanin = collections.Counter(d for v in graph.values() for d in v)
    # cycles (Tarjan)
    idx, low, st, on, sccs, c = {}, {}, [], set(), [], [0]
    def strong(v):
        idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on.add(v)
        for w in graph.get(v, []):
            if w not in idx: strong(w); low[v] = min(low[v], low[w])
            elif w in on: low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            s = []
            while True:
                w = st.pop(); on.discard(w); s.append(w)
                if w == v: break
            if len(s) > 1: sccs.append(sorted(s))
    for v in sorted(graph):
        if v not in idx: strong(v)
    undeclared = {n: sorted(set(o["used_libs"]) - set(o["declared_deps"]) - {n}) for n, o in objects.items()}
    # C++ -> JS other channels; JS -> C++ callbacks
    em_asm = sum(len(re.findall(r"\b(?:EM_ASM\w*|EM_JS|emscripten_run_script\w*)\s*\(", read(f)))
                 for f in CPP if f.startswith(("platform/web/", "modules/")))
    keepalive = [f"{f}:{lineno(read(f), m.start())}" for f in CPP for m in re.finditer(r"EMSCRIPTEN_KEEPALIVE", read(f))]
    get_func = sum(len(re.findall(r"GodotRuntime\.get_func\(", read(f))) for f in js)
    return {
        "js_library_files": len(js), "js_library_objects": len(objects),
        "objects": {n: {"file": o["file"], "exports": len(o["exports"]), "declared_deps": o["declared_deps"]}
                    for n, o in sorted(objects.items())},
        "js_exports": len(exported), "cpp_declared": len(declared), "cpp_called": len(called & exported),
        "exported_and_declared": len(exported & declared),
        "exported_never_referenced_from_cpp": sorted(exported - called - declared),
        "exported_not_declared": sorted(exported - declared),
        "cpp_declarations": {k: sorted(v) for k, v in sorted(decl.items())},
        "exported_declared_not_called": sorted((exported & declared) - called),
        "declared_not_exported": sorted(declared - exported),
        "lib_to_cpp_components": {k: dict(v.most_common()) for k, v in sorted(by_lib_comp.items())},
        "cpp_call_site_files": dict(collections.Counter(
            s.split(":")[0] for v in calls.values() for s in v).most_common()),
        "bridge_cpp_components": dict(collections.Counter(component(f) for f in cpp_files)),
        "include_reach_of_bridge_files": include_reach([f for f in cpp_files if f.startswith(home)]),
        "call_sites_outside_web_platform_and_modules": foreign,
        "js_graph": graph, "js_external_deps": {k: v for k, v in ext_deps.items() if v},
        "js_fanin": dict(fanin.most_common()), "js_cycles": sccs,
        "js_used_but_undeclared": {k: v for k, v in undeclared.items() if v},
        "em_asm_em_js_count": em_asm, "emscripten_keepalive": keepalive,
        "js_to_cpp_function_pointer_calls": get_func,
    }

# ----------------------------------------------------------------------------------------------
# 4. Swift
# ----------------------------------------------------------------------------------------------
def swift():
    sw = [f for f in FILES if f.endswith(".swift")]
    out = {"files": {}, "chain": []}
    for f in sw:
        t = read(f)
        out["files"][f] = {
            "lines": t.count("\n"),
            "main": [lineno(t, m.start()) for m in re.finditer(r"^@main\b", t, re.M)],
            "delegate_adaptor": re.findall(r"UIApplicationDelegateAdaptor\((\w+)\.self\)", t),
            "objc_exports": re.findall(r"@objc\s*\n?\s*(?:public\s+)?(?:final\s+)?class\s+(?!var\b|func\b|let\b)(\w+)", t),
            "objc_types_used": sorted(set(re.findall(r"\b(GDT\w+)\b", t)))}
    mm = [f for f in CPP if f.endswith((".mm", ".h", ".m"))]
    def find(rx, files=mm):
        return [f"{f}:{lineno(read(f), m.start())}" for f in files for m in re.finditer(rx, read(f), re.M)]
    for f, info in out["files"].items():
        for d in info["delegate_adaptor"]:
            impl = find(r"^@implementation\s+" + d + r"\b")
            iface = find(r"^@interface\s+" + d + r"\s*:\s*\w+")
            out["chain"].append({"swift_main": f"{f}:{info['main'][0] if info['main'] else '?'}", "delegate": d,
                                 "impl": impl, "interface": iface,
                                 "add_service": [s for s in find(r"addService:\[\w+") if impl and
                                                 s.split(":")[0] == impl[0].split(":")[0]],
                                 "services": [m for f2 in ([impl[0].split(":")[0]] if impl else [])
                                              for m in re.findall(r"addService:\[(\w+)\s+new\]", read(f2))]})
    out["service_superclasses"] = {n: s for f in mm for n, s in
                                   re.findall(r"^@interface\s+(GDTAppDelegateService\w*)\s*:\s*(\w+)", read(f), re.M)}
    out["bridging_headers"] = {f: re.findall(r'#import\s+"([^"]+)"', read(f)) for f in FILES
                               if os.path.basename(f).startswith("bridging_header")}
    out["apple_embedded_main_calls"] = [x for x in find(r"^(?!\s*extern).*\bapple_embedded_main\s*\(\s*\w+\s*,")]
    out["apple_embedded_main_defs"] = find(r"^int\s+apple_embedded_main\s*\(")
    out["main_setup_calls"] = find(r"\bMain::setup\w*\s*\(", [f for f in CPP if re.search(r"main_(ios|visionos)\.mm$", f)])
    out["swift_types_used_from_objc"] = find(r"\bGDTSwiftBridge\b")
    return out

res = {"jni": jni(), "csharp": csharp(), "web": web(), "swift": swift()}
with open(OUT, "w") as fh: json.dump(res, fh, indent=1, default=list)
j, c, w = res["jni"], res["csharp"], res["web"]
print("JNI down: exports", j["downcalls"]["cpp_exports"], "natives", j["downcalls"]["jvm_native_decls"],
      "matched", j["downcalls"]["matched"], "cpp_only", len(j["downcalls"]["cpp_only"]), "jvm_only", len(j["downcalls"]["jvm_only"]))
print("JNI up:", j["upcalls"]["total"], j["upcalls"]["status"])
print("C# runtime table:", {k: v for k, v in c["runtime_interop_table"].items()})
print("C# editor table:", {k: v for k, v in c["editor_icall_table"].items()})
print("C# managed cb:", {k: v for k, v in c["managed_callbacks"].items() if k != "cpp_call_sites_by_file"})
print("Web: exports", w["js_exports"], "declared", w["cpp_declared"], "called", w["cpp_called"],
      "exp&decl", w["exported_and_declared"], "cycles", w["js_cycles"])
