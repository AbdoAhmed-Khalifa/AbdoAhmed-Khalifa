#!/usr/bin/env python3
"""Generate the SVG assets used by the profile README.

The design mirrors the portfolio (abdelrahmankhalifa.com): warm paper and ink,
an oxblood accent, Fraunces headlines with an italic accent line, Instrument
Sans body and DM Mono labels. Every section is rendered twice (light + dark)
with subsetted fonts embedded, so typography is identical on every OS. Text is
measured with the real font metrics, so wrapping and chip layout are exact.

    pip install fonttools brotli
    python3 scripts/build_assets.py
"""
from __future__ import annotations

import base64
import io
import os
import sys
from collections import defaultdict
from functools import lru_cache

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "scripts", "fonts")
OUT_DIR = os.path.join(ROOT, "assets")

W = 880  # canvas width; GitHub scales images to the README column

# ---------------------------------------------------------------- tokens ---

FONTS = {
    "display": "Fraunces-Display.woff2",          # wght 350, opsz 144
    "displayItalic": "Fraunces-DisplayItalic.woff2",
    "title": "Fraunces-Title.woff2",              # wght 420, opsz 36
    "titleItalic": "Fraunces-TitleItalic.woff2",
    "body": "InstrumentSans-Regular.woff2",
    "medium": "InstrumentSans-Medium.woff2",
    "mono": "DMMono-Regular.woff2",
    "monoMedium": "DMMono-Medium.woff2",
    "arabic": "IBMPlexSansArabic-SemiBold.woff2",
}
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
FALLBACK = {
    "display": SERIF, "displayItalic": SERIF, "title": SERIF, "titleItalic": SERIF,
    "mono": MONO, "monoMedium": MONO, "arabic": "'Segoe UI', Tahoma, sans-serif",
}

# Same values as the portfolio's globals.css (light :root / [data-theme="dark"]).
LIGHT = dict(
    bg="#f4f1ea", surface="#fbf9f4", text="#1a1814", body="#3a362f", muted="#6b645a",
    line="rgba(26,24,20,0.2)", line_strong="rgba(26,24,20,0.35)",
    accent="#8e2f2a", live="#1f5c4a",
)
DARK = dict(
    bg="#141210", surface="#1c1916", text="#f2ede4", body="#d6cfc3", muted="#a39a8d",
    line="rgba(242,237,228,0.14)", line_strong="rgba(242,237,228,0.28)",
    accent="#e07560", live="#5cb896",
)
# The contact section closes on an "ink block": dark tokens in both themes,
# lifted a step on dark pages so it still reads as its own block.
INK = {"light": dict(DARK), "dark": dict(DARK, bg="#211d19", surface="#2b2622")}
THEMES = {"light": LIGHT, "dark": DARK}

# --------------------------------------------------------------- content ---

PROFILE = dict(
    name=["Abdelrahman", "Khalifa."],
    eyebrow="CAIRO, EGYPT · GMT+3",
    status="OPEN TO NEW ROLES",
    tagline="Frontend for software people depend on — React, Next.js and "
            "TypeScript, shipped to production.",
    stats=[("2+", "YEARS IN PRODUCTION"), ("3", "LIVE PLATFORMS"),
           ("Web + Mobile", "REACT · REACT NATIVE")],
)

SECTIONS = {
    "work": ("01", "SELECTED WORK", ["Work that’s out in the ", "world."]),
    "experience": ("02", "EXPERIENCE", ["Where I’ve ", "shipped."]),
    "toolkit": ("03", "SKILLS", ["What I’m ", "good at."]),
    "contact": ("04", "CONTACT", ["Send me the ", "hard screen."]),
}

PROJECTS = [
    dict(
        slug="freightin", title=["Freight", "In"], tag="LOGISTICS · LIVE",
        link="freightin.net",
        text="Container booking for shippers: pick ports, container type and date, "
             "then book in bulk. Rate search, quotation requests and shipment "
             "tracking — built from Figma to production.",
        stack=["Next.js", "TypeScript", "TanStack Query", "Tailwind", "Framer Motion"],
    ),
    dict(
        slug="masroof", title=["Masroof", None], arabic="مصروف", tag="ANDROID · SIDE PROJECT",
        link=None, note="private repo · v1.2",
        text="Your bank texts you, Masroof does the bookkeeping. It turns Egyptian "
             "bank SMS into a categorised, offline budget — subscriptions, "
             "installments, savings circles and encrypted backups. Zero network calls.",
        stack=["Expo", "React Native", "Kotlin", "SQLite", "Drizzle", "Zod"],
    ),
    dict(
        slug="traderin", title=["Trader", "In"], tag="B2B MARKETPLACE · LIVE",
        link="traderin.net",
        text="A wholesale marketplace for bulk trading. Seller dashboards for "
             "orders, product catalogue and sales analytics with interactive charts.",
        stack=["Next.js", "TypeScript", "shadcn/ui", "Recharts", "Tailwind"],
    ),
    dict(
        slug="taj", title=["Taj ", "Education"], tag="EDTECH · LIVE",
        link="tajteach.com",
        text="One education platform, three worlds. Role-based dashboards that "
             "give students, teachers and admins exactly what they need.",
        stack=["Next.js", "TypeScript", "TanStack Query", "Zustand", "Tailwind"],
    ),
]

EXPERIENCE = [
    dict(
        when="JAN 2025 — NOW", where="CAIRO", current=True,
        role="Front-End Developer", org="FTL Group",
        points=[
            "Built FreightIn’s front end from Figma: rate search, quotations and shipment tracking.",
            "Cut LCP by lazy-loading heavy dependencies and removing render-blocking work.",
            "Set up the feature-based architecture and shared component layer the team still builds on.",
            "TanStack Query data layer with real loading, error and empty states; typed multi-step forms.",
        ],
    ),
    dict(
        when="JAN — MAR 2026", where="CAIRO",
        role="Web Developer", org="Coretech Innovation",
        points=[
            "Admin dashboards and control UIs for EV charging systems and EEBUS integration.",
            "Data-dense IoT and e-mobility monitoring interfaces on REST APIs.",
        ],
    ),
    dict(
        when="MAY 2024 — JAN 2025", where="SOHAG",
        role="Front-End Instructor", org="ITI",
        points=["Taught HTML, CSS, JavaScript and React to 50+ students; supervised 10+ projects."],
    ),
    dict(
        when="2017 — 2024", where="EDUCATION", muted=True,
        role="B.Sc. Computer Science", org="Sohag University",
        points=["Then ITI’s Front-End & Cross-Platform Mobile diploma (Nov 2023 — Apr 2024)."],
    ),
]

TOOLKIT = [
    ("CORE", ["TypeScript", "JavaScript", "React", "Next.js App Router", "HTML", "CSS"]),
    ("DATA & STATE", ["TanStack Query", "Redux Toolkit", "Zustand", "React Hook Form", "Zod", "REST"]),
    ("UI & MOTION", ["Tailwind CSS", "shadcn/ui", "MUI", "Ant Design", "Sass", "Framer Motion", "GSAP"]),
    ("MOBILE", ["React Native", "Expo", "NativeWind", "Kotlin", "SQLite"]),
    ("QUALITY", ["Core Web Vitals", "Lighthouse", "Jest", "Testing Library", "RTL & i18n", "a11y"]),
    ("WORKFLOW", ["Figma", "Git", "GitHub", "GitLab", "Claude", "Codex"]),
]

CONTACT = dict(
    lead="The dense table, the bilingual form, the flow nobody wants to own.",
    email="abdelrahmanahmedkhalifa99@gmail.com",
)

# Brand glyphs from Simple Icons (CC0); mail/globe drawn as strokes. 24x24 viewBox.
ICONS = {
    "linkedin": ("fill", "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"),
    "mail": ("stroke", "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z M22 7l-10 6L2 7"),
    "globe": ("stroke", "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20Z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10a15.3 15.3 0 0 1-4 10a15.3 15.3 0 0 1-4-10a15.3 15.3 0 0 1 4-10Z"),
}

SOCIAL = [
    ("portfolio", "globe", "Portfolio"),
    ("linkedin", "linkedin", "LinkedIn"),
    ("email", "mail", "Email"),
]

# ----------------------------------------------------------- font utils ---


@lru_cache(None)
def _metrics(key: str):
    f = TTFont(os.path.join(FONT_DIR, FONTS[key]))
    return f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm


