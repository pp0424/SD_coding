from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

# 临时登录用户，后期可从数据库读取
users = {'admin': '123456'}

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username] == password:
            return redirect(url_for('auth.dashboard'))
        else:
            flash('用户名或密码错误')

    return render_template('auth/login.html')

@auth_bp.route('/dashboard')
def dashboard():
    return render_template('auth/dashboard.html')