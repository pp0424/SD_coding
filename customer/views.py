# views.py for customer module
from flask import Blueprint, render_template, request, redirect, url_for
from .models import Customer
from database import db

bp = Blueprint('customer', __name__, url_prefix='/customer')

@bp.route('/')
def list_customers():
    customers = Customer.query.all()
    return render_template('customer/list.html', customers=customers)


@bp.route('/create', methods=['GET', 'POST'])
def create_customer():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        customer = Customer(name=name, phone=phone)
        db.session.add(customer)
        db.session.commit()
        return redirect(url_for('customer.list_customers'))
    return render_template('customer/create.html')

@bp.route('/<int:id>')
def customer_detail(id):
    customer = Customer.query.get_or_404(id)
    return render_template('customer/detail.html', customer=customer)

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    if request.method == 'POST':
        customer.name = request.form['name']
        customer.phone = request.form['phone']
        db.session.commit()
        return redirect(url_for('customer.list_customers'))
    return render_template('customer/edit.html', customer=customer)


@bp.route('/test')
def test_route():
    return '测试路由成功'
