"""Download the theme fonts (variable woff2, latin + latin-ext) from Google Fonts."""
import re, sys, urllib.request
from pathlib import Path
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
url = ("https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,100..900;1,9..144,100..900"
       "&family=Outfit:wght@100..900&display=swap")
css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read().decode()
blocks = re.findall(r"/\* (\S+) \*/\s*@font-face \{(.*?)\}", css, re.S)
faces = []
for subset, body in blocks:
    if subset not in ("latin", "latin-ext"):
        continue
    fam = re.search(r"font-family: '([^']+)'", body).group(1)
    style = re.search(r"font-style: (\w+)", body).group(1)
    weight = re.search(r"font-weight: ([\d ]+)", body).group(1)
    src = re.search(r"url\((\S+?)\) format\('woff2'\)", body).group(1)
    rng = re.search(r"unicode-range: ([^;]+)", body).group(1)
    name = f"{fam.lower()}-{style}-{subset}.woff2"
    (out / name).write_bytes(urllib.request.urlopen(src).read())
    faces.append((fam, style, weight, name, rng))
    print("fetched", name)
(out / "fonts.css").write_text("".join(
    f"@font-face {{\n  font-family: '{fam}';\n  font-style: {style};\n  font-weight: {weight};\n"
    f"  font-display: swap;\n  src: url('{name}') format('woff2');\n  unicode-range: {rng};\n}}\n"
    for fam, style, weight, name, rng in faces))
print("wrote fonts.css with", len(faces), "faces")
