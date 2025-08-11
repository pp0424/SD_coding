from database import db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime



class CustomerInvoice(db.Model):
    invoice_id = db.Column(db.String(255), primary_key=True)
    customer_id = db.Column(db.String(255), nullable=False)
    sales_order_id = db.Column(db.String(255), nullable=False)
    delivery_note_ids = db.Column(db.String(255))
    invoice_date = db.Column(db.DateTime, nullable=False)
    payment_deadline = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Numeric, nullable=False)
    tax_amount = db.Column(db.Numeric, nullable=False)
    payment_status = db.Column(db.String(255))
    remarks = db.Column(db.String(255))

    items = db.relationship('InvoiceItem', backref='invoice', cascade="all, delete-orphan")
    payments = db.relationship('CustomerPayment', backref='invoice', cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    invoice_id = db.Column(db.String(255), db.ForeignKey('customer_invoice.invoice_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    delivery_item_id = db.Column(db.String(255), nullable=False)
    sales_order_item_id = db.Column(db.String(255), nullable=False)
    material_id = db.Column(db.String(255), nullable=False)
    invoiced_quantity = db.Column(db.Numeric, nullable=False)
    unit_price = db.Column(db.Numeric, nullable=False)
    tax_amount = db.Column(db.Numeric)
    item_amount = db.Column(db.Numeric)
    unit = db.Column(db.String(255))

class CustomerPayment(db.Model):
    payment_id = db.Column(db.String(255), primary_key=True)
    customer_id = db.Column(db.String(255), nullable=False)
    invoice_id = db.Column(db.String(255), db.ForeignKey('customer_invoice.invoice_id'), nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False)
    payment_amount = db.Column(db.Numeric, nullable=False)
    payment_method = db.Column(db.String(255), nullable=False)
    write_off_amount = db.Column(db.Numeric, nullable=False)
    status = db.Column(db.String(255))
    remarks = db.Column(db.String(255))
