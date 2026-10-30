"""Wrap every tabular in the given .tex files in an adjustbox that only shrinks (max width = text width). Idempotent."""
import re, sys
for p in sys.argv[1:]:
    s = open(p).read()
    if "adjustbox" in s:
        continue
    s = re.sub(r"(\\begin\{tabular\})", r"\\begin{adjustbox}{max width=\\textwidth}\n\1", s)
    s = re.sub(r"(\\end\{tabular\})", r"\1\n\\end{adjustbox}", s)
    open(p, "w").write(s)
