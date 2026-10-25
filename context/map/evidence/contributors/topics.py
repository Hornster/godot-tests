#!/usr/bin/env python3
"""Topic + kind classification and per-person / per-topic concentration for scene/resources.

Usage: python3 -I topics.py <scene-resources.json> <out-summary.json>
"""
import collections, json, re, sys

cs = [c for c in json.load(open(sys.argv[1])) if c["group"] == "meaningful"]

TOPICS = [  # (topic, regex on path relative to scene/resources/) - first match wins
    ("Animation & IK", r"^(animation|bone_map|skeleton_profile)|^3d/(joint_limitation|skeleton)"),
    ("2D skeleton modifications", r"^2d/skeleton/"),
    ("Particles material", r"^particle_process_material"),
    ("Visual shaders", r"^visual_shader"),
    ("Materials & shaders", r"material|^shader"),
    ("Text, fonts & UI theme", r"^(font|text_|label_settings|theme|style_box|dpi_texture)"),
    ("Textures & streaming", r"texture|^texture_rd|^image"),
    ("Mesh & geometry", r"mesh|surface_tool|^3d/primitive"),
    ("Scene serialization (PackedScene, .tscn/.tres)", r"^(packed_scene|resource_format)"),
    ("Environment & camera", r"^(environment|camera_attributes|compositor|sky)"),
    ("Audio streams", r"^audio"),
    ("TileSet & 2D navigation", r"^2d/(tile_set|navigation)"),
    ("Physics shapes & worlds", r"shape|^(2d|3d)/world|^world"),
    ("Curves & gradients", r"^(curve|gradient)"),
    ("Sprite frames", r"^sprite_frames"),
]
CROSS = re.compile(r"include|RequiredParam|WARN_UNUSED|warn_unused|explicit|Decouple|clangd?-tidy|memnew|cast_to|"
                   r"LocalVector|RBMap|CowData|RETURN_IF_ERROR|ContainerType|container types|StringName|GDType|"
                   r"escaped newlines|unused|math_funcs|Math` namespace|Rename|signal parameters|prefixes|"
                   r"CodeCompletionOption|_validate_property|class names in resource type hints|big endian|"
                   r"dedicated files|Split AudioServer|TileMap\(Layer\) to a module|regex code|Allow to disable|"
                   r"compil|templates be compilable|disable_physics|navigation_3d_disabled|deprecated=no", re.I)
FIX = re.compile(r"^(fix|fixes|revert|restore|reset|add safety|add missing|prevent)|\bcrash|regression", re.I)

def topic(path):
    rel = path.split("scene/resources/", 1)[1]
    for name, rx in TOPICS:
        if re.search(rx, rel):
            return name
    return "Other / build"

for c in cs:
    ts = collections.Counter(topic(f) for f in c["files"])
    c["topics"] = sorted(ts)
    c["kind"] = "cross-cutting" if CROSS.search(c["subj"]) or len(ts) >= 4 else ("fix" if FIX.search(c["subj"]) else "feature/change")

people = collections.defaultdict(lambda: dict(commits=0, prs=set(), add=0, dele=0, topics=collections.Counter(),
                                              kinds=collections.Counter(), first=None, last=None, subjects=[]))
by_topic = collections.defaultdict(lambda: collections.Counter())
for c in cs:
    p = people[c["author"]]
    p["commits"] += 1; p["prs"].add(c["pr"]); p["add"] += c["add"]; p["dele"] += c["dele"]
    p["kinds"][c["kind"]] += 1
    p["first"] = min(p["first"] or c["date"], c["date"]); p["last"] = max(p["last"] or c["date"], c["date"])
    p["subjects"].append(f'#{c["pr"]} {c["subj"]}')
    if c["kind"] != "cross-cutting":
        for t in c["topics"]:
            p["topics"][t] += 1
            by_topic[t][c["author"]] += 1

out = dict(
    total=len(cs), authors=len(people),
    kinds=collections.Counter(c["kind"] for c in cs),
    people={k: dict(v, prs=sorted(v["prs"]), topics=v["topics"].most_common(), kinds=dict(v["kinds"]))
            for k, v in sorted(people.items(), key=lambda kv: -kv[1]["commits"])},
    topics={t: dict(commits=sum(a.values()), authors=len(a), top=a.most_common(4),
                    top1_share=round(a.most_common(1)[0][1] / sum(a.values()), 2))
            for t, a in sorted(by_topic.items(), key=lambda kv: -sum(kv[1].values()))},
    commits=cs)
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)

print("total", out["total"], "authors", out["authors"], dict(out["kinds"]))
print("\n== topics (domain commits, cross-cutting excluded)")
for t, v in out["topics"].items():
    print(f'{v["commits"]:3} commits {v["authors"]:2} authors top1={v["top1_share"]:.0%}  {t}: {v["top"]}')
print("\n== people (>=2 commits)")
for k, v in out["people"].items():
    if v["commits"] >= 2:
        print(f'{k[:28]:28} c={v["commits"]:2} prs={len(v["prs"]):2} +{v["add"]}/-{v["dele"]} {v["first"]}..{v["last"]} {v["kinds"]} {v["topics"][:4]}')
# commit-share concentration
cnt = sorted((v["commits"] for v in out["people"].values()), reverse=True)
tot = sum(cnt); acc = 0
for i, n in enumerate(cnt, 1):
    acc += n
    if acc >= tot / 2:
        print(f"\n{i} people account for 50% of meaningful commits; top-3 share {sum(cnt[:3])/tot:.0%}; single-commit authors {sum(1 for n in cnt if n == 1)}")
        break
