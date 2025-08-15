# delivery/models.py

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, timezone
from flask_login import current_user
from sqlalchemy import text
from database import db
from datetime import datetime

class PickingTask(db.Model):
    """
    拣货任务（主表）
    - 与销售订单(SalesOrder)关联，一个任务对应一张销售订单（多对一）
    - 与拣货任务行(PickingTaskItem)为一对多
    - 可被交货单(DeliveryNote)引用（一个拣货任务 -> 一个交货单）
    """
    __tablename__ = 'PickingTask'

    # 拣货任务ID（主键，字符串）
    task_id = db.Column(db.String(255), primary_key=True)

    # 销售订单ID（外键，非空）
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), nullable=False)

    # 仓库代码（标识执行拣货的仓库）
    warehouse_code = db.Column(db.String(255), nullable=False)

    # 任务状态： '待拣货' / '已完成' / '已取消'
    status = db.Column(db.String(50))

    # 拣货员
    picker = db.Column(db.String(255))

    # 分配时间（任务分派给拣货员的时间，允许为空）
    assigned_at = db.Column(db.DateTime, nullable=True)

    # 拣货开始时间
    start_time = db.Column(db.DateTime)

    # 拣货完成时间
    complete_time = db.Column(db.DateTime)

    # 备注（自由文本）
    remarks = db.Column(db.Text)

    # 子表关系：拣货任务行（lazy=True 为按需加载）
    items = db.relationship('PickingTaskItem', backref='picking_task', cascade='all, delete-orphan', lazy=True)

    # 关联销售订单（反向关系：SalesOrder.picking_tasks）
    sales_order = db.relationship('SalesOrder', backref='picking_tasks')

    # 状态机：定义可接受的状态流转
    VALID_TRANSITIONS = {
        '待拣货': ['已完成', '已取消'],
        '已完成': [],
        '已取消': []
    }


class PickingTaskItem(db.Model):
    """
    拣货任务行（子表）
    - 复合主键：task_id + item_no
    - 关联库存物料(Inventory)
    """
    __tablename__ = 'PickingTaskItem'

    # 拣货任务ID（外键，复合主键之一）
    task_id = db.Column(db.String(255), db.ForeignKey('PickingTask.task_id'), primary_key=True)

    # 行号（复合主键之一，用于在任务内排序/定位）
    item_no = db.Column(db.Integer, primary_key=True)

    # 对应销售订单行号（用于追溯来源）
    sales_order_item_no = db.Column(db.Integer, nullable=False)

    # 物料ID（外键，关联库存主数据）
    material_id = db.Column(db.String(255), db.ForeignKey('Inventory.material_id'), nullable=False)

    # 需求数量（计划拣货数量，数值精度：10,2）
    required_quantity = db.Column(db.Numeric(10, 2))

    # 实际拣货数量（数值精度：10,2）
    picked_quantity = db.Column(db.Numeric(10, 2))

    # 计量单位（如 EA、PCS、BOX）
    unit = db.Column(db.String(50))

    # 存储位置（货位/库位，可为空）
    storage_location = db.Column(db.String(255), nullable=True, comment='存储位置')

    # 物料关系（便捷访问 Inventory）
    material = db.relationship('Inventory')


