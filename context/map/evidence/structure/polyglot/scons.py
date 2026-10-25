#!/usr/bin/env python3
"""Static SCons build graph for Godot: SConscript tree, module deps, per-file build conditions,
SCons-level classification of upward includes, code generators, build-script import graph.
Usage: python3 -I scons.py <repo_root> <out.json>   (stdlib only; nothing is executed)"""
import ast, collections, json, os, re, subprocess, sys

root, out_path = sys.argv[1], sys.argv[2]
tracked = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split("\n")
tracked = [f for f in tracked if f]
fileset = set(tracked)
own = [f for f in tracked if not f.startswith("thirdparty/")]
SRC_EXT = (".cpp", ".c", ".mm", ".m", ".cc")
CODE_EXT = SRC_EXT + (".h", ".hpp", ".inc")
scripts = sorted(f for f in own if os.path.basename(f) in ("SCsub", "SConstruct"))
modules = sorted({f.split("/")[1] for f in own if re.match(r"modules/[^/]+/config\.py$", f)})
platforms = sorted({f.split("/")[1] for f in own if re.match(r"platform/[^/]+/detect\.py$", f)})


def parse(path):
    return ast.parse(open(os.path.join(root, path), encoding="utf-8").read(), path)


def norm(base_dir, p):
    p = p[1:] if p.startswith("#") else os.path.join(base_dir, p)
    return os.path.normpath(p).replace("\\", "/")


def pat_re(p):  # SCons Glob semantics: '*' does not cross '/'; '**/' (python glob recursive) does
    parts = p.split("**/")
    conv = lambda q: "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in q)
    return re.compile("^" + "(?:.*/)?".join(conv(q) for q in parts) + "$")


