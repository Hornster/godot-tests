#!/usr/bin/env python3
"""Fetch PR metadata (reviewers, discussion size, body) for PRs in summary.json via gh GraphQL.

Usage: python3 -I prs.py <summary.json> <out-prs.json>
"""
import json, subprocess, sys

prs = sorted({c["pr"] for c in json.load(open(sys.argv[1]))["commits"] if c["pr"]})
FIELDS = """number title url author{login} mergedAt createdAt additions deletions
 labels(first:15){nodes{name}} comments{totalCount}
 reviews(first:60){totalCount nodes{author{login} state}}
 reviewThreads{totalCount}
 closingIssuesReferences(first:5){nodes{number title}}
 body"""
out = {}
for i in range(0, len(prs), 40):
    chunk = prs[i:i + 40]
    q = "query{repository(owner:\"godotengine\",name:\"godot\"){" + " ".join(
        f"p{n}:pullRequest(number:{n}){{{FIELDS}}}" for n in chunk) + "}}"
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True)
    data = json.loads(r.stdout)["data"]["repository"]
    for k, v in data.items():
        if v:
            v["author"] = (v["author"] or {}).get("login")
            v["labels"] = [l["name"] for l in v["labels"]["nodes"]]
            v["reviewers"] = [(x["author"] or {}).get("login") or "ghost" for x in v["reviews"]["nodes"]]
            v["approvers"] = sorted({(x["author"] or {}).get("login") or "ghost" for x in v["reviews"]["nodes"] if x["state"] == "APPROVED"})
            v["reviews"] = v["reviews"]["totalCount"]; v["comments"] = v["comments"]["totalCount"]
            v["reviewThreads"] = v["reviewThreads"]["totalCount"]
            v["closes"] = [f'#{x["number"]} {x["title"]}' for x in v["closingIssuesReferences"]["nodes"]]
            del v["closingIssuesReferences"]
            out[v["number"]] = v
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print(len(prs), "PRs requested,", len(out), "fetched")
