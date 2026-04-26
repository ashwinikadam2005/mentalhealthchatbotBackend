from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models.user import User
from models.feedback import Feedback


admin_feedback_bp = Blueprint("admin_feedback_bp", __name__)


def require_admin(user_id):
    user = User.objects(id=user_id).first()
    if not user:
        return None, (jsonify({"error": "User not found"}), 404)
    if user.email != "admin@gmail.com":
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


@admin_feedback_bp.route("/feedback/pending", methods=["GET"])
@jwt_required()
def list_pending_feedback():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    pending = Feedback.objects(status="pending").order_by("-created_at").limit(100)
    return jsonify([p.to_dict() for p in pending]), 200


@admin_feedback_bp.route("/feedback/approved", methods=["GET"])
@jwt_required()
def list_approved_feedback_admin():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    approved = (
        Feedback.objects(status="approved")
        .order_by("-approved_at", "-created_at")
        .limit(200)
    )
    return jsonify([a.to_dict() for a in approved]), 200


@admin_feedback_bp.route("/feedback/rejected", methods=["GET"])
@jwt_required()
def list_rejected_feedback_admin():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    rejected = Feedback.objects(status="rejected").order_by("-created_at").limit(200)
    return jsonify([r.to_dict() for r in rejected]), 200


@admin_feedback_bp.route("/feedback/<feedback_id>/approve", methods=["PATCH"])
@jwt_required()
def approve_feedback(feedback_id):
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    fb = Feedback.objects(id=feedback_id).first()
    if not fb:
        return jsonify({"error": "Feedback not found"}), 404

    fb.status = "approved"
    fb.approved_at = datetime.utcnow()
    fb.save()
    return jsonify({"ok": True, "feedback": fb.to_dict()}), 200


@admin_feedback_bp.route("/feedback/<feedback_id>/reject", methods=["PATCH"])
@jwt_required()
def reject_feedback(feedback_id):
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    fb = Feedback.objects(id=feedback_id).first()
    if not fb:
        return jsonify({"error": "Feedback not found"}), 404

    fb.status = "rejected"
    fb.save()
    return jsonify({"ok": True, "feedback": fb.to_dict()}), 200

