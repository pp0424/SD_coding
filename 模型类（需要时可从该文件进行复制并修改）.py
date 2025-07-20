
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, Numeric, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Customer(Base):
    __tablename__ = 'customer'
    customer_id = Column(String, primary_key=True)
    customer_name = Column(String, nullable=False)
    customer_type = Column(String, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    credit_limit = Column(Numeric, default=0)
    payment_terms_code = Column(String)
    sales_region_code = Column(String)
    status = Column(String)
    created_at = Column(DateTime)

class ContactPerson(Base):
    __tablename__ = 'contact_person'
    contact_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    country_language = Column(String)
    contact_info = Column(String, nullable=False)
    position = Column(String)
    status = Column(String)

class BPRelationship(Base):
    __tablename__ = 'bprelationship'
    relationship_id = Column(String, primary_key=True)
    main_customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    relationship_type = Column(String, nullable=False)
    description = Column(String)
    effective_date = Column(Date)
    expiry_date = Column(Date)
    status = Column(String)

class Inquiry(Base):
    __tablename__ = 'inquiry'
    inquiry_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    inquiry_date = Column(DateTime, nullable=False)
    expected_delivery_date = Column(Date)
    status = Column(String)
    expected_total_amount = Column(Numeric)
    salesperson_id = Column(String)
    remarks = Column(String)

class InquiryItem(Base):
    __tablename__ = 'inquiry_item'
    inquiry_id = Column(String, ForeignKey('inquiry.inquiry_id'), nullable=False)
    item_no = Column(Integer, nullable=False)
    material_id = Column(String, ForeignKey('material.material_id'), nullable=False)
    inquiry_quantity = Column(Numeric, nullable=False)
    unit = Column(String)
    expected_unit_price = Column(Numeric)
    item_remarks = Column(String)
    __table_args__ = (Index('pk_inquiry_item', 'inquiry_id', 'item_no', unique=True),)

class Quotation(Base):
    __tablename__ = 'quotation'
    quotation_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    inquiry_id = Column(String, ForeignKey('inquiry.inquiry_id'))
    quotation_date = Column(DateTime, nullable=False)
    valid_until_date = Column(DateTime, nullable=False)
    status = Column(String)
    total_amount = Column(Numeric, nullable=False)
    salesperson_id = Column(String)
    remarks = Column(String)

class QuotationItem(Base):
    __tablename__ = 'quotation_item'
    quotation_id = Column(String, ForeignKey('quotation.quotation_id'), nullable=False)
    item_no = Column(Integer, nullable=False)
    inquiry_item_id = Column(String)
    material_id = Column(String, ForeignKey('material.material_id'), nullable=False)
    quotation_quantity = Column(Numeric, nullable=False)
    unit_price = Column(Numeric, nullable=False)
    discount_rate = Column(Numeric, default=0)
    item_amount = Column(Numeric)
    unit = Column(String)
    __table_args__ = (Index('pk_quotation_item', 'quotation_id', 'item_no', unique=True),)

class SalesOrder(Base):
    __tablename__ = 'sales_order'
    sales_order_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    quotation_id = Column(String, ForeignKey('quotation.quotation_id'))
    order_date = Column(DateTime, nullable=False)
    required_delivery_date = Column(Date, nullable=False)
    status = Column(String)
    total_amount = Column(Numeric, nullable=False)
    credit_check_result = Column(String)
    remarks = Column(String)

class OrderItem(Base):
    __tablename__ = 'order_item'
    sales_order_id = Column(String, ForeignKey('sales_order.sales_order_id'), nullable=False)
    item_no = Column(Integer, nullable=False)
    material_id = Column(String, ForeignKey('material.material_id'), nullable=False)
    order_quantity = Column(Numeric, nullable=False)
    sales_unit_price = Column(Numeric, nullable=False)
    shipped_quantity = Column(Numeric)
    unshipped_quantity = Column(Numeric)
    item_amount = Column(Numeric)
    unit = Column(String)
    __table_args__ = (Index('pk_order_item', 'sales_order_id', 'item_no', unique=True),)

class Material(Base):
    __tablename__ = 'material'
    material_id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    base_unit = Column(String, nullable=False)
    storage_location = Column(String, nullable=False)
    available_stock = Column(Numeric)

class DeliveryNote(Base):
    __tablename__ = 'delivery_note'
    delivery_note_id = Column(String, primary_key=True)
    sales_order_id = Column(String, ForeignKey('sales_order.sales_order_id'), nullable=False)
    delivery_date = Column(DateTime, nullable=False)
    warehouse_code = Column(String, nullable=False)
    status = Column(String)
    posted_by = Column(String)
    posted_at = Column(DateTime)
    remarks = Column(String)

class DeliveryItem(Base):
    __tablename__ = 'delivery_item'
    delivery_note_id = Column(String, ForeignKey('delivery_note.delivery_note_id'), nullable=False)
    item_no = Column(Integer, nullable=False)
    sales_order_item_no = Column(Integer, nullable=False)
    material_id = Column(String, ForeignKey('material.material_id'), nullable=False)
    planned_delivery_quantity = Column(Numeric)
    actual_delivery_quantity = Column(Numeric, nullable=False)
    unit = Column(String)
    __table_args__ = (Index('pk_delivery_item', 'delivery_note_id', 'item_no', unique=True),)

class CustomerInvoice(Base):
    __tablename__ = 'customer_invoice'
    invoice_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    sales_order_id = Column(String, ForeignKey('sales_order.sales_order_id'), nullable=False)
    delivery_note_ids = Column(String)
    invoice_date = Column(DateTime, nullable=False)
    payment_deadline = Column(Date, nullable=False)
    total_amount = Column(Numeric, nullable=False)
    tax_amount = Column(Numeric, nullable=False)
    payment_status = Column(String)
    remarks = Column(String)

class InvoiceItem(Base):
    __tablename__ = 'invoice_item'
    invoice_id = Column(String, ForeignKey('customer_invoice.invoice_id'), nullable=False)
    item_no = Column(Integer, nullable=False)
    delivery_item_id = Column(String, nullable=False)
    sales_order_item_id = Column(String, nullable=False)
    material_id = Column(String, ForeignKey('material.material_id'), nullable=False)
    invoiced_quantity = Column(Numeric, nullable=False)
    unit_price = Column(Numeric, nullable=False)
    tax_amount = Column(Numeric)
    item_amount = Column(Numeric)
    unit = Column(String)
    __table_args__ = (Index('pk_invoice_item', 'invoice_id', 'item_no', unique=True),)

class CustomerPayment(Base):
    __tablename__ = 'customer_payment'
    payment_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey('customer.customer_id'), nullable=False)
    invoice_id = Column(String, ForeignKey('customer_invoice.invoice_id'), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    payment_amount = Column(Numeric, nullable=False)
    payment_method = Column(String, nullable=False)
    write_off_amount = Column(Numeric, nullable=False)
    status = Column(String)
    remarks = Column(String)
