#!/usr/bin/env python3
"""Explain the modules -> editor include count: raw `#include "editor/..."` lines vs. includes that resolve to the top-level editor/.

Run: python3 -I recount_modules_editor.py <repo_root>
A quoted include is resolved relative to the including file first, so `#include "editor/x.h"` in
modules/<m>/register_types.cpp hits modules/<m>/editor/x.h (module-local), not the editor layer.
"""
import os, re, subprocess, sys, collections
root = sys.argv[1]
INC = re.compile(r'^\s*#\s*include\s*"(editor/[^"]+)"')
COND = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)')
files = [p for p in subprocess.run(["git", "-C", root, "ls-files", "modules/"], capture_output=True, text=True).stdout.split("\n")
         if p.endswith((".h", ".cpp", ".hpp", ".mm", ".c", ".m", ".cc"))]
c = collections.Counter(); rows = []
for f in files:
    stack = []
    for ln, line in enumerate(open(os.path.join(root, f), errors="replace"), 1):
        m = COND.match(line)
        if m:
            k, rest = m.group(1), m.group(2).strip()
            if k in ("if", "ifdef", "ifndef"): stack.append(f"{k} {rest}")
            elif k in ("elif", "else") and stack: stack[-1] = f"{k} {rest}"
            elif k == "endif" and stack: stack.pop()
            continue
        m = INC.match(line)
        if not m: continue
        inc = m.group(1)
        local = os.path.normpath(os.path.join(os.path.dirname(f), inc))
        if os.path.exists(os.path.join(root, local)): target = "module-local"
        elif os.path.exists(os.path.join(root, inc)): target = "editor layer"
        else: target = "generated, module-local" if "script_templates" in inc else "unresolved"
        guards = " ".join(s for s in stack if not re.match(r"ifndef \w+_H\b", s))
        where = ("in modules/*/editor/" if "/editor/" in f else
                 "TOOLS_ENABLED" if "TOOLS_ENABLED" in guards else "other guard" if guards else "unguarded")
        c[(target, where)] += 1; rows.append((f, ln, inc, target, where))
print("raw '#include \"editor/' lines in modules:", sum(c.values()))
for k, v in sorted(c.items()): print(f"  {v:4}  {k[0]:24} {k[1]}")
