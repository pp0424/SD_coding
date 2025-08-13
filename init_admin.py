from app import app, db
from auth.models import User
from werkzeug.security import generate_password_hash

def init_admin():
    with app.app_context():
        try:
            # 检查是否已存在管理员用户
            existing_admin = User.query.filter_by(username='admin').first()
            if existing_admin:
                print("管理员用户已存在，正在更新密码...")
                existing_admin.password_hash = generate_password_hash('123456')
                db.session.commit()
                print("管理员密码已更新")
            else:
                # 创建新的管理员用户
                admin = User(
                    username='admin',
                    password_hash=generate_password_hash('123456')
                )
                db.session.add(admin)
                db.session.commit()
                print("管理员用户创建成功")
                
        except Exception as e:
            print(f"创建管理员用户时出错: {e}")
            db.session.rollback()

if __name__ == '__main__':
    init_admin()