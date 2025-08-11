from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment
from finance.forms import InvoiceForm, PaymentForm, InvoiceSearchForm, PaymentSearchForm
from order.models import SalesOrder, OrderItem
from delivery.models import DeliveryNote, DeliveryItem
from datetime import datetime, date
from database import db
import uuid

bp = Blueprint('finance', __name__, template_folder='templates')

# 1. 财务首页
@bp.route('/')
def finance_home():
    """财务首页，显示各个模块入口"""
    return render_template('finance/1.html')

# 2. 创建发票相关路由
@bp.route('/create-invoice')
def create_invoice_search():
    """创建发票 - 搜索页面"""
    return render_template('finance/create-invoice.html')

@bp.route('/api/search-order-delivery', methods=['POST'])
def api_search_order_delivery():
    """搜索订单和发货单信息的API"""
    order_id = request.form.get('order_id', '').strip()
    delivery_id = request.form.get('delivery_id', '').strip()
    
    if not order_id or not delivery_id:
        return jsonify({'success': False, 'message': '请输入订单号和发货单号'})
    
    # 查询订单信息
    sales_order = SalesOrder.query.get(order_id)
    if not sales_order:
        return jsonify({'success': False, 'message': '未找到该订单信息'})
    
    # 查询发货单信息
    delivery_note = DeliveryNote.query.filter_by(
        delivery_note_id=delivery_id, 
        sales_order_id=order_id
    ).first()
    if not delivery_note:
        return jsonify({'success': False, 'message': '未找到对应的发货单信息'})
    
    # 获取发货单明细
    delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
    
    return jsonify({
        'success': True,
        'order_info': {
            'sales_order_id': sales_order.sales_order_id,
            'customer_id': sales_order.customer_id,
            'order_date': sales_order.order_date.strftime('%Y-%m-%d') if sales_order.order_date else '',
        },
        'delivery_info': {
            'delivery_note_id': delivery_note.delivery_note_id,
            'delivery_date': delivery_note.delivery_date.strftime('%Y-%m-%d') if delivery_note.delivery_date else '',
        },
        'items': [{
            'material_id': item.material_id,
            'actual_delivery_quantity': float(item.actual_delivery_quantity),
            'unit': item.unit or '',
            'sales_order_item_no': item.sales_order_item_no
        } for item in delivery_items]
    })

@bp.route('/invoice-content')
def invoice_content():
    """发票详情页面 - 用于创建发票"""
    order_id = request.args.get('order_id')
    delivery_id = request.args.get('delivery_id')
    
    if not order_id or not delivery_id:
        flash('缺少订单号或发货单号', 'error')
        return redirect(url_for('finance.create_invoice_search'))
    
    # 获取订单和发货单信息
    sales_order = SalesOrder.query.get(order_id)
    delivery_note = DeliveryNote.query.filter_by(
        delivery_note_id=delivery_id,
        sales_order_id=order_id
    ).first()
    
    if not sales_order or not delivery_note:
        flash('未找到相关信息', 'error')
        return redirect(url_for('finance.create_invoice_search'))
    
    # 获取发货明细和对应的订单明细
    delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
    invoice_items = []
    total_amount = 0
    
    for d_item in delivery_items:
        order_item = OrderItem.query.filter_by(
            sales_order_id=order_id,
            item_no=d_item.sales_order_item_no
        ).first()
        
        if order_item:
            item_amount = float(order_item.sales_unit_price) * float(d_item.actual_delivery_quantity)
            tax_amount = item_amount * 0.13
            total_item_amount = item_amount + tax_amount
            
            invoice_items.append({
                'material_id': d_item.material_id,
                'quantity': float(d_item.actual_delivery_quantity),
                'unit_price': float(order_item.sales_unit_price),
                'unit': order_item.unit or '',
                'item_amount': item_amount,
                'tax_amount': tax_amount,
                'total_amount': total_item_amount,
                'delivery_item_id': f"{delivery_id}-{d_item.item_no}",
                'sales_order_item_id': f"{order_id}-{d_item.sales_order_item_no}"
            })
            total_amount += total_item_amount
    
    return render_template('finance/invoice-content.html', 
                         sales_order=sales_order,
                         delivery_note=delivery_note,
                         invoice_items=invoice_items,
                         total_amount=total_amount,
                         tax_amount=total_amount * 0.13 / 1.13)

