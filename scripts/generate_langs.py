#!/usr/bin/env python3
import os
import math
import requests

# -------------------- CONFIG --------------------

TOP_N = 5
EXCLUDED_LANGUAGES = set()

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
MUTED_TEXT = "#9ca3af"

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
        langs = {e["node"]["name"] for e in r["languages"]["edges"]}
        if not langs:
            continue
        commits = fetch_commit_count(r["name"])
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

# -------------------- SVG HELPERS --------------------

def pie_paths(data, cx, cy, r_outer, r_inner):
    total = sum(v for _, v in data)
    angle = -math.pi / 2
    result = []

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

        result.append((d, color, label, round(frac * 100)))
        angle = a2

    return result

# -------------------- SVG RENDER --------------------

def render_combined_svg(repo_data, commit_data):
    repo_pie = pie_paths(top_n_with_other(repo_data), 170, 160, 85, 52)
    commit_pie = pie_paths(top_n_with_other(commit_data), 430, 160, 85, 52)

    legend_items = {}
    for pie in repo_pie + commit_pie:
        _, color, label, _ = pie
        legend_items[label] = color

    legend = ""
    for i, (label, color) in enumerate(legend_items.items()):
        y = 300 + i * 18
        legend += f'''
        <rect x="40" y="{y-10}" width="12" height="12" fill="{color}" rx="2"/>
        <text x="60" y="{y}" font-size="12" fill="{TEXT_COLOR}">
          {label}
        </text>
        '''

    svg = f'''<svg width="600" height="420" viewBox="0 0 600 420"
      xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="{BG_COLOR}"/>

      <text x="20" y="28" font-size="18" fill="{TEXT_COLOR}">
        Languages overview — {USERNAME}
      </text>

      <text x="90" y="60" font-size="14" fill="{MUTED_TEXT}">
        By repositories
      </text>

      <text x="340" y="60" font-size="14" fill="{MUTED_TEXT}">
        By activity
      </text>

      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in repo_pie)}
      {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in commit_pie)}

      {legend}
    </svg>'''

    with open("languages-overview.svg", "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- MAIN --------------------

def main():
    repos = fetch_repositories()

    render_combined_svg(
        languages_by_repo_count(repos),
        commit_weighted_languages(repos)
    )

    print("Generated combined languages overview SVG")

if __name__ == "__main__":
    main()

