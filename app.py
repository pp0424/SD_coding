from flask import Flask
from database import db_init
from customer.views import bp as customer_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sd_system.db'
app.config['SECRET_KEY'] = 'dev'

db = db_init(app)

# 注册模块蓝图（只注册一次）
app.register_blueprint(customer_bp)

if __name__ == '__main__':
    app.run(debug=True)