# ---------------------------------------------------------------- 1. SCsub walker (conditions, sources, children, generators)
class Walker:
    SRC_CALLS = {"add_source_files", "add_program", "add_library", "add_shared_library", "Library", "SharedLibrary",
                 "StaticLibrary", "Program", "Object", "SharedObject", "Glob"}

    def __init__(self, path):
        self.path, self.dir = path, os.path.dirname(path)
        self.vars = {}  # name -> list[(pattern, conds)]
        self.sources, self.children, self.gens, self.thirdparty, self.unresolved = [], [], [], set(), []
        self.loopvars = set()
        self.walk(parse(path).body, [])

    def ev(self, n, conds):
        """Evaluate expression to list of (string, conds); unknown parts of strings become '*'."""
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return [(n.value, conds)]
        if isinstance(n, (ast.List, ast.Tuple)):
            return [x for e in n.elts for x in self.ev(e, conds)]
        if isinstance(n, ast.Name):
            if n.id in self.vars:
                return self.vars[n.id]
            return [("*", conds)] if n.id in self.loopvars else []
        if isinstance(n, ast.JoinedStr):
            s = "".join(v.value if isinstance(v, ast.Constant) else "*" for v in n.values)
            return [(s, conds)]
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            l, r = self.ev(n.left, conds), self.ev(n.right, conds)
            str_like = lambda e: isinstance(e, (ast.Constant, ast.JoinedStr, ast.Subscript)) or (
                isinstance(e, ast.Name) and e.id in self.loopvars)
            if str_like(n.left) or str_like(n.right):  # string concatenation
                ls = [s for s, _ in l] or ["*"]; rs = [s for s, _ in r] or ["*"]
                return [(a + b, conds) for a in ls for b in rs]
            return l + r
        if isinstance(n, ast.Subscript):
            return [("*", conds)]
        if isinstance(n, ast.Call):
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if fn in ("Glob", "glob", "File") and n.args:
                return self.ev(n.args[0], conds)
            if fn == "SConscript" and n.args:
                return self.child(n, conds)
        return []

    def child(self, call, conds):
        for s, _ in self.ev(call.args[0], conds):
            self.children.append(dict(path=norm(self.dir, s), conds=list(conds)))
        return [("@returned:" + norm(self.dir, s), conds) for s, _ in self.ev(call.args[0], conds)]

    def walk(self, body, conds):
        for st in body:
            if isinstance(st, ast.If):
                c = ast.unparse(st.test)
                self.walk(st.body, conds + [c])
                self.walk(st.orelse, conds + [f"not ({c})"])
            elif isinstance(st, (ast.For, ast.While)):
                if isinstance(st, ast.For):
                    vals = self.ev(st.iter, conds) if isinstance(st.target, ast.Name) else []
                    if vals and all(v != "*" for v, _ in vals):
                        self.vars[st.target.id] = vals  # loop over a known list: bind every element
                    else:
                        for t in ast.walk(st.target):
                            if isinstance(t, ast.Name): self.loopvars.add(t.id)
                    it = ast.unparse(st.iter)
                    self.walk(st.body, conds + [f"for-each {it}"])
                else:
                    self.walk(st.body, conds)
            elif isinstance(st, (ast.With, ast.Try)):
                self.walk(st.body, conds)
                for h in getattr(st, "handlers", []): self.walk(h.body, conds)
            elif isinstance(st, ast.FunctionDef):
                self.walk(st.body, conds + [f"def {st.name}"])
            elif isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                self.vars[st.targets[0].id] = self.ev(st.value, conds)
                self.scan_calls(st.value, conds)
            elif isinstance(st, ast.AugAssign) and isinstance(st.target, ast.Name):
                self.vars.setdefault(st.target.id, []).extend(self.ev(st.value, conds))
                self.scan_calls(st.value, conds)
            elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
                c = st.value; fn = c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
                if fn in ("append", "extend") and isinstance(c.func.value, ast.Name) and c.args:
                    self.vars.setdefault(c.func.value.id, []).extend(self.ev(c.args[0], conds))
                elif fn == "Return" and c.args:
                    for s, _ in self.ev(c.args[0], conds):
                        for p, pc in self.vars.get(s, []): self.add_src(p, pc)
                self.scan_calls(c, conds)
            else:
                for n in ast.iter_child_nodes(st):
                    if isinstance(n, ast.expr): self.scan_calls(n, conds)

    def add_src(self, p, conds):
        if p.startswith("@returned:"):
            return  # sources returned by a child SCsub are registered by the child itself
        if p.endswith(SRC_EXT) or (p.endswith(".gen.cpp")):
            self.sources.append(dict(pattern=norm(self.dir, p), conds=list(conds)))

    def scan_calls(self, node, conds):
        for c in ast.walk(node):
            if not isinstance(c, ast.Call): continue
            fn = c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
            seg = ast.unparse(c)
            for m in re.findall(r"#?thirdparty/([A-Za-z0-9_.+-]+)", seg): self.thirdparty.add(m)
            if fn == "SConscript" and c.args and c not in getattr(self, "_seen", set()):
                self._seen = getattr(self, "_seen", set()) | {c}
                self.child(c, conds)
            elif fn in self.SRC_CALLS:
                args = c.args[1:] if fn == "add_source_files" else c.args
                vals = [v for a in args for v in self.ev(a, conds)]
                if fn == "add_source_files" and not vals and args:
                    self.unresolved.append(dict(call=seg[:160], conds=list(conds)))
                for p, pc in vals: self.add_src(p, pc)
            elif fn in ("CommandNoCache", "Command") and c.args:
                tgt = [s for s, _ in self.ev(c.args[0], conds)] or [ast.unparse(c.args[0])]
                runner = [ast.unparse(a.args[0]) for a in ast.walk(c) if isinstance(a, ast.Call)
                          and getattr(a.func, "attr", "") == "Run" and a.args]
                self.gens.append(dict(targets=[norm(self.dir, t) for t in tgt], builder=(runner or ["?"])[0],
                                      conds=list(conds)))
            elif fn in ("GLSL_HEADER", "RD_GLSL", "GLES3_GLSL") and c.args:
                for s, _ in self.ev(c.args[0], conds):
                    self.gens.append(dict(targets=[norm(self.dir, s) + ".gen.h"], builder=f"glsl_builders/{fn}",
                                          conds=list(conds)))
        for m in re.findall(r"#thirdparty/([A-Za-z0-9_.+-]+)", ast.unparse(node)): self.thirdparty.add(m)
        for s in [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]:
            m = re.match(r"#?thirdparty/([A-Za-z0-9_.+-]+)", s)
            if m: self.thirdparty.add(m.group(1))


