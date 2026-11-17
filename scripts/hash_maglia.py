"""Aggiorna in revisioni/v03.md lo SHA-256 di scripts/maglia.py (da lanciare dopo ogni modifica)."""
import hashlib
import os
import re

radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
h = hashlib.sha256(open(os.path.join(radice, "scripts", "maglia.py"), "rb").read()).hexdigest()
p = os.path.join(radice, "revisioni", "v03.md")
s = open(p, encoding="utf-8", newline="").read()
s = re.sub(r"(SHA-256 di `scripts/maglia.py`: `)[0-9a-f]{64}(`)", r"\g<1>" + h + r"\g<2>", s)
open(p, "w", encoding="utf-8", newline="").write(s)
print(h)
