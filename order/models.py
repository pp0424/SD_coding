# models.py for order module
from database import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
