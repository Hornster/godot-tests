#!/usr/bin/env python3
"""Analyze cpp-dependencies component graph: SCCs, layer violations, fan-in/out."""
import re, sys, collections, json
dot = open(sys.argv[1]).read()
edges = collections.defaultdict(set); kind = {}
nodes = set(re.findall(r'^\s*"([^"]+)" \[shape', dot, re.M))
for a, b, attrs in re.findall(r'"([^"]+)" -> "([^"]+)"(?: \[([^\]]*)\])?', dot):
    edges[a].add(b); nodes |= {a, b}; kind[(a, b)] = attrs
# Tarjan SCC
idx = {}; low = {}; st = []; on = set(); sccs = []; c = [0]
sys.setrecursionlimit(10000)
def strong(v):
    idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on.add(v)
    for w in edges[v]:
        if w not in idx: strong(w); low[v] = min(low[v], low[w])
        elif w in on: low[v] = min(low[v], idx[w])
    if low[v] == idx[v]:
        s = []
        while True:
            w = st.pop(); on.discard(w); s.append(w)
            if w == v: break
        sccs.append(s)
for v in sorted(nodes):
    if v not in idx: strong(v)
big = [s for s in sccs if len(s) > 1]
# Intended layering (lower number = lower layer). Edges to a higher rank are "upward".
def rank(n):
    t = n.split(".")
    if t[0] == "core": return 0
    if t[0] == "drivers": return 1
    if t[0] == "servers": return 2
    if t[0] == "scene": return 3
    if t[0] == "modules": return 4
    if t[0] == "editor": return 5
    if t[0] == "platform": return 6
    if t[0] in ("main", "tests"): return 7
    return 9
up = collections.defaultdict(list)
for a in edges:
    for b in edges[a]:
        if rank(b) > rank(a) and not (a.split(".")[0] == "drivers" and b.startswith("servers")):
            up[(a.split(".")[0], b.split(".")[0])].append((a, b))
fanin = collections.Counter(); fanout = {a: len(bs) for a, bs in edges.items()}
for a in edges:
    for b in edges[a]: fanin[b] += 1
out = dict(nodes=len(nodes), edges=sum(len(v) for v in edges.values()),
           sccs=[sorted(s) for s in sorted(big, key=len, reverse=True)],
           acyclic=sorted(n for s in sccs if len(s) == 1 for n in s),
           upward={f"{k[0]}->{k[1]}": sorted(v) for k, v in sorted(up.items())},
           fanin=fanin.most_common(25), fanout=sorted(fanout.items(), key=lambda x: -x[1])[:25])
json.dump(out, open(sys.argv[2], "w"), indent=1)
print("nodes", out["nodes"], "edges", out["edges"])
for s in out["sccs"]: print("SCC", len(s), s if len(s) < 12 else s[:12] + ["..."])
print("UPWARD"); [print(f"  {k}: {len(v)}  {v[:8]}") for k, v in out["upward"].items()]
print("FANIN", out["fanin"]); print("FANOUT", out["fanout"])
