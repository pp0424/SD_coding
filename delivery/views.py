# delivery/views.py
from flask import Blueprint, current_app, jsonify, render_template, redirect, session, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
import traceback
from decimal import Decimal
from customer.models import Customer
from . import forms
from .models import DeliveryNote, DeliveryItem, StockChangeLog
from order.models import SalesOrder,SalesOrder, OrderItem, Material
from datetime import date, datetime, time, timedelta
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
    # 严格的状态转换规则：
    # 已创建 -> 已拣货 -> 已过账
    # 任何状态都可以取消，但取消后不可再操作
    valid_transitions = {
        '已创建': ['已拣货', '已取消'],
        '已拣货': ['已过账', '已取消'],
        '已过账': [],  # 已过账状态不能转换到其他状态
        '已取消': []   # 已取消状态不能转换到其他状态
    }
    
    if current_status not in valid_transitions:
        return f'未知的当前状态：{current_status}'
    
    allowed_transitions = valid_transitions.get(current_status, [])
    if target_status not in allowed_transitions:
        return f'不允许从状态【{current_status}】转换到【{target_status}】'
    
    # 额外业务规则：只有已拣货的发货单才能过账
    if target_status == '已过账' and current_status != '已拣货':
        return '只有已拣货状态的发货单才能过账'
    
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
            lack.append(f'物料 {m.description if m else mid} (库存位置: {m.storage_location if m else "未知"}) 可用库存不足，需要 {need}{m.base_unit if m else ""}，当前 {available}{m.base_unit if m else ""}')
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
                # 获取物料完整信息
                mat = Material.query.filter_by(material_id=oi.material_id).first()
                material_desc = mat.description if mat else ''
                base_unit = mat.base_unit if mat else oi.unit or '件'
                storage_location = mat.storage_location if mat else '未知'
                
                form.items.append_entry({
                    'sales_order_item_no': oi.item_no,
                    'material_id': oi.material_id,
                    'material_desc': material_desc,
                    'base_unit': base_unit,
                    'storage_location': storage_location,
                    'order_quantity': oi.order_quantity,
                    'unshipped_quantity': remain,
                    'planned_delivery_quantity': remain
                })
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

