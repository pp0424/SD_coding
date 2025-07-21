from app import app
from database import db
from order.models import Inquiry, InquiryItem  # 导入你所有模块的模型
from order.models import  Quotation, QuotationItem

with app.app_context():
    db.create_all()
    print("✅ 数据库初始化完成，已创建新表（如未存在）")