class DeliveryNote(db.Model):
    """
    交货单（出库单）
    - 与销售订单、拣货任务关联
    - 包含多条交货行(DeliveryItem)
    - 状态机：已创建 -> 已拣货 -> 已发货 -> 已过账；任意时点可能取消
    """
    __tablename__ = 'DeliveryNote'

    # 交货单号（主键）
    delivery_note_id = db.Column(db.String(255), primary_key=True)

    # 关联拣货任务（外键，非空）
    picking_task_id = db.Column(db.String(255), db.ForeignKey('PickingTask.task_id'), nullable=False)

    # 关联销售订单（外键，非空）
    sales_order_id = db.Column(db.String(255), db.ForeignKey('SalesOrder.sales_order_id'), nullable=False)

    # 交货日期（计划或实际的交货/出库日期，非空）
    delivery_date = db.Column(db.DateTime, nullable=False)

    # 仓库代码（执行出库的仓库）
    warehouse_code = db.Column(db.String(255), nullable=False)

    # 单据状态（枚举）：
    # '已创建' -> '已拣货' -> '已发货' -> '已过账'；任一前置状态可转 '已取消'
    status = db.Column(db.Enum(
        '已创建',
        '已拣货',
        '已发货',
        '已过账',
        '已取消'
    ), default='已创建', nullable=False)

    # 过账人（执行财务或库存过账的用户）
    posted_by = db.Column(db.String(255))

    # 过账时间
    posted_at = db.Column(db.DateTime)

    # 创建人
    created_by = db.Column(db.String(255))

    # 备注
    remarks = db.Column(db.Text)

    # 子表关系：交货行
    items = db.relationship('DeliveryItem', backref='delivery_note', cascade='all, delete-orphan', lazy=True)

    # 关联销售订单（反向关系：SalesOrder.delivery_notes）
    sales_order = db.relationship('SalesOrder', backref='delivery_notes')

    # 关联拣货任务（反向关系：PickingTask.delivery_note）
    picking_task = db.relationship('PickingTask', backref='delivery_note')

    # 状态机：定义可接受的状态流转
    VALID_TRANSITIONS = {
        '已创建': ['已拣货', '已取消'],
        '已拣货': ['已发货', '已取消'],
        '已发货': ['已过账'],
        '已过账': [],
        '已取消': []
    }


class DeliveryItem(db.Model):
    """
    交货单行
    - 复合主键：delivery_note_id + item_no
    - 记录计划与实际出库数量，用于对账与过账
    """
    __tablename__ = 'DeliveryItem'

    # 交货单号（外键，复合主键之一）
    delivery_note_id = db.Column(db.String(255), db.ForeignKey('DeliveryNote.delivery_note_id'), primary_key=True)

    # 行号（复合主键之一）
    item_no = db.Column(db.Integer, primary_key=True)

    # 对应销售订单行号（用于追溯来源与对账）
    sales_order_item_no = db.Column(db.Integer, nullable=False)

    # 物料ID（外键）
    material_id = db.Column(db.String(255), db.ForeignKey('Inventory.material_id'), nullable=False)

    # 计划交货数量（数值精度：18,4）
    planned_delivery_quantity = db.Column(db.Numeric(18, 4))

    # 实际交货数量（数值精度：18,4）
    actual_delivery_quantity = db.Column(db.Numeric(18, 4))

    # 计量单位
    unit = db.Column(db.String(50))

    # 物料关系（便捷访问 Inventory）
    material = db.relationship('Inventory')

    def is_fully_delivered(self):
        """
        判断该行是否已完全交付：
        actual_delivery_quantity >= planned_delivery_quantity 视为已完全交付
        """
        return Decimal(self.actual_delivery_quantity or 0) >= Decimal(self.planned_delivery_quantity or 0)


