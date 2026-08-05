#!/usr/bin/env python3
"""Generate Easy-Books pictograph slides + narrated MP4 for docs/marketing/.

Outputs:
  slides/01-….png … 12-….png
  audio/01-….wav …
  video/easy-books-overview.mp4
  video/concat.txt (ffmpeg helper)
"""
from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SLIDES = ROOT / "slides"
AUDIO = ROOT / "audio"
VIDEO = ROOT / "video"

W, H = 1920, 1080
BG = (18, 28, 44)          # deep slate
PANEL = (28, 42, 64)       # raised panel
GOLD = (201, 162, 78)      # brand accent (cooler than terracotta)
CREAM = (236, 240, 245)    # cool off-white
MUTED = (148, 163, 184)
TEAL = (45, 168, 150)
CORAL = (232, 120, 98)
BLUE = (96, 165, 250)

FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

# (slug, title, bullets, voiceover)
SLIDES_SPEC: list[tuple[str, str, list[str], str]] = [
    (
        "01-title",
        "Easy-Books",
        [
            "Double-entry bookkeeping for SMEs — with industry depth",
            "FastAPI · Next.js · IFRS-aligned · Multi-tenant",
            "Desktop · Docker · Cloud (Vercel + Neon)",
        ],
        "Welcome to Easy-Books — modern double-entry bookkeeping built for growing SMEs. "
        "One product that combines familiar accounting with deep industry workflows, "
        "IFRS worksheets, and an agentic AI assistant.",
    ),
    (
        "02-problem",
        "The SME accounting gap",
        [
            "QuickBooks is friendly — but thin on vertical ops",
            "Odoo is deep — but heavy to adopt and run",
            "Spreadsheets drift — no single source of financial truth",
            "Local ownership and SaaS agility rarely coexist",
        ],
        "Most SMEs are stuck between tools that are easy but shallow, "
        "and ERPs that are powerful but expensive to adopt. "
        "Easy-Books closes that gap with one general ledger and installable industry packs.",
    ),
    (
        "03-architecture",
        "One GL. Every number lives there.",
        [
            "Browser → Next.js → FastAPI → posting.py",
            "Invariant: sum of debits equals sum of credits",
            "Decimal money · tenant isolation · period locks",
            "No shadow balances — reports read live journal entries",
        ],
        "Architecture is deliberate. Every financial write goes through a single posting service. "
        "Debits always equal credits. Money is Decimal. Tenants never leak. "
        "What you see on a report is what hit the journal.",
    ),
    (
        "04-industries",
        "Industry packs, not a one-size ERP",
        [
            "Base Accounting for every company",
            "Manufacturing · Weaving · Yarn Spinning · Textile Processing",
            "Healthcare · Telecom Franchise · Purchases & Store",
            "Localization: PRA · ZATCA · India GST · Peppol · UAE VAT",
        ],
        "Companies start with base accounting, then install what they need — "
        "manufacturing, weaving, yarn spinning, textile processing, healthcare, telecom, "
        "and country localization packs — without rewriting the chart of accounts.",
    ),
    (
        "05-processing",
        "Use case: Textile Processing",
        [
            "Customer-owned grey lots — custody, not inventory value",
            "Mending → Kachi / Pakki Parchi → PPC stages",
            "Process billing 4150 · wastage 4160 · contractor labor 5220",
            "Grey settlement closes the customer stock loop",
        ],
        "Textile processing units track customer fabric as custody stock. "
        "Lots move through mending, kachi and pakki parchi, PPC stages, and fresh dispatch. "
        "Billing, wastage sales, contractor labor, and shrinkage post to dedicated accounts — "
        "then grey settlement closes the loop.",
    ),
    (
        "06-spinning",
        "Use case: Yarn Spinning with full GL",
        [
            "Bale receipt → multi-stage WIP → cone output → dispatch",
            "Stage costing credits labour and overhead",
            "Waste types mapped to expense accounts",
            "Yield calculator and lot-control reports",
        ],
        "Yarn spinning is not a memo module. Bale receipt, stage entries, cone output, "
        "and dispatch all post to the general ledger — with labour, overhead, waste, "
        "and COGS so mill managers see true lot economics.",
    ),
    (
        "07-ops-verticals",
        "Healthcare, Telecom, Purchases & Store",
        [
            "Hospital: OPD, IPD, lab, procedures, pharmacy",
            "Telecom: tracker load, RSO, devices, postpaid",
            "Purchases: demand → quotation → comparative → PO",
            "Store: gate inward/outward, issues, three-way match",
        ],
        "Beyond textiles, Easy-Books covers hospital OPD and IPD workflows, "
        "telecom franchise tracker and load operations, and a full purchase-to-store chain "
        "with gate control and three-way match — all still posting into one ledger.",
    ),
    (
        "08-ifrs",
        "IFRS depth uncommon in SME tools",
        [
            "IFRS 10 consolidation worksheets",
            "IFRS 16 leases · IFRS 15 SSP and contract assets",
            "Intercompany recon · dimensional analytics",
            "Month-end close checklist and auditor pack",
        ],
        "Advanced accounting is not an afterthought. Consolidation, leases, revenue allocation, "
        "intercompany reconciliation, and month-end close tools give finance teams "
        "worksheet depth usually reserved for much larger systems.",
    ),
    (
        "09-ai",
        "Agentic AI Financial Assistant",
        [
            "Triage → Specialist → Reviewer → Drafting pipeline",
            "Fifty-plus read-only tools over live reports",
            "Anthropic, OpenAI, Gemini, or self-hosted Ollama",
            "Answers with figures — fact-checked against tool results",
        ],
        "The AI assistant is agentic, not a chatbot glued on. "
        "It routes questions to specialists, calls real report tools, "
        "reviews figures, then drafts a polished answer — "
        "with your choice of cloud or self-hosted models.",
    ),
    (
        "10-deploy",
        "Run it your way",
        [
            "One-click script installer — Windows and macOS/Linux",
            "Electron desktop app for offline-friendly offices",
            "Docker Compose for team LAN servers",
            "Cloud: frontend and API on Vercel, database on Neon",
        ],
        "Deploy how you operate. One-click installers and a desktop app for local ownership. "
        "Docker for the office network. Or cloud with Vercel and Neon Postgres — "
        "same product, same double-entry engine.",
    ),
    (
        "11-advantages",
        "Why teams switch to Easy-Books",
        [
            "Vertical ops + real IFRS in one SME product",
            "Installable modules — grow without re-platforming",
            "Open, modern stack you can audit and extend",
            "AI that reads your books, not generic web answers",
        ],
        "Teams switch because Easy-Books combines vertical operations and IFRS worksheets "
        "in a product SMEs can actually run — with modules that grow with them, "
        "and an AI layer grounded in their own ledger.",
    ),
    (
        "12-cta",
        "Start in minutes",
        [
            "Demo: demo.simple@easy-books.app / demo1234",
            "Processing: demo.processing@easy-books.app",
            "Spinning: demo.spinning@easy-books.app",
            "Add-ons → install industry packs · Settings → Advanced for CoA guides",
        ],
        "Get started in minutes. Sign in with a demo company, explore financial and operations homes, "
        "install industry packs from Add-ons, and use Settings Advanced for processing CoA guidance. "
        "Easy-Books — books you can trust, operations you can run.",
    ),
]


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def draw_bg(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, H), fill=BG)
    # subtle diagonal bands
    for i in range(0, W + H, 80):
        draw.line([(i, 0), (i - H, H)], fill=(24, 36, 54), width=40)
    # gold top accent
    draw.rectangle((0, 0, W, 8), fill=GOLD)
    draw.rectangle((0, H - 8, W, H), fill=GOLD)


