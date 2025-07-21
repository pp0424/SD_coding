
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .forms import InquiryForm
from .forms import InquirySearchForm
from .models import Inquiry,InquiryItem
from .models import db,Quotation, QuotationItem
from sqlalchemy.orm import joinedload
from database import db
from datetime import datetime
from .models import Quotation, QuotationItem
from .forms import QuotationSearchForm

order_bp = Blueprint('order', __name__, template_folder='templates')

@order_bp.route('/')
def order_home():
    return render_template('order/index.html')

@order_bp.route('/create-inquiry',methods=['GET', 'POST'])
def create_inquiry():
    
    form = InquiryForm()
    if request.method == 'POST':
        existing = Inquiry.query.filter_by(inquiry_id=form.inquiry_id.data).first()
        if existing:
            flash('该询价单号存在，无法创建')
            return render_template('order/create_Inquiry_with_items.html', form=form)

        # 获取状态
        status = '草稿' if 'save' in request.form else '已评审'

        # 保存主表数据
        inquiry = Inquiry(
            inquiry_id=form.inquiry_id.data,
            customer_id=form.customer_id.data,
            inquiry_date=form.inquiry_date.data,
            expected_delivery_date=form.expected_delivery_date.data,
            status=status,
            expected_total_amount=form.expected_total_amount.data,
            salesperson_id=form.salesperson_id.data,
            remarks=form.remarks.data
        )
        db.session.add(inquiry)

        # 明细
        item_count = int(request.form['item_count'])
        for i in range(item_count):
            item = InquiryItem(
                inquiry_id=form.inquiry_id.data,
                item_no=i + 1,
                material_id=request.form[f'material_id_{i}'],
                inquiry_quantity=request.form[f'inquiry_quantity_{i}'],
                unit=request.form.get(f'unit_{i}'),
                expected_unit_price=request.form.get(f'expected_unit_price_{i}'),
                item_remarks=request.form.get(f'item_remarks_{i}')
            )
            db.session.add(item)

        db.session.commit()

        if status == '已评审':
            flash('提交成功！询价状态为：已评审')
            return redirect(url_for('order.create_inquiry'))
        else:
            flash('已保存为草稿 ✅')
            # 注意：不跳转，直接再次渲染页面保留原值

    return render_template('order/create_Inquiry_with_items.html', form=form)

def get_inquiry_by_id(inquiry_id):
    return Inquiry.query.options(joinedload(Inquiry.items)).filter_by(inquiry_id=inquiry_id).first()

@order_bp.route('/edit-inquiry', methods=['GET', 'POST'])
def edit_prompt():
    if request.method == 'POST':
        inquiry_id = request.form.get('inquiry_id')
        inquiry = get_inquiry_by_id(inquiry_id)
        if inquiry:
            return render_template('order/edit_inquiry_form.html', inquiry=inquiry)
        else:
            flash("未找到对应的询价单")
    return render_template('order/edit_inquiry_input.html')