walked = {s: Walker(s) for s in scripts}

# ---------------------------------------------------------------- build tree with inherited conditions
can_build, deps_decl, can_build_raw = {}, [], {}
for m in modules:
    cfg = f"modules/{m}/config.py"; src = open(os.path.join(root, cfg), encoding="utf-8").read(); t = ast.parse(src)
    for fn in t.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == "can_build":
            rets = [ast.unparse(r.value) for r in ast.walk(fn) if isinstance(r, ast.Return) and r.value is not None]
            true_rets = [r for r in rets if r != "False"]
            can_build_raw[m] = rets
            editor_only = bool(true_rets) and all("editor_build" in r and " or " not in r for r in true_rets)
            restrict = sorted({k for r in true_rets for k in re.findall(r"env\[[\"'](\w+)[\"']\]|platform ==|env\.(\w+)", r)
                               for k in k if k})
            plat = sorted(set(re.findall(r"platform == [\"'](\w+)[\"']", ast.get_source_segment(src, fn) or "")))
            can_build[m] = dict(editor_only=editor_only, always=true_rets == ["True"] and "False" not in rets,
                                flags=restrict, platforms=plat)
            for c in ast.walk(fn):
                if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "module_add_dependencies":
                    a = c.args; opt = bool(len(a) > 2 and getattr(a[2], "value", False)) or any(
                        k.arg == "optional" and getattr(k.value, "value", False) for k in c.keywords)
                    deps_decl.append(dict(declared_for=a[0].value, module=m, deps=[e.value for e in a[1].elts],
                                          optional=opt))

chain = {}  # script -> list of inherited cond lists (one per path reaching it)


def visit(script, conds):
    if script not in walked or any(conds == c for c in chain.get(script, [])) or len(chain.get(script, [])) > 4:
        return
    chain.setdefault(script, []).append(conds)
    for ch in walked[script].children:
        visit(ch["path"], conds + ch["conds"])


visit("SConstruct", [])
for m in modules:  # modules/SCsub: for name, path in env.module_list.items(): SConscript(base_path + "/SCsub")
    extra = [f"module_{m}_enabled"] + (["can_build: editor_build"] if can_build.get(m, {}).get("editor_only") else []) + (
        [] if can_build.get(m, {}).get("always", True) else [f"can_build({m})"]) + (
        [f'env["platform"] in {can_build[m]["platforms"]}'] if can_build.get(m, {}).get("platforms") else [])
    for c in chain.get("modules/SCsub", [[]]):
        visit(f"modules/{m}/SCsub", c + extra)
for p in platforms:  # SConstruct: SConscript("platform/" + env["platform"] + "/SCsub")
    visit(f"platform/{p}/SCsub", [f'env["platform"] == "{p}"'])
unreached = [s for s in scripts if s not in chain]


def tags(conds):
    t = set()
    for c in conds:
        c = c.replace("'", '"')
        neg = c.startswith("not (")
        if re.search(r"editor_build|\[\"target\"\] == \"editor\"", c): t.add("!editor" if neg else "editor")
        if re.search(r"env\[\"tests\"\]", c): t.add("!tests" if neg else "tests")
        if "dev_build" in c and not neg: t.add("dev")
        if "platform_exporters" in c: t.add("editor")
        if re.search(r"platform\"?\]? ?(==|in)|platform ==|env\[\"platform\"\]", c): t.add("platform")
        if re.search(r"module_\w+_enabled|can_build|in env\.module_list", c): t.add("module-flag")
        if re.fullmatch(r'not \(?not env\["disable_\w+"\]\)?', c): continue
        if re.fullmatch(r'not env\["disable_\w+"\]', c): t.add("default-on"); continue
        if re.search(r"env\[\"(vulkan|d3d12|metal|opengl3|rendering_device|use_sowrap|x11|wayland|disable_\w+|builtin_\w+|\w+)\"\]", c) \
                and not re.search(r"env\[\"(tests|platform|target)\"\]", c): t.add("feature")
    return t


