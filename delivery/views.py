# delivery/views.py
from flask import Blueprint, current_app, json, jsonify, render_template, redirect, session, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from sqlalchemy import exists, func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, load_only
import traceback
from decimal import ROUND_HALF_UP, Decimal
from customer.models import Customer
from . import forms
from .models import QTY_QUANT,DeliveryNote, DeliveryItem, StockChangeLog, PickingTask, PickingTaskItem,Inventory, _q
from order.models import SalesOrder,SalesOrder, OrderItem, Material
from datetime import date, datetime, time, timedelta
from math import ceil
from database import db
import uuid


delivery_bp = Blueprint('delivery', __name__, template_folder='templates')


PER_PAGE = 20

@delivery_bp.route('/')
@login_required
def delivery_home():
    # 获取所有状态及其数量
    statuses = ['已创建', '待拣货', '已拣货',  '已发货', '已过账', '已取消']
    rows = db.session.query(DeliveryNote.status, func.count(DeliveryNote.delivery_note_id)).group_by(DeliveryNote.status).all()
    counts_dict = dict(rows)
    status_counts = {status: counts_dict.get(status, 0) for status in statuses}

    recent_deliveries = DeliveryNote.query.order_by(DeliveryNote.delivery_date.desc()).limit(5).all()
    recent_changes = StockChangeLog.query.order_by(StockChangeLog.change_time.desc()).limit(5).all()
    
    return render_template('delivery/home.html',
                           status_counts=status_counts,
                           recent_deliveries=recent_deliveries,
                           recent_changes=recent_changes)

# ========== 工具函数 ==========
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

def generate_picking_task_id() -> str:
    """生成唯一的拣货任务ID，格式：PTYYYYMMDD-XXX"""

    prefix = 'PT'
    date_str = datetime.now().strftime('%Y%m%d')
    base_prefix = f"{prefix}{date_str}-"

    # 查询当天最后一个拣货任务号
    last_task = PickingTask.query.filter(
        PickingTask.task_id.like(f"{base_prefix}%")
    ).order_by(PickingTask.task_id.desc()).first()

    if last_task and len(last_task.task_id) >= len(base_prefix) + 3:
        try:
            next_num = int(last_task.task_id[-3:]) + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1

    return f"{base_prefix}{next_num:03d}"


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
    allowed_statuses = ['已审核', '部分发货']

    if so.status in ['已取消']:
        return f'该销售订单{so.status}'
    elif so.status in ['已完成']:
        return f'该销售订单{so.status}'
    elif so.status not in allowed_statuses:
        return f'该销售订单{so.status}'
    
    return None

