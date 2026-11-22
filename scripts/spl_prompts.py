#!/usr/bin/env python3
"""(Used once, for the GraphLang refactor.) Convert a .spl file's CREATE FUNCTION prompts to GraphLang prompt files, exactly as spl3 renders them:
each `{param}` of the function becomes `{{in_param}}` (spl3 replaces `{param}` literally, nothing else), SPL's ''
quote escape becomes '. Everything else is kept byte for byte. Optional renames: param -> port name."""
import re, sys, os
src, out_dir = sys.argv[1], sys.argv[2]
renames = dict(a.split("=") for a in sys.argv[3:])
text = open(src).read()
os.makedirs(out_dir, exist_ok=True)
for m in re.finditer(r"CREATE FUNCTION (\w+)\((.*?)\)\s*RETURN TEXT\s*AS \$\$\n(.*?)\n\$\$;", text, re.S):
    name, params, body = m.group(1), [p.split()[0] for p in m.group(2).split(",") if p.strip()], m.group(3)
    for p in params:
        body = body.replace("{" + p + "}", "{{in_" + renames.get(p, p) + "}}")
    with open(os.path.join(out_dir, name + ".md"), "w") as f:
        f.write(body.replace("''", "'") + "\n")
    print(name, params)
