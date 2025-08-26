from flask import Blueprint, request, redirect, session, jsonify
from flask_cors import cross_origin
import os
import base64
from email.mime.text import MIMEText

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

contact_bp = Blueprint("contact_bp", __name__)

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
REDIRECT_URI = os.getenv("REDIRECT_URI")  # must match Google Console redirect URI
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

@contact_bp.route("/authorize")
@cross_origin(supports_credentials=True)
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",  # to get refresh token
        include_granted_scopes="true",
        prompt="consent"  # ensure consent screen always appears so refresh token is granted
    )
    session["state"] = state
    return redirect(auth_url)

@contact_bp.route("/check_auth")
@cross_origin(supports_credentials=True)
def check_auth():
    if "credentials" in session:
        return jsonify({"authenticated": True})
    else:
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
    credentials = flow.credentials

    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    return jsonify({"message": "Google login successful. You can now send emails."})

@contact_bp.route("/send_email", methods=["POST"])
@cross_origin(supports_credentials=True)
def send_email():
    if "credentials" not in session:
        return jsonify({"error": "User not authenticated with Google"}), 401

    creds = Credentials(**session["credentials"])
    service = build("gmail", "v1", credentials=creds)

    data = request.json
    user_name = data.get("name")
    user_email = data.get("email")
    user_message = data.get("message")

    body = f"""
New message from {user_name} <{user_email}>:

{user_message}
"""

    message = MIMEText(body)
    message["to"] = ADMIN_EMAIL
    message["subject"] = "New Contact Form Submission"
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        sent_message = service.users().messages().send(
            userId="me",
            body={"raw": raw_message}
        ).execute()
        return jsonify({"message": "Email sent successfully", "id": sent_message["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