class StockChangeLog(db.Model):
    """
    库存变更日志
    - 记录库存数量变化的明细（可用于审计与追溯）
    - 支持记录前后数量及可用/预留/在库/待出等维度
    """
    __tablename__ = 'StockChangeLog'

    # 日志ID（主键，自增）
    id = db.Column(db.Integer, primary_key=True)

    # 物料ID（外键，必填）
    material_id = db.Column(db.String(255), db.ForeignKey('Inventory.material_id'), nullable=False)

    # 变更时间（默认当前时间）
    change_time = db.Column(db.DateTime, default=datetime.now)

    # 变更类型（释放分配、拣货、发货过账等）
    change_type = db.Column(db.String(50), nullable=False)

    # 本次变更的数量（正负皆可，单位与物料主单位一致）
    quantity_change = db.Column(db.Numeric(18, 4), nullable=False)

    # 变更前后 - 可用库存
    before_available = db.Column(db.Numeric(18, 4))
    after_available = db.Column(db.Numeric(18, 4))

    # 变更前后 - 已分配（预留）数量
    before_allocated = db.Column(db.Numeric(18, 4))
    after_allocated = db.Column(db.Numeric(18, 4))

    # 变更前后 - 物理库存（在库）
    before_physical = db.Column(db.Numeric(18, 4))
    after_physical = db.Column(db.Numeric(18, 4))

    # 变更前后 - 待出库数量（未发货、已分配/拣货中）
    before_pending_outbound = db.Column(db.Numeric(18, 4))
    after_pending_outbound = db.Column(db.Numeric(18, 4))

    # 引用发货单号
    reference_doc = db.Column(db.String(255))

    # 操作人
    operator = db.Column(db.String(255))

    # 仓库代码
    warehouse_code = db.Column(db.String(255))

    # 物料关系（反向关系：Inventory.stock_changes）
    material = db.relationship('Inventory', backref='stock_changes')


# 数量量化精度（与 Numeric(18, 4) 对齐）
QTY_QUANT = Decimal('0.0001')

def _normalize_qty(q):
    # 归一化数量：将输入转换为 Decimal，并四舍五入到 4 位小数
    q = Decimal(q or 0)
    # 避免出现超过 4 位小数
    q = q.quantize(QTY_QUANT, rounding=ROUND_HALF_UP)
    return q

def _resolve_operator(operator):
    # 获取操作者标识：
    # - 优先返回显式传入的 operator
    # - 其次尝试从 Flask-Login 的 current_user.username 获取
    # - 异常或不可用时回落为 "system"
    try:
        from flask_login import current_user
        if operator:
            return operator
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "username", "unknown")
    except Exception:
        pass
    return "system"

QTY_QUANT = Decimal('0.0001')  # 与 Numeric(18, 4) 对齐（与上方重复定义，保持一致）

def _to_decimal(x):
        # 安全地将输入转换为 Decimal：
        # - None 视为 0
        # - Decimal 原样返回
        # - 其他类型通过 str(x) 转换，避免 float 精度误差
        # - 转换失败抛出显式错误
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
    # 将任意输入量化到 4 位小数的 Decimal（ROUND_HALF_UP）
    return _to_decimal(x).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


