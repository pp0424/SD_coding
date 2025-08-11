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
def create_invoice():
    """创建发票 - 搜索页面，对应create-invoice.html"""
    return render_template('finance/create-invoice.html')

@bp.route('/api/search-order-delivery', methods=['POST'])
def api_search_order_delivery():
    """搜索订单和发货单信息的API"""
    order_number = request.json.get('order_number', '').strip()
    delivery_numbers = request.json.get('delivery_numbers', '').strip()
    
    if not order_number or not delivery_numbers:
        return jsonify({'success': False, 'message': '请输入订单号和发货单号'})
    
    # 处理多个发货单号（逗号分隔）
    delivery_ids = [d.strip() for d in delivery_numbers.split(',') if d.strip()]
    
    # 查询订单信息
    sales_order = SalesOrder.query.get(order_number)
    if not sales_order:
        return jsonify({'success': False, 'message': '未找到该订单信息'})
    
    # 验证发货单信息
    valid_deliveries = []
    for delivery_id in delivery_ids:
        delivery_note = DeliveryNote.query.filter_by(
            delivery_note_id=delivery_id, 
            sales_order_id=order_number
        ).first()
        if delivery_note:
            valid_deliveries.append({
                'order_id': delivery_note.sales_order_id,
                'delivery_id': delivery_note.delivery_note_id
            })
    
    if not valid_deliveries:
        return jsonify({'success': False, 'message': '未找到有效的发货单信息'})
    
    return jsonify({
        'success': True,
        'results': valid_deliveries,
        'order_info': {
            'sales_order_id': sales_order.sales_order_id,
            'customer_id': sales_order.customer_id
        }
    })

