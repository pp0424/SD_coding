from flask import Flask
from jinja2 import Environment, PackageLoader, select_autoescape
from database import db_init
from customer.views import bp as customer_bp
from order.views import order_bp
from delivery.views import  delivery_bp
from finance.views import bp as finance_bp
from auth.views import auth_bp
from auth.models import User
from flask_login import LoginManager


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sd_system.db'
app.config['SECRET_KEY'] = 'dev'

db = db_init(app)

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)  # 将登录管理器绑定到应用实例
login_manager.login_view = 'auth.login'  # 设置登录视图端点

# 用户加载器回调
@login_manager.user_loader
def load_user(user_id):
    # 延迟导入，避免循环依赖
    from auth.views import users
    if user_id in users:
        from auth.models import User
        return User(user_id)
    return None

##数据表与db实时同步
from order_event_listener import attach_csv_export_listeners

with app.app_context():
    attach_csv_export_listeners()


#07261928发货模块
with app.app_context():
    from delivery.models import DeliveryNote, DeliveryItem  # 确保导入模型
    db.create_all()



# 注册模块蓝图（只注册一次）
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(order_bp, url_prefix='/order')
app.register_blueprint(delivery_bp, url_prefix='/delivery')
app.register_blueprint(finance_bp)


if __name__ == '__main__':
    app.run(debug=True)





