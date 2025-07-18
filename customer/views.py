from flask import Blueprint, render_template, request, redirect, url_for
from .models import Customer
from database import db

bp = Blueprint('customer', __name__, url_prefix='/customer')

# 查询全部（列表页）
@bp.route('/')
def list_customers():
    items = Customer.query.all()
    return render_template('customer/list.html', customers=items)

# 创建（GET + POST）
@bp.route('/create', methods=['GET', 'POST'])
def create_customer():
    if request.method == 'POST':
        # TODO: 获取表单数据并构造模型对象
        item = Customer(...)  
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('customer.list_customers'))
    return render_template('customer/create.html')

# 编辑（GET + POST）
@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    item = Customer.query.get_or_404(id)
    if request.method == 'POST':
        # TODO: 更新对象字段
        # item.xxx = request.form['xxx']
        db.session.commit()
        return redirect(url_for('customer.list_customers'))
    return render_template('customer/edit.html', customer=item)
