"""
数据库初始化模块，封装 SQLAlchemy。
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def db_init(app):
    db.init_app(app)
    db.create_all()
    return db
