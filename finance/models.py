# models.py for finance module
from database import db

class Finance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    type = db.Column(db.String(50))  # 收入/支出
