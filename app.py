"""
SafariFlow Flask API v4 — Full Internal Engine
Flask handles everything:
  1. Receives simple trigger from Make.com
  2. Fetches agent profile + reviews from Supabase
  3. Fetches accommodations, transport, park fees from Supabase
  4. Calls Claude 2 to build itinerary + pricing
  5. Calls Claude 3 to write narrative
  6. Fetches destination photos from Unsplash
  7. Generates complete PDF
  8. Uploads PDF to Supabase Storage
  9. Returns PDF URL + metadata to Make.com

Make.com only needs to send:
  - agent_id
  - client details
  - trip details
"""

import os
import io
import json
import uuid
import base64
import logging
import urllib.request
import urllib.error
import urllib.parse
from flask import Flask, request, jsonify
from pdf_generator import generate_quote_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Environment variables ────────────────────────────────────────────────────
SUPABASE_URL       = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY       = os.environ.get('SUPABASE_SERVICE_KEY', '')
ANTHROPIC_API_KEY  = os.environ.get('ANTHROPIC_API_KEY', '')
UNSPLASH_ACCESS_KEY= os.environ.get('UNSPLASH_ACCESS_KEY', '')
STORAGE_BUCKET     = 'quote-pdfs'
OUTPUT_DIR         = os.path.join(os.path.dirname(__file__), 'outputs')

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── Supabase helpers ─────────────────────────────────────────────────────────
def supabase_get(table, params=None):
    """Fetch rows from a Supabase table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning(f"Supabase credentials missing — skipping {table} fetch")
        return []
    try:
        query = f"{SUPABASE_URL}/rest/v1/{table}"
        if params:
            query += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            query,
            headers={
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'apikey': SUPABASE_KEY,
                'Content-Type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Supabase fetch error ({table}): {str(e)}")
        return []


def supabase_upload(file_path, filename):
    """Upload PDF to Supabase Storage. Returns public URL."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return ''
    try:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{filename}"
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        req = urllib.request.Request(
            upload_url, data=pdf_bytes, method='POST',
            headers={
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/pdf',
                'x-upsert': 'true',
            }
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{filename}"
        logger.info(f"Uploaded to Supabase Storage: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Supabase upload error: {str(e)}")
        return ''


# ─── Claude API helper ────────────────────────────────────────────────────────
def call_claude(prompt, max_tokens=4000):
    """Call Claude API and return parsed JSON response."""
    if not ANTHROPIC_API_KEY:
        logger.warning("Anthropic API key missing")
        return {}
    try:
        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            method='POST',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())

        text = result.get('content', [{}])[0].get('text', '{}')

        # Strip markdown fences if present
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            text = '\n'.join(lines).strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"Claude JSON parse error: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Claude API error: {str(e)}")
        return {}