# ========== 视图：发货单拣货 ==========
@delivery_bp.route('/pick/<delivery_id>', methods=['GET', 'POST'])
@login_required
def pick_delivery(delivery_id):
    """拣货操作：更新状态为已拣货并减少可用库存"""
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    
    if delivery.status != '已创建':
        flash('只有已创建状态的发货单才能进行拣货操作', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    try:
        # 锁定发货单
        delivery = (db.session.query(DeliveryNote)
                    .filter(DeliveryNote.delivery_note_id == delivery_id)
                    .with_for_update()
                    .first())
        
        # 先过渡到待拣货状态
        delivery.status = '待拣货'
        db.session.flush()
        
        # 再执行状态转换到已拣货
        delivery.change_status('已拣货')
        
        # 更新操作信息
        current_time = datetime.utcnow()
        operator = getattr(current_user, 'username', 'system')
        delivery.updated_at = current_time
        delivery.updated_by = operator
        
        db.session.commit()
        flash('拣货成功，库存已扣减', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
        
    except ValueError as ve:
        db.session.rollback()
        flash(f'状态转换失败: {str(ve)}', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
    except Exception as e:
        db.session.rollback()
        flash(f'拣货过程中发生错误: {str(e)}', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

# 修改发货单（非过账）
@delivery_bp.route('/edit/<delivery_id>', methods=['GET', 'POST'])
@login_required
def edit_delivery(delivery_id):
    delivery_note = DeliveryNote.query.get_or_404(delivery_id)

    if delivery_note.status not in ['已创建', '已拣货']:
        flash('当前状态不允许修改', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    form = forms.EditDeliveryForm()
    item_forms = [forms.DeliveryItemEditForm(obj=item) for item in delivery_note.items]

    if request.method == 'GET':
        form.expected_delivery_date.data = delivery_note.delivery_date.date()
        form.warehouse_code.data = delivery_note.warehouse_code
        form.remarks.data = delivery_note.remarks

    if form.validate_on_submit():
        # 验证并更新行项目
        errors = []
        for i, item in enumerate(delivery_note.items):
            item_form = forms.DeliveryItemEditForm(request.form, prefix=f'item_{i}')
            if item_form.validate():
                new_qty = item_form.planned_delivery_quantity.data
                
                # 验证数量调整
                if new_qty < 0:
                    errors.append(f'行项目 {i+1}: 数量不能为负数')
                    continue
                    
                # 计算最大允许数量
                max_qty = compute_max_allowable_qty(
                    delivery_note.sales_order_id,
                    item.sales_order_item_no,
                    delivery_note.delivery_note_id
                )
                
                if new_qty > max_qty:
                    errors.append(f'行项目 {i+1}: 数量 {new_qty} 超过允许的最大值 {max_qty}')
                    continue
                    
                item.planned_delivery_quantity = new_qty
            else:
                errors.append(f'行项目 {i+1}: 无效数据')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('delivery/edit_delivery.html', 
                                  form=form, 
                                  delivery=delivery_note,
                                  item_forms=item_forms)

        # 更新抬头信息
        delivery_note.delivery_date = datetime.combine(form.expected_delivery_date.data, time(hour=9))
        delivery_note.warehouse_code = form.warehouse_code.data
        delivery_note.remarks = form.remarks.data
        
        db.session.commit()
        flash('发货单已更新', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    return render_template('delivery/edit_delivery.html', 
                          form=form, 
                          delivery=delivery_note,
                          item_forms=item_forms)

def compute_max_allowable_qty(sales_order_id, item_no, current_dn_id):
    """计算允许的最大发货数量"""
    # 获取销售订单行
    order_item = OrderItem.query.filter_by(
        sales_order_id=sales_order_id,
        item_no=item_no
    ).first()
    
    if not order_item:
        return Decimal('0')
    
    # 计算未发货数量
    unshipped = Decimal(order_item.order_quantity) - Decimal(order_item.shipped_quantity or '0')
    
    # 计算其他未过账发货单中的分配量
    allocated_qty = db.session.query(
        func.sum(DeliveryItem.planned_delivery_quantity)
    ).join(DeliveryNote).filter(
        DeliveryNote.sales_order_id == sales_order_id,
        DeliveryItem.sales_order_item_no == item_no,
        DeliveryNote.status.in_(['已创建', '已拣货']),
        DeliveryNote.delivery_note_id != current_dn_id
    ).scalar() or Decimal('0')
    
    # 最大允许数量 = 未发货数量 + 当前发货单中的原数量 - 其他未过账发货单的分配量
    current_item = DeliveryItem.query.filter_by(
        delivery_note_id=current_dn_id,
        sales_order_item_no=item_no
    ).first()
    
    current_qty = Decimal(current_item.planned_delivery_quantity) if current_item else Decimal('0')
    return max(Decimal('0'), unshipped + current_qty - allocated_qty)

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
@delivery_bp.route('/inventory_movement', methods=['GET'])
@login_required
def inventory_movement():
    search_form = forms.SearchInventoryMovementForm(request.args)
    material_id = search_form.material_id.data or ''
    start_date = search_form.start_date.data
    end_date = search_form.end_date.data
    delivery_id = search_form.delivery_id.data or ''
    warehouse_code = search_form.warehouse_code.data or ''
    movement_type = search_form.movement_type.data or 'all'
    page = int(request.args.get('page', 1))

    query = StockChangeLog.query
    if movement_type != 'all':
        query = query.filter(StockChangeLog.change_type == movement_type)

    if material_id:
        query = query.filter(StockChangeLog.material_id.contains(material_id))
    if start_date:
        query = query.filter(StockChangeLog.change_time >= start_date)
    if end_date:
        query = query.filter(StockChangeLog.change_time <= end_date)
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.contains(delivery_id))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.contains(warehouse_code))

    total_records = query.count()
    total_pages = max(1, ceil(total_records / PER_PAGE))
    movements = query.order_by(StockChangeLog.change_time.desc()) \
        .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    for m in movements:
        m.formatted_time = m.change_time.strftime('%Y-%m-%d %H:%M')

    return render_template(
        'delivery/stock_changes.html',
        search_form=search_form,
        movements=movements,
        page=page,
        total_pages=total_pages,
        total_records=total_records
    )

# 仅查看过账导致的库存变动（发货）
def _parse_ymd(s: str):
    s = (s or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None

@delivery_bp.route('/posted_stock_changes', methods=['GET'])
@login_required
def posted_stock_changes():
    # 读取并清洗查询参数
    material_id = (request.args.get('material_id') or '').strip()
    start_raw = (request.args.get('start_date') or '').strip()
    end_raw = (request.args.get('end_date') or '').strip()
    delivery_id = (request.args.get('delivery_id') or '').strip()
    warehouse_code = (request.args.get('warehouse_code') or '').strip()

    # 解析日期为 datetime，记录错误但不中断
    errors = []
    start_dt = _parse_ymd(start_raw)
    if start_raw and start_dt is None:
        errors.append(f"起始日期格式无效：{start_raw}（应为 YYYY-MM-DD）")

    end_dt = _parse_ymd(end_raw)
    if end_raw and end_dt is None:
        errors.append(f"结束日期格式无效：{end_raw}（应为 YYYY-MM-DD）")

    # 分页参数容错
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    # 每页大小（默认 20）
    per_page = 20
    per_page = max(1, per_page)

    # 基础查询（仅发货）
    query = (StockChangeLog.query
             .filter_by(change_type='发货')
             .order_by(StockChangeLog.change_time.desc()))

    # 模糊查询（大小写不敏感）
    if material_id:
        query = query.filter(StockChangeLog.material_id.ilike(f"%{material_id}%"))
    if delivery_id:
        query = query.filter(StockChangeLog.reference_doc.ilike(f"%{delivery_id}%"))
    if warehouse_code:
        query = query.filter(StockChangeLog.warehouse_code.ilike(f"%{warehouse_code}%"))

    # 安全日期过滤：起始含当天 00:00:00；结束用“次日零点前”排他比较
    if start_dt:
        query = query.filter(StockChangeLog.change_time >= start_dt)
    if end_dt:
        end_exclusive = end_dt + timedelta(days=1)
        query = query.filter(StockChangeLog.change_time < end_exclusive)

    # 统计与页码夹紧
    total_records = query.count()
    total_pages = max(1, ceil(total_records / per_page))
    if page > total_pages:
        page = total_pages

    # 分页查询
    changes = (query
               .offset((page - 1) * per_page)
               .limit(per_page)
               .all())

    # 传递当前查询参数（用于前端构建分页链接）
    # 可选：移除 page，让前端统一覆盖
    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)

    return render_template(
        'delivery/posted_stock_changes.html',
        changes=changes,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        query_args=query_args,
        errors=errors
    )

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

        # 清空 FieldList（正确做法）
        while len(form.items):
            form.items.pop_entry()
        # 逐行追加数据
        for item in delivery.items:
            entry = form.items.append_entry()  # 让 WTForms 自己建 entry
            entry.form.material_id.data = item.material_id
            entry.form.planned_quantity.data = float(item.planned_delivery_quantity or 0)
            entry.form.actual_quantity.data = float(item.planned_delivery_quantity or 0)

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
            
            # 开始事务处理
            current_time = datetime.utcnow()
            operator = getattr(current_user, 'username', 'system')
            
            # 设置实际发货数量
            for item_data in actual_items:
                di = item_data['delivery_item']
                actual = item_data['actual_quantity']
                di.actual_delivery_quantity = actual
            
            # 执行状态转换（过账）并更新库存
            delivery.change_status('已过账', user=operator)
            
            # 更新物料可用库存
            for item_data in actual_items:
                material = Material.query.filter_by(material_id=item_data['material_id']).first()
                if material:
                    material.available_stock = Decimal(material.available_stock or 0) - item_data['actual_quantity']
            
            # 更新发货日期和备注
            delivery.delivery_date = datetime.combine(form.actual_delivery_date.data, time(hour=9))
            if form.remarks.data:
                delivery.remarks = form.remarks.data
            
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
            
        except ValueError as ve:
            db.session.rollback()
            flash(f'状态转换失败: {str(ve)}', 'danger')
            return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('过账时发生数据库错误，请重试或联系管理员', 'danger')
            return render_template('delivery/post_delivery.html', form=form, delivery=delivery)
        except Exception as e:
            db.session.rollback()
            flash(f'过账时发生未知错误: {str(e)}', 'danger')
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
            
            # 执行状态转换（取消）
            delivery.change_status('已取消')
            
            # 更新取消信息
            delivery.cancel_reason = form.cancel_reason.data
            delivery.canceled_at = datetime.utcnow()
            delivery.canceled_by = current_user.username
            
            db.session.commit()
            flash(f'发货单【{delivery_id}】已取消', 'success')
            return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))
        except ValueError as ve:
            db.session.rollback()
            flash(f'状态转换失败: {str(ve)}', 'danger')
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

# imports（新增）
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import joinedload

@delivery_bp.get('/api/sales_orders/<sales_order_id>')
@login_required
def api_sales_order_items(sales_order_id):
    try:
        # 可选：数据库连通性检查（SQLAlchemy 2.0 需要 text()）
        db.session.execute(text('SELECT 1'))

        # joinedload 使用 sqlalchemy.orm.joinedload
        so = (
            db.session.query(SalesOrder)
            .options(joinedload(SalesOrder.items))
            .filter(SalesOrder.sales_order_id == sales_order_id.strip())
            .first()
        )

        if not so:
            current_app.logger.info(f"Sales order {sales_order_id} not found")
            return jsonify({'found': False, 'items': []}), 200

        items = []
        for oi in so.items:
            try:
                ordered = Decimal(oi.order_quantity or 0)
                shipped = Decimal(oi.shipped_quantity or 0)
                unshipped = ordered - shipped
                if unshipped <= 0:
                    continue

                # 确保 material 总是已定义
                material = None
                if getattr(oi, 'material_id', None):
                    # Flask‑SQLAlchemy 3.x 推荐 session.get；老版本用 Material.query.get 也可
                    material = db.session.get(Material, oi.material_id)

                base_unit = (material.base_unit if material else (oi.unit or ''))
                storage_location = (material.storage_location if material else '未知')
                material_desc = (material.description if material else '') or ''

                items.append({
                    'sales_order_item_no': oi.item_no,
                    'material_id': oi.material_id,
                    'material_desc': material_desc,
                    'base_unit': base_unit,
                    'storage_location': storage_location,
                    'unit': oi.unit or '',
                    'order_quantity': str(ordered),
                    'unshipped_quantity': str(unshipped),
                    'planned_delivery_quantity': str(unshipped),
                })
            except Exception as item_error:
                current_app.logger.error(
                    f"Error processing item {getattr(oi, 'item_no', '?')}: {item_error}",
                    exc_info=True
                )

        return jsonify({
            'found': True,
            'items': items,
            'order_status': so.status
        }), 200

    except SQLAlchemyError as db_error:
        current_app.logger.error(f"Database error: {db_error}", exc_info=True)
        return jsonify({
            'error': 'Database error',
            'details': str(db_error)
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500
