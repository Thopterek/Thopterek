#!/usr/bin/env python3
import base64
import difflib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

import requests

# -------------------- CONFIG --------------------
TOP_N = 10          # slices before the "Other" bucket
SHOW_OTHER = True   # group the tail into one slice instead of hiding it

# Which repos to look at
INCLUDE_CONTRIBUTED = True     # repos you don't own but have committed to
INCLUDE_COLLABORATOR = True    # collaborator / org-member repos
INCLUDE_FORKS = False
SKIP_REPOS_WITHOUT_MY_COMMITS = True
MAX_REPO_DISK_MB = 1024        # don't clone monsters; 0 disables the limit

# Reach panel
# A language counts for a repo if GitHub reports it at all. Raise this to, say,
# 0.01 to ignore languages under 1% of a repo — kills the "one stray HTML file
# makes HTML a language I use" effect. 0.0 counts every appearance.
REACH_MIN_SHARE = 0.0
# True = a language only counts for a repo if you actually touched files in it.
REACH_ONLY_LANGUAGES_I_TOUCHED = False

# My-work panel
COUNT_MODE = "added+deleted"   # or "added"
STRIP_NOTEBOOK_OUTPUTS = True
INCLUDE_NOTEBOOK_MARKDOWN = False

# Paths that are checked in but not written by hand. These are paths, not
# languages — nothing disappears from the roster unless it exists only here.
# Empty this list if you'd rather count everything.
GENERATED_PATH_PATTERNS = [
    r"(^|/)node_modules/", r"(^|/)vendor/", r"(^|/)third_party/",
    r"(^|/)dist/", r"(^|/)build/", r"(^|/)\.venv/", r"(^|/)site-packages/",
    r"\.min\.(js|css)$", r"\.bundle\.js$", r"\.map$",
    r"_pb2\.pyi?$", r"\.pb\.go$", r"(^|/)generated/",
]

# Hand additions to the embedded map, applied last. Use for file types Linguist
# doesn't know or that you want attributed differently:
#   {".foo": "Python", ".h": "C++"}
EXT_OVERRIDES = {}
FILENAME_OVERRIDES = {}

# Picked when a repo's own languages don't settle an ambiguous extension
# (.h is C, C++ or Objective-C; .m is Objective-C, MATLAB and five others).
FALLBACK_PRIORITY = [
    "C", "C++", "Objective-C", "Python", "JavaScript", "TypeScript", "Java",
    "C#", "Go", "Rust", "Ruby", "PHP", "Perl", "Shell", "MATLAB", "R",
    "Fortran", "Verilog", "Assembly", "Pascal", "Lisp", "Scheme", "Prolog",
    "TSQL", "Swift", "Kotlin", "Haskell", "Lua", "Julia",
]

# Visuals
BG_COLOR    = "#0b0f1a"
TEXT_COLOR  = "#e5e7eb"
MUTED_TEXT  = "#6b7280"
BORDER      = "#1f2937"
ROSTER_DIM  = "#374151"
OTHER_COLOR = "#4b5563"

REACH_COLORS = ["#f97316","#eab308","#22c55e","#fb7185","#a78bfa",
                "#f43f5e","#84cc16","#fbbf24","#34d399","#c084fc"]
WORK_COLORS  = ["#06b6d4","#6366f1","#00c2a8","#ff6b6b","#ffd166",
                "#38bdf8","#818cf8","#2dd4bf","#fb923c","#e879f9"]

OUTPUT_FILE = "languages-overview.svg"
PAGE_SIZE = 50
CLONE_TIMEOUT = 600
GIT_TIMEOUT = 300
# ------------------------------------------------

# ══════════════════════════════════════════════════════════════════════════
# Extension/filename -> language map, generated from github-linguist's
# languages.yml (MIT). Only `programming` and `markup` languages are included,
# the same set GitHub counts in a repo's language bar; data and prose types
# (JSON, YAML, Markdown) are absent so the "my work" panel covers the same
# languages as "reach". Values are lists where an extension is ambiguous.
# Compressed to keep this a single readable file. Do not hand-edit — use
# EXT_OVERRIDES above, or --regen-langmap to refresh from Linguist.
# --- BEGIN LANGMAP ---
_LANGMAP_B64 = """
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
qAzZKYNmyoCVEhop//rX/wGwrDX0
"""
# --- END LANGMAP ---


