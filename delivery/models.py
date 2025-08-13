# delivery/models.py

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, timezone
from flask_login import current_user
from sqlalchemy import text
from database import db
from datetime import datetime


class PickingTask(db.Model):
    __tablename__ = 'PickingTask'
    task_id = db.Column(db.String(255), primary_key=True)
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), nullable=False)
    warehouse_code = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50))
    picker = db.Column(db.String(255))  # 拣货员
    assigned_at = db.Column(db.DateTime, nullable=True)  # 分配时间
    start_time = db.Column(db.DateTime)
    complete_time = db.Column(db.DateTime)
    remarks = db.Column(db.Text)

    items = db.relationship('PickingTaskItem', backref='picking_task', cascade='all, delete-orphan', lazy=True)
    sales_order = db.relationship('SalesOrder', backref='picking_tasks')

    VALID_TRANSITIONS = {
        '待拣货': ['已完成','已取消'],
        '已完成': [],
        '已取消': []
    }

class PickingTaskItem(db.Model):
    __tablename__ = 'PickingTaskItem'
    task_id = db.Column(db.String(255), db.ForeignKey('PickingTask.task_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    sales_order_item_no = db.Column(db.Integer, nullable=False)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    required_quantity = db.Column(db.Numeric(10, 2))
    picked_quantity = db.Column(db.Numeric(10, 2))
    unit = db.Column(db.String(50))
    storage_location = db.Column(db.String(255), nullable=True, comment='存储位置')
    material = db.relationship('Material')

class DeliveryNote(db.Model):
    __tablename__ = 'DeliveryNote'
    delivery_note_id = db.Column(db.String(255), primary_key=True)
    picking_task_id = db.Column(db.String(255), db.ForeignKey('PickingTask.task_id'), nullable=False)
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), nullable=False)
    delivery_date = db.Column(db.DateTime, nullable=False)
    warehouse_code = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum(
        '已创建', 
        '已拣货',  
        '已发货', 
        '已过账', 
        '已取消'
    ), default='已创建', nullable=False)
    posted_by = db.Column(db.String(255))
    posted_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(255))
    remarks = db.Column(db.Text)

    items = db.relationship('DeliveryItem', backref='delivery_note', cascade='all, delete-orphan', lazy=True)
    sales_order = db.relationship('SalesOrder', backref='delivery_notes')
    picking_task = db.relationship('PickingTask', backref='delivery_note')

    VALID_TRANSITIONS = {
    '已创建': ['已拣货', '已取消'],
    '已拣货': ['已发货', '已取消'],
    '已发货': ['已过账'],
    '已过账': [],
    '已取消': []
    }


class DeliveryItem(db.Model):
    __tablename__ = 'DeliveryItem'
    delivery_note_id = db.Column(db.String(255), db.ForeignKey('DeliveryNote.delivery_note_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    sales_order_item_no = db.Column(db.Integer, nullable=False)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    planned_delivery_quantity = db.Column(db.Numeric(18, 4))
    actual_delivery_quantity = db.Column(db.Numeric(18, 4))
    unit = db.Column(db.String(50))

    material = db.relationship('Material')

    def is_fully_delivered(self):
        return Decimal(self.actual_delivery_quantity or 0) >= Decimal(self.planned_delivery_quantity or 0)



class StockChangeLog(db.Model):
    __tablename__ = 'StockChangeLog'
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(255), db.ForeignKey('Material.material_id'), nullable=False)
    change_time = db.Column(db.DateTime, default=datetime.now)
    change_type = db.Column(db.String(50), nullable=False)  # '发货', '拣货' 或 '其他'
    quantity_change = db.Column(db.Numeric(18, 4), nullable=False)

    before_available = db.Column(db.Numeric(18, 4))
    after_available = db.Column(db.Numeric(18, 4))
    before_allocated = db.Column(db.Numeric(18, 4))
    after_allocated = db.Column(db.Numeric(18, 4))
    before_physical = db.Column(db.Numeric(18, 4))
    after_physical = db.Column(db.Numeric(18, 4))
    before_pending_outbound = db.Column(db.Numeric(18, 4))
    after_pending_outbound = db.Column(db.Numeric(18, 4))

    reference_doc = db.Column(db.String(255))
    operator = db.Column(db.String(255))
    warehouse_code = db.Column(db.String(255))

    material = db.relationship('Material', backref='stock_changes')


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

class Inventory(db.Model):
    __tablename__ = 'Inventory'
    material_id = db.Column(db.String(255), primary_key=True, comment='物料编号')
    description = db.Column(db.String(255), nullable=False, comment='物料描述')
    base_unit = db.Column(db.String(255), nullable=False, comment='基本计量单位')
    storage_location = db.Column(db.String(255), nullable=False, comment='存储位置')
    available_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='可用库存数量')
    physical_stock  = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='账面总库存')
    allocated_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='已分配库存')
    pending_outbound= db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='待出库量')


    def allocate_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        qty = _q(qty)
        if qty <= 0:
            return None

        locked = (db.session.query(Inventory)
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

        locked = (db.session.query(Inventory)
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

        locked = (db.session.query(Inventory)
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
        locked.available_stock = _q(locked.physical_stock - locked.allocated_stock - locked.pending_outbound)

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
