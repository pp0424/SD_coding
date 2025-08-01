# models.py for order module
from database import db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime

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

class Quotation(db.Model):
    __tablename__ = 'Quotation'

    quotation_id = db.Column(db.String, primary_key=True, comment='报价单号')
    customer_id = db.Column(db.String, nullable=False, comment='客户编号')
    inquiry_id = db.Column(db.String, comment='关联询价单号')
    quotation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='报价日期')
    valid_until_date = db.Column(db.DateTime, nullable=False, comment='有效期至')
    status = db.Column(db.String, default='草稿', comment='报价状态')
    total_amount = db.Column(db.Float, nullable=False, default=0, comment='总金额')
    salesperson_id = db.Column(db.String, comment='销售员编号')
    remarks = db.Column(db.String, comment='备注')

    items = db.relationship("QuotationItem", backref="quotation", cascade="all, delete-orphan")


class QuotationItem(db.Model):
    __tablename__ = 'QuotationItem'

    quotation_id = db.Column(db.String, db.ForeignKey('Quotation.quotation_id'), primary_key=True, comment='所属报价单号')
    item_no = db.Column(db.Integer, primary_key=True, comment='行项号')
    inquiry_item_id = db.Column(db.String, comment='关联询价单行项号')
    material_id = db.Column(db.String, nullable=False, comment='物料编号')
    quotation_quantity = db.Column(db.Float, nullable=False, comment='报价数量')
    unit_price = db.Column(db.Float, nullable=False, comment='单价')
    discount_rate = db.Column(db.Float, default=0, comment='折扣率')
    item_amount = db.Column(db.Float, comment='行项金额')
    unit = db.Column(db.String, comment='物料单位')

class Material(db.Model):
    __tablename__ = 'Material'

    material_id = db.Column(db.String(255), primary_key=True, comment='物料编号')
    description = db.Column(db.String(255), nullable=False, comment='物料描述')
    base_unit = db.Column(db.String(255), nullable=False, comment='基本计量单位')
    storage_location = db.Column(db.String(255), nullable=False, comment='存储位置')
    available_stock = db.Column(db.Numeric, comment='当前可用库存')


# models.py

class SalesOrder(db.Model):
    __tablename__ = 'SalesOrder'
    sales_order_id = db.Column(db.String(255), primary_key=True)
    customer_id = db.Column(db.String(255), nullable=False)
    quotation_id = db.Column(db.String(255))
    order_date = db.Column(db.DateTime, nullable=False)
    required_delivery_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(255))
    total_amount = db.Column(db.Numeric, nullable=False)
    credit_check_result = db.Column(db.String(255))
    remarks = db.Column(db.String(255))

    # ✅ 添加这一行：建立订单 → 项目 的关系
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = 'OrderItem'
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    material = db.relationship('Material',backref="order_items")  # ✅ 告诉 SQLAlchemy 如何关联 Material 表

    order_quantity = db.Column(db.Numeric, nullable=False)
    sales_unit_price = db.Column(db.Numeric, nullable=False)
    shipped_quantity = db.Column(db.Numeric)
    unshipped_quantity = db.Column(db.Numeric)
    item_amount = db.Column(db.Numeric)
    unit = db.Column(db.String(255))

