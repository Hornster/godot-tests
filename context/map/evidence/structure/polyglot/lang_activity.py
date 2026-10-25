import subprocess, re, collections, sys
repo = sys.argv[1]
out = subprocess.run(["git","-C",repo,"log","--no-merges","--since=2026-04-22","--until=2026-10-23","--numstat","--no-renames","--format=@@%h%x09%an%x09%s"],capture_output=True,text=True).stdout
NOISE_SUBJ = re.compile(r"^(Style:|CI:)|Update to |Sync translations|clang-(format|tidy)", re.I)
def lang(p):
    if p.startswith("thirdparty/") or "/com/android/apksig/" in p or ".gen." in p: return None
    b = p.rsplit("/",1)[-1]
    if b in ("SCsub","SConstruct") or p.endswith(".py"): return "Python/SCons"
    ext = b.rsplit(".",1)[-1] if "." in b else ""
    return {"h":"C/C++/ObjC","cpp":"C/C++/ObjC","c":"C/C++/ObjC","mm":"C/C++/ObjC","inc":"C/C++/ObjC","m":"C/C++/ObjC",
            "cs":"C#","java":"Java/Kotlin","kt":"Java/Kotlin","glsl":"GLSL","js":"JavaScript","swift":"Swift","gd":"GDScript"}.get(ext)
commits = collections.Counter(); churn = collections.Counter(); authors = collections.defaultdict(set); fixes = collections.Counter()
total = 0
for block in out.split("@@")[1:]:
    head, *rows = block.strip("\n").split("\n")
    h, an, subj = (head.split("\t") + ["",""])[:3]
    if NOISE_SUBJ.search(subj): continue
    total += 1
    seen = set()
    for r in rows:
        parts = r.split("\t")
        if len(parts) != 3: continue
        a, d, p = parts; l = lang(p)
        if not l: continue
        seen.add(l)
        if a != "-": churn[l] += int(a) + int(d)
    for l in seen:
        commits[l] += 1; authors[l].add(an)
        if re.search(r"\bfix", subj, re.I): fixes[l] += 1
print(f"commits considered: {total}")
print(f"{'language':14} {'commits':>7} {'share':>6} {'authors':>7} {'fix-commits':>11} {'churn':>8}")
for l, c in commits.most_common():
    print(f"{l:14} {c:7} {c/total:6.1%} {len(authors[l]):7} {fixes[l]:11} {churn[l]:8}")
