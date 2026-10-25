#!/usr/bin/env python3
"""GLSL dependency evidence: shader->shader #include graph, C++->shader edges via *.glsl.gen.h,
and the remaining (non-shader) generated-header families. Stdlib only.
Usage: python3 -I glsl.py <repo_root> <out.json>
Resolution mirrors glsl_builders.py / gles3_builders.py: an include is relative to the including
file's directory, except paths starting with "thirdparty/" (repo root). X.glsl -> X.glsl.gen.h
next to the source (SConstruct builders RD_GLSL / GLSL_HEADER / GLES3_GLSL, suffix "glsl.gen.h")."""
import collections, json, os, re, subprocess, sys

root, out_path = sys.argv[1], sys.argv[2]
files = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")
files = [f for f in files if f and not f.startswith("thirdparty/")]
tracked_all = set(subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split("\n"))
glsl = sorted(f for f in files if f.endswith(".glsl"))
cxx = sorted(f for f in files if f.endswith((".h", ".cpp", ".hpp", ".mm", ".c", ".m", ".cc", ".inc")))

DEEP = {("servers", "rendering"), ("editor", "scene"), ("editor", "inspector"), ("scene", "gui")}
def comp(path):  # same component granularity as artifact 2
    d = path.split("/")[:-1]
    if len(d) >= 3 and (d[0], d[1]) in DEEP: return ".".join(d[:3])
    return ".".join(d[:2]) if d else "<root>"
def rank(c):
    return {"core": 0, "drivers": 1, "servers": 2, "scene": 3, "modules": 4, "editor": 5,
            "platform": 6, "main": 7, "tests": 7}.get(c.split(".")[0], 9)
def upward(a, b):
    return rank(b) > rank(a) and not (a.startswith("drivers") and b.startswith("servers"))
def read(p):
    with open(os.path.join(root, p), encoding="utf-8", errors="replace") as fh: return fh.read()

# 1. shader -> shader includes (builders match "#include " anywhere on the line, comments included)
INC = re.compile(r'#include\s+"([^"]+)"')
SECT = re.compile(r'^#\[(\w+)\]', re.M)
g_edges, unresolved, external, commented, sections = collections.defaultdict(set), [], [], [], collections.Counter()
for f in glsl:
    txt = read(f)
    for s in set(SECT.findall(txt)): sections[s] += 1
    for line in txt.split("\n"):
        for m in INC.finditer(line):
            inc = m.group(1)
            tgt = os.path.normpath(inc if inc.startswith("thirdparty/") else os.path.join(os.path.dirname(f), inc))
            if line.lstrip().startswith("//"): commented.append((f, inc))
            if tgt.startswith("thirdparty/"):
                external.append((f, tgt, tgt in tracked_all or os.path.exists(os.path.join(root, tgt))))
            elif tgt in files: g_edges[f].add(tgt)
            else: unresolved.append((f, inc))

fanin = collections.Counter(t for s in g_edges.values() for t in s)
# transitive closure size per entry shader
def closure(f, seen=None):
    seen = set() if seen is None else seen
    for t in g_edges.get(f, ()):
        if t not in seen: seen.add(t); closure(t, seen)
    return seen
# Tarjan SCC on shader graph
idx, low, st, on, sccs, cnt = {}, {}, [], set(), [], [0]
sys.setrecursionlimit(10000)
def strong(v):
    idx[v] = low[v] = cnt[0]; cnt[0] += 1; st.append(v); on.add(v)
    for w in g_edges.get(v, ()):
        if w not in idx: strong(w); low[v] = min(low[v], low[w])
        elif w in on: low[v] = min(low[v], idx[w])
    if low[v] == idx[v]:
        s = []
        while True:
            w = st.pop(); on.discard(w); s.append(w)
            if w == v: break
        if len(s) > 1 or v in g_edges.get(v, ()): sccs.append(sorted(s))
for v in glsl:
    if v not in idx: strong(v)
g_comp = collections.Counter((comp(a), comp(b)) for a, bs in g_edges.items() for b in bs if comp(a) != comp(b))
g_dir = collections.Counter((os.path.dirname(a), os.path.dirname(b)) for a, bs in g_edges.items() for b in bs
                            if os.path.dirname(a) != os.path.dirname(b))

# 2. C++ -> generated headers
GEN = re.compile(r'^\s*#\s*include\s*[<"]([^">]+\.gen\.(?:h|inc|cpp))[">]', re.M)
cx_edges, gen_other, gen_other_files, gen_total, unresolved_gen = [], collections.Counter(), collections.defaultdict(set), 0, []
for f in cxx:
    txt = read(f)
    for inc in GEN.findall(txt):
        gen_total += 1
        if inc.endswith(".glsl.gen.h"):
            cand = [os.path.normpath(inc[:-6]), os.path.normpath(os.path.join(os.path.dirname(f), inc[:-6]))]
            src = next((c for c in cand if c in files), None)
            if src: cx_edges.append((f, src))
            else: unresolved_gen.append((f, inc))
        else:
            key = re.sub(r"^.*/", "", inc) if "/" not in inc else inc
            gen_other[key] += 1; gen_other_files[key].add(f)
cx_comp = collections.Counter((comp(a), comp(b)) for a, b in cx_edges)
cx_files = collections.Counter(b for _, b in cx_edges)

