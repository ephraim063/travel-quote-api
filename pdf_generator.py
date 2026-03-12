import io
import requests
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image, PageBreak
)
from reportlab.lib.utils import ImageReader

# ─────────────────────────────────────────────────────────────────
# SafariFlow PDF Generator v2.0
# Generates: Quote PDF, Receipt PDF, Accommodation Voucher, Transport Voucher
# Maintains original Navy + Gold branding
# ─────────────────────────────────────────────────────────────────

# ─── Brand Colors (unchanged) ────────────────────────────────────
NAVY        = colors.HexColor("#0D1E35")
NAVY_MID    = colors.HexColor("#1A2E4A")
GOLD        = colors.HexColor("#C8A96E")
GOLD_LIGHT  = colors.HexColor("#E8C98E")
GOLD_BG     = colors.HexColor("#FBF6EE")
SAGE        = colors.HexColor("#4A7C59")
CREAM       = colors.HexColor("#FAFAF8")
LIGHT_GREY  = colors.HexColor("#F4F4F2")
BORDER      = colors.HexColor("#E0DDD8")
WHITE       = colors.white
TEXT_DARK   = colors.HexColor("#1A1A1A")
TEXT_MID    = colors.HexColor("#555550")
TEXT_LIGHT  = colors.HexColor("#999990")
GREEN       = colors.HexColor("#27AE60")
RED         = colors.HexColor("#E74C3C")

PAGE_W, PAGE_H = A4
MARGIN  = 16 * mm
INNER_W = PAGE_W - 2 * MARGIN


