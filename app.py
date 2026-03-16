"""
SafariFlow Flask API
Accepts a minimal payload from Make.com and generates a quote PDF.

Make.com only needs to send simple direct variable references.
All complex data processing happens here in Flask.
"""

import os
import json
import uuid
import base64
import logging
import urllib.request
import urllib.error
from flask import Flask, request, jsonify
from pdf_generator import generate_quote_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

OUTPUT_DIR      = os.path.join(os.path.dirname(__file__), 'outputs')
SUPABASE_URL    = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY    = os.environ.get('SUPABASE_SERVICE_KEY', '')
STORAGE_BUCKET  = 'quote-pdfs'

os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_json_field(val):
    """Safely parse a field that may be a JSON string or already a dict/list."""
    if val is None:
        return []
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        # Strip markdown code fences if Claude wrapped the JSON
        cleaned = val.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            cleaned = '\n'.join(lines).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return []
    return []


def upload_to_supabase(file_path, filename):
    """Upload PDF to Supabase Storage. Returns public URL or empty string."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not set — skipping upload")
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{filename}"
        logger.info(f"Uploaded to Supabase: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Supabase upload error: {str(e)}")
        return ''


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'SafariFlow PDF Generator'})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON body received'}), 400

        # ── Debug logging — remove after confirming data flow ─────────────────
        logger.info(f"PAYLOAD KEYS: {list(data.keys())}")
        logger.info(f"client_name: {data.get('client_name', 'MISSING')}")
        logger.info(f"itinerary_json length: {len(str(data.get('itinerary_json', '')))} chars")
        logger.info(f"line_items_json length: {len(str(data.get('line_items_json', '')))} chars")
        logger.info(f"intro_narrative: {str(data.get('intro_narrative', 'MISSING'))[:100]}")
        logger.info(f"total_price_usd: {data.get('total_price_usd', 'MISSING')}")
        logger.info(f"destination: {data.get('destination', 'MISSING')}")

        # ── Extract fields from Make.com payload ──────────────────────────────
        # Agent fields from Supabase-Fetch Agent (Module 42)
        agent_name   = data.get('agent_name', '')
        agent_email  = data.get('agent_email', '')
        agent_phone  = data.get('agent_phone', '')
        agency_name  = data.get('agency_name', '')
        agent_logo   = data.get('agent_logo_url', '')

        # Client fields from safariflow-intake (Module 1)
        client_name        = data.get('client_name', '')
        client_email       = data.get('client_email', '')
        client_phone       = data.get('client_phone', '')
        client_nationality = data.get('client_nationality', '')
        pax_adults         = data.get('pax_adults', '2')
        pax_children       = data.get('pax_children', '0')

        # Trip fields
        destination       = data.get('destination', '')
        start_date        = data.get('start_date', '')
        end_date          = data.get('end_date', '')
        duration_days     = data.get('duration_days', '')
        accommodation_tier= data.get('accommodation_tier', 'luxury')
        budget_usd        = data.get('budget_usd', '')
        special_requests  = data.get('special_requests', '')
        request_id        = data.get('request_id', str(uuid.uuid4())[:8].upper())

        # Claude outputs — parse safely regardless of format
        itinerary      = parse_json_field(data.get('itinerary_json'))
        line_items     = parse_json_field(data.get('line_items_json'))
        intro_narrative= data.get('intro_narrative', '')
        narrative_days = parse_json_field(data.get('narrative_days_json'))

        # Pricing
        total_price    = float(data.get('total_price_usd', 0) or 0)
        deposit_amount = round(total_price * 0.30, 2)
        balance_amount = round(total_price - deposit_amount, 2)

        # ── Build structured payload for pdf_generator ────────────────────────
        pdf_data = {
            'quote_id':     request_id,
            'generated_at': data.get('quote_date', ''),
            'accept_url':   data.get('accept_url', '#'),
            'changes_url':  data.get('changes_url', '#'),
            'inclusions':   data.get('inclusions', ''),
            'exclusions':   data.get('exclusions', ''),
            'terms':        data.get('notes', 'This quote is valid for 14 days.'),

            'agent': {
                'name':    agent_name,
                'email':   agent_email,
                'phone':   agent_phone,
                'agency':  agency_name,
                'logo_url':agent_logo,
                'website': data.get('agent_website', ''),
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
                'title':           f"{duration_days}-Day {destination} Safari",
                'start_date':      start_date,
                'end_date':        end_date,
                'duration_nights': str(duration_days),
                'destinations':    destination,
                'travel_style':    accommodation_tier.title(),
            },

            'itinerary':  itinerary,
            'line_items': line_items,

            'pricing': {
                'total_price_usd':    total_price,
                'deposit_amount_usd': deposit_amount,
                'balance_amount_usd': balance_amount,
                'within_budget':      True,
                'budget_notes':       '',
            },

            'narrative': {
                'intro': intro_narrative,
                'days':  narrative_days,
            },

            'agent_profile': data.get('agent_profile', {}),
            'agent_reviews': data.get('agent_reviews', []),
        }

        # ── Generate PDF ──────────────────────────────────────────────────────
        quote_number = f"QT-{request_id}"
        filename     = f"SafariFlow_Quote_{quote_number}.pdf"
        output_path  = os.path.join(OUTPUT_DIR, filename)

        generate_quote_pdf(pdf_data, output_path)

        # ── Upload to Supabase Storage ────────────────────────────────────────
        pdf_url = upload_to_supabase(output_path, filename)

        # ── Return base64 + metadata to Make.com ─────────────────────────────
        with open(output_path, 'rb') as f:
            pdf_bytes  = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        logger.info(f"PDF generated: {filename} ({len(pdf_bytes)} bytes)")

        return jsonify({
            'success':      True,
            'filename':     filename,
            'quote_number': quote_number,
            'pdf_base64':   pdf_base64,
            'pdf_url':      pdf_url,
            'file_size':    len(pdf_bytes),
            'client_name':  client_name,
            'agent_email':  agent_email,
            'quote_date':   data.get('quote_date', ''),
        })

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
