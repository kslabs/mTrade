#!/usr/bin/env python3
"""Apply files from `new/` into repo root, normalizing absolute project paths.

Behaviour:
- Walk `new/` directory
- For each file, replace absolute project-like paths (containing 'bGate.mTrade' or 'mTrade01')
  with the placeholder `<project-root>`.
- Backup existing target files as `.bak.TIMESTAMP`
- Overwrite targets and report summary.

Run this from repo root.
"""
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
NEW_DIR = ROOT / 'new'
if not NEW_DIR.exists():
    print('No new/ directory found. Exiting.')
    sys.exit(1)

TS = datetime.now().strftime('%Y%m%d_%H%M%S')

# Patterns to replace: project-specific absolute paths containing these markers.
PATTERNS = [
    re.compile(r"[A-Za-z]:\\\\(?:[^\\\n\"']*\\\\)*bGate\.mTrade", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\(?:[^\\\n\"']*\\\\)*mTrade01(?:\\\\mTrade01)?", re.IGNORECASE),
    re.compile(r"/Users/[^/]+/(?:bGate\.mTrade|mTrade01)(?:/mTrade01)?", re.IGNORECASE),
    re.compile(r"/home/[^/]+/(?:bGate\.mTrade|mTrade01)(?:/mTrade01)?", re.IGNORECASE),
]

def normalize_text(text: str) -> str:
    s = text
    for p in PATTERNS:
        s = p.sub('<project-root>', s)
    # Also replace backslashes sequences to forward for placeholders in docs where helpful
    s = s.replace('\\\\', '/')
    return s

changes = []
processed = 0
skipped = 0

for src in NEW_DIR.rglob('*'):
    if src.is_dir():
        continue
    rel = src.relative_to(NEW_DIR)
    target = ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        b = src.read_bytes()
        try:
            text = b.decode('utf-8')
            is_text = True
        except UnicodeDecodeError:
            # binary file — copy as-is
            is_text = False
    except Exception as e:
        print('Failed to read', src, e)
        skipped += 1
        continue

    if target.exists():
        bak = target.with_suffix(target.suffix + f'.bak.{TS}')
        try:
            target_bytes = target.read_bytes()
            bak.write_bytes(target_bytes)
        except Exception:
            pass

    if is_text:
        new_text = normalize_text(text)
        target.write_text(new_text, encoding='utf-8')
        changes.append(str(rel))
        processed += 1
    else:
        # binary
        target.write_bytes(b)
        changes.append(str(rel))
        processed += 1

print('Processed files:', processed)
print('Skipped files:', skipped)
print('Changed/added files count:', len(changes))
for c in changes[:200]:
    print(' -', c)
