"""
数据库初始化模块，封装 SQLAlchemy。
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def db_init(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()  # 自动创建所有 db.Model 的表
    return db
