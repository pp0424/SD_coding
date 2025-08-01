# delivery/models.py

from database import db
from datetime import datetime

class DeliveryNote(db.Model):
    __tablename__ = 'DeliveryNote'
    delivery_note_id = db.Column(db.String(255), primary_key=True)
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), nullable=False)
    delivery_date = db.Column(db.DateTime, nullable=False)
    warehouse_code = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='已创建')
    posted_by = db.Column(db.String(255))
    posted_at = db.Column(db.DateTime)
    remarks = db.Column(db.Text)
    
    items = db.relationship('DeliveryItem', backref='delivery_note', cascade='all, delete-orphan', lazy=True)
    sales_order = db.relationship('SalesOrder', backref='delivery_notes')

class DeliveryItem(db.Model):
    __tablename__ = 'DeliveryItem'
    delivery_note_id = db.Column(db.String(255), db.ForeignKey('DeliveryNote.delivery_note_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    sales_order_item_no = db.Column(db.Integer, nullable=False)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    planned_delivery_quantity = db.Column(db.Numeric(10, 2))
    actual_delivery_quantity = db.Column(db.Numeric(10, 2))
    unit = db.Column(db.String(50))
    
    material = db.relationship('Material')

class StockChangeLog(db.Model):
    __tablename__ = 'StockChangeLog'
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    change_time = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50), nullable=False)  # '发货' 或 '其他'
    quantity_change = db.Column(db.Numeric(10, 2), nullable=False)
    before_quantity = db.Column(db.Numeric(10, 2))
    after_quantity = db.Column(db.Numeric(10, 2))
    reference_doc = db.Column(db.String(255))  # 关联的发货单号
    operator = db.Column(db.String(255))
    warehouse_code = db.Column(db.String(255))
    
    material = db.relationship('Material', backref='stock_changes')