@bp.route('/save-invoice', methods=['POST'])
def save_invoice():
    """保存发票信息"""
    try:
        # 生成发票编号
        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # 获取表单数据
        customer_id = request.form.get('customer_id')
        sales_order_id = request.form.get('sales_order_id')
        delivery_note_id = request.form.get('delivery_note_id')
        invoice_date = datetime.strptime(request.form.get('invoice_date'), '%Y-%m-%d')
        payment_deadline = datetime.strptime(request.form.get('payment_deadline'), '%Y-%m-%d').date()
        total_amount = float(request.form.get('total_amount', 0))
        tax_amount = float(request.form.get('tax_amount', 0))
        remarks = request.form.get('remarks', '')
        
        # 创建发票
        invoice = CustomerInvoice(
            invoice_id=invoice_id,
            customer_id=customer_id,
            sales_order_id=sales_order_id,
            delivery_note_ids=delivery_note_id,
            invoice_date=invoice_date,
            payment_deadline=payment_deadline,
            total_amount=total_amount,
            tax_amount=tax_amount,
            payment_status='未付款',
            remarks=remarks
        )
        db.session.add(invoice)
        
        # 创建发票明细
        delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_note_id).all()
        item_no = 1
        
        for d_item in delivery_items:
            order_item = OrderItem.query.filter_by(
                sales_order_id=sales_order_id,
                item_no=d_item.sales_order_item_no
            ).first()
            
            if order_item:
                inv_item = InvoiceItem(
                    invoice_id=invoice_id,
                    item_no=item_no,
                    delivery_item_id=f"{delivery_note_id}-{d_item.item_no}",
                    sales_order_item_id=f"{sales_order_id}-{d_item.sales_order_item_no}",
                    material_id=d_item.material_id,
                    invoiced_quantity=d_item.actual_delivery_quantity,
                    unit_price=order_item.sales_unit_price,
                    tax_amount=order_item.sales_unit_price * d_item.actual_delivery_quantity * 0.13,
                    item_amount=order_item.sales_unit_price * d_item.actual_delivery_quantity * 1.13,
                    unit=order_item.unit
                )
                db.session.add(inv_item)
                item_no += 1
        
        db.session.commit()
        flash(f'发票创建成功，发票编号：{invoice_id}', 'success')
        return redirect(url_for('finance.finance_home'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'保存失败：{str(e)}', 'error')
        return redirect(url_for('finance.create_invoice_search'))

# 3. 修改发票相关路由
@bp.route('/edit-invoice')
def edit_invoice_search():
    """修改发票 - 搜索页面"""
    return render_template('finance/edit-invoice.html')

@bp.route('/invoice-revision/<invoice_id>')
def invoice_revision(invoice_id):
    """发票修改页面"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        flash('未找到该发票', 'error')
        return redirect(url_for('finance.edit_invoice_search'))
    
    # 获取发票明细
    invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    return render_template('finance/invoice-revision.html', 
                         invoice=invoice, 
                         invoice_items=invoice_items)

@bp.route('/update-invoice/<invoice_id>', methods=['POST'])
def update_invoice(invoice_id):
    """更新发票信息"""
    try:
        invoice = CustomerInvoice.query.get(invoice_id)
        if not invoice:
            flash('未找到该发票', 'error')
            return redirect(url_for('finance.edit_invoice_search'))
        
        # 更新发票信息
        invoice.invoice_date = datetime.strptime(request.form.get('invoice_date'), '%Y-%m-%d')
        invoice.payment_deadline = datetime.strptime(request.form.get('payment_deadline'), '%Y-%m-%d').date()
        invoice.total_amount = float(request.form.get('total_amount', 0))
        invoice.tax_amount = float(request.form.get('tax_amount', 0))
        invoice.payment_status = request.form.get('payment_status', '未付款')
        invoice.remarks = request.form.get('remarks', '')
        
        db.session.commit()
        flash('发票更新成功', 'success')
        return redirect(url_for('finance.finance_home'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'error')
        return redirect(url_for('finance.invoice_revision', invoice_id=invoice_id))

# 4. 查询发票
@bp.route('/search-invoice', methods=['GET', 'POST'])
def search_invoice():
    """查询发票"""
    results = []
    if request.method == 'POST':
        invoice_id = request.form.get('invoice_id', '').strip()
        sales_order_id = request.form.get('sales_order_id', '').strip()
        customer_id = request.form.get('customer_id', '').strip()
        
        query = CustomerInvoice.query
        
        if invoice_id:
            query = query.filter(CustomerInvoice.invoice_id.like(f'%{invoice_id}%'))
        if sales_order_id:
            query = query.filter(CustomerInvoice.sales_order_id.like(f'%{sales_order_id}%'))
        if customer_id:
            query = query.filter(CustomerInvoice.customer_id.like(f'%{customer_id}%'))
        
        results = query.all()
    
    return render_template('finance/search-invoice.html', results=results)

@bp.route('/api/invoice-detail/<invoice_id>')
def api_invoice_detail(invoice_id):
    """获取发票详细信息API"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        return jsonify({'success': False, 'message': '未找到发票信息'})
    
    invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    return jsonify({
        'success': True,
        'invoice': {
            'invoice_id': invoice.invoice_id,
            'customer_id': invoice.customer_id,
            'sales_order_id': invoice.sales_order_id,
            'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
            'payment_deadline': invoice.payment_deadline.strftime('%Y-%m-%d'),
            'total_amount': float(invoice.total_amount),
            'tax_amount': float(invoice.tax_amount),
            'payment_status': invoice.payment_status,
            'remarks': invoice.remarks or ''
        },
        'items': [{
            'material_id': item.material_id,
            'invoiced_quantity': float(item.invoiced_quantity),
            'unit_price': float(item.unit_price),
            'item_amount': float(item.item_amount or 0),
            'unit': item.unit or ''
        } for item in invoice_items]
    })

# 5. 创建收款记录相关路由
@bp.route('/create-payment')
def create_payment_search():
    """创建收款记录 - 搜索页面"""
    return render_template('finance/create-payment-search.html')

@bp.route('/payment-content/<invoice_id>')
def payment_content(invoice_id):
    """收款记录创建页面"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        flash('未找到该发票', 'error')
        return redirect(url_for('finance.create_payment_search'))
    
    # 计算已收款金额
    paid_amount = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or 0
    remaining_amount = float(invoice.total_amount) - float(paid_amount)
    
    return render_template('finance/payment-content.html', 
                         invoice=invoice,
                         paid_amount=float(paid_amount),
                         remaining_amount=remaining_amount)

@bp.route('/save-payment', methods=['POST'])
def save_payment():
    """保存收款记录"""
    try:
        # 生成收款单号
        payment_id = f"PAY-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # 获取表单数据
        invoice_id = request.form.get('invoice_id')
        customer_id = request.form.get('customer_id')
        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d')
        payment_amount = float(request.form.get('payment_amount', 0))
        payment_method = request.form.get('payment_method', '银行转账')
        write_off_amount = float(request.form.get('write_off_amount', 0))
        remarks = request.form.get('remarks', '')
        
        # 创建收款记录
        payment = CustomerPayment(
            payment_id=payment_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            payment_date=payment_date,
            payment_amount=payment_amount,
            payment_method=payment_method,
            write_off_amount=write_off_amount,
            status='已确认',
            remarks=remarks
        )
        db.session.add(payment)
        
        # 更新发票付款状态
        invoice = CustomerInvoice.query.get(invoice_id)
        if invoice:
            total_paid = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or 0
            total_paid += payment_amount
            
            if total_paid >= float(invoice.total_amount):
                invoice.payment_status = '已付款'
            else:
                invoice.payment_status = '部分付款'
        
        db.session.commit()
        flash(f'收款记录创建成功，收款单号：{payment_id}', 'success')
        return redirect(url_for('finance.finance_home'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'保存失败：{str(e)}', 'error')
        return redirect(url_for('finance.create_payment_search'))

# 6. 修改收款记录相关路由
@bp.route('/edit-payment')
def edit_payment_search():
    """修改收款记录 - 搜索页面"""
    return render_template('finance/edit-payment-search.html')

@bp.route('/payment-revision/<payment_id>')
def payment_revision(payment_id):
    """收款记录修改页面"""
    payment = CustomerPayment.query.get(payment_id)
    if not payment:
        flash('未找到该收款记录', 'error')
        return redirect(url_for('finance.edit_payment_search'))
    
    # 获取对应的发票信息
    invoice = CustomerInvoice.query.get(payment.invoice_id)
    
    return render_template('finance/payment-revision.html', 
                         payment=payment, 
                         invoice=invoice)

@bp.route('/update-payment/<payment_id>', methods=['POST'])
def update_payment(payment_id):
    """更新收款记录"""
    try:
        payment = CustomerPayment.query.get(payment_id)
        if not payment:
            flash('未找到该收款记录', 'error')
            return redirect(url_for('finance.edit_payment_search'))
        
        # 更新收款记录
        payment.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d')
        payment.payment_amount = float(request.form.get('payment_amount', 0))
        payment.payment_method = request.form.get('payment_method', '银行转账')
        payment.write_off_amount = float(request.form.get('write_off_amount', 0))
        payment.status = request.form.get('status', '已确认')
        payment.remarks = request.form.get('remarks', '')
        
        db.session.commit()
        flash('收款记录更新成功', 'success')
        return redirect(url_for('finance.finance_home'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'error')
        return redirect(url_for('finance.payment_revision', payment_id=payment_id))

# 7. 查询收款记录
@bp.route('/search-payment', methods=['GET', 'POST'])
def search_payment():
    """查询收款记录"""
    results = []
    if request.method == 'POST':
        payment_id = request.form.get('payment_id', '').strip()
        invoice_id = request.form.get('invoice_id', '').strip()
        customer_id = request.form.get('customer_id', '').strip()
        
        query = CustomerPayment.query
        
        if payment_id:
            query = query.filter(CustomerPayment.payment_id.like(f'%{payment_id}%'))
        if invoice_id:
            query = query.filter(CustomerPayment.invoice_id.like(f'%{invoice_id}%'))
        if customer_id:
            query = query.filter(CustomerPayment.customer_id.like(f'%{customer_id}%'))
        
        results = query.all()
    
    return render_template('finance/search-payment.html', results=results)

# 8. 查单据流
@bp.route('/document-flow', methods=['GET', 'POST'])
def document_flow():
    """查单据流"""
    flow_info = {}
    if request.method == 'POST':
        invoice_id = request.form.get('invoice_id', '').strip()
        sales_order_id = request.form.get('sales_order_id', '').strip()
        
        if invoice_id:
            invoice = CustomerInvoice.query.get(invoice_id)
            if invoice:
                # 获取发票明细
                invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
                # 获取收款记录
                payments = CustomerPayment.query.filter_by(invoice_id=invoice_id).all()
                # 获取订单信息
                sales_order = SalesOrder.query.get(invoice.sales_order_id)
                # 获取发货单信息
                delivery_notes = []
                if invoice.delivery_note_ids:
                    delivery_ids = [d.strip() for d in invoice.delivery_note_ids.split(',')]
                    delivery_notes = DeliveryNote.query.filter(DeliveryNote.delivery_note_id.in_(delivery_ids)).all()
                
                flow_info = {
                    'invoice': invoice,
                    'invoice_items': invoice_items,
                    'payments': payments,
                    'sales_order': sales_order,
                    'delivery_notes': delivery_notes
                }
        
        elif sales_order_id:
            # 通过订单号查找相关单据
            sales_order = SalesOrder.query.get(sales_order_id)
            if sales_order:
                invoices = CustomerInvoice.query.filter_by(sales_order_id=sales_order_id).all()
                delivery_notes = DeliveryNote.query.filter_by(sales_order_id=sales_order_id).all()
                
                flow_info = {
                    'sales_order': sales_order,
                    'invoices': invoices,
                    'delivery_notes': delivery_notes
                }
    
    return render_template('finance/document-flow.html', flow_info=flow_info)

@bp.route('/flowinfo/<invoice_id>')
def flowinfo(invoice_id):
    """单据流详细信息页面"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        flash('未找到该发票', 'error')
        return redirect(url_for('finance.document_flow'))
    
    # 获取完整的单据流信息
    invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    payments = CustomerPayment.query.filter_by(invoice_id=invoice_id).all()
    sales_order = SalesOrder.query.get(invoice.sales_order_id)
    
    # 获取发货单和发货明细
    delivery_info = []
    if invoice.delivery_note_ids:
        delivery_ids = [d.strip() for d in invoice.delivery_note_ids.split(',')]
        for delivery_id in delivery_ids:
            delivery_note = DeliveryNote.query.get(delivery_id)
            if delivery_note:
                delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
                delivery_info.append({
                    'note': delivery_note,
                    'items': delivery_items
                })
    
    return render_template('finance/flowinfo.html',
                         invoice=invoice,
                         invoice_items=invoice_items,
                         payments=payments,
                         sales_order=sales_order,
                         delivery_info=delivery_info)

@bp.route('/api/material-flow/<material_id>')
def api_material_flow(material_id):
    """根据物料编号查询流转信息API"""
    # 查找包含该物料的发票明细
    invoice_items = InvoiceItem.query.filter_by(material_id=material_id).all()
    
    flow_data = []
    for item in invoice_items:
        invoice = CustomerInvoice.query.get(item.invoice_id)
        if invoice:
            payments = CustomerPayment.query.filter_by(invoice_id=item.invoice_id).all()
            
            flow_data.append({
                'invoice_id': invoice.invoice_id,
                'sales_order_id': invoice.sales_order_id,
                'customer_id': invoice.customer_id,
                'material_id': item.material_id,
                'invoiced_quantity': float(item.invoiced_quantity),
                'unit_price': float(item.unit_price),
                'item_amount': float(item.item_amount or 0),
                'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
                'payment_status': invoice.payment_status,
                'payments': [{
                    'payment_id': p.payment_id,
                    'payment_date': p.payment_date.strftime('%Y-%m-%d'),
                    'payment_amount': float(p.payment_amount),
                    'payment_method': p.payment_method
                } for p in payments]
            })
    
    return jsonify({
        'success': True,
        'material_id': material_id,
        'flow_data': flow_data
    })

# 辅助路由 - 用于AJAX查询
@bp.route('/api/check-invoice/<invoice_id>')
def api_check_invoice(invoice_id):
    """检查发票是否存在的API"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if invoice:
        return jsonify({
            'success': True,
            'message': '发票信息查询成功',
            'invoice': {
                'invoice_id': invoice.invoice_id,
                'customer_id': invoice.customer_id,
                'sales_order_id': invoice.sales_order_id
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': '未找到该发票信息'
        })

@bp.route('/api/check-payment/<payment_id>')
def api_check_payment(payment_id):
    """检查收款记录是否存在的API"""
    payment = CustomerPayment.query.get(payment_id)
    if payment:
        return jsonify({
            'success': True,
            'message': '收款记录查询成功',
            'payment': {
                'payment_id': payment.payment_id,
                'invoice_id': payment.invoice_id,
                'customer_id': payment.customer_id
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': '未找到该收款记录'
        })