# delivery/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, DecimalField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from wtforms.fields import FieldList, FormField

class DeliveryItemForm(FlaskForm):
    material_id = StringField('物料编号', validators=[DataRequired()])
    material_desc = StringField('物料描述', render_kw={'readonly': True})
    order_quantity = DecimalField('订单数量', render_kw={'readonly': True})
    unshipped_quantity = DecimalField('未发货数量', render_kw={'readonly': True})
    planned_delivery_quantity = DecimalField('计划发货数量', validators=[DataRequired(), NumberRange(min=0)])

class CreateDeliveryForm(FlaskForm):
    sales_order_id = StringField('销售订单编号', validators=[DataRequired()])
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    items = FieldList(FormField(DeliveryItemForm), min_entries=1)
    submit = SubmitField('创建发货单')

class EditDeliveryForm(FlaskForm):
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    remarks = TextAreaField('备注')
    submit = SubmitField('更新发货单')

class SearchDeliveryForm(FlaskForm):
    delivery_id = StringField('发货单编号')
    sales_order_id = StringField('销售订单编号')
    start_date = DateField('开始日期')
    end_date = DateField('结束日期')
    status = SelectField('状态', choices=[
        ('', '全部'), 
        ('已创建', '已创建'), 
        ('已拣货', '已拣货'), 
        ('已过账', '已过账'),
        ('已取消', '已取消')
    ])
    submit = SubmitField('查询')

class StockSearchForm(FlaskForm):
    material_id = StringField('物料编号')
    start_date = DateField('开始日期')
    end_date = DateField('结束日期')
    delivery_id = StringField('发货单编号')
    warehouse_code = StringField('仓库代码')
    submit = SubmitField('查询')

class DeliveryItemPostForm(FlaskForm):
    material_id = StringField('物料编号', render_kw={'readonly': True})
    planned_quantity = DecimalField('计划数量', render_kw={'readonly': True})
    actual_quantity = DecimalField('实际数量', validators=[DataRequired(), NumberRange(min=0)])
    remarks = StringField('备注')

class PostDeliveryForm(FlaskForm):
    actual_delivery_date = DateField('实际发货日期', validators=[DataRequired()])
    items = FieldList(FormField(DeliveryItemPostForm))
    submit = SubmitField('执行过账')