def measure(s: str, font: str, size: float, ls: float = 0) -> float:
    cmap, hmtx, upem = _metrics(font)
    total = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upem * 0.6 for c in s)
    return total / upem * size + ls * max(len(s) - 1, 0)


def wrap(s: str, font: str, size: float, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if measure(trial, font, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


@lru_cache(None)
def _subset_b64(key: str, chars: str) -> str:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt", "init", "medi", "fina", "isol", "rlig"]
    font = TTFont(os.path.join(FONT_DIR, FONTS[key]), recalcTimestamp=False)  # deterministic output
    sub = subset.Subsetter(opts)
    sub.populate(text=chars)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------- builder ---


class Svg:
    def __init__(self, w: int, h: int, t: dict, label: str):
        self.w, self.h, self.t, self.label = w, h, t, label
        self.parts: list[str] = []
        self.css: list[str] = []
        self.used: dict[str, set] = defaultdict(set)

    def add(self, s: str):
        self.parts.append(s)

    def text(self, x, y, s, font="body", size=16, fill=None, ls=0, anchor="start"):
        cmap = _metrics(font)[0]
        missing = {c for c in s if c != " " and ord(c) not in cmap}
        if missing:
            sys.exit(f"font '{font}' has no glyph for {sorted(missing)} in {s!r}")
        self.used[font].update(s)
        ls_attr = f' letter-spacing="{ls}"' if ls else ""
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="f-{font}" font-size="{size}" '
                 f'fill="{fill or self.t["text"]}"{ls_attr}{anchor_attr}>{esc(s)}</text>')

    def render(self) -> str:
        faces, classes = [], []
        for key, chars in sorted(self.used.items()):
            b64 = _subset_b64(key, "".join(sorted(chars | {" "})))
            faces.append(f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
            classes.append(f".f-{key}{{font-family:'{key}',{FALLBACK.get(key, SANS)};}}")
        style = "\n".join(faces + classes + self.css)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.label)}">\n'
            f"<title>{esc(self.label)}</title>\n<style>\n{style}\n</style>\n"
            + "\n".join(self.parts) + "\n</svg>\n"
        )


def label(s: str, size=11.5) -> float:
    """Letter-spacing for mono labels: uppercase, tracked (portfolio uses 0.04em; a touch more at small sizes)."""
    return round(size * 0.08, 2)


def arrow(svg: Svg, x: float, y: float, size: float, color: str):
    """↗ drawn as a path (none of the fonts ship the glyph)."""
    s = size
    svg.add(f'<path d="M{x:.1f} {y:.1f}L{x + s:.1f} {y - s:.1f}M{x + s * 0.3:.1f} {y - s:.1f}H{x + s:.1f}V{y - s * 0.7:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>')


def headline(svg: Svg, x: float, y: float, parts: list, size: float, ls: float, plain="display", italic="displayItalic"):
    """Upright text followed by the italic accent part, as the portfolio sets its headlines."""
    t = svg.t
    svg.text(x, y, parts[0], plain, size, t["text"], ls=ls)
    if len(parts) > 1 and parts[1]:
        svg.text(x + measure(parts[0], plain, size, ls) + ls, y, parts[1], italic, size, t["accent"], ls=ls)


def section_head(svg: Svg, key: str, y: float = 22) -> float:
    """Mono eyebrow with a rule, then a serif headline. Returns the y below it."""
    t = svg.t
    index, title, lines = SECTIONS[key]
    svg.text(0, y, index, "monoMedium", 12.5, t["accent"], ls=label(12.5))
    x = measure(index, "monoMedium", 12.5, label(12.5)) + 14
    svg.text(x, y, title, "mono", 12.5, t["muted"], ls=label(12.5))
    x += measure(title, "mono", 12.5, label(12.5)) + 20
    svg.add(f'<line x1="{x:.1f}" y1="{y - 4.5}" x2="{W}" y2="{y - 4.5}" stroke="{t["line"]}"/>')
    headline(svg, -1, y + 52, lines, 42, -0.8)
    return y + 52


