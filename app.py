# ─────────────────────────────────────────────────────────────────
# SafariFlow — Flask API v3.0
# Full approval flow: Agent + Client buttons
# ─────────────────────────────────────────────────────────────────

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pdf_generator_v2 import (
    generate_quote_pdf,
    generate_receipt_pdf,
    generate_accommodation_voucher,
    generate_transport_voucher,
    generate_itinerary_pdf
)
import os
import jwt
import requests as req
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)

# ── Config ────────────────────────────────────────────────────────
API_KEY             = os.environ.get("API_KEY", "tqa-2024-secure-key-change-me-now")
SECRET_KEY          = os.environ.get("APPROVAL_SECRET", "safariflow-approval-secret-2026")
MAKE_SCENARIO2_URL  = os.environ.get("MAKE_SCENARIO2_WEBHOOK", "")
MAKE_SCENARIO3_URL  = os.environ.get("MAKE_SCENARIO3_WEBHOOK", "")
PORTAL_URL          = os.environ.get("PORTAL_URL", "https://cosmic-figolla-71951d.netlify.app")
API_BASE_URL        = os.environ.get("API_BASE_URL", "https://travel-quote-api.onrender.com")

NAVY = "#0D1E35"
GOLD = "#C8A96E"


# ── Auth ──────────────────────────────────────────────────────────
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Token Helpers ─────────────────────────────────────────────────
def make_token(data_dict, expires_days=7):
    payload = {**data_dict,
        "exp": datetime.utcnow() + timedelta(days=expires_days),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"]), None
    except jwt.ExpiredSignatureError:
        return None, "This link has expired. Please contact your agent."
    except jwt.InvalidTokenError:
        return None, "Invalid link. Please contact your agent."


def fire_webhook(url, payload):
    if not url:
        print(f"[WARN] Webhook URL not configured")
        return False
    try:
        req.post(url, json=payload, timeout=15)
        return True
    except Exception as e:
        print(f"[WARN] Webhook failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# CORE PDF ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "SafariFlow API",
        "version": "3.0",
        "features": ["quote-pdf", "itinerary-pdf", "agent-approval", "client-approval"]
    })


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
# AGENT APPROVAL ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/generate-approval-links", methods=["POST"])
@require_api_key
def generate_approval_links():
    """Called by Make.com Scenario 1 — returns agent approve/edit/reject URLs"""
    data         = request.get_json()
    quote_number = data.get("quote_number")
    agent_email  = data.get("agent_email")
    if not quote_number or not agent_email:
        return jsonify({"error": "quote_number and agent_email required"}), 400

    approve_token = make_token({"quote_number": quote_number, "agent_email": agent_email, "action": "agent_approve"})
    reject_token  = make_token({"quote_number": quote_number, "agent_email": agent_email, "action": "agent_reject"})

    return jsonify({
        "approve_url": f"{API_BASE_URL}/approve?token={approve_token}",
        "edit_url":    f"{PORTAL_URL}/drafts/{quote_number}",
        "reject_url":  f"{API_BASE_URL}/reject?token={reject_token}",
        "quote_number": quote_number,
    })


@app.route("/approve", methods=["GET"])
def approve_quote():
    """Agent clicks APPROVE → triggers Scenario 2 to send quote to client"""
    token = request.args.get("token")
    if not token:
        return page_html("error", "Missing Token", "No approval token was provided.", "")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Problem", error, "")

    quote_number = payload["quote_number"]
    agent_email  = payload["agent_email"]

    fire_webhook(MAKE_SCENARIO2_URL, {
        "quote_number": quote_number,
        "agent_email":  agent_email,
        "action":       "approved",
        "approved_at":  datetime.utcnow().isoformat(),
    })

    return page_html(
        "approved",
        "Quote Approved! ✅",
        f"Quote <b>{quote_number}</b> has been approved.",
        "The client will receive their personalised quote and itinerary within minutes.",
        show_portal=True
    )


