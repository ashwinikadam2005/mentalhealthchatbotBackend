from mongoengine import Document, StringField, IntField, DateTimeField
from datetime import datetime


class Feedback(Document):
    user_id = StringField()  # optional: who submitted (JWT identity)
    name = StringField(required=True, max_length=80)
    message = StringField(required=True, max_length=800)
    rating = IntField(min_value=1, max_value=5, default=5)
    status = StringField(choices=["pending", "approved", "rejected"], default="pending")
    created_at = DateTimeField(default=datetime.utcnow)
    approved_at = DateTimeField()

    meta = {
        "collection": "feedback",
        "ordering": ["-created_at"],
    }

    def to_dict(self):
        return {
            "_id": str(self.id),
            "user_id": self.user_id,
            "name": self.name,
            "message": self.message,
            "rating": int(self.rating or 0),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }

