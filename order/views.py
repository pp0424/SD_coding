from flask import Blueprint, render_template, request, redirect, url_for
from .models import Order
from database import db

bp = Blueprint('order', __name__, url_prefix='/order')

# 查询全部（列表页）
@bp.route('/')
def list_orders():
    items = Order.query.all()
    return render_template('order/list.html', orders=items)

# 创建（GET + POST）
@bp.route('/create', methods=['GET', 'POST'])
def create_order():
    if request.method == 'POST':
        # TODO: 获取表单数据并构造模型对象
        item = Order(...)  
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('order.list_orders'))
    return render_template('order/create.html')

# 编辑（GET + POST）
@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_order(id):
    item = Order.query.get_or_404(id)
    if request.method == 'POST':
        # TODO: 更新对象字段
        # item.xxx = request.form['xxx']
        db.session.commit()
        return redirect(url_for('order.list_orders'))
    return render_template('order/edit.html', order=item)
