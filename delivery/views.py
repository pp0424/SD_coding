# delivery/views.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from . import forms
from .models import DeliveryNote, DeliveryItem, StockChangeLog
from order.models import SalesOrder,SalesOrder, OrderItem, Material
from datetime import datetime
from math import ceil
from database import db
import uuid


delivery_bp = Blueprint('delivery', __name__, template_folder='templates')



# delivery/views.py
@delivery_bp.route('/')
@login_required
def index():
    # 获取待处理发货单
    pending_deliveries = DeliveryNote.query.filter(
        DeliveryNote.status.in_(['已创建', '已拣货'])
    ).order_by(DeliveryNote.delivery_date.asc()).limit(5).all()
    
    # 获取今日发货单
    today = datetime.utcnow().date()
    today_deliveries = DeliveryNote.query.filter(
        db.func.date(DeliveryNote.delivery_date) == today
    ).limit(5).all()
    
    # 获取库存预警物料
    low_stock_materials = Material.query.filter(
        Material.available_stock < 50
    ).order_by(Material.available_stock.asc()).limit(5).all()
    
    # 获取待过账发货单
    to_post_deliveries = DeliveryNote.query.filter_by(
        status='已创建'
    ).order_by(DeliveryNote.delivery_date.asc()).limit(5).all()
    
    # 获取发货单状态统计
    stats = {
        'created': DeliveryNote.query.filter_by(status='已创建').count(),
        'picked': DeliveryNote.query.filter_by(status='已拣货').count(),
        'posted': DeliveryNote.query.filter_by(status='已过账').count(),
        'canceled': DeliveryNote.query.filter_by(status='已取消').count(),
    }
    
    return render_template('delivery/index.html', 
                          pending_deliveries=pending_deliveries,
                          today_deliveries=today_deliveries,
                          low_stock_materials=low_stock_materials,
                          to_post_deliveries=to_post_deliveries,
                          stats=stats,
                          today=today)

