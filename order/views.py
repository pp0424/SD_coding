from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify,session
from .forms import InquiryForm
from .forms import InquirySearchForm
from .models import Inquiry,InquiryItem
from .models import db,Quotation, QuotationItem,SalesOrder, OrderItem, Material
from sqlalchemy.orm import joinedload
from database import db
from datetime import datetime
from .models import Quotation, QuotationItem
from .forms import QuotationSearchForm
from sqlalchemy import and_, or_, func
from math import ceil

import random
import decimal

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
    # ===== 状态判断：若为“已评审”，仅允许修改备注字段 =====
    if inquiry.status == '已评审':
        flash('该询价单已评审，仅允许修改备注内容。其余字段不会被更改。', 'warning')

    # 允许更新备注字段
        inquiry.remarks = request.form.get('remarks')

    # 同样允许每个明细的“item_remarks”更新
        submitted_item_nos = request.form.getlist('item_no')
        item_remarks = request.form.getlist('item_remarks')
        item_remark_map = dict(zip(submitted_item_nos, item_remarks))

        for item in inquiry.items:
            if str(item.item_no) in item_remark_map:
                item.item_remarks = item_remark_map[str(item.item_no)]

        db.session.commit()

    # 构建 new_data（与 old_data 格式一致）供前端比对展示
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
        ],
        'inquiry_id': inquiry_id
    }

        return render_template('order/edit_inquiry_confirm_update.html', old=old_data, new=new_data, min=min)


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

    # 新增：注入 inquiry_id 供前端使用
    new_data['inquiry_id'] = inquiry_id

    return render_template('order/edit_inquiry_confirm_update.html', old=old_data, new=new_data,min=min)

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

@order_bp.route('/edit-quote', methods=['GET', 'POST'])
def edit_quote_prompt():
    if request.method == 'POST':
        quote_id = request.form.get('quotation_id')
        quotation = Quotation.query.options(joinedload(Quotation.items)).filter_by(quotation_id=quote_id).first()
        if quotation:
            return render_template('order/edit_quote_form.html', quotation=quotation)
        else:
            flash("未找到该报价单")
    return render_template('order/edit_quote_input.html')


