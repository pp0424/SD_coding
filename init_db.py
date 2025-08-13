from app import app
from database import db
from order.models import Inquiry, InquiryItem  # 导入你所有模块的模型
from order.models import  Quotation, QuotationItem
from order.models import  SalesOrder,OrderItem,Material

with app.app_context():
    db.drop_all()  # 删除所有表
    print("✅ 数据库已重置，所有表已删除")
    db.create_all()
    print("✅ 数据库初始化完成，已创建新表（如未存在）")
