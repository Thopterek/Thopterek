#!/usr/bin/env python3
import os
import math
import requests
import sys

# -------------------- CONFIG --------------------
TOP_N = 5
EXCLUDED_LANGUAGES = {"HTML", "CSS"}   # pure markup / style — usually not meaningful

# Remap "surface" languages to their real underlying language.
# Add anything you like here; keys are matched exactly (case-sensitive).
LANGUAGE_REMAP = {
    "Jupyter Notebook": "Python",
    "SCSS":             "CSS",
    "Less":             "CSS",
    "Makefile":         "Shell",
    "Dockerfile":       "Shell",
    "Batchfile":        "Shell",
}

# Visuals
BG_COLOR    = "#0b0f1a"
TEXT_COLOR  = "#e5e7eb"
MUTED_TEXT  = "#9ca3af"
OTHER_COLOR = "#6b7280"

# Left / repo-size pie (warm, vibrant)
REPO_COLORS     = ["#f97316", "#eab308", "#22c55e", "#fb7185", "#a78bfa"]

# Right / activity pie (high-contrast)
ACTIVITY_COLORS = ["#06b6d4", "#6366f1", "#00c2a8", "#ff6b6b", "#ffd166"]

OUTPUT_FILE = "languages-overview.svg"
# ------------------------------------------------

TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    print("Error: GITHUB_TOKEN not set in environment.", file=sys.stderr)
    sys.exit(1)

