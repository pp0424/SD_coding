# forms.py for delivery module

from flask_wtf import FlaskForm
from wtforms import StringField, DateField, FloatField, IntegerField, FieldList, FormField, SubmitField
from wtforms.validators import DataRequired, Optional

class DeliveryNoteItemForm(FlaskForm):
    material_id = StringField('物料编号', validators=[DataRequired()])
    planned_qty = FloatField('计划发货数量', validators=[DataRequired()])
    remarks = StringField('备注', validators=[Optional()])

class DeliveryNoteForm(FlaskForm):
    sales_order_id = StringField('销售订单编号', validators=[DataRequired()])
    customer_id = StringField('客户编号', validators=[DataRequired()])
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    remarks = StringField('备注', validators=[Optional()])
    items = FieldList(FormField(DeliveryNoteItemForm), min_entries=1)
    submit = SubmitField('生成发货单')

class DeliveryNoteEditForm(FlaskForm):
    expected_delivery_date = DateField('预计发货日期', validators=[Optional()])
    warehouse_code = StringField('发货仓库代码', validators=[Optional()])
    remarks = StringField('备注', validators=[Optional()])
    submit = SubmitField('保存修改')

class DeliveryNoteQueryForm(FlaskForm):
    delivery_id = StringField('发货单编号', validators=[Optional()])
    sales_order_id = StringField('销售订单编号', validators=[Optional()])
    date_from = DateField('发货日期起', validators=[Optional()])
    date_to = DateField('发货日期止', validators=[Optional()])
    status = StringField('发货单状态', validators=[Optional()])
    submit = SubmitField('查询')
