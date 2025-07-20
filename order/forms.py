# forms.py for order module
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SubmitField, SelectField
from wtforms.validators import DataRequired, Optional


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
