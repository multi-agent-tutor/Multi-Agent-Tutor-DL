"""Copier accueil.css (maquette D2) en CSS de la landing React, isolé de maquettes.css :
toute classe devient v-<classe>, les règles globales passent sous .v-racine / html.v-page."""
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
css = open(src, encoding="utf-8").read().replace("\r\n", "\n")
# @font-face : déjà déclarées dans maquettes.css (chemins /fonts)
css = re.sub(r"@font-face \{[^}]*\}\n", "", css)
# Bloc mascotte : identique à maquettes.css, sauf la taille par défaut
css = re.sub(
    r"/\* -+ mascotte \(visage du tuteur\) \*/\n(?:.*\n)*?@keyframes eclat[^\n]*\n",
    "/* ---------------------------------------------------- mascotte : états dans maquettes.css */\n"
    "@@RACINE_MASCOTTE@@\n",
    css,
)
keyframes = re.findall(r"@keyframes ([\w-]+)", css)
GARDER = {"mascotte", "eclats", "tete", "yeux", "yeux-arcs", "yeux-points", "yeux-oups", "contour"}
CLASSE = re.compile(r"\.([a-zA-Z][\w-]*)")
out = []
for ligne in css.split("\n"):
    if "url(" not in ligne and not ligne.lstrip().startswith(("/*", "*")):
        ligne = CLASSE.sub(lambda m: m.group(0) if m.group(1) in GARDER else ".v-" + m.group(1), ligne)
    if "animation" in ligne or "@keyframes" in ligne:
        for k in keyframes:
            ligne = re.sub(rf"(?<![\w-]){k}(?![\w-])", "v-" + k, ligne)
    out.append(ligne)
css = "\n".join(out)
css = css.replace("@@RACINE_MASCOTTE@@", ".v-racine .mascotte { width: 44px; height: 44px; }")
css = css.replace(":root {", ".v-racine {", 1)
css = css.replace('--police: "Inter", "Segoe UI"', '--police: "Inter", "Noto Sans Arabic", "Segoe UI"')
css = re.sub(r"^html \{", "html.v-page {", css, flags=re.M)
css = css.replace("{ html { scroll-behavior: auto; } }", "{ html.v-page { scroll-behavior: auto; } }")
css = re.sub(r"^body \{", ".v-racine {", css, flags=re.M)
css = re.sub(r"^img, svg, canvas \{", ":where(.v-racine) :is(img, svg, canvas) {", css, flags=re.M)
css = re.sub(r"^a \{ color: inherit; \}", ":where(.v-racine) a { color: inherit; }", css, flags=re.M)
css = re.sub(
    r"^h1, h2, h3 \{",
    ":where(.v-racine) :is(h1, h2, h3) { font-family: inherit; line-height: inherit;",
    css,
    flags=re.M,
)
css = re.sub(r"^p \{", ":where(.v-racine) p {", css, flags=re.M)
css = re.sub(r"^::selection", ".v-racine ::selection", css, flags=re.M)
css = re.sub(r"^:focus-visible[^\n]*\n", "", css, flags=re.M)
open(dst, "w", encoding="utf-8", newline="\n").write(css)
print("keyframes :", keyframes)
