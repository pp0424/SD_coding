from flask import Blueprint, render_template, request, redirect, url_for, flash
from .models import DeliveryOrder, DeliveryOrderItem
from .forms import DeliveryOrderForm, DeliveryOrderEditForm, DeliveryOrderQueryForm
from database import db
from datetime import datetime

delivery_bp = Blueprint('delivery', __name__, template_folder='templates')

@delivery_bp.route('/')
def delivery_home():
    return render_template('delivery/index.html')

# 1. 创建发货流程
@delivery_bp.route('/create', methods=['GET', 'POST'])
def create_delivery():
    form = DeliveryOrderForm()
    if form.validate_on_submit():
        # 检查发货单编号唯一性（可自定义生成规则）
        delivery_id = f"D{int(datetime.utcnow().timestamp())}"
        delivery = DeliveryOrder(
            delivery_id=delivery_id,
            sales_order_id=form.sales_order_id.data,
            customer_id=form.customer_id.data,
            expected_delivery_date=form.expected_delivery_date.data,
            warehouse_code=form.warehouse_code.data,
            remarks=form.remarks.data,
            status='已创建'
        )
        db.session.add(delivery)
        for idx, item_form in enumerate(form.items.entries):
            item = DeliveryOrderItem(
                delivery_id=delivery_id,
                item_no=idx + 1,
                material_id=item_form.material_id.data,
                planned_qty=item_form.planned_qty.data,
                remarks=item_form.remarks.data
            )
            db.session.add(item)
        db.session.commit()
        flash(f'发货单创建成功，编号：{delivery_id}', 'success')
        return redirect(url_for('delivery.create_delivery'))
    return render_template('delivery/create_delivery.html', form=form)

# 2. 修改发货信息
@delivery_bp.route('/edit/<delivery_id>', methods=['GET', 'POST'])
def edit_delivery(delivery_id):
    delivery = DeliveryOrder.query.filter_by(delivery_id=delivery_id).first()
    if not delivery:
        flash('未找到该发货单', 'danger')
        return redirect(url_for('delivery.query_delivery'))
    can_edit = delivery.status != '已过账'
    form = DeliveryOrderEditForm(obj=delivery)
    if form.validate_on_submit() and can_edit:
        if form.expected_delivery_date.data:
            delivery.expected_delivery_date = form.expected_delivery_date.data
        if form.warehouse_code.data:
            delivery.warehouse_code = form.warehouse_code.data
        if form.remarks.data:
            delivery.remarks = form.remarks.data
        db.session.commit()
        flash('发货单信息已更新', 'success')
        return redirect(url_for('delivery.edit_delivery', delivery_id=delivery_id))
    return render_template('delivery/edit_delivery.html', form=form, delivery=delivery, can_edit=can_edit)

# 3. 查询发货状态
@delivery_bp.route('/query', methods=['GET', 'POST'])
def query_delivery():
    form = DeliveryOrderQueryForm(request.form)
    query = DeliveryOrder.query
    if form.validate_on_submit():
        if form.delivery_id.data:
            query = query.filter(DeliveryOrder.delivery_id.like(f"%{form.delivery_id.data}%"))
        if form.sales_order_id.data:
            query = query.filter(DeliveryOrder.sales_order_id.like(f"%{form.sales_order_id.data}%"))
        if form.date_from.data:
            query = query.filter(DeliveryOrder.expected_delivery_date >= form.date_from.data)
        if form.date_to.data:
            query = query.filter(DeliveryOrder.expected_delivery_date <= form.date_to.data)
        if form.status.data:
            query = query.filter(DeliveryOrder.status == form.status.data)
    results = query.all()
    return render_template('delivery/query_delivery.html', form=form, results=results)