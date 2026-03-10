# ─────────────────────────────────────────────────────────────────
# SafariFlow — Flask API (Updated app.py)
# Deploy to Render — replaces your existing app.py
# ─────────────────────────────────────────────────────────────────

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pdf_generator import generate_quote_pdf, generate_itinerary_pdf
import os
import jwt
import requests as req
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)

# ── Config ────────────────────────────────────────────────────────
API_KEY              = os.environ.get("API_KEY", "tqa-2024-secure-key-change-me-now")
SECRET_KEY           = os.environ.get("APPROVAL_SECRET", "safariflow-approval-secret-2026")
MAKE_SCENARIO2_URL   = os.environ.get("MAKE_SCENARIO2_WEBHOOK", "")
PORTAL_URL           = os.environ.get("PORTAL_URL", "https://cosmic-figolla-71951d.netlify.app")
API_BASE_URL         = os.environ.get("API_BASE_URL", "https://travel-quote-api.onrender.com")


# ── Auth Decorator ────────────────────────────────────────────────
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Token Helpers ─────────────────────────────────────────────────
def make_token(quote_number, agent_email, action):
    payload = {
        "quote_number": quote_number,
        "agent_email":  agent_email,
        "action":       action,
        "exp":          datetime.utcnow() + timedelta(days=7),
        "iat":          datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"]), None
    except jwt.ExpiredSignatureError:
        return None, "This approval link has expired (7 day limit)."
    except jwt.InvalidTokenError:
        return None, "Invalid approval link."


# ══════════════════════════════════════════════════════════════════
# EXISTING ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "SafariFlow API", "version": "2.0"})


@app.route("/generate-quote", methods=["POST"])
@require_api_key
def generate_quote():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        pdf_buffer = generate_quote_pdf(data)
        return Response(
            pdf_buffer.read(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=quote-{data.get('quote_number','draft')}.pdf"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate-itinerary", methods=["POST"])
@require_api_key
def generate_itinerary():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        pdf_buffer = generate_itinerary_pdf(data)
        return Response(
            pdf_buffer.read(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=itinerary-{data.get('itinerary_number','draft')}.pdf"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# NEW ROUTES — APPROVAL SYSTEM
# ══════════════════════════════════════════════════════════════════

@app.route("/generate-approval-links", methods=["POST"])
@require_api_key
def generate_approval_links():
    """
    Called by Make.com after PDF is generated.
    Returns approve/edit/reject URLs for the agent email.
    """
    data         = request.get_json()
    quote_number = data.get("quote_number")
    agent_email  = data.get("agent_email")

    if not quote_number or not agent_email:
        return jsonify({"error": "quote_number and agent_email required"}), 400

    approve_token = make_token(quote_number, agent_email, "approve")
    reject_token  = make_token(quote_number, agent_email, "reject")

    return jsonify({
        "approve_url": f"{API_BASE_URL}/approve?token={approve_token}",
        "edit_url":    f"{PORTAL_URL}/drafts/{quote_number}",
        "reject_url":  f"{API_BASE_URL}/reject?token={reject_token}",
        "quote_number": quote_number,
    })


@app.route("/approve", methods=["GET"])
def approve_quote():
    """
    Agent clicks APPROVE in email → lands here →
    triggers Make.com Scenario 2 → sends quote to client
    """
    token = request.args.get("token")
    if not token:
        return page_html("error", "Missing token", "No approval token was provided.")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Problem", error)

    quote_number = payload["quote_number"]
    agent_email  = payload["agent_email"]

    # Fire Make.com Scenario 2
    if MAKE_SCENARIO2_URL:
        try:
            req.post(MAKE_SCENARIO2_URL, json={
                "quote_number": quote_number,
                "agent_email":  agent_email,
                "action":       "approved",
                "approved_at":  datetime.utcnow().isoformat(),
            }, timeout=15)
        except Exception as e:
            print(f"[WARN] Scenario 2 webhook failed: {e}")

    return page_html(
        "approved",
        "Quote Approved! ✅",
        f"Quote <b>{quote_number}</b> has been approved.",
        f"The client will receive their quote and itinerary within minutes.",
    )


@app.route("/reject", methods=["GET"])
def reject_quote():
    """
    Agent clicks REJECT → sees reason form → submits →
    updates Sheets via Make.com
    """
    token  = request.args.get("token")
    reason = request.args.get("reason", "").strip()

    if not token:
        return page_html("error", "Missing token", "No rejection token was provided.")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Problem", error)

    quote_number = payload["quote_number"]

    # If reason submitted → process rejection
    if reason:
        if MAKE_SCENARIO2_URL:
            try:
                req.post(MAKE_SCENARIO2_URL, json={
                    "quote_number": quote_number,
                    "agent_email":  payload["agent_email"],
                    "action":       "rejected",
                    "reason":       reason,
                    "rejected_at":  datetime.utcnow().isoformat(),
                }, timeout=15)
            except Exception as e:
                print(f"[WARN] Scenario 2 webhook failed: {e}")

        return page_html(
            "rejected",
            "Quote Rejected",
            f"Quote <b>{quote_number}</b> has been marked as unavailable.",
            f"Reason logged: {reason}",
        )

    # Show rejection reason form
    return rejection_form(quote_number, token)


# ══════════════════════════════════════════════════════════════════
# HTML PAGES
# ══════════════════════════════════════════════════════════════════

def page_html(status, title, message, sub=""):
    NAVY = "#0D1E35"
    GOLD = "#C8A96E"
    colors = {
        "approved": ("#27AE60", "✅"),
        "rejected": ("#E05C2A", "❌"),
        "error":    ("#999",    "⚠️"),
    }
    color, icon = colors.get(status, ("#999", "⚠️"))

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SafariFlow — {title}</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:48px 40px;
      max-width:460px;width:100%;text-align:center;
      box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:11px;font-weight:700;letter-spacing:2.5px;
      color:{GOLD};margin-bottom:28px}}
    .icon{{font-size:52px;margin-bottom:16px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);
      margin:20px 0}}
    h1{{font-size:22px;color:{NAVY};margin-bottom:8px;font-weight:700}}
    .msg{{font-size:14px;color:#444;line-height:1.6;margin-bottom:6px}}
    .sub{{font-size:12px;color:#999;line-height:1.5;margin-bottom:28px}}
    .badge{{display:inline-block;background:{color}18;color:{color};
      border:1px solid {color}33;padding:5px 18px;border-radius:20px;
      font-size:12px;font-weight:700;letter-spacing:1px;margin-bottom:28px}}
    .btn{{display:inline-block;background:{NAVY};color:white;
      padding:12px 28px;border-radius:8px;text-decoration:none;
      font-size:13px;font-weight:600}}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">SAFARIFLOW TRAVEL</div>
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <div class="divider"></div>
    <p class="msg">{message}</p>
    <p class="sub">{sub}</p>
    <div class="badge">{status.upper()}</div><br>
    <a href="{PORTAL_URL}/quotes" class="btn">Go to Portal →</a>
  </div>
</body>
</html>"""


def rejection_form(quote_number, token):
    NAVY = "#0D1E35"
    GOLD = "#C8A96E"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SafariFlow — Reject Quote</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:40px;
      max-width:460px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:11px;font-weight:700;letter-spacing:2.5px;
      color:{GOLD};margin-bottom:20px}}
    h1{{font-size:22px;color:{NAVY};margin-bottom:6px}}
    .sub{{font-size:13px;color:#999;margin-bottom:24px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);margin:20px 0}}
    .ref{{background:#f8f8f6;border-left:3px solid {GOLD};padding:10px 14px;
      font-size:13px;color:#333;border-radius:0 8px 8px 0;margin-bottom:24px}}
    label{{font-size:11px;font-weight:700;letter-spacing:0.8px;
      color:#666;display:block;margin-bottom:8px}}
    select,textarea{{width:100%;padding:11px 12px;border:1.5px solid #e0e0e0;
      border-radius:8px;font-size:14px;margin-bottom:16px;font-family:inherit}}
    select:focus,textarea:focus{{outline:none;border-color:{GOLD}}}
    .btn{{width:100%;padding:14px;background:#E05C2A;color:white;
      border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
    .btn:hover{{background:#c44e22}}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">SAFARIFLOW TRAVEL</div>
    <h1>❌ Reject Quote</h1>
    <p class="sub">Please select a reason before rejecting.</p>
    <div class="divider"></div>
    <div class="ref">Quote Reference: <b>{quote_number}</b></div>
    <form method="GET" action="{API_BASE_URL}/reject">
      <input type="hidden" name="token" value="{token}">
      <label>REASON FOR REJECTION</label>
      <select name="reason" required>
        <option value="">— Select a reason —</option>
        <option>No availability on requested dates</option>
        <option>Package fully booked</option>
        <option>Price changed — needs revision</option>
        <option>Client requirements cannot be met</option>
        <option>Awaiting supplier confirmation</option>
        <option>Other — will follow up with client</option>
      </select>
      <label>ADDITIONAL NOTES (optional)</label>
      <textarea name="notes" rows="3"
        placeholder="Any extra context for the record..."></textarea>
      <button type="submit" class="btn">Confirm Rejection</button>
    </form>
  </div>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
