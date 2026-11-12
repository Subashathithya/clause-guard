"""Audit the translation catalogues against the keys the app actually uses.

Every `t('...')` call in src/ must exist in every locale file. A missing key
would render as the raw key in the UI, so this check runs in CI.

Usage:  python scripts/check_i18n_keys.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESSAGES = ROOT / "frontend" / "src" / "i18n" / "messages"
SRC = ROOT / "frontend" / "src"
LOCALES = ("en", "hi", "ta", "te")

NS_RE = re.compile(r"^  (\w+): \{$", re.MULTILINE)
KEY_RE = re.compile(r"^    (\w+):", re.MULTILINE)
USE_RE = re.compile(r"""\bt\(\s*['"]([a-zA-Z]+)\.(\w+)['"]""")
USE_TEMPLATE_RE = re.compile(r"""\bt\(\s*`([a-zA-Z]+)\.(\w+)`""")
DYNAMIC_RE = re.compile(r"""\bt\(\s*`\$\{""")
DYNAMIC_KEY_RE = re.compile(r"""\bt\(\s*([a-zA-Z]+)\.(\w+)['"]""")


def catalogue_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    keys: set[str] = set()
    ns = None
    for line in text.split("\n"):
        ns_match = NS_RE.match(line)
        if ns_match:
            ns = ns_match.group(1)
            continue
        if ns and line.startswith("  },"):
            ns = None
            continue
        key_match = KEY_RE.match(line)
        if ns and key_match:
            keys.add(f"{ns}.{key_match.group(1)}")
    return keys


def used_keys() -> tuple[set[str], list[tuple[str, str]]]:
    used: set[str] = set()
    dynamic: list[tuple[str, str]] = []
    for path in SRC.rglob("*.ts*"):
        if "i18n/messages" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        for match in USE_RE.finditer(text):
            used.add(f"{match.group(1)}.{match.group(2)}")
        for match in USE_TEMPLATE_RE.finditer(text):
            used.add(f"{match.group(1)}.{match.group(2)}")
        for match in DYNAMIC_RE.finditer(text):
            dynamic.append((path.as_posix(), match.group(0)))
    return used, dynamic


def main() -> int:
    catalogues = {loc: catalogue_keys(MESSAGES / f"{loc}.ts") for loc in LOCALES}
    used, dynamic = used_keys()

    failures = 0
    for loc in LOCALES:
        missing = sorted(used - catalogues[loc])
        if missing:
            failures += 1
            print(f"MISSING in {loc}.ts ({len(missing)}):")
            for key in missing:
                print(f"   - {key}")

    # A key used in one locale but not another is a translation gap.
    for loc in LOCALES[1:]:
        extra = sorted(catalogues[loc] - catalogues["en"])
        if extra:
            failures += 1
            print(f"EXTRA in {loc}.ts (not in en.ts): {extra}")

    unused = sorted(catalogues["en"] - used)
    if unused:
        print(f"note: {len(unused)} catalogue keys are not referenced directly "
              f"(some are built at runtime): {unused[:12]}{'…' if len(unused) > 12 else ''}")

    if dynamic:
        print(f"note: {len(dynamic)} dynamic t() calls (keys built at runtime)")

    print(f"checked {len(used)} keys across {len(LOCALES)} locales")
    if failures:
        print("FAILED")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
