import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)

# ─── Brand Colors ─────────────────────────────────────────────────
NAVY        = colors.HexColor("#0D1E35")   # deep navy
NAVY_MID    = colors.HexColor("#1A2E4A")   # mid navy
GOLD        = colors.HexColor("#C8A96E")   # warm gold
GOLD_LIGHT  = colors.HexColor("#E8C98E")   # light gold
GOLD_BG     = colors.HexColor("#FBF6EE")   # gold tint background
SAGE        = colors.HexColor("#4A7C59")   # safari green
CREAM       = colors.HexColor("#FAFAF8")   # off white
LIGHT_GREY  = colors.HexColor("#F4F4F2")   # light grey
BORDER      = colors.HexColor("#E0DDD8")   # subtle border
WHITE       = colors.white
TEXT_DARK   = colors.HexColor("#1A1A1A")
TEXT_MID    = colors.HexColor("#555550")
TEXT_LIGHT  = colors.HexColor("#999990")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
INNER_W = PAGE_W - 2 * MARGIN


# ─── Styles ───────────────────────────────────────────────────────
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
    }


def fmt_currency(amount, symbol="$"):
    try:
        return f"{symbol} {float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol} 0.00"


# ─── Page Canvas (header + footer) ────────────────────────────────
def draw_page(canvas, doc, agency_name, agent_email, doc_label):
    canvas.saveState()
    w, h = A4

    # ── Top header band ──
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 20*mm, w, 20*mm, fill=1, stroke=0)

    # Gold accent stripe
    canvas.setFillColor(GOLD)
    canvas.rect(0, h - 21.5*mm, w, 1.5*mm, fill=1, stroke=0)

    # Left: Agency name + tagline
    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(WHITE)
    canvas.drawString(MARGIN, h - 11*mm, agency_name.upper())
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7899BB"))
    canvas.drawString(MARGIN, h - 16*mm, "TRAVEL & SAFARI SPECIALISTS")

    # Right: Doc type
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(GOLD)
    canvas.drawRightString(w - MARGIN, h - 11*mm, doc_label)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7899BB"))
    canvas.drawRightString(w - MARGIN, h - 16*mm, f"Page {doc.page}")

    # ── Footer ──
    canvas.setFillColor(LIGHT_GREY)
    canvas.rect(0, 0, w, 14*mm, fill=1, stroke=0)

    # Gold top line on footer
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(0, 14*mm, w, 14*mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_LIGHT)
    footer = f"{agency_name}  ·  {agent_email}  ·  Prepared {datetime.now().strftime('%d %B %Y')}"
    canvas.drawCentredString(w/2, 5.5*mm, footer)

    canvas.restoreState()


