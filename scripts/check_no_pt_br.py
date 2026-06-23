#!/usr/bin/env python3
"""Pre-commit hook: detect Portuguese (pt-BR) leaking into repo-public files.

This project targets EU-remote roles where English is the working language.
Mixed-language artifacts in a public repo dilute the portfolio signal.

The check looks for two classes of evidence:

1. **Diacritics** - characters like a e i o u a o c with accents that appear
   almost exclusively in pt-BR (and other Romance languages) inside this
   project's context. Detection is a strong signal.

2. **PT-BR keywords without diacritics** - common Portuguese words with no
   English homograph that slip past diacritic scanning (e.g., "execucao"
   typed without its accent).

Scope:

- With filenames as arguments (the pre-commit path), only those files are
  scanned. Pre-commit passes the staged, tracked files it selected by type.
- Without arguments (the Makefile/CI path), the scan covers the files tracked
  by git, matching the configured extensions. Internal-only documents are
  gitignored, so they are never tracked and never scanned - no per-file
  exclusion list is needed.

Generated directories and binary files are skipped (the former are not tracked;
the latter are detected via decode failure).

Usage (manual):
    python scripts/check_no_pt_br.py [file1.py file2.tf ...]

Pre-commit hook entry (wired in `.pre-commit-config.yaml`):
    - id: check-no-pt-br
      entry: python scripts/check_no_pt_br.py
      language: system
      pass_filenames: true

Exit codes:
    0 - clean
    1 - at least one PT-BR finding (commit blocked)
    2 - internal error
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

# ─── WHAT COUNTS AS PT-BR ─────────────────────────────────────────────────────

PT_DIACRITICS: Final[frozenset[str]] = frozenset("áéíóúâêîôûãõàçÁÉÍÓÚÂÊÎÔÛÃÕÀÇ")

# Words common in PT-BR with no English homograph. Case-insensitive matching.
# Conservative by design - in a commit-blocking hook, a false positive (blocking
# a valid English commit) is worse than a missed catch, so every entry here must
# be a token that does not also occur in normal English or technical usage.
PT_KEYWORDS: Final[tuple[str, ...]] = (
    # Verbs and participles with no English homograph
    r"\busadas?\b",
    r"\busados?\b",
    r"\bsera\b",
    r"\bserao\b",
    r"\bgeradas?\b",
    r"\bgerados?\b",
    r"\bcompactadas?\b",
    r"\bcompactados?\b",
    r"\bsubstitui\b",
    r"\badicionado\b",
    r"\badicionada\b",
    r"\bremovido\b",
    r"\bremovida\b",
    # Nouns with no English homograph
    r"\bmodulo\b",
    r"\bmodulos\b",
    r"\bvariavel\b",
    r"\bvariaveis\b",
    r"\bexecucao\b",
    r"\bversao\b",
    r"\bversoes\b",
    r"\bregiao\b",
    r"\bregioes\b",
    r"\bpacote\b",
    r"\bpacotes\b",
    r"\barquivo\b",
    r"\barquivos\b",
    r"\bsenha\b",
    # Adjectives with no English homograph
    r"\breproduzivel\b",
    r"\breproduziveis\b",
    r"\bminimo\b",
    r"\bminima\b",
    r"\bconfiguravel\b",
    r"\bconfiguraveis\b",
    r"\bmoderno\b",
    r"\bmoderna\b",
    r"\brecomendado\b",
    r"\brecomendada\b",
    r"\bopcional\b",
    r"\bnecessario\b",
    r"\bnecessaria\b",
    r"\bproprio\b",
    r"\bpropria\b",
    # Function words distinctive in PT-BR (no English homograph)
    r"\bnao\b",
    r"\btambem\b",
    r"\bporque\b",
    r"\bentao\b",
    r"\bfuturo\b",
    # Phrases that strongly indicate PT-BR
    r"\bpath_dados\b",
    r"\blinha\s+de\s+comando\b",
    r"\bcomentar\s+resultados\b",
    r"\bcancela\s+runs\b",
    r"\bfalha\s+o\s+ci\b",
    r"\btoda\s+(segunda|terca|quarta|quinta|sexta)\b",
)

# Compile once for performance.
_PT_KEYWORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    "|".join(PT_KEYWORDS),
    re.IGNORECASE,
)

# ─── WHAT FILES ARE SCANNED ───────────────────────────────────────────────────

# Extensions scanned when no explicit filenames are passed.
DEFAULT_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".tf",
        ".tfvars",
        ".sh",
        ".bash",
        ".md",
        ".yml",
        ".yaml",
        ".toml",
        ".cfg",
        ".ini",
        ".json",
        ".example",
    }
)

# Extensionless filenames that should be scanned.
DEFAULT_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "Makefile",
        "Dockerfile",
    }
)

# This script holds PT-BR diacritics and keywords in its own detection rules,
# so it must never scan itself.
SELF_NAME: Final[str] = "check_no_pt_br.py"


# ─── CORE ─────────────────────────────────────────────────────────────────────


def in_scope_by_name(path: Path) -> bool:
    """Decide whether a path's name/extension is in scope for the check."""
    if path.name == SELF_NAME:
        return False
    if path.name in DEFAULT_FILENAMES:
        return True
    return path.suffix in DEFAULT_EXTENSIONS


def git_tracked_files() -> list[Path]:
    """Return the repo's git-tracked files, or raise if git is unavailable.

    Tracked files exclude anything gitignored (the internal PT-BR documents),
    so scanning this set needs no per-file exclusion list. The git executable
    is resolved to an absolute path so the call does not depend on PATH lookup.
    """
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git executable not found on PATH")
    # The command is a fixed literal (resolved git path + constant args); there is
    # no user-controlled input in the argument vector, so this call is safe.
    result = subprocess.run(  # noqa: S603
        [git, "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(name) for name in result.stdout.split("\0") if name]


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return (line_no, kind, content) findings; kind is "diacritic" or "keyword".

    Empty list means clean. Binary/unreadable files are skipped silently.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # binary or unreadable - skip silently

    findings: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if any(c in PT_DIACRITICS for c in line):
            findings.append((lineno, "diacritic", line.rstrip()))
            continue
        if _PT_KEYWORD_PATTERN.search(line):
            findings.append((lineno, "keyword", line.rstrip()))
    return findings


def collect_paths(argv: list[str]) -> list[Path]:
    """Resolve the set of files to scan.

    With argv, scan exactly those files that exist and are in scope by name.
    Without argv, scan the git-tracked files in scope.
    """
    if argv:
        return [p for arg in argv if (p := Path(arg)).is_file() and in_scope_by_name(p)]
    return [p for p in git_tracked_files() if p.is_file() and in_scope_by_name(p)]


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    argv = argv if argv is not None else sys.argv[1:]

    try:
        paths = collect_paths(argv)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"check_no_pt_br: could not list git files: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for path in paths:
        for lineno, kind, line in scan_file(path):
            failures += 1
            display_line = line if len(line) <= 120 else line[:117] + "..."
            print(f"{path}:{lineno}: [{kind}] {display_line}", file=sys.stderr)

    if failures:
        print(
            f"\n{failures} PT-BR finding(s) in repo-public files.\n"
            "Translate the text to English. Internal-only documents are "
            "gitignored and are not scanned.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
