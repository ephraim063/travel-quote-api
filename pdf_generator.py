"""
SafariFlow PDF Generator v4
- generate_quote_pdf         : clean client-facing quote, NO cost data
- generate_cost_breakdown_pdf: internal agent doc — investment + cost breakdown only
- generate_invoice_pdf       : client invoice
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

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY       = HexColor('#1B2A47')
GOLD       = HexColor('#C4922A')
GOLD_STAR  = HexColor('#E8C068')
EARTH      = HexColor('#1A1A1A')
SAGE       = HexColor('#2D4A1E')
SAND       = HexColor('#F5F0E8')
CHARCOAL   = HexColor('#1C1C1C')
MUTED      = HexColor('#444444')
RULE_CLR   = HexColor('#D4B896')
TABLE_ALT  = HexColor('#FAF7F2')
NAVY_MUTED = HexColor('#8A9AB8')
REVIEW_BG  = HexColor('#F9F6F0')
PROFIT_GRN = HexColor('#2D7A2D')
PROFIT_RED = HexColor('#B03030')
PROFIT_LGT = HexColor('#90EE90')

# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
ML = 18 * mm; MR = 18 * mm; MT = 26 * mm; MB = 22 * mm
CW = PAGE_W - ML - MR

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe(val, fallback='—'):
    if val is None or str(val).strip().lower() in ('', 'null', 'none'):
        return fallback
    return str(val).strip()

def usd(val):
    try: return f"${float(val):,.0f}"
    except: return safe(val)

def hr(width=None, color=RULE_CLR, thickness=0.4, sb=3, sa=4):
    return HRFlowable(width=width or CW, thickness=thickness, color=color, spaceBefore=sb, spaceAfter=sa)

class DestinationBar(Flowable):
    def __init__(self, destination):
        super().__init__()
        self.width = CW; self.height = 14 * mm; self.destination = destination
    def draw(self):
        c = self.canv
        c.setFillColor(SAND); c.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        c.setFillColor(RULE_CLR); c.setFont('Helvetica', 8)
        c.drawCentredString(self.width / 2, self.height / 2 - 3, self.destination.upper())

def make_styles():
    return {
        'section':      ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=8, textColor=SAGE, leading=10, spaceBefore=8, spaceAfter=2),
        'body':         ParagraphStyle('body', fontName='Helvetica', fontSize=10, textColor=CHARCOAL, leading=15),
        'body_sm':      ParagraphStyle('body_sm', fontName='Helvetica', fontSize=9, textColor=CHARCOAL, leading=13),
        'italic':       ParagraphStyle('italic', fontName='Helvetica-Oblique', fontSize=10.5, textColor=CHARCOAL, leading=16),
        'muted':        ParagraphStyle('muted', fontName='Helvetica', fontSize=8, textColor=MUTED, leading=11),
        'meta_lbl':     ParagraphStyle('meta_lbl', fontName='Helvetica-Bold', fontSize=7.5, textColor=MUTED, leading=9),
        'meta_val':     ParagraphStyle('meta_val', fontName='Helvetica', fontSize=9, textColor=CHARCOAL, leading=12),
        'meta_bold':    ParagraphStyle('meta_bold', fontName='Helvetica-Bold', fontSize=9, textColor=CHARCOAL, leading=12),
        'client_name':  ParagraphStyle('client_name', fontName='Helvetica-Bold', fontSize=17, textColor=EARTH, leading=21),
        'client_tag':   ParagraphStyle('client_tag', fontName='Helvetica', fontSize=9, textColor=MUTED, leading=12),
        'day_num':      ParagraphStyle('day_num', fontName='Helvetica-Bold', fontSize=8.5, textColor=GOLD, leading=11),
        'day_dest':     ParagraphStyle('day_dest', fontName='Helvetica', fontSize=8.5, textColor=MUTED, leading=11, alignment=TA_RIGHT),
        'day_title':    ParagraphStyle('day_title', fontName='Helvetica-Bold', fontSize=12, textColor=EARTH, leading=15),
        'highlight':    ParagraphStyle('highlight', fontName='Helvetica-Oblique', fontSize=9, textColor=SAGE, leading=12),
        'th':           ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8.5, textColor=white, leading=11),
        'td':           ParagraphStyle('td', fontName='Helvetica', fontSize=8.5, textColor=CHARCOAL, leading=12),
        'td_r':         ParagraphStyle('td_r', fontName='Helvetica', fontSize=8.5, textColor=CHARCOAL, leading=12, alignment=TA_RIGHT),
        'total_lbl':    ParagraphStyle('total_lbl', fontName='Helvetica', fontSize=9, textColor=MUTED, leading=12, alignment=TA_RIGHT),
        'total_val':    ParagraphStyle('total_val', fontName='Helvetica-Bold', fontSize=14, textColor=EARTH, leading=18, alignment=TA_RIGHT),
        'agent_name':   ParagraphStyle('agent_name', fontName='Helvetica-Bold', fontSize=18, textColor=EARTH, leading=22),
        'agent_tag':    ParagraphStyle('agent_tag', fontName='Helvetica', fontSize=9, textColor=MUTED, leading=12),
        'agent_bio':    ParagraphStyle('agent_bio', fontName='Helvetica', fontSize=9.5, textColor=CHARCOAL, leading=14),
        'stat_num':     ParagraphStyle('stat_num', fontName='Helvetica-Bold', fontSize=20, textColor=GOLD, leading=24, alignment=TA_CENTER),
        'stat_lbl':     ParagraphStyle('stat_lbl', fontName='Helvetica', fontSize=8, textColor=MUTED, leading=10, alignment=TA_CENTER),
        'award':        ParagraphStyle('award', fontName='Helvetica', fontSize=9, textColor=CHARCOAL, leading=13),
        'review_body':  ParagraphStyle('review_body', fontName='Helvetica-Oblique', fontSize=8.5, textColor=CHARCOAL, leading=13),
        'review_author':ParagraphStyle('review_author', fontName='Helvetica-Bold', fontSize=8, textColor=EARTH, leading=11),
        'review_origin':ParagraphStyle('review_origin', fontName='Helvetica', fontSize=7.5, textColor=MUTED, leading=10),
        'contact':      ParagraphStyle('contact', fontName='Helvetica', fontSize=9, textColor=CHARCOAL, leading=13),
    }

# ── Header bands ──────────────────────────────────────────────────────────────
class HeaderBand(Flowable):
    def __init__(self, agency, tagline='TRAVEL & SAFARI SPECIALISTS'):
        super().__init__()
        self.width = CW; self.height = 20 * mm
        self.agency = agency.upper(); self.tagline = tagline.upper()
    def draw(self):
        c = self.canv; w, h = self.width, self.height; pad = 5 * mm
        c.setFillColor(NAVY); c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(GOLD); c.rect(0, 0, w, 2, fill=1, stroke=0)
        c.setFillColor(white); c.setFont('Helvetica-Bold', 17); c.drawString(pad, h*0.50, self.agency)
        c.setFillColor(NAVY_MUTED); c.setFont('Helvetica', 8); c.drawString(pad, h*0.24, self.tagline)
        c.setFillColor(GOLD); c.setFont('Helvetica-Bold', 9.5); c.drawRightString(w-pad, h*0.50, 'SAFARI QUOTE')
        c.setFillColor(NAVY_MUTED); c.setFont('Helvetica', 8); c.drawRightString(w-pad, h*0.24, 'Page 1')

class InternalHeaderBand(Flowable):
    def __init__(self, agency):
        super().__init__()
        self.width = CW; self.height = 20 * mm; self.agency = agency.upper()
    def draw(self):
        c = self.canv; w, h = self.width, self.height; pad = 5 * mm
        c.setFillColor(EARTH); c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(GOLD); c.rect(0, 0, w, 2, fill=1, stroke=0)
        c.setFillColor(white); c.setFont('Helvetica-Bold', 17); c.drawString(pad, h*0.50, self.agency)
        c.setFillColor(MUTED); c.setFont('Helvetica', 8)
        c.drawString(pad, h*0.24, 'INTERNAL DOCUMENT — NOT FOR CLIENT DISTRIBUTION')
        c.setFillColor(GOLD); c.setFont('Helvetica-Bold', 9.5); c.drawRightString(w-pad, h*0.50, 'COST BREAKDOWN')

# ── Page templates ────────────────────────────────────────────────────────────
def make_page_template(agency, email, date):
    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            bh = 11*mm; by = PAGE_H - bh
            canvas.setFillColor(NAVY); canvas.rect(0, by, PAGE_W, bh, fill=1, stroke=0)
            canvas.setFillColor(GOLD); canvas.rect(0, by, PAGE_W, 1.5, fill=1, stroke=0)
            ty = by + bh * 0.38
            canvas.setFillColor(white); canvas.setFont('Helvetica-Bold', 7.5); canvas.drawString(ML, ty, agency.upper())
            canvas.setFillColor(NAVY_MUTED); canvas.setFont('Helvetica', 7)
            canvas.drawCentredString(PAGE_W/2, ty, f"{agency}  ·  {email}  ·  Prepared {date}")
            canvas.setFillColor(GOLD); canvas.setFont('Helvetica-Bold', 7.5); canvas.drawRightString(PAGE_W-MR, ty, 'SAFARI QUOTE')
        canvas.setStrokeColor(RULE_CLR); canvas.setLineWidth(0.3)
        canvas.line(ML, MB-4*mm, PAGE_W-MR, MB-4*mm)
        canvas.setFont('Helvetica', 7); canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W/2, MB-8*mm, f"{agency}  ·  {email}  ·  Page {doc.page}")
        canvas.restoreState()
    return on_page

def make_internal_page_template(agency, date):
    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            bh = 11*mm; by = PAGE_H - bh
            canvas.setFillColor(EARTH); canvas.rect(0, by, PAGE_W, bh, fill=1, stroke=0)
            canvas.setFillColor(GOLD); canvas.rect(0, by, PAGE_W, 1.5, fill=1, stroke=0)
            ty = by + bh * 0.38
            canvas.setFillColor(white); canvas.setFont('Helvetica-Bold', 7.5); canvas.drawString(ML, ty, agency.upper())
            canvas.setFillColor(MUTED); canvas.setFont('Helvetica', 7)
            canvas.drawCentredString(PAGE_W/2, ty, 'INTERNAL — NOT FOR CLIENT DISTRIBUTION')
            canvas.setFillColor(GOLD); canvas.setFont('Helvetica-Bold', 7.5); canvas.drawRightString(PAGE_W-MR, ty, 'COST BREAKDOWN')
        canvas.setStrokeColor(RULE_CLR); canvas.setLineWidth(0.3)
        canvas.line(ML, MB-4*mm, PAGE_W-MR, MB-4*mm)
        canvas.setFont('Helvetica', 7); canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W/2, MB-8*mm, f"{agency}  ·  INTERNAL  ·  Page {doc.page}")
        canvas.restoreState()
    return on_page

# ── Quote sections ────────────────────────────────────────────────────────────
def build_page1(data, S, story):
    agent = data.get('agent', {}); client = data.get('client', {})
    trip = data.get('trip', {}); profile = data.get('agent_profile', {})
    agency = safe(agent.get('agency'), 'Safari Agency')
    agent_name = safe(agent.get('name')); agent_email = safe(agent.get('email'))
    tagline = safe(profile.get('tagline'), 'Travel & Safari Specialists')
    quote_id = safe(data.get('quote_id'), 'SF-0001'); gen_date = safe(data.get('generated_at'))
    client_name = safe(client.get('name')); nationality = safe(client.get('nationality'), '')
    pax_adults = safe(client.get('pax_adults'), '2'); pax_kids = safe(client.get('pax_children'), '0')
    pax_str = f"{pax_adults} Adults" + (f", {pax_kids} Children" if pax_kids not in ('0','—') else '')
    start = safe(trip.get('start_date')); end = safe(trip.get('end_date'))
    nights = safe(trip.get('duration_nights')); dests = safe(trip.get('destinations'))

    story.append(HeaderBand(agency, tagline)); story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f"{agency}  ·  {agent_email}  ·  Prepared {gen_date}", S['muted'])); story.append(Spacer(1, 4*mm))

    dest_line = '  ·  '.join([f"✈ {d.strip()}" for d in dests.split(',')]) if dests != '—' else ''
    left_t = Table([[Paragraph('Safari Proposal prepared for', S['muted'])], [Paragraph(client_name, S['client_name'])], [Spacer(1,2)], [Paragraph(dest_line, S['client_tag'])]], colWidths=[CW*0.52])
    left_t.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),('VALIGN',(0,0),(-1,-1),'TOP')]))
    right_t = Table([[Paragraph('QUOTE NUMBER',S['meta_lbl']),Paragraph('VALID UNTIL',S['meta_lbl'])],[Paragraph(f'<b>{quote_id}</b>',S['meta_bold']),Paragraph('14 days from issue',S['meta_val'])],[Spacer(1,4),Spacer(1,4)],[Paragraph('PREPARED BY',S['meta_lbl']),Paragraph('QUOTE DATE',S['meta_lbl'])],[Paragraph(agent_name,S['meta_val']),Paragraph(gen_date,S['meta_val'])]], colWidths=[CW*0.25,CW*0.23])
    right_t.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),('VALIGN',(0,0),(-1,-1),'TOP')]))
    hero = Table([[left_t, right_t]], colWidths=[CW*0.52, CW*0.48])
    hero.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('BOX',(0,0),(-1,-1),0.4,RULE_CLR),('BACKGROUND',(0,0),(-1,-1),SAND),('LINEAFTER',(0,0),(0,-1),0.4,RULE_CLR)]))
    story.append(hero); story.append(Spacer(1, 4*mm))

    col = CW/4
    mt = Table([[Paragraph('TRAVEL DATES',S['meta_lbl']),Paragraph('TRAVELERS',S['meta_lbl']),Paragraph('DURATION',S['meta_lbl']),Paragraph('',S['meta_lbl'])],[Paragraph(f"{start} – {end}",S['meta_val']),Paragraph(pax_str,S['meta_val']),Paragraph(f"{nights} Days",S['meta_val']),Paragraph('',S['meta_val'])]], colWidths=[col,col,col,col])
    mt.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),8),('BACKGROUND',(0,0),(-1,-1),SAND),('BOX',(0,0),(-1,-1),0.4,RULE_CLR),('INNERGRID',(0,0),(-1,-1),0.3,RULE_CLR)]))
    story.append(mt); story.append(Spacer(1, 4*mm))

    story.append(Paragraph('CLIENT INFORMATION', S['section'])); story.append(hr())
    ci = Table([[Paragraph('Name',S['meta_lbl']),Paragraph('Email',S['meta_lbl']),Paragraph('Nationality',S['meta_lbl'])],[Paragraph(client_name,S['meta_val']),Paragraph(safe(client.get('email')),S['meta_val']),Paragraph(nationality,S['meta_val'])]], colWidths=[CW/3,CW/3,CW/3])
    ci.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),0)]))
    story.append(ci); story.append(Spacer(1, 3*mm))

    story.append(Paragraph('YOUR TRAVEL SPECIALIST', S['section'])); story.append(hr())
    ts = Table([[Paragraph('Agent',S['meta_lbl']),Paragraph('Email',S['meta_lbl']),Paragraph('Agency',S['meta_lbl'])],[Paragraph(agent_name,S['meta_val']),Paragraph(agent_email,S['meta_val']),Paragraph(agency,S['meta_val'])]], colWidths=[CW/3,CW/3,CW/3])
    ts.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),0)]))
    story.append(ts); story.append(Spacer(1, 4*mm))

def build_overview(data, S, story):
    intro = safe(data.get('narrative', {}).get('intro'), '')
    if not intro or intro == '—': return
    story.append(Paragraph('YOUR SAFARI OVERVIEW', S['section'])); story.append(hr())
    story.append(Spacer(1, 2*mm)); story.append(Paragraph(intro, S['italic'])); story.append(Spacer(1, 4*mm))

def build_itinerary(data, S, story):
    import io as _io
    itinerary = data.get('itinerary', []); narr_days = data.get('narrative', {}).get('days', [])
    photo_cache = data.get('photo_cache', {}); narr_idx = {}
    for d in narr_days:
        try: narr_idx[int(d.get('day_number', 0))] = d
        except: pass
    story.append(Paragraph('YOUR DAY-BY-DAY ITINERARY', S['section'])); story.append(hr()); story.append(Spacer(1, 3*mm))
    for day in itinerary:
        try: num = int(day.get('day_number', 0))
        except: num = 0
        narr = narr_idx.get(num, {}); dest = safe(day.get('destination'))
        title = safe(day.get('title'), dest); img_query = safe(day.get('image_search_query'), f"{dest} safari")
        narr_text = safe(narr.get('narrative'), ''); highlight = safe(narr.get('highlight'), '')
        accom = safe(day.get('accommodation_name')); accom_desc = safe(narr.get('accommodation_description'), '')
        room = safe(day.get('room_type')); meals = safe(day.get('meal_plan')); transport = safe(day.get('transport_description'), '')
        elems = []
        photo_bytes = photo_cache.get(img_query)
        if photo_bytes:
            try:
                from reportlab.platypus import Image as RLImage
                elems.append(RLImage(_io.BytesIO(photo_bytes), width=CW, height=42*mm)); elems.append(Spacer(1, 2*mm))
            except:
                elems.append(DestinationBar(dest)); elems.append(Spacer(1, 2*mm))
        else:
            elems.append(DestinationBar(dest)); elems.append(Spacer(1, 2*mm))
        dh = Table([[Paragraph(f"DAY {num}", S['day_num']), Paragraph(dest, S['day_dest'])]], colWidths=[CW*0.5, CW*0.5])
        dh.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        elems.append(dh); elems.append(Paragraph(title, S['day_title'])); elems.append(Spacer(1, 2*mm))
        if narr_text and narr_text != '—': elems.append(Paragraph(narr_text, S['body'])); elems.append(Spacer(1, 2*mm))
        if highlight and highlight != '—': elems.append(Paragraph(f"■  {highlight}", S['highlight'])); elems.append(Spacer(1, 2*mm))
        accom_full = f"{accom} — {accom_desc}" if accom_desc != '—' else accom
        elems.append(Paragraph(f"<b>Accommodation:</b> {accom_full}, {room}  |  <b>Meals:</b> {meals}", S['body_sm']))
        if transport and transport not in ('—','null','None'): elems.append(Paragraph(f"<b>Transfer:</b> {transport}", S['body_sm']))
        elems.append(Spacer(1, 3*mm)); elems.append(hr(color=RULE_CLR, thickness=0.3, sb=0, sa=4))
        story.append(KeepTogether(elems))

def build_pricing(data, S, story):
    """Client-facing only — NO cost data."""
    line_items = data.get('line_items', []); pricing = data.get('pricing', {})
    story.append(PageBreak()); story.append(Paragraph('INVESTMENT BREAKDOWN', S['section'])); story.append(hr()); story.append(Spacer(1, 3*mm))
    if line_items:
        rows = [[Paragraph('DESCRIPTION',S['th']),Paragraph('DETAILS',S['th']),Paragraph('QTY',S['th']),Paragraph('UNIT PRICE',S['th']),Paragraph('TOTAL',S['th'])]]
        for item in line_items:
            rows.append([Paragraph(safe(item.get('description')),S['td']),Paragraph(safe(item.get('details')),S['td']),Paragraph(str(safe(item.get('quantity'))),S['td']),Paragraph(usd(item.get('unit_price')),S['td_r']),Paragraph(usd(item.get('total_price')),S['td_r'])])
        t = Table(rows, colWidths=[58*mm,52*mm,10*mm,27*mm,27*mm], repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),EARTH),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,TABLE_ALT]),('ALIGN',(3,0),(-1,-1),'RIGHT'),('ALIGN',(0,0),(2,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),0.25,RULE_CLR)]))
        story.append(t)
    story.append(Spacer(1, 5*mm))
    totals = [[Paragraph('TOTAL INVESTMENT',S['total_lbl']),Paragraph(usd(pricing.get('total_price_usd')),S['total_val'])],[Paragraph('DEPOSIT REQUIRED (30%)',S['total_lbl']),Paragraph(usd(pricing.get('deposit_amount_usd')),S['td_r'])],[Paragraph('BALANCE DUE',S['total_lbl']),Paragraph(usd(pricing.get('balance_amount_usd')),S['td_r'])]]
    tt = Table(totals, colWidths=[CW-50*mm, 50*mm])
    tt.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEABOVE',(0,0),(-1,0),0.5,GOLD),('LINEBELOW',(0,2),(-1,2),0.5,GOLD),('BACKGROUND',(0,0),(-1,0),SAND)]))
    story.append(tt)
    notes = safe(pricing.get('budget_notes'), '')
    if notes and notes != '—': story.append(Spacer(1, 3*mm)); story.append(Paragraph(f"Note: {notes}", S['muted']))
    story.append(Spacer(1, 6*mm))

def build_inclusions_terms(data, S, story):
    inclusions = safe(data.get('inclusions'), ''); exclusions = safe(data.get('exclusions'), '')
    terms = safe(data.get('terms'), ''); accept_url = safe(data.get('accept_url'), '#'); changes_url = safe(data.get('changes_url'), '#')
    INCL_BG = HexColor('#F0FAF0'); EXCL_BG = HexColor('#FFF5F5'); col_w = (CW-6*mm)/2
    left_elems = []; right_elems = []
    if inclusions and inclusions != '—':
        left_elems += [Spacer(1,2*mm), Paragraph('INCLUDED IN THIS PACKAGE',S['section']), hr(width=col_w-8*mm,color=HexColor('#4A9E4A'))]
        for line in inclusions.split('\n'):
            line = line.strip().lstrip('-•✓').strip()
            if line: left_elems.append(Paragraph(f'<font color="#2D6B2D">✓</font>  {line}', S['body_sm']))
        left_elems.append(Spacer(1,2*mm))
    if exclusions and exclusions != '—':
        right_elems += [Spacer(1,2*mm), Paragraph('NOT INCLUDED',S['section']), hr(width=col_w-8*mm,color=HexColor('#C94040'))]
        for line in exclusions.split('\n'):
            line = line.strip().lstrip('-•✕✗').strip()
            if line: right_elems.append(Paragraph(f'<font color="#B03030">✕</font>  {line}', S['body_sm']))
        right_elems.append(Spacer(1,2*mm))
    if left_elems or right_elems:
        inc_t = Table([[left_elems, right_elems]], colWidths=[col_w, col_w])
        inc_t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('BACKGROUND',(0,0),(0,-1),INCL_BG),('BACKGROUND',(1,0),(1,-1),EXCL_BG),('BOX',(0,0),(0,-1),0.3,HexColor('#4A9E4A')),('BOX',(1,0),(1,-1),0.3,HexColor('#C94040'))]))
        story.append(inc_t)
    if terms and terms != '—': story.append(Spacer(1,3*mm)); story.append(Paragraph('NOTES & CONDITIONS',S['section'])); story.append(hr()); story.append(Paragraph(terms,S['muted']))
    story.append(Spacer(1,5*mm)); story.append(Paragraph('RESPOND TO THIS QUOTE',S['section'])); story.append(hr(color=GOLD,thickness=0.6)); story.append(Spacer(1,2*mm))
    rt = Table([[Paragraph('■ <b>ACCEPT THIS QUOTE</b>',S['body_sm']),Paragraph(accept_url,S['muted']),Paragraph('✏ <b>REQUEST CHANGES</b>',S['body_sm']),Paragraph(changes_url,S['muted'])]], colWidths=[35*mm,CW/2-35*mm,35*mm,CW/2-35*mm])
    rt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(rt)

def build_trust_page(data, S, story):
    agent = data.get('agent', {}); profile = data.get('agent_profile', {}); reviews = data.get('agent_reviews', [])
    agency = safe(agent.get('agency'), 'Safari Agency'); tagline = safe(profile.get('tagline'), 'Travel & Safari Specialists')
    bio = safe(profile.get('bio'), ''); years_exp = safe(profile.get('years_experience'), '10+')
    safaris = safe(profile.get('safaris_planned'), '500+'); countries = safe(profile.get('countries_covered'), '15')
    awards = profile.get('awards', []); memberships = profile.get('memberships', [])
    email = safe(agent.get('email')); phone = safe(agent.get('phone')); website = safe(agent.get('website'), '')
    address = safe(profile.get('address'), ''); facebook = safe(profile.get('facebook'), '')
    instagram = safe(profile.get('instagram'), ''); linkedin = safe(profile.get('linkedin'), '')

    story.append(PageBreak()); story.append(HeaderBand(agency, tagline)); story.append(Spacer(1, 5*mm))
    story.append(Table([[Paragraph(agency.upper(),S['agent_name']),Paragraph(tagline.upper(),S['agent_tag'])]], colWidths=[CW*0.6,CW*0.4])); story.append(Spacer(1,2*mm))
    if bio and bio != '—': story.append(Paragraph(bio, S['agent_bio']))
    story.append(Spacer(1,4*mm)); story.append(hr(color=GOLD,thickness=0.5)); story.append(Spacer(1,4*mm))

    sc = CW/3
    stats = Table([[[Paragraph('■',S['stat_num']),Paragraph(years_exp,S['stat_num']),Paragraph('Years Experience',S['stat_lbl'])],[Paragraph('■',S['stat_num']),Paragraph(safaris,S['stat_num']),Paragraph('Safaris Planned',S['stat_lbl'])],[Paragraph('■',S['stat_num']),Paragraph(countries,S['stat_num']),Paragraph('Countries Covered',S['stat_lbl'])]]], colWidths=[sc,sc,sc])
    stats.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('BACKGROUND',(0,0),(-1,-1),SAND),('BOX',(0,0),(-1,-1),0.3,RULE_CLR),('INNERGRID',(0,0),(-1,-1),0.3,RULE_CLR)]))
    story.append(stats); story.append(Spacer(1,5*mm))

    cw2 = (CW-6*mm)/2; le = []; re = []
    if awards: le += [Paragraph('AWARDS & RECOGNITION',S['section']),hr(width=cw2)] + [Paragraph(f"■  {safe(a)}",S['award']) for a in awards] + [Spacer(1,3*mm)]
    if memberships: re += [Paragraph('MEMBERSHIPS & ACCREDITATIONS',S['section']),hr(width=cw2)] + [Paragraph(f"✓  {safe(m)}",S['award']) for m in memberships] + [Spacer(1,3*mm)]
    if le or re:
        am = Table([[le,re]], colWidths=[cw2,cw2])
        am.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0)]))
        story.append(am)
    story.append(Spacer(1,4*mm))

    if reviews:
        story.append(Paragraph('WHAT OUR CLIENTS SAY',S['section'])); story.append(hr(color=GOLD,thickness=0.5)); story.append(Spacer(1,3*mm))
        rl = list(reviews[:3])
        while len(rl) < 3: rl.append({})
        cells = []
        for rev in rl:
            cells.append([Paragraph('★★★★★',ParagraphStyle('stars',fontName='Helvetica',fontSize=11,textColor=GOLD_STAR,leading=14)),Spacer(1,2*mm),Paragraph(f'"{safe(rev.get("review_text",""))}"',S['review_body']),Spacer(1,3*mm),Paragraph(f"— {safe(rev.get('client_name',''))}",S['review_author']),Paragraph(f"{safe(rev.get('client_origin',''))}  ·  {safe(rev.get('trip_summary',''))}",S['review_origin'])])
        cwr = (CW-4*mm)/3
        rt = Table([cells], colWidths=[cwr,cwr,cwr])
        rt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),REVIEW_BG),('BOX',(0,0),(0,-1),0.3,RULE_CLR),('BOX',(1,0),(1,-1),0.3,RULE_CLR),('BOX',(2,0),(2,-1),0.3,RULE_CLR),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8)]))
        story.append(rt); story.append(Spacer(1,5*mm))

    story.append(Paragraph('GET IN TOUCH',S['section'])); story.append(hr(color=GOLD,thickness=0.5)); story.append(Spacer(1,2*mm))
    ci = []
    if email    != '—': ci.append(f"✉  {email}")
    if phone    != '—': ci.append(f"☏  {phone}")
    if website  != '—': ci.append(f"🌐  {website}")
    if address  != '—': ci.append(f"📍  {address}")
    if facebook != '—': ci.append(f"Facebook: {facebook}")
    if instagram!= '—': ci.append(f"Instagram: {instagram}")
    if linkedin != '—': ci.append(f"LinkedIn: {linkedin}")
    mid = (len(ci)+1)//2
    ct = Table([[[Paragraph(i,S['contact']) for i in ci[:mid]],[Paragraph(i,S['contact']) for i in ci[mid:]]]], colWidths=[(CW-6*mm)/2,(CW-6*mm)/2])
    ct.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0)]))
    story.append(ct)

# ── Main: client-facing quote PDF ─────────────────────────────────────────────
def generate_quote_pdf(data: dict, output_path: str):
    S = make_styles()
    agency = safe(data.get('agent', {}).get('agency'), 'SafariFlow')
    email  = safe(data.get('agent', {}).get('email'), '')
    date   = safe(data.get('generated_at'), '')
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                            title=f"Safari Quote — {safe(data.get('client',{}).get('name',''))}", author=agency)
    story = []
    build_page1(data, S, story); build_overview(data, S, story); build_itinerary(data, S, story)
    build_pricing(data, S, story); build_inclusions_terms(data, S, story); build_trust_page(data, S, story)
    doc.build(story, onFirstPage=make_page_template(agency, email, date), onLaterPages=make_page_template(agency, email, date))

# ── Internal: agent cost breakdown PDF ────────────────────────────────────────
def generate_cost_breakdown_pdf(data: dict, output_path: str):
    """
    Internal agent document. Format:
      - Dark header band (INTERNAL — NOT FOR CLIENT DISTRIBUTION)
      - Quote/client meta strip
      - Investment Breakdown (sell prices)
      - Agent Cost Breakdown (cost, sell, markup %, profit)
      - Profit summary box
    No itinerary, no overview, no trust page. Never sent to clients.
    """
    S = make_styles()
    agent = data.get('agent', {}); client = data.get('client', {})
    trip = data.get('trip', {}); line_items = data.get('line_items', []); pricing = data.get('pricing', {})
    agency = safe(agent.get('agency'), 'SafariFlow')
    agent_name = safe(agent.get('name')); agent_email = safe(agent.get('email'))
    quote_id = safe(data.get('quote_id'), 'SF-0001'); gen_date = safe(data.get('generated_at'))
    client_name = safe(client.get('name'))
    pax_adults = safe(client.get('pax_adults'), '2'); pax_kids = safe(client.get('pax_children'), '0')
    pax_str = f"{pax_adults} Adults" + (f", {pax_kids} Children" if pax_kids not in ('0','—') else '')
    start = safe(trip.get('start_date')); end = safe(trip.get('end_date')); dests = safe(trip.get('destinations'))

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                            title=f"Cost Breakdown — {quote_id}", author=agency)
    story = []

    # Header
    story.append(InternalHeaderBand(agency)); story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f"{agency}  ·  {agent_name}  ·  {agent_email}  ·  {gen_date}", S['muted']))
    story.append(Spacer(1, 5*mm))

    # Meta strip
    col = CW/4
    mt = Table([[Paragraph('QUOTE NUMBER',S['meta_lbl']),Paragraph('CLIENT',S['meta_lbl']),Paragraph('DESTINATIONS',S['meta_lbl']),Paragraph('TRAVEL DATES',S['meta_lbl'])],[Paragraph(f'<b>{quote_id}</b>',S['meta_bold']),Paragraph(client_name,S['meta_val']),Paragraph(dests,S['meta_val']),Paragraph(f"{start} – {end}",S['meta_val'])]], colWidths=[col,col,col,col])
    mt.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),8),('BACKGROUND',(0,0),(-1,-1),SAND),('BOX',(0,0),(-1,-1),0.4,RULE_CLR),('INNERGRID',(0,0),(-1,-1),0.3,RULE_CLR)]))
    story.append(mt); story.append(Spacer(1, 6*mm))

    # Investment breakdown (sell prices)
    story.append(Paragraph('INVESTMENT BREAKDOWN', S['section'])); story.append(hr()); story.append(Spacer(1, 3*mm))
    if line_items:
        rows = [[Paragraph('DESCRIPTION',S['th']),Paragraph('DETAILS',S['th']),Paragraph('QTY',S['th']),Paragraph('UNIT PRICE',S['th']),Paragraph('TOTAL',S['th'])]]
        for item in line_items:
            rows.append([Paragraph(safe(item.get('description')),S['td']),Paragraph(safe(item.get('details')),S['td']),Paragraph(str(safe(item.get('quantity'))),S['td']),Paragraph(usd(item.get('unit_price')),S['td_r']),Paragraph(usd(item.get('total_price')),S['td_r'])])
        t = Table(rows, colWidths=[58*mm,52*mm,10*mm,27*mm,27*mm], repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),EARTH),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,TABLE_ALT]),('ALIGN',(3,0),(-1,-1),'RIGHT'),('ALIGN',(0,0),(2,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),0.25,RULE_CLR)]))
        story.append(t)
    story.append(Spacer(1, 4*mm))
    totals = [[Paragraph('TOTAL INVESTMENT',S['total_lbl']),Paragraph(usd(pricing.get('total_price_usd')),S['total_val'])],[Paragraph('DEPOSIT REQUIRED (30%)',S['total_lbl']),Paragraph(usd(pricing.get('deposit_amount_usd')),S['td_r'])],[Paragraph('BALANCE DUE',S['total_lbl']),Paragraph(usd(pricing.get('balance_amount_usd')),S['td_r'])]]
    tt = Table(totals, colWidths=[CW-50*mm, 50*mm])
    tt.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEABOVE',(0,0),(-1,0),0.5,GOLD),('LINEBELOW',(0,2),(-1,2),0.5,GOLD),('BACKGROUND',(0,0),(-1,0),SAND)]))
    story.append(tt); story.append(Spacer(1, 8*mm))

    # Agent cost breakdown
    story.append(Paragraph('AGENT COST BREAKDOWN', S['section'])); story.append(hr(color=GOLD, thickness=0.6)); story.append(Spacer(1, 3*mm))
    cost_rows = [[Paragraph('DESCRIPTION',S['th']),Paragraph('COST',S['th']),Paragraph('SELL',S['th']),Paragraph('MARKUP %',S['th']),Paragraph('PROFIT',S['th'])]]
    total_cost = 0.0; total_sell = 0.0; total_profit = 0.0
    for item in line_items:
        cost   = float(item.get('cost_total_price', item.get('total_price', 0)) or 0)
        sell   = float(item.get('total_price', 0) or 0)
        markup = float(item.get('markup_pct', 0) or 0)
        profit = float(item.get('profit', sell - cost) or 0)
        total_cost += cost; total_sell += sell; total_profit += profit
        ps = ParagraphStyle('pc', fontName='Helvetica-Bold', fontSize=8.5, textColor=PROFIT_GRN if profit >= 0 else PROFIT_RED, leading=12, alignment=TA_RIGHT)
        cost_rows.append([Paragraph(safe(item.get('description')),S['td']),Paragraph(usd(cost),S['td_r']),Paragraph(usd(sell),S['td_r']),Paragraph(f"{markup:.1f}%",S['td_r']),Paragraph(usd(profit),ps)])
    margin = (total_profit / total_sell * 100) if total_sell > 0 else 0
    cost_rows.append([
        Paragraph('TOTALS', ParagraphStyle('ctl',fontName='Helvetica-Bold',fontSize=8.5,textColor=white,leading=11)),
        Paragraph(usd(total_cost), ParagraphStyle('ctv',fontName='Helvetica-Bold',fontSize=8.5,textColor=white,leading=11,alignment=TA_RIGHT)),
        Paragraph(usd(total_sell), ParagraphStyle('ctv2',fontName='Helvetica-Bold',fontSize=8.5,textColor=white,leading=11,alignment=TA_RIGHT)),
        Paragraph(f"{margin:.1f}%", ParagraphStyle('ctm',fontName='Helvetica-Bold',fontSize=8.5,textColor=GOLD,leading=11,alignment=TA_RIGHT)),
        Paragraph(usd(total_profit), ParagraphStyle('ctp',fontName='Helvetica-Bold',fontSize=8.5,textColor=PROFIT_LGT,leading=11,alignment=TA_RIGHT)),
    ])
    ct = Table(cost_rows, colWidths=[68*mm,28*mm,28*mm,22*mm,28*mm], repeatRows=1)
    ct.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-2),[white,TABLE_ALT]),('BACKGROUND',(0,-1),(-1,-1),EARTH),('ALIGN',(1,0),(-1,-1),'RIGHT'),('ALIGN',(0,0),(0,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-2),0.25,RULE_CLR),('LINEABOVE',(0,-1),(-1,-1),0.5,GOLD)]))
    story.append(ct); story.append(Spacer(1, 5*mm))

    # Profit summary box
    summary = Table([[
        Paragraph('TOTAL COST', S['total_lbl']), Paragraph(usd(total_cost), S['td_r']), Spacer(6*mm,1),
        Paragraph('TOTAL REVENUE', S['total_lbl']), Paragraph(usd(total_sell), S['td_r']), Spacer(6*mm,1),
        Paragraph('TOTAL PROFIT', ParagraphStyle('pl',fontName='Helvetica-Bold',fontSize=9,textColor=PROFIT_GRN,leading=12,alignment=TA_RIGHT)),
        Paragraph(usd(total_profit), ParagraphStyle('pv',fontName='Helvetica-Bold',fontSize=16,textColor=PROFIT_GRN,leading=20,alignment=TA_RIGHT)), Spacer(6*mm,1),
        Paragraph('MARGIN', ParagraphStyle('ml',fontName='Helvetica-Bold',fontSize=9,textColor=GOLD,leading=12,alignment=TA_RIGHT)),
        Paragraph(f"{margin:.1f}%", ParagraphStyle('mv',fontName='Helvetica-Bold',fontSize=16,textColor=GOLD,leading=20,alignment=TA_RIGHT)),
    ]], colWidths=[28*mm,20*mm,6*mm,28*mm,20*mm,6*mm,28*mm,22*mm,6*mm,18*mm,18*mm])
    summary.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('BACKGROUND',(0,0),(-1,-1),SAND),('BOX',(0,0),(-1,-1),0.8,GOLD)]))
    story.append(summary)

    doc.build(story, onFirstPage=make_internal_page_template(agency, gen_date), onLaterPages=make_internal_page_template(agency, gen_date))

# ── Invoice PDF ───────────────────────────────────────────────────────────────
def generate_invoice_pdf(data, output_path):
    import datetime
    agent = data.get('agent', {}); client = data.get('client', {}); invoice = data.get('invoice', {}); line_items = data.get('line_items', [])
    agency = safe(agent.get('agency'), 'SafariFlow'); agent_email = safe(agent.get('email')); agent_phone = safe(agent.get('phone'))
    brand_primary = agent.get('brand_color_primary', '#2E4A7A'); brand_secondary = agent.get('brand_color_secondary', '#C4922A')
    cancel_terms = agent.get('cancellation_terms', ''); amendment_terms = agent.get('amendment_terms', '')
    try: BRAND = HexColor(brand_primary); ACCENT = HexColor(brand_secondary)
    except: BRAND = NAVY; ACCENT = GOLD
    inv_number = safe(invoice.get('invoice_number'), 'INV-0001'); inv_date = safe(invoice.get('issued_at', str(datetime.date.today()))[:10])
    quote_ref = safe(invoice.get('quote_id')); total = invoice.get('total_usd_cents', 0)/100
    deposit = invoice.get('deposit_usd_cents', 0)/100; balance = invoice.get('balance_usd_cents', 0)/100
    deposit_due = safe(invoice.get('deposit_due_date', '')); balance_due = safe(invoice.get('balance_due_date', ''))
    bank_details = safe(agent.get('bank_details', ''))
    client_name = safe(client.get('name')); client_email = safe(client.get('email')); client_phone = safe(client.get('phone'))
    start_date = safe(invoice.get('start_date', '')); end_date = safe(invoice.get('end_date', ''))
    destinations = safe(invoice.get('destinations', '')); pax_adults = invoice.get('pax_adults', 2); pax_children = invoice.get('pax_children', 0)
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=ML, rightMargin=MR, topMargin=18*mm, bottomMargin=18*mm, title=f"Invoice {inv_number}", author=agency)
    story = []
    hd = Table([[Paragraph(f"<b>{agency}</b>", ParagraphStyle('ia',fontName='Helvetica-Bold',fontSize=20,textColor=white,leading=24)),Paragraph(f"{agent_email}<br/>{agent_phone}",ParagraphStyle('ic',fontName='Helvetica',fontSize=9,textColor=HexColor('#CCCCCC'),leading=13))]], colWidths=[CW*0.6,CW*0.4])
    hd.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BRAND),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,-1),16),('BOTTOMPADDING',(0,0),(-1,-1),16),('ALIGN',(1,0),(1,0),'RIGHT')]))
    story.append(hd)
    story.append(Table([['']], colWidths=[CW], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),ACCENT),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)])))
    story.append(Spacer(1,6*mm))
    ttl = Table([[Paragraph('INVOICE',ParagraphStyle('it',fontName='Helvetica-Bold',fontSize=28,textColor=BRAND,leading=32)),Paragraph(f"<b>{inv_number}</b><br/><font size=9 color='#666666'>Date: {inv_date}</font><br/><font size=9 color='#666666'>Quote Ref: {quote_ref}</font>",ParagraphStyle('im',fontName='Helvetica',fontSize=11,textColor=EARTH,leading=16,alignment=TA_RIGHT))]], colWidths=[CW*0.5,CW*0.5])
    ttl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'BOTTOM'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(ttl); story.append(Spacer(1,6*mm))
    pax_str = f"{pax_adults} Adult{'s' if pax_adults>1 else ''}" + (f", {pax_children} Child{'ren' if pax_children>1 else ''}" if pax_children else '')
    dt = Table([[
        Table([[Paragraph('BILL TO',ParagraphStyle('bs',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))],[Paragraph(f"<b>{client_name}</b>",ParagraphStyle('bc',fontName='Helvetica-Bold',fontSize=13,textColor=EARTH,leading=16))],[Paragraph(client_email,ParagraphStyle('be',fontName='Helvetica',fontSize=9,textColor=MUTED,leading=12))],[Paragraph(client_phone,ParagraphStyle('bp',fontName='Helvetica',fontSize=9,textColor=MUTED,leading=12))]], colWidths=[CW*0.45], style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)])),
        Table([[Paragraph('SAFARI DETAILS',ParagraphStyle('sd',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))],[Paragraph(f"<b>{destinations}</b>",ParagraphStyle('dd',fontName='Helvetica-Bold',fontSize=11,textColor=BRAND,leading=14))],[Paragraph(f"{start_date} → {end_date}",ParagraphStyle('dt2',fontName='Helvetica',fontSize=9,textColor=MUTED,leading=12))],[Paragraph(pax_str,ParagraphStyle('dp',fontName='Helvetica',fontSize=9,textColor=MUTED,leading=12))]], colWidths=[CW*0.45], style=TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)])),
    ]], colWidths=[CW*0.5,CW*0.5])
    dt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(dt); story.append(Spacer(1,6*mm)); story.append(HRFlowable(width=CW,thickness=1,color=HexColor('#E8E4DE'))); story.append(Spacer(1,5*mm))
    story.append(Paragraph('SERVICES',ParagraphStyle('sv',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))); story.append(Spacer(1,3*mm))
    li_data = [['Description','Details','Qty','Unit Price','Total']]
    for item in line_items: li_data.append([item.get('description',''),item.get('details',''),str(item.get('quantity',1)),f"${item.get('unit_price',0):,.2f}",f"${item.get('total_price',0):,.2f}"])
    li_data += [['','','','SUBTOTAL',f"${total:,.2f}"],['','','','TOTAL DUE',f"${total:,.2f}"]]
    li = Table(li_data, colWidths=[CW*0.30,CW*0.28,CW*0.08,CW*0.16,CW*0.18], repeatRows=1)
    li.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BRAND),('TEXTCOLOR',(0,0),(-1,0),white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ALIGN',(2,0),(-1,-1),'RIGHT'),('FONTNAME',(0,1),(-1,-3),'Helvetica'),('ROWBACKGROUNDS',(0,1),(-1,-3),[white,TABLE_ALT]),('GRID',(0,0),(-1,-3),0.5,HexColor('#E8E4DE')),('FONTNAME',(0,-2),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,-2),(-1,-1),10),('LINEABOVE',(0,-2),(-1,-2),1,HexColor('#CCCCCC')),('BACKGROUND',(0,-1),(-1,-1),HexColor('#F8F6F2')),('TEXTCOLOR',(3,-1),(-1,-1),ACCENT)]))
    story.append(li); story.append(Spacer(1,6*mm))
    story.append(Paragraph('PAYMENT SCHEDULE',ParagraphStyle('ps',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))); story.append(Spacer(1,3*mm))
    pd_data = [['Payment','Amount','Due Date','Status'],['Deposit (confirmation)',f"${deposit:,.2f}",deposit_due,'DUE'],['Balance',f"${balance:,.2f}",balance_due,'DUE']]
    pt = Table(pd_data, colWidths=[CW*0.35,CW*0.20,CW*0.25,CW*0.20])
    pt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BRAND),('TEXTCOLOR',(0,0),(-1,0),white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('ALIGN',(1,0),(-1,-1),'RIGHT'),('GRID',(0,0),(-1,-1),0.5,HexColor('#E8E4DE')),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,TABLE_ALT]),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('TEXTCOLOR',(3,1),(3,-1),ACCENT),('FONTNAME',(3,1),(3,-1),'Helvetica-Bold')]))
    story.append(pt); story.append(Spacer(1,6*mm))
    if bank_details and bank_details != '—':
        story.append(Paragraph('PAYMENT INSTRUCTIONS',ParagraphStyle('pi',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))); story.append(Spacer(1,3*mm))
        pi = Table([[Paragraph(bank_details.replace('\n','<br/>'),ParagraphStyle('pb',fontName='Helvetica',fontSize=9,textColor=EARTH,leading=14))]], colWidths=[CW])
        pi.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor('#F8F6F2')),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),('BOX',(0,0),(-1,-1),1,HexColor('#E8E4DE'))]))
        story.append(pi); story.append(Spacer(1,4*mm))
    if cancel_terms:
        story.append(HRFlowable(width=CW,thickness=0.5,color=HexColor('#E8E4DE'))); story.append(Spacer(1,4*mm))
        story.append(Paragraph('CANCELLATION TERMS',ParagraphStyle('ct',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))); story.append(Spacer(1,2*mm))
        story.append(Paragraph(cancel_terms.replace('\n','<br/>'),ParagraphStyle('ctt',fontName='Helvetica',fontSize=8,textColor=MUTED,leading=12))); story.append(Spacer(1,3*mm))
    if amendment_terms:
        story.append(Paragraph('AMENDMENT TERMS',ParagraphStyle('at',fontName='Helvetica-Bold',fontSize=9,textColor=HexColor('#999999'),leading=12))); story.append(Spacer(1,2*mm))
        story.append(Paragraph(amendment_terms.replace('\n','<br/>'),ParagraphStyle('att',fontName='Helvetica',fontSize=8,textColor=MUTED,leading=12))); story.append(Spacer(1,4*mm))
    ft = Table([[Paragraph(f"<b>{agency}</b> · {agent_email} · {agent_phone}",ParagraphStyle('if',fontName='Helvetica',fontSize=8,textColor=white,alignment=TA_CENTER))]], colWidths=[CW])
    ft.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BRAND),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story.append(ft)
    doc.build(story)
