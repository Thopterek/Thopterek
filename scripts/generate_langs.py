#!/usr/bin/env python3
import os
import math
import requests

# -------------------- CONFIG --------------------

TOP_N = 5
EXCLUDED_LANGUAGES = set()  # optional filtering later

COLORS = [
    "#f97316",  # orange
    "#22c55e",  # green
    "#38bdf8",  # light blue
    "#a78bfa",  # purple
    "#f43f5e",  # red
    "#eab308",  # yellow
    "#14b8a6",  # teal
    "#fb7185",  # pink
]

BG_COLOR = "#0b0f1a"
TEXT_COLOR = "#e5e7eb"

# ------------------------------------------------

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

# -------------------- DATA FETCH --------------------

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

def fetch_commit_count(repo_name):
    url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?per_page=1"
    r = requests.get(url, headers=HEADERS)

    if "Link" not in r.headers:
        return len(r.json())

    for part in r.headers["Link"].split(","):
        if 'rel="last"' in part:
            return int(part.split("page=")[-1].split(">")[0])
    return 1

# -------------------- AGGREGATION --------------------

def languages_by_repo_count(repos):
    counts = {}
    for r in repos:
        langs = {e["node"]["name"] for e in r["languages"]["edges"]}
        for lang in langs:
            if lang in EXCLUDED_LANGUAGES:
                continue
            counts[lang] = counts.get(lang, 0) + 1
    return counts

def commit_weighted_languages(repos):
    weighted = {}
    for r in repos:
        commits = fetch_commit_count(r["name"])
        langs = {e["node"]["name"] for e in r["languages"]["edges"]}
        if not langs:
            continue
        weight = commits / len(langs)
        for lang in langs:
            if lang in EXCLUDED_LANGUAGES:
                continue
            weighted[lang] = weighted.get(lang, 0) + weight
    return weighted

def top_n_with_other(data):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top = items[:TOP_N]
    other = sum(v for _, v in items[TOP_N:])
    if other > 0:
        top.append(("Other", other))
    return top

# -------------------- SVG PIE --------------------

def generate_pie(data, title, filename):
    data = top_n_with_other(data)
    total = sum(v for _, v in data)
    cx, cy = 160, 140
    r_outer, r_inner = 90, 55
    angle = -math.pi / 2
    paths = []

    for i, (label, value) in enumerate(data):
        frac = value / total
        delta = frac * 2 * math.pi
        a1, a2 = angle, angle + delta
        large = 1 if delta > math.pi else 0
        color = COLORS[i % len(COLORS)]

        def pt(r, a):
            return cx + r * math.cos(a), cy + r * math.sin(a)

        x1, y1 = pt(r_outer, a1)
        x2, y2 = pt(r_outer, a2)
        x3, y3 = pt(r_inner, a2)
        x4, y4 = pt(r_inner, a1)

        d = (
            f"M{x1},{y1} "
            f"A{r_outer},{r_outer} 0 {large} 1 {x2},{y2} "
            f"L{x3},{y3} "
            f"A{r_inner},{r_inner} 0 {large} 0 {x4},{y4} Z"
        )

        paths.append((d, color, label, round(frac * 100)))
        angle = a2

    legend = ""
    for i, (_, color, label, pct) in enumerate(paths):
        y = 60 + i * 20
        legend += f'''
        <rect x="300" y="{y-10}" width="12" height="12" fill="{color}" rx="2"/>
        <text x="320" y="{y}" font-size="12" fill="{TEXT_COLOR}">
          {label} — {pct}%
        </text>
        '''

    svg = f'''<svg width="520" height="280" viewBox="0 0 520 280"
      xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="{BG_COLOR}"/>
      <text x="20" y="24" font-size="16" fill="{TEXT_COLOR}">{title}</text>
      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in paths)}
      {legend}
    </svg>'''

    with open(filename, "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- MAIN --------------------

def main():
    repos = fetch_repositories()

    generate_pie(
        languages_by_repo_count(repos),
        f"Languages by repositories — {USERNAME}",
        "languages-by-repo.svg"
    )

    generate_pie(
        commit_weighted_languages(repos),
        "Languages by activity (commit-weighted)",
        "languages-by-commit.svg"
    )

    print("Generated language pie charts")

if __name__ == "__main__":
    main()