# ---------------------------------------------------------------- per-file build condition
rules = []  # (regex, script, conds)
for s, w in walked.items():
    for inherited in chain.get(s, []):  # unreached SCsubs compile nothing
        for src in w.sources:
            rules.append((pat_re(src["pattern"]), src["pattern"], s, inherited + src["conds"]))
file_cond = {}
for f in own:
    if not f.endswith(SRC_EXT): continue
    hits = [(p, s, c) for rx, p, s, c in rules if rx.match(f)]
    if hits: file_cond[f] = hits


def verdict_tu(f):
    """Least-restrictive build class of a translation unit."""
    if f not in file_cond: return "not-in-scons"
    classes = []
    for _, _, c in file_cond[f]:
        t = tags(c)
        classes.append("editor-only" if "editor" in t else "tests-only" if "tests" in t else "dev-only" if "dev" in t
                       else "conditional" if t & {"platform", "feature", "!editor"}
                       else "module-gated" if t & {"module-flag", "default-on"} else "always")
    for k in ("always", "module-gated", "conditional", "dev-only", "tests-only", "editor-only"):
        if k in classes: return k


tu_class = {f: verdict_tu(f) for f in own if f.endswith(SRC_EXT)}

# ---------------------------------------------------------------- include graph with guards (same guard logic as upward.py)
INC = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
COND = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)")


def guard_kind(stack):
    for s in stack:
        if re.search(r"ifndef TOOLS_ENABLED|!\s*defined\s*\(?\s*TOOLS_ENABLED|after ifdef TOOLS_ENABLED|after if.*\bTOOLS_ENABLED", s):
            continue
        if "TOOLS_ENABLED" in s and not s.startswith("else"): return "editor"
        if "TESTS_ENABLED" in s and not s.startswith(("else", "ifndef")): return "tests"
    return ""


includes = collections.defaultdict(list)  # file -> [(line, target, stack)]
for f in own:
    if not f.endswith(CODE_EXT): continue
    stack = []
    for ln, line in enumerate(open(os.path.join(root, f), errors="replace"), 1):
        m = COND.match(line)
        if m:
            k, rest = m.group(1), m.group(2).strip()
            if k in ("if", "ifdef", "ifndef"): stack.append(f"{k} {rest}")
            elif k in ("elif", "else") and stack: stack[-1] = f"{k} {rest} (after {stack[-1]})"
            elif k == "endif" and stack: stack.pop()
            continue
        m = INC.match(line)
        if not m: continue
        inc = m.group(1)
        tgt = inc if inc in fileset else os.path.normpath(os.path.join(os.path.dirname(f), inc))
        guards = [s for s in stack if not re.match(r"ifndef \w+_H\b", s)]
        includes[f].append((ln, tgt if tgt in fileset else inc, guards))

# headers reachable from template-build TUs (non-editor, non-tests) through includes that are not TOOLS/TESTS-guarded
reach = set(); todo = [f for f, k in tu_class.items() if k in ("always", "module-gated", "conditional", "dev-only")]
while todo:
    f = todo.pop()
    if f in reach: continue
    reach.add(f)
    for _, t, g in includes.get(f, []):
        if t in fileset and t not in reach and guard_kind(g) == "": todo.append(t)

