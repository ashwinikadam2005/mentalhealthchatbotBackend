from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.journal import Journal

journal_bp = Blueprint("journal", __name__)

# Save a journal entry
@journal_bp.route("/save", methods=["POST"])
@jwt_required()
def save_journal():
    data = request.get_json()
    user_id = get_jwt_identity()
    entry = data.get("entry")

    if not entry:
        return jsonify({"error": "Entry cannot be empty"}), 400

    journal = Journal(user_id=user_id, entry=entry)
    journal.save()

    return jsonify({"message": "Journal entry saved"}), 201


# Get all journals of logged-in user
@journal_bp.route("/my", methods=["GET"])
@jwt_required()
def get_my_journals():
    user_id = get_jwt_identity()
    journals = Journal.objects(user_id=user_id).order_by("-created_at")
    return jsonify([{"entry": j.entry, "created_at": j.created_at} for j in journals])
