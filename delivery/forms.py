# delivery/forms.py
from flask_wtf import FlaskForm, Form
from wtforms import HiddenField, StringField, DateField, SelectField, DecimalField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from wtforms.fields import FieldList, FormField

class DeliveryItemForm(FlaskForm):
    sales_order_item_no = HiddenField()
    material_id = StringField("物料编号", validators=[DataRequired()])
    material_desc = StringField("物料描述", validators=[Optional()])
    storage_location = StringField("存储位置", validators=[Optional()])
    order_quantity = DecimalField("订单数量", validators=[Optional()])
    unshipped_quantity = DecimalField("未发数量", validators=[Optional()])
    planned_delivery_quantity = DecimalField("本次拣货数量", validators=[Optional()])
    base_unit = StringField("基本单位", validators=[Optional()])
    unit = StringField("单位", validators=[Optional()])

class CreateDeliveryForm(FlaskForm):
    sales_order_id = StringField('销售订单编号', validators=[DataRequired()])
    required_delivery_date=DateField("交货日期", validators=[DataRequired()],format='%Y-%m-%d')
    order_date = DateField("订单日期", validators=[DataRequired()],format='%Y-%m-%d')
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()])
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    items = FieldList(FormField(DeliveryItemForm), min_entries=0)
    remarks = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('创建发货单')

class DeliveryItemEditForm(FlaskForm):
    planned_delivery_quantity = DecimalField('计划发货数量', validators=[DataRequired(), NumberRange(min=0)])

class EditDeliveryForm(FlaskForm):
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()],format='%Y-%m-%d')
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()])
    items = FieldList(FormField(DeliveryItemEditForm), min_entries=0)
    submit = SubmitField('保存')

class SearchDeliveryForm(FlaskForm):
    delivery_id = StringField('发货单编号', validators=[Optional()])
    sales_order_id = StringField('销售订单编号', validators=[Optional()])
    status = SelectField('状态', choices=[('', '全部'), ('已创建', '已创建'), ('已拣货', '已拣货'), ('已过账', '已过账'), ('已取消','已取消')], validators=[Optional()], default='')
    start_date = DateField('起始日期', validators=[Optional()],format='%Y-%m-%d')
    end_date = DateField('结束日期', validators=[Optional()],format='%Y-%m-%d')
    submit = SubmitField('查询')

class SearchPickingTaskForm(FlaskForm):
    delivery_id = StringField('发货单号', validators=[Optional()])
    sales_order_id = StringField('销售订单号', validators=[Optional()])
    status = SelectField('状态', choices=[
        ('', '-- 全部状态 --'),
        ('待拣货', '待拣货'),
        ('已完成', '已完成'),
        ('已取消', '已取消')
    ], validators=[Optional()])
    start_date = DateField('开始日期', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('结束日期', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('查询')

class DeliveryItemPostForm(Form):
    item_no = HiddenField()                # 行号（Hidden）
    material_id = HiddenField()            # 物料号（Hidden）
    planned_quantity = DecimalField('计划数量', places=4, validators=[Optional()])
    actual_quantity = DecimalField('实际发货数量', places=4, validators=[Optional()])
    unit = StringField('单位', validators=[Optional()])


class PostDeliveryForm(FlaskForm):
    items = FieldList(FormField(DeliveryItemPostForm), min_entries=0)
    remarks = TextAreaField('过账备注', validators=[Optional()])
    submit = SubmitField('确认过账')

class CancelPickingForm(FlaskForm):
    cancel_reason = TextAreaField('取消原因', validators=[DataRequired()])
    submit = SubmitField('确认取消')


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
    start_date = DateField('起始日期', validators=[Optional()],format='%Y-%m-%d')
    end_date = DateField('结束日期', validators=[Optional()],format='%Y-%m-%d')
    delivery_id = StringField('发货单编号', validators=[Optional()])
    warehouse_code = StringField('仓库代码', validators=[Optional()])
    movement_type = SelectField('移动类型', choices=[
        ('all', '全部'),
        ('IN', '入库'),
        ('OUT', '出库')
    ], validators=[Optional()])
    submit = SubmitField('查询')

class ShipmentConfirmForm(FlaskForm):
    confirm = SubmitField('确认发货')


class SearchInventoryMovementForm(FlaskForm):
    material_id = StringField('物料编码', validators=[Optional()])
    start_date = DateField('开始日期', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('结束日期', format='%Y-%m-%d', validators=[Optional()])
    delivery_id = StringField('参考单号', validators=[Optional()])
    warehouse_code = StringField('仓库编码', validators=[Optional()])
    movement_type = SelectField(
        '变动类型',
        choices=[
            ('all', '全部'),
            ('初始化', '初始化'),
            ('发货', '发货'),
            ('拣货占用', '拣货占用'),
            ('释放分配', '释放分配'),
            ('其他', '其他')
        ],
        default='all')