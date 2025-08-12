from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment
from finance.forms import InvoiceForm, PaymentForm, InvoiceSearchForm, PaymentSearchForm
from order.models import SalesOrder, OrderItem
from delivery.models import DeliveryNote, DeliveryItem
from order.models import Inquiry,Quotation
from datetime import datetime, date,timedelta
from database import db
import uuid
from decimal import Decimal
from sqlalchemy import or_

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
        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # 兼容 multipart/form-data 和 JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            order_id = (request.form.get('order_id') or request.args.get('order_id') or '').strip()
            delivery_id = (request.form.get('delivery_id') or request.args.get('delivery_id') or '').strip()
            invoice_date_str = request.form.get('invoice_date')
            payment_deadline_str = request.form.get('payment_deadline')
            remarks = request.form.get('remarks', '')
        else:
            data = request.get_json(silent=True) or {}
            order_id = (data.get('order_id') or request.args.get('order_id') or '').strip()
            delivery_id = (data.get('delivery_id') or request.args.get('delivery_id') or '').strip()
            invoice_date_str = data.get('invoice_date')
            payment_deadline_str = data.get('payment_deadline')
            remarks = data.get('remarks', '')

        if not order_id or not delivery_id:
            flash('缺少必要的订单或发货单信息', 'error')
            return redirect(url_for('finance.create_invoice'))

        # 解析日期，兼容空值
        invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d") if invoice_date_str else datetime.now()
        payment_deadline = datetime.strptime(payment_deadline_str, "%Y-%m-%d") if payment_deadline_str else (datetime.now() + timedelta(days=30))

        sales_order = SalesOrder.query.get(order_id)
        if not sales_order:
            flash('未找到订单信息', 'error')
            return redirect(url_for('finance.create_invoice'))

        delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery_id).all()
        total_amount = 0

        for d_item in delivery_items:
            order_item = OrderItem.query.filter_by(
                sales_order_id=order_id,
                item_no=d_item.sales_order_item_no
            ).first()
            if order_item:
                unit_price = float(order_item.sales_unit_price or 0)
                quantity = float(d_item.actual_delivery_quantity or 0)
                item_amount = unit_price * quantity
                total_amount += item_amount * 1.13

        tax_amount = total_amount * 0.13 / 1.13

        invoice = CustomerInvoice(
            invoice_id=invoice_id,
            customer_id=sales_order.customer_id,
            sales_order_id=order_id,
            delivery_note_ids=delivery_id,
            invoice_date=invoice_date,
            payment_deadline=payment_deadline.date(),
            total_amount=total_amount,
            tax_amount=tax_amount,
            payment_status='未付款',
            remarks=remarks
        )
        db.session.add(invoice)

        item_no = 1
        for d_item in delivery_items:
            order_item = OrderItem.query.filter_by(
                sales_order_id=order_id,
                item_no=d_item.sales_order_item_no
            ).first()
            if order_item:
                unit_price = float(order_item.sales_unit_price or 0)
                quantity = float(d_item.actual_delivery_quantity or 0)
                inv_item = InvoiceItem(
                    invoice_id=invoice_id,
                    item_no=item_no,
                    delivery_item_id=f"{delivery_id}-{d_item.item_no}",
                    sales_order_item_id=f"{order_id}-{d_item.sales_order_item_no}",
                    material_id=d_item.material_id,
                    invoiced_quantity=quantity,
                    unit_price=unit_price,
                    tax_amount=unit_price * quantity * 0.13,
                    item_amount=unit_price * quantity * 1.13,
                    unit=order_item.unit
                )
                db.session.add(inv_item)
                item_no += 1

        db.session.commit()
        flash(f'发票创建成功，发票编号：{invoice_id}', 'success')
        # 成功后返回 HTML+JS 弹窗
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>提示</title>
            <script>
                window.onload = function() {{
                    alert("信息保存成功！\\n(关联的发票编号: {invoice_id})");
                    window.location.href = "{url_for('finance.finance_home')}";
                }};
            </script>
        </head>
        <body></body>
        </html>
        """

    except Exception as e:
        db.session.rollback()
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>错误</title>
            <script>
                window.onload = function() {{
                    alert("保存失败：{str(e)}");
                    window.history.back();
                }};
            </script>
        </head>
        <body></body>
        </html>
        """

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
# 4. 查询发票 - 增强版本
@bp.route('/search-invoice', methods=['GET', 'POST'])
def search_invoice():
    """查询发票 - 增强版本，支持表单验证和更好的错误处理"""
    from finance.forms import InvoiceSearchForm
    
    form = InvoiceSearchForm()
    results = []
    
    if request.method == 'POST':
        # 支持两种提交方式：表单提交和直接POST数据
        if form.validate_on_submit():
            # 使用表单数据
            search_params = {
                'invoice_id': form.invoice_id.data,
                'sales_order_id': form.sales_order_id.data,
                'customer_id': form.customer_id.data,
                'start_date': form.start_date.data,
                'end_date': form.end_date.data
            }
        else:
            # 使用原始POST数据（兼容现有HTML表单）
            search_params = {
                'invoice_id': request.form.get('invoice_id', '').strip(),
                'sales_order_id': request.form.get('sales_order_id', '').strip(),
                'customer_id': request.form.get('customer_id', '').strip(),
                'start_date': request.form.get('start_date', '').strip(),
                'end_date': request.form.get('end_date', '').strip()
            }
        
        try:
            # 构建查询
            query = CustomerInvoice.query
            
            if search_params['invoice_id']:
                query = query.filter(CustomerInvoice.invoice_id.like(f'%{search_params["invoice_id"]}%'))
            
            if search_params['sales_order_id']:
                query = query.filter(CustomerInvoice.sales_order_id.like(f'%{search_params["sales_order_id"]}%'))
            
            if search_params['customer_id']:
                query = query.filter(CustomerInvoice.customer_id.like(f'%{search_params["customer_id"]}%'))
            
            if search_params['start_date']:
                try:
                    if isinstance(search_params['start_date'], str):
                        start_date_obj = datetime.strptime(search_params['start_date'], '%Y-%m-%d')
                    else:
                        start_date_obj = datetime.combine(search_params['start_date'], datetime.min.time())
                    query = query.filter(CustomerInvoice.invoice_date >= start_date_obj)
                except (ValueError, TypeError):
                    flash('开始日期格式错误', 'error')
                    return render_template('finance/search-invoice.html', 
                                         form=form, results=results, 
                                         search_params=search_params)
            
            if search_params['end_date']:
                try:
                    if isinstance(search_params['end_date'], str):
                        end_date_obj = datetime.strptime(search_params['end_date'], '%Y-%m-%d')
                    else:
                        end_date_obj = datetime.combine(search_params['end_date'], datetime.min.time())
                    # 设置为当天结束时间
                    end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
                    query = query.filter(CustomerInvoice.invoice_date <= end_date_obj)
                except (ValueError, TypeError):
                    flash('结束日期格式错误', 'error')
                    return render_template('finance/search-invoice.html', 
                                         form=form, results=results,
                                         search_params=search_params)
            
            # 执行查询，按发票日期降序排列
            results = query.order_by(CustomerInvoice.invoice_date.desc()).limit(1000).all()
            
            # 记录查询日志
            print(f"Invoice search - Params: {search_params}, Results: {len(results)}")
            
            if len(results) == 1000:
                flash('查询结果过多，仅显示前1000条记录，请缩小查询范围', 'warning')
            elif len(results) == 0:
                flash('未找到符合条件的发票记录', 'info')
            else:
                flash(f'共找到 {len(results)} 条发票记录', 'success')
            
            # AJAX请求，返回JSON数据
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({
                    'success': True,
                    'results': [{
                        'invoice_id': invoice.invoice_id,
                        'customer_id': invoice.customer_id,
                        'sales_order_id': invoice.sales_order_id,
                        'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
                        'payment_deadline': invoice.payment_deadline.strftime('%Y-%m-%d'),
                        'total_amount': float(invoice.total_amount),
                        'tax_amount': float(invoice.tax_amount),
                        'payment_status': invoice.payment_status,
                        'remarks': invoice.remarks or ''
                    } for invoice in results],
                    'count': len(results)
                })
            
            # 更新表单数据用于回显
            if not form.validate_on_submit():
                # 手动设置表单数据
                form.invoice_id.data = search_params['invoice_id']
                form.sales_order_id.data = search_params['sales_order_id'] 
                form.customer_id.data = search_params['customer_id']
                if search_params['start_date']:
                    if isinstance(search_params['start_date'], str):
                        form.start_date.data = datetime.strptime(search_params['start_date'], '%Y-%m-%d').date()
                    else:
                        form.start_date.data = search_params['start_date']
                if search_params['end_date']:
                    if isinstance(search_params['end_date'], str):
                        form.end_date.data = datetime.strptime(search_params['end_date'], '%Y-%m-%d').date()
                    else:
                        form.end_date.data = search_params['end_date']
                        
        except Exception as e:
            print(f"Invoice search error: {str(e)}")
            flash(f'查询时发生错误：{str(e)}', 'error')
            db.session.rollback()
    
    return render_template('finance/search-invoice.html', 
                         form=form, results=results, 
                         search_params=form.data if form.data else {})

