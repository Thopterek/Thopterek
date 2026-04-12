#!/usr/bin/env python3
import os
import math
import requests
import sys

# -------------------- CONFIG --------------------
TOP_N = 10   # slices shown in each pie — no "Other" bucket
EXCLUDED_LANGUAGES = {"HTML", "CSS"}

# Remap surface languages to their real underlying language.
LANGUAGE_REMAP = {
    "Jupyter Notebook": "Python",
    "SCSS":             "CSS",
    "Less":             "CSS",
    "Makefile":         "Shell",
    "Dockerfile":       "Shell",
    "Batchfile":        "Shell",
}

# Visuals
BG_COLOR   = "#0b0f1a"
TEXT_COLOR = "#e5e7eb"
MUTED_TEXT = "#6b7280"
BORDER     = "#1f2937"
ROSTER_DIM = "#374151"

REPO_COLORS     = ["#f97316","#eab308","#22c55e","#fb7185","#a78bfa",
                   "#f43f5e","#84cc16","#fbbf24","#34d399","#c084fc"]
ACTIVITY_COLORS = ["#06b6d4","#6366f1","#00c2a8","#ff6b6b","#ffd166",
                   "#38bdf8","#818cf8","#2dd4bf","#fb923c","#e879f9"]

OUTPUT_FILE = "languages-overview.svg"
# ------------------------------------------------

TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    print("Error: GITHUB_TOKEN not set.", file=sys.stderr)
    sys.exit(1)

GITHUB_API = "https://api.github.com/graphql"
USERNAME   = os.environ.get("GH_USERNAME",
             os.environ.get("GITHUB_REPOSITORY", "").split("/")[0])
