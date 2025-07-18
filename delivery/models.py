# models.py for delivery module
from database import db

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200))
    status = db.Column(db.String(50))
