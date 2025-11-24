from peewee import Model, CharField, TextField, DateTimeField
from datetime import datetime
from database import db

class BaseModel(Model):
    class Meta:
        database = db

class ChatMessage(BaseModel):
    prenom = CharField(max_length=50)
    filiaire = CharField(max_length=120)
    commentaire = TextField()
    created_at = DateTimeField(default=datetime.utcnow)
