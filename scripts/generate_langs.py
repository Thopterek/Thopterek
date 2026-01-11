#!/usr/bin/env python3
import os
import math
import requests

TOP_N = 5
EXCLUDED_LANGUAGES = set()

BG_COLOR = "#0b0f1a"
TEXT_COLOR = "#e5e7eb"
MUTED_TEXT = "#9ca3af"
OTHER_COLOR = "#6b7280"

REPO_COLORS = [
    "#f97316", "#eab308", "#22c55e", "#fb7185", "#a78bfa"
]

ACTIVITY_COLORS = [
    "#38bdf8", "#14b8a6", "#6366f1", "#06b6d4", "#0ea5e9"
]

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GH_USERNAME", os.environ["GITHUB_REPOSITORY"].split("/")[0])

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

QUERY = """
query ($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        languages(first: 20) {
          edges { node { name } }
        }
      }
    }
  }
}
"""

# -------------------- DATA --------------------

def fetch_repositories():
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

def languages_by_repo_count(repos):
    out = {}
    for r in repos:
        for e in {e["node"]["name"] for e in r["languages"]["edges"]}:
            out[e] = out.get(e, 0) + 1
    return out

def commit_weighted_languages(repos):
    out = {}
    for r in repos:
        langs = {e["node"]["name"] for e in r["languages"]["edges"]}
        if not langs:
            continue
        weight = fetch_commit_count(r["name"]) / len(langs)
        for l in langs:
            out[l] = out.get(l, 0) + weight
    return out

def top_n(data):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top = items[:TOP_N]
    other = sum(v for _, v in items[TOP_N:])
    if other:
        top.append(("Other", other))
    return top

# -------------------- SVG HELPERS --------------------

def pie(cx, cy, data, colors):
    total = sum(v for _, v in data)
    angle = -math.pi / 2
    paths = []

    for i, (label, value) in enumerate(data):
        frac = value / total
        delta = frac * 2 * math.pi
        a1, a2 = angle, angle + delta
        large = 1 if delta > math.pi else 0
        color = OTHER_COLOR if label == "Other" else colors[i % len(colors)]

        def pt(r, a):
            return cx + r * math.cos(a), cy + r * math.sin(a)

        rO, rI = 80, 50
        x1, y1 = pt(rO, a1)
        x2, y2 = pt(rO, a2)
        x3, y3 = pt(rI, a2)
        x4, y4 = pt(rI, a1)

        d = (
            f"M{x1},{y1} A{rO},{rO} 0 {large} 1 {x2},{y2} "
            f"L{x3},{y3} A{rI},{rI} 0 {large} 0 {x4},{y4} Z"
        )

        paths.append((d, color, label, round(frac * 100)))
        angle = a2

    return paths

def legend(x, y, items):
    out = ""
    for i, (_, color, label, pct) in enumerate(items):
        out += f'''
        <rect x="{x}" y="{y + i*18}" width="12" height="12" fill="{color}" rx="2"/>
        <text x="{x+18}" y="{y + i*18 + 11}" font-size="12" fill="{TEXT_COLOR}">
          {label} — {pct}%
        </text>
        '''
    return out

# -------------------- SVG RENDER --------------------

def render(repo_data, activity_data):
    repo_pie = pie(220, 160, top_n(repo_data), REPO_COLORS)
    act_pie = pie(520, 160, top_n(activity_data), ACTIVITY_COLORS)

    svg = f'''<svg width="700" height="360" viewBox="0 0 700 360"
      xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="{BG_COLOR}"/>

      <text x="40" y="32" font-size="16" fill="{TEXT_COLOR}">
        Languages by repositories
      </text>

      <text x="380" y="32" font-size="16" fill="{TEXT_COLOR}">
        Languages by activity
      </text>

      {legend(40, 60, repo_pie)}
      {legend(380, 60, act_pie)}

      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in repo_pie)}
      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in act_pie)}
    </svg>'''

    with open("languages-overview.svg", "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- MAIN --------------------

def main():
    repos = fetch_repositories()
    render(
        languages_by_repo_count(repos),
        commit_weighted_languages(repos)
    )
    print("Generated improved combined SVG")

if __name__ == "__main__":
    main()

