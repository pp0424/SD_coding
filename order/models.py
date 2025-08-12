# models.py for order module
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import text
from database import db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime

from delivery.models import StockChangeLog

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
    quotation_date = db.Column(db.DateTime, nullable=False, default=datetime.now, comment='报价日期')
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


from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

QTY_QUANT = Decimal('0.0001')

def _normalize_qty(q):
    q = Decimal(q or 0)
    # 避免出现超过 4 位小数
    q = q.quantize(QTY_QUANT, rounding=ROUND_HALF_UP)
    return q

def _resolve_operator(operator):
    # 安全地从 current_user 取用户名
    try:
        from flask_login import current_user
        if operator:
            return operator
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "username", "unknown")
    except Exception:
        pass
    return "system"

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, timezone

QTY_QUANT = Decimal('0.0001')  # 与 Numeric(18, 4) 对齐

def _to_decimal(x):
    if x is None:
        return Decimal('0')
    if isinstance(x, Decimal):
        return x
    try:
        # 避免 float 精度问题，允许传 str/int
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"数量格式非法: {x!r}")

def _q(x):
    return _to_decimal(x).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)

class Material(db.Model):
    __tablename__ = 'Material'
    material_id = db.Column(db.String(255), primary_key=True, comment='物料编号')
    description = db.Column(db.String(255), nullable=False, comment='物料描述')
    base_unit = db.Column(db.String(255), nullable=False, comment='基本计量单位')
    storage_location = db.Column(db.String(255), nullable=False, comment='存储位置')

    physical_stock  = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='账面总库存')
    available_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='可用库存数量')
    allocated_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='已分配库存')
    pending_outbound= db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='待出库量')

    def allocate_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        qty = _q(qty)
        if qty <= 0:
            return None

        locked = (db.session.query(Material)
                  .filter_by(material_id=self.material_id)
                  .with_for_update()
                  .one_or_none())
        if locked is None:
            raise ValueError(f"物料 {self.material_id} 不存在（allocate）")

        before_available = _to_decimal(locked.available_stock)
        before_allocated = _to_decimal(locked.allocated_stock)
        before_physical  = _to_decimal(locked.physical_stock)
        before_pending   = _to_decimal(locked.pending_outbound)

        if before_available < qty:
            raise ValueError(f"{locked.material_id} 可用不足：可用 {before_available} < 需 {qty}")

        locked.available_stock = _q(before_available - qty)
        locked.allocated_stock = _q(before_allocated + qty)

        log = StockChangeLog(
            material_id=locked.material_id,
            change_time=datetime.now(timezone.utc),
            change_type='拣货占用',
            quantity_change=qty,
            before_available=before_available,
            after_available=_to_decimal(locked.available_stock),
            before_allocated=before_allocated,
            after_allocated=_to_decimal(locked.allocated_stock),
            before_physical=before_physical,
            after_physical=before_physical,
            before_pending_outbound=before_pending,
            after_pending_outbound=before_pending,
            reference_doc=(reference or ''),
            operator=_resolve_operator(operator),
            warehouse_code=(warehouse_code or locked.storage_location)
        )
        db.session.add(log)
        return locked

    def release_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        qty = _q(qty)
        if qty <= 0:
            return None

        locked = (db.session.query(Material)
                  .filter_by(material_id=self.material_id)
                  .with_for_update()
                  .one_or_none())
        if locked is None:
            raise ValueError(f"物料 {self.material_id} 不存在（release）")

        before_allocated = _to_decimal(locked.allocated_stock)
        before_available = _to_decimal(locked.available_stock)
        before_physical  = _to_decimal(locked.physical_stock)
        before_pending   = _to_decimal(locked.pending_outbound)

        if before_allocated < qty:
            raise ValueError(f"{locked.material_id} 已分配不足：已分配 {before_allocated} < 释放 {qty}")

        locked.allocated_stock = _q(before_allocated - qty)
        locked.available_stock = _q(before_available + qty)

        log = StockChangeLog(
            material_id=locked.material_id,
            change_time=datetime.now(timezone.utc),
            change_type='释放分配',
            quantity_change=-qty,
            before_available=before_available,
            after_available=_to_decimal(locked.available_stock),
            before_allocated=before_allocated,
            after_allocated=_to_decimal(locked.allocated_stock),
            before_physical=before_physical,
            after_physical=before_physical,
            before_pending_outbound=before_pending,
            after_pending_outbound=before_pending,
            reference_doc=(reference or ''),
            operator=_resolve_operator(operator),
            warehouse_code=(warehouse_code or locked.storage_location)
        )
        db.session.add(log)
        return locked

    def ship_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        qty = _q(qty)
        if qty <= 0:
            return None

        locked = (db.session.query(Material)
                  .filter_by(material_id=self.material_id)
                  .with_for_update()
                  .one_or_none())
        if locked is None:
            raise ValueError(f"物料 {self.material_id} 不存在（ship）")

        before_allocated = _to_decimal(locked.allocated_stock)
        before_physical  = _to_decimal(locked.physical_stock)
        before_available = _to_decimal(locked.available_stock)
        before_pending   = _to_decimal(locked.pending_outbound)

        if before_allocated < qty:
            raise ValueError(f"{locked.material_id} 已分配不足：{before_allocated} < {qty}")
        if before_physical < qty:
            raise ValueError(f"{locked.material_id} 账面不足：{before_physical} < {qty}")
        if before_pending < qty:
            raise ValueError(f"{locked.material_id} 待出库不足：{before_pending} < {qty}")

        locked.allocated_stock  = _q(before_allocated - qty)
        locked.physical_stock   = _q(before_physical  - qty)
        locked.pending_outbound = _q(before_pending   - qty)
        # 如果你要求不变式：available = physical - allocated - pending，可在此同步：
        # locked.available_stock = _q(locked.physical_stock - locked.allocated_stock - locked.pending_outbound)

        log = StockChangeLog(
            material_id=locked.material_id,
            change_time=datetime.now(timezone.utc),
            change_type='发货',
            quantity_change=-qty,
            before_available=before_available,
            after_available=_to_decimal(locked.available_stock),
            before_allocated=before_allocated,
            after_allocated=_to_decimal(locked.allocated_stock),
            before_physical=before_physical,
            after_physical=_to_decimal(locked.physical_stock),
            before_pending_outbound=before_pending,
            after_pending_outbound=_to_decimal(locked.pending_outbound),
            reference_doc=(reference or ''),
            operator=_resolve_operator(operator),
            warehouse_code=(warehouse_code or locked.storage_location)
        )
        db.session.add(log)
        return locked

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
