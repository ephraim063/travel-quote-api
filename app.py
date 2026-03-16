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
API_BASE_URL        = os.environ.get('API_BASE_URL', 'https://travel-quote-api.onrender.com')
PORTAL_URL          = os.environ.get('PORTAL_URL', 'https://safariflow-portal.netlify.app')
STORAGE_BUCKET      = 'quote-pdfs'
OUTPUT_DIR          = os.path.join(os.path.dirname(__file__), 'outputs')
TOKEN_EXPIRY_DAYS   = 14

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
        return False
    try:
        query = f"{SUPABASE_URL}/rest/v1/{table}?" + urllib.parse.urlencode(match_params)
        payload = json.dumps(update_data).encode('utf-8')
        req = urllib.request.Request(query, data=payload, method='PATCH', headers={
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'apikey': SUPABASE_KEY,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = resp.read()
            logger.info(f"Supabase update response: {result}")
        return True
    except Exception as e:
        logger.error(f"Supabase update error ({table}): {str(e)}")
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
        deposit    = float(itinerary_data.get('deposit_amount_usd', 0) or round(total_price * 0.30, 2))
        balance    = float(itinerary_data.get('balance_amount_usd', 0) or round(total_price - deposit, 2))

        logger.info(f"Itinerary built: {len(itinerary)} days, total ${total_price}")

        first_name = client_name.split()[0] if client_name else "Dear Guest"
        intro_narrative = f"{first_name}, your {duration_days}-day safari across {destinations} has been carefully crafted to deliver an authentic East African experience. Every detail has been arranged to ensure your journey is seamless and unforgettable."
        narrative_days = [{'day_number': d.get('day_number'), 'narrative': f"Today you explore {d.get('destination')} with your expert guide, discovering the remarkable wildlife and landscapes that make this destination truly special.", 'highlight': f"Wildlife encounters in {d.get('destination')}", 'accommodation_description': f"{d.get('accommodation_name')}, {d.get('room_type')} — your comfortable base for the night."} for d in itinerary]

        quote_number  = f"QT-{request_id}"
        approve_token = generate_token(quote_number, 'approve')
        reject_token  = generate_token(quote_number, 'reject')
        approve_url   = f"{API_BASE_URL}/approve?token={approve_token}"
        reject_url    = f"{API_BASE_URL}/reject?token={reject_token}"

        logger.info(f"Approval tokens generated for {quote_number}")

        filename    = f"SafariFlow_Quote_{quote_number}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        reviews_formatted = [{'review_text': r.get('review_text', ''), 'client_name': r.get('client_name', ''), 'client_origin': r.get('client_origin', ''), 'trip_summary': r.get('trip_summary', '')} for r in reviews]

        pdf_data = {
            'quote_id':     quote_number,
            'generated_at': start_date[:10] if start_date else '',
            'accept_url':   '#',
            'changes_url':  '#',
            'inclusions':   '- All accommodation as specified\n- All meals as per itinerary\n- All game drives\n- Park and conservancy fees\n- Internal flights as specified\n- Airport transfers',
            'exclusions':   '- International flights\n- Travel insurance\n- Visa fees\n- Personal expenses\n- Gratuities',
            'terms':        'This quote is valid for 14 days. A 30% deposit is required to confirm the booking. Balance due 60 days prior to departure.',
            'agent':        {'name': agent.get('agent_name', ''), 'email': agent.get('email', ''), 'phone': agent.get('phone', ''), 'agency': agent.get('agency_name', ''), 'logo_url': agent.get('logo_url', ''), 'website': agent.get('website', '')},
            'client':       {'name': client_name, 'email': client_email, 'phone': client_phone, 'pax_adults': str(pax_adults), 'pax_children': str(pax_children), 'nationality': client_nationality},
            'trip':         {'title': f"{duration_days}-Day {destinations} Safari", 'start_date': start_date, 'end_date': end_date, 'duration_nights': str(duration_days), 'destinations': destinations, 'travel_style': accommodation_tier.title()},
            'itinerary':    itinerary,
            'line_items':   line_items,
            'photo_cache':  {},
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

        return jsonify({
            'success':        True,
            'filename':       filename,
            'quote_number':   quote_number,
            'pdf_base64':     pdf_base64,
            'pdf_url':        pdf_url,
            'file_size':      len(pdf_bytes),
            'client_name':    client_name,
            'client_email':   client_email,
            'agent_email':    agent.get('email', ''),
            'agent_name':     agent.get('agent_name', ''),
            'agency_name':    agent.get('agency_name', ''),
            'quote_date':     start_date[:10] if start_date else '',
            'total_price_usd':total_price,
            'deposit_usd':    deposit,
            'balance_usd':    balance,
            'itinerary_days': len(itinerary),
            'approve_url':    approve_url,
            'reject_url':     reject_url,
            'destinations':   destinations,
            'start_date':     start_date,
            'end_date':       end_date,
        })

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ─── Agent Approve endpoint ───────────────────────────────────────────────────
@app.route('/approve', methods=['GET'])
def approve():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'approve')

    if not quote_id:
        return '''<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#c0392b">Invalid or Expired Link</h2>
            <p>This approval link is invalid or has expired.</p>
        </body></html>''', 400

    result = supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {
        'status': 'sent'
    })
    logger.info(f"Supabase update result for {quote_id}: {result}")

    trigger_make_webhook(MAKE_S2_WEBHOOK, {
        'event': 'quote_approved',
        'quote_number': quote_id,
        'approved_at': int(time.time()),
    })

    logger.info(f"Quote approved: {quote_id}")

    return '''<html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#f9f9f9">
        <div style="max-width:500px;margin:0 auto;background:white;padding:40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.1)">
            <div style="font-size:48px;margin-bottom:16px">&#x2705;</div>
            <h2 style="color:#1B2A47;margin-bottom:8px">Quote Approved</h2>
            <p style="color:#666">The quote has been approved and will be sent to the client shortly.</p>
            <p style="color:#C4922A;font-weight:bold;font-size:14px">''' + quote_id + '''</p>
        </div>
    </body></html>'''


# ─── Agent Reject endpoint ────────────────────────────────────────────────────
@app.route('/reject', methods=['GET'])
def reject():
    token = request.args.get('token', '')
    quote_id = verify_token(token, 'reject')

    if not quote_id:
        return '''<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#c0392b">Invalid or Expired Link</h2>
            <p>This link is invalid or has expired.</p>
        </body></html>''', 400

    result = supabase_update('quotes', {'quote_number': f'eq.{quote_id}'}, {
        'status': 'revision_requested'
    })
    logger.info(f"Supabase update result for {quote_id}: {result}")

    trigger_make_webhook(MAKE_S2_WEBHOOK, {
        'event': 'quote_rejected',
        'quote_number': quote_id,
        'rejected_at': int(time.time()),
    })

    logger.info(f"Quote rejected: {quote_id}")

    return '''<html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#f9f9f9">
        <div style="max-width:500px;margin:0 auto;background:white;padding:40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.1)">
            <div style="font-size:48px;margin-bottom:16px">&#x270F;&#xFE0F;</div>
            <h2 style="color:#1B2A47;margin-bottom:8px">Revision Requested</h2>
            <p style="color:#666">The quote has been flagged for revision. You will be notified when it is ready to review again.</p>
            <p style="color:#C4922A;font-weight:bold;font-size:14px">''' + quote_id + '''</p>
        </div>
    </body></html>'''


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
