#!/usr/bin/env python3
"""Internal dependency graphs of the managed-language code (text only, no compilation).

Java/Kotlin: Gradle subproject graph + package graph from `package`/`import` lines
in platform/android/java. C#: .csproj graph + namespace graph from `namespace`/`using`
in modules/mono. Cross-language bridges to C++ are out of scope.

Usage: python3 -I managed.py <repo_root> <out.json>
"""
import collections, json, os, re, subprocess, sys
import xml.etree.ElementTree as ET

ROOT, OUT = sys.argv[1], sys.argv[2]
ANDROID = "platform/android/java"
MONO = "modules/mono"


def tracked(prefix, exts):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--", prefix or "."], capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split("\0") if p.endswith(exts))


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
        return f.read()


def loc(p):
    return read(p).count("\n")


# One left-to-right scan so that `//` inside a string, or a quote inside a comment, is not misread.
# Covers Java/Kotlin/Groovy strings, C# verbatim (@"..") and raw ("""..""") strings.
TOKEN = re.compile(r'"""[\s\S]*?"""|(?:@\$?|\$@)"(?:""|[^"])*"|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
                   r'|/\*[\s\S]*?\*/|//[^\n]*')


def strip(src, keep_strings=False):
    def repl(m):
        t = m.group(0)
        if t.startswith("/"):
            return " "
        return t if keep_strings else '""'
    return TOKEN.sub(repl, src)


def code_only(src):
    return strip(src)


