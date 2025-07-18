# models.py for customer module
from database import db

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    info = db.Column(db.String(200), nullable=True)


    def __repr__(self):
        return f"<Customer {{self.name}}>" 