# 2️⃣ 保存更新
@order_bp.route('/edit-inquiry/save', methods=['POST'])
def edit_save():
    inquiry_id = request.form.get('inquiry_id')
    inquiry = Inquiry.query.options(joinedload(Inquiry.items)).filter_by(inquiry_id=inquiry_id).first()

    if not inquiry:
        flash('未找到该询价单')
        return redirect(url_for('order.edit_prompt'))

    # ===== 原始数据（用于对比） =====
    old_data = {
        'customer_id': inquiry.customer_id,
        'inquiry_date': inquiry.inquiry_date.strftime('%Y-%m-%d') if inquiry.inquiry_date else '',
        'expected_delivery_date': inquiry.expected_delivery_date.strftime('%Y-%m-%d') if inquiry.expected_delivery_date else '',
        'expected_total_amount': str(inquiry.expected_total_amount),
        'salesperson_id': inquiry.salesperson_id,
        'remarks': inquiry.remarks,
        'items': [
            {
                'item_no': item.item_no,
                'material_id': item.material_id,
                'inquiry_quantity': str(item.inquiry_quantity),
                'unit': item.unit,
                'expected_unit_price': str(item.expected_unit_price or ''),
                'item_remarks': item.item_remarks or ''
            }
            for item in inquiry.items
        ]
    }

    # ===== 更新主表 Inquiry =====
    inquiry.customer_id = request.form.get('customer_id')
    inquiry.inquiry_date = datetime.strptime(request.form.get('inquiry_date'), '%Y-%m-%d')
    inquiry.expected_delivery_date = datetime.strptime(request.form.get('expected_delivery_date'), '%Y-%m-%d')
    inquiry.expected_total_amount = float(request.form.get('expected_total_amount') or 0)
    inquiry.salesperson_id = request.form.get('salesperson_id')
    inquiry.remarks = request.form.get('remarks')

    # ===== 获取行项字段列表 =====
    item_nos = request.form.getlist('item_no')
    material_ids = request.form.getlist('material_id')
    inquiry_quantities = request.form.getlist('inquiry_quantity')
    units = request.form.getlist('unit')
    expected_unit_prices = request.form.getlist('expected_unit_price')
    item_remarks = request.form.getlist('item_remarks')

    # 构建前端提交的新行项数据列表
    new_items = []
    for i in range(len(item_nos)):
        if not item_nos[i] or not material_ids[i]:
            continue  # 跳过空行
        new_items.append({
            'item_no': int(item_nos[i]),
            'material_id': material_ids[i],
            'inquiry_quantity': float(inquiry_quantities[i] or 0),
            'unit': units[i],
            'expected_unit_price': float(expected_unit_prices[i] or 0),
            'item_remarks': item_remarks[i]
        })

    # ========== 行项同步处理 ==========
    # 已存在 item_no 的映射
    existing_items = {item.item_no: item for item in inquiry.items}

    # 保留 item_no，用于判断是否删除
    submitted_item_nos = [item['item_no'] for item in new_items]

    for new_item in new_items:
        item_no = new_item['item_no']
        if item_no in existing_items:
            # 更新已有项
            item = existing_items[item_no]
            item.material_id = new_item['material_id']
            item.inquiry_quantity = new_item['inquiry_quantity']
            item.unit = new_item['unit']
            item.expected_unit_price = new_item['expected_unit_price']
            item.item_remarks = new_item['item_remarks']
        else:
            # 插入新项
            new_entry = InquiryItem(
                inquiry_id=inquiry_id,
                item_no=item_no,
                material_id=new_item['material_id'],
                inquiry_quantity=new_item['inquiry_quantity'],
                unit=new_item['unit'],
                expected_unit_price=new_item['expected_unit_price'],
                item_remarks=new_item['item_remarks']
            )
            db.session.add(new_entry)

    # 删除未提交的旧项
    for item in inquiry.items:
        if item.item_no not in submitted_item_nos:
            db.session.delete(item)

    db.session.commit()

    # ========== 新数据汇总（用于对比） ==========
    new_data = {
        'customer_id': inquiry.customer_id,
        'inquiry_date': inquiry.inquiry_date.strftime('%Y-%m-%d') if inquiry.inquiry_date else '',
        'expected_delivery_date': inquiry.expected_delivery_date.strftime('%Y-%m-%d') if inquiry.expected_delivery_date else '',
        'expected_total_amount': str(inquiry.expected_total_amount),
        'salesperson_id': inquiry.salesperson_id,
        'remarks': inquiry.remarks,
        'items': [
            {
                'item_no': item.item_no,
                'material_id': item.material_id,
                'inquiry_quantity': str(item.inquiry_quantity),
                'unit': item.unit,
                'expected_unit_price': str(item.expected_unit_price or ''),
                'item_remarks': item.item_remarks or ''
            }
            for item in inquiry.items
        ]
    }

    return render_template('order/edit_inquiry_confirm_update.html', old=old_data, new=new_data)

# 3️⃣ 确认更新
@order_bp.route('/edit-inquiry/confirm_update', methods=['POST'])
def confirm_update():
    confirmed = request.form.get('confirm')
    inquiry_id = request.form.get('inquiry_id')

    if confirmed == 'yes':
        flash('✅ 已成功更新询价信息！', 'success')
    else:
        flash('⚠️ 已取消修改，数据未更新。', 'warning')
        # 回滚未提交的数据（理论上已 commit，但前端用户体验仍可保持一致）
        return redirect(url_for('order.edit_prompt'))

    return redirect(url_for('order.edit_prompt'))


# 4️⃣ 审核状态更新
@order_bp.route('/edit-inquiry/approve', methods=['POST'])
def approve_inquiry():
    inquiry_id = request.form.get('inquiry_id')
    inquiry = Inquiry.query.filter_by(inquiry_id=inquiry_id).first()

    if not inquiry:
        flash('❌ 未找到对应询价单', 'danger')
        return redirect(url_for('order.edit_prompt'))

    inquiry.status = '已评审'
    db.session.commit()

    flash('✅ 状态已更新为“已评审”', 'success')
    return redirect(url_for('order.edit_prompt'))


