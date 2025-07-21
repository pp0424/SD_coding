# forms.py for order module
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SubmitField, SelectField
from wtforms.validators import DataRequired, Optional

class InquirySearchForm(FlaskForm):
    inquiry_id = StringField('询价单号', validators=[Optional()])
    customer_id = StringField('客户编号', validators=[Optional()])
    material_id = StringField('物料编号', validators=[Optional()])
    date_start = DateField('起始日期', validators=[Optional()])
    date_end = DateField('结束日期', validators=[Optional()])

    submit = SubmitField('查询')
    show_all = SubmitField('显示全部')


class InquiryForm(FlaskForm):
    inquiry_id = StringField('询价单号', validators=[DataRequired()])
    customer_id = StringField('客户编号', validators=[DataRequired()])
    inquiry_date = DateField('询价日期', validators=[DataRequired()])
    expected_delivery_date = DateField('期望交货日期', validators=[Optional()])
    status = SelectField('询价状态', choices=[('草稿', '草稿'), ('已评审', '已评审'), ('已失效', '已失效')], validators=[Optional()])
    expected_total_amount = DecimalField('客户期望总金额', validators=[Optional()])
    salesperson_id = StringField('销售员编号', validators=[Optional()])
    remarks = StringField('备注', validators=[Optional()])
    submit = SubmitField('提交')

class QuotationSearchForm(FlaskForm):
    quotation_id = StringField("报价单号", validators=[Optional()])
    customer_id = StringField("客户编号", validators=[Optional()])
    date_start = DateField("有效起始日期", validators=[Optional()])
    date_end = DateField("有效截止日期", validators=[Optional()])
    material_id = StringField("物料编号", validators=[Optional()])
    
    submit = SubmitField("查询")
    show_all = SubmitField("显示全部数据")

