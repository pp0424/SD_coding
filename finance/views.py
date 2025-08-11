from flask import Blueprint, render_template, request, redirect, url_for, flash
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment
from finance.forms import InvoiceForm, PaymentForm, InvoiceSearchForm, PaymentSearchForm
from finance.models import db, CustomerInvoice, InvoiceItem
from order.models import SalesOrder, OrderItem
from delivery.models import DeliveryNote, DeliveryItem
from datetime import datetime
from database import db
from datetime import datetime

bp = Blueprint('finance', __name__, template_folder='templates')

# 首页
@bp.route('/')
def finance_home():
    return render_template('finance/1.html')

# 创建发票
@bp.route('/create-invoice', methods=['GET', 'POST'])
def create_invoice():
    order_id = request.args.get('order')
    delivery_ids_raw = request.args.get('delivery')
    delivery_ids = [d.strip() for d in delivery_ids_raw.split(',')] if delivery_ids_raw else []

    form = InvoiceForm()

    if request.method == 'GET':
        if order_id:
            sales_order = SalesOrder.query.get(order_id)
            if not sales_order:
                flash('未找到该订单信息', 'error')
                return redirect(url_for('finance.finance_home'))

            form.sales_order_id.data = sales_order.sales_order_id
            form.customer_id.data = sales_order.customer_id

            # 自动填入金额（合计订单项目金额）
            total = sum([item.item_amount or 0 for item in sales_order.items])
            tax = total * 0.13
            form.total_amount.data = total + tax
            form.tax_amount.data = tax

    if form.validate_on_submit():
        invoice = CustomerInvoice(
            invoice_id=form.invoice_id.data,
            customer_id=form.customer_id.data,
            sales_order_id=form.sales_order_id.data,
            delivery_note_ids=delivery_ids_raw,
            invoice_date=form.invoice_date.data,
            payment_deadline=form.payment_deadline.data,
            total_amount=form.total_amount.data,
            tax_amount=form.tax_amount.data,
            payment_status=form.payment_status.data,
            remarks=form.remarks.data
        )
        db.session.add(invoice)

        # 从发货单生成发票明细
        item_no = 1
        for delivery_id in delivery_ids:
            delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
            for d_item in delivery_items:
                order_item_id = f"{order_id}-{d_item.sales_order_item_no}"
                delivery_item_id = f"{delivery_id}-{d_item.item_no}"
                order_item = OrderItem.query.filter_by(sales_order_id=order_id, item_no=d_item.sales_order_item_no).first()
                if order_item:
                    inv_item = InvoiceItem(
                        invoice_id=invoice.invoice_id,
                        item_no=item_no,
                        delivery_item_id=delivery_item_id,
                        sales_order_item_id=order_item_id,
                        material_id=d_item.material_id,
                        invoiced_quantity=d_item.actual_delivery_quantity,
                        unit_price=order_item.sales_unit_price,
                        tax_amount=(order_item.sales_unit_price * d_item.actual_delivery_quantity * 0.13),
                        item_amount=(order_item.sales_unit_price * d_item.actual_delivery_quantity * 1.13),
                        unit=order_item.unit
                    )
                    db.session.add(inv_item)
                    item_no += 1

        db.session.commit()
        flash('发票创建成功')
        return redirect(url_for('finance.finance_home'))

    return render_template('finance/create-invoice.html', form=form, order_id=order_id, delivery_ids=delivery_ids_raw)

@bp.route('/api/search-delivery')
def api_search_delivery():
    order_id = request.args.get('order')
    delivery_raw = request.args.get('delivery', '')
    delivery_ids = [d.strip() for d in delivery_raw.split(',') if d.strip()]

    results = []

    if not order_id:
        return {"results": []}

    from delivery.models import DeliveryNote

    for delivery_id in delivery_ids:
        note = DeliveryNote.query.filter_by(delivery_note_id=delivery_id, sales_order_id=order_id).first()
        if note:
            results.append({
                'order_id': note.sales_order_id,
                'delivery_id': note.delivery_note_id
            })

    return {"results": results}



# 修改发票
@bp.route('/edit-invoice/<invoice_id>', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = CustomerInvoice.query.get_or_404(invoice_id)
    form = InvoiceForm(obj=invoice)
    if form.validate_on_submit():
        form.populate_obj(invoice)
        db.session.commit()
        flash('发票更新成功')
        return redirect(url_for('finance.finance_home'))
    return render_template('finance/edit-invoice.html', form=form, invoice_id=invoice_id)

# 查询发票
@bp.route('/search-invoice', methods=['GET', 'POST'])
def search_invoice():
    form = InvoiceSearchForm()
    results = []
    if form.validate_on_submit():
        query = CustomerInvoice.query
        if form.invoice_id.data:
            query = query.filter_by(invoice_id=form.invoice_id.data)
        if form.sales_order_id.data:
            query = query.filter_by(sales_order_id=form.sales_order_id.data)
        results = query.all()
    return render_template('finance/search-invoice.html', form=form, results=results)

# 创建收款记录
@bp.route('/create-payment', methods=['GET', 'POST'])
def create_payment():
    form = PaymentForm()
    if form.validate_on_submit():
        payment = CustomerPayment(**form.data)
        db.session.add(payment)
        db.session.commit()
        flash('收款记录创建成功')
        return redirect(url_for('finance.finance_home'))
    return render_template('finance/create-payment.html', form=form)

# 修改收款记录
@bp.route('/edit-payment/<payment_id>', methods=['GET', 'POST'])
def edit_payment(payment_id):
    payment = CustomerPayment.query.get_or_404(payment_id)
    form = PaymentForm(obj=payment)
    if form.validate_on_submit():
        form.populate_obj(payment)
        db.session.commit()
        flash('收款记录更新成功')
        return redirect(url_for('finance.finance_home'))
    return render_template('finance/edit-payment.html', form=form, payment_id=payment_id)

# 查询收款记录
@bp.route('/search-payment', methods=['GET', 'POST'])
def search_payment():
    form = PaymentSearchForm()
    results = []
    if form.validate_on_submit():
        query = CustomerPayment.query
        if form.payment_id.data:
            query = query.filter_by(payment_id=form.payment_id.data)
        if form.invoice_id.data:
            query = query.filter_by(invoice_id=form.invoice_id.data)
        results = query.all()
    return render_template('finance/search-payment.html', form=form, results=results)

# 查单据流
@bp.route('/document-flow', methods=['GET', 'POST'])
def document_flow():
    invoice_id = request.form.get('invoice_id')
    flow_info = {}
    if invoice_id:
        invoice = CustomerInvoice.query.get(invoice_id)
        if invoice:
            items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
            payments = CustomerPayment.query.filter_by(invoice_id=invoice_id).all()
            flow_info = {
                'invoice': invoice,
                'items': items,
                'payments': payments
            }
    return render_template('finance/document-flow.html', flow=flow_info)
