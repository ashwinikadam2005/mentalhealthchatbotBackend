from datetime import datetime
from mongoengine import Document, StringField, DateTimeField

class Journal(Document):
    user_id = StringField(required=True)
    entry = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {"collection": "journals"}  # optional: name of MongoDB collection