if not USERNAME:
    print("Error: Set GH_USERNAME or run inside a repo context.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

QUERY = """
query ($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isPrivate
        languages(first: 20) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# -------------------- FETCH --------------------

def fetch_repositories():
    repos, cursor = [], None
    while True:
        resp = requests.post(GITHUB_API, headers=HEADERS, json={
            "query": QUERY, "variables": {"login": USERNAME, "after": cursor}
        })
        if resp.status_code != 200:
            print("GraphQL failed:", resp.status_code, resp.text, file=sys.stderr)
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
        print(f"Warning: commit fetch for {repo_name} → {r.status_code}; defaulting to 1",
              file=sys.stderr)
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
    name = LANGUAGE_REMAP.get(name, name)
    return None if name in EXCLUDED_LANGUAGES else name


def repo_language_bytes(repo):
    result = {}
    for edge in repo.get("languages", {}).get("edges", []):
        lang = remap(edge["node"]["name"])
        if lang is None:
            continue
        result[lang] = result.get(lang, 0) + edge["size"]
    return result


def languages_by_bytes(repos):
    totals = {}
    for repo in repos:
        for lang, size in repo_language_bytes(repo).items():
            totals[lang] = totals.get(lang, 0) + size
    return totals


def commit_weighted_languages(repos):
    weighted = {}
    for repo in repos:
        lang_bytes  = repo_language_bytes(repo)
        total_bytes = sum(lang_bytes.values()) or 1
        commits     = fetch_commit_count(repo["name"])
        for lang, size in lang_bytes.items():
            weighted[lang] = weighted.get(lang, 0) + commits * (size / total_bytes)
    return weighted


def sorted_all(data):
    return sorted(data.items(), key=lambda x: x[1], reverse=True)

# -------------------- SVG HELPERS --------------------

def xe(s):
    """XML-escape text so that language names like C++, C#, F# render safely."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pie_paths(data, cx, cy, r_outer=90, r_inner=58, colors=None):
    total = sum(v for _, v in data) or 1
    angle = -math.pi / 2
    result = []
    for i, (label, value) in enumerate(data):
        frac  = value / total
        delta = frac * 2 * math.pi
        a1, a2 = angle, angle + delta
        large  = 1 if delta > math.pi else 0
        color  = colors[i % len(colors)]

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


def legend_svg(x, y, items, pct_x_offset=160):
    out = ""
    for i, (_, color, label, pct) in enumerate(items):
        yy = y + i * 21
        display = xe(label) if len(label) <= 18 else xe(label[:16] + "…")
        out += (f'<rect x="{x}" y="{yy-11}" width="10" height="10" '
                f'fill="{color}" rx="2"/>\n')
        out += (f'<text x="{x+15}" y="{yy-1}" font-size="11" fill="{TEXT_COLOR}" '
                f'font-family="monospace">{display}</text>\n')
        out += (f'<text x="{x+pct_x_offset}" y="{yy-1}" font-size="11" '
                f'fill="{MUTED_TEXT}" font-family="monospace" '
                f'text-anchor="end">{pct}%</text>\n')
    return out


def roster_svg(all_items, top_color_map, x_start, y_start, total_w, cols=4):
    col_w = (total_w - x_start * 2) // cols
    total = sum(v for _, v in all_items) or 1
    out   = ""
    for idx, (lang, val) in enumerate(all_items):
        col = idx % cols; row = idx // cols
        x   = x_start + col * col_w
        y   = y_start + row * 22
        color = top_color_map.get(lang, ROSTER_DIM)
        pct   = val / total * 100
        pct_s = f"{pct:.1f}%" if pct >= 0.05 else "<0.1%"
        display = xe(lang) if len(lang) <= 20 else xe(lang[:18] + "…")
        out += (f'<rect x="{x}" y="{y-9}" width="9" height="9" '
                f'fill="{color}" rx="1.5"/>\n')
        out += (f'<text x="{x+14}" y="{y}" font-size="11" fill="{TEXT_COLOR}" '
                f'font-family="monospace">{display}</text>\n')
        out += (f'<text x="{x+col_w-6}" y="{y}" font-size="11" fill="{MUTED_TEXT}" '
                f'font-family="monospace" text-anchor="end">{pct_s}</text>\n')
    return out

# -------------------- RENDER --------------------

def render_combined(repo_data, activity_data):
    repo_all = sorted_all(repo_data)
    act_all  = sorted_all(activity_data)
    repo_top = repo_all[:TOP_N]
    act_top  = act_all[:TOP_N]

    W           = 880
    COLS        = 4
    PAD         = 30
    LEG_X_L     = PAD
    PIE_CX_L    = 318
    LEG_X_R     = 468
    PIE_CX_R    = 756
    PIE_CY      = 180
    R_OUTER     = 92
    R_INNER     = 58
    LEG_START_Y = 72

    pie_h = max(TOP_N * 21 + LEG_START_Y, PIE_CY + R_OUTER + 16)

    ROSTER_SEP_Y = pie_h + 24
    ROSTER_TIT_Y = ROSTER_SEP_Y + 22
    ROSTER_Y_0   = ROSTER_TIT_Y + 26
    roster_rows  = math.ceil(len(repo_all) / COLS)
    TOTAL_H      = ROSTER_Y_0 + roster_rows * 22 + PAD

    top_color_map = {lang: REPO_COLORS[i] for i, (lang, _) in enumerate(repo_top)}

    repo_paths = pie_paths(repo_top, PIE_CX_L, PIE_CY,
                           r_outer=R_OUTER, r_inner=R_INNER, colors=REPO_COLORS)
    act_paths  = pie_paths(act_top,  PIE_CX_R, PIE_CY,
                           r_outer=R_OUTER, r_inner=R_INNER, colors=ACTIVITY_COLORS)

    mid_x = (PIE_CX_L + R_OUTER + LEG_X_R) // 2

    svg = f'''<svg width="{W}" height="{TOTAL_H}" viewBox="0 0 {W} {TOTAL_H}"
     xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{BG_COLOR}" rx="14"/>

  <!-- ══ PIE PANELS ══════════════════════════════════════════ -->
  <text x="{LEG_X_L}" y="26" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">Code size</text>
  <text x="{LEG_X_L}" y="42" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">bytes across all repos · public + private</text>

  <text x="{LEG_X_R}" y="26" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">Activity</text>
  <text x="{LEG_X_R}" y="42" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">commits distributed by byte share per repo</text>

  <line x1="{mid_x}" y1="14" x2="{mid_x}" y2="{pie_h + 10}"
        stroke="{BORDER}" stroke-width="1"/>

  {legend_svg(LEG_X_L, LEG_START_Y, repo_paths)}
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in repo_paths)}

  {legend_svg(LEG_X_R, LEG_START_Y, act_paths)}
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in act_paths)}

  <!-- ══ ROSTER SECTION ═══════════════════════════════════════ -->
  <line x1="{PAD}" y1="{ROSTER_SEP_Y}" x2="{W - PAD}" y2="{ROSTER_SEP_Y}"
        stroke="{BORDER}" stroke-width="1"/>

  <text x="{PAD}" y="{ROSTER_TIT_Y}" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">All languages detected</text>
  <text x="{W - PAD}" y="{ROSTER_TIT_Y}" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace" text-anchor="end"
        >sorted by code size · highlighted = top {TOP_N}</text>

  {roster_svg(repo_all, top_color_map, PAD, ROSTER_Y_0, W, cols=COLS)}
</svg>'''

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- MAIN --------------------

def main():
    print(f"Fetching repos for @{USERNAME} …", file=sys.stderr)
    repos = fetch_repositories()
    pub  = sum(1 for r in repos if not r.get("isPrivate"))
    priv = sum(1 for r in repos if r.get("isPrivate"))
    print(f"  {len(repos)} repos  ({pub} public · {priv} private)", file=sys.stderr)

    repo_data     = languages_by_bytes(repos)
    activity_data = commit_weighted_languages(repos)

    if not repo_data:
        print("No language data — check token scopes (`repo` needed for private).",
              file=sys.stderr)
        sys.exit(1)

    print(f"  {len(repo_data)} distinct languages detected", file=sys.stderr)
    render_combined(repo_data, activity_data)
    print("Wrote", OUTPUT_FILE)

if __name__ == "__main__":
    main()
