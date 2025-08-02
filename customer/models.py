# models.py for customer module
from database import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customer'

    customer_id = db.Column(db.String(255), primary_key=True, comment='客户编号，唯一键（如"CUST-CN00001"）')
    customer_name = db.Column(db.String(255), nullable=False, comment='客户名称，全称')
    customer_type = db.Column(db.String(255), nullable=False, comment='客户类型，分为person/group/organization')
    address = db.Column(db.String(255), nullable=False, comment='注册或经营地址')
    phone = db.Column(db.String(255), nullable=False, comment='固定办公电话')
    email = db.Column(db.String(255), nullable=False, comment='官方邮箱')
    credit_limit = db.Column(db.Numeric(10, 2), default=0, comment='信用额度，非负数')
    payment_terms_code = db.Column(db.String(255), comment='付款条件代码')
    sales_region_code = db.Column(db.String(255), comment='销售区域代码')
    status = db.Column(db.String(255), default='正常', comment='客户状态（"正常""已停用""已注销"）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间，可自动生成')

    # 关系定义
    contact_persons = db.relationship('ContactPerson', backref='customer', lazy=True, cascade='all, delete-orphan')
    bp_relationships = db.relationship('BPRelationship', backref='main_customer', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Customer {self.customer_name}>"

class ContactPerson(db.Model):
    __tablename__ = 'contact_person'

    contact_id = db.Column(db.String(255), primary_key=True, comment='联系人ID，唯一键（如"CONT-00001"）')
    customer_id = db.Column(db.String(255), db.ForeignKey('customer.customer_id'), nullable=False, comment='所属客户编号')
    first_name = db.Column(db.String(255), nullable=False, comment='名')
    last_name = db.Column(db.String(255), nullable=False, comment='姓')
    country_language = db.Column(db.String(255), comment='国家/语言')
    contact_info = db.Column(db.String(255), nullable=False, comment='办公电话/手机/邮箱（至少一项）')
    position = db.Column(db.String(255), comment='职位')
    status = db.Column(db.String(255), default='有效', comment='联系人状态（"有效""无效"）')

    def __repr__(self):
        return f"<ContactPerson {self.first_name} {self.last_name}>"

class BPRelationship(db.Model):
    __tablename__ = 'bp_relationship'

    relationship_id = db.Column(db.String(255), primary_key=True, comment='关系ID，唯一键（如"BPREL-00001"）')
    main_customer_id = db.Column(db.String(255), db.ForeignKey('customer.customer_id'), nullable=False, comment='主客户编号')
    contact_id = db.Column(db.String(255), db.ForeignKey('contact_person.contact_id'), nullable=True, comment='联系人ID')
    relationship_type = db.Column(db.String(255), nullable=False, comment='关系类型（如"分销商""代理商"）')
    description = db.Column(db.String(255), comment='关系描述')
    effective_date = db.Column(db.Date, comment='生效日期')
    expiry_date = db.Column(db.Date, comment='失效日期')
    status = db.Column(db.String(255), default='有效', comment='关系状态（"有效""已终止"）')

    # 关系定义
    contact_person = db.relationship('ContactPerson', backref='bp_relationships', lazy=True)

    def __repr__(self):
        return f"<BPRelationship {self.relationship_type}>"