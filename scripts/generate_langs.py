#!/usr/bin/env python3
import os
import math
import sys
import requests

# -------------------- CONFIG --------------------
TOP_N = 10   # slices shown in each pie — no "Other" bucket

# Repos you don't own but have contributed to (commits / PRs).
INCLUDE_CONTRIBUTED = True
# Repos where you are a collaborator or org member, even without commits yet.
INCLUDE_COLLABORATOR = True
INCLUDE_FORKS = False

# A repo you contributed one file to would otherwise dump its entire language
# footprint into the "Code size" donut. Keeping this True means a repo only
# counts once you actually have a commit on its default branch.
SKIP_REPOS_WITHOUT_MY_COMMITS = True

# Flip to True if one huge upstream repo you contributed to swamps the code-size
# donut: size then counts only your own repos, while activity still counts all.
SIZE_COUNTS_ONLY_OWNED_REPOS = False

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
PAGE_SIZE = 50   # repos per GraphQL page; lower this if queries time out
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

AFFILIATIONS = ["OWNER"]
if INCLUDE_COLLABORATOR:
    AFFILIATIONS += ["COLLABORATOR", "ORGANIZATION_MEMBER"]

# `history(author: {id: ...})` is what restricts commit counts to you alone.
REPO_FIELDS = """
fragment repoFields on Repository {
  nameWithOwner
  isPrivate
  isFork
  languages(first: 100) {
    edges { size node { name } }
  }
  defaultBranchRef {
    target {
      ... on Commit {
        history(author: {id: $authorId}) { totalCount }
      }
    }
  }
}
"""

VIEWER_QUERY = "query ($login: String!) { user(login: $login) { id } }"

OWNED_QUERY = REPO_FIELDS + """
query ($login: String!, $after: String, $authorId: ID!,
       $affiliations: [RepositoryAffiliation], $size: Int!) {
  user(login: $login) {
    repositories(first: $size, after: $after, ownerAffiliations: $affiliations) {
      pageInfo { hasNextPage endCursor }
      nodes { ...repoFields }
    }
  }
}
"""

CONTRIBUTED_QUERY = REPO_FIELDS + """
query ($login: String!, $after: String, $authorId: ID!, $size: Int!) {
  user(login: $login) {
    repositoriesContributedTo(
      first: $size, after: $after,
      includeUserRepositories: false,
      contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { ...repoFields }
    }
  }
}
"""

# -------------------- FETCH --------------------