@bp.route('/api/invoice-detail/<invoice_id>')
def api_invoice_detail(invoice_id):
    """获取发票详细信息API - 增强版本"""
    try:
        invoice = CustomerInvoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'success': False, 'message': '未找到发票信息'})
        
        # 获取发票明细
        invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).order_by(InvoiceItem.item_no).all()
        
        # 获取收款记录
        payments = CustomerPayment.query.filter_by(invoice_id=invoice_id).order_by(CustomerPayment.payment_date.desc()).all()
        
        # 计算已收款金额
        total_paid = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or 0
        total_paid = float(total_paid)
        remaining_amount = float(invoice.total_amount) - total_paid
        
        return jsonify({
            'success': True,
            'invoice': {
                'invoice_id': invoice.invoice_id,
                'customer_id': invoice.customer_id,
                'sales_order_id': invoice.sales_order_id,
                'delivery_note_ids': invoice.delivery_note_ids,
                'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
                'payment_deadline': invoice.payment_deadline.strftime('%Y-%m-%d'),
                'total_amount': float(invoice.total_amount),
                'tax_amount': float(invoice.tax_amount),
                'payment_status': invoice.payment_status,
                'remarks': invoice.remarks or '',
                'total_paid': total_paid,
                'remaining_amount': remaining_amount
            },
            'items': [{
                'item_no': item.item_no,
                'material_id': item.material_id,
                'invoiced_quantity': float(item.invoiced_quantity),
                'unit_price': float(item.unit_price),
                'item_amount': float(item.item_amount or 0),
                'tax_amount': float(item.tax_amount or 0),
                'unit': item.unit or '',
                'delivery_item_id': item.delivery_item_id,
                'sales_order_item_id': item.sales_order_item_id
            } for item in invoice_items],
            'payments': [{
                'payment_id': payment.payment_id,
                'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
                'payment_amount': float(payment.payment_amount),
                'payment_method': payment.payment_method,
                'write_off_amount': float(payment.write_off_amount),
                'status': payment.status,
                'remarks': payment.remarks or ''
            } for payment in payments]
        })
        
    except Exception as e:
        print(f"API invoice detail error: {str(e)}")
        return jsonify({'success': False, 'message': f'服务器错误：{str(e)}'})

