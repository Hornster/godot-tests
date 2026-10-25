#!/usr/bin/env python3
"""Territory analysis: classify commits in a window and rank areas / co-change."""
import collections, itertools, json, re, subprocess, sys

SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-04-22"
OUT = sys.argv[2] if len(sys.argv) > 2 else "territory.json"
SEP = "\x1e"

raw = subprocess.run(
    ["git", "log", "--no-merges", f"--since={SINCE}", "--numstat", "--no-renames",
     f"--format={SEP}%h\x1f%an\x1f%ae\x1f%cI\x1f%s\x1f%b\x1f"],
    capture_output=True, text=True, check=True).stdout

BOT_AUTHOR = re.compile(r"\[bot\]|dependabot|renovate|github-actions|weblate", re.I)
AGENT = re.compile(r"co-authored-by:.*(claude|copilot|anthropic|openai|cursor|codex|gemini|devin|aider)"
                   r"|generated (with|by) (claude|copilot|chatgpt|cursor|codex|ai)"
                   r"|assisted-by:|\bclaude code\b|copilot-swe-agent", re.I)
TRANSLATION_MSG = re.compile(r"sync translations|weblate", re.I)
THIRDPARTY_MSG = re.compile(r"^(thirdparty|[\w .+-]+): (update|sync|upgrade)\b.*\bto\b|update thirdparty|updated to ", re.I)
STYLE_MSG = re.compile(r"^(style|clang-format|format)\b|apply .*(rules|clang)|^codespell|typo", re.I)
MECHANICAL_MSG = re.compile(r"\b(rename|move|split|remove redundant|replace|change .* prefixes|trim|apply)\b", re.I)
HOUSEKEEPING_MSG = re.compile(r"update authors|donors|changelog|bump version|^ci\b", re.I)

def noise_path(p):
    """Paths that are vendored, generated, translations or lock/validation data."""
    return (p.startswith("thirdparty/")
            or p.endswith((".po", ".pot", ".lock"))
            or "/translations/" in p or p.startswith(("editor/translations", "doc/translations"))
            or p.startswith("misc/extension_api_validation/")
            or ".gen." in p or p.endswith(("_gen.h", ".glsl.gen.h"))
            or p in ("AUTHORS.md", "DONORS.md", "CHANGELOG.md"))

def doc_path(p):
    return p.startswith("doc/classes/") or re.match(r"modules/[^/]+/doc_classes/", p) is not None

def area(p, depth=2):
    parts = p.split("/")
    if parts[0] in ("modules", "platform", "drivers", "servers", "scene", "editor", "core", "tests", "main", "misc", "doc"):
        # three levels for very large trees
        if parts[0] in ("editor", "servers", "scene") and len(parts) > 3 and parts[1] in ("rendering", "gui", "3d", "2d", "plugins", "scene", "inspector", "docks", "export", "gui"):
            return "/".join(parts[:3]) if depth >= 3 else "/".join(parts[:2])
        return "/".join(parts[:2]) if len(parts) > 2 else parts[0] + "/(root)"
    return "(root)/" + parts[0] if len(parts) > 1 else "(root)"

def layer(p):
    top = p.split("/")[0]
    if p.startswith("core/extension/") or p.startswith("misc/extension_api_validation/"):
        return "API: GDExtension interface"
    if doc_path(p):
        return "API: class reference docs"
    if top == "modules":
        m = p.split("/")[1] if "/" in p else ""
        if m in ("gdscript", "mono", "jsonrpc"):
            return "Module: scripting (" + m + ")"
        if m in ("openxr", "webxr", "mobile_vr", "visionos_xr"):
            return "Module: XR"
        return "Module: " + m
    return {
        "core": "Core", "servers": "Servers (engine subsystems)", "scene": "Scene / nodes",
        "editor": "Editor", "platform": "Platform ports", "drivers": "Drivers (GPU/OS backends)",
        "main": "Main loop / bootstrap", "tests": "Tests", "thirdparty": "Vendored thirdparty",
        "doc": "Docs (other)", "misc": "Misc / tooling", ".github": "CI",
    }.get(top, "Build / root")

commits = []
for block in raw.split(SEP)[1:]:
    fields = block.split("\x1f")
    h, an, ae, date, subj, body = fields[:6]
    stat = fields[6] if len(fields) > 6 else ""
    files = []
    for line in stat.strip().splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, p = parts
        add = int(a) if a.isdigit() else 0
        dele = int(d) if d.isdigit() else 0
        files.append((p, add, dele))
    commits.append(dict(h=h, an=an, ae=ae, date=date, subj=subj, body=body, files=files))

def classify(c):
    msg = c["subj"] + "\n" + c["body"]
    paths = [f[0] for f in c["files"]]
    n = len(paths)
    if BOT_AUTHOR.search(c["an"] + c["ae"]):
        return "bot"
    if TRANSLATION_MSG.search(c["subj"]):
        return "translation-sync"
    if n and all(noise_path(p) or p.startswith(("modules/", "COPYRIGHT")) and "thirdparty" in c["subj"].lower() for p in paths):
        return "thirdparty-update"
    tp = sum(1 for p in paths if p.startswith("thirdparty/"))
    if n and (tp / n >= 0.6 or (THIRDPARTY_MSG.search(c["subj"]) and tp)):
        return "thirdparty-update"
    if HOUSEKEEPING_MSG.search(c["subj"]) and all(not p.startswith(("core/", "scene/", "servers/", "editor/", "modules/", "platform/", "drivers/")) for p in paths):
        return "housekeeping"
    if STYLE_MSG.search(c["subj"]):
        return "style/format"
    if n >= 40 and MECHANICAL_MSG.search(c["subj"]):
        return "mass-mechanical"
    if n and all(noise_path(p) for p in paths):
        return "generated/validation-only"
    return "meaningful"