def tarjan(nodes, edges):
    """Iterative Tarjan; returns SCCs with more than one node, largest first."""
    idx, low, on, st, sccs, n = {}, {}, set(), [], [], 0
    for root in sorted(nodes):
        if root in idx:
            continue
        work = [(root, iter(sorted(edges.get(root, ()))))]
        idx[root] = low[root] = n; n += 1; st.append(root); on.add(root)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in idx:
                    idx[w] = low[w] = n; n += 1; st.append(w); on.add(w)
                    work.append((w, iter(sorted(edges.get(w, ())))))
                    break
                if w in on:
                    low[v] = min(low[v], idx[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == idx[v]:
                    comp = []
                    while True:
                        w = st.pop(); on.discard(w); comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1:
                        sccs.append(sorted(comp))
    return sorted(sccs, key=len, reverse=True)


def fan(edges):
    fin = collections.Counter()
    for a, bs in edges.items():
        for b in bs:
            fin[b] += 1
    fout = collections.Counter({a: len(bs) for a, bs in edges.items()})
    return fin.most_common(12), fout.most_common(12)


def longest_prefix(name, known):
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    return None


# ---------------------------------------------------------------- Java / Kotlin
def java_kotlin():
    gradle_files = tracked(ANDROID, ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"))
    # Subprojects: `include ':x'` + optional projectDir override; default dir = name with ':' -> '/'.
    subprojects = {}
    for g in gradle_files:
        if not os.path.basename(g).startswith("settings"):
            continue
        base = os.path.dirname(g)
        txt = read(g)
        for name in re.findall(r"include\s*\(?\s*['\"](:[^'\"]+)['\"]", txt):
            subprojects.setdefault(name, os.path.join(base, name.strip(":").replace(":", "/")))
        for name, d in re.findall(r"project\(['\"](:[^'\"]+)['\"]\)\.projectDir\s*=\s*file\(['\"]([^'\"]+)['\"]\)", txt):
            subprojects[name] = os.path.normpath(os.path.join(base, d))
    dir2proj = {d: n for n, d in subprojects.items()}
    declared, external = [], {}
    for g in gradle_files:
        if os.path.basename(g).startswith("settings"):
            continue
        proj = dir2proj.get(os.path.dirname(g), ":(root)")
        txt = strip(read(g), keep_strings=True)
        for conf, target in re.findall(r"(\w+)\s*\(?\s*project\(\s*['\"](:[^'\"]+)['\"]\s*\)", txt):
            declared.append(dict(src=proj, dst=target, conf=conf,
                                 note="alias of :lib when app is built inside an exported project" if target == ":godot:lib" else ""))
        for target in re.findall(r"targetProjectPath\s*=\s*['\"](:[^'\"]+)['\"]", txt):
            declared.append(dict(src=proj, dst=target, conf="targetProjectPath", note="macrobenchmark target"))
        ext = collections.Counter()
        for conf, group in re.findall(r"(\w*[Ii]mplementation|api|compileOnly)\s*\(?\s*['\"]([\w.\-]+):[\w.\-]+:", txt):
            ext[f"{conf} {'.'.join(group.split('.')[:2])}"] += 1
        if ext:
            external[proj] = dict(ext)

    files = tracked(ANDROID, (".java", ".kt"))
    def proj_of(p):
        best = max((d for d in dir2proj if p.startswith(d + "/")), key=len, default=None)
        return dir2proj.get(best, ":(root)")
    def source_set(p):
        m = re.search(r"/src/([^/]+)/", p)
        return m.group(1) if m else "?"

    info = {}
    for p in files:
        src = read(p)
        pkg = re.search(r"^\s*package\s+([\w.]+)", src, re.M)
        code = code_only(src)
        info[p] = dict(
            pkg=pkg.group(1) if pkg else "(default)",
            lang="kotlin" if p.endswith(".kt") else "java",
            proj=proj_of(p), sset=source_set(p), loc=src.count("\n"),
            imports=[(bool(s), t, bool(w)) for s, t, w in
                     re.findall(r"^\s*import\s+(static\s+)?([\w.]+?)(\.\*)?\s*(?:as\s+\w+)?\s*;?\s*$", strip(src, True), re.M)],
            types=set(re.findall(r"\b(?:class|interface|enum|record|object|typealias)\s+([A-Z]\w*)", code)),
            idents=set(re.findall(r"\b[A-Z]\w*\b", code)),
        )
    first_party = ("org.godotengine", "com.godot.game")
    vendored = collections.defaultdict(lambda: dict(files=0, loc=0, dirs=set()))
    for p, f in info.items():
        if not f["pkg"].startswith(first_party):
            root = ".".join(f["pkg"].split(".")[:3])
            v = vendored[root]; v["files"] += 1; v["loc"] += f["loc"]
            v["dirs"].add(p.split("/" + root.replace(".", "/") + "/")[0])
    own = {p: f for p, f in info.items() if f["pkg"].startswith(first_party)}

    pkg_files = collections.defaultdict(list)
    for p, f in own.items():
        pkg_files[f["pkg"]].append(p)
    known = set(pkg_files)
    type_file = {}  # (pkg, Type) -> file
    for p, f in own.items():
        for t in f["types"]:
            type_file.setdefault((f["pkg"], t), p)

    pkg_edges = collections.defaultdict(collections.Counter)
    file_edges_import, external_imports = set(), collections.Counter()
    wildcard = 0
    for p, f in own.items():
        for static, target, wild in f["imports"]:
            wildcard += wild
            tp = longest_prefix(target, known) if target.startswith(first_party) else None
            if tp is None:
                if not target.startswith(first_party):
                    external_imports[".".join(target.split(".")[:2])] += 1
                continue
            if tp != f["pkg"]:
                pkg_edges[f["pkg"]][tp] += 1
            rest = target[len(tp) + 1:].split(".")
            if rest and rest[0] and (tp, rest[0]) in type_file:
                file_edges_import.add((p, type_file[(tp, rest[0])]))
    edges = {a: set(bs) for a, bs in pkg_edges.items()}
    fin, fout = fan(edges)

    # Package -> subprojects that define it; subproject edges derived from imports.
    pkg_projs = {k: sorted({own[p]["proj"] for p in v}) for k, v in pkg_files.items()}
    proj_edges = collections.Counter()
    violations = []
    rank = {":lib": 0, ":app:dataLib": 1, ":dataLib": 1, ":app": 2, ":editor": 2}
    for p, f in own.items():
        for static, target, wild in f["imports"]:
            tp = longest_prefix(target, known) if target.startswith(first_party) else None
            if tp is None:
                continue
            rest = target[len(tp) + 1:].split(".")[0]
            dst_file = type_file.get((tp, rest))
            dst_projs = [own[dst_file]["proj"]] if dst_file else pkg_projs[tp]
            for dp in dst_projs:
                if dp != f["proj"]:
                    proj_edges[(f["proj"], dp)] += 1
                    if rank.get(dp, 0) > rank.get(f["proj"], 0):
                        violations.append(dict(file=p, imports=target, from_proj=f["proj"], to_proj=dp))
    declared_pairs = {(d["src"], d["dst"]) for d in declared} | {(d["src"], ":lib") for d in declared if d["dst"] == ":godot:lib"}
    undeclared = [dict(src=a, dst=b, imports=n) for (a, b), n in proj_edges.items() if (a, b) not in declared_pairs]

    # Heuristic: same-package type references need no import. Count file->file edges by
    # matching capitalised identifiers against types declared in other files of the same package.
    same_pkg = set()
    for pkg, ps in pkg_files.items():
        for p in ps:
            for q in ps:
                if p != q and own[p]["idents"] & (own[q]["types"] - own[p]["types"]):
                    same_pkg.add((p, q))
    cross_import_file_edges = {(a, b) for a, b in file_edges_import if own[a]["pkg"] != own[b]["pkg"]}

    by_proj = collections.defaultdict(lambda: collections.Counter())
    for p, f in info.items():
        key = "vendored" if p not in own else f["proj"]
        by_proj[key]["files"] += 1; by_proj[key]["loc"] += f["loc"]; by_proj[key][f["lang"]] += 1
    return dict(
        scope=f"{ANDROID} (*.java, *.kt), tracked files",
        totals=dict(files=len(info), loc=sum(f["loc"] for f in info.values()),
                    first_party_files=len(own), first_party_loc=sum(f["loc"] for f in own.values())),
        vendored={k: dict(files=v["files"], loc=v["loc"], dirs=sorted(v["dirs"])) for k, v in vendored.items()},
        files_by_subproject={k: dict(v) for k, v in sorted(by_proj.items())},
        source_sets={f"{a} {b}": n for (a, b), n in collections.Counter((f["proj"], f["sset"]) for f in own.values()).most_common()},
        gradle=dict(subprojects=subprojects, declared_edges=declared, external_deps=external),
        packages={k: dict(files=len(v), subprojects=pkg_projs[k]) for k, v in sorted(pkg_files.items())},
        package_edges={a: dict(bs) for a, bs in sorted(pkg_edges.items())},
        package_edge_count=sum(len(b) for b in pkg_edges.values()),
        wildcard_imports=wildcard,
        external_import_roots=external_imports.most_common(15),
        fan_in=fin, fan_out=fout,
        sccs=tarjan(known, edges),
        subproject_edges_from_imports={f"{a} -> {b}": n for (a, b), n in proj_edges.most_common()},
        undeclared_subproject_edges=undeclared,
        layering_violations=violations,
        file_level=dict(
            import_file_edges_cross_package=len(cross_import_file_edges),
            heuristic_same_package_file_edges=len(same_pkg),
            note="same-package edges: capitalised identifier in file A matches a class/interface/object/enum "
                 "declared in another file B of the same package (comments/strings stripped). Heuristic; "
                 "misses Kotlin top-level functions/properties and may over-count homonyms."),
    )


# ---------------------------------------------------------------- C#
def csharp():
    projs = {}
    for cp in tracked(MONO, (".csproj",)):
        tree = ET.parse(os.path.join(ROOT, cp)).getroot()
        def props(tag):
            return [e.text.strip() for e in tree.iter(tag) if e.text and e.text.strip()]
        base = os.path.dirname(cp)
        name = os.path.splitext(os.path.basename(cp))[0]
        refs = []
        for e in tree.iter("ProjectReference"):
            tgt = os.path.normpath(os.path.join(base, e.get("Include").replace("\\", "/")))
            refs.append(dict(dst=os.path.splitext(os.path.basename(tgt))[0], path=tgt,
                             analyzer=e.get("OutputItemType") == "Analyzer"))
        projs[name] = dict(
            path=cp, dir=base,
            tfm=props("TargetFramework") + props("TargetFrameworks"),
            output=(props("OutputType") or ["Library"])[0],
            analyzer_rules=bool(props("EnforceExtendedAnalyzerRules") or props("IsRoslynComponent")),
            project_refs=refs,
            assembly_refs=[dict(name=e.get("Include"), hint=(e.findtext("HintPath") or "").strip()) for e in tree.iter("Reference")],
            package_refs=sorted({e.get("Include") for e in tree.iter("PackageReference")}),
            imports=[e.get("Project") for e in tree.iter("Import")],
            explicit_compile_items=len([e for e in tree.iter("Compile") if e.get("Include")]),
        )
    # A project consumed with OutputItemType="Analyzer" is a Roslyn analyzer / source generator.
    for p in projs.values():
        for r in p["project_refs"]:
            if r["analyzer"] and r["dst"] in projs:
                projs[r["dst"]]["consumed_as_analyzer"] = True
    dirs = sorted(((p["dir"], n) for n, p in projs.items()), key=lambda x: -len(x[0]))

    def owner(path):
        for d, n in dirs:
            if path.startswith(d + "/"):
                if n == "Godot.SourceGenerators.Tests" and "/TestData/" in path:
                    return "(fixture: Tests/TestData, not compiled)"
                return n
        if "/script_templates/" in path:
            return "(script template, not compiled)"
        return "(no project)"

    info = {}
    for p in tracked(MONO, (".cs",)):
        src = read(p)
        code = code_only(src)
        usings = []
        for g, s, t in re.findall(r"^\s*(global\s+)?using\s+(static\s+)?([\w.]+)\s*;", code, re.M):
            usings.append(dict(target=t, glob=bool(g), static=bool(s)))
        for g, t in re.findall(r"^\s*(global\s+)?using\s+\w+\s*=\s*([\w.]+)(?:<[^;]*>)?\s*;", code, re.M):
            usings.append(dict(target=t, glob=bool(g), static=True))  # alias target may be a type
        info[p] = dict(
            proj=owner(p), loc=src.count("\n"),
            ns=re.findall(r"^\s*namespace\s+([\w.]+)", code, re.M) or ["(global)"],
            usings=usings,
            types=set(re.findall(r"\b(?:class|struct|interface|enum|record|delegate\s+[\w<>\[\],. ?]+?)\s+([A-Za-z_]\w*)", code)),
            idents=collections.Counter(re.findall(r"\b[A-Z]\w*\b", code)),
        )
    compiled = {p: f for p, f in info.items() if not f["proj"].startswith("(")}
    ns_files = collections.defaultdict(list)
    for p, f in compiled.items():
        for n in f["ns"]:
            ns_files[n].append(p)
    polyfills = {n: sorted({compiled[p]["proj"] for p in ps}) for n, ps in ns_files.items() if n.startswith("System")}
    known = {n for n in ns_files if not n.startswith("System")}
    ns_projs = {n: sorted({compiled[p]["proj"] for p in ps}) for n, ps in ns_files.items()}

    # Global usings apply to every file of their project.
    proj_globals = collections.defaultdict(list)
    for p, f in compiled.items():
        proj_globals[f["proj"]] += [u for u in f["usings"] if u["glob"]]

    ns_edges = collections.defaultdict(collections.Counter)
    proj_use = collections.Counter()
    ext_roots = collections.Counter()
    unresolved = collections.Counter()  # Godot*-prefixed usings that no tracked C# declares
    for p, f in compiled.items():
        targets = [u for u in f["usings"] if not u["glob"]] + proj_globals[f["proj"]]
        for u in targets:
            t = u["target"]
            # `using static A.B.Type;` names a type: resolve to its namespace. Plain `using` must match exactly.
            tn = longest_prefix(t, known) if u["static"] else (t if t in known else None)
            if tn is None:
                ext_roots[t.split(".")[0]] += 1
                if t.startswith("Godot"):
                    unresolved[t] += 1
                continue
            for n in f["ns"]:
                if tn != n:
                    ns_edges[n][tn] += 1
            if f["proj"] not in ns_projs[tn]:
                for dp in ns_projs[tn]:
                    proj_use[(f["proj"], dp, tn)] += 1
    edges = {a: set(bs) for a, bs in ns_edges.items()}
    fin, fout = fan(edges)

    # Reachability over ProjectReference (incl. analyzers, whose generators emit types) + assembly References (GodotSharp*.dll).
    reach_direct = {n: {r["dst"] for r in p["project_refs"]} |
                       {a["name"] for a in p["assembly_refs"]} for n, p in projs.items()}
    def reach(n, seen=None):
        seen = seen if seen is not None else set()
        for m in reach_direct.get(n, ()):
            if m not in seen:
                seen.add(m); reach(m, seen)
        return seen
    undeclared = collections.defaultdict(lambda: collections.Counter())
    for (src, dst, ns), c in proj_use.items():
        if src.startswith("("):
            continue
        # the namespace is fine if ANY project declaring it is reachable
        if not any(d in reach(src) for d in ns_projs[ns]):
            undeclared[f"{src} -> {ns} (declared in {', '.join(ns_projs[ns])})"]["usings"] += c

    # Heuristic: references to the generated Godot API (GodotSharp/Generated, absent from the tree).
    # Generated classes = Object-derived ClassDB classes documented in doc/classes, modules/*/doc_classes and
    # platform/*/doc_classes (the `inherits=` attribute; Variant built-ins like String/Vector2 have none and are
    # hand-written or mapped to BCL types in C#), minus type names hand-written anywhere in the repo's C#.
    # `Object` itself is exposed as `GodotObject`.
    doc_xml = [p for p in tracked("", (".xml",)) if re.match(r"(doc/classes|modules/[^/]+/doc_classes|platform/[^/]+/doc_classes)/", p)]
    classdb = {"GodotObject"} | {os.path.splitext(os.path.basename(p))[0] for p in doc_xml if 'inherits="' in read(p)[:400]}
    hand_written = set().union(*(f["types"] for f in info.values()))
    bcl_homonyms = {"Thread", "Mutex", "Semaphore", "Range", "Timer", "Expression", "Time", "JSON", "Marshal",
                    "Script", "Label", "Button", "Container", "Control", "Window", "Image", "Font", "Path",
                    "Environment", "Directory", "File", "Crypto", "Performance", "Engine"}
    generated = classdb - hand_written
    gen_strict = generated - bcl_homonyms
    gen_by_proj = collections.defaultdict(lambda: dict(files=0, using_generated=0, using_generated_strict=0))
    gen_names = collections.Counter()
    for p, f in compiled.items():
        hits = set(f["idents"]) & generated
        strict = hits & gen_strict
        g = gen_by_proj[f["proj"]]
        g["files"] += 1
        g["using_generated"] += bool(hits)
        g["using_generated_strict"] += bool(strict)
        gen_names.update(strict)

    # Heuristic: implicit edges through enclosing / same namespace (C# resolves these without `using`).
    ns_types = collections.defaultdict(set)
    for p, f in compiled.items():
        for n in f["ns"]:
            ns_types[n] |= f["types"]
    implicit_ns = collections.Counter()
    for p, f in compiled.items():
        for n in f["ns"]:
            parts = n.split(".")
            for i in range(len(parts) - 1, 0, -1):
                parent = ".".join(parts[:i])
                if parent in ns_types and set(f["idents"]) & (ns_types[parent] - f["types"]):
                    implicit_ns[(n, parent)] += 1

    by_proj = collections.defaultdict(collections.Counter)
    for f in info.values():
        by_proj[f["proj"]]["files"] += 1; by_proj[f["proj"]]["loc"] += f["loc"]
    return dict(
        scope=f"{MONO} (*.cs, *.csproj), tracked files; GodotSharp*/Generated is gitignored and absent",
        totals=dict(files=len(info), loc=sum(f["loc"] for f in info.values()),
                    compiled_files=len(compiled), compiled_loc=sum(f["loc"] for f in compiled.values())),
        files_by_project={k: dict(v) for k, v in sorted(by_proj.items())},
        projects=projs,
        namespaces={n: dict(files=len(ps), projects=ns_projs[n]) for n, ps in sorted(ns_files.items())},
        namespace_edges={a: dict(bs) for a, bs in sorted(ns_edges.items())},
        namespace_edge_count=sum(len(b) for b in ns_edges.values()),
        external_using_roots=ext_roots.most_common(15),
        unresolved_godot_usings=dict(unresolved),
        fan_in=fin, fan_out=fout,
        sccs=tarjan(known, edges),
        bcl_polyfill_namespaces=polyfills,
        cross_project_namespace_use={f"{a} -> {b} via {n}": c for (a, b, n), c in sorted(proj_use.items())},
        cross_project_use_without_reference={k: dict(v) for k, v in undeclared.items()},
        generated_api_heuristic=dict(
            classdb_classes=len(classdb), generated_candidates=len(generated),
            per_project={k: v for k, v in sorted(gen_by_proj.items())},
            top_names=gen_names.most_common(20),
            note="file counts as 'using generated API' if a capitalised identifier (comments/strings stripped) matches a "
                 "ClassDB class name that no repo C# file declares; 'strict' drops BCL/common-word homonyms. Heuristic."),
        implicit_namespace_edges_heuristic={f"{a} -> {b}": c for (a, b), c in implicit_ns.most_common()},
    )


result = dict(java_kotlin=java_kotlin(), csharp=csharp())


def default(o):
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


with open(OUT, "w") as f:
    json.dump(result, f, indent=1, default=default)
jk, cs = result["java_kotlin"], result["csharp"]
print("JAVA/KOTLIN", jk["totals"], "vendored", {k: (v["files"], v["loc"]) for k, v in jk["vendored"].items()})
print("  pkgs", len(jk["packages"]), "pkg-edges", jk["package_edge_count"], "SCCs", [len(s) for s in jk["sccs"]])
print("  subproject edges from imports", jk["subproject_edges_from_imports"])
print("  violations", len(jk["layering_violations"]), "undeclared", jk["undeclared_subproject_edges"])
print("C#", cs["totals"], "ns", len(cs["namespaces"]), "ns-edges", cs["namespace_edge_count"], "SCCs", [len(s) for s in cs["sccs"]])
print("  no-ref cross-project", cs["cross_project_use_without_reference"])