@bp.route('/invoice-content')
def invoice_content():
    """发票详情页面，对应invoice content.html"""
    order_id = request.args.get('order_id')
    delivery_id = request.args.get('delivery_id')
    
    if not order_id or not delivery_id:
        flash('缺少订单号或发货单号', 'error')
        return redirect(url_for('finance.create_invoice'))
    
    # 获取订单和发货单信息
    sales_order = SalesOrder.query.get(order_id)
    delivery_note = DeliveryNote.query.filter_by(
        delivery_note_id=delivery_id,
        sales_order_id=order_id
    ).first()
    
    if not sales_order or not delivery_note:
        flash('未找到相关信息', 'error')
        return redirect(url_for('finance.create_invoice'))
    
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
                'total_amount': total_item_amount
            })
            total_amount += total_item_amount
    
    return render_template('finance/invoice content.html', 
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
        
        # 获取表单数据（从URL参数或表单数据获取）
        order_id = request.form.get('order_id') or request.args.get('order_id')
        delivery_id = request.form.get('delivery_id') or request.args.get('delivery_id')
        
        if not order_id or not delivery_id:
            flash('缺少必要的订单或发货单信息', 'error')
            return redirect(url_for('finance.create_invoice'))
        
        # 获取订单信息
        sales_order = SalesOrder.query.get(order_id)
        if not sales_order:
            flash('未找到订单信息', 'error')
            return redirect(url_for('finance.create_invoice'))
        
        # 计算发票金额
        delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
        total_amount = 0
        
        for d_item in delivery_items:
            order_item = OrderItem.query.filter_by(
                sales_order_id=order_id,
                item_no=d_item.sales_order_item_no
            ).first()
            if order_item:
                item_amount = float(order_item.sales_unit_price) * float(d_item.actual_delivery_quantity)
                total_amount += item_amount * 1.13  # 含税
        
        tax_amount = total_amount * 0.13 / 1.13
        
        # 创建发票
        invoice = CustomerInvoice(
            invoice_id=invoice_id,
            customer_id=sales_order.customer_id,
            sales_order_id=order_id,
            delivery_note_ids=delivery_id,
            invoice_date=datetime.now(),
            payment_deadline=(datetime.now() + datetime.timedelta(days=30)).date(),
            total_amount=total_amount,
            tax_amount=tax_amount,
            payment_status='未付款',
            remarks=''
        )
        db.session.add(invoice)
        
        # 创建发票明细
        item_no = 1
        for d_item in delivery_items:
            order_item = OrderItem.query.filter_by(
                sales_order_id=order_id,
                item_no=d_item.sales_order_item_no
            ).first()
            
            if order_item:
                inv_item = InvoiceItem(
                    invoice_id=invoice_id,
                    item_no=item_no,
                    delivery_item_id=f"{delivery_id}-{d_item.item_no}",
                    sales_order_item_id=f"{order_id}-{d_item.sales_order_item_no}",
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
        return jsonify({'success': True, 'invoice_id': invoice_id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# 3. 修改发票相关路由
@bp.route('/edit-invoice')
def edit_invoice():
    """修改发票 - 搜索页面，对应edit-invoice.html"""
    return render_template('finance/edit-invoice.html')

@bp.route('/api/check-invoice/<invoice_id>')
def api_check_invoice(invoice_id):
    """检查发票是否存在并返回跳转信息"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if invoice:
        return jsonify({
            'success': True,
            'message': '发票信息查询成功',
            'redirect_url': url_for('finance.invoice_revision', invoice_id=invoice_id)
        })
    else:
        return jsonify({
            'success': False,
            'message': '未找到该发票信息'
        })

@bp.route('/invoice-revision/<invoice_id>')
def invoice_revision(invoice_id):
    """发票修改页面，对应invoice revision.html"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        flash('未找到该发票', 'error')
        return redirect(url_for('finance.edit_invoice'))
    
    # 获取发票明细
    invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    return render_template('finance/invoice revision.html', 
                         invoice=invoice, 
                         invoice_items=invoice_items)

@bp.route('/update-invoice/<invoice_id>', methods=['POST'])
def update_invoice(invoice_id):
    """更新发票信息"""
    try:
        invoice = CustomerInvoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'success': False, 'message': '未找到该发票'})
        
        # 获取JSON数据
        data = request.get_json()
        
        # 更新发票信息
        if 'invoice_date' in data:
            invoice.invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d')
        if 'payment_deadline' in data:
            invoice.payment_deadline = datetime.strptime(data['payment_deadline'], '%Y-%m-%d').date()
        if 'total_amount' in data:
            invoice.total_amount = float(data['total_amount'])
        if 'tax_amount' in data:
            invoice.tax_amount = float(data['tax_amount'])
        if 'payment_status' in data:
            invoice.payment_status = data['payment_status']
        if 'remarks' in data:
            invoice.remarks = data['remarks']
        
        db.session.commit()
        return jsonify({'success': True, 'message': '发票更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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
def create_payment():
    """创建收款记录 - 搜索页面，对应create-payment.html"""
    return render_template('finance/create-payment.html')

@bp.route('/api/check-invoice-for-payment/<invoice_id>')
def api_check_invoice_for_payment(invoice_id):
    """检查发票是否存在并返回收款页面跳转信息"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if invoice:
        return jsonify({
            'success': True,
            'message': '发票信息查询成功',
            'redirect_url': url_for('finance.payment_content', invoice_id=invoice_id)
        })
    else:
        return jsonify({
            'success': False,
            'message': '未找到该发票信息'
        })

@bp.route('/payment-content/<invoice_id>')
def payment_content(invoice_id):
    """收款记录创建页面，对应payment content.html"""
    invoice = CustomerInvoice.query.get(invoice_id)
    if not invoice:
        flash('未找到该发票', 'error')
        return redirect(url_for('finance.create_payment'))
    
    # 计算已收款金额
    paid_amount = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or 0
    remaining_amount = float(invoice.total_amount) - float(paid_amount)
    
    return render_template('finance/payment content.html', 
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
        data = request.get_json()
        invoice_id = data.get('invoice_id')
        
        # 获取发票信息
        invoice = CustomerInvoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'success': False, 'message': '未找到发票信息'})
        
        # 创建收款记录
        payment = CustomerPayment(
            payment_id=payment_id,
            customer_id=invoice.customer_id,
            invoice_id=invoice_id,
            payment_date=datetime.strptime(data['payment_date'], '%Y-%m-%d'),
            payment_amount=float(data['payment_amount']),
            payment_method=data['payment_method'],
            write_off_amount=float(data.get('write_off_amount', 0)),
            status='已确认',
            remarks=data.get('remarks', '')
        )
        db.session.add(payment)
        
        # 更新发票付款状态
        total_paid = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or 0
        total_paid += payment.payment_amount
        
        if total_paid >= float(invoice.total_amount):
            invoice.payment_status = '已付款'
        else:
            invoice.payment_status = '部分付款'
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'收款记录创建成功',
            'payment_id': payment_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# 6. 修改收款记录相关路由
@bp.route('/edit-payment')
def edit_payment():
    """修改收款记录 - 搜索页面，对应edit-payment.html"""
    return render_template('finance/edit-payment.html')

@bp.route('/api/check-payment/<payment_id>')
def api_check_payment(payment_id):
    """检查收款记录是否存在并返回跳转信息"""
    payment = CustomerPayment.query.get(payment_id)
    if payment:
        return jsonify({
            'success': True,
            'message': '收款记录查询成功',
            'redirect_url': url_for('finance.payment_revision', payment_id=payment_id)
        })
    else:
        return jsonify({
            'success': False,
            'message': '未找到该收款记录'
        })

@bp.route('/payment-revision/<payment_id>')
def payment_revision(payment_id):
    """收款记录修改页面，对应payment revision.html"""
    payment = CustomerPayment.query.get(payment_id)
    if not payment:
        flash('未找到该收款记录', 'error')
        return redirect(url_for('finance.edit_payment'))
    
    # 获取对应的发票信息
    invoice = CustomerInvoice.query.get(payment.invoice_id)
    
    return render_template('finance/payment revision.html', 
                         payment=payment, 
                         invoice=invoice)

@bp.route('/update-payment/<payment_id>', methods=['POST'])
def update_payment(payment_id):
    """更新收款记录"""
    try:
        payment = CustomerPayment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'message': '未找到该收款记录'})
        
        # 获取JSON数据
        data = request.get_json()
        
        # 更新收款记录
        if 'payment_date' in data:
            payment.payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
        if 'payment_amount' in data:
            payment.payment_amount = float(data['payment_amount'])
        if 'payment_method' in data:
            payment.payment_method = data['payment_method']
        if 'write_off_amount' in data:
            payment.write_off_amount = float(data['write_off_amount'])
        if 'status' in data:
            payment.status = data['status']
        if 'remarks' in data:
            payment.remarks = data['remarks']
        
        db.session.commit()
        return jsonify({'success': True, 'message': '收款记录更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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