def _load_langmap():
    raw = zlib.decompress(base64.b64decode("".join(_LANGMAP_B64.split())))
    data = json.loads(raw.decode("utf-8"))
    ext, fname = data["ext"], data["filename"]
    for key, value in EXT_OVERRIDES.items():
        ext[key.lower()] = [value] if isinstance(value, str) else list(value)
    for key, value in FILENAME_OVERRIDES.items():
        fname[key] = [value] if isinstance(value, str) else list(value)
    return ext, fname


EXT_TO_LANGS, FILENAME_TO_LANGS = _load_langmap()

TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API = "https://api.github.com/graphql"
USERNAME = os.environ.get("GH_USERNAME",
           os.environ.get("GITHUB_REPOSITORY", "").split("/")[0])
HEADERS = {"Authorization": f"bearer {TOKEN}",
           "Accept": "application/vnd.github+json"}

AFFILIATIONS = ["OWNER"]
if INCLUDE_COLLABORATOR:
    AFFILIATIONS += ["COLLABORATOR", "ORGANIZATION_MEMBER"]

GENERATED_RE = [re.compile(p) for p in GENERATED_PATH_PATTERNS]

# -------------------- GRAPHQL --------------------

REPO_FIELDS = """
fragment repoFields on Repository {
  nameWithOwner
  isPrivate
  isFork
  diskUsage
  languages(first: 100) {
    edges { size node { name } }
  }
  defaultBranchRef {
    name
    target {
      ... on Commit {
        history(author: {id: $authorId}, first: 5) {
          totalCount
          nodes { author { email name } }
        }
      }
    }
  }
}
"""

VIEWER_QUERY = "query ($login: String!) { user(login: $login) { id login name } }"

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


