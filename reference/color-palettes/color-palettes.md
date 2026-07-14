# Skill: OpenTikZ color palette

The single source of truth for colors in OpenTikZ. **All icons, templates, and
examples reference these named colors — never hard-code a hex value inline.**

Because every `.tex` must compile **standalone**, colors cannot be `\input` from
a shared file at build time. Instead, each content file **mirrors the palette
block below into its own preamble**. This file is the canonical definition those
copies must match.

## Named colors

The default palette is the color-blind-friendly **Okabe-Ito** set, chosen so
figures remain distinguishable under the common forms of color vision deficiency
and in grayscale print.

| Name       | Light (default) | Dark-tuned | Typical role                         |
|------------|-----------------|------------|--------------------------------------|
| `otblue`   | `#0072B2`       | `#56B4E9`  | primary blocks, main flow            |
| `otorange` | `#E69F00`       | `#E69F00`  | highlight / accent, "the new thing"  |
| `otteal`   | `#009E73`       | `#2EBE9B`  | success / data / secondary blocks    |
| `otpurple` | `#CC79A7`       | `#E08FBE`  | tertiary blocks, auxiliary paths     |
| `otgray`   | `#5A5A5A`       | `#B3B3B3`  | structure: outlines, text, arrows    |

Convention: use **fill tints** for surfaces (`fill=otblue!12`) and the **full
color** (often darkened: `draw=otblue!75!black`) for strokes, so adjacent blocks
read clearly. `otgray` is the neutral for outlines/arrows/labels.

## Light palette block (default — paste into preamble)

```latex
% --- OpenTikZ palette (light / default, color-blind-friendly Okabe-Ito) ---
\definecolor{otblue}{HTML}{0072B2}
\definecolor{otorange}{HTML}{E69F00}
\definecolor{otteal}{HTML}{009E73}
\definecolor{otpurple}{HTML}{CC79A7}
\definecolor{otgray}{HTML}{5A5A5A}
```

## Dark palette block (for dark backgrounds — same names, swap the block)

A figure switches to dark mode by replacing the light block with this one: the
**names are identical**, so no body edits are needed. You **must** also set a dark
page background — `\definecolor{otpaper}{HTML}{1E1E1E}` then `\pagecolor{otpaper}`.
The dark colors are tuned for a dark canvas; rendered on a white page the tints
look washed-out grey, which is the usual "the dark palette looks broken" mistake.

```latex
% --- OpenTikZ palette (dark-tuned, same names) ---
\definecolor{otpaper}{HTML}{1E1E1E}   % dark page background; \pagecolor{otpaper}
\definecolor{otblue}{HTML}{56B4E9}
\definecolor{otorange}{HTML}{E69F00}
\definecolor{otteal}{HTML}{2EBE9B}
\definecolor{otpurple}{HTML}{E08FBE}
\definecolor{otgray}{HTML}{B3B3B3}
```

> Open item (future, non-MVP): tint syntax like `otblue!15` mixes toward **white**,
> so on `otpaper` the tints lift toward white rather than blending into the dark
> background. A future enhancement could define dark-aware tints (e.g. mix toward
> `otpaper`). For MVP, the full colors + `\pagecolor{otpaper}` read fine.

## ESL domain-semantic tokens (contract §2 extension — ADR-0005 D7, WP-3)

These **extend** the palette above; they do not remap the ESL domain-semantic
figure families (analog-AI circuit schematics, tsarilp-style MPSoC architecture
blocks) onto the five `ot*` names. Source of truth:
`contract/backend-contract-v1.2.0.md` §2 (vendored, read-only — see
`contract/CONTRACT.md`). **Token → role binding is frozen by the contract**: a
host document may re-hue a token but must keep its role; `tools/validate.py`
fails the build if this table drifts from the vendored contract's §2 table
(`_palette_contract_drift_problem`).

| Token | Role / meaning | Default hue | Neutral hex |
|---|---|---|---|
| `inputdomain` | inputs / activations | blue | `#2B6CB0` |
| `weightdomain` | analog weight cells | green | `#2F8F4E` |
| `digitaldomain` | digital words / logic | gray | `#7A7A7A` |
| `analogdomain` | analog current / accumulation | orange | `#E08A1E` |
| `intra-bus` | intra-tile interconnect | Orange | `#E8890C` |
| `inter-bus` | inter-tile interconnect | NavyBlue | `#1F3A93` |
| `core-accent` | processing-core fill accent | Aquamarine / ForestGreen | `#4FB8A8` |
| `process-accent` | flow transform-stage accent | NavyBlue | `#1F3A93` |
| `param-accent` | parameter/artifact box accent | ForestGreen | `#228B22` |

