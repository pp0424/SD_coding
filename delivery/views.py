# delivery/views.py
from flask import Blueprint, jsonify, render_template, redirect, session, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from decimal import Decimal
from customer.models import Customer
from . import forms
from .models import DeliveryNote, DeliveryItem, StockChangeLog
from order.models import SalesOrder,SalesOrder, OrderItem, Material
from datetime import date, datetime, time
from math import ceil
from database import db
import uuid


delivery_bp = Blueprint('delivery', __name__, template_folder='templates')

def to_decimal(val):
    """统一的数值转换函数"""
    if val is None:
        return Decimal('0')
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except:
        return Decimal('0')

def gen_delivery_note_id() -> str:
    """生成唯一的发货单编号"""
    today_str = datetime.today().strftime('%Y%m%d')
    base_prefix = f'DN{today_str}-'

    # 查找当天最后一个发货单号
    last_dn = DeliveryNote.query.filter(
        DeliveryNote.delivery_note_id.like(f"{base_prefix}%")
    ).order_by(DeliveryNote.delivery_note_id.desc()).first()

    # 生成下一个序号
    if last_dn and len(last_dn.delivery_note_id) >= len(base_prefix) + 3:
        try:
            next_num = int(last_dn.delivery_note_id[-3:]) + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1
    
    return f"{base_prefix}{next_num:03d}"

PER_PAGE = 20

@delivery_bp.route('/')
@login_required
def delivery_home():
    today = datetime.utcnow().date()
    recent_deliveries = DeliveryNote.query.order_by(DeliveryNote.delivery_date.desc()).limit(5).all()
    pending_postings = DeliveryNote.query.filter_by(status='已创建').count()
    recent_changes = StockChangeLog.query.order_by(StockChangeLog.change_time.desc()).limit(5).all()
    
    return render_template('delivery/home.html',
                           today=today,
                           recent_deliveries=recent_deliveries,
                           pending_postings=pending_postings,
                           recent_changes=recent_changes)

# ========== 工具函数 ==========


def lock_sales_order_and_items(sales_order_id: str) -> tuple[SalesOrder, list[OrderItem]]:
    """加锁抬头和行，防并发重复分配"""
    so = (db.session.query(SalesOrder)
          .filter(SalesOrder.sales_order_id == sales_order_id)
          .with_for_update(nowait=False)
          .first())
    if not so:
        return None, []
    items = (db.session.query(OrderItem)
             .filter(OrderItem.sales_order_id == sales_order_id)
             .with_for_update(nowait=False)
             .all())
    return so, items


def validate_sales_order_header(so: SalesOrder) -> str | None:
    """验证销售订单状态是否允许创建发货"""
    if not so:
        return '销售订单不存在'
    
    # 定义允许创建发货的状态
    allowed_statuses = ['已创建', '已审核', '部分发货']
    
    if so.status in ['已取消']:
        return f'销售订单状态【{so.status}】已取消，不允许创建发货'
    elif so.status in ['已完成']:
        return f'销售订单状态【{so.status}】已完成，不允许创建发货'
    elif so.status not in allowed_statuses:
        return f'销售订单状态【{so.status}】不允许创建发货，请联系管理员'
    
    return None

def validate_delivery_status_transition(current_status: str, target_status: str) -> str | None:
    """验证发货单状态转换是否合法"""
    # 修正状态转换规则：必须经过拣货才能过账
    valid_transitions = {
        '已创建': ['已拣货', '已取消'],
        '已拣货': ['已过账', '已取消'],
        '已过账': [],  # 已过账状态不能转换到其他状态
        '已取消': []   # 已取消状态不能转换到其他状态
    }
    
    if current_status not in valid_transitions:
        return f'未知的当前状态：{current_status}'
    
    if target_status not in valid_transitions.get(current_status, []):
        return f'不允许从状态【{current_status}】转换到【{target_status}】'
    
    return None


