#!/usr/bin/env python3
"""
bruh
"""
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
MAX_REPO_DISK_MB = 4096        # don't clone monsters; 0 disables the limit

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
# What to do when a notebook won't parse as JSON (Git LFS pointer, merge
# conflict markers, truncated file): "numstat" counts git's raw line numbers
# for that one change and flags it, "skip" drops the change.
ON_NOTEBOOK_PARSE_FAIL = "numstat"

# Which Linguist types count as work. GitHub's own language bar counts
# programming + markup, so leaving this as-is keeps both panels consistent.
# Add "prose" to count Markdown/AsciiDoc docs, "data" for JSON/YAML/config.
COUNTED_TYPES = {"programming", "markup"}

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
# Common code languages, most likely first, used when the repo itself gives no
# signal. Deliberately contains no data/prose languages: listing XML here would
# make .tsx resolve to XML instead of TSX, .res to XML instead of ReScript, and
# so on for every code language not in this list.
FALLBACK_PRIORITY = [
    "C", "C++", "Objective-C", "Objective-C++", "Python", "JavaScript",
    "TypeScript", "Java", "C#", "Go", "Rust", "Ruby", "PHP", "Perl", "Shell",
    "MATLAB", "R", "Fortran", "Verilog", "VHDL", "Assembly", "Pascal", "Lisp",
    "Scheme", "Prolog", "Swift", "Kotlin", "Haskell", "Lua", "Julia", "Zig",
    "HTML", "CSS", "TeX", "Makefile", "Wolfram Language",
]

# Extensions where the likeliest answer is NOT a programming language, so
# neither the priority list nor "prefer code over data" would get it right.
# .md is the important one: Linguist gives it to both Markdown (prose) and GCC
# Machine Description (programming), and without this line every README edit
# lands under GCC Machine Description.
AMBIGUOUS_DEFAULTS = {
    ".md": "Markdown",        ".sql": "SQL",       ".ddl": "SQL",
    ".prc": "SQL",            ".asc": "AsciiDoc",  ".srt": "SubRip Text",
    ".pkl": "Pickle",         ".pc": "pkg-config", ".dsc": "Debian Package Control File",
    ".ks": "Kickstart",       ".cue": "Cue Sheet", ".star": "STAR",
    ".spec": "RPM Spec",      ".msg": "ROS Interface",
    ".yml": "YAML",           ".yaml": "YAML",     ".txt": "Text",
    ".cfg": "INI",
}

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
# languages.yml (MIT). All Linguist languages are included, with each one's
# type (programming / markup / data / prose), because filtering here is what
# made README.md resolve to "GCC Machine Description". COUNTED_TYPES below
# decides what actually counts. Values are lists where an extension is
# ambiguous, resolved against the repo's own languages first.
# Compressed to keep this a single readable file. Do not hand-edit — use
# EXT_OVERRIDES above, or --regen-langmap to refresh from Linguist.
# --- BEGIN LANGMAP ---
_LANGMAP_B64 = """
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
J/r3v/8XUPJbIQ==
"""
# --- END LANGMAP ---


def _load_langmap():
    raw = zlib.decompress(base64.b64decode("".join(_LANGMAP_B64.split())))
    data = json.loads(raw.decode("utf-8"))
    ext, fname = data["ext"], data["filename"]
    types = data.get("types", {})   # tolerate a pre-types blob
    for key, value in EXT_OVERRIDES.items():
        ext[key.lower()] = [value] if isinstance(value, str) else list(value)
    for key, value in FILENAME_OVERRIDES.items():
        fname[key] = [value] if isinstance(value, str) else list(value)
    return ext, fname, types


EXT_TO_LANGS, FILENAME_TO_LANGS, LANGUAGE_TYPES = _load_langmap()

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