def chips(svg: Svg, x0: float, y: float, items: list[str], max_x: float, h=28, gap=8) -> float:
    t = svg.t
    x = x0
    for item in items:
        w = measure(item, "mono", 12.5) + 24
        if x + w > max_x and x > x0:
            x, y = x0, y + h + gap
        svg.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
                f'fill="{t["surface"]}" stroke="{t["line"]}"/>')
        svg.text(x + 12, y + h / 2 + 4.3, item, "mono", 12.5, t["body"])
        x += w + gap
    return y + h


def panel(svg: Svg, h: float, fill: str, y: float = 0, rx: float = 18):
    svg.add(f'<rect x="0.5" y="{y + 0.5}" width="{W - 1}" height="{h - 1}" rx="{rx}" fill="{fill}" stroke="{svg.t["line"]}"/>')


REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important;}}"
PULSE = ".pulse{animation:pulse 2.2s ease-in-out infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}"

# -------------------------------------------------------------- sections ---


def hero(t: dict) -> Svg:
    p = PROFILE
    H = 480
    svg = Svg(W, H + 16, t, f"{' '.join(p['name'])} — Frontend Developer in Cairo, Egypt. {p['tagline']}")
    svg.css.append(".flow{stroke-dasharray:3 7;animation:flow 1.4s linear infinite}"
                   "@keyframes flow{to{stroke-dashoffset:-20}}" + PULSE + REDUCED)
    panel(svg, H, t["bg"], rx=22)
    pad = 44

    # eyebrow + status
    svg.text(pad, 62, p["eyebrow"], "mono", 12, t["muted"], ls=label(12))
    status_w = measure(p["status"], "mono", 12, label(12))
    sx = W - pad - status_w
    svg.add(f'<circle cx="{sx - 14}" cy="58" r="4" fill="{t["live"]}" class="pulse"/>')
    svg.text(sx, 62, p["status"], "mono", 12, t["text"], ls=label(12))

    # route graphic (figma → code → production), sitting behind the right column
    route = "M600 330 C 668 330, 664 232, 728 232 S 790 138, 836 138"
    svg.add(f'<path d="{route}" fill="none" stroke="{t["line_strong"]}" stroke-width="1.5"/>')
    svg.add(f'<path d="{route}" fill="none" stroke="{t["accent"]}" stroke-width="1.5" class="flow"/>')
    for cx, cy, name, lx, ly, anchor in [(600, 330, "figma", 600, 358, "middle"),
                                         (728, 232, "code", 744, 214, "start"),
                                         (836, 138, "production", 836, 114, "end")]:
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="11" fill="none" stroke="{t["accent"]}" stroke-opacity=".3"/>')
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{t["accent"]}"/>')
        svg.text(lx, ly, name, "mono", 12, t["muted"], anchor=anchor)
    svg.add(f'<circle r="3" fill="{t["accent"]}"><animateMotion dur="4s" repeatCount="indefinite" path="{route}"/></circle>')

    # name: two lines, the last italic in the accent — as on the portfolio hero
    size = 92
    svg.text(pad - 4, 168, p["name"][0], "display", size, t["text"], ls=-3.6)
    svg.text(pad - 4, 252, p["name"][1], "displayItalic", size, t["accent"], ls=-3.6)

    for i, line in enumerate(wrap(p["tagline"], "body", 19, 500)):
        svg.text(pad, 304 + i * 28, line, "body", 19, t["body"])

    svg.add(f'<line x1="{pad}" y1="378" x2="{W - pad}" y2="378" stroke="{t["line"]}"/>')
    x = pad
    for num, cap in p["stats"]:
        svg.text(x, 424, num, "title", 30, t["text"], ls=-0.6)
        svg.text(x, 448, cap, "mono", 11, t["muted"], ls=label(11))
        x += max(measure(num, "title", 30, -0.6), measure(cap, "mono", 11, label(11))) + 56
    return svg


def work_header(t: dict) -> Svg:
    svg = Svg(W, 100, t, "01 — Selected work. Work that’s out in the world.")
    section_head(svg, "work")
    return svg


def chip_rows(items: list[str], width: float, gap=8) -> int:
    x, n = 0.0, 1
    for item in items:
        w = measure(item, "mono", 12.5) + 24
        if x + w > width and x > 0:
            x, n = 0.0, n + 1
        x += w + gap
    return n


