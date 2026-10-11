#!/usr/bin/env python3
"""Generate the SVG assets used by the profile README.

Every section is rendered twice (light + dark) from the same content and
design tokens, with subsetted fonts embedded so typography is identical on
every OS. Text is measured with the real font metrics, so wrapping and chip
layout are exact.

    pip install fonttools brotli
    python3 scripts/build_assets.py
"""
from __future__ import annotations

import base64
import io
import os
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
    "body": "Inter-Regular.woff2",
    "medium": "Inter-Medium.woff2",
    "semibold": "Inter-SemiBold.woff2",
    "display": "InterDisplay-Bold.woff2",
    "displaySemi": "InterDisplay-SemiBold.woff2",
    "mono": "JetBrainsMono-Medium.woff2",
    "arabic": "IBMPlexSansArabic-SemiBold.woff2",
}
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
FALLBACK = {
    "mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    "arabic": "'Segoe UI', Tahoma, sans-serif",
}

THEMES = {
    "dark": dict(
        text="#f0f6fc", muted="#9198a1", faint="#7d8590", border="#30363d",
        card="#161b22", chip="#0d1117", grid="#30363d",
        a1="#22d3ee", a2="#60a5fa", ok="#3fb950",
    ),
    "light": dict(
        text="#1f2328", muted="#59636e", faint="#6e7781", border="#d1d9e0",
        card="#ffffff", chip="#f6f8fa", grid="#d1d9e0",
        a1="#0891b2", a2="#2563eb", ok="#1a7f37",
    ),
}

# --------------------------------------------------------------- content ---

PROFILE = dict(
    name="Abdelrahman Khalifa",
    role="Frontend Developer",
    statement=[
        "I build the interfaces people trust with real cargo",
        "and real money — from Figma to production.",
    ],
    status="OPEN TO NEW OPPORTUNITIES",
    location="CAIRO, EGYPT",
    stats=[("2+", "YEARS IN PRODUCTION"), ("3", "LIVE PLATFORMS"),
           ("Web + Mobile", "REACT · REACT NATIVE")],
)

