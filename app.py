import os
import json
import uuid
import base64
import logging
from flask import Flask, request, jsonify
from pdf_generator import generate_quote_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'SafariFlow PDF Generator'})


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON body received'}), 400

        required_keys = ['agency_name', 'client_name', 'days', 'items']
        missing = [k for k in required_keys if k not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {missing}'}), 400

        quote_number = data.get('quote_number', str(uuid.uuid4())[:8].upper())
        filename     = f"SafariFlow_Quote_{quote_number}.pdf"
        output_path  = os.path.join(OUTPUT_DIR, filename)

        generate_quote_pdf(data, output_path)

        # Read and encode as base64 so Make.com can receive and store in Supabase
        with open(output_path, 'rb') as f:
            pdf_bytes   = f.read()
            pdf_base64  = base64.b64encode(pdf_bytes).decode('utf-8')

        logger.info(f"PDF generated successfully: {filename} ({len(pdf_bytes)} bytes)")

        return jsonify({
            'success':      True,
            'filename':     filename,
            'quote_number': quote_number,
            'pdf_base64':   pdf_base64,
            'file_size':    len(pdf_bytes),
            'client_name':  data.get('client_name', ''),
            'agent_email':  data.get('agent_email', ''),
            'quote_date':   data.get('quote_date', ''),
        })

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