def graphql(query, variables):
    resp = requests.post(GITHUB_API, headers=HEADERS,
                         json={"query": query, "variables": variables})
    if resp.status_code != 200:
        print("GraphQL failed:", resp.status_code, resp.text[:300], file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    if data.get("errors"):
        for err in data["errors"]:
            print("GraphQL warning:", err.get("message"), file=sys.stderr)
        if not data.get("data") or not data["data"].get("user"):
            sys.exit(1)
    return data["data"]


def fetch_me():
    return graphql(VIEWER_QUERY, {"login": USERNAME})["user"]


def my_commit_info(repo):
    """(commit count, set of author emails) for commits authored by me."""
    branch = repo.get("defaultBranchRef") or {}
    target = branch.get("target") or {}
    history = target.get("history") or {}
    emails = set()
    for node in history.get("nodes") or []:
        email = ((node or {}).get("author") or {}).get("email")
        if email:
            emails.add(email.lower())
    return history.get("totalCount", 0), emails


def fetch_page(query, field, author_id, cursor):
    variables = {"login": USERNAME, "after": cursor,
                 "authorId": author_id, "size": PAGE_SIZE}
    if field == "repositories":
        variables["affiliations"] = AFFILIATIONS
    page = graphql(query, variables)["user"][field]
    return page["nodes"], page["pageInfo"]


def fetch_repositories(author_id):
    """Owned + collaborator + contributed repos, deduped by nameWithOwner."""
    seen, repos, emails = set(), [], set()

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
                count, found = my_commit_info(repo)
                emails |= found
                repo["myCommits"] = count
                repo["branch"] = (repo.get("defaultBranchRef") or {}).get("name")
                repo["isMine"] = name.split("/")[0].lower() == USERNAME.lower()
                repos.append(repo)
            if not info["hasNextPage"]:
                break
            cursor = info["endCursor"]
    return repos, emails

# -------------------- LANGUAGE MAPPING --------------------

def head_languages(repo):
    """{language: bytes} exactly as GitHub reports it. No remapping."""
    out = {}
    for edge in (repo.get("languages") or {}).get("edges", []):
        name = edge["node"]["name"]
        out[name] = out.get(name, 0) + edge["size"]
    return out


def is_generated(path):
    return any(rx.search(path) for rx in GENERATED_RE)


def candidates_for(path):
    base = os.path.basename(path)
    if base in FILENAME_TO_LANGS:
        return FILENAME_TO_LANGS[base]
    parts = base.lower().split(".")
    for i in range(1, len(parts)):      # longest suffix first: .d.ts before .ts
        suffix = "." + ".".join(parts[i:])
        if suffix in EXT_TO_LANGS:
            return EXT_TO_LANGS[suffix]
    return []


def language_for_path(path, repo_langs):
    """Map a file to a language, using the repo's own languages to break ties."""
    cands = candidates_for(path)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    overlap = [c for c in cands if c in repo_langs]
    pool = overlap or cands
    if len(pool) == 1:
        return pool[0]
    for preferred in FALLBACK_PRIORITY:
        if preferred in pool:
            return preferred
    return sorted(pool)[0]

# -------------------- GIT --------------------

def redact(text):
    return text.replace(TOKEN, "***") if TOKEN else text


def run_git(args, cwd=None, timeout=GIT_TIMEOUT, check=True):
    proc = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(redact(proc.stderr.strip()[:300]))
    return proc.stdout


def clone_url(name_with_owner):
    return f"https://x-access-token:{TOKEN}@github.com/{name_with_owner}.git"


def clone_repo(repo, workdir):
    """Bare, single-branch clone into the throwaway work directory."""
    name = repo["nameWithOwner"]
    path = os.path.join(workdir, name.replace("/", "__") + ".git")
    args = ["clone", "--quiet", "--bare", "--single-branch", "--no-tags"]
    if repo.get("branch"):
        args += ["--branch", repo["branch"]]
    args += [clone_url(name), path]
    run_git(args, timeout=CLONE_TIMEOUT)
    return path


def author_filters(identities):
    return [f"--author={i}" for i in sorted(identities)]


def resolve_rename(path):
    """numstat renames: 'a => b' and 'src/{old => new}/f.c'."""
    if "{" in path and " => " in path:
        prefix, rest = path.split("{", 1)
        middle, suffix = rest.split("}", 1)
        new = middle.split(" => ")[-1]
        return re.sub(r"//+", "/", prefix + new + suffix)
    if " => " in path:
        return path.split(" => ")[-1]
    return path


def walk_history(repo_path, identities):
    """[(sha, path, added, deleted, binary)] for my commits on the branch."""
    out = run_git(["log", "HEAD", "--no-merges", "--numstat", "-M",
                   "--format=%x01%H"] + author_filters(identities),
                  cwd=repo_path)
    changes, sha = [], None
    for line in out.splitlines():
        if line.startswith("\x01"):
            sha = line[1:].strip()
            continue
        if not line.strip() or sha is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add, dele = parts[0], parts[1]
        path = resolve_rename("\t".join(parts[2:]))
        binary = add == "-" or dele == "-"
        changes.append((sha, path, 0 if binary else int(add),
                        0 if binary else int(dele), binary))
    return changes

# -------------------- NOTEBOOKS --------------------

def notebook_code_lines(text):
    """Source lines of code cells only — no outputs, no execution counts."""
    nb = json.loads(text)
    cells = nb.get("cells")
    if cells is None:                   # nbformat v3
        cells = [c for ws in nb.get("worksheets", []) for c in ws.get("cells", [])]
    wanted = {"code"} | ({"markdown"} if INCLUDE_NOTEBOOK_MARKDOWN else set())
    lines = []
    for cell in cells:
        if cell.get("cell_type") not in wanted:
            continue
        src = cell.get("source", cell.get("input", []))
        if isinstance(src, str):
            src = src.splitlines()
        lines.extend(str(s).rstrip("\n") for s in src)
    return lines


def blob_lines(repo_path, ref, path):
    """Code lines of a notebook blob; empty list if the blob doesn't exist."""
    try:
        text = run_git(["show", f"{ref}:{path}"], cwd=repo_path)
    except (RuntimeError, subprocess.TimeoutExpired):
        return []
    try:
        return notebook_code_lines(text)
    except (json.JSONDecodeError, AttributeError, TypeError):
        raise ValueError("unparseable notebook")


def notebook_diff(repo_path, sha, path):
    """Added/deleted code lines for one notebook change, outputs ignored."""
    old = blob_lines(repo_path, f"{sha}^", path)
    new = blob_lines(repo_path, sha, path)
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    added = deleted = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            deleted += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, deleted

# -------------------- AGGREGATION --------------------

def count_lines(added, deleted):
    return added if COUNT_MODE == "added" else added + deleted


def measure_repo(repo, workdir, identities, stats):
    """Line counts per language for one repo. Returns {} if it can't be read."""
    name = repo["nameWithOwner"]
    disk_mb = (repo.get("diskUsage") or 0) / 1024
    if MAX_REPO_DISK_MB and disk_mb > MAX_REPO_DISK_MB:
        print(f"  skip {name}: {disk_mb:.0f} MB over MAX_REPO_DISK_MB",
              file=sys.stderr)
        stats["skipped_size"] += 1
        return {}
    path = None
    try:
        path = clone_repo(repo, workdir)
        changes = walk_history(path, identities)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"  skip {name}: {redact(str(exc))}", file=sys.stderr)
        stats["skipped_clone"] += 1
        return {}

    repo_langs = head_languages(repo)
    lines = {}
    try:
        for sha, file_path, added, deleted, binary in changes:
            if is_generated(file_path):
                stats["generated_skipped"] += 1
                continue
            lang = language_for_path(file_path, repo_langs)
            if lang is None:
                ext = (os.path.splitext(file_path)[1].lower()
                       or os.path.basename(file_path))
                stats["unmapped"][ext] = stats["unmapped"].get(ext, 0) + 1
                continue
            if file_path.lower().endswith(".ipynb") and STRIP_NOTEBOOK_OUTPUTS:
                try:
                    added, deleted = notebook_diff(path, sha, file_path)
                    stats["notebook_diffs"] += 1
                except ValueError:
                    stats["notebook_failed"] += 1
                    continue
            elif binary:
                continue
            lines[lang] = lines.get(lang, 0) + count_lines(added, deleted)
    finally:
        # Reclaim disk as we go rather than holding every clone until the end.
        shutil.rmtree(path, ignore_errors=True)
    return lines