def project(t: dict, pr: dict, index: int) -> Svg:
    col = 330
    lines = wrap(pr["text"], "body", 16.5, W - col - 32)
    rows = chip_rows(pr["stack"], W - col - 32)
    chips_h = rows * 28 + (rows - 1) * 8
    # card grows to fit: text block, 22px breathing room, chips, 32px padding
    h = max(220, round(54 - 12 + len(lines) * 25 + 22 + chips_h + 32))
    gap = 14  # transparent space below the card so stacked cards breathe
    title = "".join(x for x in pr["title"] if x)
    svg = Svg(W, h + gap, t, f"{title} — {pr['tag'].title()}. {pr['text']} Stack: {', '.join(pr['stack'])}.")
    panel(svg, h, t["bg"], rx=16)

    left = 32
    svg.text(left, 50, f"{index:02d}", "monoMedium", 12.5, t["accent"], ls=label(12.5))
    svg.text(left + 30, 50, pr["tag"], "mono", 11.5, t["muted"], ls=label(11.5))
    headline(svg, left - 1, 98, pr["title"], 38, -1, "title", "titleItalic")
    if pr.get("arabic"):
        x = left + measure(title, "title", 38, -1) + 12
        svg.text(x, 96, pr["arabic"], "arabic", 22, t["muted"])
    if pr["link"]:
        svg.text(left, h - 34, pr["link"], "mono", 13, t["accent"])
        arrow(svg, left + measure(pr["link"], "mono", 13) + 7, h - 35, 7, t["accent"])
    else:
        svg.text(left, h - 34, pr["note"], "mono", 13, t["muted"])

    svg.add(f'<line x1="{col - 28}" y1="32" x2="{col - 28}" y2="{h - 32}" stroke="{t["line"]}"/>')
    for i, line in enumerate(lines):
        svg.text(col, 54 + i * 25, line, "body", 16.5, t["body"])
    chips(svg, col, h - 32 - chips_h, pr["stack"], W - 32)
    return svg


def experience(t: dict) -> Svg:
    rail, body_x = 196, 226
    y = 140
    blocks = []
    for e in EXPERIENCE:
        pts = [wrap(pt, "body", 15.5, W - body_x) for pt in e["points"]]
        blocks.append((e, pts, y))
        y += 32 + sum(len(p) for p in pts) * 24 + (len(pts) - 1) * 4 + 30
    svg = Svg(W, int(y - 10), t, "02 — Experience. Where I’ve shipped. " + " ".join(
        f"{e['role']} at {e['org']} ({e['when'].title()}): {' '.join(e['points'])}" for e in EXPERIENCE))
    svg.css.append(PULSE + REDUCED)
    section_head(svg, "experience")

    top, bottom = blocks[0][2] - 6, blocks[-1][2] - 6
    svg.add(f'<line x1="{rail}" y1="{top}" x2="{rail}" y2="{bottom}" stroke="{t["line_strong"]}"/>')
    svg.add(f'<line x1="{rail}" y1="{top}" x2="{rail}" y2="{blocks[1][2] - 6}" stroke="{t["accent"]}" stroke-width="1.5"/>')

    for e, pts, by in blocks:
        muted = e.get("muted")
        svg.text(0, by, e["when"], "mono", 11.5, t["text"] if not muted else t["muted"], ls=label(11.5))
        svg.text(0, by + 20, e["where"], "mono", 11, t["muted"], ls=label(11))
        if e.get("current"):
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="10" fill="{t["accent"]}" fill-opacity=".16" class="pulse"/>')
        if muted:
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="4.5" fill="{t["surface"]}" stroke="{t["muted"]}" stroke-width="1.5"/>')
        else:
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="5" fill="{t["accent"]}"/>')
        svg.text(body_x, by, e["role"], "title", 22, t["text"] if not muted else t["body"], ls=-0.4)
        rx = body_x + measure(e["role"], "title", 22, -0.4) + 8
        svg.text(rx, by, e["org"], "titleItalic", 22, t["body"] if not muted else t["muted"], ls=-0.4)
        ly = by + 32
        for lines in pts:
            for line in lines:
                svg.text(body_x, ly, line, "body", 15.5, t["body"] if not muted else t["muted"])
                ly += 24
            ly += 4
    return svg


