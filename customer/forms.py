from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField
from wtforms.validators import DataRequired, Email, NumberRange, Optional, Length

class CustomerForm(FlaskForm):
    customer_name = StringField('客户名称', validators=[DataRequired()])
    customer_type = SelectField('客户类型',
                               choices=[('person', '个人'), ('group', '团体'), ('organization', '组织')],
                               validators=[DataRequired()])
    address = StringField('注册或经营地址', validators=[DataRequired()])
    phone = StringField('固定办公电话', validators=[DataRequired()])
    email = StringField('官方邮箱', validators=[DataRequired(), Email()])
    credit_limit = DecimalField('信用额度', validators=[Optional(), NumberRange(min=0)], default=0)
    payment_terms_code = StringField('付款条件代码', validators=[Optional()])
    sales_region_code = StringField('销售区域代码', validators=[Optional()])
    status = SelectField('客户状态',
                        choices=[('正常', '正常'), ('已停用', '已停用'), ('已注销', '已注销')],
                        default='正常')

class ContactPersonForm(FlaskForm):
    customer_id = SelectField('所属客户', validators=[DataRequired()], coerce=str)
    first_name = StringField('名', validators=[DataRequired()])
    last_name = StringField('姓', validators=[DataRequired()])
    country_language = SelectField('国家/语言',
                                  choices=[
                                      ('中国/中文', '中国/中文'),
                                      ('美国/英语', '美国/英语'),
                                      ('英国/英语', '英国/英语'),
                                      ('日本/日语', '日本/日语'),
                                      ('韩国/韩语', '韩国/韩语'),
                                      ('德国/德语', '德国/德语'),
                                      ('法国/法语', '法国/法语'),
                                      ('意大利/意大利语', '意大利/意大利语'),
                                      ('西班牙/西班牙语', '西班牙/西班牙语'),
                                      ('俄罗斯/俄语', '俄罗斯/俄语'),
                                      ('印度/英语', '印度/英语'),
                                      ('巴西/葡萄牙语', '巴西/葡萄牙语'),
                                      ('加拿大/英语', '加拿大/英语'),
                                      ('澳大利亚/英语', '澳大利亚/英语'),
                                      ('新加坡/英语', '新加坡/英语'),
                                      ('马来西亚/英语', '马来西亚/英语'),
                                      ('泰国/泰语', '泰国/泰语'),
                                      ('越南/越南语', '越南/越南语'),
                                      ('其他', '其他')
                                  ],
                                  validators=[Optional()],
                                  default='中国/中文')
    country_language_other = StringField('其他国家/语言', validators=[Optional(), Length(max=100)])
    contact_info = StringField('联系方式', validators=[DataRequired()])
    position = StringField('职位', validators=[Optional()])
    status = SelectField('联系人状态',
                        choices=[('有效', '有效'), ('无效', '无效')],
                        default='有效')

class BPRelationshipForm(FlaskForm):
    main_customer_id = SelectField('主客户', validators=[DataRequired()], coerce=str)
    contact_id = SelectField('联系人', validators=[Optional()], coerce=str)
    relationship_type = SelectField('关系类型',
                                   choices=[('分销商', '分销商'), ('代理商', '代理商'), ('合作伙伴', '合作伙伴')],
                                   validators=[DataRequired()])
    description = TextAreaField('关系描述', validators=[Optional()])
    effective_date = DateField('生效日期', validators=[Optional()])
    expiry_date = DateField('失效日期', validators=[Optional()])
    status = SelectField('关系状态',
                        choices=[('有效', '有效'), ('已终止', '已终止')],
                        default='有效')

class CustomerSearchForm(FlaskForm):
    search_type = SelectField('搜索类型',
                             choices=[('customer_id', '客户编号'), ('customer_name', '客户名称'),
                                    ('sales_region_code', '销售区域'), ('status', '客户状态')],
                             default='customer_name')
    search_value = StringField('搜索内容', validators=[Optional()])

class ContactSearchForm(FlaskForm):
    search_type = SelectField('搜索类型',
                             choices=[('customer_id', '所属客户编号'), ('first_name', '名'),
                                    ('last_name', '姓'), ('position', '职位')],
                             default='first_name')
    search_value = StringField('搜索内容', validators=[Optional()])

class BPRelationshipSearchForm(FlaskForm):
    search_type = SelectField('搜索类型',
                             choices=[('main_customer_id', '主客户编号'), ('relationship_type', '关系类型'),
                                    ('status', '关系状态')],
                             default='relationship_type')
    search_value = StringField('搜索内容', validators=[Optional()])
# forms.py for customer module