# 批量查询API，用于提高性能
@bp.route('/api/invoices-summary')
def api_invoices_summary():
    """获取发票汇总信息API"""
    try:
        # 获取各种状态的发票统计
        total_count = CustomerInvoice.query.count()
        paid_count = CustomerInvoice.query.filter_by(payment_status='已付款').count()
        partial_count = CustomerInvoice.query.filter_by(payment_status='部分付款').count()
        unpaid_count = CustomerInvoice.query.filter_by(payment_status='未付款').count()
        
        # 获取金额汇总
        total_amount = db.session.query(db.func.sum(CustomerInvoice.total_amount)).scalar() or 0
        paid_amount = db.session.query(db.func.sum(CustomerPayment.payment_amount)).scalar() or 0
        
        return jsonify({
            'success': True,
            'summary': {
                'total_count': total_count,
                'paid_count': paid_count,
                'partial_count': partial_count,
                'unpaid_count': unpaid_count,
                'total_amount': float(total_amount),
                'paid_amount': float(paid_amount),
                'unpaid_amount': float(total_amount) - float(paid_amount)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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

@bp.route('/payment content/<invoice_id>')
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
        
        total_paid = db.session.query(db.func.sum(CustomerPayment.payment_amount)).filter_by(invoice_id=invoice_id).scalar() or Decimal('0')

        # 把 payment.payment_amount 转为 Decimal
        payment_amount_decimal = Decimal(str(payment.payment_amount))

        total_paid += payment_amount_decimal

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

@bp.route('/payment revision/<payment_id>')
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
# routes.py (或你的 blueprint 文件)
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import or_
# 假设下面这些模型已在你的项目中定义并导入
# from .models import CustomerInvoice, InvoiceItem, CustomerPayment, SalesOrder, DeliveryNote, DeliveryItem, Inquiry, Quotation

from jinja2.runtime import Undefined




def _safe_amount(obj, *attrs):
    """从对象尝试取第一个存在的数值字段（total_amount/amount等），并返回 float"""
    for a in attrs:
        if hasattr(obj, a):
            val = getattr(obj, a)
            try:
                return float(val or 0)
            except Exception:
                return 0.0
    return 0.0

def _safe_date_str(obj, attr):
    d = getattr(obj, attr, None)
    try:
        return d.strftime('%Y-%m-%d') if d else ''
    except Exception:
        return str(d) if d else ''

@bp.route('/document-flow', methods=['GET', 'POST'])
def document_flow():
    """
    渲染查询页面（支持 GET）。
    注：页面内的查询主要通过 /api/document-flow 异步获取数据；保留 POST 的传统渲染（可选）。
    """
    flow_info = {}
    # 保留原始 POST 渲染逻辑以兼容旧表单提交（如果你愿意）
    if request.method == 'POST' and not request.is_json:
        invoice_id = request.form.get('invoice_id', '').strip()
        sales_order_id = request.form.get('sales_order_id', '').strip()
        if invoice_id:
            invoice = CustomerInvoice.query.filter_by(invoice_id=invoice_id).first()
            if invoice:
                invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
                payments = CustomerPayment.query.filter_by(invoice_id=invoice_id).all()
                sales_order = SalesOrder.query.filter_by(sales_order_id=invoice.sales_order_id).first() if getattr(invoice, 'sales_order_id', None) else None
                delivery_notes = []
                if getattr(invoice, 'delivery_note_ids', None):
                    delivery_ids = [d.strip() for d in invoice.delivery_note_ids.split(',') if d.strip()]
                    delivery_notes = DeliveryNote.query.filter(DeliveryNote.delivery_note_id.in_(delivery_ids)).all()
                flow_info = {
                    'invoice': invoice,
                    'invoice_items': invoice_items,
                    'payments': payments,
                    'sales_order': sales_order,
                    'delivery_notes': delivery_notes
                }
        elif sales_order_id:
            sales_order = SalesOrder.query.filter_by(sales_order_id=sales_order_id).first()
            if sales_order:
                invoices = CustomerInvoice.query.filter_by(sales_order_id=sales_order_id).all()
                delivery_notes = DeliveryNote.query.filter_by(sales_order_id=sales_order_id).all()
                flow_info = {
                    'sales_order': sales_order,
                    'invoices': invoices,
                    'delivery_notes': delivery_notes
                }
    return render_template('finance/document-flow.html', flow_info=flow_info)


@bp.route('/api/document-flow', methods=['POST'])
def api_document_flow():
    """
    JSON API：接收 { customer_id, document_id }，返回所有匹配的单据（发票/订单/发货/询价/报价）
    返回: { success: True, count: N, documents: [...] }
    每个 document: { id, customer, type, amount, date, status }
    """
    data = request.get_json(silent=True) or {}
    customer_id = (data.get('customer_id') or '').strip()
    document_id = (data.get('document_id') or '').strip()

    results = []

    # 1. 发票
    invoices_query = CustomerInvoice.query
    if customer_id:
        invoices_query = invoices_query.filter_by(customer_id=customer_id)
    if document_id:
        invoices_query = invoices_query.filter(CustomerInvoice.invoice_id.like(f"%{document_id}%"))
    invoices = invoices_query.all()
    for inv in invoices:
        results.append({
            "id": getattr(inv, 'invoice_id', None) or getattr(inv, 'id', None),
            "customer": getattr(inv, 'customer_id', ''),
            "type": "销售发票",
            "amount": _safe_amount(inv, 'total_amount', 'amount'),
            "date": _safe_date_str(inv, 'invoice_date'),
            "status": getattr(inv, 'payment_status', '') or getattr(inv, 'status', '')
        })

    # 2. 订单
    orders_query = SalesOrder.query
    if customer_id:
        orders_query = orders_query.filter_by(customer_id=customer_id)
    if document_id:
        orders_query = orders_query.filter(SalesOrder.sales_order_id.like(f"%{document_id}%"))
    orders = orders_query.all()
    for order in orders:
        results.append({
            "id": getattr(order, 'sales_order_id', None) or getattr(order, 'id', None),
            "customer": getattr(order, 'customer_id', ''),
            "type": "销售订单",
            "amount": _safe_amount(order, 'total_amount', 'amount'),
            "date": _safe_date_str(order, 'order_date'),
            "status": getattr(order, 'status', '')
        })

    # 3. 发货单
    deliveries_query = DeliveryNote.query
    if customer_id:
        deliveries_query = deliveries_query.filter_by(customer_id=customer_id)
    if document_id:
        deliveries_query = deliveries_query.filter(DeliveryNote.delivery_note_id.like(f"%{document_id}%"))
    deliveries = deliveries_query.all()
    for dn in deliveries:
        results.append({
            "id": getattr(dn, 'delivery_note_id', None) or getattr(dn, 'id', None),
            "customer": getattr(dn, 'customer_id', ''),
            "type": "发货单",
            "amount": _safe_amount(dn, 'total_amount', 'amount'),
            "date": _safe_date_str(dn, 'delivery_date'),
            "status": getattr(dn, 'status', '')
        })

    # 4. 询价单
    try:
        inquiries_query = Inquiry.query
        if customer_id:
            inquiries_query = inquiries_query.filter_by(customer_id=customer_id)
        if document_id:
            inquiries_query = inquiries_query.filter(Inquiry.inquiry_id.like(f"%{document_id}%"))
        inquiries = inquiries_query.all()
        for iq in inquiries:
            results.append({
                "id": getattr(iq, 'inquiry_id', None) or getattr(iq, 'id', None),
                "customer": getattr(iq, 'customer_id', ''),
                "type": "询价单",
                "amount": _safe_amount(iq, 'total_amount', 'amount'),
                "date": _safe_date_str(iq, 'inquiry_date'),
                "status": getattr(iq, 'status', '')
            })
    except Exception:
        # 如果没有 Inquiry 模型或查询失败，忽略
        pass

    # 5. 报价单
    try:
        quotations_query = Quotation.query
        if customer_id:
            quotations_query = quotations_query.filter_by(customer_id=customer_id)
        if document_id:
            quotations_query = quotations_query.filter(Quotation.quotation_id.like(f"%{document_id}%"))
        quotations = quotations_query.all()
        for qt in quotations:
            results.append({
                "id": getattr(qt, 'quotation_id', None) or getattr(qt, 'id', None),
                "customer": getattr(qt, 'customer_id', ''),
                "type": "报价单",
                "amount": _safe_amount(qt, 'total_amount', 'amount'),
                "date": _safe_date_str(qt, 'quotation_date'),
                "status": getattr(qt, 'status', '')
            })
    except Exception:
        pass

    # 可选：按日期降序排序（如果 date 是 'YYYY-MM-DD' 格式字符串）
    try:
        results.sort(key=lambda r: r.get('date') or '', reverse=True)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "count": len(results),
        "documents": results
    })


@bp.route('/flowinfo/<doc_id>')
def flowinfo(doc_id):
    """
    通用单据详情页面：尝试按发票 -> 订单 -> 发货单 -> 询价 -> 报价 顺序查找并渲染对应详情页。
    如果找不到，则返回到 document_flow 页面并提示未找到。
    """
    # 1) 试作发票
    invoice = CustomerInvoice.query.filter_by(invoice_id=doc_id).first()
    if invoice:
        invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice.invoice_id).all()
        payments = CustomerPayment.query.filter_by(invoice_id=invoice.invoice_id).all()
        sales_order = CustomerInvoice.query.filter_by(sales_order_id=invoice.sales_order_id).first() if getattr(invoice, 'sales_order_id', None) else None

        delivery_info = []
        if getattr(invoice, 'delivery_note_ids', None):
            delivery_ids = [d.strip() for d in invoice.delivery_note_ids.split(',') if d.strip()]
            for delivery_id in delivery_ids:
                delivery_note = DeliveryNote.query.filter_by(delivery_note_id=delivery_id).first()
                if delivery_note:
                    delivery_items = DeliveryNote.query.filter_by(delivery_note_id=delivery_id).all()
                    delivery_info.append({'note': delivery_note, 'items': delivery_items})

        return render_template('finance/flowinfo.html',
                               invoice=invoice,
                               invoice_items=invoice_items,
                               payments=payments,
                               sales_order=sales_order,
                               delivery_info=delivery_info)

    # 2) 销售订单
    sales_order = SalesOrder.query.filter_by(sales_order_id=doc_id).first()
    if sales_order:
        invoices = CustomerInvoice.query.filter_by(sales_order_id=sales_order.sales_order_id).all()
        delivery_notes = DeliveryNote.query.filter_by(sales_order_id=sales_order.sales_order_id).all()
        # 这里可以渲染专门的订单详情模板，若没有则渲染通用模板
        return render_template('finance/flowinfo.html',
                               sales_order=sales_order,
                               invoices=invoices,
                               delivery_notes=delivery_notes)

    # 3) 发货单
    delivery = DeliveryNote.query.filter_by(delivery_note_id=doc_id).first()
    if delivery:
        delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery.delivery_note_id).all()
        # 可以在此查找关联发票/订单
        related_invoices = CustomerInvoice.query.filter(CustomerInvoice.delivery_note_ids.like(f"%{delivery.delivery_note_id}%")).all()
        return render_template('finance/flowinfo.html',
                               delivery=delivery,
                               items=delivery_items,
                               related_invoices=related_invoices)

    # 4) 询价单
    try:
        inquiry = Inquiry.query.filter_by(inquiry_id=doc_id).first()
        if inquiry:
            # 若你有询价明细模型，可查询并渲染
            return render_template('finance/flowinfo.html', inquiry=inquiry)
    except Exception:
        pass

    # 5) 报价单
    try:
        quotation = Quotation.query.filter_by(quotation_id=doc_id).first()
        if quotation:
            return render_template('finance/flowinfo.html', quotation=quotation)
    except Exception:
        pass

    # 若以上都未找到
    flash('未找到该单据或单据类型不受支持', 'error')
    return redirect(url_for('finance.document_flow'))