# ─── QUOTE PDF ────────────────────────────────────────────────────
def generate_quote_pdf(data):
    buffer = io.BytesIO()
    styles = S()

    agency   = data.get("agency_name", "SafariFlow")
    symbol   = data.get("currency_symbol", "$")
    ag_email = data.get("agent_email", "")

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=26*mm, bottomMargin=20*mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    template = PageTemplate(
        id="main", frames=[frame],
        onPage=lambda c, d: draw_page(c, d, agency, ag_email, "TRAVEL QUOTE")
    )
    doc.addPageTemplates([template])

    story = []

    # ── 1. Hero Section ─────────────────────────────────────────
    client_name = data.get("client_name", "Valued Client")
    destination = data.get("destination", "")

    hero = Table([[
        Table([
            [Paragraph(f"Quote prepared for", styles["label"])],
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

    # ── 2. Quote Meta Grid ───────────────────────────────────────
    meta = [
        ("QUOTE DATE",    data.get("quote_date", "—")),
        ("TRAVEL DATES",  data.get("travel_dates", "—")),
        ("TRAVELERS",     str(data.get("num_travelers", "—"))),
        ("TRAVEL AGENT",  data.get("agent_name", "—")),
    ]
    col_w = INNER_W / 4

    meta_cells = []
    for label, val in meta:
        cell = Table([
            [Paragraph(label, styles["label"])],
            [Paragraph(val, styles["value"])],
        ], colWidths=[col_w - 6])
        cell.setStyle(TableStyle([
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        meta_cells.append(cell)

    meta_table = Table([meta_cells], colWidths=[col_w]*4)
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("LINEBELOW", (0,0), (-1,-1), 0.8, GOLD),
        ("LINEABOVE", (0,0), (-1,-1), 0.3, BORDER),
        ("LINEBEFORE", (1,0), (1,0), 0.5, BORDER),
        ("LINEBEFORE", (2,0), (2,0), 0.5, BORDER),
        ("LINEBEFORE", (3,0), (3,0), 0.5, BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6*mm))

    # ── 3. Client + Agent Info Row ───────────────────────────────
    client_block = Table([
        [Paragraph("CLIENT INFORMATION", styles["section_title"])],
        [Spacer(1, 4)],
        [Paragraph("Name", styles["label"])],
        [Paragraph(data.get("client_name", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Email", styles["label"])],
        [Paragraph(data.get("client_email", "—"), styles["body"])],
        [Spacer(1, 3)],
        [Paragraph("Phone", styles["label"])],
        [Paragraph(data.get("client_phone", "—") or "—", styles["body"])],
    ], colWidths=[INNER_W * 0.48])

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
    ], colWidths=[INNER_W * 0.48])

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

    # ── 4. Items Table ───────────────────────────────────────────
    story.append(Paragraph("QUOTE BREAKDOWN", styles["section_title"]))
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

    for i, item in enumerate(data.get("items", [])):
        try:
            up = float(item.get("unit_price", 0))
            qty = float(item.get("quantity", 1))
            line = up * qty
            subtotal += line
        except:
            line = 0

        rows.append([
            Table([
                [Paragraph(item.get("description",""), styles["item_desc"])],
            ], colWidths=[col_widths[0]-10]),
            Paragraph(item.get("details",""), styles["item_detail"]),
            Paragraph(str(item.get("quantity",1)), styles["body"]),
            Paragraph(fmt_currency(item.get("unit_price",0), symbol), styles["price"]),
            Paragraph(fmt_currency(line, symbol), styles["price_bold"]),
        ])

    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    n = len(rows)

    row_colors = []
    for i in range(1, n):
        bg = WHITE if i % 2 == 1 else LIGHT_GREY
        row_colors.append(("BACKGROUND", (0,i), (-1,i), bg))

    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), GOLD),
        ("LINEBELOW", (0,0), (-1,0), 1.5, GOLD),
        # All cells
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

    # ── 5. Total Banner ──────────────────────────────────────────
    grand_total = subtotal - float(data.get("discount", 0))

    total_banner = Table([[
        Paragraph("TOTAL INVESTMENT", styles["total_label"]),
        Paragraph(fmt_currency(grand_total, symbol), styles["total_amount"]),
    ]], colWidths=[INNER_W * 0.55, INNER_W * 0.45])
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
    story.append(Spacer(1, 6*mm))

    # ── 6. Inclusions / Exclusions ───────────────────────────────
    notes_raw = data.get("notes", "")
    inc_text = ""
    exc_text = ""

    # Parse inclusions/exclusions from notes if present
    if "Package includes:" in notes_raw:
        parts = notes_raw.split("Package includes:")
        base_note = parts[0].strip()
        rest = parts[1]
        if "Not included:" in rest:
            inc_text, exc_text = rest.split("Not included:")
        else:
            inc_text = rest
    else:
        base_note = notes_raw

    if inc_text or exc_text:
        inc_items = [i.strip() for i in inc_text.split(",") if i.strip()]
        exc_items = [i.strip() for i in exc_text.split(",") if i.strip()]

        inc_content = [Paragraph("INCLUDED IN THIS PACKAGE", styles["inc_title"]), Spacer(1, 5)]
        for item in inc_items:
            inc_content.append(Paragraph(f"<b>&#x2713;</b>  {item}", styles["inc_item"]))
            inc_content.append(Spacer(1, 2))

        exc_content = [Paragraph("NOT INCLUDED", styles["exc_title"]), Spacer(1, 5)]
        for item in exc_items:
            exc_content.append(Paragraph(f"<b>&#x2715;</b>  {item}", styles["inc_item"]))
            exc_content.append(Spacer(1, 2))

        half = INNER_W / 2
        ie_table = Table([[inc_content, exc_content]], colWidths=[half, half])
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

    # ── 7. Notes & Conditions ────────────────────────────────────
    if base_note:
        story.append(Paragraph("NOTES & CONDITIONS", styles["section_title"]))
        story.append(Spacer(1, 2*mm))
        notes_table = Table([[Paragraph(base_note, styles["note"])]], colWidths=[INNER_W])
        notes_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), GOLD_BG),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("RIGHTPADDING", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBELOW", (0,0), (-1,-1), 1, GOLD),
            ("LINEABOVE", (0,0), (-1,-1), 1, GOLD),
            ("LINEBEFORE", (0,0), (-1,-1), 3, GOLD),
        ]))
        story.append(notes_table)
        story.append(Spacer(1, 5*mm))

    # ── 8. Payment & Booking ────────────────────────────────────
    payment_items = [
        ("Deposit Required",  "50% on booking confirmation"),
        ("Balance Due",       "30 days before departure"),
        ("Payment Methods",   "Bank transfer / Credit card"),
        ("Cancellation",      "See terms & conditions"),
    ]

    payment_cells = []
    for label, val in payment_items:
        payment_cells.append(Table([
            [Paragraph(label.upper(), styles["label"])],
            [Paragraph(val, styles["body_mid"])],
        ], colWidths=[INNER_W/4 - 4]))

    payment_table = Table([payment_cells], colWidths=[INNER_W/4]*4)
    payment_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CREAM),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ("LINEABOVE", (0,0), (-1,-1), 0.5, BORDER),
        ("LINEBELOW", (0,-1), (-1,-1), 0.5, BORDER),
        ("LINEBEFORE", (1,0), (1,-1), 0.5, BORDER),
        ("LINEBEFORE", (2,0), (2,-1), 0.5, BORDER),
        ("LINEBEFORE", (3,0), (3,-1), 0.5, BORDER),
    ]))

    story.append(Paragraph("BOOKING & PAYMENT", styles["section_title"]))
    story.append(Spacer(1, 2*mm))
    story.append(payment_table)
    story.append(Spacer(1, 5*mm))

    # ── 9. CTA Footer ────────────────────────────────────────────
    cta = Table([[
        Table([
            [Paragraph("READY TO BOOK?", styles["total_label"])],
            [Spacer(1, 4)],
            [Paragraph(
                f"Contact <b>{data.get('agent_name','your agent')}</b> to confirm this quote.",
                ParagraphStyle("cta_body", fontSize=9, fontName="Helvetica",
                    textColor=colors.HexColor("#AABBCC"), leading=13)
            )],
            [Paragraph(
                ag_email,
                ParagraphStyle("cta_email", fontSize=9, fontName="Helvetica-Bold",
                    textColor=GOLD, leading=13)
            )],
        ], colWidths=[INNER_W * 0.6]),
        Table([
            [Paragraph("This quote is confidential and prepared exclusively for the named client.", 
                ParagraphStyle("disc", fontSize=7.5, fontName="Helvetica",
                    textColor=colors.HexColor("#7899BB"), leading=11, alignment=TA_RIGHT))],
            [Spacer(1, 4)],
            [Paragraph(
                f"Quote valid until {data.get('valid_until','—')}",
                ParagraphStyle("vld", fontSize=8, fontName="Helvetica-Bold",
                    textColor=GOLD, leading=12, alignment=TA_RIGHT))],
        ], colWidths=[INNER_W * 0.36]),
    ]], colWidths=[INNER_W*0.62, INNER_W*0.38])

    cta.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBEFORE", (1,0), (1,-1), 0.5, colors.HexColor("#2A4A6A")),
    ]))
    story.append(cta)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── ITINERARY PDF (unchanged structure, improved styling) ────────
def generate_itinerary_pdf(data):
    buffer = io.BytesIO()
    styles = S()
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

    # Hero
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

    # Summary strip
    summary = [
        ("CLIENT", data.get("client_name","—")),
        ("TRAVELERS", str(data.get("num_travelers","—"))),
        ("DAYS", str(len(data.get("days",[])))),
        ("AGENT", data.get("agent_name","—")),
    ]
    col_w = INNER_W / 4
    sum_cells = []
    for label, val in summary:
        sum_cells.append(Table([
            [Paragraph(label, styles["label"])],
            [Paragraph(val, styles["value"])],
        ], colWidths=[col_w-6]))

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

    # Day by day
    story.append(Paragraph("YOUR DAY-BY-DAY ITINERARY", styles["section_title"]))
    story.append(Spacer(1, 3*mm))

    for day in data.get("days", []):
        day_num   = day.get("day_number","")
        day_date  = day.get("date","")
        day_title = day.get("title","")

        # Day header bar
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
