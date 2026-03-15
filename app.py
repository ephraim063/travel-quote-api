import os
import json
import uuid
import logging
from flask import Flask, request, jsonify, send_file
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

        quote_id = data.get('quote_id') or str(uuid.uuid4())[:8].upper()
        filename = f"SafariFlow_Quote_{quote_id}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)

        generate_quote_pdf(data, output_path)

        logger.info(f"PDF generated successfully: {filename}")

        return send_file(
            output_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
