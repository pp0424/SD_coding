from flask import Blueprint, render_template, request, redirect, url_for, flash
from .models import Customer, ContactPerson, BPRelationship
from .forms import CustomerForm, ContactPersonForm, BPRelationshipForm, CustomerSearchForm, ContactSearchForm, BPRelationshipSearchForm
from database import db
from datetime import datetime

bp = Blueprint('customer', __name__, url_prefix='/customer')


def generate_customer_id():
    """生成客户编号"""
    last_customer = Customer.query.order_by(Customer.customer_id.desc()).first()
    if last_customer:
        # 从 "CUST-CN00001" 中提取数字部分 "00001"
        last_num = int(last_customer.customer_id.split('-')[-1][2:])  # 去掉 "CN" 前缀
        new_num = last_num + 1
    else:
        new_num = 1
    return f"CUST-CN{new_num:05d}"


def generate_contact_id():
    """生成联系人ID"""
    last_contact = ContactPerson.query.order_by(ContactPerson.contact_id.desc()).first()
    if last_contact:
        # 从 "CONT-00001" 中提取数字部分 "00001"
        last_num = int(last_contact.contact_id.split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"CONT-{new_num:05d}"


def generate_relationship_id():
    """生成业务伙伴关系ID"""
    last_relationship = BPRelationship.query.order_by(BPRelationship.relationship_id.desc()).first()
    if last_relationship:
        # 从 "BPREL-00001" 中提取数字部分 "00001"
        last_num = int(last_relationship.relationship_id.split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"BPREL-{new_num:05d}"


# 客户管理主页
@bp.route('/')
def index():
    return render_template('customer/index.html')


# 客户列表和搜索
@bp.route('/customers')
def list_customers():
    search_form = CustomerSearchForm()
    customers = Customer.query.all()
    return render_template('customer/customer_list.html', customers=customers, search_form=search_form)


@bp.route('/customers/search', methods=['POST'])
def search_customers():
    search_form = CustomerSearchForm()
    customers = []

    if search_form.validate_on_submit():
        search_type = search_form.search_type.data
        search_value = search_form.search_value.data

        if search_value:
            if search_type == 'customer_id':
                customers = Customer.query.filter(Customer.customer_id.like(f'%{search_value}%')).all()
            elif search_type == 'customer_name':
                customers = Customer.query.filter(Customer.customer_name.like(f'%{search_value}%')).all()
            elif search_type == 'sales_region_code':
                customers = Customer.query.filter(Customer.sales_region_code.like(f'%{search_value}%')).all()
            elif search_type == 'status':
                customers = Customer.query.filter(Customer.status == search_value).all()
        else:
            customers = Customer.query.all()

    return render_template('customer/customer_list.html', customers=customers, search_form=search_form)


# 创建客户
@bp.route('/customers/create', methods=['GET', 'POST'])
def create_customer():
    form = CustomerForm()

    if form.validate_on_submit():
        customer_id = generate_customer_id()
        new_customer = Customer(
            customer_id=customer_id,
            customer_name=form.customer_name.data,
            customer_type=form.customer_type.data,
            address=form.address.data,
            phone=form.phone.data,
            email=form.email.data,
            credit_limit=form.credit_limit.data or 0,
            payment_terms_code=form.payment_terms_code.data,
            sales_region_code=form.sales_region_code.data,
            status=form.status.data
        )

        try:
            db.session.add(new_customer)
            db.session.commit()
            flash('客户创建成功！', 'success')
            return redirect(url_for('customer.list_customers'))
        except Exception as e:
            db.session.rollback()
            flash('客户创建失败，请检查输入信息！', 'error')

    return render_template('customer/customer_form.html', form=form, title='创建客户')


# 查看客户详情
@bp.route('/customers/<customer_id>')
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    contacts = ContactPerson.query.filter_by(customer_id=customer_id).all()
    relationships = BPRelationship.query.filter_by(main_customer_id=customer_id).all()
    return render_template('customer/customer_detail.html',
                           customer=customer, contacts=contacts, relationships=relationships)


# 编辑客户
@bp.route('/customers/<customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer)

    if form.validate_on_submit():
        customer.customer_name = form.customer_name.data
        customer.customer_type = form.customer_type.data
        customer.address = form.address.data
        customer.phone = form.phone.data
        customer.email = form.email.data
        customer.credit_limit = form.credit_limit.data or 0
        customer.payment_terms_code = form.payment_terms_code.data
        customer.sales_region_code = form.sales_region_code.data
        customer.status = form.status.data

        try:
            db.session.commit()
            flash('客户信息更新成功！', 'success')
            return redirect(url_for('customer.view_customer', customer_id=customer_id))
        except Exception as e:
            db.session.rollback()
            flash('客户信息更新失败！', 'error')

    return render_template('customer/customer_form.html', form=form, title='编辑客户', customer=customer)

# 删除客户
@bp.route('/customers/<customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    try:
        # 删除关联的联系人和业务伙伴关系（由于设置了cascade，会自动删除）
        db.session.delete(customer)
        db.session.commit()
        flash('客户删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash('客户删除失败，可能存在关联数据！', 'error')

    return redirect(url_for('customer.list_customers'))


# 联系人管理
@bp.route('/contacts')
def list_contacts():
    search_form = ContactSearchForm()
    contacts = ContactPerson.query.all()
    return render_template('customer/contact_list.html', contacts=contacts, search_form=search_form)


@bp.route('/contacts/search', methods=['POST'])
def search_contacts():
    search_form = ContactSearchForm()
    contacts = []

    if search_form.validate_on_submit():
        search_type = search_form.search_type.data
        search_value = search_form.search_value.data

        if search_value:
            if search_type == 'customer_id':
                contacts = ContactPerson.query.filter(ContactPerson.customer_id.like(f'%{search_value}%')).all()
            elif search_type == 'first_name':
                contacts = ContactPerson.query.filter(ContactPerson.first_name.like(f'%{search_value}%')).all()
            elif search_type == 'last_name':
                contacts = ContactPerson.query.filter(ContactPerson.last_name.like(f'%{search_value}%')).all()
            elif search_type == 'position':
                contacts = ContactPerson.query.filter(ContactPerson.position.like(f'%{search_value}%')).all()
        else:
            contacts = ContactPerson.query.all()

    return render_template('customer/contact_list.html', contacts=contacts, search_form=search_form)


# 创建联系人
@bp.route('/contacts/create', methods=['GET', 'POST'])
def create_contact():
    form = ContactPersonForm()

    # 填充客户选择列表
    customers = Customer.query.all()
    form.customer_id.choices = [(c.customer_id, f"{c.customer_id} - {c.customer_name}") for c in customers]

    # 如果URL中有customer_id参数，预选该客户
    if request.method == 'GET' and 'customer_id' in request.args:
        form.customer_id.data = request.args.get('customer_id')

    if form.validate_on_submit():
        # 处理国家/语言字段
        country_language = form.country_language.data
        if country_language == '其他' and form.country_language_other.data:
            country_language = form.country_language_other.data

        contact_id = generate_contact_id()
        new_contact = ContactPerson(
            contact_id=contact_id,
            customer_id=form.customer_id.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            country_language=country_language,
            contact_info=form.contact_info.data,
            position=form.position.data,
            status=form.status.data
        )

        try:
            db.session.add(new_contact)
            db.session.commit()
            flash('联系人创建成功！', 'success')
            return redirect(url_for('customer.list_contacts'))
        except Exception as e:
            db.session.rollback()
            flash('联系人创建失败！', 'error')

    return render_template('customer/contact_form.html', form=form, title='创建联系人')


# 编辑联系人
@bp.route('/contacts/<contact_id>/edit', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact = ContactPerson.query.get_or_404(contact_id)
    form = ContactPersonForm(obj=contact)

    # 填充客户选择列表
    customers = Customer.query.all()
    form.customer_id.choices = [(c.customer_id, f"{c.customer_id} - {c.customer_name}") for c in customers]

    # 处理国家/语言字段的初始化
    if request.method == 'GET':
        predefined_choices = [choice[0] for choice in form.country_language.choices if choice[0] != '其他']
        if contact.country_language and contact.country_language not in predefined_choices:
            # 如果当前值不在预定义选项中，设置为"其他"
            form.country_language.data = '其他'
            form.country_language_other.data = contact.country_language

    if form.validate_on_submit():
        # 处理国家/语言字段
        country_language = form.country_language.data
        if country_language == '其他' and form.country_language_other.data:
            country_language = form.country_language_other.data

        contact.customer_id = form.customer_id.data
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.country_language = country_language
        contact.contact_info = form.contact_info.data
        contact.position = form.position.data
        contact.status = form.status.data

        try:
            db.session.commit()
            flash('联系人信息更新成功！', 'success')
            return redirect(url_for('customer.list_contacts'))
        except Exception as e:
            db.session.rollback()
            flash('联系人信息更新失败！', 'error')

    return render_template('customer/contact_form.html', form=form, title='编辑联系人', contact=contact)

# 删除联系人
@bp.route('/contacts/<contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    contact = ContactPerson.query.get_or_404(contact_id)

    try:
        db.session.delete(contact)
        db.session.commit()
        flash('联系人删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash('联系人删除失败！', 'error')

    return redirect(url_for('customer.list_contacts'))


# 业务伙伴关系管理
@bp.route('/relationships')
def list_relationships():
    search_form = BPRelationshipSearchForm()
    relationships = BPRelationship.query.all()
    return render_template('customer/relationship_list.html', relationships=relationships, search_form=search_form)

@bp.route('/relationships/search', methods=['POST'])
def search_relationships():
    search_form = BPRelationshipSearchForm()
    relationships = []

    if search_form.validate_on_submit():
        search_type = search_form.search_type.data
        search_value = search_form.search_value.data

        if search_value:
            if search_type == 'main_customer_id':
                relationships = BPRelationship.query.filter(BPRelationship.main_customer_id.like(f'%{search_value}%')).all()
            elif search_type == 'relationship_type':
                relationships = BPRelationship.query.filter(BPRelationship.relationship_type.like(f'%{search_value}%')).all()
            elif search_type == 'status':
                relationships = BPRelationship.query.filter(BPRelationship.status == search_value).all()
        else:
            relationships = BPRelationship.query.all()

    return render_template('customer/relationship_list.html', relationships=relationships, search_form=search_form)


# 创建业务伙伴关系
@bp.route('/relationships/create', methods=['GET', 'POST'])
def create_relationship():
    form = BPRelationshipForm()

    # 填充客户选择列表
    customers = Customer.query.all()
    form.main_customer_id.choices = [(c.customer_id, f"{c.customer_id} - {c.customer_name}") for c in customers]

    # 初始化联系人选择列表
    if request.method == 'GET':
        # GET请求：初始化或从URL参数预选
        if 'customer_id' in request.args:
            customer_id = request.args.get('customer_id')
            form.main_customer_id.data = customer_id
            # 填充该客户的联系人列表
            contacts = ContactPerson.query.filter_by(customer_id=customer_id).all()
            form.contact_id.choices = [('', '无联系人')] + [(c.contact_id, f"{c.first_name} {c.last_name} - {c.position or '无职位'}") for c in contacts]
        else:
            # 默认选择第一个客户的联系人
            if customers:
                first_customer = customers[0]
                contacts = ContactPerson.query.filter_by(customer_id=first_customer.customer_id).all()
                form.contact_id.choices = [('', '无联系人')] + [(c.contact_id, f"{c.first_name} {c.last_name} - {c.position or '无职位'}") for c in contacts]
            else:
                form.contact_id.choices = [('', '无客户')]
    else:
        # POST请求：根据提交的客户ID设置联系人选择列表
        if form.main_customer_id.data:
            contacts = ContactPerson.query.filter_by(customer_id=form.main_customer_id.data).all()
            form.contact_id.choices = [('', '无联系人')] + [(c.contact_id, f"{c.first_name} {c.last_name} - {c.position or '无职位'}") for c in contacts]
        else:
            form.contact_id.choices = [('', '请先选择客户')]

    if form.validate_on_submit():

        relationship_id = generate_relationship_id()
        contact_id = form.contact_id.data if form.contact_id.data else None
        new_relationship = BPRelationship(
            relationship_id=relationship_id,
            main_customer_id=form.main_customer_id.data,
            contact_id=contact_id,
            relationship_type=form.relationship_type.data,
            description=form.description.data,
            effective_date=form.effective_date.data,
            expiry_date=form.expiry_date.data,
            status=form.status.data
        )

        try:
            db.session.add(new_relationship)
            db.session.commit()
            flash('业务伙伴关系创建成功！', 'success')
            return redirect(url_for('customer.list_relationships'))
        except Exception as e:
            db.session.rollback()
            flash('业务伙伴关系创建失败！', 'error')

    return render_template('customer/relationship_form.html', form=form, title='创建业务伙伴关系')


# 编辑业务伙伴关系
@bp.route('/relationships/<relationship_id>/edit', methods=['GET', 'POST'])
def edit_relationship(relationship_id):
    relationship = BPRelationship.query.get_or_404(relationship_id)

    # 不使用obj=relationship，手动设置字段值以确保正确处理
    form = BPRelationshipForm()

    # 填充客户选择列表
    customers = Customer.query.all()
    form.main_customer_id.choices = [(c.customer_id, f"{c.customer_id} - {c.customer_name}") for c in customers]

    # 填充联系人选择列表并设置默认值
    if request.method == 'GET':
        # 手动设置所有字段的值
        form.main_customer_id.data = relationship.main_customer_id
        form.relationship_type.data = relationship.relationship_type
        form.description.data = relationship.description
        form.effective_date.data = relationship.effective_date
        form.expiry_date.data = relationship.expiry_date
        form.status.data = relationship.status

        # GET请求：根据现有关系设置联系人列表
        if relationship.main_customer_id:
            contacts = ContactPerson.query.filter_by(customer_id=relationship.main_customer_id).all()
            form.contact_id.choices = [('', '无联系人')] + [(c.contact_id, f"{c.first_name} {c.last_name} - {c.position or '无职位'}") for c in contacts]
            # 设置当前联系人的值
            form.contact_id.data = relationship.contact_id or ''
        else:
            form.contact_id.choices = [('', '请先选择客户')]
            form.contact_id.data = ''
    else:
        # POST请求：根据提交的客户ID设置联系人选择列表
        if form.main_customer_id.data:
            contacts = ContactPerson.query.filter_by(customer_id=form.main_customer_id.data).all()
            form.contact_id.choices = [('', '无联系人')] + [(c.contact_id, f"{c.first_name} {c.last_name} - {c.position or '无职位'}") for c in contacts]
        else:
            form.contact_id.choices = [('', '请先选择客户')]

    if form.validate_on_submit():
        relationship.main_customer_id = form.main_customer_id.data
        relationship.contact_id = form.contact_id.data if form.contact_id.data else None
        relationship.relationship_type = form.relationship_type.data
        relationship.description = form.description.data
        relationship.effective_date = form.effective_date.data
        relationship.expiry_date = form.expiry_date.data
        relationship.status = form.status.data

        try:
            db.session.commit()
            flash('业务伙伴关系更新成功！', 'success')
            return redirect(url_for('customer.list_relationships'))
        except Exception as e:
            db.session.rollback()
            flash('业务伙伴关系更新失败！', 'error')

    return render_template('customer/relationship_form.html', form=form, title='编辑业务伙伴关系',
                           relationship=relationship)

# 删除业务伙伴关系
@bp.route('/relationships/<relationship_id>/delete', methods=['POST'])
def delete_relationship(relationship_id):
    relationship = BPRelationship.query.get_or_404(relationship_id)

    try:
        db.session.delete(relationship)
        db.session.commit()
        flash('业务伙伴关系删除成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash('业务伙伴关系删除失败！', 'error')

    return redirect(url_for('customer.list_relationships'))

# AJAX接口：根据客户ID获取联系人列表
@bp.route('/api/contacts/<customer_id>')
def get_contacts_by_customer(customer_id):
    from flask import jsonify
    contacts = ContactPerson.query.filter_by(customer_id=customer_id).all()
    contact_list = [{'contact_id': c.contact_id, 'name': f"{c.first_name} {c.last_name} - {c.position or '无职位'}"} for c in contacts]
    return jsonify({'contacts': contact_list})
