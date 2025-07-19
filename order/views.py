from flask import Blueprint, render_template

order_bp = Blueprint('order', __name__, template_folder='templates')

@order_bp.route('/')
def order_home():
    return render_template('order/index.html')

@order_bp.route('/create-inquiry')
def create_inquiry():
    return render_template('order/create_inquiry.html')

@order_bp.route('/edit-inquiry')
def edit_inquiry():
    return render_template('order/edit_inquiry.html')

@order_bp.route('/query-inquiry')
def query_inquiry():
    return render_template('order/query_inquiry.html')

@order_bp.route('/create-quote')
def create_quote():
    return render_template('order/create_quote.html')

@order_bp.route('/edit-quote')
def edit_quote():
    return render_template('order/edit_quote.html')

@order_bp.route('/query-quote')
def query_quote():
    return render_template('order/query_quote.html')

@order_bp.route('/create-order')
def create_order():
    return render_template('order/create_order.html')

@order_bp.route('/edit-order')
def edit_order():
    return render_template('order/edit_order.html')

@order_bp.route('/query-order')
def query_order():
    return render_template('order/query_order.html')
