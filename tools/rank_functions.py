import re
import pathlib

p = pathlib.Path('static/app.js')
text = p.read_text(encoding='utf-8', errors='ignore')
lines = text.splitlines()

# Heuristic: match classic function declarations at column 0-ish.
pat = re.compile(r'^\s*function\s+([A-Za-z_$][\w$]*)\s*\(')

funcs = []
for i, line in enumerate(lines):
    m = pat.match(line)
    if not m:
        continue
    name = m.group(1)

    j = i
    brace_found = False
    bal = 0
    started = False
    end = None

    while j < len(lines):
        l = lines[j]
        # crude (doesn't ignore strings/comments), but OK for ranking
        for ch in l:
            if ch == '{':
                bal += 1
                brace_found = True
                started = True
            elif ch == '}':
                if started:
                    bal -= 1
        if brace_found and started and bal == 0:
            end = j
            break
        j += 1

    if end is None:
        end = len(lines) - 1

    funcs.append((name, i + 1, end + 1, end - i + 1))

funcs.sort(key=lambda x: x[3], reverse=True)

print('Top functions by line count:')
for name, start, end, n in funcs[:15]:
    print(f'{n:5d} lines  {name}  (L{start}-L{end})')

print('\nTotal funcs found:', len(funcs))