`core-accent`'s contract default hue is dual (`Aquamarine / ForestGreen` — the
two families that use this role picked different hues). This palette binds it
to **Aquamarine**, the tsarilp/architecture-family default the ported
`esl-architecture-block` fixture uses; `param-accent` already carries
`ForestGreen` for that same family's config/parameter role, so both contract
hues are represented in the palette, just under their own token names.

**Neutral hex** is the backend-agnostic sRGB fallback for non-TeX consumers of
this palette (draw.io/SVG backends); it travels with the token, not as part of
the TeX binding.

### ESL token palette block (mirror into preamble alongside the light/dark block above)

Some of these tokens bind to `dvipsnames` hues (`Aquamarine`, `NavyBlue`,
`ForestGreen`, `Orange`), so a template using any of them needs
`\usepackage[dvipsnames]{xcolor}` (plain `\usepackage{xcolor}` does not define
those names).

```latex
% --- ESL domain-semantic tokens (contract §2, ADR-0005 D7) ---
% needs \usepackage[dvipsnames]{xcolor} for Aquamarine/NavyBlue/ForestGreen/Orange
\colorlet{inputdomain}{blue}
\colorlet{weightdomain}{green}
\colorlet{digitaldomain}{gray}
\colorlet{analogdomain}{orange}
\colorlet{intra-bus}{Orange}
\colorlet{inter-bus}{NavyBlue}
\colorlet{core-accent}{Aquamarine}
\colorlet{process-accent}{NavyBlue}
\colorlet{param-accent}{ForestGreen}
```

### Typography and arrowhead tokens (contract §2)

Carried here too, since they are named in the same contract section — a
backend maps each to its own font/arrow model; for the TikZ backend:

- `body-font` — match the host manuscript body; **settled: newtx Times, never
  Computer Modern** (`\usepackage{newtxtext}` in the host document's preamble;
  content `.tex` files stay standalone-default since they are figures, not the
  manuscript body — this token governs the *host* document that includes them).
- `domain-label` — small italic (`font=\small\itshape` or a template's own
  `domainlbl`-style equivalent).
- `role-label` — footnotesize (`font=\footnotesize`).
- `sidenote` — ~6.5pt gray (`font=\fontsize{6.5}{8}\selectfont, text=digitaldomain!55!black`
  or equivalent neutral-gray tint — a template's `sidenote` style realizes this).
- **Arrowhead:** `arrow = Stealth` — every directed edge uses TikZ's
  `arrows.meta` `Stealth` arrowhead (`>=Stealth` in the `tikzpicture` options,
  as both ESL fixtures already do).

## How to apply

- **New content**: paste the light block into the preamble; reference colors by
  name only (`fill=otteal!15`, `draw=otblue!75!black`, `text=otgray`).
- **Recolor a figure** (e.g. "make it teal"): change color *names* in the body
  (`otblue` → `otteal`); do not touch the `\definecolor` block and never
  introduce a raw hex or a built-in name like `blue`/`red`.
- **Re-theme to a different hue family**: keep using the five names; only their
  *roles* change. If a figure needs a sixth distinct color, prefer a tint/shade
  of an existing name (`otblue!60`) before adding a new one.
- **Dark variant**: swap the light block for the dark block; the body is
  unchanged because the names match.

## Constraints

- Never write a hex literal or a stock xcolor/dvipsnames name (`blue`, `red`,
  `green!50`, `Aquamarine`) in content. Always go through a palette name —
  the five `ot*` names **or** an ESL domain-semantic token above (tints/shades
  allowed on either). `tools/validate.py` enforces this on every template.
- Keep the `\definecolor`/`\colorlet` values byte-for-byte identical to the
  tables above so every figure shares one palette. `swatches.svg` is the
  visual reference.
- These five names, plus the nine ESL domain-semantic tokens, are the full
  palette the contract skills target when recoloring — don't rename them, and
  don't force the ESL tokens onto the five `ot*` names or vice versa (ADR-0005
  D7: extend the palette, never remap).

See `swatches.tex` / `swatches.svg` for a rendered reference of both variants.
