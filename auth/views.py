from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User

auth_bp = Blueprint('auth', __name__, template_folder='templates', static_folder='static')

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    # 如果用户已经登录，直接跳转到仪表板
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 添加基本验证
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('auth/login.html')
        
        # 从数据库查询用户
        user = User.query.filter_by(username=username).first()
        
        # 校验用户存在且密码正确
        if user and user.password_hash == password:
            login_user(user)
            flash('登录成功！', 'success')
            # 获取下一个页面参数，如果没有则跳转到仪表板
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('auth.dashboard'))
        else:
            flash('用户名或密码错误', 'error')

    return render_template('auth/login.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('auth/dashboard.html', user=current_user)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出', 'success')
    return redirect(url_for('auth.login'))