# ─── Styles (unchanged + new additions) ──────────────────────────
def S():
    return {
        "agency": ParagraphStyle("agency", fontSize=15, fontName="Helvetica-Bold",
            textColor=WHITE, leading=20),
        "agency_sub": ParagraphStyle("agency_sub", fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#AABBCC"), leading=12, letterSpacing=1.5),
        "doc_type": ParagraphStyle("doc_type", fontSize=9, fontName="Helvetica-Bold",
            textColor=GOLD, leading=13, letterSpacing=2),
        "hero_name": ParagraphStyle("hero_name", fontSize=20, fontName="Helvetica-Bold",
            textColor=NAVY, leading=26),
        "hero_dest": ParagraphStyle("hero_dest", fontSize=11, fontName="Helvetica",
            textColor=TEXT_MID, leading=16),
        "label": ParagraphStyle("label", fontSize=7, fontName="Helvetica-Bold",
            textColor=TEXT_LIGHT, leading=11, letterSpacing=1.2),
        "value": ParagraphStyle("value", fontSize=10, fontName="Helvetica-Bold",
            textColor=TEXT_DARK, leading=14),
        "value_gold": ParagraphStyle("value_gold", fontSize=10, fontName="Helvetica-Bold",
            textColor=GOLD, leading=14),
        "body": ParagraphStyle("body", fontSize=9.5, fontName="Helvetica",
            textColor=TEXT_DARK, leading=14),
        "body_mid": ParagraphStyle("body_mid", fontSize=9, fontName="Helvetica",
            textColor=TEXT_MID, leading=13),
        "body_small": ParagraphStyle("body_small", fontSize=8, fontName="Helvetica",
            textColor=TEXT_LIGHT, leading=12),
        "section_title": ParagraphStyle("section_title", fontSize=8, fontName="Helvetica-Bold",
            textColor=NAVY, leading=12, letterSpacing=1.5),
        "item_desc": ParagraphStyle("item_desc", fontSize=9.5, fontName="Helvetica-Bold",
            textColor=TEXT_DARK, leading=13),
        "item_detail": ParagraphStyle("item_detail", fontSize=8.5, fontName="Helvetica",
            textColor=TEXT_MID, leading=12),
        "price": ParagraphStyle("price", fontSize=9.5, fontName="Helvetica",
            textColor=TEXT_DARK, leading=13, alignment=TA_RIGHT),
        "price_bold": ParagraphStyle("price_bold", fontSize=9.5, fontName="Helvetica-Bold",
            textColor=TEXT_DARK, leading=13, alignment=TA_RIGHT),
        "total_label": ParagraphStyle("total_label", fontSize=10, fontName="Helvetica-Bold",
            textColor=GOLD_LIGHT, leading=14),
        "total_amount": ParagraphStyle("total_amount", fontSize=20, fontName="Helvetica-Bold",
            textColor=WHITE, leading=24, alignment=TA_RIGHT),
        "footer": ParagraphStyle("footer", fontSize=7.5, fontName="Helvetica",
            textColor=TEXT_LIGHT, leading=11, alignment=TA_CENTER),
        "agent_name": ParagraphStyle("agent_name", fontSize=11, fontName="Helvetica-Bold",
            textColor=NAVY, leading=16),
        "note": ParagraphStyle("note", fontSize=8.5, fontName="Helvetica",
            textColor=TEXT_MID, leading=13),
        "inc_title": ParagraphStyle("inc_title", fontSize=8, fontName="Helvetica-Bold",
            textColor=SAGE, leading=12, letterSpacing=1),
        "exc_title": ParagraphStyle("exc_title", fontSize=8, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#C0392B"), leading=12, letterSpacing=1),
        "inc_item": ParagraphStyle("inc_item", fontSize=9, fontName="Helvetica",
            textColor=TEXT_DARK, leading=13),
        "right_label": ParagraphStyle("right_label", fontSize=8, fontName="Helvetica",
            textColor=TEXT_MID, leading=12, alignment=TA_RIGHT),
        # New styles for v2
        "narrative": ParagraphStyle("narrative", fontSize=10, fontName="Helvetica",
            textColor=TEXT_DARK, leading=16),
        "narrative_intro": ParagraphStyle("narrative_intro", fontSize=11, fontName="Helvetica",
            textColor=TEXT_MID, leading=17, leftIndent=8,
            borderPadding=(8, 0, 8, 0)),
        "day_title": ParagraphStyle("day_title", fontSize=13, fontName="Helvetica-Bold",
            textColor=WHITE, leading=18),
        "day_narrative": ParagraphStyle("day_narrative", fontSize=9.5, fontName="Helvetica",
            textColor=TEXT_DARK, leading=15),
        "highlight": ParagraphStyle("highlight", fontSize=9, fontName="Helvetica-Bold",
            textColor=SAGE, leading=13),
        "review_text": ParagraphStyle("review_text", fontSize=9.5, fontName="Helvetica",
            textColor=TEXT_DARK, leading=15),
        "reviewer": ParagraphStyle("reviewer", fontSize=8, fontName="Helvetica-Bold",
            textColor=GOLD, leading=12),
        "award_item": ParagraphStyle("award_item", fontSize=9, fontName="Helvetica",
            textColor=TEXT_DARK, leading=13),
        "bio": ParagraphStyle("bio", fontSize=9.5, fontName="Helvetica",
            textColor=TEXT_MID, leading=15),
        "social": ParagraphStyle("social", fontSize=9, fontName="Helvetica",
            textColor=GOLD, leading=13),
        "voucher_title": ParagraphStyle("voucher_title", fontSize=18, fontName="Helvetica-Bold",
            textColor=WHITE, leading=24),
        "voucher_ref": ParagraphStyle("voucher_ref", fontSize=10, fontName="Helvetica-Bold",
            textColor=GOLD, leading=14),
        "receipt_amount": ParagraphStyle("receipt_amount", fontSize=24, fontName="Helvetica-Bold",
            textColor=WHITE, leading=30, alignment=TA_RIGHT),
        "center": ParagraphStyle("center", fontSize=9, fontName="Helvetica",
            textColor=TEXT_MID, leading=13, alignment=TA_CENTER),
    }


def fmt_currency(amount, symbol="$"):
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"


def fmt_cents(cents, symbol="$"):
    try:
        return fmt_currency(float(cents) / 100, symbol)
    except:
        return f"{symbol}0.00"


def stars(rating):
    try:
        r = int(float(rating))
        return "★" * r + "☆" * (5 - r)
    except:
        return "★★★★★"


# ─── Fetch image from URL ─────────────────────────────────────────
def fetch_image(url, width, height):
    """Fetch image from URL and return ReportLab Image object"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_buffer = io.BytesIO(response.content)
            return Image(img_buffer, width=width, height=height)
    except Exception as e:
        print(f"[WARN] Could not fetch image: {url} — {e}")
    return None


def fetch_unsplash_image(query, width, height, access_key=None):
    """Fetch a relevant image from Unsplash API"""
    if not access_key:
        return None
    try:
        url = f"https://api.unsplash.com/search/photos?query={query}&orientation=landscape&per_page=1"
        headers = {"Authorization": f"Client-ID {access_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                img_url = data["results"][0]["urls"]["regular"]
                return fetch_image(img_url, width, height)
    except Exception as e:
        print(f"[WARN] Unsplash fetch failed: {e}")
    return None


# ─── Page Canvas (header + footer) — unchanged ───────────────────
def draw_page(canvas, doc, agency_name, agent_email, doc_label):
    canvas.saveState()
    w, h = A4

    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 20*mm, w, 20*mm, fill=1, stroke=0)

    canvas.setFillColor(GOLD)
    canvas.rect(0, h - 21.5*mm, w, 1.5*mm, fill=1, stroke=0)

    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(WHITE)
    canvas.drawString(MARGIN, h - 11*mm, agency_name.upper())
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7899BB"))
    canvas.drawString(MARGIN, h - 16*mm, "TRAVEL & SAFARI SPECIALISTS")

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(GOLD)
    canvas.drawRightString(w - MARGIN, h - 11*mm, doc_label)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7899BB"))
    canvas.drawRightString(w - MARGIN, h - 16*mm, f"Page {doc.page}")

    canvas.setFillColor(LIGHT_GREY)
    canvas.rect(0, 0, w, 14*mm, fill=1, stroke=0)

    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(0, 14*mm, w, 14*mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_LIGHT)
    footer = f"{agency_name}  ·  {agent_email}  ·  Prepared {datetime.now().strftime('%d %B %Y')}"
    canvas.drawCentredString(w/2, 5.5*mm, footer)

    canvas.restoreState()


# ─── HELPER: Section divider ─────────────────────────────────────
def section_divider(styles, title):
    t = Table([[Paragraph(title, styles["section_title"])]],
        colWidths=[INNER_W])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,-1), 1.5, GOLD),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 2),
    ]))
    return t


# ─── HELPER: Info grid cell ──────────────────────────────────────
def info_cell(label, value, styles, col_w):
    return Table([
        [Paragraph(label, styles["label"])],
        [Paragraph(str(value) if value else "—", styles["value"])],
    ], colWidths=[col_w - 6])


# ══════════════════════════════════════════════════════════════════
# QUOTE PDF v2
# ══════════════════════════════════════════════════════════════════

def generate_quote_pdf(data):
    buffer  = io.BytesIO()
    styles  = S()
    agency  = data.get("agency_name", "SafariFlow")
    symbol  = data.get("currency_symbol", "$")
    ag_email = data.get("agent_email", "")
    unsplash_key = data.get("unsplash_access_key", "")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "SAFARI QUOTE")
    )
    doc.addPageTemplates([template])
    story = []

    # ── HERO IMAGE ───────────────────────────────────────────────
    hero_query = data.get("unsplash_hero_query", f"{data.get('destination', 'safari africa')} landscape")
    hero_img = fetch_unsplash_image(hero_query, INNER_W, 55*mm, unsplash_key)
    if hero_img:
        hero_img.hAlign = "LEFT"
        story.append(hero_img)
        story.append(Spacer(1, 3*mm))

    # ── HERO SECTION ─────────────────────────────────────────────
    client_name = data.get("client_name", "Valued Client")
    destination = data.get("destination", "")

    hero = Table([[
        Table([
            [Paragraph("Safari Proposal prepared for", styles["label"])],
            [Paragraph(client_name, styles["hero_name"])],
            [Spacer(1, 3)],
            [Paragraph(f"&#x2708;  {destination}", styles["hero_dest"])] if destination else [Spacer(1,1)],
        ], colWidths=[INNER_W * 0.62]),
        Table([
            [Paragraph("QUOTE NUMBER", styles["label"])],
            [Paragraph(data.get("quote_number", "—"), styles["value_gold"])],
            [Spacer(1, 6)],
            [Paragraph("VALID UNTIL", styles["label"])],
            [Paragraph(data.get("valid_until", "—"), styles["value"])],
            [Spacer(1, 6)],
            [Paragraph("PREPARED BY", styles["label"])],
            [Paragraph(data.get("agent_name", "—"), styles["value"])],
        ], colWidths=[INNER_W * 0.35]),
    ]], colWidths=[INNER_W * 0.65, INNER_W * 0.35])

    hero.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ("LINEBEFORE", (1,0), (1,0), 1, BORDER),
    ]))
    story.append(hero)
    story.append(Spacer(1, 5*mm))

    # ── META GRID ────────────────────────────────────────────────
    col_w = INNER_W / 4
    meta = [
        ("QUOTE DATE",    data.get("quote_date", "—")),
        ("TRAVEL DATES",  data.get("travel_dates", "—")),
        ("TRAVELERS",     str(data.get("num_travelers", "—"))),
        ("DURATION",      f"{data.get('duration_days', '—')} Days"),
    ]
    meta_cells = [info_cell(l, v, styles, col_w) for l, v in meta]
    meta_table = Table([meta_cells], colWidths=[col_w]*4)
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("LINEBELOW", (0,0), (-1,-1), 0.8, GOLD),
        ("LINEABOVE", (0,0), (-1,-1), 0.3, BORDER),
        ("LINEBEFORE", (1,0), (1,0), 0.5, BORDER),
        ("LINEBEFORE", (2,0), (2,0), 0.5, BORDER),
        ("LINEBEFORE", (3,0), (3,0), 0.5, BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6*mm))

    # ── CLIENT + AGENT INFO ──────────────────────────────────────
    half = INNER_W * 0.48
    client_block = Table([
        [Paragraph("CLIENT INFORMATION", styles["section_title"])],
        [Spacer(1, 4)],
        [Paragraph("Name", styles["label"])],
        [Paragraph(data.get("client_name", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Email", styles["label"])],
        [Paragraph(data.get("client_email", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Nationality", styles["label"])],
        [Paragraph(data.get("client_nationality", "—") or "—", styles["body"])],
    ], colWidths=[half])

    agent_block = Table([
        [Paragraph("YOUR TRAVEL SPECIALIST", styles["section_title"])],
        [Spacer(1, 4)],
        [Paragraph("Agent", styles["label"])],
        [Paragraph(data.get("agent_name", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Email", styles["label"])],
        [Paragraph(data.get("agent_email", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Agency", styles["label"])],
        [Paragraph(data.get("agency_name", "—"), styles["body"])],
    ], colWidths=[half])

    info_row = Table([[client_block, agent_block]], colWidths=[INNER_W*0.5, INNER_W*0.5])
    info_row.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBEFORE", (1,0), (1,0), 0.8, GOLD),
    ]))
    story.append(info_row)
    story.append(Spacer(1, 6*mm))

    # ── INTRODUCTION NARRATIVE ───────────────────────────────────
    intro = data.get("introduction", "")
    if intro:
        story.append(section_divider(styles, "YOUR SAFARI OVERVIEW"))
        story.append(Spacer(1, 3*mm))
        intro_box = Table([[Paragraph(intro, styles["narrative_intro"])]],
            colWidths=[INNER_W])
        intro_box.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 16),
            ("RIGHTPADDING", (0,0), (-1,-1), 16),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(intro_box)
        story.append(Spacer(1, 6*mm))

    # ── DAY BY DAY ITINERARY ─────────────────────────────────────
    days = data.get("days", [])
    if days:
        story.append(section_divider(styles, "YOUR DAY-BY-DAY ITINERARY"))
        story.append(Spacer(1, 3*mm))

        for day in days:
            day_num   = day.get("day_number", "")
            day_title = day.get("title", "")
            day_dest  = day.get("destination", "")
            narrative = day.get("narrative", "")
            highlight = day.get("highlight", "")
            accom     = day.get("accommodation_description", "")
            img_query = day.get("image_search_query", f"{day_dest} safari")

            # Day image
            day_img = fetch_unsplash_image(img_query, INNER_W, 40*mm, unsplash_key)

            # Day header
            day_hdr = Table([[
                Paragraph(f"DAY {day_num}", ParagraphStyle("dn",
                    fontSize=8, fontName="Helvetica-Bold",
                    textColor=GOLD, leading=12)),
                Paragraph(f"<b>{day_title}</b>", ParagraphStyle("dt",
                    fontSize=11, fontName="Helvetica-Bold",
                    textColor=WHITE, leading=15)),
                Paragraph(day_dest, ParagraphStyle("dd",
                    fontSize=8.5, fontName="Helvetica",
                    textColor=colors.HexColor("#9AABBF"),
                    leading=12, alignment=TA_RIGHT)),
            ]], colWidths=[INNER_W*0.1, INNER_W*0.63, INNER_W*0.27])
            day_hdr.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), NAVY),
                ("LEFTPADDING", (0,0), (-1,-1), 12),
                ("RIGHTPADDING", (0,0), (-1,-1), 12),
                ("TOPPADDING", (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LINEBELOW", (0,0), (-1,-1), 1.5, GOLD),
            ]))

            # Day content
            day_content = []
            if day_img:
                day_content.append(day_img)
                day_content.append(Spacer(1, 2*mm))

            if narrative:
                day_content.append(Paragraph(narrative, styles["day_narrative"]))
                day_content.append(Spacer(1, 2*mm))

            if highlight:
                day_content.append(Paragraph(f"&#x2728; {highlight}", styles["highlight"]))
                day_content.append(Spacer(1, 2*mm))

            if accom:
                day_content.append(Paragraph(f"<b>Accommodation:</b> {accom}",
                    styles["body_mid"]))

            content_table = Table([[day_content]], colWidths=[INNER_W])
            content_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), CREAM),
                ("LEFTPADDING", (0,0), (-1,-1), 14),
                ("RIGHTPADDING", (0,0), (-1,-1), 14),
                ("TOPPADDING", (0,0), (-1,-1), 10),
                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                ("LINEBELOW", (0,0), (-1,-1), 0.5, BORDER),
            ]))

            story.append(KeepTogether([day_hdr, content_table, Spacer(1, 3*mm)]))

        story.append(Spacer(1, 3*mm))

    # ── QUOTE BREAKDOWN ──────────────────────────────────────────
    story.append(section_divider(styles, "INVESTMENT BREAKDOWN"))
    story.append(Spacer(1, 2*mm))

    col_widths = [INNER_W*0.31, INNER_W*0.32, INNER_W*0.08, INNER_W*0.15, INNER_W*0.14]
    header_row = [
        Paragraph("DESCRIPTION", styles["label"]),
        Paragraph("DETAILS", styles["label"]),
        Paragraph("QTY", styles["label"]),
        Paragraph("UNIT PRICE", styles["label"]),
        Paragraph("TOTAL", styles["label"]),
    ]

    rows = [header_row]
    subtotal = 0

    for item in data.get("items", []):
        try:
            up   = float(item.get("unit_price", 0))
            qty  = float(item.get("quantity", 1))
            line = up * qty
            subtotal += line
        except:
            line = 0

        rows.append([
            Paragraph(item.get("description",""), styles["item_desc"]),
            Paragraph(item.get("details",""), styles["item_detail"]),
            Paragraph(str(item.get("quantity",1)), styles["body"]),
            Paragraph(fmt_currency(item.get("unit_price",0), symbol), styles["price"]),
            Paragraph(fmt_currency(line, symbol), styles["price_bold"]),
        ])

    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    row_colors  = [("BACKGROUND", (0,i), (-1,i), WHITE if i%2==1 else LIGHT_GREY)
                   for i in range(1, len(rows))]

    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), GOLD),
        ("LINEBELOW", (0,0), (-1,0), 1.5, GOLD),
        ("LEFTPADDING", (0,0), (-1,-1), 9),
        ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,1), (-1,-1), 0.3, BORDER),
        ("LINEBEFORE", (4,0), (4,-1), 0.5, BORDER),
    ] + row_colors))

    story.append(items_table)
    story.append(Spacer(1, 1*mm))

    # ── TOTAL BANNER ─────────────────────────────────────────────
    grand_total = subtotal - float(data.get("discount", 0))
    deposit_pct = float(data.get("deposit_percentage", 30))
    deposit_amt = grand_total * (deposit_pct / 100)
    balance_amt = grand_total - deposit_amt

    total_banner = Table([[
        Paragraph("TOTAL INVESTMENT", styles["total_label"]),
        Paragraph(fmt_currency(grand_total, symbol), styles["total_amount"]),
    ]], colWidths=[INNER_W*0.55, INNER_W*0.45])
    total_banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEABOVE", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(total_banner)
    story.append(Spacer(1, 2*mm))

    # Deposit breakdown
    deposit_row = Table([[
        Table([
            [Paragraph("DEPOSIT REQUIRED", styles["label"])],
            [Paragraph(f"{fmt_currency(deposit_amt, symbol)}  ({int(deposit_pct)}%)", styles["value_gold"])],
        ], colWidths=[INNER_W*0.48]),
        Table([
            [Paragraph("BALANCE DUE", styles["label"])],
            [Paragraph(fmt_currency(balance_amt, symbol), styles["value"])],
        ], colWidths=[INNER_W*0.48]),
    ]], colWidths=[INNER_W*0.5, INNER_W*0.5])
    deposit_row.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LINEBEFORE", (1,0), (1,-1), 0.8, GOLD),
        ("LINEBELOW", (0,-1), (-1,-1), 1, GOLD),
    ]))
    story.append(deposit_row)
    story.append(Spacer(1, 6*mm))

    # ── INCLUSIONS / EXCLUSIONS ──────────────────────────────────
    notes_raw = data.get("notes", "")
    inc_text  = ""
    exc_text  = ""
    base_note = notes_raw

    if "Package includes:" in notes_raw:
        parts = notes_raw.split("Package includes:")
        base_note = parts[0].strip()
        rest = parts[1]
        if "Not included:" in rest:
            inc_text, exc_text = rest.split("Not included:")
        else:
            inc_text = rest

    if inc_text or exc_text:
        inc_items = [i.strip() for i in inc_text.split(",") if i.strip()]
        exc_items = [i.strip() for i in exc_text.split(",") if i.strip()]

        inc_content = [Paragraph("INCLUDED IN THIS PACKAGE", styles["inc_title"]), Spacer(1, 5)]
        for it in inc_items:
            inc_content.append(Paragraph(f"<b>&#x2713;</b>  {it}", styles["inc_item"]))
            inc_content.append(Spacer(1, 2))

        exc_content = [Paragraph("NOT INCLUDED", styles["exc_title"]), Spacer(1, 5)]
        for it in exc_items:
            exc_content.append(Paragraph(f"<b>&#x2715;</b>  {it}", styles["inc_item"]))
            exc_content.append(Spacer(1, 2))

        ie_table = Table([[inc_content, exc_content]], colWidths=[INNER_W/2, INNER_W/2])
        ie_table.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F0FAF3")),
            ("BACKGROUND", (1,0), (1,-1), colors.HexColor("#FEF5F5")),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LINEBEFORE", (1,0), (1,-1), 1, BORDER),
            ("LINEBELOW", (0,-1), (-1,-1), 0.5, BORDER),
        ]))
        story.append(ie_table)
        story.append(Spacer(1, 5*mm))

    # ── NOTES ────────────────────────────────────────────────────
    if base_note:
        story.append(section_divider(styles, "NOTES & CONDITIONS"))
        story.append(Spacer(1, 2*mm))
        notes_table = Table([[Paragraph(base_note, styles["note"])]], colWidths=[INNER_W])
        notes_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
            ("LINEBELOW", (0,0), (-1,-1), 1, GOLD),
        ]))
        story.append(notes_table)
        story.append(Spacer(1, 5*mm))

    # ── ACTION BUTTONS (Accept / Change / Reject) ────────────────
    accept_url  = data.get("accept_url", "")
    changes_url = data.get("changes_url", "")

    if accept_url or changes_url:
        story.append(section_divider(styles, "RESPOND TO THIS QUOTE"))
        story.append(Spacer(1, 3*mm))

        btn_cells = []
        if accept_url:
            btn_cells.append(Table([[
                Paragraph("&#x2705; ACCEPT THIS QUOTE",
                    ParagraphStyle("btn_accept", fontSize=10,
                    fontName="Helvetica-Bold", textColor=WHITE,
                    leading=14, alignment=TA_CENTER)),
                Paragraph(accept_url,
                    ParagraphStyle("btn_url", fontSize=7,
                    fontName="Helvetica", textColor=GOLD_LIGHT,
                    leading=10, alignment=TA_CENTER)),
            ]], colWidths=[INNER_W*0.46]))

        if changes_url:
            btn_cells.append(Table([[
                Paragraph("&#x270F; REQUEST CHANGES",
                    ParagraphStyle("btn_change", fontSize=10,
                    fontName="Helvetica-Bold", textColor=WHITE,
                    leading=14, alignment=TA_CENTER)),
                Paragraph(changes_url,
                    ParagraphStyle("btn_url2", fontSize=7,
                    fontName="Helvetica", textColor=GOLD_LIGHT,
                    leading=10, alignment=TA_CENTER)),
            ]], colWidths=[INNER_W*0.46]))

        if btn_cells:
            btn_table = Table([btn_cells],
                colWidths=[INNER_W*0.5] * len(btn_cells))
            btn_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (0,-1), GREEN),
                ("BACKGROUND", (1,0), (1,-1), NAVY_MID) if len(btn_cells) > 1 else ("BACKGROUND", (0,0), (-1,-1), GREEN),
                ("LEFTPADDING", (0,0), (-1,-1), 16),
                ("RIGHTPADDING", (0,0), (-1,-1), 16),
                ("TOPPADDING", (0,0), (-1,-1), 12),
                ("BOTTOMPADDING", (0,0), (-1,-1), 12),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LINEBEFORE", (1,0), (1,-1), 1, WHITE) if len(btn_cells) > 1 else ("LINEABOVE", (0,0), (-1,-1), 0, WHITE),
            ]))
            story.append(btn_table)
            story.append(Spacer(1, 6*mm))

    # ══════════════════════════════════════════════════════════════
    # AGENCY TRUST PAGE (new last page)
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())

    profile  = data.get("agent_profile", {})
    reviews  = data.get("agent_reviews", [])

    # Agency header
    agency_hdr = Table([[
        Paragraph(agency.upper(), ParagraphStyle("ap_name",
            fontSize=18, fontName="Helvetica-Bold",
            textColor=WHITE, leading=24)),
        Paragraph("TRAVEL & SAFARI SPECIALISTS", ParagraphStyle("ap_tag",
            fontSize=9, fontName="Helvetica",
            textColor=GOLD, leading=13, alignment=TA_RIGHT)),
    ]], colWidths=[INNER_W*0.65, INNER_W*0.35])
    agency_hdr.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(agency_hdr)
    story.append(Spacer(1, 4*mm))

    # Bio
    bio = profile.get("bio", "")
    if bio:
        bio_table = Table([[Paragraph(bio, styles["bio"])]], colWidths=[INNER_W])
        bio_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CREAM),
            ("LEFTPADDING", (0,0), (-1,-1), 16),
            ("RIGHTPADDING", (0,0), (-1,-1), 16),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(bio_table)
        story.append(Spacer(1, 4*mm))

    # Stats strip
    yrs  = str(profile.get("years_experience", ""))
    saf  = str(profile.get("safaris_completed", ""))
    ctr  = str(profile.get("countries_covered", ""))

    if yrs or saf or ctr:
        stat_cells = []
        for icon, num, lbl in [("&#x1F3C6;", f"{yrs} Years", "Experience"),
                                ("&#x1F43E;", f"{saf}+", "Safaris Planned"),
                                ("&#x1F30D;", f"{ctr}", "Countries Covered")]:
            stat_cells.append(Table([
                [Paragraph(icon, ParagraphStyle("si", fontSize=18,
                    fontName="Helvetica", leading=24, alignment=TA_CENTER))],
                [Paragraph(num, ParagraphStyle("sn", fontSize=12,
                    fontName="Helvetica-Bold", textColor=NAVY,
                    leading=16, alignment=TA_CENTER))],
                [Paragraph(lbl, ParagraphStyle("sl", fontSize=8,
                    fontName="Helvetica", textColor=TEXT_LIGHT,
                    leading=11, alignment=TA_CENTER))],
            ], colWidths=[INNER_W/3 - 8]))

        stats_table = Table([stat_cells], colWidths=[INNER_W/3]*3)
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), WHITE),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LINEBEFORE", (1,0), (1,-1), 0.5, BORDER),
            ("LINEBEFORE", (2,0), (2,-1), 0.5, BORDER),
            ("LINEBELOW", (0,-1), (-1,-1), 1, GOLD),
            ("LINEABOVE", (0,0), (-1,0), 0.5, BORDER),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 4*mm))

    # Awards & Memberships
    awards      = profile.get("awards", [])
    memberships = profile.get("memberships", [])

    if awards or memberships:
        aw_content = []
        if awards:
            aw_content.append(Paragraph("AWARDS & RECOGNITION", styles["inc_title"]))
            aw_content.append(Spacer(1, 4))
            for a in awards:
                aw_content.append(Paragraph(f"&#x1F3C6;  {a}", styles["award_item"]))
                aw_content.append(Spacer(1, 3))

        mb_content = []
        if memberships:
            mb_content.append(Paragraph("MEMBERSHIPS & ACCREDITATIONS", styles["inc_title"]))
            mb_content.append(Spacer(1, 4))
            for m in memberships:
                mb_content.append(Paragraph(f"&#x2713;  {m}", styles["award_item"]))
                mb_content.append(Spacer(1, 3))

        if aw_content and mb_content:
            aw_table = Table([[aw_content, mb_content]],
                colWidths=[INNER_W*0.5, INNER_W*0.5])
        elif aw_content:
            aw_table = Table([[aw_content]], colWidths=[INNER_W])
        else:
            aw_table = Table([[mb_content]], colWidths=[INNER_W])

        aw_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CREAM),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LINEBEFORE", (1,0), (1,-1), 0.5, BORDER) if (aw_content and mb_content) else ("LINEABOVE", (0,0), (-1,-1), 0, WHITE),
            ("LINEBELOW", (0,-1), (-1,-1), 1, GOLD),
        ]))
        story.append(aw_table)
        story.append(Spacer(1, 4*mm))

    # Client Reviews
    if reviews:
        story.append(section_divider(styles, "WHAT OUR CLIENTS SAY"))
        story.append(Spacer(1, 3*mm))

        review_cells = []
        for rev in reviews[:3]:  # max 3 reviews
            rating_stars = stars(rev.get("rating", 5))
            cell_content = [
                Paragraph(rating_stars, ParagraphStyle("stars",
                    fontSize=12, fontName="Helvetica",
                    textColor=GOLD, leading=16)),
                Spacer(1, 4),
                Paragraph(f'"{rev.get("review_text","")}"', styles["review_text"]),
                Spacer(1, 6),
                Paragraph(f'— {rev.get("reviewer_name","")}',
                    styles["reviewer"]),
                Paragraph(f'{rev.get("reviewer_nationality","")} · {rev.get("trip_destination","")}',
                    styles["body_small"]),
            ]
            review_cells.append(cell_content)

        if len(review_cells) == 3:
            rev_table = Table([review_cells],
                colWidths=[INNER_W/3]*3)
        elif len(review_cells) == 2:
            rev_table = Table([review_cells],
                colWidths=[INNER_W/2]*2)
        else:
            rev_table = Table([review_cells], colWidths=[INNER_W])

        rev_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), WHITE),
            ("LEFTPADDING", (0,0), (-1,-1), 12),
            ("RIGHTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 14),
            ("BOTTOMPADDING", (0,0), (-1,-1), 14),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LINEBEFORE", (1,0), (1,-1), 0.5, BORDER),
            ("LINEBEFORE", (2,0), (2,-1), 0.5, BORDER) if len(review_cells) == 3 else ("LINEABOVE", (0,0), (-1,-1), 0, WHITE),
            ("LINEABOVE", (0,0), (-1,0), 0.5, BORDER),
            ("LINEBELOW", (0,-1), (-1,-1), 1, GOLD),
        ]))
        story.append(rev_table)
        story.append(Spacer(1, 4*mm))

    # Contact & Social
    story.append(section_divider(styles, "GET IN TOUCH"))
    story.append(Spacer(1, 3*mm))

    contact_items = []
    if ag_email:
        contact_items.append(f"&#x2709;  {ag_email}")
    if profile.get("whatsapp"):
        contact_items.append(f"&#x1F4F1;  {profile.get('whatsapp')}")
    if profile.get("website_url"):
        contact_items.append(f"&#x1F310;  {profile.get('website_url')}")
    if profile.get("office_location"):
        contact_items.append(f"&#x1F4CD;  {profile.get('office_location')}")

    social_items = []
    socials = [
        ("Facebook", profile.get("facebook_url","")),
        ("Instagram", profile.get("instagram_url","")),
        ("LinkedIn", profile.get("linkedin_url","")),
        ("TikTok", profile.get("tiktok_url","")),
        ("TripAdvisor", profile.get("tripadvisor_url","")),
    ]
    for name, url in socials:
        if url:
            social_items.append(f"{name}: {url}")

    contact_left = [Paragraph(c, styles["body"]) for c in contact_items]
    contact_right = [Paragraph(s, styles["social"]) for s in social_items]

    if contact_left or contact_right:
        contact_table = Table([[contact_left, contact_right]],
            colWidths=[INNER_W*0.5, INNER_W*0.5])
        contact_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), NAVY),
            ("LEFTPADDING", (0,0), (-1,-1), 16),
            ("RIGHTPADDING", (0,0), (-1,-1), 16),
            ("TOPPADDING", (0,0), (-1,-1), 14),
            ("BOTTOMPADDING", (0,0), (-1,-1), 14),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LINEBEFORE", (1,0), (1,-1), 0.5, colors.HexColor("#2A4A6A")),
        ]))
        story.append(contact_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════
# RECEIPT PDF
# ══════════════════════════════════════════════════════════════════

def generate_receipt_pdf(data):
    buffer   = io.BytesIO()
    styles   = S()
    agency   = data.get("agency_name", "SafariFlow")
    ag_email = data.get("agent_email", "")
    symbol   = data.get("currency_symbol", "$")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "PAYMENT RECEIPT")
    )
    doc.addPageTemplates([template])
    story = []

    # Receipt header
    rcpt_hdr = Table([[
        Table([
            [Paragraph("PAYMENT RECEIPT", styles["label"])],
            [Paragraph(data.get("receipt_number", "—"), styles["value_gold"])],
            [Spacer(1, 6)],
            [Paragraph("BOOKING REFERENCE", styles["label"])],
            [Paragraph(data.get("booking_number", "—"), styles["value"])],
        ], colWidths=[INNER_W*0.6]),
        Table([
            [Paragraph("RECEIPT DATE", styles["label"])],
            [Paragraph(data.get("receipt_date", datetime.now().strftime("%d %B %Y")), styles["value"])],
            [Spacer(1, 6)],
            [Paragraph("STATUS", styles["label"])],
            [Paragraph("PAID", ParagraphStyle("paid",
                fontSize=12, fontName="Helvetica-Bold",
                textColor=GREEN, leading=16))],
        ], colWidths=[INNER_W*0.35]),
    ]], colWidths=[INNER_W*0.65, INNER_W*0.35])

    rcpt_hdr.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ("LINEBEFORE", (1,0), (1,0), 1, BORDER),
    ]))
    story.append(rcpt_hdr)
    story.append(Spacer(1, 5*mm))

    # Client info
    col_w = INNER_W / 4
    meta = [
        ("CLIENT NAME",    data.get("client_name", "—")),
        ("CLIENT EMAIL",   data.get("client_email", "—")),
        ("DESTINATION",    data.get("destination", "—")),
        ("TRAVEL DATES",   data.get("travel_dates", "—")),
    ]
    meta_cells = [info_cell(l, v, styles, col_w) for l, v in meta]
    meta_table = Table([meta_cells], colWidths=[col_w]*4)
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("LINEBELOW", (0,0), (-1,-1), 0.8, GOLD),
        ("LINEABOVE", (0,0), (-1,-1), 0.3, BORDER),
        ("LINEBEFORE", (1,0), (1,0), 0.5, BORDER),
        ("LINEBEFORE", (2,0), (2,0), 0.5, BORDER),
        ("LINEBEFORE", (3,0), (3,0), 0.5, BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6*mm))

    # Amount paid banner
    amount_paid = data.get("amount_paid_usd", 0)
    paid_banner = Table([[
        Paragraph("AMOUNT RECEIVED", styles["total_label"]),
        Paragraph(fmt_currency(amount_paid, symbol), styles["receipt_amount"]),
    ]], colWidths=[INNER_W*0.5, INNER_W*0.5])
    paid_banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEABOVE", (0,0), (-1,-1), 2, GOLD),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(paid_banner)
    story.append(Spacer(1, 4*mm))

    # Payment breakdown
    total       = float(data.get("total_trip_cost_usd", 0))
    paid        = float(data.get("amount_paid_usd", 0))
    balance     = total - paid
    due_date    = data.get("balance_due_date", "—")
    payment_ref = data.get("payment_reference", "—")
    method      = data.get("payment_method", "Bank Transfer")

    breakdown_rows = [
        [Paragraph("DESCRIPTION", styles["label"]),
         Paragraph("AMOUNT", ParagraphStyle("al", fontSize=7,
             fontName="Helvetica-Bold", textColor=TEXT_LIGHT,
             leading=11, letterSpacing=1.2, alignment=TA_RIGHT))],
        [Paragraph("Total Trip Cost", styles["body"]),
         Paragraph(fmt_currency(total, symbol), styles["price"])],
        [Paragraph(f"Amount Paid ({data.get('payment_type','Deposit')})", styles["body"]),
         Paragraph(fmt_currency(paid, symbol),
             ParagraphStyle("pp", fontSize=9.5, fontName="Helvetica-Bold",
             textColor=GREEN, leading=13, alignment=TA_RIGHT))],
        [Paragraph("Outstanding Balance", styles["body"]),
         Paragraph(fmt_currency(balance, symbol), styles["price_bold"])],
        [Paragraph(f"Balance Due Date: {due_date}", styles["body_mid"]),
         Paragraph("", styles["price"])],
    ]

    bdown_table = Table(breakdown_rows,
        colWidths=[INNER_W*0.7, INNER_W*0.3])
    bdown_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), GOLD),
        ("LINEBELOW", (0,0), (-1,0), 1.5, GOLD),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBELOW", (0,1), (-1,-1), 0.3, BORDER),
        ("BACKGROUND", (0,3), (-1,3), GOLD_BG),
        ("BACKGROUND", (0,4), (-1,4), LIGHT_GREY),
    ]))
    story.append(bdown_table)
    story.append(Spacer(1, 4*mm))

    # Payment details
    pay_detail_rows = [
        ("PAYMENT METHOD", method),
        ("PAYMENT REFERENCE", payment_ref),
        ("RECEIVED BY", agency),
        ("DATE RECEIVED", data.get("receipt_date", datetime.now().strftime("%d %B %Y"))),
    ]
    pd_cells = [info_cell(l, v, styles, INNER_W/4) for l, v in pay_detail_rows]
    pd_table = Table([pd_cells], colWidths=[INNER_W/4]*4)
    pd_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
        ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
        ("LINEBEFORE", (3,0),(3,-1), 0.5, BORDER),
        ("LINEABOVE", (0,0),(-1,0), 0.5, BORDER),
        ("LINEBELOW", (0,-1),(-1,-1), 1, GOLD),
    ]))
    story.append(pd_table)
    story.append(Spacer(1, 6*mm))

    # Reminder note
    if balance > 0:
        reminder = Table([[
            Paragraph(
                f"&#x26A0;  Please note: An outstanding balance of "
                f"<b>{fmt_currency(balance, symbol)}</b> is due by "
                f"<b>{due_date}</b>. Payment instructions will be sent separately.",
                styles["note"])
        ]], colWidths=[INNER_W])
        reminder.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(reminder)
        story.append(Spacer(1, 5*mm))

    # Thank you footer
    thanks = Table([[
        Paragraph(f"Thank you for booking with {agency}!",
            ParagraphStyle("ty", fontSize=12, fontName="Helvetica-Bold",
            textColor=WHITE, leading=16, alignment=TA_CENTER)),
        Paragraph("This is an official receipt. Please retain for your records.",
            ParagraphStyle("tr", fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#AABBCC"), leading=12,
            alignment=TA_CENTER)),
    ]], colWidths=[INNER_W])
    thanks.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("LINEABOVE", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(thanks)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════
# ACCOMMODATION VOUCHER PDF
# ══════════════════════════════════════════════════════════════════

def generate_accommodation_voucher(data):
    buffer   = io.BytesIO()
    styles   = S()
    agency   = data.get("agency_name", "SafariFlow")
    ag_email = data.get("agent_email", "")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "ACCOMMODATION VOUCHER")
    )
    doc.addPageTemplates([template])
    story = []

    # Voucher header
    vchr_hdr = Table([[
        Paragraph("&#x1F3E8; ACCOMMODATION VOUCHER",
            ParagraphStyle("vh", fontSize=16, fontName="Helvetica-Bold",
            textColor=WHITE, leading=22)),
        Table([
            [Paragraph("VOUCHER NUMBER", styles["label"])],
            [Paragraph(data.get("voucher_number", "—"), styles["value_gold"])],
        ], colWidths=[INNER_W*0.35]),
    ]], colWidths=[INNER_W*0.65, INNER_W*0.35])
    vchr_hdr.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ("LINEBEFORE", (1,0), (1,0), 1, colors.HexColor("#2A4A6A")),
    ]))
    story.append(vchr_hdr)
    story.append(Spacer(1, 5*mm))

    # Property details
    story.append(section_divider(styles, "PROPERTY DETAILS"))
    story.append(Spacer(1, 3*mm))

    prop_rows = [
        ("PROPERTY NAME",    data.get("property_name", "—")),
        ("DESTINATION",      data.get("destination", "—")),
        ("COUNTRY",          data.get("country", "—")),
        ("ROOM TYPE",        data.get("room_type", "—")),
        ("MEAL PLAN",        data.get("meal_plan", "—")),
        ("CHECK-IN DATE",    data.get("check_in_date", "—")),
        ("CHECK-OUT DATE",   data.get("check_out_date", "—")),
        ("NUMBER OF NIGHTS", str(data.get("nights", "—"))),
    ]

    prop_cells_1 = [info_cell(l, v, styles, INNER_W/2)
                    for l, v in prop_rows[:4]]
    prop_cells_2 = [info_cell(l, v, styles, INNER_W/2)
                    for l, v in prop_rows[4:]]

    for cells in [prop_cells_1, prop_cells_2]:
        t = Table([cells], colWidths=[INNER_W/4]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CREAM),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
            ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
            ("LINEBEFORE", (3,0),(3,-1), 0.5, BORDER),
            ("LINEBELOW", (0,-1),(-1,-1), 0.5, BORDER),
        ]))
        story.append(t)
    story.append(Spacer(1, 4*mm))

    # Guest names
    guests = data.get("guest_names", [])
    if guests:
        story.append(section_divider(styles, "GUESTS"))
        story.append(Spacer(1, 3*mm))
        guest_rows = [[
            Paragraph(str(i+1), styles["label"]),
            Paragraph(g, styles["body"]),
        ] for i, g in enumerate(guests)]
        guest_table = Table(guest_rows, colWidths=[INNER_W*0.1, INNER_W*0.9])
        guest_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), WHITE),
            ("LEFTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
            ("LINEABOVE", (0,0), (-1,0), 0.5, BORDER),
        ]))
        story.append(guest_table)
        story.append(Spacer(1, 4*mm))

    # Supplier contact
    story.append(section_divider(styles, "PROPERTY CONTACT"))
    story.append(Spacer(1, 3*mm))

    sup_col = INNER_W / 3
    sup_cells = [
        info_cell("PROPERTY EMAIL", data.get("supplier_email", "—"), styles, sup_col),
        info_cell("PROPERTY PHONE", data.get("supplier_phone", "—"), styles, sup_col),
        info_cell("BOOKING REF", data.get("booking_number", "—"), styles, sup_col),
    ]
    sup_table = Table([sup_cells], colWidths=[sup_col]*3)
    sup_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
        ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
        ("LINEBELOW", (0,-1),(-1,-1), 1, GOLD),
    ]))
    story.append(sup_table)
    story.append(Spacer(1, 4*mm))

    # Special notes
    notes = data.get("special_notes", "")
    if notes:
        notes_t = Table([[Paragraph(notes, styles["note"])]], colWidths=[INNER_W])
        notes_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(notes_t)
        story.append(Spacer(1, 4*mm))

    # Agent footer
    agent_footer = Table([[
        Paragraph(f"Issued by: {agency}  ·  {ag_email}",
            ParagraphStyle("af", fontSize=9, fontName="Helvetica-Bold",
            textColor=WHITE, leading=13, alignment=TA_CENTER)),
        Paragraph(f"This voucher is valid for the dates specified above. "
            f"Present this voucher at check-in.",
            ParagraphStyle("av", fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#AABBCC"), leading=12,
            alignment=TA_CENTER)),
    ]], colWidths=[INNER_W])
    agent_footer.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LINEABOVE", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(agent_footer)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════
# TRANSPORT VOUCHER PDF
# ══════════════════════════════════════════════════════════════════

def generate_transport_voucher(data):
    buffer   = io.BytesIO()
    styles   = S()
    agency   = data.get("agency_name", "SafariFlow")
    ag_email = data.get("agent_email", "")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "TRANSPORT VOUCHER")
    )
    doc.addPageTemplates([template])
    story = []

    # Header
    transport_type = data.get("transport_type", "transfer").upper()
    icon = "&#x2708;" if data.get("transport_type") == "fly" else \
           "&#x1F6A2;" if data.get("transport_type") == "boat" else "&#x1F697;"

    vchr_hdr = Table([[
        Paragraph(f"{icon} TRANSPORT VOUCHER — {transport_type}",
            ParagraphStyle("th", fontSize=16, fontName="Helvetica-Bold",
            textColor=WHITE, leading=22)),
        Table([
            [Paragraph("VOUCHER NUMBER", styles["label"])],
            [Paragraph(data.get("voucher_number", "—"), styles["value_gold"])],
        ], colWidths=[INNER_W*0.35]),
    ]], colWidths=[INNER_W*0.65, INNER_W*0.35])
    vchr_hdr.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ("LINEBEFORE", (1,0), (1,0), 1, colors.HexColor("#2A4A6A")),
    ]))
    story.append(vchr_hdr)
    story.append(Spacer(1, 5*mm))

    # Route highlight
    route_banner = Table([[
        Paragraph(data.get("from_location", "—"),
            ParagraphStyle("rl", fontSize=14, fontName="Helvetica-Bold",
            textColor=GOLD, leading=18, alignment=TA_CENTER)),
        Paragraph("&#x27A1;",
            ParagraphStyle("ra", fontSize=18, fontName="Helvetica",
            textColor=WHITE, leading=24, alignment=TA_CENTER)),
        Paragraph(data.get("to_location", "—"),
            ParagraphStyle("rr", fontSize=14, fontName="Helvetica-Bold",
            textColor=GOLD, leading=18, alignment=TA_CENTER)),
    ]], colWidths=[INNER_W*0.42, INNER_W*0.16, INNER_W*0.42])
    route_banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY_MID),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-1), 1, GOLD),
    ]))
    story.append(route_banner)
    story.append(Spacer(1, 4*mm))

    # Transfer details
    story.append(section_divider(styles, "TRANSFER DETAILS"))
    story.append(Spacer(1, 3*mm))

    transfer_rows = [
        ("OPERATOR",        data.get("operator_name", "—")),
        ("VEHICLE TYPE",    data.get("vehicle_type", "—")),
        ("PICKUP DATE",     data.get("pickup_date", "—")),
        ("PICKUP TIME",     data.get("pickup_time", "—")),
        ("PICKUP POINT",    data.get("pickup_point", "—")),
        ("DROP-OFF POINT",  data.get("dropoff_point", "—")),
        ("DURATION",        data.get("duration", "—")),
        ("BOOKING REF",     data.get("booking_number", "—")),
    ]

    tr_cells_1 = [info_cell(l, v, styles, INNER_W/4)
                  for l, v in transfer_rows[:4]]
    tr_cells_2 = [info_cell(l, v, styles, INNER_W/4)
                  for l, v in transfer_rows[4:]]

    for cells in [tr_cells_1, tr_cells_2]:
        t = Table([cells], colWidths=[INNER_W/4]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CREAM),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
            ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
            ("LINEBEFORE", (3,0),(3,-1), 0.5, BORDER),
            ("LINEBELOW", (0,-1),(-1,-1), 0.5, BORDER),
        ]))
        story.append(t)
    story.append(Spacer(1, 4*mm))

    # Passengers
    passengers = data.get("passenger_names", [])
    if passengers:
        story.append(section_divider(styles, "PASSENGERS"))
        story.append(Spacer(1, 3*mm))
        pax_rows = [[
            Paragraph(str(i+1), styles["label"]),
            Paragraph(p, styles["body"]),
        ] for i, p in enumerate(passengers)]
        pax_table = Table(pax_rows, colWidths=[INNER_W*0.1, INNER_W*0.9])
        pax_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), WHITE),
            ("LEFTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
            ("LINEABOVE", (0,0), (-1,0), 0.5, BORDER),
        ]))
        story.append(pax_table)
        story.append(Spacer(1, 4*mm))

    # Operator contact
    story.append(section_divider(styles, "OPERATOR CONTACT"))
    story.append(Spacer(1, 3*mm))

    op_col = INNER_W / 3
    op_cells = [
        info_cell("OPERATOR EMAIL", data.get("operator_email", "—"), styles, op_col),
        info_cell("OPERATOR PHONE", data.get("operator_phone", "—"), styles, op_col),
        info_cell("CONFIRMATION REF", data.get("operator_ref", "—"), styles, op_col),
    ]
    op_table = Table([op_cells], colWidths=[op_col]*3)
    op_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
        ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
        ("LINEBELOW", (0,-1),(-1,-1), 1, GOLD),
    ]))
    story.append(op_table)
    story.append(Spacer(1, 4*mm))

    # Notes
    notes = data.get("special_notes", "")
    if notes:
        notes_t = Table([[Paragraph(notes, styles["note"])]], colWidths=[INNER_W])
        notes_t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(notes_t)
        story.append(Spacer(1, 4*mm))

    # Footer
    agent_footer = Table([[
        Paragraph(f"Issued by: {agency}  ·  {ag_email}",
            ParagraphStyle("af2", fontSize=9, fontName="Helvetica-Bold",
            textColor=WHITE, leading=13, alignment=TA_CENTER)),
        Paragraph("Present this voucher to your driver/pilot at the time of transfer.",
            ParagraphStyle("av2", fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#AABBCC"), leading=12,
            alignment=TA_CENTER)),
    ]], colWidths=[INNER_W])
    agent_footer.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LINEABOVE", (0,0), (-1,-1), 2, GOLD),
    ]))
    story.append(agent_footer)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── Keep original itinerary PDF for backwards compatibility ──────
def generate_itinerary_pdf(data):
    """Original itinerary PDF — maintained for backwards compatibility"""
    buffer   = io.BytesIO()
    styles   = S()
    agency   = data.get("agency_name", "SafariFlow")
    ag_email = data.get("agent_email", "")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "TRAVEL ITINERARY")
    )
    doc.addPageTemplates([template])
    story = []

    hero_data = [[
        Paragraph(data.get("destination","Your Journey"), styles["hero_name"]),
        Table([
            [Paragraph("ITINERARY REF", styles["label"])],
            [Paragraph(data.get("itinerary_number","—"), styles["value_gold"])],
            [Spacer(1, 4)],
            [Paragraph("TRAVEL DATES", styles["label"])],
            [Paragraph(data.get("travel_dates","—"), styles["value"])],
        ], colWidths=[INNER_W*0.35])
    ]]
    hero = Table(hero_data, colWidths=[INNER_W*0.65, INNER_W*0.35])
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ("LINEBEFORE", (1,0), (1,-1), 1, BORDER),
    ]))
    story.append(hero)
    story.append(Spacer(1, 6*mm))

    summary = [
        ("CLIENT", data.get("client_name","—")),
        ("TRAVELERS", str(data.get("num_travelers","—"))),
        ("DAYS", str(len(data.get("days",[])))),
        ("AGENT", data.get("agent_name","—")),
    ]
    col_w = INNER_W / 4
    sum_cells = [info_cell(l, v, styles, col_w) for l, v in summary]
    sum_table = Table([sum_cells], colWidths=[col_w]*4)
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBELOW", (0,-1), (-1,-1), 1, GOLD),
        ("LINEBEFORE", (1,0),(1,-1), 0.5, BORDER),
        ("LINEBEFORE", (2,0),(2,-1), 0.5, BORDER),
        ("LINEBEFORE", (3,0),(3,-1), 0.5, BORDER),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("YOUR DAY-BY-DAY ITINERARY", styles["section_title"]))
    story.append(Spacer(1, 3*mm))

    for day in data.get("days", []):
        day_num   = day.get("day_number","")
        day_date  = day.get("date","")
        day_title = day.get("title","")

        day_hdr = Table([[
            Paragraph(f"DAY {day_num}", ParagraphStyle("dn", fontSize=8,
                fontName="Helvetica-Bold", textColor=GOLD, leading=12)),
            Paragraph(f"<b>{day_title}</b>", ParagraphStyle("dt", fontSize=11,
                fontName="Helvetica-Bold", textColor=WHITE, leading=15)),
            Paragraph(day_date, ParagraphStyle("dd", fontSize=8.5,
                fontName="Helvetica", textColor=colors.HexColor("#9AABBF"),
                leading=12, alignment=TA_RIGHT)),
        ]], colWidths=[INNER_W*0.1, INNER_W*0.63, INNER_W*0.27])
        day_hdr.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), NAVY),
            ("LEFTPADDING", (0,0), (-1,-1), 12),
            ("RIGHTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LINEBELOW", (0,0), (-1,-1), 1.5, GOLD),
        ]))

        act_rows = []
        for i, act in enumerate(day.get("activities", [])):
            bg = WHITE if i % 2 == 0 else LIGHT_GREY
            act_row = Table([[
                Paragraph(act.get("time",""), ParagraphStyle("at", fontSize=8,
                    fontName="Helvetica-Bold", textColor=GOLD, leading=11)),
                Table([
                    [Paragraph(act.get("title",""), ParagraphStyle("atl", fontSize=10,
                        fontName="Helvetica-Bold", textColor=NAVY, leading=13))],
                    [Paragraph(act.get("description",""), styles["body_mid"])],
                ], colWidths=[INNER_W*0.88 - 8]),
            ]], colWidths=[INNER_W*0.12, INNER_W*0.88])
            act_row.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), bg),
                ("LEFTPADDING", (0,0), (-1,-1), 10),
                ("RIGHTPADDING", (0,0), (-1,-1), 10),
                ("TOPPADDING", (0,0), (-1,-1), 7),
                ("BOTTOMPADDING", (0,0), (-1,-1), 7),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
            ]))
            act_rows.append(act_row)

        story.append(KeepTogether([day_hdr] + act_rows + [Spacer(1, 4*mm)]))

    doc.build(story)
    buffer.seek(0)
    return buffer
