"""
SafariFlow PDF Generator v3
Produces a luxury safari quote document from the Make.com payload.

PDF Structure:
  Page 1   — Header band · client info · quote meta · overview narrative
  Page 2+  — Day-by-day itinerary with destination placeholder bars
  Page N   — Investment breakdown · pricing totals
  Page N   — Inclusions/exclusions · terms · respond section
  Last     — Agent trust page · stats · awards · reviews · contact

Data sources:
  agent / agent_profile / agent_reviews → Supabase-Fetch Agent (Module 42)
  client / trip                         → Variables-Normalize Data (Module 49)
  itinerary / line_items / pricing      → Claude 2-Build Itinerary (Module 51)
  narrative                             → Claude 3-Write Narrative (Module 52)

Note: Destination photos (Unsplash) are a later phase.
      Placeholder bars show destination name until photos are integrated.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable


# ─── Colours ──────────────────────────────────────────────────────────────────
NAVY       = HexColor('#1B2A47')
GOLD       = HexColor('#C4922A')
GOLD_STAR  = HexColor('#E8C068')
EARTH      = HexColor('#2C1810')
SAGE       = HexColor('#4A5E3A')
SAND       = HexColor('#F5F0E8')
CHARCOAL   = HexColor('#3D3D3D')
MUTED      = HexColor('#7A7A7A')
RULE_CLR   = HexColor('#D4B896')
TABLE_ALT  = HexColor('#FAF7F2')
NAVY_MUTED = HexColor('#8A9AB8')
REVIEW_BG  = HexColor('#F9F6F0')


# ─── Page geometry ────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
ML = 18 * mm
MR = 18 * mm
MT = 14 * mm
MB = 22 * mm
CW = PAGE_W - ML - MR


# ─── Helpers ──────────────────────────────────────────────────────────────────
def safe(val, fallback='—'):
    if val is None or str(val).strip().lower() in ('', 'null', 'none'):
        return fallback
    return str(val).strip()


def usd(val):
    try:
        return f"${float(val):,.0f}"
    except (TypeError, ValueError):
        return safe(val)


def hr(width=None, color=RULE_CLR, thickness=0.4, sb=3, sa=4):
    return HRFlowable(
        width=width or CW, thickness=thickness,
        color=color, spaceBefore=sb, spaceAfter=sa
    )


class DestinationBar(Flowable):
    """
    Sand-coloured placeholder bar shown where a destination photo will appear.
    Displays the destination name centred. Photo integration added in a later phase.
    """
    def __init__(self, destination):
        super().__init__()
        self.width       = CW
        self.height      = 14 * mm
        self.destination = destination

    def draw(self):
        c = self.canv
        c.setFillColor(SAND)
        c.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        c.setFillColor(RULE_CLR)
        c.setFont('Helvetica', 8)
        c.drawCentredString(self.width / 2, self.height / 2 - 3,
                            self.destination.upper())


# ─── Typography ───────────────────────────────────────────────────────────────
def make_styles():
    return {
        'section': ParagraphStyle('section',
            fontName='Helvetica-Bold', fontSize=8,
            textColor=SAGE, leading=10,
            spaceBefore=8, spaceAfter=2),
        'h1': ParagraphStyle('h1',
            fontName='Helvetica-Bold', fontSize=16,
            textColor=EARTH, leading=20, spaceBefore=4, spaceAfter=4),
        'h2': ParagraphStyle('h2',
            fontName='Helvetica-Bold', fontSize=11,
            textColor=EARTH, leading=14),
        'body': ParagraphStyle('body',
            fontName='Helvetica', fontSize=10,
            textColor=CHARCOAL, leading=15),
        'body_sm': ParagraphStyle('body_sm',
            fontName='Helvetica', fontSize=9,
            textColor=CHARCOAL, leading=13),
        'italic': ParagraphStyle('italic',
            fontName='Helvetica-Oblique', fontSize=10.5,
            textColor=CHARCOAL, leading=16),
        'muted': ParagraphStyle('muted',
            fontName='Helvetica', fontSize=8,
            textColor=MUTED, leading=11),
        'footer': ParagraphStyle('footer',
            fontName='Helvetica', fontSize=7.5,
            textColor=MUTED, leading=10, alignment=TA_CENTER),
        'meta_lbl': ParagraphStyle('meta_lbl',
            fontName='Helvetica-Bold', fontSize=7.5,
            textColor=MUTED, leading=9),
        'meta_val': ParagraphStyle('meta_val',
            fontName='Helvetica', fontSize=9,
            textColor=CHARCOAL, leading=12),
        'meta_bold': ParagraphStyle('meta_bold',
            fontName='Helvetica-Bold', fontSize=9,
            textColor=CHARCOAL, leading=12),
        'client_name': ParagraphStyle('client_name',
            fontName='Helvetica-Bold', fontSize=17,
            textColor=EARTH, leading=21),
        'client_tag': ParagraphStyle('client_tag',
            fontName='Helvetica', fontSize=9,
            textColor=MUTED, leading=12),
        'day_num': ParagraphStyle('day_num',
            fontName='Helvetica-Bold', fontSize=8.5,
            textColor=GOLD, leading=11),
        'day_dest': ParagraphStyle('day_dest',
            fontName='Helvetica', fontSize=8.5,
            textColor=MUTED, leading=11, alignment=TA_RIGHT),
        'day_title': ParagraphStyle('day_title',
            fontName='Helvetica-Bold', fontSize=12,
            textColor=EARTH, leading=15),
        'highlight': ParagraphStyle('highlight',
            fontName='Helvetica-Oblique', fontSize=9,
            textColor=SAGE, leading=12),
        'th': ParagraphStyle('th',
            fontName='Helvetica-Bold', fontSize=8.5,
            textColor=white, leading=11),
        'td': ParagraphStyle('td',
            fontName='Helvetica', fontSize=8.5,
            textColor=CHARCOAL, leading=12),
        'td_r': ParagraphStyle('td_r',
            fontName='Helvetica', fontSize=8.5,
            textColor=CHARCOAL, leading=12, alignment=TA_RIGHT),
        'total_lbl': ParagraphStyle('total_lbl',
            fontName='Helvetica', fontSize=9,
            textColor=MUTED, leading=12, alignment=TA_RIGHT),
        'total_val': ParagraphStyle('total_val',
            fontName='Helvetica-Bold', fontSize=14,
            textColor=EARTH, leading=18, alignment=TA_RIGHT),
        'agent_name': ParagraphStyle('agent_name',
            fontName='Helvetica-Bold', fontSize=18,
            textColor=EARTH, leading=22),
        'agent_tag': ParagraphStyle('agent_tag',
            fontName='Helvetica', fontSize=9,
            textColor=MUTED, leading=12),
        'agent_bio': ParagraphStyle('agent_bio',
            fontName='Helvetica', fontSize=9.5,
            textColor=CHARCOAL, leading=14),
        'stat_num': ParagraphStyle('stat_num',
            fontName='Helvetica-Bold', fontSize=20,
            textColor=GOLD, leading=24, alignment=TA_CENTER),
        'stat_lbl': ParagraphStyle('stat_lbl',
            fontName='Helvetica', fontSize=8,
            textColor=MUTED, leading=10, alignment=TA_CENTER),
        'award': ParagraphStyle('award',
            fontName='Helvetica', fontSize=9,
            textColor=CHARCOAL, leading=13),
        'review_body': ParagraphStyle('review_body',
            fontName='Helvetica-Oblique', fontSize=8.5,
            textColor=CHARCOAL, leading=13),
        'review_author': ParagraphStyle('review_author',
            fontName='Helvetica-Bold', fontSize=8,
            textColor=EARTH, leading=11),
        'review_origin': ParagraphStyle('review_origin',
            fontName='Helvetica', fontSize=7.5,
            textColor=MUTED, leading=10),
        'contact': ParagraphStyle('contact',
            fontName='Helvetica', fontSize=9,
            textColor=CHARCOAL, leading=13),
    }


# ─── Header band flowable ─────────────────────────────────────────────────────
class HeaderBand(Flowable):
    """Full-width navy band: agency name + tagline left · SAFARI QUOTE right."""
    def __init__(self, agency, tagline='TRAVEL & SAFARI SPECIALISTS'):
        super().__init__()
        self.width   = CW
        self.height  = 20 * mm
        self.agency  = agency.upper()
        self.tagline = tagline.upper()

    def draw(self):
        c   = self.canv
        w, h = self.width, self.height
        pad  = 5 * mm

        c.setFillColor(NAVY)
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # Gold bottom rule
        c.setFillColor(GOLD)
        c.rect(0, 0, w, 2, fill=1, stroke=0)

        # Agency name
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 17)
        c.drawString(pad, h * 0.50, self.agency)

        # Tagline
        c.setFillColor(NAVY_MUTED)
        c.setFont('Helvetica', 8)
        c.drawString(pad, h * 0.24, self.tagline)

        # SAFARI QUOTE
        c.setFillColor(GOLD)
        c.setFont('Helvetica-Bold', 9.5)
        c.drawRightString(w - pad, h * 0.50, 'SAFARI QUOTE')

        # Page label
        c.setFillColor(NAVY_MUTED)
        c.setFont('Helvetica', 8)
        c.drawRightString(w - pad, h * 0.24, 'Page 1')


# ─── Section 1: Page 1 header ─────────────────────────────────────────────────
def build_page1(data, S, story):
    agent   = data.get('agent', {})
    client  = data.get('client', {})
    trip    = data.get('trip', {})
    profile = data.get('agent_profile', {})

    agency     = safe(agent.get('agency'), 'Safari Agency')
    agent_name = safe(agent.get('name'))
    agent_email= safe(agent.get('email'))
    tagline    = safe(profile.get('tagline'), 'Travel & Safari Specialists')
    quote_id   = safe(data.get('quote_id'), 'SF-0001')
    gen_date   = safe(data.get('generated_at'))

    client_name = safe(client.get('name'))
    nationality = safe(client.get('nationality'), '')
    pax_adults  = safe(client.get('pax_adults'), '2')
    pax_kids    = safe(client.get('pax_children'), '0')
    pax_str     = f"{pax_adults} Adults"
    if pax_kids not in ('0', '—'):
        pax_str += f", {pax_kids} Children"

    start  = safe(trip.get('start_date'))
    end    = safe(trip.get('end_date'))
    nights = safe(trip.get('duration_nights'))
    dests  = safe(trip.get('destinations'))

    # ── Navy header band ──────────────────────────────────────────────────────
    story.append(HeaderBand(agency, tagline))
    story.append(Spacer(1, 3 * mm))

    # Subline
    story.append(Paragraph(
        f"{agency}  ·  {agent_email}  ·  Prepared {gen_date}",
        S['muted']
    ))
    story.append(Spacer(1, 4 * mm))

    # ── Client hero block ─────────────────────────────────────────────────────
    dest_line = '  ·  '.join(
        [f"✈ {d.strip()}" for d in dests.split(',')]
    ) if dests != '—' else ''

    left_rows = [
        [Paragraph('Safari Proposal prepared for', S['muted'])],
        [Paragraph(client_name, S['client_name'])],
        [Spacer(1, 2)],
        [Paragraph(dest_line, S['client_tag'])],
    ]
    left_t = Table(left_rows, colWidths=[CW * 0.52])
    left_t.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 4),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))

    right_rows = [
        [Paragraph('QUOTE NUMBER',    S['meta_lbl']),
         Paragraph('VALID UNTIL',     S['meta_lbl'])],
        [Paragraph(f'<b>{quote_id}</b>', S['meta_bold']),
         Paragraph('14 days from issue', S['meta_val'])],
        [Spacer(1, 4), Spacer(1, 4)],
        [Paragraph('PREPARED BY',     S['meta_lbl']),
         Paragraph('QUOTE DATE',      S['meta_lbl'])],
        [Paragraph(agent_name,        S['meta_val']),
         Paragraph(gen_date,          S['meta_val'])],
    ]
    right_t = Table(right_rows, colWidths=[CW * 0.25, CW * 0.23])
    right_t.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 4),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))

    hero = Table([[left_t, right_t]], colWidths=[CW * 0.52, CW * 0.48])
    hero.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('BOX',           (0,0), (-1,-1), 0.4, RULE_CLR),
        ('BACKGROUND',    (0,0), (-1,-1), SAND),
        ('LINEAFTER',     (0,0), (0,-1),  0.4, RULE_CLR),
    ]))
    story.append(hero)
    story.append(Spacer(1, 4 * mm))

    # ── Trip meta strip ───────────────────────────────────────────────────────
    col = CW / 4
    meta_rows = [[
        Paragraph('TRAVEL DATES',  S['meta_lbl']),
        Paragraph('TRAVELERS',     S['meta_lbl']),
        Paragraph('DURATION',      S['meta_lbl']),
        Paragraph('',              S['meta_lbl']),
    ],[
        Paragraph(f"{start} – {end}", S['meta_val']),
        Paragraph(pax_str,            S['meta_val']),
        Paragraph(f"{nights} Days",   S['meta_val']),
        Paragraph('',                 S['meta_val']),
    ]]
    mt = Table(meta_rows, colWidths=[col, col, col, col])
    mt.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('BACKGROUND',    (0,0), (-1,-1), SAND),
        ('BOX',           (0,0), (-1,-1), 0.4, RULE_CLR),
        ('INNERGRID',     (0,0), (-1,-1), 0.3, RULE_CLR),
    ]))
    story.append(mt)
    story.append(Spacer(1, 4 * mm))

    # ── Client information ────────────────────────────────────────────────────
    story.append(Paragraph('CLIENT INFORMATION', S['section']))
    story.append(hr())

    ci_rows = [[
        Paragraph('Name',        S['meta_lbl']),
        Paragraph('Email',       S['meta_lbl']),
        Paragraph('Nationality', S['meta_lbl']),
    ],[
        Paragraph(client_name,                  S['meta_val']),
        Paragraph(safe(client.get('email')),    S['meta_val']),
        Paragraph(nationality,                  S['meta_val']),
    ]]
    ci = Table(ci_rows, colWidths=[CW/3, CW/3, CW/3])
    ci.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
    ]))
    story.append(ci)
    story.append(Spacer(1, 3 * mm))

    # ── Travel specialist ─────────────────────────────────────────────────────
    story.append(Paragraph('YOUR TRAVEL SPECIALIST', S['section']))
    story.append(hr())

    ts_rows = [[
        Paragraph('Agent',  S['meta_lbl']),
        Paragraph('Email',  S['meta_lbl']),
        Paragraph('Agency', S['meta_lbl']),
    ],[
        Paragraph(agent_name,  S['meta_val']),
        Paragraph(agent_email, S['meta_val']),
        Paragraph(agency,      S['meta_val']),
    ]]
    ts = Table(ts_rows, colWidths=[CW/3, CW/3, CW/3])
    ts.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
    ]))
    story.append(ts)
    story.append(Spacer(1, 4 * mm))


# ─── Section 2: Overview narrative ───────────────────────────────────────────
def build_overview(data, S, story):
    intro = safe(data.get('narrative', {}).get('intro'), '')
    if not intro or intro == '—':
        return
    story.append(Paragraph('YOUR SAFARI OVERVIEW', S['section']))
    story.append(hr())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(intro, S['italic']))
    story.append(Spacer(1, 4 * mm))


# ─── Section 3: Day-by-day itinerary ─────────────────────────────────────────
def build_itinerary(data, S, story):
    import io as _io
    itinerary  = data.get('itinerary', [])
    narr_days  = data.get('narrative', {}).get('days', [])
    photo_cache= data.get('photo_cache', {})

    narr_idx = {}
    for d in narr_days:
        try:
            narr_idx[int(d.get('day_number', 0))] = d
        except (TypeError, ValueError):
            pass

    story.append(Paragraph('YOUR DAY-BY-DAY ITINERARY', S['section']))
    story.append(hr())
    story.append(Spacer(1, 3 * mm))

    for day in itinerary:
        try:
            num = int(day.get('day_number', 0))
        except (TypeError, ValueError):
            num = 0

        narr       = narr_idx.get(num, {})
        dest       = safe(day.get('destination'))
        title      = safe(day.get('title'), dest)
        img_query  = safe(day.get('image_search_query'), f"{dest} safari")
        narr_text  = safe(narr.get('narrative'), '')
        highlight  = safe(narr.get('highlight'), '')
        accom      = safe(day.get('accommodation_name'))
        accom_desc = safe(narr.get('accommodation_description'), '')
        room       = safe(day.get('room_type'))
        meals      = safe(day.get('meal_plan'))
        transport  = safe(day.get('transport_description'), '')

        elems = []

        # Destination photo — use real photo if available, else placeholder bar
        photo_bytes = photo_cache.get(img_query)
        if photo_bytes:
            try:
                from reportlab.platypus import Image as RLImage
                img = RLImage(_io.BytesIO(photo_bytes), width=CW, height=42*mm)
                elems.append(img)
                elems.append(Spacer(1, 2 * mm))
            except Exception:
                elems.append(DestinationBar(dest))
                elems.append(Spacer(1, 2 * mm))
        else:
            elems.append(DestinationBar(dest))
            elems.append(Spacer(1, 2 * mm))

        # Day number + destination header
        dh = Table([[
            Paragraph(f"DAY {num}", S['day_num']),
            Paragraph(dest,         S['day_dest']),
        ]], colWidths=[CW * 0.5, CW * 0.5])
        dh.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elems.append(dh)
        elems.append(Paragraph(title, S['day_title']))
        elems.append(Spacer(1, 2 * mm))

        if narr_text and narr_text != '—':
            elems.append(Paragraph(narr_text, S['body']))
            elems.append(Spacer(1, 2 * mm))

        if highlight and highlight != '—':
            elems.append(Paragraph(f"■  {highlight}", S['highlight']))
            elems.append(Spacer(1, 2 * mm))

        accom_full = f"{accom} — {accom_desc}" if accom_desc != '—' else accom
        elems.append(Paragraph(
            f"<b>Accommodation:</b> {accom_full}, {room}  |  <b>Meals:</b> {meals}",
            S['body_sm']
        ))

        if transport and transport not in ('—', 'null', 'None'):
            elems.append(Paragraph(
                f"<b>Transfer:</b> {transport}", S['body_sm']
            ))

        elems.append(Spacer(1, 3 * mm))
        elems.append(hr(color=RULE_CLR, thickness=0.3, sb=0, sa=4))

        story.append(KeepTogether(elems))


# ─── Section 4: Investment breakdown ─────────────────────────────────────────
def build_pricing(data, S, story):
    line_items = data.get('line_items', [])
    pricing    = data.get('pricing', {})

    story.append(PageBreak())
    story.append(Paragraph('INVESTMENT BREAKDOWN', S['section']))
    story.append(hr())
    story.append(Spacer(1, 3 * mm))

    if line_items:
        rows = [[
            Paragraph('DESCRIPTION', S['th']),
            Paragraph('DETAILS',     S['th']),
            Paragraph('QTY',         S['th']),
            Paragraph('UNIT PRICE',  S['th']),
            Paragraph('TOTAL',       S['th']),
        ]]
        for item in line_items:
            rows.append([
                Paragraph(safe(item.get('description')), S['td']),
                Paragraph(safe(item.get('details')),     S['td']),
                Paragraph(str(safe(item.get('quantity'))), S['td']),
                Paragraph(usd(item.get('unit_price')),   S['td_r']),
                Paragraph(usd(item.get('total_price')),  S['td_r']),
            ])

        t = Table(rows, colWidths=[58*mm, 52*mm, 10*mm, 27*mm, 27*mm],
                  repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),  EARTH),
            ('ROWBACKGROUNDS',(0,1),  (-1,-1), [white, TABLE_ALT]),
            ('ALIGN',         (3,0),  (-1,-1), 'RIGHT'),
            ('ALIGN',         (0,0),  (2,-1),  'LEFT'),
            ('VALIGN',        (0,0),  (-1,-1), 'TOP'),
            ('TOPPADDING',    (0,0),  (-1,-1), 5),
            ('BOTTOMPADDING', (0,0),  (-1,-1), 5),
            ('LEFTPADDING',   (0,0),  (-1,-1), 5),
            ('RIGHTPADDING',  (0,0),  (-1,-1), 5),
            ('LINEBELOW',     (0,0),  (-1,-1), 0.25, RULE_CLR),
        ]))
        story.append(t)

    story.append(Spacer(1, 5 * mm))

    total   = usd(pricing.get('total_price_usd'))
    deposit = usd(pricing.get('deposit_amount_usd'))
    balance = usd(pricing.get('balance_amount_usd'))
    notes   = safe(pricing.get('budget_notes'), '')

    totals = [
        [Paragraph('TOTAL INVESTMENT',     S['total_lbl']),
         Paragraph(total,                  S['total_val'])],
        [Paragraph('DEPOSIT REQUIRED (30%)', S['total_lbl']),
         Paragraph(deposit,                S['td_r'])],
        [Paragraph('BALANCE DUE',          S['total_lbl']),
         Paragraph(balance,                S['td_r'])],
    ]
    tt = Table(totals, colWidths=[CW - 50*mm, 50*mm])
    tt.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEABOVE',     (0,0), (-1,0),  0.5, GOLD),
        ('LINEBELOW',     (0,2), (-1,2),  0.5, GOLD),
        ('BACKGROUND',    (0,0), (-1,0),  SAND),
    ]))
    story.append(tt)

    if notes and notes != '—':
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"Note: {notes}", S['muted']))

    story.append(Spacer(1, 6 * mm))


# ─── Section 5: Inclusions / Terms / Respond ─────────────────────────────────
def build_inclusions_terms(data, S, story):
    inclusions  = safe(data.get('inclusions'), '')
    exclusions  = safe(data.get('exclusions'), '')
    terms       = safe(data.get('terms'), '')
    accept_url  = safe(data.get('accept_url'), '#')
    changes_url = safe(data.get('changes_url'), '#')

    col_w = (CW - 6*mm) / 2
    left_elems = []
    right_elems = []

    if inclusions and inclusions != '—':
        left_elems.append(Paragraph('INCLUDED IN THIS PACKAGE', S['section']))
        left_elems.append(hr(width=col_w))
        for line in inclusions.split('\n'):
            line = line.strip().lstrip('-•✓').strip()
            if line:
                left_elems.append(Paragraph(f"✓  {line}", S['body_sm']))

    if exclusions and exclusions != '—':
        right_elems.append(Paragraph('NOT INCLUDED', S['section']))
        right_elems.append(hr(width=col_w))
        for line in exclusions.split('\n'):
            line = line.strip().lstrip('-•✕✗').strip()
            if line:
                right_elems.append(Paragraph(f"✕  {line}", S['body_sm']))

    if left_elems or right_elems:
        inc_t = Table([[left_elems, right_elems]],
                      colWidths=[col_w, col_w])
        inc_t.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
        ]))
        story.append(inc_t)

    if terms and terms != '—':
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph('NOTES & CONDITIONS', S['section']))
        story.append(hr())
        story.append(Paragraph(terms, S['muted']))

    # Respond section
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph('RESPOND TO THIS QUOTE', S['section']))
    story.append(hr(color=GOLD, thickness=0.6))
    story.append(Spacer(1, 2 * mm))

    rt = Table([[
        Paragraph('■ <b>ACCEPT THIS QUOTE</b>', S['body_sm']),
        Paragraph(accept_url, S['muted']),
        Paragraph('✏ <b>REQUEST CHANGES</b>', S['body_sm']),
        Paragraph(changes_url, S['muted']),
    ]], colWidths=[35*mm, CW/2 - 35*mm, 35*mm, CW/2 - 35*mm])
    rt.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(rt)


# ─── Section 6: Agent trust page ─────────────────────────────────────────────
def build_trust_page(data, S, story):
    agent   = data.get('agent', {})
    profile = data.get('agent_profile', {})
    reviews = data.get('agent_reviews', [])

    agency      = safe(agent.get('agency'), 'Safari Agency')
    tagline     = safe(profile.get('tagline'), 'Travel & Safari Specialists')
    bio         = safe(profile.get('bio'), '')
    years_exp   = safe(profile.get('years_experience'), '10+')
    safaris     = safe(profile.get('safaris_planned'), '500+')
    countries   = safe(profile.get('countries_covered'), '15')
    awards      = profile.get('awards', [])
    memberships = profile.get('memberships', [])
    email       = safe(agent.get('email'))
    phone       = safe(agent.get('phone'))
    website     = safe(agent.get('website'), '')
    address     = safe(profile.get('address'), '')
    facebook    = safe(profile.get('facebook'), '')
    instagram   = safe(profile.get('instagram'), '')
    linkedin    = safe(profile.get('linkedin'), '')

    story.append(PageBreak())

    # Navy header band
    story.append(HeaderBand(agency, tagline))
    story.append(Spacer(1, 5 * mm))

    # Agency name + tagline
    story.append(Table([[
        Paragraph(agency.upper(), S['agent_name']),
        Paragraph(tagline.upper(), S['agent_tag']),
    ]], colWidths=[CW * 0.6, CW * 0.4]))
    story.append(Spacer(1, 2 * mm))

    # Bio
    if bio and bio != '—':
        story.append(Paragraph(bio, S['agent_bio']))

    story.append(Spacer(1, 4 * mm))
    story.append(hr(color=GOLD, thickness=0.5))
    story.append(Spacer(1, 4 * mm))

    # ── Stats strip ───────────────────────────────────────────────────────────
    stat_col = CW / 3
    stats_data = [[
        [Paragraph('■', S['stat_num']),
         Paragraph(years_exp, S['stat_num']),
         Paragraph('Years Experience', S['stat_lbl'])],
        [Paragraph('■', S['stat_num']),
         Paragraph(safaris, S['stat_num']),
         Paragraph('Safaris Planned', S['stat_lbl'])],
        [Paragraph('■', S['stat_num']),
         Paragraph(countries, S['stat_num']),
         Paragraph('Countries Covered', S['stat_lbl'])],
    ]]
    stats = Table(stats_data, colWidths=[stat_col, stat_col, stat_col])
    stats.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND',    (0,0), (-1,-1), SAND),
        ('BOX',           (0,0), (-1,-1), 0.3, RULE_CLR),
        ('INNERGRID',     (0,0), (-1,-1), 0.3, RULE_CLR),
    ]))
    story.append(stats)
    story.append(Spacer(1, 5 * mm))

    # ── Awards + Memberships ──────────────────────────────────────────────────
    col_w = (CW - 6*mm) / 2
    left_elems = []
    right_elems = []

    if awards:
        left_elems.append(Paragraph('AWARDS & RECOGNITION', S['section']))
        left_elems.append(hr(width=col_w))
        for a in awards:
            left_elems.append(Paragraph(f"■  {safe(a)}", S['award']))
        left_elems.append(Spacer(1, 3 * mm))

    if memberships:
        right_elems.append(Paragraph('MEMBERSHIPS & ACCREDITATIONS', S['section']))
        right_elems.append(hr(width=col_w))
        for m in memberships:
            right_elems.append(Paragraph(f"✓  {safe(m)}", S['award']))
        right_elems.append(Spacer(1, 3 * mm))

    if left_elems or right_elems:
        am_t = Table([[left_elems, right_elems]],
                     colWidths=[col_w, col_w])
        am_t.setStyle(TableStyle([
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING',   (0,0), (-1,-1), 0),
        ]))
        story.append(am_t)

    story.append(Spacer(1, 4 * mm))

    # ── 3 Client reviews ──────────────────────────────────────────────────────
    if reviews:
        story.append(Paragraph('WHAT OUR CLIENTS SAY', S['section']))
        story.append(hr(color=GOLD, thickness=0.5))
        story.append(Spacer(1, 3 * mm))

        review_list = list(reviews[:3])
        while len(review_list) < 3:
            review_list.append({})

        cells = []
        for rev in review_list:
            text   = safe(rev.get('review_text'), '')
            author = safe(rev.get('client_name'), '')
            origin = safe(rev.get('client_origin'), '')
            trip   = safe(rev.get('trip_summary'), '')

            cell = [
                Paragraph('★★★★★', ParagraphStyle('stars',
                    fontName='Helvetica', fontSize=11,
                    textColor=GOLD_STAR, leading=14)),
                Spacer(1, 2 * mm),
                Paragraph(f'"{text}"', S['review_body']),
                Spacer(1, 3 * mm),
                Paragraph(f"— {author}", S['review_author']),
                Paragraph(f"{origin}  ·  {trip}", S['review_origin']),
            ]
            cells.append(cell)

        col_w_r = (CW - 4*mm) / 3
        rev_t = Table([cells],
                      colWidths=[col_w_r, col_w_r, col_w_r])
        rev_t.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('BACKGROUND',    (0,0), (-1,-1), REVIEW_BG),
            ('BOX',           (0,0), (0,-1),  0.3, RULE_CLR),
            ('BOX',           (1,0), (1,-1),  0.3, RULE_CLR),
            ('BOX',           (2,0), (2,-1),  0.3, RULE_CLR),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ]))
        story.append(rev_t)
        story.append(Spacer(1, 5 * mm))

    # ── Get in touch ──────────────────────────────────────────────────────────
    story.append(Paragraph('GET IN TOUCH', S['section']))
    story.append(hr(color=GOLD, thickness=0.5))
    story.append(Spacer(1, 2 * mm))

    contact_items = []
    if email    != '—': contact_items.append(f"✉  {email}")
    if phone    != '—': contact_items.append(f"☏  {phone}")
    if website  != '—': contact_items.append(f"🌐  {website}")
    if address  != '—': contact_items.append(f"📍  {address}")
    if facebook != '—': contact_items.append(f"Facebook: {facebook}")
    if instagram!= '—': contact_items.append(f"Instagram: {instagram}")
    if linkedin != '—': contact_items.append(f"LinkedIn: {linkedin}")

    mid    = (len(contact_items) + 1) // 2
    left_c = [Paragraph(i, S['contact']) for i in contact_items[:mid]]
    right_c= [Paragraph(i, S['contact']) for i in contact_items[mid:]]

    ct = Table([[left_c, right_c]],
               colWidths=[(CW - 6*mm)/2, (CW - 6*mm)/2])
    ct.setStyle(TableStyle([
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',   (0,0), (-1,-1), 0),
    ]))
    story.append(ct)


# ─── Running header/footer ────────────────────────────────────────────────────
def make_page_template(agency, email, date):
    def on_page(canvas, doc):
        canvas.saveState()

        # Subpage header (pages 2+)
        if doc.page > 1:
            canvas.setFillColor(NAVY)
            canvas.rect(ML, PAGE_H - MT - 9*mm, CW, 9*mm, fill=1, stroke=0)
            canvas.setFillColor(GOLD)
            canvas.rect(ML, PAGE_H - MT - 9*mm, CW, 1.5, fill=1, stroke=0)

            canvas.setFillColor(white)
            canvas.setFont('Helvetica-Bold', 7.5)
            canvas.drawString(ML + 4*mm, PAGE_H - MT - 5.5*mm,
                              agency.upper())

            canvas.setFillColor(NAVY_MUTED)
            canvas.setFont('Helvetica', 7)
            canvas.drawCentredString(PAGE_W / 2, PAGE_H - MT - 5.5*mm,
                f"{agency}  ·  {email}  ·  Prepared {date}")

            canvas.setFillColor(GOLD)
            canvas.setFont('Helvetica-Bold', 7.5)
            canvas.drawRightString(PAGE_W - MR - 4*mm,
                                   PAGE_H - MT - 5.5*mm, 'SAFARI QUOTE')

        # Footer
        canvas.setStrokeColor(RULE_CLR)
        canvas.setLineWidth(0.3)
        canvas.line(ML, MB - 4*mm, PAGE_W - MR, MB - 4*mm)

        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, MB - 8*mm,
            f"{agency}  ·  {email}  ·  Page {doc.page}")

        canvas.restoreState()
    return on_page


# ─── Main entry point ─────────────────────────────────────────────────────────
def generate_quote_pdf(data: dict, output_path: str):
    """
    Generate a complete safari quote PDF.
    Data must be pre-structured by app.py before calling this function.
    Flask v4 sends the correct structure directly — no remapping needed.
    """
    S      = make_styles()
    agency = safe(data.get('agent', {}).get('agency'), 'SafariFlow')
    email  = safe(data.get('agent', {}).get('email'), '')
    date   = safe(data.get('generated_at'), '')

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title=f"Safari Quote — {safe(data.get('client', {}).get('name', ''))}",
        author=agency,
    )

    story = []
    build_page1(data, S, story)
    build_overview(data, S, story)
    build_itinerary(data, S, story)
    build_pricing(data, S, story)
    build_inclusions_terms(data, S, story)
    build_trust_page(data, S, story)

    doc.build(
        story,
        onFirstPage=make_page_template(agency, email, date),
        onLaterPages=make_page_template(agency, email, date),
    )