GITHUB_API = "https://api.github.com/graphql"
USERNAME = os.environ.get("GH_USERNAME", os.environ.get("GITHUB_REPOSITORY", "").split("/")[0])
if not USERNAME:
    print("Error: Could not determine GH username. Set GH_USERNAME or run in a repo context.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# No privacy filter → returns ALL repos (public + private) the token can see.
# ownerAffiliations: OWNER ensures we only count repos you own, not just starred/member repos.
QUERY = """
query ($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isPrivate
        languages(first: 20) {
          edges {
            size
            node { name }
          }
        }
      }
    }
  }
}
"""

# -------------------- DATA FETCH --------------------

def fetch_repositories():
    repos = []
    cursor = None
    while True:
        resp = requests.post(GITHUB_API, headers=HEADERS, json={
            "query": QUERY,
            "variables": {"login": USERNAME, "after": cursor}
        })
        if resp.status_code != 200:
            print("GraphQL request failed:", resp.status_code, resp.text, file=sys.stderr)
            sys.exit(1)
        data = resp.json()
        if data.get("errors"):
            print("GraphQL errors:", data["errors"], file=sys.stderr)
            sys.exit(1)
        page = data["data"]["user"]["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return repos


def fetch_commit_count(repo_name):
    url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?per_page=1"
    r = requests.get(url, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
    })
    if r.status_code != 200:
        print(f"Warning: commit fetch for {repo_name} returned {r.status_code}; defaulting to 1", file=sys.stderr)
        return 1
    if "Link" not in r.headers:
        try:
            return max(len(r.json()), 1)
        except Exception:
            return 1
    for part in r.headers["Link"].split(","):
        if 'rel="last"' in part:
            try:
                return int(part.split("page=")[-1].split(">")[0])
            except Exception:
                return 1
    return 1

# -------------------- AGGREGATION --------------------

def remap(name):
    """Apply LANGUAGE_REMAP and return None if the result is excluded."""
    name = LANGUAGE_REMAP.get(name, name)
    if name in EXCLUDED_LANGUAGES:
        return None
    return name


def repo_language_bytes(repo):
    """Return {language: bytes} for a single repo, after remapping."""
    result = {}
    for edge in repo.get("languages", {}).get("edges", []):
        lang = remap(edge["node"]["name"])
        if lang is None:
            continue
        result[lang] = result.get(lang, 0) + edge["size"]
    return result


def languages_by_bytes(repos):
    """Left pie: total bytes written in each language across all repos."""
    totals = {}
    for repo in repos:
        for lang, size in repo_language_bytes(repo).items():
            totals[lang] = totals.get(lang, 0) + size
    return totals


def commit_weighted_languages(repos):
    """
    Right pie: each repo's commit count is distributed across its languages
    proportionally by byte size.  This reflects where you actually *work*,
    not just where you have the most lines sitting around.
    """
    weighted = {}
    for repo in repos:
        lang_bytes = repo_language_bytes(repo)
        total_bytes = sum(lang_bytes.values()) or 1
        commits = fetch_commit_count(repo["name"])
        for lang, size in lang_bytes.items():
            share = size / total_bytes
            weighted[lang] = weighted.get(lang, 0) + commits * share
    return weighted


def top_n_with_other(data):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    top   = items[:TOP_N]
    other = sum(v for _, v in items[TOP_N:])
    if other > 0:
        top.append(("Other", other))
    return top

# -------------------- SVG HELPERS --------------------

def pie_paths(data, cx, cy, r_outer=88, r_inner=56, colors=None):
    total = sum(v for _, v in data) or 1
    angle = -math.pi / 2
    result = []
    for i, (label, value) in enumerate(data):
        frac  = value / total
        delta = frac * 2 * math.pi
        a1, a2 = angle, angle + delta
        large = 1 if delta > math.pi else 0
        color = OTHER_COLOR if label == "Other" else colors[i % len(colors)]

        def pt(r, a):
            return cx + r * math.cos(a), cy + r * math.sin(a)

        x1, y1 = pt(r_outer, a1); x2, y2 = pt(r_outer, a2)
        x3, y3 = pt(r_inner, a2); x4, y4 = pt(r_inner, a1)
        d = (f"M{x1:.2f},{y1:.2f} "
             f"A{r_outer},{r_outer} 0 {large} 1 {x2:.2f},{y2:.2f} "
             f"L{x3:.2f},{y3:.2f} "
             f"A{r_inner},{r_inner} 0 {large} 0 {x4:.2f},{y4:.2f} Z")
        result.append((d, color, label, round(frac * 100)))
        angle = a2
    return result


def legend_svg(x, y, items):
    out = ""
    for i, (_, color, label, pct) in enumerate(items):
        yy = y + i * 20
        out += f'<rect x="{x}" y="{yy-12}" width="12" height="12" fill="{color}" rx="2"/>\n'
        out += f'<text x="{x+18}" y="{yy-2}" font-size="12" fill="{TEXT_COLOR}">{label} — {pct}%</text>\n'
    return out

# -------------------- RENDER --------------------

def render_combined(repo_data, activity_data):
    repo_top = top_n_with_other(repo_data)
    act_top  = top_n_with_other(activity_data)

    left_legend_x,  left_legend_y  = 40,  70
    left_pie_cx,    left_pie_cy    = 280, 160

    right_legend_x, right_legend_y = 440, 70
    right_pie_cx,   right_pie_cy   = 680, 160

    repo_paths = pie_paths(repo_top, left_pie_cx,  left_pie_cy,  colors=REPO_COLORS)
    act_paths  = pie_paths(act_top,  right_pie_cx, right_pie_cy, colors=ACTIVITY_COLORS)

    # Divider line between the two panels
    divider = f'<line x1="400" y1="20" x2="400" y2="260" stroke="{MUTED_TEXT}" stroke-width="0.5" stroke-dasharray="4 4" opacity="0.4"/>'

    svg = f'''<svg width="800" height="280" viewBox="0 0 800 280" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{BG_COLOR}" rx="12"/>

  <!-- panel titles -->
  <text x="40"  y="36" font-size="14" font-weight="600" fill="{TEXT_COLOR}" font-family="monospace">Languages by code size</text>
  <text x="440" y="36" font-size="14" font-weight="600" fill="{TEXT_COLOR}" font-family="monospace">Languages by activity</text>
  <text x="40"  y="52" font-size="10" fill="{MUTED_TEXT}" font-family="monospace">weighted by bytes across all repos (public + private)</text>
  <text x="440" y="52" font-size="10" fill="{MUTED_TEXT}" font-family="monospace">commits distributed by byte share per repo</text>

  {divider}

  <!-- left legend -->
  {legend_svg(left_legend_x, left_legend_y, repo_paths)}
  <!-- right legend -->
  {legend_svg(right_legend_x, right_legend_y, act_paths)}

  <!-- left pie -->
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in repo_paths)}
  <!-- right pie -->
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in act_paths)}
</svg>'''

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- MAIN --------------------

def main():
    print(f"Fetching repos for @{USERNAME} …", file=sys.stderr)
    repos = fetch_repositories()
    pub  = sum(1 for r in repos if not r.get("isPrivate"))
    priv = sum(1 for r in repos if r.get("isPrivate"))
    print(f"Found {len(repos)} repos ({pub} public, {priv} private)", file=sys.stderr)

    repo_data     = languages_by_bytes(repos)
    activity_data = commit_weighted_languages(repos)

    if not repo_data:
        print("No language data found — check token scopes.", file=sys.stderr)
        sys.exit(1)

    render_combined(repo_data, activity_data)
    print("Wrote", OUTPUT_FILE)

if __name__ == "__main__":
    main()
