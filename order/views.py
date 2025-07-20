
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .forms import InquiryForm
from .forms import InquirySearchForm
from .models import Inquiry,InquiryItem
from sqlalchemy.orm import joinedload
from database import db
from datetime import datetime

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
    inquiry = get_inquiry_by_id(inquiry_id)
    if not inquiry:
        flash("找不到要更新的询价单")
        return redirect(url_for('order.edit_prompt'))

    old_data = {
        'customer_id': inquiry.customer_id,
        'inquiry_date': inquiry.inquiry_date,
        'expected_delivery_date': inquiry.expected_delivery_date,
        'expected_total_amount': inquiry.expected_total_amount,
        'salesperson_id': inquiry.salesperson_id,
        'remarks': inquiry.remarks
    }

    inquiry.customer_id = request.form.get('customer_id')
    inquiry.inquiry_date = datetime.strptime(request.form.get('inquiry_date'), '%Y-%m-%d')
    inquiry.expected_delivery_date = datetime.strptime(request.form.get('expected_delivery_date'), '%Y-%m-%d')
    inquiry.expected_total_amount = float(request.form.get('expected_total_amount'))
    inquiry.salesperson_id = request.form.get('salesperson_id')
    inquiry.remarks = request.form.get('remarks')

    db.session.flush()  # 暂不提交，先展示新旧数据对比

    return render_template('order/edit_inquiry_confirm_update.html', old=old_data, new=inquiry)

# 3️⃣ 确认更新
@order_bp.route('/edit-inquiry/confirm_update', methods=['POST'])
def confirm_update():
    confirmed = request.form.get('confirm')
    inquiry_id = request.form.get('inquiry_id')

    if confirmed == 'yes':
        db.session.commit()
        flash('✅ 已成功更新询价信息')
    else:
        db.session.rollback()
        flash('⚠️ 取消了修改，数据未更改')

    return redirect(url_for('order.edit_prompt'))

# 4️⃣ 审核状态更新
@order_bp.route('/edit-inquiry/approve', methods=['POST'])
def approve_inquiry():
    inquiry_id = request.form.get('inquiry_id')
    inquiry = Inquiry.query.filter_by(inquiry_id=inquiry_id).first()
    if inquiry:
        inquiry.status = '已评审'
        db.session.commit()
        flash('✅ 状态已变为已评审')
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

@order_bp.route('/create-quote')
def create_quote():
    return render_template('order/create_quote.html')

@order_bp.route('/edit-quote')
def edit_quote():
    return render_template('order/edit_quote.html')

@order_bp.route('/query-quote')
def query_quote():
    return render_template('order/query_quote.html')

@order_bp.route('/create-order')
def create_order():
    return render_template('order/create_order.html')

@order_bp.route('/edit-order')
def edit_order():
    return render_template('order/edit_order.html')

@order_bp.route('/query-order')
def query_order():
    return render_template('order/query_order.html')