# ---------------------------------------------------------------- 3. upward includes, all lower layers incl. modules
RANK = {"core": 0, "drivers": 1, "servers": 2, "scene": 3, "modules": 4, "editor": 5, "platform": 6, "main": 7, "tests": 7}
upward = []
for f, incs in includes.items():
    top = f.split("/")[0]
    for ln, t, g in incs:
        if t not in fileset: continue
        tt = t.split("/")[0]
        if not (RANK.get(tt, 9) > RANK.get(top, 9) and top in ("core", "drivers", "servers", "scene", "modules")): continue
        if top == "drivers" and tt == "servers": continue
        if top == "modules" and tt == "modules": continue
        gs = " ".join(g)
        cat = ("TOOLS_ENABLED" if "TOOLS_ENABLED" in gs else "DEBUG/TESTS" if re.search(r"DEBUG_ENABLED|TESTS_ENABLED|DEV_ENABLED", gs)
               else "platform/feature guard" if gs else "UNGUARDED")
        if f.endswith(SRC_EXT):
            scons = tu_class[f]
        else:
            scons = "header reachable in template builds" if f in reach else "header only reachable from editor/tests TUs"
        final = ("preprocessor: TOOLS_ENABLED" if cat == "TOOLS_ENABLED" else "preprocessor: debug/tests" if cat == "DEBUG/TESTS"
                 else "SCons: editor-only" if scons == "editor-only" else "SCons: tests-only" if scons == "tests-only"
                 else "SCons: header only in editor/tests TUs" if scons.startswith("header only")
                 else "compiled in template builds" if scons in ("always", "module-gated", "header reachable in template builds")
                 else "compiled when flag/platform set" if scons == "conditional" else scons)
        upward.append(dict(src=f, line=ln, inc=t, guards=g, cat=cat, scons=scons, verdict=final))

# ---------------------------------------------------------------- 2. declared vs. include-based module dependencies
mod_of = lambda f: f.split("/")[1] if f.startswith("modules/") and f.count("/") >= 2 else None
inc_edges = collections.defaultdict(lambda: collections.Counter())
for f, incs in includes.items():
    a = mod_of(f)
    if not a: continue
    for ln, t, g in incs:
        b = mod_of(t) if t in fileset else None
        if b and b != a:
            inc_edges[(a, b)][guard_kind(g) or ("guarded" if g else "unguarded")] += 1
# thirdparty libraries compiled by a module vs. referenced by another module's SCsub
tp_owner = collections.defaultdict(set)  # thirdparty lib -> owner (module name or SCsub dir) that compiles it
for sc in scripts:
    txt = open(os.path.join(root, sc), encoding="utf-8").read()
    owner = sc.split("/")[1] if sc.startswith("modules/") else os.path.dirname(sc)
    for lib in re.findall(r'thirdparty_\w*dir\w*\s*=\s*f?"#thirdparty/([A-Za-z0-9_.+-]+)', txt): tp_owner[lib].add(owner)
tp_edges = []
for m in modules:
    w = walked.get(f"modules/{m}/SCsub")
    for lib in sorted(w.thirdparty if w else []):
        for o in sorted(tp_owner.get(lib, ())):
            if o != m and m not in tp_owner[lib]: tp_edges.append(dict(module=m, uses_thirdparty=lib, compiled_by=o))
declared = {(d["module"], x): d["optional"] for d in deps_decl for x in d["deps"]}
declared_key_mismatch = [d for d in deps_decl if d["declared_for"] != d["module"]]
compare = []
for (a, b), cnt in sorted(inc_edges.items()):
    compare.append(dict(src=a, dst=b, includes=dict(cnt), declared=("optional" if declared.get((a, b)) else "required")
                        if (a, b) in declared else "UNDECLARED"))
declared_unused = [dict(src=a, dst=b, optional=o) for (a, b), o in declared.items() if (a, b) not in inc_edges]

# ---------------------------------------------------------------- 4. generators
gens = [dict(script=s, **g) for s, w in walked.items() for g in w.gens]
gen_includes = collections.Counter()
for f, incs in includes.items():
    for _, t, _ in incs:
        if ".gen." in t: gen_includes[t] += 1