def build_stats(repos, workdir, identities):
    reach, work = {}, {}
    stats = {"unmapped": {}, "generated_skipped": 0, "notebook_diffs": 0,
             "notebook_failed": 0, "skipped_clone": 0, "skipped_size": 0,
             "repos_counted": 0}

    for repo in repos:
        if SKIP_REPOS_WITHOUT_MY_COMMITS and repo["myCommits"] == 0:
            continue
        head = head_languages(repo)
        if not head:
            continue
        stats["repos_counted"] += 1

        my_lines = measure_repo(repo, workdir, identities, stats)
        for lang, count in my_lines.items():
            if count:
                work[lang] = work.get(lang, 0) + count

        total_bytes = sum(head.values()) or 1
        for lang, size in head.items():
            if size / total_bytes < REACH_MIN_SHARE:
                continue
            if REACH_ONLY_LANGUAGES_I_TOUCHED and lang not in my_lines:
                continue
            reach[lang] = reach.get(lang, 0) + 1

    return reach, work, stats


def ranked(data):
    return sorted(data.items(), key=lambda kv: (-kv[1], kv[0]))

# -------------------- SVG HELPERS --------------------

def xe(s):
    """XML-escape so C++, C#, F# and friends render safely."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def abbrev(n):
    n = round(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1000:.0f}k"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def top_with_other(items):
    """Top TOP_N entries plus a synthetic Other row for the tail."""
    top, tail = items[:TOP_N], items[TOP_N:]
    if SHOW_OTHER and tail:
        top = top + [(f"Other ({len(tail)} langs)", sum(v for _, v in tail))]
    return top, tail


def pie_paths(data, cx, cy, r_outer, r_inner, colors, other_index=None):
    total = sum(v for _, v in data) or 1
    angle = -math.pi / 2
    result = []
    for i, (label, value) in enumerate(data):
        frac = value / total
        delta = frac * 2 * math.pi
        color = OTHER_COLOR if i == other_index else colors[i % len(colors)]

        def pt(r, a):
            return cx + r * math.cos(a), cy + r * math.sin(a)

        if frac >= 0.9995:      # one language owns everything; arcs would collapse
            d = (f"M{cx},{cy - r_outer} "
                 f"A{r_outer},{r_outer} 0 1 1 {cx - 0.01:.2f},{cy - r_outer} Z "
                 f"M{cx},{cy - r_inner} "
                 f"A{r_inner},{r_inner} 0 1 0 {cx - 0.01:.2f},{cy - r_inner} Z")
            result.append((d, color, label, value))
            break

        a1, a2 = angle, angle + delta
        large = 1 if delta > math.pi else 0
        x1, y1 = pt(r_outer, a1); x2, y2 = pt(r_outer, a2)
        x3, y3 = pt(r_inner, a2); x4, y4 = pt(r_inner, a1)
        d = (f"M{x1:.2f},{y1:.2f} "
             f"A{r_outer},{r_outer} 0 {large} 1 {x2:.2f},{y2:.2f} "
             f"L{x3:.2f},{y3:.2f} "
             f"A{r_inner},{r_inner} 0 {large} 0 {x4:.2f},{y4:.2f} Z")
        result.append((d, color, label, value))
        angle = a2
    return result


def legend_svg(x, y, items, fmt, value_x_offset=170):
    out = ""
    for i, (_, color, label, value) in enumerate(items):
        yy = y + i * 21
        display = xe(label) if len(label) <= 20 else xe(label[:18] + "…")
        out += (f'<rect x="{x}" y="{yy-11}" width="10" height="10" '
                f'fill="{color}" rx="2"/>\n')
        out += (f'<text x="{x+15}" y="{yy-1}" font-size="11" fill="{TEXT_COLOR}" '
                f'font-family="monospace">{display}</text>\n')
        out += (f'<text x="{x+value_x_offset}" y="{yy-1}" font-size="11" '
                f'fill="{MUTED_TEXT}" font-family="monospace" '
                f'text-anchor="end">{xe(fmt(value))}</text>\n')
    return out


def roster_svg(rows, color_map, x_start, y_start, total_w, cols):
    col_w = (total_w - x_start * 2) // cols
    out = ""
    for idx, (lang, reach_n, lines_n) in enumerate(rows):
        col, row = idx % cols, idx // cols
        x = x_start + col * col_w
        y = y_start + row * 22
        color = color_map.get(lang, ROSTER_DIM)
        value = f"{reach_n}× · {abbrev(lines_n)}" if lines_n else f"{reach_n}× · —"
        display = xe(lang) if len(lang) <= 18 else xe(lang[:16] + "…")
        out += (f'<rect x="{x}" y="{y-9}" width="9" height="9" '
                f'fill="{color}" rx="1.5"/>\n')
        out += (f'<text x="{x+14}" y="{y}" font-size="11" fill="{TEXT_COLOR}" '
                f'font-family="monospace">{display}</text>\n')
        out += (f'<text x="{x+col_w-6}" y="{y}" font-size="11" fill="{MUTED_TEXT}" '
                f'font-family="monospace" text-anchor="end">{xe(value)}</text>\n')
    return out

# -------------------- RENDER --------------------

def render(reach, work, summary):
    reach_all, work_all = ranked(reach), ranked(work)
    reach_top, reach_tail = top_with_other(reach_all)
    work_top, work_tail = top_with_other(work_all)

    W, PAD, COLS = 880, 30, 3
    LEG_X_L, LEG_X_R = PAD, 468
    PIE_CX_L, PIE_CX_R = 318, 756
    PIE_CY, R_OUTER, R_INNER = 180, 92, 58
    LEG_START_Y = 72

    rows = max(len(reach_top), len(work_top))
    pie_h = max(rows * 21 + LEG_START_Y, PIE_CY + R_OUTER + 16)

    SEP_Y = pie_h + 24
    TITLE_Y = SEP_Y + 22
    ROSTER_Y = TITLE_Y + 26

    all_langs = sorted(set(reach) | set(work),
                       key=lambda l: (-reach.get(l, 0), -work.get(l, 0), l))
    roster_rows = [(l, reach.get(l, 0), work.get(l, 0)) for l in all_langs]
    n_rows = math.ceil(len(roster_rows) / COLS)
    FOOTER_Y = ROSTER_Y + n_rows * 22 + 18
    TOTAL_H = FOOTER_Y + PAD - 8

    reach_other = len(reach_top) - 1 if reach_tail and SHOW_OTHER else None
    work_other = len(work_top) - 1 if work_tail and SHOW_OTHER else None

    color_map = {lang: REACH_COLORS[i % len(REACH_COLORS)]
                 for i, (lang, _) in enumerate(reach_all[:TOP_N])}

    reach_paths = pie_paths(reach_top, PIE_CX_L, PIE_CY, R_OUTER, R_INNER,
                            REACH_COLORS, reach_other)
    work_paths = pie_paths(work_top, PIE_CX_R, PIE_CY, R_OUTER, R_INNER,
                           WORK_COLORS, work_other)

    mid_x = (PIE_CX_L + R_OUTER + LEG_X_R) // 2
    unit = "lines added + deleted" if COUNT_MODE != "added" else "lines added"

    svg = f'''<svg width="{W}" height="{TOTAL_H}" viewBox="0 0 {W} {TOTAL_H}"
     xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{BG_COLOR}" rx="14"/>

  <!-- ══ PIE PANELS ══════════════════════════════════════════ -->
  <text x="{LEG_X_L}" y="26" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">Reach</text>
  <text x="{LEG_X_L}" y="42" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">repos each language appears in</text>

  <text x="{LEG_X_R}" y="26" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">My work</text>
  <text x="{LEG_X_R}" y="42" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">{unit} by me · notebook outputs stripped</text>

  <line x1="{mid_x}" y1="14" x2="{mid_x}" y2="{pie_h + 10}"
        stroke="{BORDER}" stroke-width="1"/>

  {legend_svg(LEG_X_L, LEG_START_Y, reach_paths, lambda v: f"{round(v)}×")}
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in reach_paths)}

  {legend_svg(LEG_X_R, LEG_START_Y, work_paths, abbrev)}
  {''.join(f'<path d="{d}" fill="{c}"/>' for d, c, _, _ in work_paths)}

  <!-- ══ ROSTER ═══════════════════════════════════════════════ -->
  <line x1="{PAD}" y1="{SEP_Y}" x2="{W - PAD}" y2="{SEP_Y}"
        stroke="{BORDER}" stroke-width="1"/>

  <text x="{PAD}" y="{TITLE_Y}" font-size="13" font-weight="bold"
        fill="{TEXT_COLOR}" font-family="monospace">All languages detected</text>
  <text x="{W - PAD}" y="{TITLE_Y}" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace" text-anchor="end"
        >repos × · lines · highlighted = top {TOP_N} by reach</text>

  {roster_svg(roster_rows, color_map, PAD, ROSTER_Y, W, COLS)}

  <text x="{PAD}" y="{FOOTER_Y}" font-size="10" fill="{MUTED_TEXT}"
        font-family="monospace">{xe(summary)}</text>
</svg>'''

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

# -------------------- LANGMAP REGENERATION --------------------

def regen_langmap():
    """Rebuild the embedded map from Linguist and rewrite this file in place."""
    import textwrap
    try:
        import yaml
    except ImportError:
        print("Needs PyYAML:  pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    url = ("https://raw.githubusercontent.com/github-linguist/linguist/"
           "main/lib/linguist/languages.yml")
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        print("Download failed:", resp.status_code, file=sys.stderr)
        sys.exit(1)
    spec = yaml.safe_load(resp.text)

    ext, fname = {}, {}
    for name, info in sorted(spec.items()):
        if info.get("type") not in {"programming", "markup"}:
            continue
        for e in info.get("extensions", []):
            ext.setdefault(e.lower(), []).append(name)
        for f in info.get("filenames", []):
            fname.setdefault(f, []).append(name)

    payload = json.dumps({"ext": ext, "filename": fname},
                         separators=(",", ":"), sort_keys=True)
    blob = base64.b64encode(zlib.compress(payload.encode("utf-8"), 9)).decode()
    wrapped = "\n" + "\n".join(textwrap.wrap(blob, 76)) + "\n"

    # Sentinels are assembled here so they don't match this code itself.
    begin = "# --- BEGIN " + "LANGMAP ---\n"
    end = "# --- END " + "LANGMAP ---"
    path = os.path.abspath(__file__)
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    if begin not in source or end not in source:
        print("Couldn't find the langmap markers in this file.", file=sys.stderr)
        sys.exit(1)
    head = source.split(begin)[0] + begin
    tail = end + source.split(end, 1)[1]
    new_source = f'{head}_LANGMAP_B64 = """{wrapped}"""\n{tail}'

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(new_source)
    os.replace(tmp, path)
    langs = sum(1 for i in spec.values()
                if i.get("type") in {"programming", "markup"})
    print(f"Updated embedded map: {langs} languages, {len(ext)} extensions, "
          f"{len(fname)} filenames")

# -------------------- MAIN --------------------

def main():
    if not TOKEN:
        print("Error: GITHUB_TOKEN not set.", file=sys.stderr)
        sys.exit(1)
    if not USERNAME:
        print("Error: Set GH_USERNAME or run inside a repo context.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Fetching repos for @{USERNAME} …", file=sys.stderr)
    me = fetch_me()
    repos, emails = fetch_repositories(me["id"])

    identities = {e for e in emails if e}
    identities |= {e.strip().lower()
                   for e in os.environ.get("GH_EMAILS", "").split(",") if e.strip()}
    if not identities:
        identities = {USERNAME}
        print("  no commit emails found; matching by username only",
              file=sys.stderr)

    pub = sum(1 for r in repos if not r.get("isPrivate"))
    mine = sum(1 for r in repos if r["isMine"])
    print(f"  {len(repos)} repos ({pub} public · {len(repos)-pub} private · "
          f"{mine} owned · {len(repos)-mine} contributed)", file=sys.stderr)
    print(f"  matching commits by: {', '.join(sorted(identities))}", file=sys.stderr)

    workdir = tempfile.mkdtemp(prefix="langstats-")
    try:
        reach, work, stats = build_stats(repos, workdir, identities)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not reach:
        print("No language data — check token scopes "
              "(`repo` + `read:org` for private and org repos).", file=sys.stderr)
        sys.exit(1)

    commits = sum(r["myCommits"] for r in repos)
    total_lines = round(sum(work.values()))
    summary = (f"{stats['repos_counted']} repos · {commits:,} commits by "
               f"@{USERNAME} · {total_lines:,} lines · "
               f"{len(set(reach) | set(work))} languages")

    print(f"  {summary}", file=sys.stderr)
    if stats["notebook_diffs"]:
        print(f"  {stats['notebook_diffs']} notebook diffs stripped of outputs",
              file=sys.stderr)
    if stats["generated_skipped"]:
        print(f"  {stats['generated_skipped']} generated-path changes ignored",
              file=sys.stderr)
    if stats["unmapped"]:
        worst = sorted(stats["unmapped"].items(), key=lambda kv: -kv[1])[:8]
        print("  unmapped file types (add to EXT_OVERRIDES if wanted): "
              + ", ".join(f"{e}×{n}" for e, n in worst), file=sys.stderr)

    render(reach, work, summary)
    print("Wrote", OUTPUT_FILE)


if __name__ == "__main__":
    if "--regen-langmap" in sys.argv:
        regen_langmap()
    else:
        main()
