"""
数据库初始化模块，封装 SQLAlchemy。
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def db_init(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()  # 确保在上下文中创建表
    return db