PROJECTS = [
    dict(
        slug="freightin", title="FreightIn", tag="LIVE · B2B LOGISTICS",
        link="freightin.net ↗",
        text="Book ocean, air and land freight as easily as a flight. Rate search, "
             "multi-step quotation requests and shipment tracking — built from "
             "Figma to production and live today.",
        stack=["Next.js", "TypeScript", "TanStack Query", "Tailwind", "Framer Motion"],
    ),
    dict(
        slug="masroof", title="Masroof", arabic="مصروف", tag="ANDROID · SIDE PROJECT",
        link="private repo · v1.2",
        text="Your bank texts you, Masroof does the bookkeeping. It turns Egyptian "
             "bank SMS into a categorised, offline budget — subscriptions, "
             "installments, savings circles and encrypted backups. Zero network calls.",
        stack=["Expo", "React Native", "Kotlin", "SQLite", "Drizzle", "Zod"],
    ),
    dict(
        slug="traderin", title="TraderIn", tag="LIVE · B2B MARKETPLACE",
        link="traderin.net ↗",
        text="A wholesale marketplace for bulk trading. Seller dashboards for "
             "orders, product catalogue and sales analytics with interactive charts.",
        stack=["Next.js", "TypeScript", "shadcn/ui", "Recharts", "Tailwind"],
    ),
    dict(
        slug="taj", title="Taj", tag="LIVE · EDTECH",
        link="tajteach.com ↗",
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
            "Built FreightIn's front end from Figma: rate search, quotations and shipment tracking.",
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
        points=[
            "Taught HTML, CSS, JavaScript and React to 50+ students; supervised 10+ projects.",
        ],
    ),
    dict(
        when="2017 — 2024", where="EDUCATION", muted=True,
        role="B.Sc. Computer Science", org="Sohag University",
        points=["Then ITI's Front-End & Cross-Platform Mobile diploma (Nov 2023 — Apr 2024)."],
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
    lines=["Have a product that deserves", "a sharp, fast interface?"],
    email="abdelrahmanahmedkhalifa99@gmail.com",
)

# Brand glyphs from Simple Icons (CC0); mail/globe drawn as strokes. 24x24 viewBox.
ICONS = {
    "linkedin": ("fill", "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"),
    "x": ("fill", "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"),
    "instagram": ("fill", "M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678c-3.405 0-6.162 2.76-6.162 6.162 0 3.405 2.76 6.162 6.162 6.162 3.405 0 6.162-2.76 6.162-6.162 0-3.405-2.76-6.162-6.162-6.162zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm7.846-10.405c0 .795-.646 1.44-1.44 1.44-.795 0-1.44-.646-1.44-1.44 0-.794.646-1.439 1.44-1.439.793-.001 1.44.645 1.44 1.439z"),
    "mail": ("stroke", "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z M22 7l-10 6L2 7"),
    "globe": ("stroke", "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20Z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10a15.3 15.3 0 0 1-4 10a15.3 15.3 0 0 1-4-10a15.3 15.3 0 0 1 4-10Z"),
}

SOCIAL = [
    ("portfolio", "globe", "Portfolio"),
    ("linkedin", "linkedin", "LinkedIn"),
    ("x", "x", "X"),
    ("instagram", "instagram", "Instagram"),
    ("email", "mail", "Email"),
]

# ----------------------------------------------------------- font utils ---


@lru_cache(None)
def _font(key: str) -> TTFont:
    return TTFont(os.path.join(FONT_DIR, FONTS[key]))


@lru_cache(None)
def _metrics(key: str):
    f = _font(key)
    return f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm


def measure(s: str, font: str, size: float, ls: float = 0) -> float:
    cmap, hmtx, upem = _metrics(font)
    total = 0
    for ch in s:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] if g else upem * 0.6
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
        self.defs: list[str] = []
        self.css: list[str] = []
        self.used: dict[str, set] = defaultdict(set)

    def add(self, s: str):
        self.parts.append(s)

    def text(self, x, y, s, font="body", size=16, fill=None, ls=0, anchor="start", attrs=""):
        self.used[font].update(s)
        fill = fill or self.t["text"]
        ls_attr = f' letter-spacing="{ls}"' if ls else ""
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="f-{font}" font-size="{size}" '
                 f'fill="{fill}"{ls_attr}{anchor_attr}{attrs}>{esc(s)}</text>')

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
            f"<title>{esc(self.label)}</title>\n"
            f"<defs>{''.join(self.defs)}</defs>\n<style>\n{style}\n</style>\n"
            + "\n".join(self.parts) + "\n</svg>\n"
        )


def accent_gradient(svg: Svg, gid="ac", vertical=False):
    t = svg.t
    x2, y2 = ("0", "1") if vertical else ("1", "0")
    svg.defs.append(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">'
        f'<stop offset="0" stop-color="{t["a1"]}"/><stop offset="1" stop-color="{t["a2"]}"/></linearGradient>'
    )


def section_label(svg: Svg, y: float, index: str, title: str):
    t = svg.t
    svg.text(0, y, index, "mono", 13, "url(#ac)", ls=1)
    x = measure(index, "mono", 13, 1) + 14
    svg.text(x, y, title, "mono", 13, t["muted"], ls=2.4)
    x += measure(title, "mono", 13, 2.4) + 20
    svg.add(f'<line x1="{x:.1f}" y1="{y - 4.5}" x2="{W}" y2="{y - 4.5}" stroke="{t["border"]}"/>')


def chips(svg: Svg, x0: float, y: float, items: list[str], max_x: float, h=28, gap=8) -> float:
    t = svg.t
    x = x0
    for item in items:
        w = measure(item, "mono", 12) + 24
        if x + w > max_x and x > x0:
            x, y = x0, y + h + gap
        svg.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="7" '
                f'fill="{t["chip"]}" stroke="{t["border"]}"/>')
        svg.text(x + 12, y + h / 2 + 4.2, item, "mono", 12, t["muted"])
        x += w + gap
    return y + h


REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important;}}"

# -------------------------------------------------------------- sections ---


def hero(t: dict) -> Svg:
    p = PROFILE
    svg = Svg(W, 420, t, f"{p['name']} — {p['role']}. " + " ".join(p["statement"]))
    accent_gradient(svg)

    # dot grid + route graphic on the right
    svg.defs.append(
        f'<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1.1" fill="{t["grid"]}"/></pattern>'
        '<radialGradient id="fade" cx="0.6" cy="0.5" r="0.55">'
        '<stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<mask id="m"><rect x="560" y="0" width="320" height="360" fill="url(#fade)"/></mask>'
    )
    svg.css.append(
        ".flow{stroke-dasharray:3 7;animation:flow 1.4s linear infinite}"
        "@keyframes flow{to{stroke-dashoffset:-20}}"
        ".pulse{animation:pulse 2.2s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}" + REDUCED
    )
    svg.add('<rect x="560" y="0" width="320" height="360" fill="url(#dots)" mask="url(#m)"/>')
    route = "M612 300 C 680 300, 676 196, 744 196 S 806 92, 860 92"
    svg.add(f'<path d="{route}" fill="none" stroke="{t["border"]}" stroke-width="2"/>')
    svg.add(f'<path d="{route}" fill="none" stroke="url(#ac)" stroke-width="2" class="flow"/>')
    for (cx, cy, label, lx, ly, anchor) in [
        (612, 300, "figma", 612, 330, "middle"),
        (744, 196, "code", 762, 172, "start"),
        (860, 92, "production", 860, 66, "end"),
    ]:
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="12" fill="none" stroke="{t["a1"]}" stroke-opacity=".35"/>')
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="5" fill="url(#ac)"/>')
        svg.text(lx, ly, label, "mono", 12, t["faint"], anchor=anchor)
    svg.add(f'<circle r="3.5" fill="{t["a1"]}"><animateMotion dur="4s" repeatCount="indefinite" path="{route}"/></circle>')

    # status pill
    pill = p["status"]
    pw = measure(pill, "mono", 11.5, 1.6) + 46
    svg.add(f'<rect x="1" y="20" width="{pw:.1f}" height="30" rx="15" fill="none" stroke="{t["border"]}"/>')
    svg.add(f'<circle cx="19" cy="35" r="4.5" fill="{t["ok"]}" class="pulse"/>')
    svg.text(32, 39.2, pill, "mono", 11.5, t["muted"], ls=1.6)
    svg.text(pw + 18, 39.2, "/  " + p["location"], "mono", 11.5, t["faint"], ls=1.6)

    # name, role, statement
    size = 64
    while measure(p["name"], "display", size, -1.2) > 560:
        size -= 1
    svg.text(-2, 126, p["name"], "display", size, t["text"], ls=-1.2)
    svg.text(0, 170, p["role"], "displaySemi", 30, "url(#ac)", ls=-0.4)
    for i, line in enumerate(p["statement"]):
        svg.text(0, 222 + i * 30, line, "body", 19.5, t["muted"])

    # stats row
    x = 0
    for num, cap in p["stats"]:
        svg.text(x, 352, num, "displaySemi", 30, t["text"], ls=-0.4)
        svg.text(x, 380, cap, "mono", 10.5, t["faint"], ls=1.4)
        x += max(measure(num, "displaySemi", 30), measure(cap, "mono", 10.5, 1.4)) + 44
    return svg


def work_header(t: dict) -> Svg:
    svg = Svg(W, 34, t, "Selected work")
    accent_gradient(svg)
    section_label(svg, 22, "01", "SELECTED WORK")
    return svg


