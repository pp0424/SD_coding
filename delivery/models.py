# models.py for delivery module
from database import db
from datetime import datetime

class DeliveryNote(db.Model):
    __tablename__ = 'DeliveryNote'
    delivery_id = db.Column(db.String, primary_key=True)  # 发货单编号
    sales_order_id = db.Column(db.String, nullable=False)  # 关联销售订单编号
    customer_id = db.Column(db.String, nullable=False)     # 客户编号
    expected_delivery_date = db.Column(db.Date, nullable=False)  # 预计发货日期
    warehouse_code = db.Column(db.String, nullable=False)  # 发货仓库代码
    status = db.Column(db.String, default='已创建')         # 发货单状态
    remarks = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('DeliveryItem', backref='delivery_order', cascade="all, delete-orphan", lazy='joined')

class DeliveryItem(db.Model):
    __tablename__ = 'DeliveryItem'
    delivery_id = db.Column(db.String, db.ForeignKey('DeliveryNote.delivery_id'), primary_key=True)
    item_no = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String, nullable=False)     # 物料编号
    planned_qty = db.Column(db.Float, nullable=False)      # 计划发货数量
    picked_qty = db.Column(db.Float, default=0)            # 已拣货数量
    remarks = db.Column(db.String)

class Material(db.Model):
    __tablename__ = 'Material'
    __table_args__ = {'extend_existing': True}  # ✅ 解决“重复定义表”错误

    material_id = db.Column(db.String(255), primary_key=True, comment='物料编号，唯一键')
    description = db.Column(db.String(255), nullable=False, comment='物料描述')
    base_unit = db.Column(db.String(255), nullable=False, comment='基本计量单位')
    storage_location = db.Column(db.String(255), nullable=False, comment='存储位置')
    available_stock = db.Column(db.Numeric, comment='当前可用库存')
