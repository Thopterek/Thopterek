#!/usr/bin/env python3
import os
import math
import requests

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GH_USERNAME", os.environ["GITHUB_REPOSITORY"].split("/")[0])

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Optional filtering (empty by default)
EXCLUDED_LANGUAGES = set()

TOP_N = 5

COLORS = [
    "#f97316", "#1e3a8a", "#fb923c",
    "#334155", "#fdba74", "#475569"
]

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

def fetch_repos():
    repos, cursor = [], None
    while True:
        r = requests.post(GITHUB_API, headers=HEADERS, json={
            "query": QUERY,
            "variables": {"login": USERNAME, "after": cursor}
        }).json()
        page = r["data"]["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return repos

def fetch_commit_count(repo):
    url = f"https://api.github.com/repos/{USERNAME}/{repo}/commits?per_page=1"
    r = requests.get(url, headers=HEADERS)
    if "Link" not in r.headers:
        return len(r.json())
    for part in r.headers["Link"].split(","):
        if 'rel="last"' in part:
            return int(part.split("page=")[-1].split(">")[0])
    return 1

def aggregate_languages(repos):
    totals = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            lang = e["node"]["name"]
            if lang in EXCLUDED_LANGUAGES:
                continue
            totals[lang] = totals.get(lang, 0) + e["size"]
    return totals

def commit_weighted_languages(repos):
    weighted = {}
    for r in repos:
        commits = fetch_commit_count(r["name"])
        langs = {e["node"]["name"]: e["size"] for e in r["languages"]["edges"]}
        total = sum(langs.values()) or 1
        for lang, size in langs.items():
            if lang in EXCLUDED_LANGUAGES:
                continue
            weighted[lang] = weighted.get(lang, 0) + commits * (size / total)
    return weighted

def top_n_with_other(data):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top = items[:TOP_N]
    other = sum(v for _, v in items[TOP_N:])
    if other > 0:
        top.append(("Other", other))
    return top

def pie_paths(data, cx, cy, r, r_inner):
    total = sum(v for _, v in data)
    angle = -math.pi / 2
    paths = []
    for i, (label, value) in enumerate(data):
        frac = value / total
        delta = frac * 2 * math.pi
        a1, a2 = angle, angle + delta

        def pt(rad, ang):
            return cx + rad * math.cos(ang), cy + rad * math.sin(ang)

        x1, y1 = pt(r, a1)
        x2, y2 = pt(r, a2)
        x3, y3 = pt(r_inner, a2)
        x4, y4 = pt(r_inner, a1)

        large = 1 if delta > math.pi else 0
        color = COLORS[i % len(COLORS)]

        d = (
            f"M{x1},{y1} "
            f"A{r},{r} 0 {large} 1 {x2},{y2} "
            f"L{x3},{y3} "
            f"A{r_inner},{r_inner} 0 {large} 0 {x4},{y4} Z"
        )
        paths.append((d, color, label, round(frac * 100)))
        angle = a2
    return paths

def render_svg(filename, title, data):
    data = top_n_with_other(data)
    paths = pie_paths(data, 160, 140, 90, 55)

    legend = ""
    for i, (_, _, label, pct) in enumerate(paths):
        y = 60 + i * 20
        legend += f'''
        <rect x="300" y="{y-10}" width="12" height="12" fill="{paths[i][1]}" rx="2"/>
        <text x="320" y="{y}" font-size="12" fill="#e5e7eb">{label} — {pct}%</text>
        '''

    svg = f'''<svg width="520" height="280" viewBox="0 0 520 280"
      xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0b0f1a"/>
      <text x="20" y="24" font-size="16" fill="#e5e7eb">{title}</text>
      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in paths)}
      {legend}
    </svg>'''

    with open(filename, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    repos = fetch_repos()
    render_svg(
        "languages-by-size.svg",
        f"Languages by code size — {USERNAME}",
        aggregate_languages(repos)
    )
    render_svg(
        "languages-by-commit.svg",
        f"Languages by activity (commit-weighted)",
        commit_weighted_languages(repos)
    )
    print("Generated pie charts")

if __name__ == "__main__":
    main()

