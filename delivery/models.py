# delivery/models.py

from flask_login import current_user
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
    
    VALID_TRANSITIONS = {
        '已创建': ['待拣货', '已取消'],
        '待拣货': ['已拣货', '已取消'],
        '已拣货': ['待发货', '已过账'],
        '待发货': ['已发货'],
        '已发货': ['已过账', '已完成'],
        '已过账': ['已完成'],
        '已完成': [],
        '已取消': []
    }
    
    def change_status(self, new_status, user=None):
        if new_status not in self.VALID_TRANSITIONS.get(self.status, []):
            raise ValueError(f"Invalid status transition from {self.status} to {new_status}")
            
        # Handle special state transitions
        if new_status == '已拣货':
            self._handle_picked()
        elif new_status == '已发货':
            self._handle_shipped()
        elif new_status == '已过账':
            self._handle_posted(user)
            
        self.status = new_status
    
    def _handle_picked(self):
        """Update inventory when items are picked"""
        for item in self.items:
            material = item.material
            # Reduce available stock, increase allocated quantity
            material.available_stock -= item.planned_delivery_quantity
            material.allocated_stock += item.planned_delivery_quantity
            # Create stock movement log
            self._create_stock_log(
                material, 
                '拣货', 
                -item.planned_delivery_quantity,
                "拣货操作减少可用库存"
            )
    
    def _handle_shipped(self):
        """Update inventory when items are shipped"""
        for item in self.items:
            material = item.material
            # Reduce allocated quantity and physical stock
            material.allocated_stock -= item.actual_delivery_quantity
            material.physical_stock -= item.actual_delivery_quantity
            # Create stock movement log
            self._create_stock_log(
                material, 
                '发货', 
                -item.actual_delivery_quantity,
                "发货操作减少实际库存"
            )
    
    def _handle_posted(self, user):
        """Handle posting to financial system"""
        self.posted_by = user
        self.posted_at = datetime.utcnow()
        # Create financial posting record would go here
    
    def _create_stock_log(self, material, change_type, quantity_change, notes):
        log = StockChangeLog(
            material_id=material.material_id,
            change_type=change_type,
            quantity_change=quantity_change,
            before_quantity=material.physical_stock,
            after_quantity=material.physical_stock + quantity_change,
            reference_doc=self.delivery_note_id,
            operator=current_user.username if current_user else 'system',
            warehouse_code=self.warehouse_code,
            notes=notes
        )
        db.session.add(log)

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