# --explain prints which files fed each language, so a surprising entry in the
# chart can be traced back to real paths instead of guessed at.
EXPLAIN = "--explain" in sys.argv
EXPLAIN_FILES = 8

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
    """(matched key, candidate languages) — key is a filename or an extension."""
    base = os.path.basename(path)
    if base in FILENAME_TO_LANGS:
        return base, FILENAME_TO_LANGS[base]
    parts = base.lower().split(".")
    for i in range(1, len(parts)):      # longest suffix first: .d.ts before .ts
        suffix = "." + ".".join(parts[i:])
        if suffix in EXT_TO_LANGS:
            return suffix, EXT_TO_LANGS[suffix]
    return None, []


def counts_as_code(lang):
    """Whether a resolved language counts toward the my-work panel."""
    return LANGUAGE_TYPES.get(lang, "programming") in COUNTED_TYPES


def language_for_path(path, repo_langs):
    """Map a file to a language. Ties are broken in order of trustworthiness:
    what GitHub already reports for this repo, then the curated trap table,
    then the priority list, then code over data, then alphabetically."""
    key, cands = candidates_for(path)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]

    overlap = [c for c in cands if c in repo_langs]
    pool = overlap or cands
    if len(pool) == 1:
        return pool[0]

    default = AMBIGUOUS_DEFAULTS.get(key)
    if default in pool:
        return default
    for preferred in FALLBACK_PRIORITY:
        if preferred in pool:
            return preferred
    code = [c for c in pool if counts_as_code(c)]
    return sorted(code or pool)[0]

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


