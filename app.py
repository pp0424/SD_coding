from flask import Flask
from database import db_init
from customer.views import bp as customer_bp
from order.views import order_bp
from delivery.views import bp as delivery_bp
from finance.views import bp as finance_bp
from auth.views import auth_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sd_system.db'
app.config['SECRET_KEY'] = 'dev'

db = db_init(app)

# 注册模块蓝图（只注册一次）
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(order_bp, url_prefix='/order')
app.register_blueprint(delivery_bp)
app.register_blueprint(finance_bp)

if __name__ == '__main__':
    app.run(debug=True)