@order_bp.route('/edit-quote/save', methods=['GET','POST'])
def edit_quote_save():
    quote_id = request.form.get('quotation_id')
    quotation = Quotation.query.options(joinedload(Quotation.items)).filter_by(quotation_id=quote_id).first()

    if not quotation:
        flash('未找到该报价单', 'danger')
        return redirect(url_for('order.edit_quote_prompt'))

    # ========== 原始数据（用于对比） ==========
    old_data = {
        "customer_id": quotation.customer_id,
        "inquiry_id": quotation.inquiry_id,
        "quotation_date": quotation.quotation_date.strftime('%Y-%m-%d') if quotation.quotation_date else '',
        "valid_until_date": quotation.valid_until_date.strftime('%Y-%m-%d') if quotation.valid_until_date else '',
        "total_amount": str(quotation.total_amount),
        "salesperson_id": quotation.salesperson_id,
        "remarks": quotation.remarks,
        "items": [
            {
                'item_no': item.item_no,
                'material_id': item.material_id,
                'quotation_quantity': str(item.quotation_quantity),
                'unit': item.unit,
                'unit_price': str(item.unit_price),
                'discount_rate': str(item.discount_rate),
                'item_amount': str(item.item_amount),
                'inquiry_item_id': item.inquiry_item_id or ''
            } for item in quotation.items
        ]
    }
    # ========== 状态校验：已审核则禁止修改关键信息 ==========
    if quotation.status == '已发送':
           flash('该报价单已审核，只允许修改备注、有效期等非关键内容。', 'warning')

    # 主表仅允许修改备注
           quotation.valid_until_date=request.form.get("valid_until_date")
           quotation.remarks = request.form.get("remarks")
           db.session.commit()

    # 构建新旧数据对比页
           new_data = old_data.copy()
           new_data["valid_until_date"]=quotation.valid_until_date
           new_data["remarks"] = quotation.remarks
           return render_template('order/edit_quote_confirm_update.html',old=old_data, new=new_data,quotation_id=quote_id, min=min,
                                   old_items_map={item['item_no']: item for item in old_data['items']},new_items_map={item['item_no']: item for item in old_data['items']},
                                   all_item_nos=[item['item_no'] for item in old_data['items']])



    # ========== 更新主表 ==========
    quotation.customer_id = request.form.get("customer_id")
    quotation.inquiry_id = request.form.get("inquiry_id")

    try:
        quotation.quotation_date = datetime.strptime(request.form.get("quotation_date"), '%Y-%m-%d')
        quotation.valid_until_date = datetime.strptime(request.form.get("valid_until_date"), '%Y-%m-%d')
    except Exception:
        flash("请填写合法的日期", "danger")
        return redirect(request.url)

    quotation.total_amount = float(request.form.get("total_amount") or 0)
    quotation.salesperson_id = request.form.get("salesperson_id")
    quotation.remarks = request.form.get("remarks")

    # ========== 子表同步 ==========
    item_nos = request.form.getlist('item_no')
    material_ids = request.form.getlist('material_id')
    quotation_quantities = request.form.getlist('quotation_quantity')
    units = request.form.getlist('unit')
    unit_prices = request.form.getlist('unit_price')
    discount_rates = request.form.getlist('discount_rate')
    item_amounts = request.form.getlist('item_amount')
    inquiry_item_ids = request.form.getlist('inquiry_item_id')

    new_items = []
    for i in range(len(item_nos)):
        if not item_nos[i] or not material_ids[i]:
            continue
        new_items.append({
            'item_no': int(item_nos[i]),
            'material_id': material_ids[i],
            'quotation_quantity': float(quotation_quantities[i] or 0),
            'unit': units[i],
            'unit_price': float(unit_prices[i] or 0),
            'discount_rate': float(discount_rates[i] or 0),
            'item_amount': float(item_amounts[i] or 0),
            'inquiry_item_id': inquiry_item_ids[i]
        })

    existing_items = {item.item_no: item for item in quotation.items}
    submitted_item_nos = [item['item_no'] for item in new_items]

    for item_data in new_items:
        item_no = item_data['item_no']
        if item_no in existing_items:
            item = existing_items[item_no]
        else:
            item = QuotationItem(quotation_id=quote_id, item_no=item_no)
            db.session.add(item)

        item.material_id = item_data['material_id']
        item.quotation_quantity = item_data['quotation_quantity']
        item.unit = item_data['unit']
        item.unit_price = item_data['unit_price']
        item.discount_rate = item_data['discount_rate']
        item.item_amount = item_data['item_amount']
        item.inquiry_item_id = item_data['inquiry_item_id']

    for old_item in quotation.items:
        if old_item.item_no not in submitted_item_nos:
            db.session.delete(old_item)

    db.session.commit()

    # ========== 新数据（对比用） ==========
    new_data = {
        "customer_id": quotation.customer_id,
        "inquiry_id": quotation.inquiry_id,
        "quotation_date": quotation.quotation_date.strftime('%Y-%m-%d') if quotation.quotation_date else '',
        "valid_until_date": quotation.valid_until_date.strftime('%Y-%m-%d') if quotation.valid_until_date else '',
        "total_amount": str(quotation.total_amount),
        "salesperson_id": quotation.salesperson_id,
        "remarks": quotation.remarks,
        "items": [
            {
                'item_no': item.item_no,
                'material_id': item.material_id,
                'quotation_quantity': str(item.quotation_quantity),
                'unit': item.unit,
                'unit_price': str(item.unit_price),
                'discount_rate': str(item.discount_rate),
                'item_amount': str(item.item_amount),
                'inquiry_item_id': item.inquiry_item_id or ''
            } for item in quotation.items
        ]
    }

    # ===== 识别并标记新增项（前端存在但数据库没有的 item_no） =====
    old_item_nos = {item['item_no'] for item in old_data['items']}
    for new_item in new_data['items']:
        if new_item['item_no'] not in old_item_nos:
            new_item['is_new'] = True
    
    old_items_map = {item['item_no']: item for item in old_data['items']}
    new_items_map = {item['item_no']: item for item in new_data['items']}

    all_item_nos = sorted(set(old_items_map.keys()) | set(new_items_map.keys())) 

    return render_template('order/edit_quote_confirm_update.html', old=old_data, new=new_data, quotation_id=quote_id,min=min,old_items_map=old_items_map,
    new_items_map=new_items_map,all_item_nos=all_item_nos)

@order_bp.route('/edit-quote/confirm_update', methods=['POST'])
def confirm_quote_update():
    quote_id = request.form.get('quotation_id')
    confirmed = request.form.get('confirm')

    if confirmed == 'yes':
        flash('已成功更新报价信息')
    else:
        flash('取消了修改，数据未更改')

    return redirect(url_for('order.edit_quote_prompt'))