# compare with artifact-2 component graph (were these edges already known from other includes?)
dot_path = os.path.join(root, "context/map/evidence/structure/full.dot")
known = set()
if os.path.exists(dot_path):
    known = set(re.findall(r'"([^"]+)" -> "([^"]+)"', read(dot_path)))
cx_new = {k: v for k, v in cx_comp.items() if k[0] != k[1] and k not in known}

# builder family per shader (from SCsub conventions + explicit calls)
fam = {}
for sc in (f for f in files if f.endswith("SCsub")):
    t = read(sc); d = os.path.dirname(sc)
    for b, name in re.findall(r'\.(RD_GLSL|GLSL_HEADER|GLES3_GLSL)\("([^"]+)"\)', t): fam[os.path.normpath(os.path.join(d, name))] = b
    if re.search(r'for glsl_file in gl_include_files:\s*\n\s*env\.GLSL_HEADER', t):
        for g in glsl:
            if os.path.dirname(g) == d and g.endswith("_inc.glsl"): fam[g] = "GLSL_HEADER"
    for b in ("RD_GLSL", "GLES3_GLSL"):
        if re.search(r'for glsl_file in glsl_files:\s*\n\s*env\.' + b, t):
            for g in glsl:
                if os.path.dirname(g) == d and not g.endswith("_inc.glsl"): fam[g] = b
compiled = set(fam)
not_compiled = [g for g in glsl if g not in compiled and fanin[g] == 0]

out = dict(
    glsl_files=len(glsl), glsl_by_component=collections.Counter(comp(g) for g in glsl).most_common(),
    sections_used=dict(sections), builder_family=collections.Counter(fam.values()),
    shader_include_edges=sum(len(v) for v in g_edges.values()),
    shader_edges=sorted([a, b] for a, bs in g_edges.items() for b in bs),
    unresolved_shader_includes=unresolved, thirdparty_shader_includes=external, commented_includes=commented,
    shader_hubs=fanin.most_common(25), cycles=sccs,
    deepest_closure=sorted(((len(closure(g)), g) for g in glsl), reverse=True)[:10],
    cross_component_shader_edges=[[a, b, n] for (a, b), n in g_comp.most_common()],
    cross_dir_shader_edges=[[a, b, n] for (a, b), n in g_dir.most_common()],
    shader_files_neither_compiled_nor_included=not_compiled,
    cxx_generated_includes_total=gen_total, cxx_to_shader_edges=len(cx_edges),
    cxx_includer_files=len({a for a, _ in cx_edges}), shader_sources_used_by_cxx=len(cx_files),
    shaders_used_by_most_cxx_files=cx_files.most_common(10),
    unresolved_glsl_gen_includes=unresolved_gen,
    cxx_to_shader_component_edges=[[a, b, n, upward(a, b) if a != b else False] for (a, b), n in cx_comp.most_common()],
    cxx_to_shader_component_edges_new_vs_full_dot=[[a, b, n] for (a, b), n in sorted(cx_new.items())],
    shader_component_edges_new_vs_full_dot=[[a, b, n] for (a, b), n in g_comp.items() if (a, b) not in known],
    non_shader_generated=[[k, n, len(gen_other_files[k]), sorted({comp(x) for x in gen_other_files[k]})]
                          for k, n in gen_other.most_common()],
    non_shader_generated_includes=sum(gen_other.values()),
)
# where a non-shader generated header has a repo-root path, its owning component is known even though
# the file is absent in an unbuilt tree: list the component edges this implies that full.dot lacks
ng = collections.Counter()
for k, fs in gen_other_files.items():
    if "/" in k and k.split("/")[0] in ("core", "drivers", "servers", "scene", "modules", "editor", "platform", "main", "tests"):
        for f in fs:
            if comp(f) != comp(k): ng[(comp(f), comp(k), k)] += 1
out["non_shader_generated_component_edges"] = [[a, b, h, n, (a, b) in known, upward(a, b)] for (a, b, h), n in sorted(ng.items())]
out["non_shader_generated_upward_unknown_to_full_dot"] = sorted({(a, b, h) for (a, b, h) in ng if upward(a, b) and (a, b) not in known})
json.dump(out, open(out_path, "w"), indent=1)
for k in ("glsl_files", "glsl_by_component", "sections_used", "builder_family", "shader_include_edges",
          "unresolved_shader_includes", "commented_includes", "cycles", "shader_hubs", "deepest_closure",
          "cross_component_shader_edges", "shader_files_neither_compiled_nor_included",
          "cxx_generated_includes_total", "cxx_to_shader_edges", "cxx_includer_files", "shader_sources_used_by_cxx",
          "shaders_used_by_most_cxx_files", "unresolved_glsl_gen_includes", "cxx_to_shader_component_edges",
          "cxx_to_shader_component_edges_new_vs_full_dot", "shader_component_edges_new_vs_full_dot",
          "non_shader_generated_includes", "non_shader_generated_upward_unknown_to_full_dot"):
    print(k, "=", json.dumps(out[k])[:900])
print("thirdparty_shader_includes =", len(external), sorted({t for _, t, _ in external})[:6], "all exist:", all(e for *_, e in external))
print("non_shader_generated (", len(out["non_shader_generated"]), "families ) top:")
for r in out["non_shader_generated"][:45]: print("  ", r)