def draw_pictograph_row(draw: ImageDraw.ImageDraw, y: int, items: list[tuple[str, tuple[int, int, int]]]) -> None:
    """Simple icon-like rounded tiles as pictographs."""
    n = len(items)
    gap = 28
    tile_w = min(260, (W - 160 - gap * (n - 1)) // n)
    total = n * tile_w + (n - 1) * gap
    x0 = (W - total) // 2
    for i, (label, color) in enumerate(items):
        x = x0 + i * (tile_w + gap)
        draw.rounded_rectangle((x, y, x + tile_w, y + 120), radius=18, fill=PANEL, outline=color, width=3)
        # glyph circle
        cx, cy = x + tile_w // 2, y + 42
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=color)
        fnt = font(FONT_BOLD, 16)
        lines = wrap(draw, label, fnt, tile_w - 24)
        ty = y + 78
        for line in lines[:2]:
            tw = draw.textlength(line, font=fnt)
            draw.text(((x + (tile_w - tw) / 2), ty), line, font=fnt, fill=CREAM)
            ty += 18


def render_slide(slug: str, title: str, bullets: list[str], index: int, total: int) -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw_bg(img)
    draw = ImageDraw.Draw(img)

    # brand mark
    brand = font(FONT_BOLD, 28)
    draw.text((80, 40), "EASY-BOOKS", font=brand, fill=GOLD)
    draw.text((W - 200, 44), f"{index}/{total}", font=font(FONT_SANS, 22), fill=MUTED)

    # title
    title_fnt = font(FONT_SERIF, 64 if len(title) < 36 else 52)
    for i, line in enumerate(wrap(draw, title, title_fnt, W - 160)[:2]):
        draw.text((80, 110 + i * 72), line, font=title_fnt, fill=CREAM)

    # pictograph strip by slide theme
    pictos: dict[str, list[tuple[str, tuple[int, int, int]]]] = {
        "01-title": [("Books", GOLD), ("Ops", TEAL), ("IFRS", BLUE), ("AI", CORAL)],
        "02-problem": [("Shallow", CORAL), ("Heavy", MUTED), ("Drift", CORAL), ("Gap", GOLD)],
        "03-architecture": [("UI", BLUE), ("API", TEAL), ("Posting", GOLD), ("GL", CREAM)],
        "04-industries": [("Spin", TEAL), ("Process", GOLD), ("Health", CORAL), ("Telecom", BLUE)],
        "05-processing": [("Grey Lot", TEAL), ("Parchi", GOLD), ("PPC", BLUE), ("Settle", CORAL)],
        "06-spinning": [("Bale", GOLD), ("WIP", TEAL), ("Cone", BLUE), ("Dispatch", CORAL)],
        "07-ops-verticals": [("OPD", CORAL), ("Tracker", BLUE), ("Demand", GOLD), ("Gate", TEAL)],
        "08-ifrs": [("IFRS 10", GOLD), ("IFRS 16", TEAL), ("IFRS 15", BLUE), ("Close", CORAL)],
        "09-ai": [("Triage", BLUE), ("Tools", TEAL), ("Review", GOLD), ("Draft", CORAL)],
        "10-deploy": [("Desktop", GOLD), ("Docker", TEAL), ("Vercel", BLUE), ("Neon", CORAL)],
        "11-advantages": [("Depth", GOLD), ("Modules", TEAL), ("Open", BLUE), ("AI", CORAL)],
        "12-cta": [("Demo", GOLD), ("Processing", TEAL), ("Spinning", BLUE), ("Add-ons", CORAL)],
    }
    draw_pictograph_row(draw, 280, pictos.get(slug, [("Module", GOLD)] * 4))

    # bullets panel
    panel_top = 440
    draw.rounded_rectangle((80, panel_top, W - 80, H - 80), radius=24, fill=PANEL)
    bullet_fnt = font(FONT_SANS, 34)
    y = panel_top + 48
    for b in bullets:
        draw.ellipse((120, y + 12, 140, y + 32), fill=GOLD)
        for j, line in enumerate(wrap(draw, b, bullet_fnt, W - 280)):
            draw.text((170, y + j * 42), line, font=bullet_fnt, fill=CREAM)
        y += 42 * max(1, len(wrap(draw, b, bullet_fnt, W - 280))) + 18

    out = SLIDES / f"{slug}.png"
    img.save(out, "PNG", optimize=True)
    return out


