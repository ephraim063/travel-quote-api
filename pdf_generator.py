import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

# ─── Brand Colors ────────────────────────────────────────────────
BRAND_DARK    = colors.HexColor("#1A2E4A")   # deep navy
BRAND_ACCENT  = colors.HexColor("#C8A96E")   # warm gold
BRAND_LIGHT   = colors.HexColor("#F5F7FA")   # light grey bg
BRAND_MID     = colors.HexColor("#4A6FA5")   # medium blue
WHITE         = colors.white
TEXT_DARK     = colors.HexColor("#222222")
TEXT_MID      = colors.HexColor("#555555")
TEXT_LIGHT    = colors.HexColor("#888888")
SUCCESS_GREEN = colors.HexColor("#27AE60")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ─── Style Helpers ───────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["h1"] = ParagraphStyle(
        "h1", fontSize=22, fontName="Helvetica-Bold",
        textColor=WHITE, leading=28, alignment=TA_LEFT
    )
    styles["h2"] = ParagraphStyle(
        "h2", fontSize=14, fontName="Helvetica-Bold",
        textColor=BRAND_DARK, leading=20, spaceAfter=4
    )
    styles["h3"] = ParagraphStyle(
        "h3", fontSize=11, fontName="Helvetica-Bold",
        textColor=BRAND_DARK, leading=16
    )
    styles["body"] = ParagraphStyle(
        "body", fontSize=9.5, fontName="Helvetica",
        textColor=TEXT_DARK, leading=14
    )
    styles["body_mid"] = ParagraphStyle(
        "body_mid", fontSize=9, fontName="Helvetica",
        textColor=TEXT_MID, leading=13
    )
    styles["body_small"] = ParagraphStyle(
        "body_small", fontSize=8, fontName="Helvetica",
        textColor=TEXT_LIGHT, leading=12
    )
    styles["label"] = ParagraphStyle(
        "label", fontSize=7.5, fontName="Helvetica-Bold",
        textColor=TEXT_LIGHT, leading=12, spaceAfter=1,
        letterSpacing=0.5
    )
    styles["value"] = ParagraphStyle(
        "value", fontSize=9.5, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=14
    )
    styles["accent"] = ParagraphStyle(
        "accent", fontSize=9.5, fontName="Helvetica-Bold",
        textColor=BRAND_ACCENT, leading=14
    )
    styles["total"] = ParagraphStyle(
        "total", fontSize=13, fontName="Helvetica-Bold",
        textColor=WHITE, leading=18, alignment=TA_RIGHT
    )
    styles["right"] = ParagraphStyle(
        "right", fontSize=9.5, fontName="Helvetica",
        textColor=TEXT_DARK, leading=14, alignment=TA_RIGHT
    )
    styles["right_bold"] = ParagraphStyle(
        "right_bold", fontSize=9.5, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=14, alignment=TA_RIGHT
    )
    styles["day_title"] = ParagraphStyle(
        "day_title", fontSize=12, fontName="Helvetica-Bold",
        textColor=WHITE, leading=16
    )
    styles["activity_time"] = ParagraphStyle(
        "activity_time", fontSize=8.5, fontName="Helvetica-Bold",
        textColor=BRAND_ACCENT, leading=12
    )
    styles["activity_title"] = ParagraphStyle(
        "activity_title", fontSize=10, fontName="Helvetica-Bold",
        textColor=BRAND_DARK, leading=14
    )
    styles["footer"] = ParagraphStyle(
        "footer", fontSize=7.5, fontName="Helvetica",
        textColor=TEXT_LIGHT, leading=11, alignment=TA_CENTER
    )
    return styles


def fmt_currency(amount, symbol="R"):
    try:
        return f"{symbol} {float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol} {amount}"