def graphql(query, variables):
    resp = requests.post(GITHUB_API, headers=HEADERS,
                         json={"query": query, "variables": variables})
    if resp.status_code != 200:
        print("GraphQL failed:", resp.status_code, resp.text[:300], file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    if data.get("errors"):
        # Missing scopes on a single private repo shouldn't kill the whole run.
        for err in data["errors"]:
            print("GraphQL warning:", err.get("message"), file=sys.stderr)
        if not data.get("data") or not data["data"].get("user"):
            sys.exit(1)
    return data["data"]


def fetch_author_id():
    return graphql(VIEWER_QUERY, {"login": USERNAME})["user"]["id"]


def my_commits(repo):
    """Commits authored by USERNAME on the repo's default branch."""
    branch = repo.get("defaultBranchRef")
    if not branch or not branch.get("target"):
        return 0
    return branch["target"].get("history", {}).get("totalCount", 0)


def fetch_page(query, field, author_id, cursor):
    variables = {"login": USERNAME, "after": cursor,
                 "authorId": author_id, "size": PAGE_SIZE}
    if field == "repositories":
        variables["affiliations"] = AFFILIATIONS
    page = graphql(query, variables)["user"][field]
    return page["nodes"], page["pageInfo"]


def fetch_repositories(author_id):
    """Owned + collaborator + contributed repos, deduplicated by nameWithOwner."""
    seen, repos = set(), []

    sources = [(OWNED_QUERY, "repositories")]
    if INCLUDE_CONTRIBUTED:
        sources.append((CONTRIBUTED_QUERY, "repositoriesContributedTo"))

    for query, field in sources:
        cursor = None
        while True:
            nodes, info = fetch_page(query, field, author_id, cursor)
            for repo in nodes:
                if not repo:
                    continue
                name = repo["nameWithOwner"]
                if name in seen:
                    continue
                if repo.get("isFork") and not INCLUDE_FORKS:
                    continue
                seen.add(name)
                repo["myCommits"] = my_commits(repo)
                repo["isMine"] = name.split("/")[0].lower() == USERNAME.lower()
                repos.append(repo)
            if not info["hasNextPage"]:
                break
            cursor = info["endCursor"]
    return repos

# -------------------- AGGREGATION --------------------

def repo_language_bytes(repo):
    """Every language GitHub reports, as-is — no exclusions, no remapping."""
    result = {}
    for edge in (repo.get("languages") or {}).get("edges", []):
        lang = edge["node"]["name"]
        result[lang] = result.get(lang, 0) + edge["size"]
    return result


def build_stats(repos):
    size_totals, activity_totals = {}, {}
    counted = 0
    for repo in repos:
        commits = repo["myCommits"]
        if SKIP_REPOS_WITHOUT_MY_COMMITS and commits == 0:
            continue
        lang_bytes = repo_language_bytes(repo)
        if not lang_bytes:
            continue
        counted += 1
        count_size = repo.get("isMine", True) or not SIZE_COUNTS_ONLY_OWNED_REPOS
        total_bytes = sum(lang_bytes.values()) or 1
        for lang, size in lang_bytes.items():
            if count_size:
                size_totals[lang] = size_totals.get(lang, 0) + size
            activity_totals[lang] = (activity_totals.get(lang, 0)
                                     + commits * (size / total_bytes))
    return size_totals, activity_totals, counted


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
        color = colors[i % len(colors)]

        def pt(r, a):
            return cx + r * math.cos(a), cy + r * math.sin(a)

        if frac >= 0.9995:  # single language: a normal arc would collapse
            d = (f"M{cx},{cy - r_outer} "
                 f"A{r_outer},{r_outer} 0 1 1 {cx - 0.01:.2f},{cy - r_outer} Z "
                 f"M{cx},{cy - r_inner} "
                 f"A{r_inner},{r_inner} 0 1 0 {cx - 0.01:.2f},{cy - r_inner} Z")
            result.append((d, color, label, 100))
            break

        a1, a2 = angle, angle + delta
        large  = 1 if delta > math.pi else 0
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
        pct_s = f"{pct:.1f}%" if pct >= 0.05 else "&lt;0.1%"
        display = xe(lang) if len(lang) <= 20 else xe(lang[:18] + "…")
        out += (f'<rect x="{x}" y="{y-9}" width="9" height="9" '
                f'fill="{color}" rx="1.5"/>\n')
        out += (f'<text x="{x+14}" y="{y}" font-size="11" fill="{TEXT_COLOR}" '
                f'font-family="monospace">{display}</text>\n')
        out += (f'<text x="{x+col_w-6}" y="{y}" font-size="11" fill="{MUTED_TEXT}" '
                f'font-family="monospace" text-anchor="end">{pct_s}</text>\n')
    return out

# -------------------- RENDER --------------------

def render_combined(repo_data, activity_data, scope_note=""):
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

    pie_h = max(len(repo_top) * 21 + LEG_START_Y, PIE_CY + R_OUTER + 16)

    ROSTER_SEP_Y = pie_h + 24
    ROSTER_TIT_Y = ROSTER_SEP_Y + 22
    ROSTER_Y_0   = ROSTER_TIT_Y + 26
    roster_rows  = math.ceil(len(repo_all) / COLS)
    TOTAL_H      = ROSTER_Y_0 + roster_rows * 22 + PAD

    top_color_map = {lang: REPO_COLORS[i % len(REPO_COLORS)]
                     for i, (lang, _) in enumerate(repo_top)}

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
        font-family="monospace">{xe(scope_note)}</text>

  <text x="{LEG_X_R}" y="26" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">Activity</text>
  <text x="{LEG_X_R}" y="42" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">my commits, split by byte share per repo</text>

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
    author_id = fetch_author_id()
    repos = fetch_repositories(author_id)

    pub   = sum(1 for r in repos if not r.get("isPrivate"))
    priv  = len(repos) - pub
    mine  = sum(1 for r in repos if r["isMine"])
    other = len(repos) - mine
    print(f"  {len(repos)} repos  ({pub} public · {priv} private)", file=sys.stderr)
    print(f"  {mine} owned · {other} contributed to", file=sys.stderr)

    repo_data, activity_data, counted = build_stats(repos)
    total_commits = sum(r["myCommits"] for r in repos)

    if not repo_data:
        print("No language data — check token scopes "
              "(`repo` + `read:org` needed for private and org repos).",
              file=sys.stderr)
        sys.exit(1)

    print(f"  {counted} repos counted · {total_commits} commits by @{USERNAME}",
          file=sys.stderr)
    print(f"  {len(repo_data)} distinct languages detected", file=sys.stderr)

    scope = "bytes across all repos I commit to · public + private"
    render_combined(repo_data, activity_data, scope_note=scope)
    print("Wrote", OUTPUT_FILE)


if __name__ == "__main__":
    main()
