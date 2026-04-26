from flask import Blueprint, request, redirect, session, jsonify
from flask_cors import cross_origin
import os, base64, re
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from models.contact_message import ContactMessage

contact_bp = Blueprint("contact_bp", __name__)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
REDIRECT_URI = os.getenv("REDIRECT_URI")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# Email validation
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# --- Google OAuth ---
@contact_bp.route("/authorize")
@cross_origin(supports_credentials=True)
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(auth_url)

@contact_bp.route("/check_auth")
@cross_origin(supports_credentials=True)
def check_auth():
    if "credentials" in session:
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False}), 401

@contact_bp.route("/oauth2callback")
@cross_origin(supports_credentials=True)
def oauth2callback():
    state = session.get("state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    return redirect(f"{FRONTEND_ORIGIN}/contact?auth=success")

# --- Save message and send email ---
@contact_bp.route("/send_email", methods=["POST"])
@cross_origin(supports_credentials=True)
def send_email():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    message_text = data.get("message")

    # Validate fields
    if not all([name, email, message_text]):
        return jsonify({"error": "All fields are required"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email"}), 400

    # --- Save to MongoDB ---
    try:
        msg = ContactMessage(name=name, email=email, message=message_text)
        msg.save()
        print("Saved to MongoDB:", msg.to_mongo())  # debugging
    except Exception as e:
        print("DB error:", e)
        return jsonify({"error": "Failed to save message"}), 500

    # --- Send email via Gmail API if OAuth done ---
    if "credentials" in session:
        try:
            creds = Credentials(**session["credentials"])
            service = build("gmail", "v1", credentials=creds)
            email_body = f"New message from {name} <{email}>:\n\n{message_text}"
            mime_msg = MIMEText(email_body)
            mime_msg["to"] = ADMIN_EMAIL
            mime_msg["subject"] = "New Contact Form Submission"
            raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
        except Exception as e:
            print("Email sending error:", e)
            return jsonify({"error": f"Saved to DB but failed to send email: {str(e)}"}), 500

    return jsonify({"message": "Message saved successfully!"}), 201
