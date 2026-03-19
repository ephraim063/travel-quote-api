"""
SafariFlow Flask API v5
Added: JWT approval token generation, /approve and /reject endpoints
"""

import os
import io
import json
import uuid
import base64
import hmac
import hashlib
import logging
import urllib.request
import urllib.error
import urllib.parse
import time
from flask import Flask, request, jsonify, redirect
from pdf_generator import generate_quote_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Environment variables ────────────────────────────────────────────────────
SUPABASE_URL        = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY        = os.environ.get('SUPABASE_SERVICE_KEY', '')
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')
APPROVAL_SECRET     = os.environ.get('APPROVAL_SECRET', 'safariflow-secret-change-me')
MAKE_S2_WEBHOOK     = os.environ.get('MAKE_SCENARIO2_WEBHOOK', '')
MAKE_S3_WEBHOOK     = os.environ.get('MAKE_SCENARIO3_WEBHOOK', '')
API_BASE_URL        = os.environ.get('API_BASE_URL', 'https://web-production-4788f.up.railway.app')
PORTAL_URL          = os.environ.get('PORTAL_URL', 'https://safariflow-portal.netlify.app')
RESEND_API_KEY      = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM         = os.environ.get('RESEND_FROM', 'SafariFlow <onboarding@resend.dev>')
UNSPLASH_ACCESS_KEY = os.environ.get('UNSPLASH_ACCESS_KEY', '')
STORAGE_BUCKET      = 'quote-pdfs'
OUTPUT_DIR          = os.path.join(os.path.dirname(__file__), 'outputs')
TOKEN_EXPIRY_DAYS   = 7

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── JWT-style token helpers ──────────────────────────────────────────────────
def generate_token(quote_id, action):
    expires = int(time.time()) + (TOKEN_EXPIRY_DAYS * 86400)
    payload = f"{quote_id}:{action}:{expires}"
    sig = hmac.new(
        APPROVAL_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    token_str = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(token_str.encode()).decode()


def verify_token(token, expected_action):
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split(':')
        if len(parts) != 4:
            return None
        quote_id, action, expires, sig = parts
        if action != expected_action:
            return None
        if int(expires) < int(time.time()):
            return None
        expected_payload = f"{quote_id}:{action}:{expires}"
        expected_sig = hmac.new(
            APPROVAL_SECRET.encode(),
            expected_payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return quote_id
    except Exception:
        return None


# ─── Supabase helpers ─────────────────────────────────────────────────────────
def supabase_get(table, params=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        query = f"{SUPABASE_URL}/rest/v1/{table}"
        if params:
            query += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(query, headers={
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'apikey': SUPABASE_KEY,
            'Content-Type': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Supabase fetch error ({table}): {str(e)}")
        return []


def supabase_update(table, match_params, update_data):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase credentials missing — cannot update")
        return False
    try:
        query = f"{SUPABASE_URL}/rest/v1/{table}?" + urllib.parse.urlencode(match_params)
        payload = json.dumps(update_data).encode('utf-8')
        logger.info(f"PATCH URL: {query}")
        logger.info(f"PATCH body: {update_data}")
        req = urllib.request.Request(query, data=payload, method='PATCH', headers={
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'apikey': SUPABASE_KEY,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = resp.read().decode()
            logger.info(f"PATCH response: {result}")
        return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"Supabase PATCH HTTP error: {e.code} {e.reason} — {error_body}")
        return False
    except Exception as e:
        logger.error(f"Supabase PATCH error: {str(e)}")
        return False


def supabase_upload(file_path, filename):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return ''
    try:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{filename}"
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        req = urllib.request.Request(upload_url, data=pdf_bytes, method='POST', headers={
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/pdf',
            'x-upsert': 'true',
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{filename}"
        logger.info(f"Uploaded to Supabase Storage: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Supabase upload error: {str(e)}")
        return ''


def trigger_make_webhook(webhook_url, payload):
    if not webhook_url:
        logger.warning("Make webhook URL not set")
        return False
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(webhook_url, data=data, method='POST', headers={
            'Content-Type': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        logger.info(f"Make webhook triggered: {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"Make webhook error: {str(e)}")
        return False


# ─── Resend email helper ──────────────────────────────────────────────────────
def send_email(to, subject, html, attachments=None):
    """Send email via Resend API."""
    if not RESEND_API_KEY:
        logger.warning("Resend API key not set — skipping email")
        return False
    try:
        payload = {
            'from': RESEND_FROM,
            'to': [to] if isinstance(to, str) else to,
            'subject': subject,
            'html': html,
        }
        if attachments:
            payload['attachments'] = attachments

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=data, method='POST',
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            logger.info(f"Email sent via Resend: {result.get('id')}")
        return True
    except urllib.error.HTTPError as e:
        logger.error(f"Resend error: {e.code} {e.read().decode()}")
        return False
    except Exception as e:
        logger.error(f"Resend error: {str(e)}")
        return False


def agent_approval_email_html(agent_name, agency_name, client_name, quote_number,
                               start_date, end_date, total_price,
                               approve_url, reject_url,
                               brand_primary='#2E4A7A', brand_secondary='#C4922A'):
    """Build agent approval email HTML."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:30px 0;">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
<tr><td style="background-color:{brand_primary};padding:30px;text-align:center;">
  <h1 style="margin:0;color:#FFFFFF;font-size:22px;letter-spacing:2px;">{agency_name}</h1>
  <p style="margin:6px 0 0;color:#FFFFFF;font-size:12px;letter-spacing:1px;">NEW QUOTE READY FOR REVIEW</p>
</td></tr>
<tr><td style="background-color:{brand_secondary};height:3px;"></td></tr>
<tr><td style="padding:36px 40px;background:#ffffff;">
  <p style="color:#1A1A1A;font-size:16px;margin:0 0 8px;">Hello <strong>{agent_name}</strong>, a new safari quote has been generated and is ready for your review.</p>
  <table width="100%" cellpadding="12" style="background:#F5F0E8;border-radius:6px;margin:16px 0;">
    <tr>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;">CLIENT</td>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;">QUOTE NUMBER</td>
    </tr>
    <tr>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">{client_name}</td>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">{quote_number}</td>
    </tr>
    <tr>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;padding-top:8px;">TRAVEL DATES</td>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;padding-top:8px;">TOTAL VALUE</td>
    </tr>
    <tr>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">{start_date} — {end_date}</td>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">${total_price:,.0f}</td>
    </tr>
  </table>
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0 8px;">
    <tr><td align="center">
      <a href="{approve_url}" style="display:inline-block;background-color:{brand_primary};color:#FFFFFF;padding:16px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;letter-spacing:1px;">
        ✅ APPROVE &amp; SEND TO CLIENT
      </a>
    </td></tr>
  </table>
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 16px;">
    <tr><td align="center">
      <a href="{reject_url}" style="display:inline-block;background-color:{brand_secondary};color:#FFFFFF;padding:16px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;letter-spacing:1px;">
        ✏️ MAKE CHANGES
      </a>
    </td></tr>
  </table>
  <table width="100%" cellpadding="10" style="background:#FFF5F5;border-radius:6px;border:1px solid #F5CCCC;margin-bottom:16px;">
    <tr><td style="color:#B03030;font-size:13px;font-weight:bold;text-align:center;">⚠ THESE LINKS WILL EXPIRE IN 7 DAYS</td></tr>
  </table>
  <p style="color:#1A1A1A;font-size:14px;margin:0;">This quote was generated automatically by SafariFlow.</p>
</td></tr>
<tr><td style="background:#F5F0E8;padding:20px 40px;text-align:center;">
  <p style="margin:0;color:#444444;font-size:12px;">{agency_name} · Powered by SafariFlow</p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def client_quote_email_html(client_name, agency_name, agent_name, agent_email, agent_phone,
                             quote_number, start_date, end_date,
                             accept_url, changes_url,
                             brand_primary='#2E4A7A', brand_secondary='#C4922A'):
    """Build client quote email HTML."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:30px 0;">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
<tr><td style="background-color:{brand_primary};padding:30px;text-align:center;">
  <h1 style="margin:0;color:#FFFFFF;font-size:22px;letter-spacing:2px;">{agency_name}</h1>
  <p style="margin:6px 0 0;color:#FFFFFF;font-size:12px;letter-spacing:1px;">TRAVEL &amp; SAFARI SPECIALISTS</p>
</td></tr>
<tr><td style="background-color:{brand_secondary};height:3px;"></td></tr>
<tr><td style="padding:36px 40px;background:#ffffff;">
  <p style="color:#1A1A1A;font-size:16px;margin:0 0 8px;">Dear <strong>{client_name}</strong>, your personalised safari quote is ready for review.</p>
  <table width="100%" cellpadding="12" style="background:#F5F0E8;border-radius:6px;margin:16px 0;">
    <tr>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;">QUOTE NUMBER</td>
      <td style="color:#444444;font-size:11px;letter-spacing:1px;font-weight:bold;">TRAVEL DATES</td>
    </tr>
    <tr>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">{quote_number}</td>
      <td style="color:#1A1A1A;font-size:14px;font-weight:bold;">{start_date} — {end_date}</td>
    </tr>
  </table>
  <p style="color:#1A1A1A;font-size:15px;text-align:center;">Please review the attached PDF and let us know your decision.</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0 8px;">
    <tr><td align="center">
      <a href="{accept_url}" style="display:inline-block;background-color:{brand_primary};color:#FFFFFF;padding:16px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;letter-spacing:1px;">
        TAP THIS LINK TO ACCEPT THIS QUOTE
      </a>
    </td></tr>
  </table>
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 16px;">
    <tr><td align="center">
      <a href="{changes_url}" style="display:inline-block;background-color:{brand_secondary};color:#FFFFFF;padding:16px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;letter-spacing:1px;">
        TAP THIS LINK TO REQUEST CHANGES
      </a>
    </td></tr>
  </table>
  <table width="100%" cellpadding="10" style="background:#FFF5F5;border-radius:6px;border:1px solid #F5CCCC;margin-bottom:16px;">
    <tr><td style="color:#B03030;font-size:13px;font-weight:bold;text-align:center;">⚠ THESE LINKS WILL EXPIRE IN 7 DAYS</td></tr>
  </table>
  <p style="color:#1A1A1A;font-size:15px;">We look forward to crafting your perfect safari experience.</p>
</td></tr>
<tr><td style="background:#F5F0E8;padding:20px 40px;text-align:center;">
  <p style="margin:0;color:#444444;font-size:12px;">{agency_name} · {agent_email} · {agent_phone}</p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""


# ─── Claude API helper ────────────────────────────────────────────────────────
def call_claude(prompt, max_tokens=4000):
    if not ANTHROPIC_API_KEY:
        return {}
    try:
        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload, method='POST',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
        text = result.get('content', [{}])[0].get('text', '{}').strip()
        if text.startswith('```'):
            lines = [l for l in text.split('\n') if not l.strip().startswith('```')]
            text = '\n'.join(lines).strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Claude JSON parse error: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Claude API error: {str(e)}")
        return {}


# ─── Unsplash photo fetcher ───────────────────────────────────────────────────
def fetch_unsplash_photo(query, width=800, height=500):
    """Fetch a single photo from Unsplash for a given query. Returns image bytes or None."""
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://api.unsplash.com/search/photos?query={safe_query}&per_page=1&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
        req = urllib.request.Request(url, headers={'User-Agent': 'SafariFlow/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        results = data.get('results', [])
        if not results:
            return None
        photo_url = results[0].get('urls', {}).get('regular', '')
        if not photo_url:
            return None
        # Download the actual image
        img_req = urllib.request.Request(photo_url, headers={'User-Agent': 'SafariFlow/1.0'})
        with urllib.request.urlopen(img_req, timeout=10) as img_resp:
            return img_resp.read()
    except Exception as e:
        logger.warning(f"Unsplash fetch failed for '{query}': {str(e)}")
        return None


def fetch_photos_for_itinerary(itinerary):
    """Fetch photos for all itinerary days in parallel. Returns photo_cache dict."""
    if not UNSPLASH_ACCESS_KEY:
        logger.info("Unsplash key not set — skipping photos")
        return {}

    import threading

    photo_cache = {}
    lock = threading.Lock()

    # Deduplicate queries to avoid redundant API calls
    queries = {}
    for day in itinerary:
        query = day.get('image_search_query') or f"{day.get('destination', '')} safari wildlife Kenya"
        day_num = day.get('day_number', 0)
        queries[day_num] = query

    def fetch_one(day_num, query):
        img_bytes = fetch_unsplash_photo(query)
        if img_bytes:
            with lock:
                photo_cache[str(day_num)] = img_bytes
            logger.info(f"Photo fetched for day {day_num}: {query}")
        else:
            logger.warning(f"No photo for day {day_num}: {query}")

    threads = []
    for day_num, query in queries.items():
        t = threading.Thread(target=fetch_one, args=(day_num, query))
        t.start()
        threads.append(t)

    # Wait max 20 seconds for all photos
    for t in threads:
        t.join(timeout=20)

    logger.info(f"Photos fetched: {len(photo_cache)}/{len(queries)} days")
    return photo_cache


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'SafariFlow PDF Generator v5'})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON body received'}), 400

        agent_id          = data.get('agent_id', '')
        request_id        = data.get('request_id', str(uuid.uuid4())[:8].upper())
        client_name       = data.get('client_name', '')
        client_email      = data.get('client_email', '')
        client_phone      = data.get('client_phone', '')
        client_nationality= data.get('client_nationality', 'international')
        pax_adults        = int(data.get('pax_adults', 2) or 2)
        pax_children      = int(data.get('pax_children', 0) or 0)
        destinations      = data.get('destination', '')
        start_date        = data.get('start_date', '')
        end_date          = data.get('end_date', '')
        duration_days     = int(data.get('duration_days', 7) or 7)
        accommodation_tier= data.get('accommodation_tier', 'luxury')
        budget_usd        = float(data.get('budget_usd', 10000) or 10000)
        special_requests  = data.get('special_requests', '')

        logger.info(f"Generating quote for {client_name} — {destinations}")

        agents   = supabase_get('agents', {'id': f'eq.{agent_id}', 'select': '*'})
        agent    = agents[0] if agents else {}
        profiles = supabase_get('agent_profiles', {'agent_id': f'eq.{agent_id}', 'select': '*'})
        profile  = profiles[0] if profiles else {}
        reviews  = supabase_get('agent_reviews', {'agent_id': f'eq.{agent_id}', 'select': '*', 'limit': '3'})

        accommodations = supabase_get('accommodations', {'agent_id': f'eq.{agent_id}', 'is_active': 'eq.true', 'select': '*'})
        transport      = supabase_get('transport_routes', {'agent_id': f'eq.{agent_id}', 'is_active': 'eq.true', 'select': '*'})
        park_fees      = supabase_get('park_fees', {'agent_id': f'eq.{agent_id}', 'select': '*'})

        logger.info(f"Found: {len(accommodations)} accommodations, {len(transport)} transport, {len(park_fees)} park fees")

        def cents(val):
            return round((val or 0) / 100, 2)

        accom_for_claude = [{'name': a.get('name'), 'destination': a.get('destination'), 'category': a.get('category'), 'room_type': a.get('room_type'), 'meal_plan': a.get('meal_plan'), 'price_per_person_usd': cents(a.get('price_per_person_usd_cents'))} for a in accommodations]
        transport_for_claude = [{'from': t.get('from_location'), 'to': t.get('to_location'), 'type': t.get('transport_type'), 'operator': t.get('operator_name'), 'price_per_person_usd': cents(t.get('price_per_person_usd_cents')), 'duration_hours': t.get('duration_hours')} for t in transport]
        fees_for_claude = [{'park': f.get('park_name'), 'destination': f.get('destination'), 'visitor_category': f.get('visitor_category'), 'fee_per_person_per_day_usd': cents(f.get('fee_per_person_per_day_usd_cents'))} for f in park_fees]

        claude2_prompt = f"""You are a safari itinerary pricing specialist. Build the optimal itinerary using ONLY the exact pricing data provided below.

Return ONLY a valid JSON object. No explanation. No markdown. No code fences. Start your response with {{ and end with }}.

Structure:
{{
  "itinerary": [{{"day_number": 1, "date": "YYYY-MM-DD", "destination": "string", "title": "string", "accommodation_name": "string", "room_type": "string", "meal_plan": "string", "nights": 1, "transport_description": "string or null", "image_search_query": "string"}}],
  "line_items": [{{"line_type": "accommodation|transport|park_fee", "description": "string", "details": "string", "quantity": 2, "unit_price": 1950.00, "total_price": 3900.00}}],
  "total_price_usd": 0, "deposit_amount_usd": 0, "balance_amount_usd": 0, "within_budget": true, "budget_notes": "string or null"
}}

RULES: Sequence destinations logically. Select best-value accommodation for tier. Include all transport and park fees. deposit_amount_usd = total * 0.30.

TRIP REQUIREMENTS:
{json.dumps({"destinations": destinations, "duration_days": duration_days, "start_date": start_date, "end_date": end_date, "pax_adults": pax_adults, "pax_children": pax_children, "accommodation_tier": accommodation_tier, "budget_usd": budget_usd, "special_requests": special_requests, "visitor_category": "non_resident"})}

AVAILABLE ACCOMMODATIONS: {json.dumps(accom_for_claude)}
AVAILABLE TRANSPORT: {json.dumps(transport_for_claude)}
PARK FEES: {json.dumps(fees_for_claude)}"""

        itinerary_data = call_claude(claude2_prompt, max_tokens=4000)
        itinerary  = itinerary_data.get('itinerary', [])
        line_items = itinerary_data.get('line_items', [])
        total_price= float(itinerary_data.get('total_price_usd', 0) or 0)

        # ── Apply agent markup ────────────────────────────────────────────────
        markup_type = agent.get('markup_type', 'overall')
        markup_overall = float(agent.get('markup_overall_pct', 0) or 0) / 100
        markup_map = {
            'accommodation': float(agent.get('markup_accommodation_pct', 0) or 0) / 100,
            'transport':     float(agent.get('markup_transport_pct', 0) or 0) / 100,
            'park_fee':      float(agent.get('markup_park_fees_pct', 0) or 0) / 100,
            'activity':      float(agent.get('markup_activities_pct', 0) or 0) / 100,
        }

        marked_up_items = []
        for item in line_items:
            item = dict(item)
            if markup_type == 'overall':
                pct = markup_overall
            else:
                line_type = item.get('line_type', 'accommodation')
                pct = markup_map.get(line_type, markup_overall)
            if pct > 0:
                item['unit_price'] = round(float(item.get('unit_price', 0)) * (1 + pct), 2)
                item['total_price'] = round(float(item.get('total_price', 0)) * (1 + pct), 2)
            marked_up_items.append(item)

        line_items = marked_up_items
        total_price = sum(float(i.get('total_price', 0)) for i in line_items)
        deposit    = round(total_price * (float(agent.get('deposit_percentage', 30) or 30) / 100), 2)
        balance    = round(total_price - deposit, 2)

        logger.info(f"Itinerary built: {len(itinerary)} days, total ${total_price} (after markup)")

        first_name = client_name.split()[0] if client_name else "Dear Guest"
        intro_narrative = f"{first_name}, your {duration_days}-day safari across {destinations} has been carefully crafted to deliver an authentic East African experience. Every detail has been arranged to ensure your journey is seamless and unforgettable."
        narrative_days = [{'day_number': d.get('day_number'), 'narrative': f"Today you explore {d.get('destination')} with your expert guide, discovering the remarkable wildlife and landscapes that make this destination truly special.", 'highlight': f"Wildlife encounters in {d.get('destination')}", 'accommodation_description': f"{d.get('accommodation_name')}, {d.get('room_type')} — your comfortable base for the night."} for d in itinerary]

        quote_number         = f"QT-{request_id}"
        approve_token        = generate_token(quote_number, 'approve')
        reject_token         = generate_token(quote_number, 'reject')
        client_accept_token  = generate_token(quote_number, 'client-accept')
        client_changes_token = generate_token(quote_number, 'client-changes')
        approve_url          = f"{API_BASE_URL}/approve?token={approve_token}"
        reject_url           = f"{API_BASE_URL}/reject?token={reject_token}"
        client_accept_url    = f"{API_BASE_URL}/client-accept?token={client_accept_token}"
        client_changes_url   = f"{API_BASE_URL}/client-changes?token={client_changes_token}"

        logger.info(f"Approval tokens generated for {quote_number}")

        filename    = f"SafariFlow_Quote_{quote_number}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        reviews_formatted = [{'review_text': r.get('review_text', ''), 'client_name': r.get('client_name', ''), 'client_origin': r.get('client_origin', ''), 'trip_summary': r.get('trip_summary', '')} for r in reviews]

        logger.info("Fetching destination photos from Unsplash...")
        photo_cache = fetch_photos_for_itinerary(itinerary)

        pdf_data = {
            'quote_id':     quote_number,
            'generated_at': start_date[:10] if start_date else '',
            'accept_url':   '#',
            'changes_url':  '#',
            'inclusions':   '- All accommodation as specified\n- All meals as per itinerary\n- All game drives\n- Park and conservancy fees\n- Internal flights as specified\n- Airport transfers',
            'exclusions':   '- International flights\n- Travel insurance\n- Visa fees\n- Personal expenses\n- Gratuities',
            'terms':        agent.get('cancellation_terms') or 'This quote is valid for 14 days. A 30% deposit is required to confirm the booking. Balance due 60 days prior to departure.',
            'agent':        {'name': agent.get('agent_name', ''), 'email': agent.get('email', ''), 'phone': agent.get('phone', ''), 'agency': agent.get('agency_name', ''), 'logo_url': agent.get('logo_url', ''), 'website': agent.get('website', '')},
            'client':       {'name': client_name, 'email': client_email, 'phone': client_phone, 'pax_adults': str(pax_adults), 'pax_children': str(pax_children), 'nationality': client_nationality},
            'trip':         {'title': f"{duration_days}-Day {destinations} Safari", 'start_date': start_date, 'end_date': end_date, 'duration_nights': str(duration_days), 'destinations': destinations, 'travel_style': accommodation_tier.title()},
            'itinerary':    itinerary,
            'line_items':   line_items,
            'photo_cache':  photo_cache,
            'pricing':      {'total_price_usd': total_price, 'deposit_amount_usd': deposit, 'balance_amount_usd': balance, 'within_budget': itinerary_data.get('within_budget', True), 'budget_notes': itinerary_data.get('budget_notes', '')},
            'narrative':    {'intro': intro_narrative, 'days': narrative_days},
            'agent_profile':{'tagline': profile.get('tagline', 'Travel & Safari Specialists'), 'bio': profile.get('bio', ''), 'years_experience': profile.get('years_experience', ''), 'safaris_planned': profile.get('safaris_planned', ''), 'countries_covered': profile.get('countries_covered', ''), 'awards': profile.get('awards', []), 'memberships': profile.get('memberships', []), 'address': profile.get('address', ''), 'facebook': profile.get('facebook', ''), 'instagram': profile.get('instagram', ''), 'linkedin': profile.get('linkedin', '')},
            'agent_reviews': reviews_formatted,
        }

        logger.info("Generating PDF...")
        generate_quote_pdf(pdf_data, output_path)
        pdf_url = supabase_upload(output_path, filename)

        with open(output_path, 'rb') as f:
            pdf_bytes  = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        logger.info(f"PDF complete: {filename} ({len(pdf_bytes)} bytes)")

        # ── Send agent approval email via Resend ──────────────────────────────
        agent_email_addr = agent.get('email', '')
        if agent_email_addr:
            email_html = agent_approval_email_html(
                agent_name=agent.get('agent_name', 'Agent'),
                agency_name=agent.get('agency_name', 'SafariFlow'),
                client_name=client_name,
                quote_number=quote_number,
                start_date=start_date,
                end_date=end_date,
                total_price=total_price,
                approve_url=approve_url,
                reject_url=reject_url,
                brand_primary=agent.get('brand_color_primary', '#2E4A7A'),
                brand_secondary=agent.get('brand_color_secondary', '#C4922A'),
            )
            send_email(
                to=agent_email_addr,
                subject=f"New Quote Ready for Review — {client_name} ({quote_number})",
                html=email_html,
                attachments=[{
                    'filename': filename,
                    'content': pdf_base64,
                }]
            )
            logger.info(f"Agent approval email sent to {agent_email_addr}")

        return jsonify({
            'success':        True,
            'filename':       filename,
            'quote_number':   quote_number,
            'pdf_base64':     pdf_base64,
            'pdf_url':           pdf_url,
            'file_size':         len(pdf_bytes),
            'client_name':       client_name,
            'client_email':      client_email,
            'agent_email':       agent.get('email', ''),
            'agent_name':        agent.get('agent_name', ''),
            'agency_name':       agent.get('agency_name', ''),
            'quote_date':        start_date[:10] if start_date else '',
            'total_price_usd':   total_price,
            'deposit_usd':       deposit,
            'balance_usd':       balance,
            'itinerary_days':    len(itinerary),
            'approve_url':       approve_url,
            'reject_url':        reject_url,
            'client_accept_url': client_accept_url,
            'client_changes_url':client_changes_url,
            'destinations':      destinations,
            'start_date':        start_date,
            'end_date':          end_date,
        })

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ─── Helper: confirmation page ────────────────────────────────────────────────
def confirmation_page(token, action, title, message, button_label, button_color, icon):
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SafariFlow</title></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
<div style="max-width:500px;margin:60px auto;background:white;padding:40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.1);text-align:center;">
    <div style="font-size:48px;margin-bottom:16px">{icon}</div>
    <h2 style="color:#1B2A47;margin-bottom:8px">{title}</h2>
    <p style="color:#444;margin-bottom:24px">{message}</p>
    <form method="POST" action="/{action}-confirm">
        <input type="hidden" name="token" value="{token}">
        <button type="submit" style="background:{button_color};color:white;border:none;padding:14px 32px;border-radius:6px;font-size:15px;font-weight:bold;cursor:pointer;margin-right:12px;">
            {button_label}
        </button>
        <a href="javascript:history.back()" style="display:inline-block;background:#ccc;color:white;padding:14px 24px;border-radius:6px;font-size:15px;font-weight:bold;text-decoration:none;">
            Cancel
        </a>
    </form>
</div>
</body></html>'''


def success_page(icon, title, message, quote_id):
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SafariFlow</title></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
<div style="max-width:500px;margin:60px auto;background:white;padding:40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.1);text-align:center;">
    <div style="font-size:48px;margin-bottom:16px">{icon}</div>
    <h2 style="color:#1B2A47;margin-bottom:8px">{title}</h2>
    <p style="color:#444">{message}</p>
    <p style="color:#C4922A;font-weight:bold;font-size:14px;margin-top:16px">{quote_id}</p>
</div>
</body></html>'''


def invalid_page():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;text-align:center;padding:60px;background:#f4f4f4;">
<div style="max-width:500px;margin:0 auto;background:white;padding:40px;border-radius:12px;">
    <h2 style="color:#c0392b">Invalid or Expired Link</h2>
    <p style="color:#444">This link is invalid or has expired. Please contact your travel specialist.</p>
</div></body></html>''', 400


# ─── Agent Approve ────────────────────────────────────────────────────────────
@app.route('/approve', methods=['GET'])
def approve():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'approve')
    if not quote_id:
        return invalid_page()
    return confirmation_page(token, 'approve',
        'Approve This Quote',
        f'You are about to approve quote <strong>{quote_id}</strong> and send it to the client. Are you sure?',
        'Yes, Approve & Send', '#1B2A47', '&#x2705;')


@app.route('/approve-confirm', methods=['POST'])
def approve_confirm():
    token = request.form.get('token', '')
    quote_id = verify_token(token, 'approve')
    if not quote_id:
        return invalid_page()

    # Update status
    supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {'status': 'sent'})

    # Fetch quote and agent details to send client email
    quotes = supabase_get('quotes', {'quote_number': f'eq.{quote_id}', 'select': '*'})
    if quotes:
        quote = quotes[0]
        agents = supabase_get('agents', {'id': f'eq.{quote.get("agent_id")}', 'select': '*'})
        agent = agents[0] if agents else {}

        client_email_addr = quote.get('client_email', '')
        client_accept_token = generate_token(quote_id, 'client-accept')
        client_changes_token = generate_token(quote_id, 'client-changes')
        accept_url = f"{API_BASE_URL}/client-accept?token={client_accept_token}"
        changes_url = f"{API_BASE_URL}/client-changes?token={client_changes_token}"

        if client_email_addr:
            # Fetch PDF from Supabase Storage
            pdf_url = quote.get('pdf_url', '')
            pdf_base64 = ''
            if pdf_url:
                try:
                    req = urllib.request.Request(pdf_url, headers={'User-Agent': 'SafariFlow/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        pdf_base64 = base64.b64encode(resp.read()).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Could not fetch PDF for attachment: {str(e)}")

            email_html = client_quote_email_html(
                client_name=quote.get('client_name', 'Dear Guest'),
                agency_name=agent.get('agency_name', 'SafariFlow'),
                agent_name=agent.get('agent_name', ''),
                agent_email=agent.get('email', ''),
                agent_phone=agent.get('phone', ''),
                quote_number=quote_id,
                start_date=str(quote.get('start_date', '')),
                end_date=str(quote.get('end_date', '')),
                accept_url=accept_url,
                changes_url=changes_url,
                brand_primary=agent.get('brand_color_primary', '#2E4A7A'),
                brand_secondary=agent.get('brand_color_secondary', '#C4922A'),
            )

            attachments = []
            if pdf_base64:
                attachments = [{'filename': f'SafariFlow_Quote_{quote_id}.pdf', 'content': pdf_base64}]

            send_email(
                to=client_email_addr,
                subject=f"Your Safari Quote is Ready — {quote_id}",
                html=email_html,
                attachments=attachments if attachments else None,
            )
            logger.info(f"Client quote email sent to {client_email_addr}")

    trigger_make_webhook(MAKE_S2_WEBHOOK, {'event': 'quote_approved', 'quote_number': quote_id, 'approved_at': int(time.time())})
    logger.info(f"Quote approved: {quote_id}")
    return success_page('&#x2705;', 'Quote Approved', 'The quote has been approved and sent to the client.', quote_id)


# ─── Agent Reject ─────────────────────────────────────────────────────────────
@app.route('/reject', methods=['GET'])
def reject():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'reject')
    if not quote_id:
        return invalid_page()
    return confirmation_page(token, 'reject',
        'Request Changes',
        f'You are about to flag quote <strong>{quote_id}</strong> for revision. Are you sure?',
        'Yes, Request Changes', '#C4922A', '&#x270F;&#xFE0F;')


@app.route('/reject-confirm', methods=['POST'])
def reject_confirm():
    token = request.form.get('token', '')
    quote_id = verify_token(token, 'reject')
    if not quote_id:
        return invalid_page()
    supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {'status': 'revision_requested'})
    trigger_make_webhook(MAKE_S2_WEBHOOK, {'event': 'quote_rejected', 'quote_number': quote_id, 'rejected_at': int(time.time())})
    logger.info(f"Quote rejected: {quote_id}")
    return success_page('&#x270F;&#xFE0F;', 'Revision Requested', 'The quote has been flagged for revision. You will be notified when it is ready to review again.', quote_id)


# ─── Client Accept ────────────────────────────────────────────────────────────
@app.route('/client-accept', methods=['GET'])
def client_accept():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'client-accept')
    if not quote_id:
        return invalid_page()
    return confirmation_page(token, 'client-accept',
        'Accept This Quote',
        f'You are about to accept quote <strong>{quote_id}</strong> and confirm your safari booking. Are you sure?',
        'Yes, Accept This Quote', '#1B2A47', '&#x1F389;')


@app.route('/client-accept-confirm', methods=['POST'])
def client_accept_confirm():
    token = request.form.get('token', '')
    quote_id = verify_token(token, 'client-accept')
    if not quote_id:
        return invalid_page()
    supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {'status': 'accepted'})
    trigger_make_webhook(MAKE_S2_WEBHOOK, {'event': 'quote_accepted', 'quote_number': quote_id, 'accepted_at': int(time.time())})
    logger.info(f"Quote accepted by client: {quote_id}")
    return success_page('&#x1F389;', 'Quote Accepted!', 'Thank you! Your safari booking is confirmed. Your travel specialist will be in touch shortly with payment details.', quote_id)


# ─── Client Changes ───────────────────────────────────────────────────────────
@app.route('/client-changes', methods=['GET'])
def client_changes():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'client-changes')
    if not quote_id:
        return invalid_page()

    # Fetch quote and agent details
    quotes = supabase_get('quotes', {'quote_number': f'eq.{quote_id}', 'select': '*'})
    quote = quotes[0] if quotes else {}
    agents = supabase_get('agents', {'id': f'eq.{quote.get("agent_id", "")}', 'select': '*'})
    agent = agents[0] if agents else {}
    brand_primary = agent.get('brand_color_primary', '#2E4A7A')
    brand_secondary = agent.get('brand_color_secondary', '#C4922A')
    agency_name = agent.get('agency_name', 'SafariFlow')

    # Fetch optional extras for this agent
    extras = supabase_get('optional_extras', {
        'agent_id': f'eq.{agent.get("id", "")}',
        'is_active': 'eq.true',
        'select': 'id,name,category,price_per_person_usd_cents,price_type,duration_hours',
        'order': 'category.asc,name.asc'
    }) if agent.get('id') else []

    # Build extras buttons HTML
    extras_html = ''
    if extras:
        extras_buttons = ''
        for ex in extras:
            price = ex.get('price_per_person_usd_cents', 0) / 100
            price_label = f"${price:,.0f}/pp" if ex.get('price_type') == 'per_person' else f"${price:,.0f}/grp"
            extras_buttons += f'''
            <div class="extra-btn" onclick="toggleExtra(this)" data-id="{ex['id']}" data-name="{ex['name']}">
              <input type="hidden" name="extra_{ex['id']}" value="no" class="extra-input">
              <div class="extra-name">{ex['name']}</div>
              <div class="extra-meta">{ex.get('category','')} · {ex.get('duration_hours',2)}h · {price_label}</div>
            </div>'''
        extras_html = f'''
      <div class="section-label" style="margin-top:24px;">Would you like to add any extras?</div>
      <p style="font-size:12px;color:#888;margin-bottom:12px;">Tap to add experiences to your revised quote.</p>
      <div class="extras-grid">{extras_buttons}</div>'''

    min_date = time.strftime('%Y-%m-%d')

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Request Changes — {quote_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
  .container {{ max-width: 580px; margin: 40px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }}
  .header {{ background: {brand_primary}; padding: 28px; text-align: center; color: white; }}
  .header h1 {{ font-size: 20px; letter-spacing: 2px; margin-bottom: 4px; }}
  .header p {{ font-size: 12px; opacity: 0.8; }}
  .gold-line {{ background: {brand_secondary}; height: 3px; }}
  .body {{ padding: 32px; }}
  .body h2 {{ font-size: 18px; color: #1A1A1A; margin-bottom: 6px; }}
  .sub {{ font-size: 13px; color: #666; margin-bottom: 24px; }}
  .section-label {{ font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #999; text-transform: uppercase; margin-bottom: 10px; }}
  .quote-ref {{ background: #F8F6F2; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 13px; color: #666; }}
  .quote-ref span {{ color: {brand_secondary}; font-weight: bold; font-family: monospace; }}

  /* Change toggle buttons */
  .changes-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 8px; }}
  .change-btn {{
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px; border-radius: 10px; cursor: pointer;
    border: 2px solid #E8E4DE; background: #F8F6F2;
    transition: all 0.2s; user-select: none;
  }}
  .change-btn:hover {{ border-color: {brand_secondary}; }}
  .change-btn.selected {{ border-color: {brand_primary}; background: rgba(46,74,122,0.07); }}
  .change-btn input {{ display: none; }}
  .change-icon {{ font-size: 20px; flex-shrink: 0; }}
  .change-label {{ font-size: 13px; color: #1A1A1A; font-weight: 500; flex: 1; }}
  .change-btn.selected .change-label {{ color: {brand_primary}; font-weight: 700; }}
  .check-mark {{
    width: 20px; height: 20px; border-radius: 50%;
    background: {brand_primary}; color: white; font-size: 11px;
    display: none; align-items: center; justify-content: center; flex-shrink: 0;
  }}
  .change-btn.selected .check-mark {{ display: flex; }}

  /* Expandable fields */
  .expand-field {{
    display: none; background: #F0EDE8; border-radius: 10px;
    padding: 16px; margin-top: 10px; margin-bottom: 4px;
    border: 1px solid #E0D8CE; animation: slideDown 0.2s ease;
  }}
  .expand-field.visible {{ display: block; }}
  @keyframes slideDown {{ from {{ opacity:0; transform:translateY(-8px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .expand-label {{ font-size: 11px; font-weight: bold; color: #888; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }}

  /* Budget input */
  .budget-input {{
    width: 100%; padding: 10px 14px; border: 1px solid #E8E4DE;
    border-radius: 8px; font-size: 16px; font-weight: 600;
    color: #1A1A1A; outline: none; font-family: Arial, sans-serif;
  }}
  .budget-input:focus {{ border-color: {brand_primary}; }}

  /* Date input */
  .form-row-dates {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .date-input {{
    width: 100%; padding: 10px 12px; border: 1px solid #E8E4DE;
    border-radius: 8px; font-size: 14px; font-family: Arial, sans-serif;
    outline: none; color: #1A1A1A; cursor: pointer;
    transition: border 0.2s;
  }}
  .date-input:focus {{ border-color: {brand_primary}; }}

  /* Traveler stepper */
  .stepper-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }}
  .stepper-label {{ font-size: 13px; color: #444; font-weight: 500; }}
  .stepper-controls {{ display: flex; align-items: center; gap: 12px; }}
  .stepper-btn {{
    width: 32px; height: 32px; border-radius: 50%;
    background: {brand_primary}; color: white; border: none;
    font-size: 18px; cursor: pointer; display: flex;
    align-items: center; justify-content: center; font-weight: bold;
  }}
  .stepper-btn:hover {{ opacity: 0.85; }}
  .stepper-value {{ font-size: 16px; font-weight: 700; color: #1A1A1A; min-width: 24px; text-align: center; }}

  /* Extras */
  .extras-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
  .extra-btn {{
    padding: 12px 14px; border-radius: 10px; cursor: pointer;
    border: 2px solid #E8E4DE; background: #F8F6F2;
    transition: all 0.2s; user-select: none;
  }}
  .extra-btn:hover {{ border-color: {brand_secondary}; }}
  .extra-btn.selected {{ border-color: {brand_secondary}; background: rgba(196,146,42,0.08); }}
  .extra-name {{ font-size: 13px; color: #1A1A1A; font-weight: 600; margin-bottom: 3px; }}
  .extra-btn.selected .extra-name {{ color: {brand_secondary}; }}
  .extra-meta {{ font-size: 11px; color: #888; }}
  .extra-btn.selected .extra-meta {{ color: {brand_secondary}; opacity: 0.8; }}

  /* Notes */
  .notes-area {{
    width: 100%; padding: 12px 14px; border: 1px solid #E8E4DE;
    border-radius: 8px; font-size: 13px; font-family: Arial, sans-serif;
    outline: none; resize: vertical; min-height: 80px;
    transition: border 0.2s; color: #1A1A1A;
  }}
  .notes-area:focus {{ border-color: {brand_primary}; }}

  .submit-btn {{
    width: 100%; background: {brand_primary}; color: white; border: none;
    padding: 14px; border-radius: 8px; font-size: 15px; font-weight: bold;
    cursor: pointer; letter-spacing: 1px; margin-top: 8px;
  }}
  .submit-btn:hover {{ opacity: 0.9; }}

  @media (max-width: 480px) {{
    .changes-grid, .extras-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{agency_name}</h1>
    <p>REQUEST CHANGES TO YOUR QUOTE</p>
  </div>
  <div class="gold-line"></div>
  <div class="body">
    <h2>What would you like changed?</h2>
    <p class="sub">Tap the options below. We'll revise your quote and send it back to you.</p>

    <div class="quote-ref">Quote Reference: <span>{quote_id}</span></div>

    <form method="POST" action="/client-changes-confirm" id="changeForm">
      <input type="hidden" name="token" value="{token}">
      <input type="hidden" name="revised_month" id="revised_month_hidden" value="">
      <input type="hidden" name="revised_adults" id="revised_adults_hidden" value="0">
      <input type="hidden" name="revised_children" id="revised_children_hidden" value="0">

      <div class="section-label">What needs changing?</div>

      <div class="changes-grid">

        <!-- Accommodation -->
        <div class="change-btn" onclick="toggleChange(this, 'accommodation')">
          <input type="hidden" name="change_accommodation" value="no">
          <span class="change-icon">🏨</span>
          <span class="change-label">Accommodation</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Travel Dates -->
        <div class="change-btn" onclick="toggleChange(this, 'dates')">
          <input type="hidden" name="change_dates" value="no">
          <span class="change-icon">📅</span>
          <span class="change-label">Travel Dates</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Budget -->
        <div class="change-btn" onclick="toggleChange(this, 'budget')">
          <input type="hidden" name="change_budget" value="no">
          <span class="change-icon">💰</span>
          <span class="change-label">Budget</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Destinations -->
        <div class="change-btn" onclick="toggleChange(this, 'destinations')">
          <input type="hidden" name="change_destinations" value="no">
          <span class="change-icon">📍</span>
          <span class="change-label">Destinations</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Travelers -->
        <div class="change-btn" onclick="toggleChange(this, 'travelers')">
          <input type="hidden" name="change_travelers" value="no">
          <span class="change-icon">👥</span>
          <span class="change-label">No. of Travelers</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Transport -->
        <div class="change-btn" onclick="toggleChange(this, 'transport')">
          <input type="hidden" name="change_transport" value="no">
          <span class="change-icon">✈️</span>
          <span class="change-label">Transport</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Duration -->
        <div class="change-btn" onclick="toggleChange(this, 'duration')">
          <input type="hidden" name="change_duration" value="no">
          <span class="change-icon">🌙</span>
          <span class="change-label">Trip Duration</span>
          <span class="check-mark">✓</span>
        </div>

        <!-- Other -->
        <div class="change-btn" onclick="toggleChange(this, 'other')">
          <input type="hidden" name="change_other" value="no">
          <span class="change-icon">✏️</span>
          <span class="change-label">Other</span>
          <span class="check-mark">✓</span>
        </div>

      </div>

      <!-- Budget expand field -->
      <div class="expand-field" id="field_budget">
        <div class="expand-label">What is your revised budget? (USD)</div>
        <input type="number" name="revised_budget" class="budget-input" placeholder="e.g. 8000" min="0">
      </div>

      <!-- Dates expand field — exact date picker -->
      <div class="expand-field" id="field_dates">
        <div class="expand-label">Select New Travel Dates</div>
        <div class="form-row-dates">
          <div>
            <div style="font-size:12px;color:#666;font-weight:600;margin-bottom:6px;">Start Date</div>
            <input type="date" name="revised_start_date" class="date-input" min="{min_date}">
          </div>
          <div>
            <div style="font-size:12px;color:#666;font-weight:600;margin-bottom:6px;">End Date</div>
            <input type="date" name="revised_end_date" class="date-input" min="{min_date}">
          </div>
        </div>
        <p style="font-size:11px;color:#999;margin-top:8px;">⚠ Please ensure dates align with your flights</p>
      </div>

      <!-- Travelers expand field — stepper -->
      <div class="expand-field" id="field_travelers">
        <div class="expand-label">How many travelers?</div>
        <div class="stepper-row">
          <span class="stepper-label">Adults</span>
          <div class="stepper-controls">
            <button type="button" class="stepper-btn" onclick="updatePax('adults', -1)">−</button>
            <span class="stepper-value" id="adults_display">2</span>
            <button type="button" class="stepper-btn" onclick="updatePax('adults', 1)">+</button>
          </div>
        </div>
        <div class="stepper-row">
          <span class="stepper-label">Children</span>
          <div class="stepper-controls">
            <button type="button" class="stepper-btn" onclick="updatePax('children', -1)">−</button>
            <span class="stepper-value" id="children_display">0</span>
            <button type="button" class="stepper-btn" onclick="updatePax('children', 1)">+</button>
          </div>
        </div>
      </div>

      {extras_html}

      <!-- Always visible notes field -->
      <div style="margin-top:20px;">
        <div class="section-label">Anything else you'd like us to know?</div>
        <textarea name="notes" class="notes-area" placeholder="Any other details, preferences or requests not covered above..."></textarea>
      </div>

      <input type="hidden" name="revised_budget_final" id="revised_budget_final" value="">

      <button type="submit" class="submit-btn">✏️ SUBMIT CHANGE REQUEST</button>
    </form>
  </div>
</div>

<script>
  // ── Change toggle ──────────────────────────────────────────────────────────
  function toggleChange(btn, type) {{
    btn.classList.toggle('selected');
    var input = btn.querySelector('input[type="hidden"]');
    var isSelected = btn.classList.contains('selected');
    input.value = isSelected ? 'yes' : 'no';

    // Show/hide expand fields
    var field = document.getElementById('field_' + type);
    if (field) {{
      if (isSelected) {{
        field.classList.add('visible');
      }} else {{
        field.classList.remove('visible');
      }}
    }}
  }}

  // ── Date validation — end date must be after start date ───────────────────
  document.addEventListener('change', function(e) {{
    if (e.target.name === 'revised_start_date') {{
      var endInput = document.querySelector('[name="revised_end_date"]');
      if (endInput) {{
        endInput.min = e.target.value;
        if (endInput.value && endInput.value < e.target.value) {{
          endInput.value = '';
        }}
      }}
    }}
  }});

  // ── Traveler stepper ───────────────────────────────────────────────────────
  var adults = 2;
  var children = 0;

  function updatePax(type, delta) {{
    if (type === 'adults') {{
      adults = Math.max(1, adults + delta);
      document.getElementById('adults_display').textContent = adults;
      document.getElementById('revised_adults_hidden').value = adults;
    }} else {{
      children = Math.max(0, children + delta);
      document.getElementById('children_display').textContent = children;
      document.getElementById('revised_children_hidden').value = children;
    }}
  }}

  // ── Extras toggle ──────────────────────────────────────────────────────────
  function toggleExtra(btn) {{
    btn.classList.toggle('selected');
    var input = btn.querySelector('.extra-input');
    input.value = btn.classList.contains('selected') ? 'yes' : 'no';
  }}
</script>
</body>
</html>'''

    # Build extras buttons HTML
    extras_html = ''
    if extras:
        extras_buttons = ''
        for ex in extras:
            price = ex.get('price_per_person_usd_cents', 0) / 100
            price_label = f"${price:,.0f}/pp" if ex.get('price_type') == 'per_person' else f"${price:,.0f}/grp"
            extras_buttons += f'''
            <div class="extra-btn" onclick="toggleExtra(this)" data-id="{ex['id']}" data-name="{ex['name']}">
              <input type="hidden" name="extra_{ex['id']}" value="no" class="extra-input">
              <div class="extra-name">{ex['name']}</div>
              <div class="extra-meta">{ex.get('category','')} · {ex.get('duration_hours',2)}h · {price_label}</div>
            </div>'''

        extras_html = f'''
      <div class="section-label" style="margin-top:20px;">Would you like to add any extras?</div>
      <div class="extras-grid">{extras_buttons}</div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Request Changes — {quote_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
  .container {{ max-width: 580px; margin: 40px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }}
  .header {{ background: {brand_primary}; padding: 28px; text-align: center; color: white; }}
  .header h1 {{ font-size: 20px; letter-spacing: 2px; margin-bottom: 4px; }}
  .header p {{ font-size: 12px; opacity: 0.8; }}
  .gold-line {{ background: {brand_secondary}; height: 3px; }}
  .body {{ padding: 32px; }}
  .body h2 {{ font-size: 18px; color: #1A1A1A; margin-bottom: 6px; }}
  .sub {{ font-size: 13px; color: #666; margin-bottom: 24px; }}
  .section-label {{ font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #999; text-transform: uppercase; margin-bottom: 10px; }}
  .quote-ref {{ background: #F8F6F2; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 13px; color: #666; }}
  .quote-ref span {{ color: {brand_secondary}; font-weight: bold; font-family: monospace; }}

  /* Change toggle buttons */
  .changes-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
  .change-btn {{
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px; border-radius: 10px; cursor: pointer;
    border: 2px solid #E8E4DE; background: #F8F6F2;
    transition: all 0.2s; user-select: none;
  }}
  .change-btn:hover {{ border-color: {brand_secondary}; }}
  .change-btn.selected {{ border-color: {brand_primary}; background: rgba(46,74,122,0.08); }}
  .change-btn input {{ display: none; }}
  .change-icon {{ font-size: 20px; flex-shrink: 0; }}
  .change-label {{ font-size: 13px; color: #1A1A1A; font-weight: 500; }}
  .change-btn.selected .change-label {{ color: {brand_primary}; font-weight: 700; }}
  .check-mark {{ margin-left: auto; width: 20px; height: 20px; border-radius: 50%; background: {brand_primary}; color: white; font-size: 11px; display: none; align-items: center; justify-content: center; flex-shrink: 0; }}
  .change-btn.selected .check-mark {{ display: flex; }}

  /* Extras toggle buttons */
  .extras-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
  .extra-btn {{
    padding: 12px 14px; border-radius: 10px; cursor: pointer;
    border: 2px solid #E8E4DE; background: #F8F6F2;
    transition: all 0.2s; user-select: none;
  }}
  .extra-btn:hover {{ border-color: {brand_secondary}; }}
  .extra-btn.selected {{ border-color: {brand_secondary}; background: rgba(196,146,42,0.08); }}
  .extra-name {{ font-size: 13px; color: #1A1A1A; font-weight: 600; margin-bottom: 3px; }}
  .extra-btn.selected .extra-name {{ color: {brand_secondary}; }}
  .extra-meta {{ font-size: 11px; color: #888; }}
  .extra-btn.selected .extra-meta {{ color: {brand_secondary}; opacity: 0.8; }}

  /* Budget row */
  .budget-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
  .form-group {{ margin-bottom: 16px; }}
  .form-group label {{ display: block; font-size: 12px; font-weight: bold; color: #666; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .form-group input, .form-group textarea, .form-group select {{
    width: 100%; padding: 10px 12px; border: 1px solid #E8E4DE;
    border-radius: 8px; font-size: 13px; font-family: Arial, sans-serif;
    outline: none; transition: border 0.2s;
  }}
  .form-group input:focus, .form-group textarea:focus {{ border-color: {brand_primary}; }}
  .form-group textarea {{ min-height: 80px; resize: vertical; }}
  .submit-btn {{
    width: 100%; background: {brand_primary}; color: white; border: none;
    padding: 14px; border-radius: 8px; font-size: 15px; font-weight: bold;
    cursor: pointer; letter-spacing: 1px; margin-top: 8px;
  }}
  .submit-btn:hover {{ opacity: 0.9; }}
  @media (max-width: 480px) {{
    .changes-grid, .extras-grid {{ grid-template-columns: 1fr; }}
    .budget-row {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{agency_name}</h1>
    <p>REQUEST CHANGES TO YOUR QUOTE</p>
  </div>
  <div class="gold-line"></div>
  <div class="body">
    <h2>What would you like changed?</h2>
    <p class="sub">Tap the options below and we'll revise your quote and send it back to you.</p>

    <div class="quote-ref">Quote Reference: <span>{quote_id}</span></div>

    <form method="POST" action="/client-changes-confirm">
      <input type="hidden" name="token" value="{token}">

      <div class="section-label">What needs changing?</div>
      <div class="changes-grid">
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_accommodation" value="no">
          <span class="change-icon">🏨</span>
          <span class="change-label">Accommodation</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_dates" value="no">
          <span class="change-icon">📅</span>
          <span class="change-label">Travel Dates</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_budget" value="no">
          <span class="change-icon">💰</span>
          <span class="change-label">Budget</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_destinations" value="no">
          <span class="change-icon">📍</span>
          <span class="change-label">Destinations</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_travelers" value="no">
          <span class="change-icon">👥</span>
          <span class="change-label">No. of Travelers</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_transport" value="no">
          <span class="change-icon">✈️</span>
          <span class="change-label">Transport</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_duration" value="no">
          <span class="change-icon">🌙</span>
          <span class="change-label">Trip Duration</span>
          <span class="check-mark">✓</span>
        </div>
        <div class="change-btn" onclick="toggleChange(this)">
          <input type="hidden" name="change_other" value="no">
          <span class="change-icon">✏️</span>
          <span class="change-label">Other</span>
          <span class="check-mark">✓</span>
        </div>
      </div>

      {extras_html}

      <div class="budget-row">
        <div class="form-group">
          <label>Revised Budget (USD)</label>
          <input type="number" name="revised_budget" placeholder="e.g. 8000">
        </div>
        <div class="form-group">
          <label>Preferred Travel Month</label>
          <select name="preferred_month">
            <option value="">— No change —</option>
            <option>January</option><option>February</option><option>March</option>
            <option>April</option><option>May</option><option>June</option>
            <option>July</option><option>August</option><option>September</option>
            <option>October</option><option>November</option><option>December</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>Additional Notes</label>
        <textarea name="notes" placeholder="Please describe any specific changes you would like..."></textarea>
      </div>

      <button type="submit" class="submit-btn">✏️ SUBMIT CHANGE REQUEST</button>
    </form>
  </div>
</div>

<script>
function toggleChange(btn) {{
  btn.classList.toggle('selected');
  var input = btn.querySelector('input[type="hidden"]');
  input.value = btn.classList.contains('selected') ? 'yes' : 'no';
}}

function toggleExtra(btn) {{
  btn.classList.toggle('selected');
  var input = btn.querySelector('.extra-input');
  input.value = btn.classList.contains('selected') ? 'yes' : 'no';
}}
</script>
</body>
</html>'''

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Request Changes — {quote_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
  .container {{ max-width: 560px; margin: 40px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.1); }}
  .header {{ background: {brand_primary}; padding: 28px; text-align: center; color: white; }}
  .header h1 {{ font-size: 20px; letter-spacing: 2px; margin-bottom: 4px; }}
  .header p {{ font-size: 12px; opacity: 0.8; }}
  .gold-line {{ background: {brand_secondary}; height: 3px; }}
  .body {{ padding: 32px; }}
  .body h2 {{ font-size: 18px; color: #1A1A1A; margin-bottom: 6px; }}
  .body .sub {{ font-size: 13px; color: #666; margin-bottom: 24px; }}
  .section-label {{ font-size: 11px; font-weight: bold; letter-spacing: 1px; color: #999; text-transform: uppercase; margin-bottom: 10px; }}
  .checkboxes {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }}
  .checkbox-item {{ display: flex; align-items: center; gap: 8px; background: #F8F6F2; border: 1px solid #E8E4DE; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.2s; }}
  .checkbox-item:hover {{ border-color: {brand_secondary}; }}
  .checkbox-item input {{ accent-color: {brand_primary}; width: 16px; height: 16px; cursor: pointer; }}
  .checkbox-item label {{ font-size: 13px; color: #1A1A1A; cursor: pointer; }}
  .budget-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
  .form-group {{ margin-bottom: 16px; }}
  .form-group label {{ display: block; font-size: 12px; font-weight: bold; color: #666; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .form-group input, .form-group textarea, .form-group select {{ width: 100%; padding: 10px 12px; border: 1px solid #E8E4DE; border-radius: 8px; font-size: 13px; font-family: Arial, sans-serif; outline: none; transition: border 0.2s; }}
  .form-group input:focus, .form-group textarea:focus {{ border-color: {brand_primary}; }}
  .form-group textarea {{ min-height: 90px; resize: vertical; }}
  .submit-btn {{ width: 100%; background: {brand_primary}; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; letter-spacing: 1px; margin-top: 8px; }}
  .submit-btn:hover {{ opacity: 0.9; }}
  .quote-ref {{ background: #F8F6F2; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; font-size: 13px; color: #666; }}
  .quote-ref span {{ color: {brand_secondary}; font-weight: bold; font-family: monospace; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{agency_name}</h1>
    <p>REQUEST CHANGES TO YOUR QUOTE</p>
  </div>
  <div class="gold-line"></div>
  <div class="body">
    <h2>What would you like changed?</h2>
    <p class="sub">Please tell us what you'd like us to adjust. We'll revise your quote and send it back to you.</p>

    <div class="quote-ref">Quote Reference: <span>{quote_id}</span></div>

    <form method="POST" action="/client-changes-confirm">
      <input type="hidden" name="token" value="{token}">

      <div class="section-label">What needs changing?</div>
      <div class="checkboxes">
        <div class="checkbox-item">
          <input type="checkbox" id="c1" name="change_accommodation" value="yes">
          <label for="c1">🏨 Accommodation</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c2" name="change_dates" value="yes">
          <label for="c2">📅 Travel Dates</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c3" name="change_budget" value="yes">
          <label for="c3">💰 Budget</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c4" name="change_destinations" value="yes">
          <label for="c4">📍 Destinations</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c5" name="change_travelers" value="yes">
          <label for="c5">👥 No. of Travelers</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c6" name="change_transport" value="yes">
          <label for="c6">✈️ Transport</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c7" name="change_duration" value="yes">
          <label for="c7">🌙 Trip Duration</label>
        </div>
        <div class="checkbox-item">
          <input type="checkbox" id="c8" name="change_other" value="yes">
          <label for="c8">✏️ Other</label>
        </div>
      </div>

      <div class="budget-row">
        <div class="form-group">
          <label>Revised Budget (USD)</label>
          <input type="number" name="revised_budget" placeholder="e.g. 8000">
        </div>
        <div class="form-group">
          <label>Preferred Travel Month</label>
          <select name="preferred_month">
            <option value="">— No change —</option>
            <option>January</option><option>February</option><option>March</option>
            <option>April</option><option>May</option><option>June</option>
            <option>July</option><option>August</option><option>September</option>
            <option>October</option><option>November</option><option>December</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>Additional Notes</label>
        <textarea name="notes" placeholder="Please describe the specific changes you would like..."></textarea>
      </div>

      <button type="submit" class="submit-btn">✏️ SUBMIT CHANGE REQUEST</button>
    </form>
  </div>
</div>
</body>
</html>'''


@app.route('/client-changes-confirm', methods=['POST'])
def client_changes_confirm():
    token = request.form.get('token', '')
    quote_id = verify_token(token, 'client-changes')
    if not quote_id:
        return invalid_page()

    # Capture selected extras
    selected_extras = []
    for key, value in request.form.items():
        if key.startswith('extra_') and value == 'yes':
            extra_id = key.replace('extra_', '')
            selected_extras.append(extra_id)

    change_request = {
        'accommodation': request.form.get('change_accommodation') == 'yes',
        'dates':         request.form.get('change_dates') == 'yes',
        'budget':        request.form.get('change_budget') == 'yes',
        'destinations':  request.form.get('change_destinations') == 'yes',
        'travelers':     request.form.get('change_travelers') == 'yes',
        'transport':     request.form.get('change_transport') == 'yes',
        'duration':      request.form.get('change_duration') == 'yes',
        'other':         request.form.get('change_other') == 'yes',
        'revised_budget':    request.form.get('revised_budget', ''),
        'revised_start_date': request.form.get('revised_start_date', ''),
        'revised_end_date':   request.form.get('revised_end_date', ''),
        'revised_month':      request.form.get('revised_month', ''),
        'revised_adults':     request.form.get('revised_adults', '0'),
        'revised_children':   request.form.get('revised_children', '0'),
        'preferred_month':    request.form.get('revised_month', ''),
        'notes':              request.form.get('notes', ''),
        'selected_extras':    selected_extras,
    }

    # Build human-readable summary for agent notification
    changes_list = []
    if change_request['accommodation']: changes_list.append('Accommodation')
    if change_request['dates']:         changes_list.append('Travel Dates')
    if change_request['budget']:        changes_list.append('Budget')
    if change_request['destinations']:  changes_list.append('Destinations')
    if change_request['travelers']:     changes_list.append('Number of Travelers')
    if change_request['transport']:     changes_list.append('Transport')
    if change_request['duration']:      changes_list.append('Trip Duration')
    if change_request['other']:         changes_list.append('Other')

    # Update quote status and save change request
    supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {
        'status': 'revision_requested',
        'change_request': json.dumps(change_request),
    })

    # Trigger Scenario 3 — AI Revision Pipeline
    trigger_make_webhook(MAKE_S3_WEBHOOK, {
        'event':            'client_changes_requested',
        'quote_number':     quote_id,
        'changes_requested': changes_list,
        'revised_budget':   change_request['revised_budget'],
        'preferred_month':  change_request['preferred_month'],
        'notes':            change_request['notes'],
        'requested_at':     int(time.time()),
    })

    logger.info(f"Client requested changes for {quote_id}: {changes_list}")

    # ── Send agent notification email via Resend ──────────────────────────────
    quotes = supabase_get('quotes', {'quote_number': f'eq.{quote_id}', 'select': '*'})
    if quotes:
        quote = quotes[0]
        agents = supabase_get('agents', {'id': f'eq.{quote.get("agent_id")}', 'select': '*'})
        agent = agents[0] if agents else {}
        agent_email_addr = agent.get('email', '')
        if agent_email_addr:
            brand_primary = agent.get('brand_color_primary', '#2E4A7A')
            brand_secondary = agent.get('brand_color_secondary', '#C4922A')
            agency_name = agent.get('agency_name', 'SafariFlow')
            agent_name = agent.get('agent_name', 'Agent')
            portal_link = f"{PORTAL_URL}/quotes/review/{quote_id}"
            changes_html = ''.join([f'<li style="margin-bottom:6px;color:#1A1A1A;font-size:13px;">{c}</li>' for c in changes_list])
            budget_line = f'<p style="margin:12px 0;font-size:13px;color:#1A1A1A;"><strong>Revised budget:</strong> ${float(change_request["revised_budget"]):,.0f}</p>' if change_request.get('revised_budget') else ''
            notes_line = f'<div style="background:#F8F6F2;border-radius:8px;padding:12px 14px;margin:12px 0;font-size:13px;color:#444;">💬 {change_request["notes"]}</div>' if change_request.get('notes') else ''

            revision_email_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:30px 0;">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
<tr><td style="background-color:{brand_primary};padding:30px;text-align:center;">
  <h1 style="margin:0;color:#FFFFFF;font-size:22px;letter-spacing:2px;">{agency_name}</h1>
  <p style="margin:6px 0 0;color:#FFFFFF;font-size:12px;letter-spacing:1px;">CLIENT CHANGE REQUEST</p>
</td></tr>
<tr><td style="background-color:{brand_secondary};height:3px;"></td></tr>
<tr><td style="padding:36px 40px;background:#ffffff;">
  <p style="color:#1A1A1A;font-size:16px;margin:0 0 16px;">Hello <strong>{agent_name}</strong>, your client has requested changes to quote <strong>{quote_id}</strong>.</p>
  <div style="background:#FFF8F0;border:1px solid #F5DFB0;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
    <p style="font-size:12px;font-weight:bold;color:#888;letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;">Changes Requested:</p>
    <ul style="margin:0;padding-left:18px;">{changes_html}</ul>
    {budget_line}
    {notes_line}
  </div>
  <p style="color:#1A1A1A;font-size:14px;margin-bottom:20px;">The AI has been notified and will rebuild the quote automatically. Click below to review and approve the revised quote before sending to the client.</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
    <tr><td align="center">
      <a href="{portal_link}" style="display:inline-block;background-color:{brand_primary};color:#FFFFFF;padding:16px 32px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:14px;letter-spacing:1px;">
        🔍 REVIEW REVISED QUOTE
      </a>
    </td></tr>
  </table>
  <p style="color:#1A1A1A;font-size:13px;margin:0;">Quote reference: <strong>{quote_id}</strong></p>
</td></tr>
<tr><td style="background:#F5F0E8;padding:20px 40px;text-align:center;">
  <p style="margin:0;color:#444444;font-size:12px;">{agency_name} · Powered by SafariFlow</p>
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""

            send_email(
                to=agent_email_addr,
                subject=f"Client Requested Changes — {quote_id}",
                html=revision_email_html,
            )
            logger.info(f"Revision notification sent to {agent_email_addr}")

    return success_page('✏️', 'Changes Received!',
        'Thank you! We have received your change request. Our team will revise your quote and send you an updated version shortly.',
        quote_id)


# ─── Package Safari PDF ───────────────────────────────────────────────────────
@app.route('/generate-package-pdf', methods=['POST'])
def generate_package_pdf():
    """Stream 2 — Generate PDF from a pre-built package."""
    try:
        data = request.get_json(force=True)
        agent_id        = data.get('agent_id', '')
        package_id      = data.get('package_id', '')
        client_name     = data.get('client_name', '')
        client_email    = data.get('client_email', '')
        client_phone    = data.get('client_phone', '')
        client_nationality = data.get('client_nationality', '')
        start_date      = data.get('start_date', '')
        end_date        = data.get('end_date', '')
        pax_adults      = int(data.get('pax_adults', 2))
        pax_children    = int(data.get('pax_children', 0))
        special_requests = data.get('special_requests', [])
        request_id      = data.get('request_id', str(uuid.uuid4())[:8])

        logger.info(f"Package PDF request: agent={agent_id}, package={package_id}, client={client_name}")

        # Fetch agent
        agents = supabase_get('agents', {'id': f'eq.{agent_id}', 'select': '*'})
        if not agents:
            return jsonify({'error': 'Agent not found'}), 404
        agent = agents[0]

        # Fetch package from Supabase
        packages = supabase_get('packages', {'id': f'eq.{package_id}', 'select': '*'})
        if not packages:
            return jsonify({'error': 'Package not found'}), 404
        pkg = packages[0]

        # Calculate pricing with markup
        base_price = float(pkg.get('base_price_usd_cents', 0)) / 100
        markup_type = agent.get('markup_type', 'overall')
        markup_pct = float(agent.get('markup_overall_pct', 0) or 0) / 100
        if markup_type == 'per_category':
            markup_pct = float(agent.get('markup_accommodation_pct', 0) or 0) / 100
        total_per_person = round(base_price * (1 + markup_pct), 2)
        total_price = round(total_per_person * pax_adults, 2)
        deposit_pct = float(agent.get('deposit_percentage', 30) or 30) / 100
        deposit = round(total_price * deposit_pct, 2)
        balance = round(total_price - deposit, 2)

        duration_days = pkg.get('duration_days', 7)
        destinations = pkg.get('destination', '')

        # Build itinerary from package days
        pkg_itinerary = pkg.get('itinerary_days', [])
        if not pkg_itinerary:
            pkg_itinerary = [{'day_number': i+1, 'destination': destinations, 'title': f'Day {i+1}', 'accommodation_name': pkg.get('accommodation_name', ''), 'room_type': 'Standard Room', 'meal_plan': 'Full Board', 'nights': 1, 'transport_description': None, 'image_search_query': f'{destinations} safari wildlife'} for i in range(duration_days)]

        # Line items
        line_items = [
            {'line_type': 'accommodation', 'description': pkg.get('name', ''), 'details': f'{duration_days} nights · {destinations}', 'quantity': pax_adults, 'unit_price': total_per_person, 'total_price': total_price},
        ]

        # Personalise narrative with Claude
        narrative_prompt = f"""Write a warm, professional safari introduction for {client_name} who has booked the {pkg.get('name', '')} package.
Duration: {duration_days} days in {destinations}.
Special requests: {', '.join(special_requests) if special_requests else 'None'}.
Keep it to 3 sentences, personal and evocative. Return only the narrative text, no JSON."""

        try:
            narrative_result = call_claude(narrative_prompt, max_tokens=300)
            intro_narrative = narrative_result if isinstance(narrative_result, str) else f"{client_name.split()[0]}, your {duration_days}-day safari awaits. Every detail of your {pkg.get('name', '')} experience has been expertly arranged for an unforgettable journey."
        except Exception:
            intro_narrative = f"{client_name.split()[0]}, your {duration_days}-day safari awaits. Every detail of your {pkg.get('name', '')} experience has been expertly arranged for an unforgettable journey."

        narrative_days = [{'day_number': d.get('day_number'), 'narrative': d.get('narrative', f"Today you explore {d.get('destination', destinations)} with your expert guide."), 'highlight': d.get('highlight', f"Wildlife encounters in {d.get('destination', destinations)}"), 'accommodation_description': f"{d.get('accommodation_name', '')}, {d.get('room_type', 'Standard Room')} — your comfortable base."} for d in pkg_itinerary]

        # Tokens
        quote_number         = f"QT-PKG-{request_id}"
        approve_token        = generate_token(quote_number, 'approve')
        reject_token         = generate_token(quote_number, 'reject')
        client_accept_token  = generate_token(quote_number, 'client-accept')
        client_changes_token = generate_token(quote_number, 'client-changes')
        approve_url          = f"{API_BASE_URL}/approve?token={approve_token}"
        reject_url           = f"{API_BASE_URL}/reject?token={reject_token}"
        client_accept_url    = f"{API_BASE_URL}/client-accept?token={client_accept_token}"
        client_changes_url   = f"{API_BASE_URL}/client-changes?token={client_changes_token}"

        # Fetch photos
        photo_cache = fetch_photos_for_itinerary(pkg_itinerary)

        filename    = f"SafariFlow_Package_{quote_number}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        pdf_data = {
            'quote_id':     quote_number,
            'generated_at': start_date[:10] if start_date else '',
            'accept_url':   '#', 'changes_url': '#',
            'inclusions':   pkg.get('inclusions', '- All accommodation as specified\n- All meals as per itinerary\n- All game drives\n- Park fees'),
            'exclusions':   pkg.get('exclusions', '- International flights\n- Travel insurance\n- Personal expenses'),
            'terms':        agent.get('cancellation_terms') or 'This quote is valid for 14 days. A 30% deposit is required to confirm the booking.',
            'agent':        {'name': agent.get('agent_name', ''), 'email': agent.get('email', ''), 'phone': agent.get('phone', ''), 'agency': agent.get('agency_name', ''), 'logo_url': agent.get('logo_url', ''), 'website': agent.get('website', '')},
            'client':       {'name': client_name, 'email': client_email, 'phone': client_phone, 'pax_adults': str(pax_adults), 'pax_children': str(pax_children), 'nationality': client_nationality},
            'trip':         {'title': pkg.get('name', ''), 'start_date': start_date, 'end_date': end_date, 'duration_nights': str(duration_days), 'destinations': destinations, 'travel_style': pkg.get('category', 'Safari')},
            'itinerary':    pkg_itinerary,
            'line_items':   line_items,
            'photo_cache':  photo_cache,
            'pricing':      {'total_price_usd': total_price, 'deposit_amount_usd': deposit, 'balance_amount_usd': balance, 'within_budget': True, 'budget_notes': ''},
            'narrative':    {'intro': intro_narrative, 'days': narrative_days},
            'agent_profile': {'tagline': 'Travel & Safari Specialists', 'bio': '', 'years_experience': '', 'safaris_planned': '', 'countries_covered': '', 'awards': [], 'memberships': [], 'address': '', 'facebook': '', 'instagram': '', 'linkedin': ''},
            'agent_reviews': [],
        }

        generate_quote_pdf(pdf_data, output_path)
        pdf_url = supabase_upload(output_path, filename)

        with open(output_path, 'rb') as f:
            pdf_bytes = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # Send agent approval email
        agent_email_addr = agent.get('email', '')
        if agent_email_addr:
            email_html = agent_approval_email_html(
                agent_name=agent.get('agent_name', 'Agent'),
                agency_name=agent.get('agency_name', 'SafariFlow'),
                client_name=client_name,
                quote_number=quote_number,
                start_date=start_date,
                end_date=end_date,
                total_price=total_price,
                approve_url=approve_url,
                reject_url=reject_url,
                brand_primary=agent.get('brand_color_primary', '#2E4A7A'),
                brand_secondary=agent.get('brand_color_secondary', '#C4922A'),
            )
            send_email(
                to=agent_email_addr,
                subject=f"New Package Quote Ready — {client_name} ({quote_number})",
                html=email_html,
                attachments=[{'filename': filename, 'content': pdf_base64}]
            )

        logger.info(f"Package PDF complete: {filename}")
        return jsonify({
            'success': True,
            'filename': filename,
            'quote_number': quote_number,
            'pdf_base64': pdf_base64,
            'pdf_url': pdf_url,
            'client_name': client_name,
            'client_email': client_email,
            'agent_email': agent.get('email', ''),
            'total_price_usd': total_price,
            'deposit_usd': deposit,
            'balance_usd': balance,
            'approve_url': approve_url,
            'reject_url': reject_url,
            'client_accept_url': client_accept_url,
            'client_changes_url': client_changes_url,
        })

    except Exception as e:
        logger.error(f"Package PDF failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
