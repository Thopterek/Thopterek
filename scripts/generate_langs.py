#!/usr/bin/env python3
import os
import sys
import requests
import json

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    print("Error: GITHUB_TOKEN not found in environment.", file=sys.stderr)
    sys.exit(1)

# username can be passed via env GH_USERNAME, otherwise infer from repository owner
USERNAME = os.environ.get("GH_USERNAME")
if not USERNAME:
    # fallback to GITHUB_REPOSITORY (owner/repo)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    USERNAME = repo.split("/")[0] if "/" in repo else None
if not USERNAME:
    print("Error: Could not determine GitHub username. Set GH_USERNAME env var.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "generate-langs-script"
}

# GraphQL query with pagination
QUERY = """
query ($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        languages(first: 20) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

def fetch_all_repos(login):
    repos = []
    has_next = True
    cursor = None
    while has_next:
        variables = {"login": login, "after": cursor}
        resp = requests.post(GITHUB_API, headers=HEADERS, json={"query": QUERY, "variables": variables})
        if resp.status_code != 200:
            print("GitHub API error:", resp.status_code, resp.text, file=sys.stderr)
            sys.exit(1)
        data = resp.json()
        if "errors" in data:
            print("GitHub GraphQL errors:", data["errors"], file=sys.stderr)
            sys.exit(1)
        user = data.get("data", {}).get("user")
        if not user:
            print("No user data returned. Check username and token permissions.", file=sys.stderr)
            sys.exit(1)
        page = user["repositories"]
        repos.extend(page["nodes"])
        has_next = page["pageInfo"]["hasNextPage"]
        cursor = page["pageInfo"]["endCursor"]
    return repos

def aggregate_languages(repos):
    totals = {}
    for r in repos:
        lang_edges = r.get("languages", {}).get("edges", []) or []
        for e in lang_edges:
            name = e["node"]["name"]
            size = e.get("size") or 0
            totals[name] = totals.get(name, 0) + size
    return totals

def build_svg(sorted_langs, username):
    # simple horizontal bars + labels
    top = sorted_langs[:8]  # top 8 languages
    total_percent = sum(x["percent"] for x in top)
    width = 560
    bar_area_width = 420
    row_h = 28
    height = 60 + len(top)*row_h
    rows = []
    y = 48
    for i, lang in enumerate(top):
        bar_w = int((lang["percent"]/100.0) * bar_area_width)
        rows.append(f'<text x="18" y="{y-8}" font-family="Arial" font-size="12">{i+1}. {lang["name"]} — {lang["percent"]}%</text>')
        rows.append(f'<rect x="150" y="{y-20}" width="{bar_w}" height="14" rx="4" ry="4" />')
        y += row_h
    title = f"Top languages for {username}"
    svg = f'''<?xml version="1.0" encoding="utf-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#0b1220"/>
  <text x="18" y="20" font-family="Arial" font-size="16" fill="#ffffff">{title}</text>
  {''.join(rows)}
</svg>'''
    return svg

def main():
    repos = fetch_all_repos(USERNAME)
    totals = aggregate_languages(repos)
    if not totals:
        print("No language data found (maybe user has no public non-fork repos).", file=sys.stderr)
        sys.exit(0)
    total_bytes = sum(totals.values()) or 1
    sorted_langs = sorted(
        [{"name": k, "bytes": v, "percent": round((v/total_bytes)*100)} for k, v in totals.items()],
        key=lambda x: x["bytes"],
        reverse=True
    )
    svg = build_svg(sorted_langs, USERNAME)
    with open("languages.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("languages.svg generated — top languages:", [l["name"] for l in sorted_langs[:8]])

if __name__ == "__main__":
    main()

