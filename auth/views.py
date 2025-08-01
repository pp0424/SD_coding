from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User

auth_bp = Blueprint('auth', __name__)

# 临时登录用户，后期可从数据库读取
users = {'admin': '123456'}

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('auth.dashboard'))
        else:
            flash('用户名或密码错误')

    return render_template('auth/login.html')

@auth_bp.route('/dashboard')
@login_required  # 添加登录保护
def dashboard():
    return render_template('auth/dashboard.html')

#@auth_bp.route('/logout')
#@login_required
#def logout():
#    logout_user()
#    flash('您已成功退出', 'success')
#    return redirect(url_for('auth.login'))