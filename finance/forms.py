# forms.py for finance module
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateTimeField, DateField, SelectField, TextAreaField
from wtforms.validators import DataRequired

class InvoiceSearchForm(FlaskForm):
    invoice_id = StringField('发票编号')
    sales_order_id = StringField('订单编号')

class PaymentSearchForm(FlaskForm):
    payment_id = StringField('收款编号')
    invoice_id = StringField('发票编号')

class InvoiceForm(FlaskForm):
    invoice_id = StringField('发票编号', validators=[DataRequired()])
    customer_id = StringField('客户编号', validators=[DataRequired()])
    sales_order_id = StringField('订单编号', validators=[DataRequired()])
    invoice_date = DateTimeField('开票日期', validators=[DataRequired()])
    payment_deadline = DateField('付款期限', validators=[DataRequired()])
    total_amount = DecimalField('总金额', validators=[DataRequired()])
    tax_amount = DecimalField('税额', validators=[DataRequired()])
    payment_status = SelectField('付款状态', choices=[('未收款', '未收款'), ('部分收款', '部分收款'), ('已结清', '已结清')])
    remarks = TextAreaField('备注')

class PaymentForm(FlaskForm):
    payment_id = StringField('收款编号', validators=[DataRequired()])
    customer_id = StringField('客户编号', validators=[DataRequired()])
    invoice_id = StringField('发票编号', validators=[DataRequired()])
    payment_date = DateTimeField('收款日期', validators=[DataRequired()])
    payment_amount = DecimalField('收款金额', validators=[DataRequired()])
    write_off_amount = DecimalField('核销金额', validators=[DataRequired()])
    payment_method = SelectField('收款方式', choices=[('银行转账', '银行转账'), ('现金', '现金')])
    status = SelectField('状态', choices=[('已确认', '已确认'), ('已取消', '已取消')])
    remarks = TextAreaField('备注')
