from flask import Blueprint, request, jsonify
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.feedback import Feedback


feedback_bp = Blueprint("feedback_bp", __name__)


@feedback_bp.route("", methods=["POST"])
@jwt_required()
def submit_feedback():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    message = (data.get("message") or "").strip()
    rating = data.get("rating", 5)

    if not name or len(name) < 2:
        return jsonify({"error": "Name is required"}), 400
    if not message or len(message) < 5:
        return jsonify({"error": "Feedback message is required"}), 400

    try:
        rating_int = int(rating)
    except Exception:
        rating_int = 5
    rating_int = max(1, min(5, rating_int))

    fb = Feedback(
        user_id=str(user_id) if user_id else None,
        name=name[:80],
        message=message[:800],
        rating=rating_int,
        status="pending",
        created_at=datetime.utcnow(),
    )
    fb.save()

    return jsonify({"ok": True, "message": "Feedback submitted for admin approval."}), 201


@feedback_bp.route("/approved", methods=["GET"])
def list_approved_feedback():
    try:
        limit = int(request.args.get("limit", 9))
    except Exception:
        limit = 9
    limit = max(1, min(20, limit))

    items = (
        Feedback.objects(status="approved")
        .order_by("-approved_at", "-created_at")
        .limit(limit)
    )
    return jsonify([f.to_dict() for f in items]), 200

