from flask import Blueprint, render_template, request, redirect, url_for
from .models import Delivery
from database import db

bp = Blueprint('delivery', __name__, url_prefix='/delivery')

# 查询全部（列表页）
@bp.route('/')
def list_deliverys():
    items = Delivery.query.all()
    return render_template('delivery/list.html', deliverys=items)

# 创建（GET + POST）
@bp.route('/create', methods=['GET', 'POST'])
def create_delivery():
    if request.method == 'POST':
        # TODO: 获取表单数据并构造模型对象
        item = Delivery(...)  
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('delivery.list_deliverys'))
    return render_template('delivery/create.html')

# 编辑（GET + POST）
@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_delivery(id):
    item = Delivery.query.get_or_404(id)
    if request.method == 'POST':
        # TODO: 更新对象字段
        # item.xxx = request.form['xxx']
        db.session.commit()
        return redirect(url_for('delivery.list_deliverys'))
    return render_template('delivery/edit.html', delivery=item)