def validate_delivery_status_transition(current_status: str, target_status: str) -> str | None:
    """验证发货单状态转换是否合法（根据业务逻辑）"""
    valid_transitions = {
        '已创建': ['已拣货','已取消'],
        '已拣货': ['已发货', '已取消'],
        '已发货': ['已过账'],   # 已发货不能取消，只能过账
        '已过账': [],  # 最终状态
        '已取消': []   # 最终状态
    }
    
    if current_status not in valid_transitions:
        return f'未知的当前状态：{current_status}'
    
    allowed_transitions = valid_transitions.get(current_status, [])
    if target_status not in allowed_transitions:
        return f'不允许从状态【{current_status}】转换到【{target_status}】'
    
    # 额外业务规则验证
    if target_status == '已过账' and current_status != '已发货':
        return '只有已发货状态的发货单才能过账'
    if target_status == '已发货' and current_status != '已拣货':
        return '只有已拣货状态的发货单才能发货'
    
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
    简化 ATP：按物料聚合需求，基于 Inventory.available_stock 校验（全局，不分仓）。
    只做校验与行锁，不做占用扣减（避免与过账扣减重复）。
    """
    # 汇总需求
    demand = {}
    for it in valid_items:
        demand[it['material_id']] = demand.get(it['material_id'], Decimal(0)) + it['planned_qty']

    mat_ids = list(demand.keys())
    if not mat_ids:
        return

    mats = (db.session.query(Inventory)
            .filter(Inventory.material_id.in_(mat_ids))
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
        DeliveryNote.status.in_(['已拣货']),
        DeliveryNote.delivery_note_id != current_dn_id
    ).scalar() or Decimal('0')
    
    # 最大允许数量 = 未发货数量 + 当前发货单中的原数量 - 其他未过账发货单的分配量
    current_item = DeliveryItem.query.filter_by(
        delivery_note_id=current_dn_id,
        sales_order_item_no=item_no
    ).first()
    
    current_qty = Decimal(current_item.planned_delivery_quantity) if current_item else Decimal('0')
    return max(Decimal('0'), unshipped + current_qty - allocated_qty)

# ========== 工具函数 ==========


##1、创建发货单
@delivery_bp.route('/create_delivery', methods=['GET', 'POST'])
@login_required
def create_delivery():
    """
    创建发货单（状态：已创建），并生成拣货任务及 PickingTaskItem
    """
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
            if not wh_code:
                flash('请填写发货仓库代码', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)
            if not exp_date or exp_date < date.today():
                flash('预计发货日期不能早于今天', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 1) 加锁读取订单与行，并进行订单头校验
            sales_order, so_items = lock_sales_order_and_items(so_id)
            header_err = validate_sales_order_header(sales_order)
            if header_err:
                flash(header_err, 'danger')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 仅允许“已审核/部分发货”的订单创建发货单
            if sales_order.status not in ['已审核', '部分发货']:
                flash('只有“已审核”或“部分发货”的订单允许创建发货单', 'danger')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 2) 行校验与收集
            valid_items, errs = collect_and_validate_items(form, so_items)
            if errs:
                for e in errs:
                    flash(e, 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)
            if not valid_items:
                flash('没有有效的发货行', 'warning')
                return render_template('delivery/create_delivery.html', form=form, order_items=form.items.entries)

            # 3) ATP 校验（基于 Inventory.available_stock）
            atp_check_by_material(valid_items)

            # 创建拣货任务
            new_task_id = generate_picking_task_id()
            picking_task = PickingTask(
                task_id=new_task_id,
                sales_order_id=so_id,
                warehouse_code=wh_code,
                status='待拣货',
                picker=getattr(current_user, 'username', 'system'),
                assigned_at=datetime.now(),
            )
            db.session.add(picking_task)
            db.session.flush()

            # 创建发货单（状态：已创建）
            dn_id = gen_delivery_note_id()
            delivery_dt = datetime.combine(exp_date, time(0, 0, 0))
            dn = DeliveryNote(
                delivery_note_id=dn_id,
                sales_order_id=so_id,
                delivery_date=delivery_dt,
                warehouse_code=wh_code,
                status='已创建',
                remarks=form.remarks.data or '',
                created_by=getattr(current_user, 'username', 'system'),
                picking_task_id=new_task_id,
            )
            db.session.add(dn)
            db.session.flush()

            # 添加发货单行项目 + 同步生成 PickingTaskItem
            line_no = 1
            for it in valid_items:
                planned_qty = Decimal(it['planned_qty'] or 0)
                if planned_qty <= 0:
                    continue

                # 发货单行
                di = DeliveryItem(
                    delivery_note_id=dn_id,
                    item_no=line_no,
                    sales_order_item_no=it['item_no'],
                    material_id=it['material_id'],
                    planned_delivery_quantity=planned_qty,
                    actual_delivery_quantity=Decimal('0'),
                    unit=it.get('unit')
                )
                db.session.add(di)

                # 拣货任务明细生成PickingTaskItem时
                pti = PickingTaskItem(
                    task_id=new_task_id,
                    item_no=line_no,
                    sales_order_item_no=it['item_no'],
                    material_id=it['material_id'],
                    required_quantity=planned_qty,
                    picked_quantity=Decimal('0'),
                    unit=it.get('unit'),
                    storage_location=Inventory.query.filter_by(material_id=it['material_id']).first().storage_location
                )
                db.session.add(pti)


                line_no += 1

            # 提交事务
            db.session.commit()
            flash(f'发货单【{dn_id}】创建成功', 'success')
            return redirect(url_for('delivery.create_delivery', form=form))

        except ValueError as ve:
            db.session.rollback()
            current_app.logger.exception("ValueError during create_delivery: %s", ve)
            flash(str(ve), 'danger')
        except SQLAlchemyError as se:
            db.session.rollback()
            current_app.logger.exception("SQLAlchemyError during create_delivery: %s", se)
            flash(f'数据库操作失败：{se}', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Unknown error during create_delivery: %s", e)
            flash(f'创建发货单时发生未知错误：{e}', 'danger')

    # GET：根据订单号预填行
    if form.sales_order_id.data:
        so = SalesOrder.query.filter_by(sales_order_id=form.sales_order_id.data).first()
        if so and not form.items.entries:
            so_items = OrderItem.query.filter_by(sales_order_id=so.sales_order_id).all()
            for oi in so_items:
                remain = compute_unshipped_dynamic(oi)
                if remain <= 0:
                    continue
                mat = Inventory.query.filter_by(material_id=oi.material_id).first()
                form.items.append_entry({
                    'sales_order_item_no': oi.item_no,
                    'material_id': oi.material_id,
                    'material_desc': (mat.description if mat else ''),
                    'base_unit': (mat.base_unit if mat else oi.unit or '件'),
                    'storage_location': (mat.storage_location if mat else '未知'),
                    'order_quantity': oi.order_quantity,
                    'unshipped_quantity': remain,
                    'planned_delivery_quantity': remain
                })
            order_items_for_view = form.items.entries
    

    return render_template('delivery/create_delivery.html', form=form,order_items=order_items_for_view)

##发货单详情
@delivery_bp.route('/detail/<delivery_id>')
@login_required
def delivery_detail(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    return render_template('delivery/delivery_detail.html', delivery=delivery)

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


##取消发货单
@delivery_bp.route('/cancel/<delivery_id>', methods=['GET', 'POST'])
@login_required
def cancel_delivery(delivery_id):
    from decimal import Decimal
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    original_status = delivery.status

    # 验证状态转换
    status_error = validate_delivery_status_transition(original_status, '已取消')
    if status_error:
        flash(status_error, 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    form = forms.CancelDeliveryForm()

    if request.method == 'GET':
        return render_template('delivery/cancel_delivery.html', form=form, delivery=delivery)

    if form.validate_on_submit():
        try:
            # 加锁发货单，防止并发修改
            delivery = (db.session.query(DeliveryNote)
                        .filter(DeliveryNote.delivery_note_id == delivery_id)
                        .with_for_update(nowait=False)
                        .first())
            if not delivery:
                flash('发货单不存在', 'danger')
                return redirect(url_for('delivery.delivery_list'))

            # 避免重复释放同一物料库存
            released_materials = set()

            # 已创建状态
            if original_status == '已创建':
                if delivery.picking_task:
                    task = delivery.picking_task
                    task.status = '已取消'
                    task.canceled_at = datetime.now()
                    task.canceled_by = current_user.username

                    for item in task.items:
                        item.status = '已取消'
                        item.canceled_at = datetime.now()
                        item.canceled_by = current_user.username

                        # 回退拣货明细库存
                        if item.material_id not in released_materials:
                            material = Inventory.query.filter_by(material_id=item.material_id).first()
                            if material:
                                qty = _q(item.picked_quantity)
                                if qty > 0:
                                    material.release_stock(
                                        qty,
                                        operator=current_user.username,
                                        warehouse_code=delivery.warehouse_code,
                                        reference=delivery.delivery_note_id
                                    )
                                    released_materials.add(item.material_id)

            # 已拣货状态
            elif original_status == '已拣货':
                # 恢复发货明细库存
                for item in delivery.items:
                    if item.material_id not in released_materials:
                        material = Inventory.query.filter_by(material_id=item.material_id).first()
                        if material:
                            qty = _q(item.planned_delivery_quantity)
                            if qty > 0:
                                material.release_stock(
                                    qty,
                                    operator=current_user.username,
                                    warehouse_code=delivery.warehouse_code,
                                    reference=delivery.delivery_note_id
                                )
                                released_materials.add(item.material_id)

                # 取消拣货单及明细，同时回退库存
                if delivery.picking_task:
                    task = delivery.picking_task
                    task.status = '已取消'
                    task.canceled_at = datetime.now()
                    task.canceled_by = current_user.username

                    for item in task.items:
                        item.status = '已取消'
                        item.canceled_at = datetime.now()
                        item.canceled_by = current_user.username

                        if item.material_id not in released_materials:
                            material = Inventory.query.filter_by(material_id=item.material_id).first()
                            if material:
                                qty = _q(item.picked_quantity)
                                if qty > 0:
                                    material.release_stock(
                                        qty,
                                        operator=current_user.username,
                                        warehouse_code=delivery.warehouse_code,
                                        reference=delivery.delivery_note_id
                                    )
                                    released_materials.add(item.material_id)

            # 已发货状态
            elif original_status == '已发货':
                flash('已发货的发货单不能直接取消，请走退货流程', 'danger')
                return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

            # 已过账或已取消状态
            elif original_status in ['已过账', '已取消']:
                flash(f'{original_status} 状态的发货单不能取消', 'danger')
                return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

            # 更新发货单状态和取消信息
            delivery.status = '已取消'
            delivery.cancel_reason = form.cancel_reason.data
            delivery.canceled_at = datetime.now()
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

# 修改发货单（仅已创建状态下）
@delivery_bp.route('/edit/<delivery_id>', methods=['GET', 'POST'])
@login_required
def edit_delivery(delivery_id):
    delivery_note = DeliveryNote.query.get_or_404(delivery_id)

    # 1️⃣ 只允许 "已创建" 状态修改
    if delivery_note.status != '已创建':
        flash('只有“已创建”状态的发货单才能修改', 'danger')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    form = forms.EditDeliveryForm()
    item_forms = [forms.DeliveryItemEditForm(obj=item, prefix=f'item_{i}') 
                  for i, item in enumerate(delivery_note.items)]

    # GET 请求时填充表单数据
    if request.method == 'GET':
        form.expected_delivery_date.data = delivery_note.delivery_date.date()
        form.warehouse_code.data = delivery_note.warehouse_code
        form.remarks.data = delivery_note.remarks

    # 2️⃣ 提交时校验 & 更新
    if form.validate_on_submit():
        errors = []

        for i, item in enumerate(delivery_note.items):
            item_form = forms.DeliveryItemEditForm(request.form, prefix=f'item_{i}')
            if item_form.validate():
                new_qty = item_form.planned_delivery_quantity.data

                # 数量验证
                if new_qty < 0:
                    errors.append(f'行项目 {i+1}: 数量不能为负数')
                    continue

                max_qty = compute_max_allowable_qty(
                    delivery_note.sales_order_id,
                    item.sales_order_item_no,
                    delivery_note.delivery_note_id
                )

                if Decimal(new_qty) > Decimal(max_qty):
                    errors.append(f'行项目 {i+1}: 数量 {new_qty} 超过允许的最大值 {max_qty}')
                    continue

                item.planned_delivery_quantity = new_qty
            else:
                errors.append(f'行项目 {i+1}: 数据无效')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template(
                'delivery/edit_delivery.html',
                form=form,
                delivery=delivery_note,
                item_forms=item_forms
            )

        # 3️⃣ 更新发货单抬头
        delivery_note.delivery_date = datetime.combine(form.expected_delivery_date.data, time(hour=9))
        delivery_note.warehouse_code = form.warehouse_code.data
        delivery_note.remarks = form.remarks.data

        # 4️⃣ 同步到 PickingTask
        if delivery_note.picking_task:
            picking_task = delivery_note.picking_task
            picking_task.warehouse_code = delivery_note.warehouse_code
            picking_task.remarks = delivery_note.remarks

            # 同步行项目
            for d_item in delivery_note.items:
                task_item = PickingTaskItem.query.filter_by(
                    task_id=picking_task.task_id,
                    sales_order_item_no=d_item.sales_order_item_no
                ).first()
                if task_item:
                    task_item.required_quantity = d_item.planned_delivery_quantity

        db.session.commit()
        flash('发货单已更新并同步到拣货任务', 'success')
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    return render_template(
        'delivery/edit_delivery.html',
        form=form,
        delivery=delivery_note,
        item_forms=item_forms
    )

##2、发货单拣货
# -------------------------
# 拣货任务列表
# GET /delivery/picking_tasks
# -------------------------
@delivery_bp.route('/picking_tasks', methods=['GET', 'POST'])
@login_required
def picking_task_list():
    form = forms.SearchPickingTaskForm(request.args)  # 如果用 GET
    q = db.session.query(PickingTask)

    if form.delivery_id.data:
        q = q.join(DeliveryNote, isouter=True).filter(
            DeliveryNote.delivery_note_id.like(f"%{form.delivery_id.data.strip()}%")
        )
    if form.sales_order_id.data:
        q = q.filter(PickingTask.sales_order_id.like(f"%{form.sales_order_id.data.strip()}%"))
    if form.status.data:
        q = q.filter(PickingTask.status == form.status.data)
    if form.start_date.data:
        q = q.filter(PickingTask.start_time >= form.start_date.data)
    if form.end_date.data:
        q = q.filter(PickingTask.start_time <= form.end_date.data)

    q = q.order_by(
        PickingTask.complete_time.desc().nullslast(),
        PickingTask.start_time.desc().nullslast()
    )
    tasks = q.all()

    rows = []
    for t in tasks:
        dn = (db.session.query(DeliveryNote)
              .filter_by(picking_task_id=t.task_id)
              .order_by(DeliveryNote.delivery_date)
              .first())
        rows.append({'task': t, 'delivery': dn})

    return render_template('delivery/picking_task_list.html', form=form, rows=rows)


# -------------------------
# 拣货任务详情页
# GET /delivery/picking_task/<task_id>
# -------------------------
@delivery_bp.route('/picking_task/<task_id>')
@login_required
def picking_task_detail(task_id):
    """
    展示单个拣货任务详情，同时加载关联的发货单及其发货物料明细。
    """
    task = PickingTask.query.get_or_404(task_id)

    # 取关联发货单
    delivery = DeliveryNote.query.filter_by(picking_task_id=task_id).first()

    # 取发货单物料明细，如果有发货单
    delivery_items = []
    if delivery:
        delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery.delivery_note_id).all()

    return render_template(
        'delivery/picking_task_detail.html',
        task=task,
        delivery=delivery,
        delivery_items=delivery_items
    )

# -------------------------
# 确认拣货页面（GET）
# -------------------------
@delivery_bp.route('/picking/confirm/<delivery_id>/<task_id>', methods=['GET'])
@login_required
def confirm_picking_page(delivery_id, task_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    task = PickingTask.query.get_or_404(task_id)

    # 校验任务归属与仓库一致性
    if str(delivery.picking_task_id) != str(task.task_id):
        flash('该拣货任务不属于此发货单', 'danger')
        return redirect(url_for('delivery.picking_task_detail', task_id=task.task_id))

    if delivery.warehouse_code != task.warehouse_code:
        flash('发货单与拣货任务的仓库不一致', 'danger')
        return redirect(url_for('delivery.picking_task_detail', task_id=task.task_id))

    return render_template('delivery/confirm_picking.html', delivery=delivery, task=task)


# -------------------------
# 开始拣货（POST API）
# -------------------------
@delivery_bp.route('/api/picking/start/<task_id>', methods=['POST'])
@login_required
def api_start_picking(task_id):
    now = datetime.now()
    operator = getattr(current_user, 'username', 'system')
    try:
        task = (db.session.query(PickingTask)
                .filter_by(task_id=task_id)
                .with_for_update()
                .one_or_none())
        if not task:
            return ("任务不存在", 404)

        if not task.start_time:
            task.start_time = now
            task.picker = operator
            if hasattr(task, 'updated_at'):
                task.updated_at = now
            if hasattr(task, 'updated_by'):
                task.updated_by = operator

        db.session.commit()  # 用 commit 而不是 with begin
        return jsonify({
            'task_id': task.task_id,
            'start_time': task.start_time.strftime('%Y-%m-%d %H:%M'),
            'picker': task.picker
        })
    except Exception as e:
        db.session.rollback()
        return (str(e), 500)

@delivery_bp.route('/confirm_picking/<delivery_id>', methods=['POST'])
@login_required
def confirm_picking(delivery_id):
    now = datetime.now()
    operator = getattr(current_user, 'username', 'system')

    # 记录原始 payload（帮助排查前端数据）
    raw = request.get_data(as_text=True)
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    if not payload and raw:
        # 如果前端传的是 form encoded 的 tasks 字符串，尝试解析
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}

    current_app.logger.info(
        "confirm_picking called delivery_id=%s operator=%s payload=%s",
        delivery_id, operator, json.dumps(payload, ensure_ascii=False)
    )

    tasks_input = payload.get('tasks', [])
    # 兜底解析 task_id
    fallback_task_id = None
    ids_from_payload = {t.get('task_id') for t in tasks_input if t.get('task_id')}
    if len(ids_from_payload) == 1:
        fallback_task_id = next(iter(ids_from_payload))

    # 基础校验
    if not tasks_input:
        msg = '没有收到拣货确认数据'
        current_app.logger.warning(msg)
        flash(msg, 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg), 400
        delivery = DeliveryNote.query.get(delivery_id)
        task_id_for_redirect = getattr(delivery, 'picking_task_id', None) if delivery else fallback_task_id
        return redirect(url_for('delivery.picking_task_detail', task_id=task_id_for_redirect))

    # 收集 task_ids 并做非空校验
    task_ids = {t.get('task_id') for t in tasks_input if t.get('task_id')}
    if not task_ids:
        msg = '提交的 tasks 中缺少有效的 task_id'
        current_app.logger.warning(msg + " payload_tasks=%s", tasks_input)
        flash(msg, 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg), 400
        return redirect(url_for('delivery.picking_task_detail', task_id=fallback_task_id))

    try:
        # 用 begin_nested 避免 “A transaction is already begun”
        with db.session.begin_nested():
            # 1. 锁发货单
            delivery = (db.session.query(DeliveryNote)
                        .filter_by(delivery_note_id=delivery_id)
                        .with_for_update()
                        .one_or_none())
            if not delivery:
                raise ValueError(f'发货单[{delivery_id}]不存在')

            current_app.logger.info("delivery loaded: id=%s status=%s items=%d",
                                    delivery.delivery_note_id, getattr(delivery, 'status', None),
                                    len(getattr(delivery, 'items', []) or []))

            if getattr(delivery, 'status', None) != '已创建':
                raise ValueError(f'当前状态[{delivery.status}]不允许拣货确认')

            # 2. 锁发货明细
            items = (db.session.query(DeliveryItem)
                     .filter_by(delivery_note_id=delivery_id)
                     .with_for_update()
                     .all())
            item_map = {i.sales_order_item_no: i for i in items}
            current_app.logger.info("delivery items count=%d", len(items))

            # 3. 锁任务头
            tasks = (db.session.query(PickingTask)
                     .filter(PickingTask.task_id.in_(list(task_ids)))
                     .with_for_update()
                     .all())
            if not tasks:
                raise ValueError(f'未找到任何拣货任务: {task_ids}')
            task_map = {t.task_id: t for t in tasks}
            current_app.logger.info("tasks locked: %s", list(task_map.keys()))

            # 仓库一致性
            for task in tasks:
                if task.warehouse_code != delivery.warehouse_code:
                    raise ValueError(f"拣货任务 {task.task_id} 仓库与发货单不一致")

            # 4. 锁任务明细
            pti_rows = (db.session.query(PickingTaskItem)
                        .filter(PickingTaskItem.task_id.in_(list(task_ids)))
                        .with_for_update()
                        .all())
            if not pti_rows:
                raise ValueError('任务明细为空 (PickingTaskItem)')
            pti_map = {(p.task_id, p.item_no): p for p in pti_rows}

            # 5. 遍历输入数据 → 校验 + 库存占用 + 更新数量
            for t in tasks_input:
                task_id = t.get('task_id')
                item_no = t.get('item_no')
                try:
                    picked_qty = Decimal(str(t.get('picked_quantity', '0')))
                except Exception:
                    raise ValueError(f'任务{task_id} 明细{item_no} 拣货数量格式不正确')

                if picked_qty <= 0:
                    raise ValueError(f'任务{task_id} 明细{item_no}拣货数量必须 > 0')

                pti = pti_map.get((task_id, item_no))
                if not pti:
                    raise ValueError(f'任务{task_id} 明细{item_no}不存在')

                req_qty = Decimal(str(pti.required_quantity or 0))
                already = Decimal(str(pti.picked_quantity or 0))
                remaining = req_qty - already
                if picked_qty > remaining:
                    raise ValueError(f'任务{task_id} 明细{item_no}超拣（剩余 {remaining}）')

                # 库存占用
                try:
                    pti.material.allocate_stock(
                        picked_qty,
                        operator=operator,
                        warehouse_code=delivery.warehouse_code,
                        reference=delivery.delivery_note_id
                    )
                except Exception:
                    current_app.logger.exception("allocate_stock failed for material=%s task=%s item_no=%s",
                                                 getattr(pti.material, 'material_id', None),
                                                 task_id, item_no)
                    raise

                # 更新拣货明细
                pti.picked_quantity = already + picked_qty
                if t.get('storage_location'):
                    pti.storage_location = t['storage_location']
                if hasattr(pti, 'updated_at'):
                    pti.updated_at = now
                if hasattr(pti, 'updated_by'):
                    pti.updated_by = operator

                # 更新发货行
                delivery_item = item_map.get(pti.sales_order_item_no)
                if delivery_item:
                    delivery_item.actual_delivery_quantity = (
                        Decimal(str(delivery_item.actual_delivery_quantity or 0)) + picked_qty
                    )
                    if hasattr(delivery_item, 'updated_at'):
                        delivery_item.updated_at = now
                    if hasattr(delivery_item, 'updated_by'):
                        delivery_item.updated_by = operator

            # 6. 任务状态推进
            for task in task_map.values():
                ptis = [p for p in pti_rows if p.task_id == task.task_id]
                total_picked_qty = sum(Decimal(str(p.picked_quantity or 0)) for p in ptis)

                if hasattr(task, 'picked_quantity'):
                    task.picked_quantity = total_picked_qty
                elif hasattr(task, 'total_picked_quantity'):
                    task.total_picked_quantity = total_picked_qty

                all_done_task = ptis and all(
                    Decimal(str(p.picked_quantity or 0)) >= Decimal(str(p.required_quantity or 0))
                    for p in ptis
                )
                any_done_task = any(Decimal(str(p.picked_quantity or 0)) > 0 for p in ptis)

                if all_done_task:
                    task.status = '已完成'
                    task.complete_time = now
                elif any_done_task and getattr(task, 'status', None) not in ('已完成',):
                    task.status = '待拣货'

                task.picker = operator
                if hasattr(task, 'updated_at'):
                    task.updated_at = now
                if hasattr(task, 'updated_by'):
                    task.updated_by = operator

            # 7. 发货单状态推进
            all_done_delivery = all(
                Decimal(str(i.actual_delivery_quantity or 0)) >= Decimal(str(i.planned_delivery_quantity or 0))
                for i in items
            )
            if all_done_delivery:
                delivery.status = '已拣货'
                if hasattr(delivery, 'updated_at'):
                    delivery.updated_at = now
                if hasattr(delivery, 'updated_by'):
                    delivery.updated_by = operator

        # 手动提交
        db.session.commit()

        msg = '拣货完成'
        current_app.logger.info(msg + f' delivery_id={delivery_id} tasks={len(tasks_input)}')
        flash(msg, 'success')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=True, message=msg,
                           redirect=url_for('delivery.picking_task_detail',
                                            task_id=getattr(delivery, 'picking_task_id', fallback_task_id)))

    except ValueError as ve:
        db.session.rollback()
        current_app.logger.warning("业务校验失败: %s", ve)
        flash(f'拣货失败: {ve}', 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=str(ve)), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("拣货处理发生未捕获异常")
        flash('拣货失败: 内部错误', 'danger')
        if current_app.debug:
            return jsonify(success=False, message=str(e), traceback=traceback.format_exc()), 500
        return jsonify(success=False, message='内部错误'), 500

    # 最终跳回任务详情（非 AJAX）
    task_id_for_redirect = getattr(delivery, 'picking_task_id', None) if 'delivery' in locals() else fallback_task_id
    return redirect(url_for('delivery.picking_task_detail', task_id=task_id_for_redirect))

@delivery_bp.route('/cancel_picking_task/<task_id>', methods=['GET', 'POST'])
@login_required
def cancel_picking_task(task_id):
    """
    取消拣货任务（支持两种状态）：
      - 若任务状态 == '待拣货'：仅将任务置为 '已取消'（不修改库存）
      - 若任务状态 == '已完成'：释放已占用库存（调用 Inventory.release_stock），并回退已拣数量与发货行已拣量
    前提：相关发货单不能为 '已发货'（若已发货需走退货/回库流程）。
    支持普通表单提交与 AJAX(JSON) 提交，返回与现有风格一致（flash / jsonify / redirect）。
    """
    now = datetime.now()
    operator = getattr(current_user, 'username', 'system')

    # load task
    task = PickingTask.query.get_or_404(task_id)

    # try find linked delivery (typical mapping: DeliveryNote.picking_task_id -> PickingTask.task_id)
    delivery = DeliveryNote.query.filter_by(picking_task_id=task.task_id).first()
    # 只有发货单状态为已创建或已拣货时才能取消
    if delivery.status not in ['已创建', '已拣货']:
        flash("只有发货单状态为 '已创建' 或 '已拣货' 时才能取消拣货任务", "danger")
        return redirect(url_for('delivery.picking_task_detail', task_id=task_id))

    form = forms.CancelPickingForm()

    # GET: render page
    if request.method == 'GET':
        delivery_items = []
        if delivery:
            delivery_items = DeliveryItem.query.filter_by(delivery_note_id=delivery.delivery_note_id).all()
        return render_template(
            'delivery/cancel_picking_task.html',
            form=form,
            task=task,
            delivery=delivery,
            delivery_items=delivery_items
        )

    # POST: validate form
    if not form.validate_on_submit():
        msg = '取消原因为必填项'
        flash(msg, 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg), 400
        return redirect(url_for('delivery.picking_task_detail', task_id=task.task_id))

    try:
        # begin nested transaction to avoid outer transaction conflicts
        with db.session.begin_nested():
            # re-lock task
            task_locked = (db.session.query(PickingTask)
                           .filter(PickingTask.task_id == task_id)
                           .with_for_update()
                           .one_or_none())
            if not task_locked:
                raise ValueError(f'拣货任务[{task_id}]不存在')

            # lock and validate delivery (if present)
            delivery_locked = None
            delivery_items = []
            delivery_item_map = {}
            if delivery:
                delivery_locked = (db.session.query(DeliveryNote)
                                   .filter(DeliveryNote.delivery_note_id == delivery.delivery_note_id)
                                   .with_for_update()
                                   .one_or_none())
                if not delivery_locked:
                    raise ValueError(f'发货单[{delivery.delivery_note_id}]不存在')

                if getattr(delivery_locked, 'status', None) == '已发货':
                    raise ValueError('发货单已发货，不能取消拣货；请走退货/回库流程')

                # lock delivery items (for adjusting actual_delivery_quantity)
                delivery_items = (db.session.query(DeliveryItem)
                                  .filter(DeliveryItem.delivery_note_id == delivery_locked.delivery_note_id)
                                  .with_for_update()
                                  .all())
                # map by sales_order_item_no 
                delivery_item_map = {di.sales_order_item_no: di for di in delivery_items if getattr(di, 'sales_order_item_no', None) is not None}

            # only allow cancel for two statuses
            if task_locked.status not in ('待拣货', '已完成'):
                raise ValueError(f'仅允许取消状态为 待拣货 或 已完成 的拣货任务，当前状态: {task_locked.status}')

            # Prepare set of sales_order header ids to update later
            so_ids = set()
            # prefer delivery-level sales_order_id if exists
            if delivery_locked and getattr(delivery_locked, 'sales_order_id', None):
                so_ids.add(delivery_locked.sales_order_id)

            # CASE A: 待拣货 -> 无库存变动，仅改状态
            if task_locked.status == '待拣货':
                task_locked.status = '已取消'
                task_locked.cancel_reason = form.cancel_reason.data
                task_locked.canceled_at = now
                task_locked.canceled_by = operator
                task_locked.picker = None
                task_locked.complete_time = None
                if hasattr(task_locked, 'updated_at'):
                    task_locked.updated_at = now
                if hasattr(task_locked, 'updated_by'):
                    task_locked.updated_by = operator

                # 强制将发货单设为 已创建（按你的要求）
                if delivery_locked:
                    delivery_locked.status = '已创建'
                    if hasattr(delivery_locked, 'updated_at'):
                        delivery_locked.updated_at = now
                    if hasattr(delivery_locked, 'updated_by'):
                        delivery_locked.updated_by = operator

                    # collect sales_order ids from delivery_items if present
                    for di in delivery_items:
                        if getattr(di, 'sales_order_id', None):
                            so_ids.add(di.sales_order_id)

            # CASE B: 已完成 -> 释放库存并回退数量
            else:
                # lock task items
                pti_rows = (db.session.query(PickingTaskItem)
                            .filter(PickingTaskItem.task_id == task_locked.task_id)
                            .with_for_update()
                            .all())
                if pti_rows is None:
                    pti_rows = []

                # build releases per material and record per-pti release
                release_by_material = {}
                pti_release = {}
                for pti in pti_rows:
                    picked = Decimal(str(pti.picked_quantity or 0))
                    if picked <= 0:
                        pti_release[(pti.task_id, pti.item_no)] = Decimal('0')
                        continue

                    # find material id
                    mat_id = None
                    if hasattr(pti, 'material') and getattr(pti, 'material') is not None:
                        mat_id = getattr(pti.material, 'material_id', None)
                    if not mat_id:
                        mat_id = getattr(pti, 'material_id', None)
                    if not mat_id:
                        current_app.logger.warning("PickingTaskItem %s.%s 缺少 material_id，跳过释放", pti.task_id, pti.item_no)
                        pti_release[(pti.task_id, pti.item_no)] = Decimal('0')
                        continue

                    # quantize picked qty
                    picked = picked.quantize(QTY_QUANT)
                    release_by_material[mat_id] = release_by_material.get(mat_id, Decimal('0')) + picked
                    pti_release[(pti.task_id, pti.item_no)] = picked

                # Normalize material release quantities and call Inventory.release_stock
                for mat_id, rel_qty in release_by_material.items():
                    rel_qty = Decimal(rel_qty).quantize(QTY_QUANT)
                    if rel_qty <= 0:
                        continue
                    mat = db.session.query(Inventory).filter_by(material_id=mat_id).one_or_none()
                    if not mat:
                        raise ValueError(f'物料 {mat_id} 在库存表中不存在（release）')
                    try:
                        # Inventory.release_stock 应该会 with_for_update() 并检查 allocated >= rel_qty
                        mat.release_stock(rel_qty, operator=operator,
                                          warehouse_code=(delivery_locked.warehouse_code if delivery_locked else None),
                                          reference=(delivery_locked.delivery_note_id if delivery_locked else None))
                    except Exception:
                        current_app.logger.exception("release_stock failed for material=%s task=%s", mat_id, task_id)
                        raise

                # 对每个 pti 回退 picked_quantity 并更新对应发货行 actual_delivery_quantity（若能映射）
                for pti in pti_rows:
                    key = (pti.task_id, pti.item_no)
                    rel = pti_release.get(key, Decimal('0'))
                    if rel <= 0:
                        continue

                    before_pti = Decimal(str(pti.picked_quantity or 0)).quantize(QTY_QUANT)
                    new_pti = (before_pti - rel).quantize(QTY_QUANT)
                    if new_pti < 0:
                        raise ValueError(f'任务明细 {pti.task_id}.{pti.item_no} 回退后数量为负，请检查数据')
                    pti.picked_quantity = new_pti
                    if hasattr(pti, 'updated_at'):
                        pti.updated_at = now
                    if hasattr(pti, 'updated_by'):
                        pti.updated_by = operator

                    # update delivery item if mapped by sales_order_item_no
                    so_item_no = getattr(pti, 'sales_order_item_no', None)
                    di = delivery_item_map.get(so_item_no)
                    if di:
                        before_di = Decimal(str(di.actual_delivery_quantity or 0)).quantize(QTY_QUANT)
                        new_di = (before_di - rel).quantize(QTY_QUANT)
                        if new_di < 0:
                            raise ValueError(f'发货行 {di.sales_order_item_no} 的 actual_delivery_quantity 回退后为负，请检查数据')
                        di.actual_delivery_quantity = new_di
                        if hasattr(di, 'updated_at'):
                            di.updated_at = now
                        if hasattr(di, 'updated_by'):
                            di.updated_by = operator

                # finally mark task canceled and write cancel info
                task_locked.status = '已取消'
                task_locked.cancel_reason = form.cancel_reason.data
                task_locked.canceled_at = now
                task_locked.canceled_by = operator
                task_locked.picker = None
                task_locked.complete_time = None
                if hasattr(task_locked, 'updated_at'):
                    task_locked.updated_at = now
                if hasattr(task_locked, 'updated_by'):
                    task_locked.updated_by = operator

                # force delivery to '已创建' per requirement
                if delivery_locked:
                    delivery_locked.status = '已创建'
                    if hasattr(delivery_locked, 'updated_at'):
                        delivery_locked.updated_at = now
                    if hasattr(delivery_locked, 'updated_by'):
                        delivery_locked.updated_by = operator

        # commit the transaction
        db.session.commit()

        msg = f'拣货任务 {task_id} 已取消'
        current_app.logger.info(msg + f' by={operator}')
        flash(msg, 'success')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            redirect_url = url_for('delivery.picking_task_detail', task_id=task_locked.task_id)
            return jsonify(success=True, message=msg, redirect=redirect_url)
        return redirect(url_for('delivery.picking_task_detail', task_id=task_locked.task_id))

    except ValueError as ve:
        db.session.rollback()
        current_app.logger.warning("取消拣货业务校验失败: %s", ve)
        flash(f'取消拣货失败: {ve}', 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=str(ve)), 400

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("取消拣货时发生数据库错误")
        flash('取消拣货时发生数据库错误', 'danger')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='数据库错误'), 500

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("取消拣货时发生未知异常")
        flash('取消拣货失败: 内部错误', 'danger')
        if current_app.debug:
            import traceback
            return jsonify(success=False, message=str(e), traceback=traceback.format_exc()), 500
        return jsonify(success=False, message='内部错误'), 500
    

###-----------执行发货---------##
Q4 = Decimal('0.0001')
def to_decimal(v):
    if v is None:
        return Decimal('0')
    return Decimal(str(v)).quantize(Q4, rounding=ROUND_HALF_UP)

@delivery_bp.route('/shipment-list', methods=['GET', 'POST'])
@login_required
def shipment_list():
    """
    发货单列表 + 查询
    模板使用 {{ form.csrf_token }}，因此这里统一变量名为 form
    返回 (DeliveryNote, PickingTask) 元组，模板中解包使用
    """
    from datetime import datetime, time

    form = forms.SearchDeliveryForm()

    # 基础查询：发货单 + 拣货任务（仅展示“已拣货”的发货单，且拣货任务“已完成”）
    deliveries_q = (
        db.session.query(DeliveryNote, PickingTask)
        .join(PickingTask, DeliveryNote.picking_task_id == PickingTask.task_id)
        .filter(
            DeliveryNote.status == '已拣货',
            PickingTask.status == '已完成'
        )
        .order_by(DeliveryNote.delivery_date.desc())
    )

    # 兼容 GET 参数（无提交也能筛选）
    if form.validate_on_submit() or request.method == 'GET':
        form.delivery_id.data = form.delivery_id.data or request.args.get('delivery_id', '')
        form.sales_order_id.data = form.sales_order_id.data or request.args.get('sales_order_id', '')
        form.status.data = form.status.data or request.args.get('status', '')

        if request.args.get('start_date'):
            try:
                form.start_date.data = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            except Exception:
                pass
        if request.args.get('end_date'):
            try:
                form.end_date.data = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            except Exception:
                pass

        # 按表单条件追加过滤
        if form.delivery_id.data:
            deliveries_q = deliveries_q.filter(DeliveryNote.delivery_note_id.contains(form.delivery_id.data))
        if form.sales_order_id.data:
            deliveries_q = deliveries_q.filter(DeliveryNote.sales_order_id.contains(form.sales_order_id.data))
        if form.start_date.data:
            deliveries_q = deliveries_q.filter(
                DeliveryNote.delivery_date >= datetime.combine(form.start_date.data, time.min)
            )
        if form.end_date.data:
            deliveries_q = deliveries_q.filter(
                DeliveryNote.delivery_date <= datetime.combine(form.end_date.data, time.max)
            )
        # 可选：允许覆盖默认状态（否则默认锁定为“已拣货”）
        if form.status.data:
            deliveries_q = deliveries_q.filter(DeliveryNote.status == form.status.data)

    # 只在这里执行查询
    deliveries = deliveries_q.all()

    return render_template(
        'delivery/shipment_list.html',
        form=form,
        deliveries=deliveries
    )

@delivery_bp.route('/shipment-page/<delivery_id>', methods=['GET'])
@login_required
def shipment_page(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    form = forms.ShipmentConfirmForm()
    return render_template(
        'delivery/shipment_list.html',
        delivery=delivery,
        form=form
    )

Q4 = Decimal('0.0001')

def to_decimal(v):
    if v is None:
        return Decimal('0')
    return Decimal(str(v)).quantize(Q4, rounding=ROUND_HALF_UP)

@delivery_bp.route('/shipment/<delivery_id>', methods=['POST'])
@login_required
def shipment(delivery_id):
    form = forms.ShipmentConfirmForm()
    if not form.validate_on_submit():
        flash('CSRF 校验失败，请重试', 'danger')
        return redirect(url_for('delivery.shipment_list'))

    try:
        delivery = DeliveryNote.query.get_or_404(delivery_id)
        delivery = (db.session.query(DeliveryNote)
                        .filter(DeliveryNote.delivery_note_id == delivery_id)
                        .with_for_update(nowait=False)
                        .first())

        if delivery.status != '已拣货':
            raise ValueError(f'当前状态[{delivery.status}]不允许直接发货')

        operator = getattr(current_user, 'username', 'system')
        wh_code = delivery.warehouse_code
        reference = delivery.delivery_note_id

        for item in delivery.items:
            ship_qty = to_decimal(item.actual_delivery_quantity or 0)
            if ship_qty <= 0:
                continue

            material = (db.session.query(Inventory)
                        .filter_by(material_id=item.material_id)
                        .with_for_update()
                        .one_or_none())
            if not material:
                raise ValueError(f'物料 {item.material_id} 不存在')

            material.ship_stock(
                qty=ship_qty,
                operator=operator,
                warehouse_code=wh_code,
                reference=reference
            )

        delivery.status = '已发货'
        delivery.updated_at = datetime.now()
        delivery.updated_by = operator

        db.session.commit()
        flash(f'发货单 {delivery_id} 发货成功', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'发货失败：{str(e)}', 'danger')

    return redirect(url_for('delivery.shipment_list'))


###-----------执行过账---------##
@delivery_bp.route('/post_delivery/<delivery_id>', methods=['GET', 'POST'])
@login_required
def post_delivery(delivery_id):
    # 获取发货单并锁定，防止并发修改
    delivery = (db.session.query(DeliveryNote)
                .filter(DeliveryNote.delivery_note_id == delivery_id)
                .options(joinedload(DeliveryNote.items))
                .with_for_update()
                .first())
    if not delivery:
        flash(f"发货单 {delivery_id} 不存在", "danger")
        return redirect(url_for('delivery.shipment_list'))

    form = forms.PostDeliveryForm()

    # GET 请求 — 初始化表单数据
    if request.method == 'GET':
        for item in delivery.items:
            entry = form.items.append_entry()
            entry.item_no.data = item.item_no  # ✅ 新增隐藏字段
            entry.material_id.data = item.material_id
            entry.planned_quantity.data = float(item.planned_delivery_quantity or 0)
            entry.actual_quantity.data = float(item.actual_delivery_quantity or item.planned_delivery_quantity or 0)
        form.actual_delivery_date.data = delivery.delivery_date
        return render_template('delivery/post_delivery.html', delivery=delivery, form=form)

    # POST 请求 — 表单验证
    if not form.validate_on_submit():
        flash("表单验证失败，请检查输入", "danger")
        return render_template('delivery/post_delivery.html', delivery=delivery, form=form)

    try:
        # 状态校验
        if delivery.status != '已发货':
            flash(f"发货单当前状态为 {delivery.status}，不允许过账", "danger")
            return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

        # 遍历每一行发货记录
        for i, item_form in enumerate(form.items.entries):
            item_no = int(item_form.item_no.data)
            planned_qty = Decimal(item_form.planned_quantity.data or 0)
            actual_qty = Decimal(item_form.actual_quantity.data or 0)

            if actual_qty < 0:
                raise ValueError(f"第{i+1}行实际发货数量不能为负")
            if actual_qty > planned_qty:
                raise ValueError(f"第{i+1}行实际发货数量({actual_qty})不能大于计划数量({planned_qty})")

            # 找到对应的 DeliveryItem
            delivery_item = next((di for di in delivery.items if di.item_no == item_no), None)
            if not delivery_item:
                raise ValueError(f"发货明细 {item_no} 不存在")

            # 找到对应的订单行
            order_item = (db.session.query(OrderItem)
                          .filter(OrderItem.sales_order_id == delivery.sales_order_id,
                                  OrderItem.item_no == delivery_item.sales_order_item_no)
                          .with_for_update()
                          .first())
            if not order_item:
                raise ValueError(f"订单项 {delivery.sales_order_id}-{delivery_item.sales_order_item_no} 不存在")

            # 校验订单剩余量
            remaining_qty = Decimal(order_item.order_quantity or 0) - Decimal(order_item.shipped_quantity or 0)
            if actual_qty > remaining_qty:
                raise ValueError(f"第{i+1}行发货数量({actual_qty})超过订单剩余量({remaining_qty})")

            # 获取物料并加锁
            material = (db.session.query(Inventory)
                        .filter(Inventory.material_id == delivery_item.material_id)
                        .with_for_update()
                        .first())
            if not material:
                raise ValueError(f"物料 {delivery_item.material_id} 不存在")

            # 计算数量变化
            previous_actual_qty = delivery_item.actual_delivery_quantity or Decimal('0')
            delta_qty = actual_qty - previous_actual_qty

            # 库存扣减或回滚
            if delta_qty > 0:
                material.ship_stock(qty=delta_qty,
                                     operator=current_user.username,
                                     warehouse_code=delivery.warehouse_code,
                                     reference=delivery.delivery_note_id)
            elif delta_qty < 0:
                if not current_app.config.get('ALLOW_DELIVERY_ROLLBACK', True):
                    raise ValueError("系统配置不允许减少发货数量")
                material.return_stock(qty=abs(delta_qty),
                                       operator=current_user.username,
                                       warehouse_code=delivery.warehouse_code,
                                       reference=delivery.delivery_note_id)

            # 更新发货明细
            delivery_item.actual_delivery_quantity = actual_qty

            # 更新订单发货统计
            order_item.shipped_quantity = (order_item.shipped_quantity or Decimal('0')) + delta_qty
            order_item.unshipped_quantity = max(
                Decimal(order_item.order_quantity or 0) - Decimal(order_item.shipped_quantity or 0),
                Decimal('0')
            )

        # 更新发货单状态
        delivery.status = '已过账'
        posted_at = form.actual_delivery_date.data
        if not isinstance(posted_at, datetime):
            posted_at = datetime.now()
        delivery.posted_at = posted_at
        delivery.posted_by = current_user.username
        if form.remarks.data:
            delivery.remarks = (delivery.remarks or '') + f"\n[过账备注] {form.remarks.data}"

        db.session.commit()
        flash("发货单过账成功，库存已扣减，订单已更新", "success")
        return redirect(url_for('delivery.delivery_detail', delivery_id=delivery_id))

    except ValueError as ve:
        db.session.rollback()
        flash(str(ve), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("数据库错误，请联系管理员", "danger")

    return render_template('delivery/post_delivery.html', delivery=delivery, form=form)

@delivery_bp.route('/post-list', methods=['GET'])
@login_required
def post_list():
    """
    过账发货列表 + 查询
    展示状态为“已发货”的发货单
    模板中同样使用 {{ form.csrf_token }}，统一变量名为 form
    """
    form = forms.SearchDeliveryForm()

    if form.validate_on_submit():
         query = DeliveryNote.query
         if form.delivery_id.data:
             query = query.filter(DeliveryNote.delivery_note_id.like(f"%{form.delivery_id.data}%"))
         if form.sales_order_id.data:
             query = query.filter(DeliveryNote.sales_order_id.like(f"%{form.sales_order_id.data}%"))
         deliveries = query.filter_by(status='已发货').all()
    else:
         deliveries = DeliveryNote.query.filter_by(status='已发货').all()

    return render_template(
        'delivery/post_list.html',  # 建议单独做一个模板，避免和发货确认列表混用
        form=form,
        deliveries=deliveries
    )

###-----------库存变动查询---------##
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


###-----------自动加载销售订单商品信息---------##
@delivery_bp.get('/api/sales_orders/<sales_order_id>')
@login_required
def api_sales_order_items(sales_order_id):
    try:
        sales_order_id = (sales_order_id or '').strip()
        if not sales_order_id:
            return jsonify({'found': False, 'items': []}), 200

        # 确保 DB 可用
        db.session.execute(text('SELECT 1'))

        # 查询订单及其行
        so = (
            db.session.query(SalesOrder)
            .options(joinedload(SalesOrder.items))
            .filter(SalesOrder.sales_order_id == sales_order_id)
            .first()
        )

        if not so:
            current_app.logger.info(f"Sales order {sales_order_id} not found")
            return jsonify({'found': False, 'items': []}), 200

        items = []
        storage_locations_set = set()  # 用集合收集仓库位置

        for oi in so.items:
            try:
                ordered = float(oi.order_quantity or 0)
                shipped = float(oi.shipped_quantity or 0)
                unshipped = ordered - shipped
                if unshipped <= 0:
                    continue

                # 获取物料信息
                material = None
                if getattr(oi, 'material_id', None):
                    material = db.session.get(Inventory, oi.material_id)

                base_unit = material.base_unit if material else (oi.unit or '')
                storage_location = material.storage_location if material else '未知'
                material_desc = material.description if material else ''

                storage_locations_set.add(storage_location)

                items.append({
                    'sales_order_item_no': oi.item_no,
                    'material_id': oi.material_id,
                    'material_desc': material_desc,
                    'base_unit': base_unit,
                    'storage_location': storage_location,
                    'unit': oi.unit or '',
                    'order_quantity': ordered,
                    'unshipped_quantity': unshipped,
                    'planned_delivery_quantity': unshipped
                })

            except Exception as item_error:
                current_app.logger.error(
                    f"Error processing item {getattr(oi, 'item_no', '?')}: {item_error}",
                    exc_info=True
                )

        # 将所有仓库位置用逗号拼接，返回给前端
        warehouse_code = ','.join(sorted(storage_locations_set)) if storage_locations_set else ''

        return jsonify({
            'found': True,
            'items': items,
            'order_status': so.status,
            'warehouse_code': warehouse_code,
            'order_date': so.order_date.isoformat() if so.order_date else '',
            'required_delivery_date': so.required_delivery_date.isoformat() if so.required_delivery_date else ''
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
