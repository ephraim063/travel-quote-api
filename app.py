from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import io
import traceback
from pdf_generator import generate_quote_pdf, generate_itinerary_pdf
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY", "dev-key-change-in-production")

def require_api_key(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Travel Quote PDF API",
        "version": "1.0.0",
        "endpoints": ["/generate-quote", "/generate-itinerary", "/health"]
    })


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})


@app.route("/generate-quote", methods=["POST"])
@require_api_key
def generate_quote():
    """
    Generate a travel quote PDF.
    
    Expected JSON body:
    {
        "client_name": "John Smith",
        "client_email": "john@example.com",
        "quote_number": "Q-2024-001",
        "quote_date": "2024-01-15",
        "valid_until": "2024-01-29",
        "agent_name": "Sarah Johnson",
        "agent_email": "sarah@travelagency.com",
        "agency_name": "Luxury Travel Co.",
        "destination": "Bali, Indonesia",
        "travel_dates": "March 15 - March 25, 2024",
        "num_travelers": 2,
        "items": [
            {
                "description": "Return flights (JNB → DPS)",
                "details": "Economy class, direct flight",
                "unit_price": 15000,
                "quantity": 2
            },
            {
                "description": "5-Star Resort - 10 nights",
                "details": "Deluxe ocean view room, breakfast included",
                "unit_price": 8500,
                "quantity": 1
            }
        ],
        "notes": "Price includes airport transfers. Visa fees not included.",
        "currency": "ZAR",
        "currency_symbol": "R"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        required = ["client_name", "quote_number", "items", "agency_name"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        pdf_buffer = generate_quote_pdf(data)

        filename = f"quote_{data.get('quote_number', 'draft')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/generate-itinerary", methods=["POST"])
@require_api_key
def generate_itinerary():
    """
    Generate a detailed travel itinerary PDF.
    
    Expected JSON body:
    {
        "client_name": "John Smith",
        "itinerary_number": "IT-2024-001",
        "agency_name": "Luxury Travel Co.",
        "agent_name": "Sarah Johnson",
        "agent_email": "sarah@travelagency.com",
        "destination": "Bali, Indonesia",
        "travel_dates": "March 15 - March 25, 2024",
        "num_travelers": 2,
        "days": [
            {
                "day_number": 1,
                "date": "March 15, 2024",
                "title": "Arrival in Bali",
                "activities": [
                    {
                        "time": "14:00",
                        "title": "Arrive at Ngurah Rai International Airport",
                        "description": "Meet & greet by our local representative. Transfer to hotel."
                    },
                    {
                        "time": "16:00",
                        "title": "Check-in at The Mulia Resort",
                        "description": "5-star beachfront resort in Nusa Dua"
                    }
                ]
            }
        ],
        "inclusions": ["Airport transfers", "Daily breakfast", "Local guide"],
        "exclusions": ["International flights", "Travel insurance", "Personal expenses"],
        "important_notes": "Please ensure all travelers have valid passports."
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        required = ["client_name", "itinerary_number", "days", "agency_name"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        pdf_buffer = generate_itinerary_pdf(data)

        filename = f"itinerary_{data.get('itinerary_number', 'draft')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
