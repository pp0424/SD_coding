from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():  # 确保有 Flask 应用上下文
    admin = User(
        username='admin',
        password_hash=generate_password_hash('123456'),
    )
    db.session.add(admin)
    db.session.commit()
    print("管理员用户创建成功")
