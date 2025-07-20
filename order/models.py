# models.py for order module
from database import db

# models.py
class Inquiry(db.Model):
    __tablename__ = 'Inquiry'
    inquiry_id = db.Column(db.String, primary_key=True)
    customer_id = db.Column(db.String, nullable=False)
    inquiry_date = db.Column(db.DateTime, nullable=False)
    expected_delivery_date = db.Column(db.Date)
    status = db.Column(db.String)
    expected_total_amount = db.Column(db.Float)
    salesperson_id = db.Column(db.String)
    remarks = db.Column(db.String)

    # ✅ 建立与 InquiryItem 的一对多关系
    items = db.relationship('InquiryItem', backref='inquiry', cascade="all, delete-orphan", lazy='joined')


class InquiryItem(db.Model):
    __tablename__ = 'InquiryItem'
    inquiry_id = db.Column(db.String, db.ForeignKey('Inquiry.inquiry_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String, nullable=False)
    inquiry_quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String)
    expected_unit_price = db.Column(db.Float)
    item_remarks = db.Column(db.String)