# ─── Header / Footer canvas drawing ──────────────────────────────
def draw_header_footer(canvas, doc, agency_name, doc_type="QUOTE"):
    canvas.saveState()
    w, h = A4

    # Top color bar
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)

    # Agency name left
    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(WHITE)
    canvas.drawString(MARGIN, h - 14 * mm, agency_name.upper())

    # Doc type right
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(BRAND_ACCENT)
    canvas.drawRightString(w - MARGIN, h - 14 * mm, doc_type)

    # Gold accent line
    canvas.setStrokeColor(BRAND_ACCENT)
    canvas.setLineWidth(2)
    canvas.line(0, h - 22 * mm, w, h - 22 * mm)

    # Footer
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_LIGHT)
    footer_text = (
        f"{agency_name}  |  "
        f"Generated {datetime.now().strftime('%d %B %Y')}  |  "
        f"Page {doc.page}"
    )
    canvas.drawCentredString(w / 2, 10 * mm, footer_text)

    # Footer line
    canvas.setStrokeColor(BRAND_ACCENT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 15 * mm, w - MARGIN, 15 * mm)

    canvas.restoreState()


# ─── QUOTE PDF ────────────────────────────────────────────────────
def generate_quote_pdf(data):
    buffer = io.BytesIO()
    S = make_styles()

    agency_name = data.get("agency_name", "Travel Agency")
    currency_symbol = data.get("currency_symbol", "R")

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main"
    )
    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=lambda c, d: draw_header_footer(c, d, agency_name, "TRAVEL QUOTE")
    )
    doc.addPageTemplates([template])

    story = []
    usable_w = PAGE_W - 2 * MARGIN

    # ── Quote Hero Block ──
    hero_data = [[
        Paragraph(
            f"<b>Quote for {data.get('client_name', '')}</b>",
            ParagraphStyle("hero", fontSize=18, fontName="Helvetica-Bold",
                           textColor=BRAND_DARK, leading=24)
        ),
        Paragraph(
            f"<b>{data.get('destination', 'Your Dream Destination')}</b>",
            ParagraphStyle("hero_dest", fontSize=11, fontName="Helvetica",
                           textColor=BRAND_MID, leading=16, alignment=TA_RIGHT)
        )
    ]]
    hero_table = Table(hero_data, colWidths=[usable_w * 0.6, usable_w * 0.4])
    hero_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 6, 6]),
    ]))
    story.append(hero_table)
    story.append(Spacer(1, 6 * mm))

    # ── Info Grid (Quote No, Date, Valid Until, Travelers) ──
    info_items = [
        ("QUOTE NUMBER", data.get("quote_number", "—")),
        ("QUOTE DATE", data.get("quote_date", datetime.now().strftime("%d %B %Y"))),
        ("VALID UNTIL", data.get("valid_until", "—")),
        ("TRAVEL DATES", data.get("travel_dates", "—")),
        ("TRAVELERS", str(data.get("num_travelers", "—"))),
        ("AGENT", data.get("agent_name", "—")),
    ]

    col_w = usable_w / 3

    # Build two rows of 3 info cells each
    for row_items in [info_items[:3], info_items[3:]]:
        row_cells = []
        for label, value in row_items:
            cell = Table(
                [[Paragraph(label, S["label"])], [Paragraph(value, S["value"])]],
                colWidths=[col_w - 4]
            )
            cell.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            row_cells.append(cell)

        grid = Table([row_cells], colWidths=[col_w] * 3)
        grid.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, BRAND_ACCENT),
            ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#E0E0E0")),
            ("LINEBEFORE", (2, 0), (2, 0), 0.5, colors.HexColor("#E0E0E0")),
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ]))
        story.append(grid)
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 4 * mm))

    # ── Client Info ──
    story.append(Paragraph("CLIENT INFORMATION", S["label"]))
    story.append(Spacer(1, 2 * mm))
    client_data = [
        [
            Paragraph("Name", S["label"]),
            Paragraph("Email", S["label"]),
            Paragraph("Phone", S["label"]),
        ],
        [
            Paragraph(data.get("client_name", "—"), S["body"]),
            Paragraph(data.get("client_email", "—"), S["body"]),
            Paragraph(data.get("client_phone", "—"), S["body"]),
        ]
    ]
    client_table = Table(client_data, colWidths=[usable_w / 3] * 3)
    client_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
        ("BACKGROUND", (0, 1), (-1, 1), WHITE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BRAND_ACCENT),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#E8E8E8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 5 * mm))

    # ── Items Table ──
    story.append(Paragraph("QUOTE BREAKDOWN", S["label"]))
    story.append(Spacer(1, 2 * mm))

    items_header = [
        Paragraph("DESCRIPTION", S["label"]),
        Paragraph("DETAILS", S["label"]),
        Paragraph("QTY", S["label"]),
        Paragraph("UNIT PRICE", S["label"]),
        Paragraph("TOTAL", S["label"]),
    ]

    col_widths = [
        usable_w * 0.28,
        usable_w * 0.30,
        usable_w * 0.08,
        usable_w * 0.17,
        usable_w * 0.17,
    ]

    items_data = [items_header]
    subtotal = 0

    for item in data.get("items", []):
        try:
            unit_price = float(item.get("unit_price", 0))
            qty = float(item.get("quantity", 1))
            line_total = unit_price * qty
            subtotal += line_total
        except (ValueError, TypeError):
            line_total = 0
            subtotal += 0

        row = [
            Paragraph(item.get("description", ""), S["body"]),
            Paragraph(item.get("details", ""), S["body_mid"]),
            Paragraph(str(item.get("quantity", 1)), S["body"]),
            Paragraph(fmt_currency(item.get("unit_price", 0), currency_symbol), S["right"]),
            Paragraph(fmt_currency(line_total, currency_symbol), S["right_bold"]),
        ]
        items_data.append(row)

    # Subtotal / tax / total rows
    discount = float(data.get("discount", 0))
    tax_rate = float(data.get("tax_rate", 0))
    tax_amount = (subtotal - discount) * (tax_rate / 100)
    grand_total = subtotal - discount + tax_amount

    def summary_row(label, amount, bold=False, accent=False):
        label_style = S["right_bold"] if bold else S["right"]
        val_style = S["accent"] if accent else (S["right_bold"] if bold else S["right"])
        return [
            Paragraph("", S["body"]),
            Paragraph("", S["body"]),
            Paragraph("", S["body"]),
            Paragraph(label, label_style),
            Paragraph(fmt_currency(amount, currency_symbol), val_style),
        ]

    items_data.append(["", "", "", Paragraph("─" * 20, S["body_small"]), Paragraph("─" * 20, S["body_small"])])
    items_data.append(summary_row("Subtotal", subtotal))
    if discount > 0:
        items_data.append(summary_row(f"Discount", -discount))
    if tax_rate > 0:
        items_data.append(summary_row(f"Tax ({tax_rate}%)", tax_amount))

    items_table = Table(items_data, colWidths=col_widths, repeatRows=1)
    n = len(items_data)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, n - 3), [WHITE, BRAND_LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_ACCENT),
        ("LINEBELOW", (0, 1), (-1, n - 4), 0.3, colors.HexColor("#E8E8E8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 2 * mm))

    # ── Grand Total Banner ──
    total_data = [[
        Paragraph("TOTAL INVESTMENT", ParagraphStyle(
            "ti", fontSize=10, fontName="Helvetica-Bold",
            textColor=BRAND_ACCENT, leading=14
        )),
        Paragraph(
            fmt_currency(grand_total, currency_symbol),
            ParagraphStyle("gt", fontSize=18, fontName="Helvetica-Bold",
                           textColor=WHITE, leading=22, alignment=TA_RIGHT)
        )
    ]]
    total_table = Table(total_data, colWidths=[usable_w * 0.5, usable_w * 0.5])
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 5 * mm))

    # ── Notes / Inclusions ──
    if data.get("notes"):
        story.append(HRFlowable(width=usable_w, thickness=0.5, color=BRAND_ACCENT))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("NOTES & CONDITIONS", S["label"]))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(data["notes"], S["body_mid"]))
        story.append(Spacer(1, 3 * mm))

    if data.get("inclusions") or data.get("exclusions"):
        inc_exc_data = []
        if data.get("inclusions"):
            inc_lines = [Paragraph("INCLUDED", S["label"])]
            for item in data["inclusions"]:
                inc_lines.append(Paragraph(f"&#x2713;  {item}", S["body"]))
            inc_exc_data.append(inc_lines)
        if data.get("exclusions"):
            exc_lines = [Paragraph("NOT INCLUDED", S["label"])]
            for item in data["exclusions"]:
                exc_lines.append(Paragraph(f"&#x2715;  {item}", S["body"]))
            inc_exc_data.append(exc_lines)

        if len(inc_exc_data) == 2:
            ie_col_w = usable_w / 2
            ie_table = Table(
                [inc_exc_data],
                colWidths=[ie_col_w, ie_col_w]
            )
        else:
            ie_table = Table([inc_exc_data], colWidths=[usable_w])

        ie_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ]))
        story.append(ie_table)
        story.append(Spacer(1, 4 * mm))

    # ── Agent Signature Block ──
    story.append(HRFlowable(width=usable_w, thickness=0.5, color=BRAND_ACCENT))
    story.append(Spacer(1, 3 * mm))
    agent_data = [[
        Table([
            [Paragraph("YOUR TRAVEL SPECIALIST", S["label"])],
            [Paragraph(data.get("agent_name", "—"), S["h3"])],
            [Paragraph(data.get("agent_email", ""), S["body_mid"])],
            [Paragraph(data.get("agent_phone", ""), S["body_mid"])],
        ], colWidths=[usable_w * 0.5]),
        Table([
            [Paragraph("READY TO BOOK?", S["label"])],
            [Paragraph("Contact us to confirm this quote and secure your booking.", S["body_mid"])],
            [Spacer(1, 4)],
            [Paragraph(
                data.get("booking_note", "Prices subject to availability and exchange rate fluctuations."),
                ParagraphStyle("bn", fontSize=8, fontName="Helvetica",
                               textColor=TEXT_LIGHT, leading=12)
            )],
        ], colWidths=[usable_w * 0.5]),
    ]]
    agent_table = Table(agent_data, colWidths=[usable_w * 0.5, usable_w * 0.5])
    agent_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBEFORE", (1, 0), (1, 0), 1, BRAND_ACCENT),
        ("LEFTPADDING", (1, 0), (1, 0), 16),
    ]))
    story.append(agent_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── ITINERARY PDF ────────────────────────────────────────────────
def generate_itinerary_pdf(data):
    buffer = io.BytesIO()
    S = make_styles()

    agency_name = data.get("agency_name", "Travel Agency")

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main"
    )
    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=lambda c, d: draw_header_footer(c, d, agency_name, "TRAVEL ITINERARY")
    )
    doc.addPageTemplates([template])

    story = []
    usable_w = PAGE_W - 2 * MARGIN

    # ── Hero ──
    hero_data = [[
        Paragraph(
            f"<b>{data.get('destination', 'Your Journey')}</b>",
            ParagraphStyle("it_hero", fontSize=20, fontName="Helvetica-Bold",
                           textColor=BRAND_DARK, leading=26)
        ),
        Table([
            [Paragraph("ITINERARY", S["label"])],
            [Paragraph(data.get("itinerary_number", "—"), S["value"])],
            [Paragraph(data.get("travel_dates", ""), S["body_mid"])],
        ], colWidths=[usable_w * 0.38])
    ]]
    hero_table = Table(hero_data, colWidths=[usable_w * 0.62, usable_w * 0.38])
    hero_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_ACCENT),
    ]))
    story.append(hero_table)
    story.append(Spacer(1, 5 * mm))

    # ── Trip Summary ──
    summary_items = [
        ("CLIENT", data.get("client_name", "—")),
        ("TRAVELERS", str(data.get("num_travelers", "—"))),
        ("DURATION", f"{len(data.get('days', []))} Days"),
        ("TRAVEL AGENT", data.get("agent_name", "—")),
    ]
    col_w = usable_w / len(summary_items)
    summary_cells = []
    for label, val in summary_items:
        summary_cells.append(
            Table(
                [[Paragraph(label, S["label"])], [Paragraph(val, S["value"])]],
                colWidths=[col_w - 4]
            )
        )

    summary_table = Table([summary_cells], colWidths=[col_w] * len(summary_items))
    summary_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_ACCENT),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#DDDDDD")),
        ("LINEBEFORE", (2, 0), (2, 0), 0.5, colors.HexColor("#DDDDDD")),
        ("LINEBEFORE", (3, 0), (3, 0), 0.5, colors.HexColor("#DDDDDD")),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6 * mm))

    # ── Day-by-Day Itinerary ──
    story.append(Paragraph("YOUR DAY-BY-DAY ITINERARY", S["label"]))
    story.append(Spacer(1, 3 * mm))

    for day in data.get("days", []):
        day_num = day.get("day_number", "")
        day_date = day.get("date", "")
        day_title = day.get("title", "")

        # Day header
        day_header_data = [[
            Paragraph(f"DAY {day_num}", ParagraphStyle(
                "dn", fontSize=9, fontName="Helvetica-Bold",
                textColor=BRAND_ACCENT, leading=12
            )),
            Paragraph(f"<b>{day_title}</b>", S["day_title"]),
            Paragraph(day_date, ParagraphStyle(
                "dd", fontSize=9, fontName="Helvetica",
                textColor=colors.HexColor("#AABBCC"), leading=12, alignment=TA_RIGHT
            )),
        ]]
        day_header = Table(
            day_header_data,
            colWidths=[usable_w * 0.12, usable_w * 0.6, usable_w * 0.28]
        )
        day_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        # Activities
        activity_rows = []
        for i, act in enumerate(day.get("activities", [])):
            bg = WHITE if i % 2 == 0 else BRAND_LIGHT
            act_cell = [
                Table([
                    [Paragraph(act.get("time", ""), S["activity_time"])],
                ], colWidths=[usable_w * 0.12]),
                Table([
                    [Paragraph(act.get("title", ""), S["activity_title"])],
                    [Paragraph(act.get("description", ""), S["body_mid"])],
                ], colWidths=[usable_w * 0.88 - 4]),
            ]
            row_table = Table([act_cell], colWidths=[usable_w * 0.12, usable_w * 0.88])
            row_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E8E8E8")),
            ]))
            activity_rows.append(row_table)

        day_block = KeepTogether([day_header] + activity_rows + [Spacer(1, 4 * mm)])
        story.append(day_block)

    # ── Inclusions & Exclusions ──
    if data.get("inclusions") or data.get("exclusions"):
        story.append(HRFlowable(width=usable_w, thickness=0.5, color=BRAND_ACCENT))
        story.append(Spacer(1, 4 * mm))

        col_sections = []
        if data.get("inclusions"):
            inc_content = [Paragraph("WHAT'S INCLUDED", S["label"]), Spacer(1, 4)]
            for item in data["inclusions"]:
                inc_content.append(Paragraph(f"&#x2713;  {item}", S["body"]))
            col_sections.append(inc_content)
        if data.get("exclusions"):
            exc_content = [Paragraph("NOT INCLUDED", S["label"]), Spacer(1, 4)]
            for item in data["exclusions"]:
                exc_content.append(Paragraph(f"&#x2715;  {item}", S["body"]))
            col_sections.append(exc_content)

        if len(col_sections) == 2:
            ie_table = Table([col_sections], colWidths=[usable_w / 2, usable_w / 2])
        else:
            ie_table = Table([col_sections], colWidths=[usable_w])
        ie_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ]))
        story.append(ie_table)
        story.append(Spacer(1, 4 * mm))

    # ── Important Notes ──
    if data.get("important_notes"):
        notes_data = [[
            Paragraph("&#x26A0;  IMPORTANT NOTES", ParagraphStyle(
                "imp", fontSize=9, fontName="Helvetica-Bold",
                textColor=BRAND_DARK, leading=14
            )),
        ], [
            Paragraph(data["important_notes"], S["body_mid"])
        ]]
        notes_table = Table(notes_data, colWidths=[usable_w])
        notes_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF8E6")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FFFDF5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_ACCENT),
        ]))
        story.append(notes_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