def project(t: dict, pr: dict, index: int) -> Svg:
    h, gap = 214, 14  # gap: transparent space below the card so stacked cards breathe
    svg = Svg(W, h + gap, t, f"{pr['title']} — {pr['tag'].title()}. {pr['text']} Stack: {', '.join(pr['stack'])}.")
    accent_gradient(svg)
    accent_gradient(svg, "acv", vertical=True)
    svg.add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="16" fill="{t["card"]}" stroke="{t["border"]}"/>')
    svg.add(f'<rect x="0.5" y="40" width="3" height="56" rx="1.5" fill="url(#acv)"/>')

    left = 32
    svg.text(left, 50, f"{index:02d}", "mono", 12.5, "url(#ac)", ls=1)
    svg.text(left - 1, 92, pr["title"], "display", 32, t["text"], ls=-0.6)
    if pr.get("arabic"):
        x = left + measure(pr["title"], "display", 32, -0.6) + 12
        svg.text(x, 91, pr["arabic"], "arabic", 22, t["faint"])
    svg.text(left, 122, pr["tag"], "mono", 11, t["faint"], ls=1.5)
    link_fill = "url(#ac)" if pr["link"].endswith("↗") else t["faint"]
    svg.text(left, h - 34, pr["link"], "mono", 13, link_fill)

    col = 318
    svg.add(f'<line x1="{col - 26}" y1="32" x2="{col - 26}" y2="{h - 32}" stroke="{t["border"]}" stroke-dasharray="2 5"/>')
    lines = wrap(pr["text"], "body", 16, W - col - 32)
    for i, line in enumerate(lines):
        svg.text(col, 52 + i * 25, line, "body", 16, t["muted"])
    chips(svg, col, h - 32 - 28, pr["stack"], W - 32)
    assert len(lines) <= 4, f"{pr['slug']}: description too long ({len(lines)} lines)"
    return svg


def experience(t: dict) -> Svg:
    left_w, rail, body_x = 176, 196, 226
    y = 70
    blocks = []
    for e in EXPERIENCE:
        pts = [wrap(pt, "body", 15, W - body_x) for pt in e["points"]]
        height = 30 + sum(len(p) for p in pts) * 23 + (len(pts) - 1) * 6
        blocks.append((e, pts, y))
        y += height + 30
    svg = Svg(W, int(y - 10), t, "Experience. " + " ".join(
        f"{e['role']} at {e['org']} ({e['when'].title()}): {' '.join(e['points'])}" for e in EXPERIENCE))
    accent_gradient(svg)
    accent_gradient(svg, "acv", vertical=True)
    svg.css.append(".pulse{animation:pulse 2.2s ease-in-out infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}" + REDUCED)
    section_label(svg, 22, "02", "EXPERIENCE")

    first_y, last_y = blocks[0][2], blocks[-1][2]
    svg.add(f'<line x1="{rail}" y1="{first_y - 6}" x2="{rail}" y2="{last_y - 6}" stroke="{t["border"]}" stroke-width="1.5"/>')
    svg.add(f'<line x1="{rail}" y1="{first_y - 6}" x2="{rail}" y2="{blocks[1][2] - 6}" stroke="url(#acv)" stroke-width="1.5"/>')

    for e, pts, by in blocks:
        muted = e.get("muted")
        svg.text(0, by, e["when"], "mono", 11.5, t["muted"] if not muted else t["faint"], ls=1.2)
        svg.text(0, by + 20, e["where"], "mono", 10.5, t["faint"], ls=1.4)
        if e.get("current"):
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="10" fill="{t["a1"]}" fill-opacity=".18" class="pulse"/>')
        if muted:
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="4.5" fill="{t["chip"]}" stroke="{t["faint"]}" stroke-width="1.5"/>')
        else:
            svg.add(f'<circle cx="{rail}" cy="{by - 6}" r="5" fill="url(#ac)"/>')
        svg.text(body_x, by, e["role"], "displaySemi", 19, t["text"] if not muted else t["muted"], ls=-0.2)
        rx = body_x + measure(e["role"], "displaySemi", 19, -0.2) + 10
        svg.text(rx, by, "· " + e["org"], "medium", 16, t["muted"])
        ly = by + 30
        for lines in pts:
            for line in lines:
                svg.text(body_x, ly, line, "body", 15, t["muted"] if not muted else t["faint"])
                ly += 23
            ly += 6
    return svg