# ─── Unsplash photo fetcher ───────────────────────────────────────────────────
def fetch_photo(query):
    """Fetch a destination photo from Unsplash. Returns image bytes or None."""
    try:
        if UNSPLASH_ACCESS_KEY:
            # Use official API if key available
            url = (f"https://api.unsplash.com/photos/random"
                   f"?query={urllib.parse.quote(query)}&orientation=landscape"
                   f"&client_id={UNSPLASH_ACCESS_KEY}")
            req = urllib.request.Request(url, headers={'User-Agent': 'SafariFlow/4.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                photo_url = data['urls']['regular']
        else:
            # Fallback to source.unsplash.com
            clean = urllib.parse.quote(query.replace(' ', ','))
            photo_url = f"https://source.unsplash.com/800x400/?{clean}"

        req = urllib.request.Request(photo_url, headers={'User-Agent': 'SafariFlow/4.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()

    except Exception as e:
        logger.warning(f"Photo fetch failed for '{query}': {str(e)}")
        return None


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'SafariFlow PDF Generator v4'})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON body received'}), 400

        # ── Extract basic fields from Make.com ────────────────────────────────
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

        # ── Step 1: Fetch agent data from Supabase ────────────────────────────
        logger.info("Fetching agent data...")
        agents = supabase_get('agents', {'id': f'eq.{agent_id}', 'select': '*'})
        agent  = agents[0] if agents else {}

        profiles = supabase_get('agent_profiles', {'agent_id': f'eq.{agent_id}', 'select': '*'})
        profile  = profiles[0] if profiles else {}

        reviews = supabase_get('agent_reviews', {'agent_id': f'eq.{agent_id}', 'select': '*', 'limit': '3'})

        # ── Step 2: Fetch pricing data from Supabase ──────────────────────────
        logger.info("Fetching pricing data...")
        accommodations = supabase_get('accommodations', {
            'agent_id': f'eq.{agent_id}',
            'is_active': 'eq.true',
            'select': '*'
        })

        transport = supabase_get('transport_routes', {
            'agent_id': f'eq.{agent_id}',
            'is_active': 'eq.true',
            'select': '*'
        })

        park_fees = supabase_get('park_fees', {
            'agent_id': f'eq.{agent_id}',
            'select': '*'
        })

        logger.info(f"Found: {len(accommodations)} accommodations, {len(transport)} transport, {len(park_fees)} park fees")

        # ── Step 3: Call Claude 2 — Build Itinerary ───────────────────────────
        logger.info("Calling Claude 2 — Build Itinerary...")

        # Convert cents to USD for Claude
        accom_for_claude = []
        for a in accommodations:
            accom_for_claude.append({
                'name': a.get('name'),
                'destination': a.get('destination'),
                'category': a.get('category'),
                'room_type': a.get('room_type'),
                'meal_plan': a.get('meal_plan'),
                'price_per_person_usd': round((a.get('price_per_person_usd_cents') or 0) / 100, 2),
            })

        transport_for_claude = []
        for t in transport:
            transport_for_claude.append({
                'from': t.get('from_location'),
                'to': t.get('to_location'),
                'type': t.get('transport_type'),
                'operator': t.get('operator_name'),
                'price_per_person_usd': round((t.get('price_per_person_usd_cents') or 0) / 100, 2),
                'duration_hours': t.get('duration_hours'),
            })

        fees_for_claude = []
        for f in park_fees:
            fees_for_claude.append({
                'park': f.get('park_name'),
                'destination': f.get('destination'),
                'visitor_category': f.get('visitor_category'),
                'fee_per_person_per_day_usd': round((f.get('fee_per_person_per_day_usd_cents') or 0) / 100, 2),
            })

        claude2_prompt = f"""You are a safari itinerary pricing specialist. Build the optimal itinerary using ONLY the exact pricing data provided below.

Return ONLY a valid JSON object. No explanation. No markdown. No code fences. No backticks. Start your response with {{ and end with }}.

Structure:
{{
  "itinerary": [
    {{
      "day_number": 1,
      "date": "YYYY-MM-DD",
      "destination": "string",
      "title": "string",
      "accommodation_name": "string",
      "room_type": "string",
      "meal_plan": "string",
      "nights": 1,
      "transport_description": "string or null",
      "image_search_query": "string"
    }}
  ],
  "line_items": [
    {{
      "line_type": "accommodation|transport|park_fee",
      "description": "string",
      "details": "string",
      "quantity": 2,
      "unit_price": 1950.00,
      "total_price": 3900.00
    }}
  ],
  "total_price_usd": 0,
  "deposit_amount_usd": 0,
  "balance_amount_usd": 0,
  "within_budget": true,
  "budget_notes": "string or null"
}}

RULES:
- Sequence destinations in logical geographic order
- Select best-value accommodation matching the tier requested
- Calculate all transport between destinations
- Include park fees for all applicable destinations
- Check total against client budget
- If over budget: select lower-tier options and note in budget_notes
- deposit_amount_usd = total * 0.30

TRIP REQUIREMENTS:
{json.dumps({
    "destinations": destinations,
    "duration_days": duration_days,
    "start_date": start_date,
    "end_date": end_date,
    "pax_adults": pax_adults,
    "pax_children": pax_children,
    "accommodation_tier": accommodation_tier,
    "budget_usd": budget_usd,
    "special_requests": special_requests,
    "visitor_category": "non_resident" if client_nationality.lower() not in ['kenyan', 'tanzanian', 'ugandan'] else "resident"
}, indent=2)}

AVAILABLE ACCOMMODATIONS:
{json.dumps(accom_for_claude, indent=2)}

AVAILABLE TRANSPORT:
{json.dumps(transport_for_claude, indent=2)}

PARK FEES:
{json.dumps(fees_for_claude, indent=2)}"""

        itinerary_data = call_claude(claude2_prompt, max_tokens=4000)

        itinerary  = itinerary_data.get('itinerary', [])
        line_items = itinerary_data.get('line_items', [])
        total_price= float(itinerary_data.get('total_price_usd', 0) or 0)
        deposit    = float(itinerary_data.get('deposit_amount_usd', 0) or round(total_price * 0.30, 2))
        balance    = float(itinerary_data.get('balance_amount_usd', 0) or round(total_price - deposit, 2))

        logger.info(f"Itinerary built: {len(itinerary)} days, total ${total_price}")

        # ── Step 4: Call Claude 3 — Write Narrative ───────────────────────────
        logger.info("Calling Claude 3 — Write Narrative...")

        claude3_prompt = f"""You are a luxury safari copywriter. Write compelling narrative text for this safari itinerary.

Return ONLY a valid JSON object. No explanation. No markdown. No code fences. No backticks. Start your response with {{ and end with }}.

Structure:
{{
  "intro_narrative": "2-3 sentence personalised opening addressing client by first name",
  "days": [
    {{
      "day_number": 1,
      "narrative": "2-3 sentence description of the day",
      "highlight": "One memorable highlight line — max 12 words",
      "accommodation_description": "Property name, room type, one evocative sentence"
    }}
  ]
}}

TONE: Warm, aspirational, professional. Use client first name.
Never use clichés like 'breathtaking' or 'once in a lifetime'.
Focus on sensory details, wildlife, authentic African experiences.

CLIENT NAME: {client_name}
SPECIAL REQUESTS: {special_requests}

ITINERARY:
{json.dumps(itinerary, indent=2)}"""

        narrative_data = call_claude(claude3_prompt, max_tokens=3000)

        intro_narrative = narrative_data.get('intro_narrative', '')
        narrative_days  = narrative_data.get('days', [])

        logger.info(f"Narrative written: {len(narrative_days)} days")

        # ── Step 5: Fetch destination photos ──────────────────────────────────
        # ── Step 5: Photos disabled for speed — re-enable after pipeline confirmed ────
        logger.info("Photos disabled for speed testing...")
        photo_cache = {}

        # ── Step 6: Build complete PDF data structure ─────────────────────────
        quote_number = f"QT-{request_id}"
        filename     = f"SafariFlow_Quote_{quote_number}.pdf"
        output_path  = os.path.join(OUTPUT_DIR, filename)

        # Parse reviews for trust page
        reviews_formatted = []
        for r in reviews:
            reviews_formatted.append({
                'review_text':   r.get('review_text', ''),
                'client_name':   r.get('client_name', ''),
                'client_origin': r.get('client_origin', ''),
                'trip_summary':  r.get('trip_summary', ''),
            })

        pdf_data = {
            'quote_id':     quote_number,
            'generated_at': start_date[:10] if start_date else '',
            'accept_url':   '#',
            'changes_url':  '#',
            'inclusions':   '- All accommodation as specified\n- All meals as per itinerary\n- All game drives\n- Park and conservancy fees\n- Internal flights as specified\n- Airport transfers',
            'exclusions':   '- International flights\n- Travel insurance\n- Visa fees\n- Personal expenses\n- Gratuities',
            'terms':        'This quote is valid for 14 days. A 30% deposit is required to confirm the booking. Balance due 60 days prior to departure.',

            'agent': {
                'name':    agent.get('agent_name', ''),
                'email':   agent.get('email', ''),
                'phone':   agent.get('phone', ''),
                'agency':  agent.get('agency_name', ''),
                'logo_url':agent.get('logo_url', ''),
                'website': agent.get('website', ''),
            },

            'client': {
                'name':        client_name,
                'email':       client_email,
                'phone':       client_phone,
                'pax_adults':  str(pax_adults),
                'pax_children':str(pax_children),
                'nationality': client_nationality,
            },

            'trip': {
                'title':           f"{duration_days}-Day {destinations} Safari",
                'start_date':      start_date,
                'end_date':        end_date,
                'duration_nights': str(duration_days),
                'destinations':    destinations,
                'travel_style':    accommodation_tier.title(),
            },

            'itinerary':    itinerary,
            'line_items':   line_items,
            'photo_cache':  photo_cache,

            'pricing': {
                'total_price_usd':    total_price,
                'deposit_amount_usd': deposit,
                'balance_amount_usd': balance,
                'within_budget':      itinerary_data.get('within_budget', True),
                'budget_notes':       itinerary_data.get('budget_notes', ''),
            },

            'narrative': {
                'intro': intro_narrative,
                'days':  narrative_days,
            },

            'agent_profile': {
                'tagline':          profile.get('tagline', 'Travel & Safari Specialists'),
                'bio':              profile.get('bio', ''),
                'years_experience': profile.get('years_experience', ''),
                'safaris_planned':  profile.get('safaris_planned', ''),
                'countries_covered':profile.get('countries_covered', ''),
                'awards':           profile.get('awards', []),
                'memberships':      profile.get('memberships', []),
                'address':          profile.get('address', ''),
                'facebook':         profile.get('facebook', ''),
                'instagram':        profile.get('instagram', ''),
                'linkedin':         profile.get('linkedin', ''),
            },

            'agent_reviews': reviews_formatted,
        }

        # ── Step 7: Generate PDF ──────────────────────────────────────────────
        logger.info("Generating PDF...")
        generate_quote_pdf(pdf_data, output_path)

        # ── Step 8: Upload to Supabase Storage ────────────────────────────────
        pdf_url = supabase_upload(output_path, filename)

        # ── Step 9: Return result to Make.com ─────────────────────────────────
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
            'agent_email':    agent.get('email', ''),
            'quote_date':     start_date[:10] if start_date else '',
            'total_price_usd':total_price,
            'itinerary_days': len(itinerary),
        })

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
