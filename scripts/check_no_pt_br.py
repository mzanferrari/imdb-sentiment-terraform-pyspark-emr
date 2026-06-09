#!/usr/bin/env python3
"""Pre-commit hook: detect Portuguese (pt-BR) leaking into repo-public files.

This project targets EU-remote roles where English is the working language.
Mixed-language artifacts in a public repo dilute the portfolio signal.

The check looks for two classes of evidence:

1. **Diacritics** - characters like á é í ó ú ã õ ç that appear almost
   exclusively in pt-BR (and other Romance languages) inside this project's
   context. Detection is a strong signal.

2. **PT-BR keywords without diacritics** - common Portuguese words that have
   no English homograph and slip past diacritic scanning (e.g., "execução"
   becoming "execucao" in someone's hurried typing).

The hook **never** scans:

- The internal-only documents that legitimately stay in PT-BR
  (AUDITORIA.md, AUDITORIA_V2.md, AUDITORIA_V3.md, AUDITORIA_V4.md, AUDITORIA_V5.md,
  ROADMAP_UPGRADE.md, CODE_COMMENTS_GUIDE.md, GUIA_DE_USO_DESTA_AUDITORIA.md)
- Generated directories (data/, logs/, .terraform/, build/, etc.)
- Binary files (detected via decode failure)

Usage (manual):
    python scripts/check_no_pt_br.py [file1.py file2.tf ...]

Without arguments, scans every tracked file matching the configured globs.

Pre-commit hook entry (already wired in `.pre-commit-config.yaml`):
    - id: check-no-pt-br
      name: No PT-BR in repo-public files
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
import sys
from pathlib import Path
from typing import Final

# ─── WHAT COUNTS AS PT-BR ─────────────────────────────────────────────────────

PT_DIACRITICS: Final[frozenset[str]] = frozenset("áéíóúâêîôûãõàçÁÉÍÓÚÂÊÎÔÛÃÕÀÇ")

# Words common in PT-BR with no English homograph. Case-insensitive matching.
# Conservative list - false positives are worse than missed catches in a hook.
PT_KEYWORDS: Final[tuple[str, ...]] = (
    r"\busadas?\b",
    r"\busado\b",
    r"\busados\b",
    r"\bsera\b",  # "sera" (will be) without accent
    r"\bserao\b",  # "serao" (they will be) without accent
    r"\btambem\b",  # "tambem" (also) without accent
    r"\bnao\b",  # "nao" (no/not) without accent - distinctive in PT-BR
    r"\bmodulo\b",
    r"\bmodulos\b",
    r"\bvariavel\b",
    r"\bvariaveis\b",
    r"\breproduzivel\b",
    r"\breproduziveis\b",
    r"\bminimo\b",
    r"\bminima\b",
    r"\bconfiguravel\b",
    r"\bconfiguraveis\b",
    r"\bexecucao\b",
    r"\bversao\b",
    r"\bversoes\b",
    r"\bregiao\b",
    r"\bpacote\b",
    r"\bpacotes\b",
    r"\barquivo\b",
    r"\barquivos\b",
    # Phrases that strongly indicate PT-BR
    r"\bpath_dados\b",
    r"\blinha\s+de\s+comando\b",
    r"\bcomentar\s+resultados\b",
    r"\bcancela\s+runs\b",
    r"\bfalha\s+o\s+ci\b",
    r"\btoda\s+(segunda|terca|quarta|quinta|sexta)\b",
)

# Compile once for performance
_PT_KEYWORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    "|".join(PT_KEYWORDS),
    re.IGNORECASE,
)

# ─── WHAT FILES ARE SCANNED ───────────────────────────────────────────────────

# Files (basename) that legitimately stay in PT-BR - they never go to the public repo.
INTERNAL_ONLY_FILES: Final[frozenset[str]] = frozenset(
    {
        "AUDITORIA.md",
        "AUDITORIA_V2.md",
        "AUDITORIA_V3.md",
        "AUDITORIA_V4.md",
        "AUDITORIA_V5.md",
        "ROADMAP_UPGRADE.md",
        "CODE_COMMENTS_GUIDE.md",
        "GUIA_DE_USO_DESTA_AUDITORIA.md",
        "GUIA_EXECUCAO_FASES_0_1.md",
    }
)

# Directories never scanned regardless of contents
EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "data",
        "logs",
        "build",
        "dist",
        "__pycache__",
        ".venv",
        "venv",
        ".terraform",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)

# Default extensions scanned when no explicit filenames are passed
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

# Filenames without extension that should be scanned
DEFAULT_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "Makefile",
        "Dockerfile",
    }
)


# ─── CORE ─────────────────────────────────────────────────────────────────────


def should_scan(path: Path) -> bool:
    """Decide whether a path is in scope for the check."""
    if not path.is_file():
        return False
    if path.name in INTERNAL_ONLY_FILES:
        return False
    # Skip the checker itself - it legitimately contains diacritics in its
    # detection rules (which would otherwise trigger the checker on itself).
    if path.name == "check_no_pt_br.py":
        return False
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False
    if path.name in DEFAULT_FILENAMES:
        return True
    return path.suffix in DEFAULT_EXTENSIONS


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


def collect_paths_from_args(argv: list[str]) -> list[Path]:
    """Return paths to scan based on CLI argv."""
    if argv:
        return [Path(p) for p in argv if Path(p).exists()]
    # No args - walk current directory
    return [p for p in Path().rglob("*") if should_scan(p)]


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    argv = argv if argv is not None else sys.argv[1:]
    paths = collect_paths_from_args(argv)

    failures = 0
    for path in paths:
        if not should_scan(path):
            continue
        for lineno, kind, line in scan_file(path):
            failures += 1
            # Truncate the printed line so very long lines don't drown the output
            display_line = line if len(line) <= 120 else line[:117] + "..."
            print(f"{path}:{lineno}: [{kind}] {display_line}", file=sys.stderr)

    if failures:
        print(
            f"\n{failures} PT-BR finding(s) in repo-public files.\n"
            "Translate the text to English or, if the file is internal-only, "
            "add its basename to INTERNAL_ONLY_FILES in scripts/check_no_pt_br.py.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