class Inventory(db.Model):
    """
    库存模型：
    - available_stock：可用库存（可直接分配/销售）
    - physical_stock：账面总库存（实际在库）
    - allocated_stock：已分配（占用但未发货）
    - pending_outbound：待出库（通常拣货完成待发货）
    说明：模型方法会记录 StockChangeLog 以便审计；并通过 with_for_update 实现行级锁，需在事务中使用。
    """
    __tablename__ = 'Inventory'

    material_id = db.Column(db.String(255), primary_key=True, comment='物料编号')
    description = db.Column(db.String(255), nullable=False, comment='物料描述')
    base_unit = db.Column(db.String(255), nullable=False, comment='基本计量单位')
    storage_location = db.Column(db.String(255), nullable=False, comment='存储位置')

    # 库存四象限，均与 Numeric(18,4) 对齐并有默认值 0
    available_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='可用库存数量')
    physical_stock  = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='账面总库存')
    allocated_stock = db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='已分配库存')
    pending_outbound= db.Column(db.Numeric(18, 4), nullable=False, server_default=text('0'), comment='待出库量')

    def allocate_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        """
        占用库存：available -> allocated
        - 校验 qty > 0，且可用库存充足
        - 上锁当前物料记录（with_for_update）
        - 更新 available/allocated
        - 记录“拣货占用”日志
        返回：上锁后的库存记录（供调用方继续使用）
        """
        qty = _q(qty)
        if qty <= 0:
            return None

        # 行级锁，避免并发下超卖
        locked = (db.session.query(Inventory)
                  .filter_by(material_id=self.material_id)
                  .with_for_update()
                  .one_or_none())
        if locked is None:
            raise ValueError(f"物料 {self.material_id} 不存在（allocate）")

        # 读取变更前数量（转为 Decimal，确保精度一致）
        before_available = _to_decimal(locked.available_stock)
        before_allocated = _to_decimal(locked.allocated_stock)
        before_physical  = _to_decimal(locked.physical_stock)
        before_pending   = _to_decimal(locked.pending_outbound)

        # 充足性校验
        if before_available < qty:
            raise ValueError(f"{locked.material_id} 可用不足：可用 {before_available} < 需 {qty}")

        # 扣减可用，增加已分配
        locked.available_stock = _q(before_available - qty)
        locked.allocated_stock = _q(before_allocated + qty)

        # 写入审计日志（数量正向表示占用）
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
            after_physical=before_physical,  # 占用不影响物理库存
            before_pending_outbound=before_pending,
            after_pending_outbound=before_pending,
            reference_doc=(reference or ''),     # 参考单据号（如拣货任务/销售单等）
            operator=_resolve_operator(operator),# 操作者
            warehouse_code=(warehouse_code or locked.storage_location) # 仓库
        )
        db.session.add(log)
        return locked

    def release_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        """
        释放占用：allocated -> available
        - 校验 qty > 0，且已分配库存充足
        - 上锁、更新 allocated/available
        - 记录“释放分配”日志（quantity_change 为负）
        """
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

        # 充足性校验（不可释放超过已分配）
        if before_allocated < qty:
            raise ValueError(f"{locked.material_id} 已分配不足：已分配 {before_allocated} < 释放 {qty}")

        # 减少已分配，回补可用
        locked.allocated_stock = _q(before_allocated - qty)
        locked.available_stock = _q(before_available + qty)

        # 审计日志（负数代表释放）
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
            after_physical=before_physical,  # 释放不影响物理库存
            before_pending_outbound=before_pending,
            after_pending_outbound=before_pending,
            reference_doc=(reference or ''),
            operator=_resolve_operator(operator),
            warehouse_code=(warehouse_code or locked.storage_location)
        )
        db.session.add(log)
        return locked

    def ship_stock(self, qty, operator=None, warehouse_code=None, reference=None):
        """
        发货过账：从“已分配/物理/待出库”同时扣减，并重算“可用”
        典型顺序依赖：
        - before：应当已有拣货完成 -> 待出库 pending_outbound >= qty
        - 校验：allocated >= qty, physical >= qty, pending_outbound >= qty
        - 更新：allocated -= qty, physical -= qty, pending_outbound -= qty
                available = physical - allocated - pending_outbound
        - 记录“发货过账”日志（quantity_change 为负）
        """
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

        # 发货三重校验：防止负库存/越权扣减
        if before_allocated < qty:
            raise ValueError(f"{locked.material_id} 已分配不足：{before_allocated} < {qty}")
        if before_physical < qty:
            raise ValueError(f"{locked.material_id} 账面不足：{before_physical} < {qty}")
        if before_pending < qty:
            raise ValueError(f"{locked.material_id} 待出库不足：{before_pending} < {qty}")

        # 同步扣减三项，并重算可用库存（可用 = 物理 - 已分配 - 待出库）
        locked.allocated_stock  = _q(before_allocated - qty)
        locked.physical_stock   = _q(before_physical  - qty)
        locked.pending_outbound = _q(before_pending   - qty)
        locked.available_stock = _q(locked.physical_stock - locked.allocated_stock - locked.pending_outbound)

        # 审计日志（发货数量为负）
        log = StockChangeLog(
            material_id=locked.material_id,
            change_time=datetime.now(timezone.utc),
            change_type='发货过账',
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
