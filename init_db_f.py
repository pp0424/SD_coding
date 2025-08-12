from app import app
from database import db
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment

with app.app_context():
    #db.drop_all()  # 删除所有表
    #print("✅ 数据库已重置，所有表已删除")
    db.create_all()
    print("✅ 数据库初始化完成，已创建新表（如未存在）")