def toolkit(t: dict) -> Svg:
    start, col = 130, 176
    y = start
    rows = []
    for name, items in TOOLKIT:
        rows.append((name, items, y))
        x, n = col, 1  # pre-measure how many chip rows this group needs
        for item in items:
            w = measure(item, "mono", 12.5) + 24
            if x + w > W and x > col:
                x, n = col, n + 1
            x += w + 8
        y += n * 36 + 12
    svg = Svg(W, int(y - 8), t, "03 — Skills. What I’m good at. " + " ".join(
        f"{n.title()}: {', '.join(i)}." for n, i, _ in rows))
    section_head(svg, "toolkit")
    for name, items, ry in rows:
        svg.text(0, ry + 18.5, name, "mono", 11.5, t["muted"], ls=label(11.5))
        chips(svg, col, ry, items, W)
    return svg


def contact(theme: str) -> Svg:
    t = INK[theme]  # ink block in both themes
    page = THEMES[theme]
    h, gap = 290, 18
    c = CONTACT
    svg = Svg(W, h + gap, t, f"04 — Contact. Send me the hard screen. {c['lead']} Email {c['email']}")
    # eyebrow sits on the page, in page colours
    svg.t = page
    index, title, lines = SECTIONS["contact"]
    svg.text(0, 22, index, "monoMedium", 12.5, page["accent"], ls=label(12.5))
    x = measure(index, "monoMedium", 12.5, label(12.5)) + 14
    svg.text(x, 22, title, "mono", 12.5, page["muted"], ls=label(12.5))
    x += measure(title, "mono", 12.5, label(12.5)) + 20
    svg.add(f'<line x1="{x:.1f}" y1="17.5" x2="{W}" y2="17.5" stroke="{page["line"]}"/>')
    svg.t = t
    svg.add(f'<rect x="0.5" y="48.5" width="{W - 1}" height="{h - 50}" rx="20" fill="{t["bg"]}" stroke="{t["line"]}"/>')
    headline(svg, 40, 136, lines, 54, -1.2)
    svg.text(40, 180, c["lead"], "body", 18, t["body"])
    svg.add(f'<line x1="40" y1="210" x2="{W - 40}" y2="210" stroke="{t["line"]}"/>')
    svg.text(40, 250, c["email"], "mono", 15, t["accent"])
    arrow(svg, 40 + measure(c["email"], "mono", 15) + 9, 249, 8, t["accent"])
    svg.text(W - 40, 250, "EMAIL ME", "monoMedium", 12, t["text"], ls=label(12), anchor="end")
    return svg


def social_chip(t: dict, icon: str, text: str) -> Svg:
    """A single link chip: brand glyph + label. One image per link so each can be wrapped in <a>."""
    h, pad, size, gap = 36, 14, 16, 9
    w = round(pad + size + gap + measure(text, "medium", 14.5) + pad)
    svg = Svg(w, h, t, text)
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{h / 2}" fill="{t["bg"]}" stroke="{t["line_strong"]}"/>')
    kind, d = ICONS[icon]
    paint = (f'fill="{t["text"]}"' if kind == "fill"
             else f'fill="none" stroke="{t["text"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')
    svg.add(f'<path transform="translate({pad} {(h - size) / 2}) scale({size / 24})" d="{d}" {paint}/>')
    svg.text(pad + size + gap, h / 2 + 5, text, "medium", 14.5, t["text"])
    return svg


# ------------------------------------------------------------------ main ---


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for theme, t in THEMES.items():
        outputs = {
            "hero": hero(t),
            "work": work_header(t),
            "experience": experience(t),
            "toolkit": toolkit(t),
            "contact": contact(theme),
        }
        for i, pr in enumerate(PROJECTS, 1):
            outputs[f"project-{pr['slug']}"] = project(t, pr, i)
        for slug, icon, text in SOCIAL:
            outputs[f"social-{slug}"] = social_chip(t, icon, text)
        for name, svg in outputs.items():
            with open(os.path.join(OUT_DIR, f"{name}-{theme}.svg"), "w", encoding="utf-8") as f:
                f.write(svg.render())
            count += 1
    print(f"wrote {count} files to {os.path.relpath(OUT_DIR, ROOT)}/")


if __name__ == "__main__":
    main()
