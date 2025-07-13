"""
主程序入口：负责启动 Flask 应用，并注册各模块蓝图。
"""
from flask import Flask
from database import db_init

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sd_system.db'
app.config['SECRET_KEY'] = 'dev'

db = db_init(app)

# 注册各功能模块的蓝图（暂时注释，模块开发后取消注释）
# from customer.views import bp as customer_bp
# app.register_blueprint(customer_bp)

if __name__ == '__main__':
    app.run(debug=True)
