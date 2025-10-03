from mongoengine import (
    Document, StringField, ListField, EmbeddedDocument, EmbeddedDocumentField,
    DateTimeField, ReferenceField, DictField
)
from datetime import datetime
from .user import User


class Message(EmbeddedDocument):
    sender = StringField(required=True, choices=["user", "bot"])
    text = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)


class Chat(Document):
    user = ReferenceField(User, required=True, reverse_delete_rule=2)  # CASCADE
    title = StringField(default="New Chat")
    messages = ListField(EmbeddedDocumentField(Message))
    metadata = DictField(default=dict)   # 👈 New field for age, problem type, severity, etc.
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "chats",
        "ordering": ["-updated_at"]
    }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super(Chat, self).save(*args, **kwargs)

    def to_dict(self):
        return {
            "_id": str(self.id),
            "title": self.title,
            "messages": [
                {
                    "sender": m.sender,
                    "text": m.text,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None
                } for m in self.messages
            ],
            "metadata": self.metadata,  # 👈 include metadata in response
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