@order_bp.route('/edit-quote/approve', methods=['POST'])
def approve_quotation():
    quote_id = request.form.get('quotation_id')
    quotation = Quotation.query.filter_by(quotation_id=quote_id).first()
    if quotation:
        quotation.status = '已确认'
        db.session.commit()
        flash('报价单状态已变更为“已确认”')
    return redirect(url_for('order.edit_quote_prompt'))

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

@order_bp.route('/api/quotation/<quotation_id>')
def get_quotation_data(quotation_id):
    quotation = Quotation.query.options(joinedload(Quotation.items)).filter_by(quotation_id=quotation_id).first()
    if not quotation:
        return jsonify({'success': False, 'message': '报价单不存在'}), 404

    return jsonify({
        'success': True,
        'data': {
            'customer_id': quotation.customer_id,
            'salesperson_id': quotation.salesperson_id,
            'remarks': quotation.remarks,
            'items': [
                {
                    'item_no': item.item_no,
                    'material_id': item.material_id,
                    'order_quantity': item.quotation_quantity,
                    'sales_unit_price': item.unit_price,
                    'unit': item.unit,
                    'item_amount': item.item_amount
                } for item in quotation.items
            ]
        }
    })


@order_bp.route('/api/check-material/<mat_id>')
def api_check_material(mat_id):
    exists = Material.query.get(mat_id) is not None
    return {'exists': exists}


@order_bp.route('/create-order', methods=['GET', 'POST'])
def create_order():
    if request.method == 'GET':
        return render_template('order/create_order.html')

    # POST 创建逻辑
    order_id = f"SO-{datetime.now().strftime('%Y%m%d-%H%M%S')}{random.randint(100,999)}"
    save_type = request.form.get('save_type')
    order = SalesOrder(
        sales_order_id=order_id,
        customer_id=request.form.get('customer_id'),
        quotation_id=request.form.get('quotation_id'),
        order_date=datetime.strptime(request.form.get('order_date'), '%Y-%m-%d'),
        required_delivery_date=datetime.strptime(request.form.get('required_delivery_date'), '%Y-%m-%d'),
        remarks=request.form.get('remarks'),
        status='草稿' if save_type == 'draft' else '已创建',
        total_amount=0
    )

    db.session.add(order)

    item_nos = request.form.getlist('item_no')
    material_ids = request.form.getlist('material_id')
    quantities = request.form.getlist('order_quantity')
    units = request.form.getlist('unit')
    prices = request.form.getlist('sales_unit_price')
    amounts = request.form.getlist('item_amount')

    total = 0
    for i in range(len(item_nos)):
        amt = float(amounts[i] or 0)
        item = OrderItem(
            sales_order_id=order_id,
            item_no=int(item_nos[i]),
            material_id=material_ids[i],
            order_quantity=float(quantities[i]),
            sales_unit_price=float(prices[i]),
            shipped_quantity=0,
            unshipped_quantity=float(quantities[i]),
            unit=units[i],
            item_amount=amt
        )
        db.session.add(item)
        total += amt

    order.total_amount = total
    db.session.commit()

    flash("订单创建完成 ✅" if save_type == 'create' else "草稿保存成功 ✅", "success")
    return redirect(url_for('order.order_detail', sales_order_id=order_id))


@order_bp.route('/order-detail/<sales_order_id>')
def order_detail(sales_order_id):
    order = SalesOrder.query.options(
        joinedload(SalesOrder.items).joinedload(OrderItem.material)
    ).filter_by(sales_order_id=sales_order_id).first()

    if not order:
        flash('订单不存在', 'danger')
        return redirect(url_for('order.create_order'))

    return render_template('order/order_detail.html', order=order)



@order_bp.route('/edit-order', methods=['GET', 'POST'])
def edit_order():
    order = None
    searched = False
    if request.method == 'POST':
        searched = True
        order_id = request.form.get('sales_order_id')  # 使用 .get 可避免 400 错误
        if order_id:
            order = SalesOrder.query.filter_by(sales_order_id=order_id).first()
        if not order:
            error = f"未找到订单号 {order_id}。请确认输入。"
    return render_template('order/edit_order.html', order=order, searched=searched)