def toolkit(t: dict) -> Svg:
    y = 62
    rows = []
    for label, items in TOOLKIT:
        rows.append((label, items, y))
        # pre-measure to know how many chip rows this group needs
        x, n = 176, 1
        for item in items:
            w = measure(item, "mono", 12) + 24
            if x + w > W and x > 176:
                x, n = 176, n + 1
            x += w + 8
        y += n * 36 + 12
    svg = Svg(W, int(y - 8), t, "Toolkit. " + " ".join(f"{l.title()}: {', '.join(i)}." for l, i, _ in rows))
    accent_gradient(svg)
    section_label(svg, 22, "03", "TOOLKIT")
    for label, items, ry in rows:
        svg.text(0, ry + 18.5, label, "mono", 11, t["faint"], ls=1.6)
        chips(svg, 176, ry, items, W)
    return svg


def contact(t: dict) -> Svg:
    h, gap = 250, 18
    c = CONTACT
    svg = Svg(W, h + gap, t, " ".join(c["lines"]) + f" Email {c['email']}")
    accent_gradient(svg)
    svg.defs.append(
        f'<radialGradient id="glow" cx="1" cy="0" r="0.9"><stop offset="0" stop-color="{t["a1"]}" stop-opacity=".16"/>'
        f'<stop offset="1" stop-color="{t["a1"]}" stop-opacity="0"/></radialGradient>'
    )
    section_label(svg, 22, "04", "CONTACT")
    svg.add(f'<rect x="0.5" y="48.5" width="{W - 1}" height="{h - 50}" rx="16" fill="{t["card"]}" stroke="{t["border"]}"/>')
    svg.add(f'<rect x="0.5" y="48.5" width="{W - 1}" height="{h - 50}" rx="16" fill="url(#glow)"/>')
    for i, line in enumerate(c["lines"]):
        svg.text(32, 112 + i * 44, line, "display", 36, t["text"], ls=-0.8)
    svg.text(32, 210, c["email"] + "  ↗", "mono", 14, "url(#ac)")
    return svg



def social_chip(t: dict, icon: str, label: str) -> Svg:
    """A single link chip: brand glyph + label. One image per link so each can be wrapped in <a>."""
    h, pad, size, gap = 36, 14, 16, 9
    w = round(pad + size + gap + measure(label, "medium", 14) + pad)
    svg = Svg(w, h, t, label)
    svg.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{t["card"]}" stroke="{t["border"]}"/>')
    kind, d = ICONS[icon]
    paint = (f'fill="{t["text"]}"' if kind == "fill"
             else f'fill="none" stroke="{t["text"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')
    svg.add(f'<path transform="translate({pad} {(h - size) / 2}) scale({size / 24})" d="{d}" {paint}/>')
    svg.text(pad + size + gap, h / 2 + 5, label, "medium", 14, t["text"])
    return svg


# ------------------------------------------------------------------ main ---


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    builders = {
        "hero": hero,
        "work": work_header,
        "experience": experience,
        "toolkit": toolkit,
        "contact": contact,
    }
    for theme, t in THEMES.items():
        outputs = {name: fn(t) for name, fn in builders.items()}
        for i, pr in enumerate(PROJECTS, 1):
            outputs[f"project-{pr['slug']}"] = project(t, pr, i)
        for slug, icon, label in SOCIAL:
            outputs[f"social-{slug}"] = social_chip(t, icon, label)
        for name, svg in outputs.items():
            path = os.path.join(OUT_DIR, f"{name}-{theme}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg.render())
    print(f"wrote {len(outputs) * len(THEMES)} files to {os.path.relpath(OUT_DIR, ROOT)}/")


if __name__ == "__main__":
    main()