@app.route("/reject", methods=["GET"])
def reject_quote():
    """Agent clicks REJECT → shows reason form → fires Scenario 2 with rejected status"""
    token  = request.args.get("token")
    reason = request.args.get("reason", "").strip()

    if not token:
        return page_html("error", "Missing Token", "No token provided.", "")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Problem", error, "")

    quote_number = payload["quote_number"]

    if reason:
        fire_webhook(MAKE_SCENARIO2_URL, {
            "quote_number": quote_number,
            "agent_email":  payload["agent_email"],
            "action":       "rejected",
            "reason":       reason,
            "rejected_at":  datetime.utcnow().isoformat(),
        })
        return page_html(
            "rejected",
            "Quote Rejected",
            f"Quote <b>{quote_number}</b> has been marked as unavailable.",
            f"Reason: {reason}",
            show_portal=True
        )

    return rejection_form(quote_number, token, "agent")


# ══════════════════════════════════════════════════════════════════
# CLIENT APPROVAL ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/generate-client-links", methods=["POST"])
@require_api_key
def generate_client_links():
    """Called by Make.com Scenario 2 — returns client accept/changes URLs"""
    data         = request.get_json()
    quote_number = data.get("quote_number")
    client_email = data.get("client_email")
    client_name  = data.get("client_name", "")
    agent_email  = data.get("agent_email", "")

    if not quote_number or not client_email:
        return jsonify({"error": "quote_number and client_email required"}), 400

    accept_token  = make_token({
        "quote_number": quote_number,
        "client_email": client_email,
        "client_name":  client_name,
        "agent_email":  agent_email,
        "action":       "client_accept"
    }, expires_days=14)  # expires with quote validity

    changes_token = make_token({
        "quote_number": quote_number,
        "client_email": client_email,
        "client_name":  client_name,
        "agent_email":  agent_email,
        "action":       "client_changes"
    }, expires_days=14)

    return jsonify({
        "accept_url":  f"{API_BASE_URL}/client-accept?token={accept_token}",
        "changes_url": f"{API_BASE_URL}/client-changes?token={changes_token}",
        "quote_number": quote_number,
    })


@app.route("/client-accept", methods=["GET"])
def client_accept():
    """Client clicks ACCEPT QUOTE → triggers Scenario 3 → notifies agent"""
    token = request.args.get("token")
    if not token:
        return page_html("error", "Invalid Link", "This link is not valid.", "")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Expired", error, "")

    quote_number = payload["quote_number"]
    client_name  = payload.get("client_name", "")
    client_email = payload["client_email"]
    agent_email  = payload.get("agent_email", "")

    fire_webhook(MAKE_SCENARIO3_URL, {
        "quote_number": quote_number,
        "client_name":  client_name,
        "client_email": client_email,
        "agent_email":  agent_email,
        "action":       "client_accepted",
        "accepted_at":  datetime.utcnow().isoformat(),
    })

    return client_accept_html(client_name, quote_number, agent_email)


@app.route("/client-changes", methods=["GET", "POST"])
def client_changes():
    """Client clicks REQUEST CHANGES → shows changes form → notifies agent"""
    token = request.args.get("token")
    if not token:
        return page_html("error", "Invalid Link", "This link is not valid.", "")

    payload, error = decode_token(token)
    if error:
        return page_html("error", "Link Expired", error, "")

    quote_number = payload["quote_number"]
    client_name  = payload.get("client_name", "")
    client_email = payload["client_email"]
    agent_email  = payload.get("agent_email", "")

    # If form submitted
    changes_text = request.args.get("changes", "").strip()
    budget_note  = request.args.get("budget", "").strip()
    dates_note   = request.args.get("dates", "").strip()

    if changes_text:
        fire_webhook(MAKE_SCENARIO3_URL, {
            "quote_number": quote_number,
            "client_name":  client_name,
            "client_email": client_email,
            "agent_email":  agent_email,
            "action":       "client_changes_requested",
            "changes":      changes_text,
            "budget_note":  budget_note,
            "dates_note":   dates_note,
            "requested_at": datetime.utcnow().isoformat(),
        })
        return page_html(
            "changes",
            "Changes Requested! ✏️",
            f"Thank you <b>{client_name}</b>!",
            f"Your agent will review your requests and send a revised quote shortly.",
            show_portal=False
        )

    return client_changes_form(quote_number, token, client_name)


# ══════════════════════════════════════════════════════════════════
# HTML PAGES
# ══════════════════════════════════════════════════════════════════

