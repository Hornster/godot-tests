#!/usr/bin/env python3
"""File-level upward includes with the preprocessor guard they sit under; plus header fan-in."""
import os, re, sys, json, collections
root = sys.argv[1]
RANK = {"core": 0, "drivers": 1, "servers": 2, "scene": 3, "modules": 4, "editor": 5, "platform": 6, "main": 7, "tests": 7}
INC = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
COND = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)')
files = []
for d, _, fs in os.walk(root):
    for f in fs:
        if f.endswith((".h", ".cpp", ".hpp", ".mm", ".c", ".m", ".cc")):
            files.append(os.path.relpath(os.path.join(d, f), root))
fileset = set(files)
fanin = collections.Counter(); fanin_layers = collections.defaultdict(set)
upward = []
for f in files:
    top = f.split("/")[0]; stack = []
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
        if tgt not in fileset: continue
        if tgt != f: fanin[tgt] += 1; fanin_layers[tgt].add(top)
        ttop = tgt.split("/")[0]
        if RANK.get(ttop, 9) > RANK.get(top, 9) and top in ("core", "servers", "scene", "drivers"):
            guards = [s for s in stack if not re.match(r"ifndef \w+_H\b", s)]
            upward.append(dict(src=f, line=ln, inc=tgt, guards=guards))
g = collections.Counter()
for u in upward:
    gs = " ".join(u["guards"])
    cat = ("TOOLS_ENABLED" if "TOOLS_ENABLED" in gs else
           "DEBUG/TESTS" if re.search(r"DEBUG_ENABLED|TESTS_ENABLED|DEV_ENABLED", gs) else
           "platform/feature guard" if gs else "UNGUARDED")
    u["cat"] = cat; g[(u["src"].split("/")[0], u["inc"].split("/")[0], cat)] += 1
json.dump(dict(upward=upward, fanin=[(k, v, sorted(fanin_layers[k])) for k, v in fanin.most_common(40)]),
          open(sys.argv[2], "w"), indent=1)
for k, v in sorted(g.items()): print(v, k)
print("--- UNGUARDED")
for u in upward:
    if u["cat"] == "UNGUARDED": print(f'  {u["src"]}:{u["line"]} -> {u["inc"]}')
print("--- TOP HEADER FAN-IN")
for k, v in fanin.most_common(30): print(f"  {v:5} {k}  {sorted(fanin_layers[k])}")
