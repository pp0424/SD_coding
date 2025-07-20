
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .forms import InquiryForm
from .models import Inquiry,InquiryItem
from database import db

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

@order_bp.route('/edit-inquiry')
def edit_inquiry():
    return render_template('order/edit_inquiry.html')

@order_bp.route('/query-inquiry')
def query_inquiry():
    return render_template('order/query_inquiry.html')

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