def page_html(status, title, message, sub, show_portal=False):
    status_config = {
        "approved": ("#27AE60", "✅"),
        "rejected": ("#E05C2A", "❌"),
        "changes":  ("#4A90D9", "✏️"),
        "error":    ("#999999", "⚠️"),
    }
    color, icon = status_config.get(status, ("#999", "⚠️"))
    portal_btn = f'<br><br><a href="{PORTAL_URL}/quotes" style="display:inline-block;background:{NAVY};color:white;padding:11px 26px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;">Go to Portal →</a>' if show_portal else ''

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>SafariFlow — {title}</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:44px 36px;
      max-width:440px;width:100%;text-align:center;
      box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:10px;font-weight:700;letter-spacing:2.5px;
      color:{GOLD};margin-bottom:24px}}
    .icon{{font-size:50px;margin-bottom:14px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);margin:18px 0}}
    h1{{font-size:21px;color:{NAVY};margin-bottom:8px;font-weight:700}}
    .msg{{font-size:14px;color:#444;line-height:1.6;margin-bottom:6px}}
    .sub{{font-size:12px;color:#999;line-height:1.5;margin-bottom:24px}}
    .badge{{display:inline-block;background:{color}18;color:{color};
      border:1px solid {color}33;padding:5px 18px;border-radius:20px;
      font-size:11px;font-weight:700;letter-spacing:1px}}
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
    <div class="badge">{status.upper()}</div>
    {portal_btn}
  </div>
</body>
</html>"""


def client_accept_html(client_name, quote_number, agent_email):
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>SafariFlow — Booking Confirmed!</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:44px 36px;
      max-width:460px;width:100%;text-align:center;
      box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:10px;font-weight:700;letter-spacing:2.5px;color:{GOLD};margin-bottom:20px}}
    .icon{{font-size:56px;margin-bottom:14px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);margin:18px 0}}
    h1{{font-size:22px;color:{NAVY};margin-bottom:8px;font-weight:700}}
    .msg{{font-size:14px;color:#444;line-height:1.6;margin-bottom:6px}}
    .sub{{font-size:12px;color:#999;line-height:1.5;margin-bottom:20px}}
    .steps{{background:#FBF6EE;border-radius:10px;padding:18px 20px;
      text-align:left;margin:20px 0}}
    .step{{display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;font-size:13px;color:#444}}
    .step:last-child{{margin-bottom:0}}
    .step-num{{background:{GOLD};color:white;width:22px;height:22px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:11px;font-weight:700;flex-shrink:0;margin-top:1px}}
    .agent-box{{background:{NAVY};border-radius:10px;padding:14px 18px;margin-top:16px}}
    .agent-label{{font-size:10px;color:#7899BB;letter-spacing:1px;margin-bottom:4px}}
    .agent-name{{font-size:14px;font-weight:700;color:white}}
    .agent-email{{font-size:12px;color:{GOLD};margin-top:2px}}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">SAFARIFLOW TRAVEL</div>
    <div class="icon">🎉</div>
    <h1>Quote Accepted!</h1>
    <div class="divider"></div>
    <p class="msg">Thank you <b>{client_name}</b>!</p>
    <p class="sub">Your agent has been notified and will be in touch shortly with deposit payment instructions.</p>

    <div class="steps">
      <div style="font-size:10px;font-weight:700;letter-spacing:1px;color:#999;margin-bottom:12px;">WHAT HAPPENS NEXT</div>
      <div class="step">
        <div class="step-num">1</div>
        <div>Your agent will send a <b>deposit invoice</b> within 24 hours</div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div>Pay <b>50% deposit</b> via secure payment link to confirm booking</div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div>Receive your <b>booking confirmation</b> and travel documents</div>
      </div>
      <div class="step">
        <div class="step-num">4</div>
        <div><b>Balance payment</b> due 30 days before departure</div>
      </div>
    </div>

    <div class="agent-box">
      <div class="agent-label">YOUR TRAVEL SPECIALIST</div>
      <div class="agent-name">Ibrahim — SafariFlow Travel</div>
      <div class="agent-email">{agent_email}</div>
    </div>

    <p style="font-size:11px;color:#bbb;margin-top:16px;">
      Quote Reference: <b>{quote_number}</b>
    </p>
  </div>
</body>
</html>"""


def client_changes_form(quote_number, token, client_name):
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>SafariFlow — Request Changes</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:36px;
      max-width:480px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:10px;font-weight:700;letter-spacing:2.5px;color:{GOLD};margin-bottom:18px}}
    h1{{font-size:21px;color:{NAVY};margin-bottom:6px}}
    .sub{{font-size:13px;color:#999;margin-bottom:20px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);margin:18px 0}}
    .ref{{background:#f8f8f6;border-left:3px solid {GOLD};padding:9px 14px;
      font-size:13px;color:#333;border-radius:0 8px 8px 0;margin-bottom:20px}}
    label{{font-size:10px;font-weight:700;letter-spacing:0.8px;color:#666;
      display:block;margin-bottom:7px;text-transform:uppercase}}
    input,select,textarea{{width:100%;padding:11px 13px;border:1.5px solid #e8e4de;
      border-radius:8px;font-size:14px;margin-bottom:14px;
      font-family:inherit;color:#0D1E35}}
    input:focus,select:focus,textarea:focus{{outline:none;border-color:{GOLD}}}
    .btn{{width:100%;padding:14px;background:{NAVY};color:white;border:none;
      border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
    .btn:hover{{background:#1A2E4A}}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">SAFARIFLOW TRAVEL</div>
    <h1>✏️ Request Changes</h1>
    <p class="sub">Tell us what you'd like adjusted and we'll send a revised quote.</p>
    <div class="divider"></div>
    <div class="ref">Quote Reference: <b>{quote_number}</b> &nbsp;·&nbsp; {client_name}</div>

    <form method="GET" action="{API_BASE_URL}/client-changes">
      <input type="hidden" name="token" value="{token}">

      <label>What would you like changed?</label>
      <textarea name="changes" rows="4" required
        placeholder="e.g. Can we add an extra night? Prefer a different lodge? Different dates?"></textarea>

      <label>Budget consideration (optional)</label>
      <select name="budget">
        <option value="">— No budget change —</option>
        <option value="Looking for a lower price option">Looking for a lower price option</option>
        <option value="Happy to increase budget for upgrade">Happy to increase budget for upgrade</option>
        <option value="Budget is flexible">Budget is flexible</option>
      </select>

      <label>Date flexibility (optional)</label>
      <select name="dates">
        <option value="">— Dates are fixed —</option>
        <option value="Dates are flexible by a few days">Flexible by a few days</option>
        <option value="Dates are flexible by 1-2 weeks">Flexible by 1-2 weeks</option>
        <option value="Completely flexible on dates">Completely flexible</option>
      </select>

      <button type="submit" class="btn">Send Change Request →</button>
    </form>
  </div>
</body>
</html>"""


def rejection_form(quote_number, token, actor="agent"):
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>SafariFlow — Reject Quote</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:{NAVY};min-height:100vh;display:flex;align-items:center;
      justify-content:center;padding:20px}}
    .card{{background:white;border-radius:16px;padding:36px;
      max-width:460px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,0.4)}}
    .brand{{font-size:10px;font-weight:700;letter-spacing:2.5px;color:{GOLD};margin-bottom:18px}}
    h1{{font-size:21px;color:{NAVY};margin-bottom:6px}}
    .sub{{font-size:13px;color:#999;margin-bottom:20px}}
    .divider{{height:2px;background:linear-gradient(to right,{GOLD},transparent);margin:18px 0}}
    .ref{{background:#f8f8f6;border-left:3px solid {GOLD};padding:9px 14px;
      font-size:13px;color:#333;border-radius:0 8px 8px 0;margin-bottom:20px}}
    label{{font-size:10px;font-weight:700;letter-spacing:0.8px;color:#666;
      display:block;margin-bottom:7px}}
    select,textarea{{width:100%;padding:11px 13px;border:1.5px solid #e8e4de;
      border-radius:8px;font-size:14px;margin-bottom:14px;font-family:inherit}}
    select:focus,textarea:focus{{outline:none;border-color:{GOLD}}}
    .btn{{width:100%;padding:14px;background:#E05C2A;color:white;border:none;
      border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
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
        placeholder="Any extra context..."></textarea>
      <button type="submit" class="btn">Confirm Rejection</button>
    </form>
  </div>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