def synth_voice(text: str, wav_path: Path) -> float:
    """Generate WAV via espeak-ng; return duration seconds."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "espeak-ng",
            "-v", "en-us",
            "-s", "145",
            "-p", "40",
            "-a", "160",
            "-w", str(wav_path),
            text,
        ],
        check=True,
        capture_output=True,
    )
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def build_video(slide_paths: list[Path], audio_paths: list[Path], durations: list[float]) -> Path:
    VIDEO.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for i, (slide, audio, dur) in enumerate(zip(slide_paths, audio_paths, durations), start=1):
        # hold slide slightly longer than audio
        hold = max(dur + 0.6, 4.0)
        seg = VIDEO / f"seg_{i:02d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(slide),
                "-i", str(audio),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-t", f"{hold:.2f}",
                "-vf", f"scale={W}:{H},fps=30",
                str(seg),
            ],
            check=True,
            capture_output=True,
        )
        segments.append(seg)

    concat_list = VIDEO / "concat.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in segments))
    out = VIDEO / "easy-books-overview.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out),
        ],
        check=True,
        capture_output=True,
        cwd=str(VIDEO),
    )
    return out


def main() -> None:
    SLIDES.mkdir(parents=True, exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)

    slide_paths: list[Path] = []
    audio_paths: list[Path] = []
    durations: list[float] = []
    total = len(SLIDES_SPEC)

    script_lines = ["# Easy-Books — Presentation Voiceover Script\n", f"_Generated from {total} slides._\n"]

    for idx, (slug, title, bullets, vo) in enumerate(SLIDES_SPEC, start=1):
        print(f"[{idx}/{total}] {slug}")
        sp = render_slide(slug, title, bullets, idx, total)
        ap = AUDIO / f"{slug}.wav"
        dur = synth_voice(vo, ap)
        slide_paths.append(sp)
        audio_paths.append(ap)
        durations.append(dur)
        script_lines.append(f"## Slide {idx}: {title}\n")
        script_lines.append(f"**Duration (approx):** {dur:.1f}s\n")
        for b in bullets:
            script_lines.append(f"- {b}")
        script_lines.append("")
        script_lines.append(f"> {vo}\n")

    (ROOT / "VOICEOVER_SCRIPT.md").write_text("\n".join(script_lines) + "\n")
    out = build_video(slide_paths, audio_paths, durations)
    total_dur = sum(max(d + 0.6, 4.0) for d in durations)
    print(f"Wrote {out} (~{total_dur:.0f}s)")
    print(f"Slides: {SLIDES}")
    print(f"Script: {ROOT / 'VOICEOVER_SCRIPT.md'}")


if __name__ == "__main__":
    main()