gen_targets = {os.path.basename(t): g["builder"] for g in gens for t in g["targets"]}
gen_family = collections.Counter(); gen_unmatched = collections.Counter()
for t, n in gen_includes.items():
    b = gen_targets.get(os.path.basename(t))
    if b is None and t.endswith(".glsl.gen.h"): b = "glsl_builders (GLSL family)"
    if b is None and re.search(r"_svg\.gen\.h$", t): b = "platform_builders.export_icon_builder"
    (gen_family if b else gen_unmatched)[b or t] += n
builder_files = sorted(f for f in own if re.search(r"(_builders|methods|platform_methods|scu_builders)\.py$", f))
builder_funcs = {}
for f in builder_files:
    builder_funcs[f] = [n.name for n in parse(f).body if isinstance(n, ast.FunctionDef)]

# ---------------------------------------------------------------- 5. python import graph among build scripts
pyfiles = sorted(f for f in own if f.endswith(".py") or os.path.basename(f) in ("SCsub", "SConstruct"))
local_mods = {}
for f in own:
    if f.endswith(".py"):
        local_mods[f[:-3].replace("/", ".")] = f; local_mods.setdefault(os.path.basename(f)[:-3], f)
imp = collections.defaultdict(set)
for f in pyfiles:
    try: t = parse(f)
    except SyntaxError: continue
    for n in ast.walk(t):
        names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module] if isinstance(n, ast.ImportFrom) and n.module else []
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_helper_module" and n.args:
            names.append(n.args[0].value)
        for nm in names:
            if nm in local_mods and local_mods[nm] != f: imp[f].add(local_mods[nm])
py_fanin = collections.Counter(t for v in imp.values() for t in v)

out = dict(
    counts=dict(scripts=len(scripts), modules=len(modules), platforms=platforms, reached=len(chain), unreached=unreached,
                source_rules=len(rules), tus_classified=collections.Counter(tu_class.values())),
    tree={s: dict(inherited=chain.get(s), children=w.children, thirdparty=sorted(w.thirdparty),
                  unresolved_sources=w.unresolved) for s, w in walked.items()},
    can_build=can_build, can_build_returns=can_build_raw, declared_deps=deps_decl, declared_key_mismatch=declared_key_mismatch,
    module_include_edges=compare, declared_without_includes=declared_unused, thirdparty_cross_module=tp_edges,
    upward=upward, generators=gens, generated_includes_by_builder=gen_family.most_common(),
    generated_includes_unmatched=gen_unmatched.most_common(), builder_functions=builder_funcs,
    py_imports={k: sorted(v) for k, v in sorted(imp.items())}, py_fanin=py_fanin.most_common(),
    tu_class=tu_class,
)
json.dump(out, open(out_path, "w"), indent=1, default=list)

# ---------------------------------------------------------------- condensed stdout
print("scripts", len(scripts), "reached", len(chain), "unreached", unreached)
print("TU classes", dict(collections.Counter(tu_class.values())))
print("not-in-scons (own, non-thirdparty):", sum(1 for k in tu_class.values() if k == "not-in-scons"))
v = collections.Counter((u["src"].split("/")[0], u["inc"].split("/")[0], u["cat"], u["verdict"]) for u in upward)
for k, n in sorted(v.items()): print(f"{n:4} {k}")
print("--- UNGUARDED upward includes and SCons verdict")
for u in upward:
    if u["cat"] == "UNGUARDED": print(f'  {u["verdict"]:<45} {u["src"]}:{u["line"]} -> {u["inc"]}')
print("--- module include edges"); [print(" ", c) for c in compare]
print("--- declared without include edge", declared_unused)
print("--- key mismatch", declared_key_mismatch)
print("--- thirdparty cross-module", tp_edges)
print("--- generated includes by builder", gen_family.most_common(25))
print("--- unmatched generated includes", gen_unmatched.most_common(25))
print("--- py fan-in", py_fanin.most_common(15))