def walk_history(repo_path, identities):
    """[(sha, path, old_path, added, deleted, binary)] for my commits.

    Uses -z (NUL-separated) rather than line-based numstat. Without it git
    quotes any path containing non-ASCII characters — "Übung 1.ipynb" arrives
    as "\\303\\234bung 1.ipynb", and every later `git show sha:path` for that
    file fails, which silently zeroed out notebook line counts. -z also emits
    renames as separate old/new fields, so no brace parsing is needed.
    """
    out = run_git(["log", "HEAD", "--no-merges", "--numstat", "-z", "-M",
                   "--format=%x01%H"] + author_filters(identities),
                  cwd=repo_path)
    tokens = out.split("\0")
    changes, sha, i = [], None, 0
    while i < len(tokens):
        token = tokens[i].strip("\n")
        if not token:
            i += 1
            continue
        if token.startswith("\x01"):
            sha = token[1:].strip()
            i += 1
            continue
        parts = token.split("\t")
        if len(parts) < 3 or sha is None:
            i += 1
            continue
        add, dele, path = parts[0], parts[1], parts[2]
        old_path = None
        if path == "":              # rename/copy: old and new follow as fields
            old_path = tokens[i + 1] if i + 1 < len(tokens) else None
            path = tokens[i + 2] if i + 2 < len(tokens) else ""
            i += 3
        else:
            i += 1
        if not path:
            continue
        binary = add == "-" or dele == "-"
        changes.append((sha, path, old_path or path, 0 if binary else int(add),
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


def notebook_diff(repo_path, sha, path, old_path=None):
    """Added/deleted code lines for one notebook change, outputs ignored.

    old_path matters for renames: looking the new name up in the parent commit
    would find nothing and count the whole notebook as freshly written.
    """
    old = blob_lines(repo_path, f"{sha}^", old_path or path)
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
        for sha, file_path, old_path, added, deleted, binary in changes:
            if is_generated(file_path):
                stats["generated_skipped"] += 1
                continue
            lang = language_for_path(file_path, repo_langs)
            if lang is None:
                ext = (os.path.splitext(file_path)[1].lower()
                       or os.path.basename(file_path))
                stats["unmapped"][ext] = stats["unmapped"].get(ext, 0) + 1
                continue
            if not counts_as_code(lang):
                kind = LANGUAGE_TYPES.get(lang, "?")
                key = f"{lang} ({kind})"
                stats["type_skipped"][key] = (stats["type_skipped"].get(key, 0)
                                              + count_lines(added, deleted))
                continue
            if file_path.lower().endswith(".ipynb") and STRIP_NOTEBOOK_OUTPUTS:
                try:
                    added, deleted = notebook_diff(path, sha, file_path,
                                                   old_path)
                    stats["notebook_diffs"] += 1
                except ValueError:
                    stats["notebook_failed"] += 1
                    if ON_NOTEBOOK_PARSE_FAIL != "numstat" or binary:
                        continue
            elif binary:
                continue
            counted = count_lines(added, deleted)
            lines[lang] = lines.get(lang, 0) + counted
            if EXPLAIN:
                per_lang = stats["explain"].setdefault(lang, {})
                key = f"{name}/{file_path}"
                per_lang[key] = per_lang.get(key, 0) + counted
    finally:
        # Reclaim disk as we go rather than holding every clone until the end.
        shutil.rmtree(path, ignore_errors=True)
    return lines


def build_stats(repos, workdir, identities):
    reach, work = {}, {}
    stats = {"unmapped": {}, "generated_skipped": 0, "notebook_diffs": 0,
             "notebook_failed": 0, "skipped_clone": 0, "skipped_size": 0,
             "repos_counted": 0, "type_skipped": {}, "explain": {}}

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

    # Every type is included — filtering at generation time is what made .md
    # resolve to "GCC Machine Description" (the only *programming* language
    # claiming .md) once Markdown, a *prose* language, had been dropped.
    # What gets counted is decided later, by COUNTED_TYPES.
    ext, fname, types = {}, {}, {}
    for name, info in sorted(spec.items()):
        kind = info.get("type")
        if not kind:
            continue
        types[name] = kind
        for e in info.get("extensions", []):
            ext.setdefault(e.lower(), []).append(name)
        for f in info.get("filenames", []):
            fname.setdefault(f, []).append(name)

    payload = json.dumps({"ext": ext, "filename": fname, "types": types},
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
    print(f"Updated embedded map: {len(types)} languages, {len(ext)} "
          f"extensions, {len(fname)} filenames")

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
    if stats["notebook_failed"]:
        action = ("counted from raw numstat"
                  if ON_NOTEBOOK_PARSE_FAIL == "numstat" else "dropped")
        print(f"  {stats['notebook_failed']} notebooks would not parse "
              f"({action}) — Git LFS pointers or conflict markers?",
              file=sys.stderr)
    if stats["skipped_size"] or stats["skipped_clone"]:
        print(f"  repos with no line data: {stats['skipped_size']} over the "
              f"size limit, {stats['skipped_clone']} failed to clone — these "
              f"still count for reach, which is why a language can show reach "
              f"but no lines", file=sys.stderr)
    if stats["generated_skipped"]:
        print(f"  {stats['generated_skipped']} generated-path changes ignored",
              file=sys.stderr)
    if stats["type_skipped"]:
        worst = sorted(stats["type_skipped"].items(), key=lambda kv: -kv[1])[:6]
        print("  not counted, type not in COUNTED_TYPES: "
              + ", ".join(f"{k} {abbrev(v)}" for k, v in worst), file=sys.stderr)
    if stats["unmapped"]:
        worst = sorted(stats["unmapped"].items(), key=lambda kv: -kv[1])[:8]
        print("  unmapped file types (add to EXT_OVERRIDES if wanted): "
              + ", ".join(f"{e}×{n}" for e, n in worst), file=sys.stderr)
    if EXPLAIN:
        print("\n--- where each language's lines came from ---", file=sys.stderr)
        for lang, _ in ranked(work):
            paths = sorted(stats["explain"].get(lang, {}).items(),
                           key=lambda kv: -kv[1])
            print(f"{lang}  ({abbrev(work[lang])} lines, "
                  f"{len(paths)} files)", file=sys.stderr)
            for file_path, count in paths[:EXPLAIN_FILES]:
                print(f"    {abbrev(count):>7}  {file_path}", file=sys.stderr)

    render(reach, work, summary)
    print("Wrote", OUTPUT_FILE)


if __name__ == "__main__":
    if "--regen-langmap" in sys.argv:
        regen_langmap()
    else:
        main()
