from mongoengine import Document, StringField, EmailField, DateTimeField
import datetime

class ContactMessage(Document):
    name = StringField(required=True)
    email = EmailField(required=True)
    message = StringField(required=True)
    createdAt = DateTimeField(default=datetime.datetime.utcnow)