def sum_open_delivery_allocations(sales_order_id: str, sales_order_item_no: int) -> Decimal:
    """
    计算某订单行在“未过账”的发货计划量（属于‘已创建’或‘已拣货’状态的交货单）
    用于动态扣减未发货量，防止重复创建。
    """
    q = (db.session.query(func.coalesce(func.sum(DeliveryItem.planned_delivery_quantity), 0))
         .join(DeliveryNote, DeliveryNote.delivery_note_id == DeliveryItem.delivery_note_id)
         .filter(DeliveryNote.sales_order_id == sales_order_id)
         .filter(DeliveryItem.sales_order_item_no == sales_order_item_no)
         .filter(DeliveryNote.status.in_(['已创建', '已拣货'])))
    return Decimal(q.scalar() or 0)


def compute_unshipped_dynamic(oi: OrderItem) -> Decimal:
    """
    未发货量 = 订单量 - 已发货 - 未过账交货计划量
    这样当多次创建交货时能正确收敛剩余额度。
    """
    order_q = Decimal(oi.order_quantity or 0)
    shipped = Decimal(oi.shipped_quantity or 0)
    allocated_open = sum_open_delivery_allocations(oi.sales_order_id, oi.item_no)
    return order_q - shipped - allocated_open


def collect_and_validate_items(form: forms.CreateDeliveryForm, order_items: list[OrderItem]) -> tuple[list[dict], list[str]]:
    """按照 HiddenField 的 sales_order_item_no 精确匹配行，并校验计划量 <= 剩余额度"""
    errors, valid_items = [], []
    items_by_no = {int(i.item_no): i for i in order_items}

    for f in form.items.entries:
        # sales_order_item_no 是 HiddenField，通常为 str，需要转 int
        try:
            item_no = int(f.sales_order_item_no.data)
        except (TypeError, ValueError):
            errors.append('存在无法识别的订单行号')
            continue

        planned = Decimal(f.planned_delivery_quantity.data or 0)
        if planned <= 0:
            continue

        oi = items_by_no.get(item_no)
        if not oi:
            errors.append(f'无法找到订单行 {item_no}')
            continue

        remain = compute_unshipped_dynamic(oi)
        if remain <= 0:
            errors.append(f'订单行 {item_no} 已无可发数量')
            continue
        if planned > remain:
            errors.append(f'订单行 {item_no} 计划发货 {planned} 超过剩余可发 {remain}')
            continue

        valid_items.append({
            'order_item': oi,
            'item_no': item_no,
            'material_id': oi.material_id,
            'unit': oi.unit or '件',
            'planned_qty': planned
        })

    if not valid_items and not errors:
        errors.append('请至少填写一项有效的发货数量')
    return valid_items, errors


def atp_check_by_material(valid_items: list[dict]):
    """
    简化 ATP：按物料聚合需求，基于 Material.available_stock 校验（全局，不分仓）。
    只做校验与行锁，不做占用扣减（避免与过账扣减重复）。
    """
    # 汇总需求
    demand = {}
    for it in valid_items:
        demand[it['material_id']] = demand.get(it['material_id'], Decimal(0)) + it['planned_qty']

    mat_ids = list(demand.keys())
    if not mat_ids:
        return

    mats = (db.session.query(Material)
            .filter(Material.material_id.in_(mat_ids))
            .with_for_update(nowait=False)  # 行锁，降低并发误分配概率
            .all())
    mats_by_id = {m.material_id: m for m in mats}

    lack = []
    for mid, need in demand.items():
        m = mats_by_id.get(mid)
        available = Decimal(m.available_stock or 0) if m else Decimal(0)
        if available < need:
            lack.append(f'物料 {mid} 可用库存不足，需要 {need}，当前 {available}')
    if lack:
        raise ValueError('；'.join(lack))


# ========== 视图：创建发货 ==========

