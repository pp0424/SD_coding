# delivery/forms.py
from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, DateField, SelectField, DecimalField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from wtforms.fields import FieldList, FormField

class DeliveryItemForm(FlaskForm):
    sales_order_item_no = HiddenField()
    material_id = StringField('物料编号', validators=[DataRequired()])
    material_desc = StringField('物料描述', render_kw={'readonly': True})
    order_quantity = DecimalField('订单数量', render_kw={'readonly': True})
    unshipped_quantity = DecimalField('未发货数量', render_kw={'readonly': True})
    planned_delivery_quantity = DecimalField('计划发货数量', validators=[DataRequired(), NumberRange(min=0)])

class CreateDeliveryForm(FlaskForm):
    sales_order_id = StringField('销售订单编号', validators=[DataRequired()])
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    items = FieldList(FormField(DeliveryItemForm), min_entries=0)
    remarks = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('创建发货单')

class DeliveryItemEditForm(FlaskForm):
    planned_delivery_quantity = DecimalField('计划发货数量', validators=[DataRequired(), NumberRange(min=0)])

class EditDeliveryForm(FlaskForm):
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()])
    items = FieldList(FormField(DeliveryItemEditForm), min_entries=0)
    submit = SubmitField('保存')

class SearchDeliveryForm(FlaskForm):
    delivery_id = StringField('发货单编号', validators=[Optional()])
    sales_order_id = StringField('销售订单编号', validators=[Optional()])
    status = SelectField('状态', choices=[('', '全部'), ('已创建', '已创建'), ('已拣货', '已拣货'), ('已过账', '已过账'), ('已取消','已取消')], validators=[Optional()], default='')
    start_date = DateField('起始日期', validators=[Optional()])
    end_date = DateField('结束日期', validators=[Optional()])
    submit = SubmitField('查询')

class DeliveryItemPostForm(FlaskForm):
    material_id = StringField('物料编号', render_kw={'readonly': True})
    planned_quantity = DecimalField('计划数量', render_kw={'readonly': True})
    actual_quantity = DecimalField('实际发货数量', validators=[DataRequired(), NumberRange(min=0)])

class PostDeliveryForm(FlaskForm):
    actual_delivery_date = DateField('实际发货日期', validators=[DataRequired()])
    items = FieldList(FormField(DeliveryItemPostForm), min_entries=0)
    remarks = TextAreaField('过账备注', validators=[Optional()])
    submit = SubmitField('确认过账')

class CancelDeliveryForm(FlaskForm):
    cancel_reason = TextAreaField('取消原因', validators=[DataRequired()], render_kw={'rows': 3, 'placeholder': '请输入取消原因'})
    submit = SubmitField('确认取消')

class ChangeStatusForm(FlaskForm):
    new_status = SelectField('新状态', choices=[
        ('已拣货', '已拣货'),
        ('已取消', '已取消')
    ], validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()], render_kw={'rows': 2, 'placeholder': '状态变更备注（可选）'})
    submit = SubmitField('确认变更')

class SearchInventoryMovementForm(FlaskForm):
    material_id = StringField('物料编号', validators=[Optional()])
    start_date = DateField('起始日期', validators=[Optional()])
    end_date = DateField('结束日期', validators=[Optional()])
    delivery_id = StringField('发货单编号', validators=[Optional()])
    warehouse_code = StringField('仓库代码', validators=[Optional()])
    movement_type = SelectField('移动类型', choices=[
        ('all', '全部'),
        ('IN', '入库'),
        ('OUT', '出库')
    ], validators=[Optional()])
    submit = SubmitField('查询')
