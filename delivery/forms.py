# delivery/forms.py
from flask_wtf import FlaskForm, Form
from wtforms import HiddenField, StringField, DateField, SelectField, DecimalField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
from wtforms.fields import FieldList, FormField


class DeliveryItemForm(FlaskForm):
    """
    发货单行项目表单
    - 用于创建发货单时，录入每一行发货物料的信息
    - 含物料编号、描述、存储位置、订单数量、未发数量、本次计划发货数量、单位等
    """
    sales_order_item_no = HiddenField()  # 对应销售订单行ID（隐藏）
    material_id = StringField("物料编号", validators=[DataRequired(message="物料编号不能为空")])
    material_desc = StringField("物料描述", validators=[Optional()])
    storage_location = StringField("存储位置", validators=[Optional()])
    order_quantity = DecimalField("订单数量", validators=[Optional()])       # 来源于销售订单
    unshipped_quantity = DecimalField("未发数量", validators=[Optional()])   # 自动计算
    planned_delivery_quantity = DecimalField(
        "本次拣货数量",
        validators=[Optional()],
        description="本次实际要发货的数量，不能超过未发数量"
    )
    base_unit = StringField("基本单位", validators=[Optional()])
    unit = StringField("单位", validators=[Optional()])


class CreateDeliveryForm(FlaskForm):
    """
    创建发货单表单
    - 包含发货单主信息（订单号、日期、仓库等）
    - 可添加多个发货行项目（DeliveryItemForm）
    """
    sales_order_id = StringField('销售订单编号', validators=[DataRequired(message="必须关联销售订单")])
    required_delivery_date = DateField("交货日期", validators=[DataRequired()], format='%Y-%m-%d')
    order_date = DateField("订单日期", validators=[DataRequired()], format='%Y-%m-%d')
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()], format='%Y-%m-%d')
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired(message="必须指定发货仓库")])
    items = FieldList(FormField(DeliveryItemForm), min_entries=0, description="需要发货的商品行项目")
    remarks = TextAreaField('备注', validators=[Optional()], render_kw={"placeholder": "可填写特殊发货要求"})
    submit = SubmitField('创建发货单')


class DeliveryItemEditForm(FlaskForm):
    """
    发货单行项目编辑表单
    - 仅允许修改计划发货数量
    - 数量必须 >= 0
    """
    planned_delivery_quantity = DecimalField(
        '计划发货数量',
        validators=[
            DataRequired(message="必须填写发货数量"),
            NumberRange(min=0, message="发货数量不能为负数")
        ],
        description="不能超过未发数量"
    )


class EditDeliveryForm(FlaskForm):
    """
    发货单编辑表单
    - 修改未发货的发货单信息
    - 可调整预计发货日期、仓库、备注、行项目数量
    """
    expected_delivery_date = DateField('预计发货日期', validators=[DataRequired()], format='%Y-%m-%d')
    warehouse_code = StringField('发货仓库代码', validators=[DataRequired(message="必须指定发货仓库")])
    remarks = TextAreaField('备注', validators=[Optional()])
    items = FieldList(FormField(DeliveryItemEditForm), min_entries=0, description="各物料的计划发货数量")
    submit = SubmitField('保存')


class SearchDeliveryForm(FlaskForm):
    """
    发货单搜索表单
    - 根据单号、订单号、状态、日期范围筛选
    """
    delivery_id = StringField('发货单编号', validators=[Optional()], render_kw={"placeholder": "输入发货单号"})
    sales_order_id = StringField('销售订单编号', validators=[Optional()], render_kw={"placeholder": "输入关联的销售订单号"})
    status = SelectField(
        '状态',
        choices=[
            ('', '全部'),
            ('已创建', '已创建'),
            ('已拣货', '已拣货'),
            ('已过账', '已过账'),
            ('已取消', '已取消')
        ],
        validators=[Optional()],
        default=''
    )
    start_date = DateField('起始日期', validators=[Optional()], format='%Y-%m-%d')
    end_date = DateField('结束日期', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('查询')


class SearchPickingTaskForm(FlaskForm):
    """拣货任务搜索表单"""
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
    """
    发货过账行项目表单（子表）
    - 用于确认实际发货数量
    """
    item_no = HiddenField()         # 行号
    material_id = HiddenField()     # 物料编号
    planned_quantity = DecimalField('计划数量', places=4, validators=[Optional()])
    actual_quantity = DecimalField('实际发货数量', places=4, validators=[Optional()])
    unit = StringField('单位', validators=[Optional()])


class PostDeliveryForm(FlaskForm):
    """
    发货过账表单
    - 显示计划数量并输入实际发货数量
    - 允许添加备注
    """
    items = FieldList(FormField(DeliveryItemPostForm), min_entries=0, description="确认实际发货数量")
    remarks = TextAreaField('过账备注', validators=[Optional()], render_kw={"placeholder": "输入过账备注信息（如差异原因）"})
    submit = SubmitField('确认过账')


class CancelPickingForm(FlaskForm):
    """取消拣货任务表单"""
    cancel_reason = TextAreaField('取消原因', validators=[DataRequired()])
    submit = SubmitField('确认取消')


class CancelDeliveryForm(FlaskForm):
    """取消发货单表单"""
    cancel_reason = TextAreaField('取消原因', validators=[DataRequired()], render_kw={'rows': 3, 'placeholder': '请输入取消原因'})
    submit = SubmitField('确认取消')


class ChangeStatusForm(FlaskForm):
    """发货单状态变更表单"""
    new_status = SelectField('新状态', choices=[
        ('已拣货', '已拣货'),
        ('已取消', '已取消')
    ], validators=[DataRequired()])
    remarks = TextAreaField('备注', validators=[Optional()], render_kw={'rows': 2, 'placeholder': '状态变更备注（可选）'})
    submit = SubmitField('确认变更')


class SearchInventoryMovementForm(FlaskForm):
    """
    库存移动记录搜索表单
    - 根据物料、仓库、时间、发货单号、变动类型过滤
    """
    material_id = SelectField('物料编号', validators=[Optional()], coerce=str, choices=[])
    warehouse_code = SelectField('仓库代码', validators=[Optional()], coerce=str, choices=[])
    start_date = DateField('起始日期', validators=[Optional()], format='%Y-%m-%d')
    end_date = DateField('结束日期', validators=[Optional()], format='%Y-%m-%d')
    delivery_id = StringField('发货单编号', validators=[Optional()])
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
        default='all'
    )
    submit = SubmitField('查询')


class ShipmentConfirmForm(FlaskForm):
    """确认发货按钮表单（用于提交确认操作）"""
    confirm = SubmitField('确认发货')


class SearchInventoryForm(FlaskForm):
    """库存查询表单"""
    material_id = StringField('物料编号', validators=[Optional()])  # 物料ID查询条件
    description = StringField('物料描述', validators=[Optional()])
    storage_location = StringField('存储位置', validators=[Optional()])
    submit = SubmitField('搜索')