@order_bp.route('/query-inquiry', methods=['GET', 'POST'])
def query_inquiry():
    form = InquirySearchForm()
    results = []

    if request.method == 'POST':
        # ✅ 点击“显示全部”
        if form.show_all.data:
            results = Inquiry.query.options(joinedload(Inquiry.items)).all()

        # ✅ 点击“查询”
        elif form.submit.data:
            query = Inquiry.query

            if form.inquiry_id.data:
                query = query.filter(Inquiry.inquiry_id.like(f"%{form.inquiry_id.data}%"))
            if form.customer_id.data:
                query = query.filter(Inquiry.customer_id.like(f"%{form.customer_id.data}%"))
            if form.date_start.data:
                query = query.filter(Inquiry.inquiry_date >= form.date_start.data)
            if form.date_end.data:
                query = query.filter(Inquiry.inquiry_date <= form.date_end.data)
            if form.material_id.data:
                # 通过关联表查询物料编号
                query = query.join(InquiryItem).filter(InquiryItem.material_id.like(f"%{form.material_id.data}%"))

            results = query.options(joinedload(Inquiry.items)).all()

    return render_template('order/query_inquiry.html', form=form, results=results)

@order_bp.route('/create-quote', methods=['GET', 'POST'])
def create_quotation():
    if request.method == 'POST':
        # 获取主表数据
        quotation_id = request.form.get('quotation_id')
        customer_id = request.form.get('customer_id')
        inquiry_id = request.form.get('inquiry_id')
        quotation_date = request.form.get('quotation_date')
        valid_until_date = request.form.get('valid_until_date')
        status = request.form.get('status')  # '草稿' or '已评审'
        total_amount = request.form.get('total_amount') or 0
        salesperson_id = request.form.get('salesperson_id')
        remarks = request.form.get('remarks')

        # 是否已存在，避免重复创建
        quotation = Quotation.query.get(quotation_id)
        if not quotation:
            quotation = Quotation(quotation_id=quotation_id)
            db.session.add(quotation)

        # 更新主表字段
        quotation.customer_id = customer_id
        quotation.inquiry_id = inquiry_id
        quotation.quotation_date = datetime.strptime(quotation_date, '%Y-%m-%d')
        quotation.valid_until_date = datetime.strptime(valid_until_date, '%Y-%m-%d')
        quotation.status = status
        quotation.total_amount = float(total_amount)
        quotation.salesperson_id = salesperson_id
        quotation.remarks = remarks

        # 清除旧的明细行（也可优化为比对更新）
        QuotationItem.query.filter_by(quotation_id=quotation_id).delete()

        # 获取明细数据
        item_nos = request.form.getlist('item_no')
        material_ids = request.form.getlist('material_id')
        quotation_quantities = request.form.getlist('quotation_quantity')
        unit_prices = request.form.getlist('unit_price')
        discount_rates = request.form.getlist('discount_rate')
        item_amounts = request.form.getlist('item_amount')
        units = request.form.getlist('unit')
        inquiry_item_ids = request.form.getlist('inquiry_item_id')

        for i in range(len(item_nos)):
            item = QuotationItem(
                quotation_id=quotation_id,
                item_no=int(item_nos[i]),
                material_id=material_ids[i],
                quotation_quantity=float(quotation_quantities[i]),
                unit_price=float(unit_prices[i]),
                discount_rate=float(discount_rates[i]),
                item_amount=float(item_amounts[i]),
                unit=units[i],
                inquiry_item_id=inquiry_item_ids[i]
            )
            db.session.add(item)

        db.session.commit()

        flash(f"报价单 {quotation_id} 保存成功（状态：{status}）", 'success')

        if status == '已评审':
            return redirect(url_for('order.create_quotation'))

    return render_template('order/create_quotation.html')

@order_bp.route('/edit-quote')
def edit_quote():
    return render_template('order/edit_quote.html')

@order_bp.route('/query-quote', methods=['GET', 'POST'])
def query_quotation():
    form = QuotationSearchForm()
    results = []

    if form.validate_on_submit():
        if form.show_all.data:
            results = Quotation.query.options(joinedload(Quotation.items)).all()
        elif form.submit.data:
            query = Quotation.query

            if form.quotation_id.data:
                query = query.filter(Quotation.quotation_id.like(f"%{form.quotation_id.data}%"))
            if form.customer_id.data:
                query = query.filter(Quotation.customer_id.like(f"%{form.customer_id.data}%"))
            if form.date_start.data:
                query = query.filter(Quotation.valid_until_date >= form.date_start.data)
            if form.date_end.data:
                query = query.filter(Quotation.valid_until_date <= form.date_end.data)
            if form.material_id.data:
                query = query.join(QuotationItem).filter(QuotationItem.material_id.like(f"%{form.material_id.data}%"))
            
            results = query.options(joinedload(Quotation.items)).all()

    return render_template('order/query_quotation.html', form=form, results=results)

@order_bp.route('/create-order')
def create_order():
    return render_template('order/create_order.html')

@order_bp.route('/edit-order')
def edit_order():
    return render_template('order/edit_order.html')

@order_bp.route('/query-order')
def query_order():
    return render_template('order/query_order.html')
