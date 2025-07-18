from flask import Blueprint, render_template, request, redirect, url_for
from .models import Finance
from database import db

bp = Blueprint('finance', __name__, url_prefix='/finance')

# 查询全部（列表页）
@bp.route('/')
def list_finances():
    items = Finance.query.all()
    return render_template('finance/list.html', finances=items)

# 创建（GET + POST）
@bp.route('/create', methods=['GET', 'POST'])
def create_finance():
    if request.method == 'POST':
        # TODO: 获取表单数据并构造模型对象
        item = Finance(...)  
        db.session.add(item)
        db.session.commit()
        return redirect(url_for('finance.list_finances'))
    return render_template('finance/create.html')

# 编辑（GET + POST）
@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_finance(id):
    item = Finance.query.get_or_404(id)
    if request.method == 'POST':
        # TODO: 更新对象字段
        # item.xxx = request.form['xxx']
        db.session.commit()
        return redirect(url_for('finance.list_finances'))
    return render_template('finance/edit.html', finance=item)