@order_bp.route('/edit-order/basic/<order_id>', methods=['GET', 'POST'])
def edit_order_basic(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        # 提取表单内容
        updated_data = {
            'customer_id': request.form['customer_id'],
            'quotation_id': request.form['quotation_id'],
            'order_date': datetime.strptime(request.form['order_date'], '%Y-%m-%d'),
            'required_delivery_date': datetime.strptime(request.form['required_delivery_date'], '%Y-%m-%d'),
            'status': request.form['status'],
            'total_amount': float(request.form['total_amount']),
            'credit_check_result': request.form['credit_check_result'],
            'remarks': request.form['remarks']
        }

        # 将旧值与新值打包送入预览页面
        session['temp_update'] = {
            'order_id': order_id,
            'step': 'basic',
            'updated': updated_data
        }

        return redirect(url_for('order.preview_salesorder_changes'))

    return render_template('order/edit_order_basic.html', order=order)

@order_bp.route('/edit-order/items/<order_id>', methods=['GET', 'POST'])
def edit_order_items(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        updates = []
        row_count = int(request.form.get('row_count', 0))

        for i in range(row_count):
            item_no = request.form.get(f'item_no_{i}')
            material_id = request.form.get(f'material_id_{i}')

            # 如果 material_id 是空的，跳过此行
            if not material_id:
                continue

            update_data = {
                'material_id': material_id,
                'order_quantity': request.form.get(f'order_quantity_{i}'),
                'sales_unit_price': request.form.get(f'sales_unit_price_{i}'),
                'shipped_quantity': request.form.get(f'shipped_quantity_{i}'),
                'unshipped_quantity': request.form.get(f'unshipped_quantity_{i}'),
                'item_amount': request.form.get(f'item_amount_{i}'),
                'unit': request.form.get(f'unit_{i}')
            }

            if item_no == 'new':
                update_data['action'] = 'add'
            else:
                update_data['action'] = 'update'
                update_data['item_no'] = item_no

            updates.append(update_data)

        session['temp_update'] = {
            'order_id': order_id,
            'updates': updates,
            'step': 'items'
        }
        return redirect(url_for('order.preview_changes'))

    return render_template('order/edit_order_items.html', order=order)


@order_bp.route('/preview-salesorder-changes', methods=['GET', 'POST']) 
def preview_salesorder_changes():  #订单基本信息更新预览页
    temp_update = session.get('temp_update')
    if not temp_update or temp_update.get('step') != 'basic':
        return redirect(url_for('order.edit_order_basic'))

    order_id = temp_update['order_id']
    updates = temp_update['updated']
    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        if 'confirm' in request.form:
            # 执行数据库更新
            for field, new_val in updates.items():
                if hasattr(order, field):
                    setattr(order, field, new_val)
            db.session.commit()
            session.pop('temp_update')
            return redirect(url_for('order.order_detail', sales_order_id=order_id))
        elif 'cancel' in request.form:
            return redirect(url_for('order.edit_order_basic', order_id=order_id))

    old_data = {
        'customer_id': order.customer_id,
        'quotation_id': order.quotation_id or '',
        'order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else '',
        'required_delivery_date': order.required_delivery_date.strftime('%Y-%m-%d') if order.required_delivery_date else '',
        'status': order.status or '',
        'total_amount': float(order.total_amount),
        'credit_check_result': order.credit_check_result or '',
        'remarks': order.remarks or '',
    }

    return render_template('order/preview_salesorder.html', order=order, old_data=old_data, new_data=updates)



@order_bp.route('/preview-changes', methods=['GET', 'POST'])  # items更新预览页
def preview_changes():
    temp_update = session.get('temp_update')
    if not temp_update:
        return redirect(url_for('order.edit_order_items'))

    order_id = temp_update['order_id']
    updates = temp_update['updates']
    step = temp_update.get('step')

    order = SalesOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        if 'confirm' in request.form:
            for u in updates:
                action = u.get('action')

                if action == 'update':
                    try:
                        item_no = int(u['item_no'])
                    except (KeyError, ValueError, TypeError):
                        continue

                    item = OrderItem.query.filter_by(sales_order_id=order_id, item_no=item_no).first()
                    if item:
                        item.material_id = u['material_id']
                        item.order_quantity = u['order_quantity']
                        item.sales_unit_price = u['sales_unit_price']
                        item.shipped_quantity = u['shipped_quantity']
                        item.unshipped_quantity = u['unshipped_quantity']
                        item.item_amount = u['item_amount']
                        item.unit = u['unit']

                elif action == 'delete':
                    try:
                        item_no = int(u['item_no'])
                        OrderItem.query.filter_by(sales_order_id=order_id, item_no=item_no).delete()
                    except Exception:
                        continue

                elif action == 'add':
                    max_item_no = db.session.query(
                        db.func.max(OrderItem.item_no)
                    ).filter_by(sales_order_id=order_id).scalar() or 0

                    new_item = OrderItem(
                        sales_order_id=order_id,
                        item_no=max_item_no + 1,
                        material_id=u['material_id'],
                        order_quantity=u['order_quantity'],
                        sales_unit_price=u['sales_unit_price'],
                        shipped_quantity=u['shipped_quantity'],
                        unshipped_quantity=u['unshipped_quantity'],
                        item_amount=u['item_amount'],
                        unit=u['unit']
                    )
                    db.session.add(new_item)

            db.session.commit()
            
            session.pop('temp_update')
            return redirect(url_for('order.order_detail', sales_order_id=order_id))

        elif 'cancel' in request.form:
            if step == 'items':
                return redirect(url_for('order.edit_order_items', order_id=order_id))
            else:
                return redirect(url_for('order.edit_order_items'))

    # ----------- 构造比较数据 -----------
    old_items = {int(item.item_no): item for item in order.items}
    compare_list = []

    for u in updates:
        action = u.get('action')

        if action in ['update', 'delete']:
            try:
                item_no = int(u['item_no'])
                old = old_items.get(item_no)
                if not old:
                    continue
            except Exception:
                continue

            old_data = {
                'material_id': old.material_id,
                'order_quantity': float(old.order_quantity or 0),
                'sales_unit_price': float(old.sales_unit_price or 0),
                'shipped_quantity': float(old.shipped_quantity or 0),
                'unshipped_quantity': float(old.unshipped_quantity or 0),
                'item_amount': float(old.item_amount or 0),
                'unit': old.unit or ''
            }

            if action == 'update':
                new_data = {
                    'material_id': u['material_id'],
                    'order_quantity': float(u.get('order_quantity') or 0),
                    'sales_unit_price': float(u.get('sales_unit_price') or 0),
                    'shipped_quantity': float(u.get('shipped_quantity') or 0),
                    'unshipped_quantity': float(u.get('unshipped_quantity') or 0),
                    'item_amount': float(u.get('item_amount') or 0),
                    'unit': u.get('unit') or ''
                }
                compare_list.append({
                    'action': 'update',
                    'item_no': item_no,
                    'old': old_data,
                    'new': new_data
                })

            elif action == 'delete':
                compare_list.append({
                    'action': 'delete',
                    'item_no': item_no,
                    'old': old_data,
                    'new': None
                })

        elif action == 'add':
            try:
                new_data = {
                    'material_id': u['material_id'],
                    'order_quantity': float(u.get('order_quantity') or 0),
                    'sales_unit_price': float(u.get('sales_unit_price') or 0),
                    'shipped_quantity': float(u.get('shipped_quantity') or 0),
                    'unshipped_quantity': float(u.get('unshipped_quantity') or 0),
                    'item_amount': float(u.get('item_amount') or 0),
                    'unit': u.get('unit') or ''
                }
                compare_list.append({
                    'action': 'add',
                    'item_no': None,
                    'old': None,
                    'new': new_data
                })
            except Exception:
                continue

    return render_template('order/preview_order_items.html', order=order, compare_list=compare_list)







@order_bp.route('/query-order', methods=['GET', 'POST'])
def query_order():
    page = int(request.args.get('page', 1))
    per_page = 10

    # 同时支持 POST（表单）和 GET（分页）
    form = request.form if request.method == 'POST' else request.args
    show_all = form.get('show_all') == '1'

    query = SalesOrder.query.options(joinedload(SalesOrder.items))

    if not show_all:
        if form.get('sales_order_id'):
            query = query.filter(SalesOrder.sales_order_id.like(f"%{form.get('sales_order_id')}%"))
        if form.get('customer_id'):
            query = query.filter(SalesOrder.customer_id.like(f"%{form.get('customer_id')}%"))
        if form.get('status') and form.get('status') != '全部':
            query = query.filter(SalesOrder.status == form.get('status'))
        if form.get('date_from'):
            query = query.filter(SalesOrder.order_date >= form.get('date_from'))
        if form.get('date_to'):
            query = query.filter(SalesOrder.order_date <= form.get('date_to'))
        if form.get('min_total'):
            query = query.filter(SalesOrder.total_amount >= float(form.get('min_total')))
        if form.get('max_total'):
            query = query.filter(SalesOrder.total_amount <= float(form.get('max_total')))
        if form.get('material_keyword'):
            query = query.join(SalesOrder.items).join(OrderItem.material).filter(
                Material.description.ilike(f"%{form.get('material_keyword')}%")
            ).distinct()

    total = query.count()
    orders = query.order_by(SalesOrder.order_date.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = ceil(total / per_page)

    return render_template('order/query_order.html',
                           orders=orders,
                           page=page,
                           total_pages=total_pages,
                           form_data=form)