for c in commits:
    c["cls"] = classify(c)
    c["agent"] = bool(AGENT.search(c["subj"] + "\n" + c["body"] + "\n" + c["an"] + c["ae"]))

summary = collections.Counter((("agent:" if c["agent"] else "") + c["cls"]) for c in commits)

def tally(group):
    areas = collections.defaultdict(lambda: dict(commits=0, authors=set(), add=0, dele=0, fixes=0, api_commits=0))
    files = collections.defaultdict(lambda: dict(commits=0, authors=set(), churn=0, fixes=0))
    layers = collections.defaultdict(lambda: dict(commits=0, authors=set(), churn=0))
    for c in group:
        is_fix = bool(re.search(r"\bfix(es|ed)?\b|crash|regression", c["subj"], re.I))
        touches_api = any(doc_path(f[0]) or f[0].startswith(("core/extension/", "misc/extension_api_validation/")) for f in c["files"])
        seen_a, seen_l = set(), set()
        for p, a, d in c["files"]:
            if noise_path(p):
                continue
            ar = area(p, 3)
            A = areas[ar]
            if ar not in seen_a:
                A["commits"] += 1; A["authors"].add(c["an"]); A["fixes"] += is_fix; A["api_commits"] += touches_api
                seen_a.add(ar)
            A["add"] += a; A["dele"] += d
            if not doc_path(p):
                F = files[p]; F["commits"] += 1; F["authors"].add(c["an"]); F["churn"] += a + d; F["fixes"] += is_fix
            ly = layer(p)
            L = layers[ly]
            if ly not in seen_l:
                L["commits"] += 1; L["authors"].add(c["an"]); seen_l.add(ly)
            L["churn"] += a + d
    fin = lambda d: {k: {**v, "authors": len(v["authors"])} for k, v in d.items()}
    return fin(areas), fin(files), fin(layers)

meaningful = [c for c in commits if c["cls"] == "meaningful" and not c["agent"]]
agent_group = [c for c in commits if c["agent"]]
areas, files, layers = tally(meaningful)

# Co-change on meaningful commits, ignoring huge commits and noise/doc paths.
MAXF = 25
pair_area = collections.Counter(); single_area = collections.Counter()
pair_file = collections.Counter(); single_file = collections.Counter()
cross_layer = collections.Counter()
for c in meaningful:
    ps = [f[0] for f in c["files"] if not noise_path(f[0])]
    if not ps or len(ps) > MAXF:
        continue
    code = sorted({p for p in ps if not doc_path(p)})
    ars = sorted({area(p, 2) for p in ps if not doc_path(p)})
    lys = sorted({layer(p) for p in ps})
    for a in ars: single_area[a] += 1
    for x in itertools.combinations(ars, 2): pair_area[x] += 1
    for f in code: single_file[f] += 1
    for x in itertools.combinations(code, 2): pair_file[x] += 1
    for x in itertools.combinations(lys, 2): cross_layer[x] += 1

def coupling(pairs, singles, minsup):
    out = []
    for (a, b), n in pairs.items():
        if n < minsup:
            continue
        out.append(dict(a=a, b=b, together=n, conf_a_b=round(n / singles[a], 2), conf_b_a=round(n / singles[b], 2),
                        jaccard=round(n / (singles[a] + singles[b] - n), 2)))
    return sorted(out, key=lambda r: (-r["together"], -r["jaccard"]))

def strip_header_pairs(rows):
    """Drop .h/.cpp twins of the same stem — trivially coupled."""
    def stem(p): return re.sub(r"\.(h|cpp|hpp|mm|m|c)$", "", p)
    return [r for r in rows if stem(r["a"]) != stem(r["b"])]

noise_groups = collections.defaultdict(list)
for c in commits:
    if c["cls"] != "meaningful":
        noise_groups[c["cls"]].append(dict(h=c["h"], an=c["an"], subj=c["subj"], files=len(c["files"])))

monthly = collections.Counter(c["date"][:7] for c in meaningful)

json.dump(dict(
    since=SINCE, total=len(commits), summary=summary, monthly=sorted(monthly.items()),
    agent_commits=[dict(h=c["h"], an=c["an"], subj=c["subj"], cls=c["cls"]) for c in agent_group],
    noise_groups={k: dict(count=len(v), sample=sorted(v, key=lambda r: -r["files"])[:12]) for k, v in noise_groups.items()},
    meaningful_authors=len({c["an"] for c in meaningful}),
    areas=sorted(([k, v] for k, v in areas.items()), key=lambda kv: -kv[1]["commits"])[:60],
    layers=sorted(([k, v] for k, v in layers.items()), key=lambda kv: -kv[1]["commits"]),
    files=sorted(([k, v] for k, v in files.items()), key=lambda kv: (-kv[1]["commits"], -kv[1]["churn"]))[:50],
    area_pairs=coupling(pair_area, single_area, 6)[:40],
    file_pairs=strip_header_pairs(coupling(pair_file, single_file, 4))[:50],
    cross_layer=cross_layer.most_common(30),
), open(OUT, "w"), indent=1, default=list)
print("ok", OUT)
