
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, DecimalField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import date, datetime, timedelta

class InvoiceSearchForm(FlaskForm):
    """发票查询表单"""
    invoice_id = StringField('发票号', validators=[Optional()])
    sales_order_id = StringField('销售订单号', validators=[Optional()])
    customer_id = StringField('客户编号', validators=[Optional()])
    start_date = DateField('开始日期', validators=[Optional()], default=lambda: date.today() - timedelta(days=30))
    end_date = DateField('结束日期', validators=[Optional()], default=date.today)
    submit = SubmitField('查询')

class PaymentSearchForm(FlaskForm):
    """收款记录查询表单"""
    payment_id = StringField('收款单号', validators=[Optional()])
    invoice_id = StringField('发票号', validators=[Optional()])
    customer_id = StringField('客户编号', validators=[Optional()])
    start_date = DateField('开始日期', validators=[Optional()], default=lambda: date.today() - timedelta(days=30))
    end_date = DateField('结束日期', validators=[Optional()], default=date.today)
    payment_method = SelectField('收款方式', 
                                choices=[('', '全部'), ('银行转账', '银行转账'), 
                                        ('现金', '现金'), ('支票', '支票'), ('其他', '其他')],
                                validators=[Optional()])
    submit = SubmitField('查询')

class InvoiceForm(FlaskForm):
    """发票创建/编辑表单"""
    customer_id = StringField('客户编号', validators=[DataRequired(message='客户编号不能为空')])
    sales_order_id = StringField('销售订单号', validators=[DataRequired(message='销售订单号不能为空')])
    delivery_note_ids = StringField('发货单号', validators=[DataRequired(message='发货单号不能为空')])
    invoice_date = DateField('开票日期', validators=[DataRequired(message='开票日期不能为空')], default=date.today)
    payment_deadline = DateField('付款期限', validators=[DataRequired(message='付款期限不能为空')], 
                                default=lambda: date.today() + timedelta(days=30))
    total_amount = DecimalField('发票总额', validators=[DataRequired(message='发票总额不能为空'), 
                                                  NumberRange(min=0, message='金额必须大于0')], places=2)
    tax_amount = DecimalField('税额', validators=[DataRequired(message='税额不能为空'), 
                                               NumberRange(min=0, message='税额必须大于0')], places=2)
    payment_status = SelectField('付款状态', 
                               choices=[('未付款', '未付款'), ('部分付款', '部分付款'), ('已付款', '已付款')],
                               default='未付款',
                               validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('保存')

class PaymentForm(FlaskForm):
    """收款记录创建/编辑表单"""
    invoice_id = StringField('发票号', validators=[DataRequired(message='发票号不能为空')])
    payment_date = DateField('收款日期', validators=[DataRequired(message='收款日期不能为空')], default=date.today)
    payment_amount = DecimalField('收款金额', validators=[DataRequired(message='收款金额不能为空'), 
                                                    NumberRange(min=0.01, message='收款金额必须大于0')], places=2)
    payment_method = SelectField('收款方式', 
                               choices=[('银行转账', '银行转账'), ('现金', '现金'), 
                                      ('支票', '支票'), ('其他', '其他')],
                               validators=[DataRequired(message='请选择收款方式')])
    write_off_amount = DecimalField('核销金额', validators=[Optional(), NumberRange(min=0)], 
                                  places=2, default=0)
    status = SelectField('状态', 
                        choices=[('已确认', '已确认'), ('待确认', '待确认'), ('已取消', '已取消')],
                        default='已确认',
                        validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('保存')

class DocumentFlowSearchForm(FlaskForm):
    """单据流查询表单"""
    invoice_id = StringField('发票号', validators=[Optional()])
    sales_order_id = StringField('销售订单号', validators=[Optional()])
    material_id = StringField('物料编号', validators=[Optional()])
    submit = SubmitField('查询')

    def validate(self):
        """自定义验证：至少填写一个查询条件"""
        if not super().validate():
            return False
        
        if not (self.invoice_id.data or self.sales_order_id.data or self.material_id.data):
            self.invoice_id.errors.append('请至少填写一个查询条件')
            return False
        
        return True