@delivery_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_delivery():
    form = forms.CreateDeliveryForm()
    order_items_for_view = []

    # GET 支持 querystring 预填订单号
    if request.method == 'GET' and not form.sales_order_id.data:
        qs = request.args.get('sales_order_id')
        if qs:
            form.sales_order_id.data = qs

    if request.method == 'POST':
        try:
            so_id = (form.sales_order_id.data or '').strip()
            wh_code = (form.warehouse_code.data or '').strip()
            exp_date = form.expected_delivery_date.data

            if not so_id:
                flash('请填写销售订单编号', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            if not exp_date or exp_date < date.today():
                flash('预计发货日期不能早于今天', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            if not wh_code:
                flash('请填写发货仓库代码', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 加锁读取订单与行
            sales_order, so_items = lock_sales_order_and_items(so_id)
            header_err = validate_sales_order_header(sales_order)
            if header_err:
                flash(header_err, 'danger')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 行校验与收集
            valid_items, errs = collect_and_validate_items(form, so_items)
            if errs:
                for e in errs:
                    flash(e, 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # ATP 校验（基于 Material.available_stock）
            atp_check_by_material(valid_items)

            # 创建发货抬头（状态使用‘已创建’，与你的查询下拉一致）
            dn_id = gen_delivery_note_id()
            delivery_dt = datetime.combine(exp_date, time(0, 0, 0))

            dn = DeliveryNote(
                delivery_note_id=dn_id,
                sales_order_id=so_id,
                delivery_date=delivery_dt,
                warehouse_code=wh_code,
                status='已创建',
                remarks=form.remarks.data,
                posted_by=session.get('username', '系统'),
                posted_at=datetime.utcnow()
            )
            db.session.add(dn)
            db.session.flush()

            # 创建发货行（实际发货数量创建时为 0，等待过账）
            for idx, it in enumerate(valid_items, start=1):
                di = DeliveryItem(
                    delivery_note_id=dn_id,
                    item_no=idx,
                    sales_order_item_no=it['item_no'],
                    material_id=it['material_id'],
                    planned_delivery_quantity=it['planned_qty'],
                    actual_delivery_quantity=Decimal('0'),
                    unit=it['unit']
                )
                db.session.add(di)

            # （可选）根据剩余可发量更新订单状态：仅在确有剩余且已有交货时标为“部分发货（处理中）”
            # 在 SAP 中，订单状态更多依赖进度与文档流；这里保持谨慎，不改或仅在需要时改。
            # remaining_total = sum([max(Decimal(0), compute_unshipped_dynamic(i)) for i in so_items])
            # if remaining_total < sum([Decimal(i.order_quantity or 0) - Decimal(i.shipped_quantity or 0) for i in so_items]):
            #     sales_order.status = '部分发货'

            db.session.commit()
            flash(f'发货单【{dn_id}】创建成功', 'success')
            return redirect(url_for('delivery.delivery_home'))

        except ValueError as ve:
            db.session.rollback()
            flash(str(ve), 'danger')
        except SQLAlchemyError:
            db.session.rollback()
            flash('数据库操作失败，请重试或联系管理员', 'danger')
        except Exception:
            db.session.rollback()
            flash('创建发货单时发生未知错误', 'danger')

    # GET：根据订单号预填行（动态未发货量，考虑未过账交货的已分配）
    if form.sales_order_id.data:
        so = SalesOrder.query.filter_by(sales_order_id=form.sales_order_id.data).first()
        if so and not form.items.entries:
            so_items = OrderItem.query.filter_by(sales_order_id=so.sales_order_id).all()
            for oi in so_items:
                remain = compute_unshipped_dynamic(oi)
                if remain <= 0:
                    continue
                # 物料描述取自 Material
                mat = Material.query.filter_by(material_id=oi.material_id).first()
                material_desc = mat.description if mat else ''
                form.items.append_entry({
                    'sales_order_item_no': oi.item_no,
                    'material_id': oi.material_id,
                    'material_desc': material_desc,
                    'order_quantity': oi.order_quantity,
                    'unshipped_quantity': remain,
                    'planned_delivery_quantity': remain
                })
            order_items_for_view = form.items.entries

    return render_template('delivery/create_delivery.html', form=form, order_items=order_items_for_view)

# 修改发货单（非过账）
@delivery_bp.route('/edit/<delivery_id>', methods=['GET', 'POST'])
@login_required
def edit_delivery(delivery_id):
    delivery_note = DeliveryNote.query.get_or_404(delivery_id)

    if delivery_note.status not in ['已创建', '已拣货']:
        flash('当前状态不允许修改', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    form = forms.EditDeliveryForm()

    if request.method == 'GET':
        form.expected_delivery_date.data = delivery_note.delivery_date.date()
        form.warehouse_code.data = delivery_note.warehouse_code
        form.remarks.data = delivery_note.remarks

    if form.validate_on_submit():
        delivery_note.delivery_date = datetime.combine(form.expected_delivery_date.data, time(hour=9))
        delivery_note.warehouse_code = form.warehouse_code.data
        delivery_note.remarks = form.remarks.data
        db.session.commit()
        flash('发货单已更新', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    return render_template('delivery/edit_delivery.html', form=form, delivery=delivery_note)

# 发货列表/查询
@delivery_bp.route('/list', methods=['GET', 'POST'])
@login_required
def delivery_list():
    form = forms.SearchDeliveryForm()
    deliveries = DeliveryNote.query.order_by(DeliveryNote.delivery_date.desc())

    if form.validate_on_submit() or request.method == 'GET':
        # 兼容 GET 参数
        form.delivery_id.data = form.delivery_id.data or request.args.get('delivery_id', '')
        form.sales_order_id.data = form.sales_order_id.data or request.args.get('sales_order_id', '')
        form.status.data = form.status.data or request.args.get('status', '')
        if request.args.get('start_date'):
            try:
                form.start_date.data = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            except: pass
        if request.args.get('end_date'):
            try:
                form.end_date.data = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            except: pass

        if form.delivery_id.data:
            deliveries = deliveries.filter(DeliveryNote.delivery_note_id.contains(form.delivery_id.data))
        if form.sales_order_id.data:
            deliveries = deliveries.filter(DeliveryNote.sales_order_id.contains(form.sales_order_id.data))
        if form.start_date.data:
            deliveries = deliveries.filter(DeliveryNote.delivery_date >= datetime.combine(form.start_date.data, time.min))
        if form.end_date.data:
            deliveries = deliveries.filter(DeliveryNote.delivery_date <= datetime.combine(form.end_date.data, time.max))
        if form.status.data:
            deliveries = deliveries.filter(DeliveryNote.status == form.status.data)

    deliveries = deliveries.all()
    return render_template('delivery/delivery_list.html', deliveries=deliveries, form=form)

# 详情
@delivery_bp.route('/detail/<delivery_id>')
@login_required
def delivery_detail(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    return render_template('delivery/delivery_detail.html', delivery=delivery)

# 库存变动（包含发货）
@delivery_bp.route('/stock_changes', methods=['GET'])
@login_required
def stock_changes():
    material_id = request.args.get('material_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    delivery_id = request.args.get('delivery_id', '')
    warehouse_code = request.args.get('warehouse_code', '')
    page = int(request.args.get('page', 1))

    query = StockChangeLog.query.order_by(StockChangeLog.change_time.desc())

    if material_id:
        query = query.filter(StockChangeLog.material_id.contains(material_id))
    if start_date:
        query = query.filter(StockChangeLog.change_time >= f'{start_date} 00:00:00')
    if end_date:
        query = query.filter(StockChangeLog.change_time <= f'{end_date} 23:59:59')
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.contains(delivery_id))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.contains(warehouse_code))

    total_records = query.count()
    total_pages = max(1, ceil(total_records / PER_PAGE))
    changes = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    return render_template('delivery/stock_changes.html',
                           changes=changes,
                           page=page,
                           total_pages=total_pages,
                           total_records=total_records)

# 仅查看过账导致的库存变动（发货）
@delivery_bp.route('/posted_stock_changes', methods=['GET'])
@login_required
def posted_stock_changes():
    material_id = request.args.get('material_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    delivery_id = request.args.get('delivery_id', '')
    warehouse_code = request.args.get('warehouse_code', '')
    page = int(request.args.get('page', 1))

    query = StockChangeLog.query.filter_by(change_type='发货').order_by(StockChangeLog.change_time.desc())

    if material_id:
        query = query.filter(StockChangeLog.material_id.contains(material_id))
    if start_date:
        query = query.filter(StockChangeLog.change_time >= f'{start_date} 00:00:00')
    if end_date:
        query = query.filter(StockChangeLog.change_time <= f'{end_date} 23:59:59')
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.contains(delivery_id))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.contains(warehouse_code))

    total_records = query.count()
    total_pages = max(1, ceil(total_records / PER_PAGE))
    changes = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    return render_template('delivery/posted_stock_changes.html',
                           changes=changes,
                           page=page,
                           total_pages=total_pages,
                           total_records=total_records)

def validate_stock_availability(delivery_items: list, warehouse_code: str) -> list[str]:
    """验证库存可用性，返回错误信息列表"""
    errors = []
    
    # 按物料汇总需求量
    material_demands = {}
    for item in delivery_items:
        material_id = item['material_id']
        actual_qty = item['actual_quantity']
        if actual_qty > 0:
            material_demands[material_id] = material_demands.get(material_id, Decimal('0')) + actual_qty
    
    if not material_demands:
        return errors
    
    # 批量查询物料库存（加锁防止并发问题）
    materials = (db.session.query(Material)
                .filter(Material.material_id.in_(list(material_demands.keys())))
                .with_for_update(nowait=False)
                .all())
    
    materials_dict = {m.material_id: m for m in materials}
    
    # 检查每个物料的库存
    for material_id, demand_qty in material_demands.items():
        material = materials_dict.get(material_id)
        if not material:
            errors.append(f'物料 {material_id} 不存在')
            continue
            
        available = to_decimal(material.available_stock)
        if available < demand_qty:
            errors.append(f'物料 {material_id} 库存不足：需要 {demand_qty}，可用 {available}')
    
    return errors

# 过账
@delivery_bp.route('/post/<delivery_id>', methods=['GET', 'POST'])
@login_required
def post_delivery(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    
    # 验证当前状态是否允许过账（必须是已拣货状态）
    if delivery.status != '已拣货':
        flash('只有【已拣货】状态的发货单才能进行过账操作', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    form = forms.PostDeliveryForm()

    if request.method == 'GET':
        form.actual_delivery_date.data = delivery.delivery_date.date()
        form.items.entries = []
        for item in delivery.items:
            sub = forms.DeliveryItemPostForm()
            sub.material_id.data = item.material_id
            sub.planned_quantity.data = item.planned_delivery_quantity
            # 默认等于计划
            sub.actual_quantity.data = item.planned_delivery_quantity
            form.items.append_entry(sub)

    if form.validate_on_submit():
        try:
            # 收集实际发货数据
            actual_items = []
            for idx, di in enumerate(delivery.items):
                sub = form.items[idx]
                actual = to_decimal(sub.form.actual_quantity.data)
                
                # 基本数量验证
                if actual < 0:
                    flash(f'物料 {di.material_id} 实际数量不能为负数', 'danger')
                    return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
                
                if actual > to_decimal(di.planned_delivery_quantity):
                    flash(f'物料 {di.material_id} 实际数量 {actual} 不能超过计划数量 {di.planned_delivery_quantity}', 'danger')
                    return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
                
                actual_items.append({
                    'delivery_item': di,
                    'material_id': di.material_id,
                    'actual_quantity': actual,
                    'planned_quantity': to_decimal(di.planned_delivery_quantity)
                })
            
            # 库存可用性验证
            stock_errors = validate_stock_availability(actual_items, delivery.warehouse_code)
            if stock_errors:
                for error in stock_errors:
                    flash(error, 'danger')
                return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
            
            # 开始事务处理
            current_time = datetime.utcnow()
            operator = getattr(current_user, 'username', 'system')
            
            # 更新发货单状态
            delivery.status = '已过账'
            delivery.posted_at = current_time
            delivery.posted_by = operator
            delivery.delivery_date = datetime.combine(form.actual_delivery_date.data, time(hour=9))
            if form.remarks.data:
                delivery.remarks = form.remarks.data
            
            # 处理每个发货行项目
            for item_data in actual_items:
                di = item_data['delivery_item']
                actual = item_data['actual_quantity']
                
                if actual <= 0:
                    continue  # 跳过零数量的行项目
                
                # 更新发货行实际数量
                di.actual_delivery_quantity = actual
                
                # 扣减库存（TODO: 待实现分仓库存管理）
                mat = Material.query.get(di.material_id)
                before_stock = to_decimal(mat.available_stock)
                mat.available_stock = before_stock - actual
                
                # 记录库存变动日志
                log = StockChangeLog(
                    material_id=di.material_id,
                    change_type='发货',
                    quantity_change=Decimal('0') - actual,
                    before_quantity=before_stock,
                    after_quantity=mat.available_stock,
                    reference_doc=delivery_id,
                    operator=operator,
                    warehouse_code=delivery.warehouse_code,
                    change_time=current_time
                )
                db.session.add(log)
                
                # 记录警告（当前库存管理未分仓）
                flash('警告：当前库存扣减使用全局库存，未实现分仓管理', 'warning')
                
                # 更新销售订单行
                oi = OrderItem.query.filter_by(
                    sales_order_id=delivery.sales_order_id, 
                    item_no=di.sales_order_item_no
                ).first()
                
                if oi:
                    oi.shipped_quantity = to_decimal(oi.shipped_quantity) + actual
                    oi.unshipped_quantity = to_decimal(oi.order_quantity) - to_decimal(oi.shipped_quantity)
                    # 确保未发货数量不为负数
                    if oi.unshipped_quantity < 0:
                        oi.unshipped_quantity = Decimal('0')
            
            # 更新销售订单状态
            so = SalesOrder.query.get(delivery.sales_order_id)
            if so:
                all_items = OrderItem.query.filter_by(sales_order_id=so.sales_order_id).all()
                if all_items:
                    # 检查是否所有行项目都已完全发货
                    all_shipped = all(to_decimal(x.unshipped_quantity) <= 0 for x in all_items)
                    if all_shipped:
                        so.status = '已完成'
                    else:
                        # 检查是否有任何行项目已部分发货
                        any_shipped = any(to_decimal(x.shipped_quantity) > 0 for x in all_items)
                        if any_shipped:
                            so.status = '部分发货'
            
            db.session.commit()
            flash(f'发货单【{delivery_id}】过账成功', 'success')
            return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('过账时发生数据库错误，请重试或联系管理员', 'danger')
            return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
        except Exception as e:
            db.session.rollback()
            flash('过账时发生未知错误，请重试或联系管理员', 'danger')
            return render_template('delivery/post_delivery.html', form=form, delivery=delivery)

    return render_template('delivery/post_delivery.html', form=form, delivery=delivery)

# 取消发货单
@delivery_bp.route('/cancel/<delivery_id>', methods=['GET', 'POST'])
@login_required
def cancel_delivery(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    
    # 验证状态转换
    status_error = validate_delivery_status_transition(delivery.status, '已取消')
    if status_error:
        flash(status_error, 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    form = forms.CancelDeliveryForm()
    
    if request.method == 'GET':
        return render_template('delivery/cancel_delivery.html', form=form, delivery=delivery)
    
    if form.validate_on_submit():
        try:
            # 加锁发货单
            delivery = (db.session.query(DeliveryNote)
                        .filter(DeliveryNote.delivery_note_id == delivery_id)
                        .with_for_update(nowait=False)
                        .first())
            
            if not delivery:
                flash('发货单不存在', 'danger')
                return redirect(url_for('delivery.delivery_list'))
            
            # 更新状态
            delivery.status = '已取消'
            delivery.cancel_reason = form.cancel_reason.data
            delivery.canceled_at = datetime.utcnow()
            delivery.canceled_by = current_user.username
            
            db.session.commit()
            flash(f'发货单【{delivery_id}】已取消', 'success')
            return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
        except SQLAlchemyError:
            db.session.rollback()
            flash('取消发货单时发生数据库错误', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'取消发货单时发生未知错误: {str(e)}', 'danger')
    
    return render_template('delivery/cancel_delivery.html', form=form, delivery=delivery)

# 变更发货单状态
@delivery_bp.route('/change_status/<delivery_id>', methods=['GET', 'POST'])
@login_required
def change_delivery_status(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    
    # 验证状态转换
    if delivery.status not in ['已创建', '已拣货']:
        flash('当前状态不允许变更', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    
    form = forms.ChangeStatusForm()
    
    if request.method == 'GET':
        # 设置默认值
        if delivery.status == '已创建':
            form.new_status.data = '已拣货'
        else:
            form.new_status.data = '已创建'
        return render_template('delivery/change_status.html', form=form, delivery=delivery)
    
    if form.validate_on_submit():
        new_status = form.new_status.data
        status_error = validate_delivery_status_transition(delivery.status, new_status)
        if status_error:
            flash(status_error, 'danger')
            return render_template('delivery/change_status.html', form=form, delivery=delivery)
        
        try:
            # 加锁发货单
            delivery = (db.session.query(DeliveryNote)
                        .filter(DeliveryNote.delivery_note_id == delivery_id)
                        .with_for_update(nowait=False)
                        .first())
            
            if not delivery:
                flash('发货单不存在', 'danger')
                return redirect(url_for('delivery.delivery_list'))
            
            # 更新状态
            delivery.status = new_status
            if form.remarks.data:
                delivery.remarks = (delivery.remarks or '') + f"\n状态变更: {new_status} - {form.remarks.data}"
            delivery.updated_at = datetime.utcnow()
            delivery.updated_by = current_user.username
            
            db.session.commit()
            flash(f'发货单状态已变更为【{new_status}】', 'success')
            return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
        except SQLAlchemyError:
            db.session.rollback()
            flash('状态变更时发生数据库错误', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'状态变更时发生未知错误: {str(e)}', 'danger')
    
    return render_template('delivery/change_status.html', form=form, delivery=delivery)

@delivery_bp.get('/api/sales_orders/<sales_order_id>')
def api_sales_order_items(sales_order_id):
    so = SalesOrder.query.filter_by(sales_order_id=sales_order_id.strip()).first()
    if not so:
        return jsonify({'found': False, 'items': []}), 200

    items = []
    # 遍历订单行
    for oi in so.items:  # OrderItem 列表
        ordered = Decimal(oi.order_quantity or 0)
        shipped = Decimal(oi.shipped_quantity or 0)
        unshipped = ordered - shipped
        if unshipped <= 0:
            continue
        items.append({
            'sales_order_item_no': oi.item_no,
            'material_id': oi.material_id,
            'material_desc': oi.material.description if oi.material else '',
            'unit': oi.unit or '',
            'order_quantity': str(ordered),
            'unshipped_quantity': str(unshipped),
            'planned_delivery_quantity': str(unshipped)  # 默认带出未发数量
        })

    return jsonify({'found': True, 'items': items}), 200