@delivery_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_delivery():
    form = forms.CreateDeliveryForm()
    
    if request.method == 'GET':
        so_id = request.args.get('so_id')
        if so_id:
            form.sales_order_id.data = so_id
    
    if form.validate_on_submit():
        so_id = form.sales_order_id.data
        sales_order = SalesOrder.query.get(so_id)
        
        if not sales_order:
            flash('销售订单不存在', 'danger')
            return redirect(url_for('delivery.create_delivery'))
        
        # 生成发货单号
        delivery_id = f"DN-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4]}"
        
        # 创建发货单
        delivery_note = DeliveryNote(
            delivery_note_id=delivery_id,
            sales_order_id=so_id,
            delivery_date=form.expected_delivery_date.data,
            warehouse_code=form.warehouse_code.data,
            status='已创建'
        )
        
        # 添加行项
        for item_form in form.items:
            order_item = next((item for item in sales_order.items if item.material_id == item_form.material_id.data), None)
            if not order_item:
                continue
                
            if item_form.planned_delivery_quantity.data > order_item.unshipped_quantity:
                flash(f"物料 {item_form.material_id.data} 的发货数量超过未发货数量", 'danger')
                return redirect(url_for('delivery.create_delivery'))
            
            delivery_item = DeliveryItem(
                delivery_note_id=delivery_id,
                item_no=len(delivery_note.items) + 1,
                sales_order_item_no=order_item.item_no,
                material_id=item_form.material_id.data,
                planned_delivery_quantity=item_form.planned_delivery_quantity.data,
                actual_delivery_quantity=0,
                unit=order_item.material.base_unit
            )
            delivery_note.items.append(delivery_item)
        
        db.session.add(delivery_note)
        db.session.commit()
        flash('发货单创建成功', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    # 加载销售订单项
    if form.sales_order_id.data:
        sales_order = SalesOrder.query.get(form.sales_order_id.data)
        if sales_order:
            form.items = []
            for item in sales_order.items:
                if item.unshipped_quantity > 0:
                    item_form = forms.DeliveryItemForm()
                    item_form.material_id = item.material_id
                    item_form.material_desc = item.material.description
                    item_form.order_quantity = item.order_quantity
                    item_form.unshipped_quantity = item.unshipped_quantity
                    item_form.planned_delivery_quantity = item.unshipped_quantity
                    form.items.append_entry(item_form)
    
    return render_template('delivery/create_delivery.html', form=form)

@delivery_bp.route('/edit/<delivery_id>', methods=['GET', 'POST'])
@login_required
def edit_delivery(delivery_id):
    delivery_note = DeliveryNote.query.get_or_404(delivery_id)
    
    if delivery_note.status not in ['已创建', '已拣货']:
        flash('当前状态不允许修改', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    form = forms.EditDeliveryForm(obj=delivery_note)
    
    if form.validate_on_submit():
        delivery_note.delivery_date = form.expected_delivery_date.data
        delivery_note.warehouse_code = form.warehouse_code.data
        delivery_note.remarks = form.remarks.data
        db.session.commit()
        flash('发货单已更新', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    return render_template('delivery/edit_delivery.html', form=form, delivery=delivery_note)

@delivery_bp.route('/list', methods=['GET', 'POST'])
@login_required
def delivery_list():
    form = forms.SearchDeliveryForm()
    deliveries = DeliveryNote.query.order_by(DeliveryNote.delivery_date.desc())
    
    if form.validate_on_submit():
        if form.delivery_id.data:
            deliveries = deliveries.filter(DeliveryNote.delivery_note_id.contains(form.delivery_id.data))
        if form.sales_order_id.data:
            deliveries = deliveries.filter(DeliveryNote.sales_order_id.contains(form.sales_order_id.data))
        if form.start_date.data:
            deliveries = deliveries.filter(DeliveryNote.delivery_date >= form.start_date.data)
        if form.end_date.data:
            end_date = datetime.combine(form.end_date.data, datetime.max.time())
            deliveries = deliveries.filter(DeliveryNote.delivery_date <= end_date)
        if form.status.data:
            deliveries = deliveries.filter_by(status=form.status.data)
    
    deliveries = deliveries.all()
    return render_template('delivery/delivery_list.html', deliveries=deliveries, form=form)

@delivery_bp.route('/detail/<delivery_id>')
@login_required
def delivery_detail(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    return render_template('delivery/delivery_detail.html', delivery=delivery)

PER_PAGE = 20  # 每页显示20条记录
@delivery_bp.route('/stock_changes', methods=['GET', 'POST'])
@login_required
def stock_changes():
    # 获取查询参数
    material_id = request.args.get('material_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    delivery_id = request.args.get('delivery_id', '')
    warehouse_code = request.args.get('warehouse_code', '')
    page = int(request.args.get('page', 1))
    
    # 构建基础查询
    query = StockChangeLog.query.filter_by(change_type='发货').order_by(StockChangeLog.change_time.desc())
    
    # 应用过滤条件
    if material_id:
        query = query.filter(StockChangeLog.material_id.contains(material_id))
    if start_date:
        query = query.filter(StockChangeLog.change_time >= start_date)
    if end_date:
        query = query.filter(StockChangeLog.change_time <= end_date + ' 23:59:59')
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.contains(delivery_id))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.contains(warehouse_code))
    
    # 计算总记录数和总页数
    total_records = query.count()
    total_pages = ceil(total_records / PER_PAGE)
    
    # 分页查询
    changes = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    
    return render_template('delivery/stock_changes.html', 
                          changes=changes,
                          page=page,
                          total_pages=total_pages,
                          total_records=total_records)

@delivery_bp.route('/post/<delivery_id>', methods=['GET', 'POST'])
@login_required
def post_delivery(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    
    if delivery.status != '已创建':
        flash('当前状态不允许过账', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    form = forms.PostDeliveryForm()
    
    # 初始化表单数据
    if request.method == 'GET':
        form.actual_delivery_date.data = delivery.delivery_date
        for item in delivery.items:
            item_form = forms.DeliveryItemPostForm()
            item_form.material_id = item.material_id
            item_form.planned_quantity = item.planned_delivery_quantity
            item_form.actual_quantity = item.planned_delivery_quantity
            form.items.append_entry(item_form)
    
    if form.validate_on_submit():
        # 更新发货单状态
        delivery.status = '已过账'
        delivery.posted_at = datetime.utcnow()
        delivery.posted_by = current_user.username
        delivery.delivery_date = form.actual_delivery_date.data
        
        # 更新行项和库存
        for i, item in enumerate(delivery.items):
            item_form = form.items[i]
            item.actual_delivery_quantity = item_form.actual_quantity.data
            
            # 更新库存
            material = Material.query.get(item.material_id)
            before_stock = material.available_stock
            material.available_stock -= item_form.actual_quantity.data
            after_stock = material.available_stock
            
            # 记录库存变动
            stock_change = StockChangeLog(
                material_id=item.material_id,
                change_type='发货',
                quantity_change=-item_form.actual_quantity.data,
                before_quantity=before_stock,
                after_quantity=after_stock,
                reference_doc=delivery_id,
                operator=current_user.username,
                warehouse_code=delivery.warehouse_code
            )
            db.session.add(stock_change)
            
            # 更新销售订单行项
            order_item = OrderItem.query.filter_by(
                sales_order_id=delivery.sales_order_id,
                item_no=item.sales_order_item_no
            ).first()
            
            if order_item:
                order_item.shipped_quantity += item_form.actual_quantity.data
                order_item.unshipped_quantity = order_item.order_quantity - order_item.shipped_quantity
        
        # 更新销售订单状态
        sales_order = SalesOrder.query.get(delivery.sales_order_id)
        if all(item.unshipped_quantity <= 0 for item in sales_order.items):
            sales_order.status = '已完成'
        else:
            sales_order.status = '部分发货'
        
        db.session.commit()
        flash('发货过账成功', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    return render_template('delivery/post_delivery.html', form=form, delivery=delivery)

@delivery_bp.route('/posted_stock_changes', methods=['GET', 'POST'])
@login_required
def posted_stock_changes():
    # 获取查询参数
    material_id = request.args.get('material_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    delivery_id = request.args.get('delivery_id', '')
    warehouse_code = request.args.get('warehouse_code', '')
    page = int(request.args.get('page', 1))
    
    # 构建基础查询 - 只查询发货类型的变动
    query = StockChangeLog.query.filter_by(change_type='发货').order_by(StockChangeLog.change_time.desc())
    
    # 应用过滤条件
    if material_id:
        query = query.filter(StockChangeLog.material_id.contains(material_id))
    if start_date:
        query = query.filter(StockChangeLog.change_time >= start_date)
    if end_date:
        query = query.filter(StockChangeLog.change_time <= end_date + ' 23:59:59')
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.contains(delivery_id))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.contains(warehouse_code))
    
    # 计算总记录数和总页数
    total_records = query.count()
    total_pages = ceil(total_records / PER_PAGE)
    
    # 分页查询
    changes = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    
    return render_template('delivery/posted_stock_changes.html', 
                          changes=changes,
                          page=page,
                          total_pages=total_pages,
                          total_records=total_records)