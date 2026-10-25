#!/usr/bin/env python3
"""Contributor map for one path: who touched it, on what topics, via which PRs.

Usage: python3 -I contributors.py <ref> <since> <path> <out.json>
"""
import collections, json, re, subprocess, sys

REF, SINCE, PATH, OUT = sys.argv[1:5]
SEP = "\x1e"

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout

# commit -> PR number, via first-parent merge commits ("Merge pull request #N from ...")
pr_of = {}
for line in git("log", REF, "--merges", "--first-parent", f"--since={SINCE}",
                "--format=%H %P\x1f%s").splitlines():
    head, subj = line.split("\x1f", 1)
    parts = head.split()
    m = re.match(r"Merge pull request #(\d+)", subj)
    if not m or len(parts) < 3:
        continue
    merge, p1, p2 = parts[0], parts[1], parts[2]
    for c in git("rev-list", f"{p1}..{p2}").split():
        pr_of[c] = int(m.group(1))

raw = git("log", REF, "--no-merges", f"--since={SINCE}", "--numstat", "--no-renames",
          f"--format={SEP}%H\x1f%aN\x1f%aE\x1f%cI\x1f%s\x1f%b\x1f", "--", PATH)

BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions|weblate", re.I)
AGENT_AUTHOR = re.compile(r"^(claude|copilot|codex|devin|cursor)", re.I)
AGENT_TRAILER = re.compile(r"co-authored-by:.*(claude|copilot|anthropic|openai|cursor|codex|gemini|devin)", re.I)
STYLE = re.compile(r"^(style|clang-format|format)\b|clang-tidy|apply .*(rules|clang)|^codespell|typo|readability-identifier", re.I)
MECHANICAL = re.compile(r"\b(rename|move|split|remove redundant|replace|trim|apply|sweep)\b", re.I)

commits = []
for block in raw.split(SEP)[1:]:
    f = block.split("\x1f")
    h, an, ae, date, subj, body = f[:6]
    files = []
    for line in (f[6] if len(f) > 6 else "").strip().splitlines():
        p = line.split("\t")
        if len(p) == 3:
            files.append((p[2], int(p[0]) if p[0].isdigit() else 0, int(p[1]) if p[1].isdigit() else 0))
    own = [x for x in files if x[0].startswith(PATH.rstrip("/") + "/")]
    if BOT.search(an) or BOT.search(ae):
        group = "bot"
    elif AGENT_AUTHOR.search(an):
        group = "agent-authored"
    elif STYLE.search(subj):
        group = "style"
    elif len(files) >= 40 and MECHANICAL.search(subj):
        group = "mass-mechanical"
    else:
        group = "meaningful"
    commits.append(dict(h=h[:10], author=an, email=ae, date=date[:10], subj=subj,
                        agent_coauthor=bool(AGENT_TRAILER.search(body)),
                        pr=pr_of.get(h), group=group, total_files=len(files),
                        files=[x[0] for x in own], add=sum(x[1] for x in own),
                        dele=sum(x[2] for x in own)))

json.dump(commits, open(OUT, "w"), indent=1, ensure_ascii=False)
print(len(commits), "commits;", collections.Counter(c["group"] for c in commits))
print("with PR:", sum(1 for c in commits if c["pr"]), "agent co-author trailers:",
      sum(c["agent_coauthor"] for c in commits))
