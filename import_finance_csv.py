import csv
from datetime import datetime
from decimal import Decimal

from app import app, db  # ❗项目实际的 Flask 应用上下文
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment  # 实际模型

#财务模块数据导入脚本

def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期格式: {date_str}")

def load_csv_to_model(file_path, model, preprocess_row=None):
    with open(file_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        instances = []
        for row in reader:
            if preprocess_row:
                row = preprocess_row(row)
            instance = model(**row)
            instances.append(instance)
        db.session.bulk_save_objects(instances)
        db.session.commit()
        print(f"✅ 导入 {file_path} 成功，共 {len(instances)} 条记录。")

def import_all():
    with app.app_context():
        # 先清空表，保证数据同步
        db.session.query(InvoiceItem).delete()
        db.session.query(CustomerPayment).delete()
        db.session.query(CustomerInvoice).delete()
        db.session.commit()

        # 1. 导入客户发票表
        load_csv_to_model('instance/customer_invoice.csv', CustomerInvoice, lambda r: {
            'invoice_id': r['invoice_id'],
            'customer_id': r['customer_id'],
            'sales_order_id': r['sales_order_id'],
            'delivery_note_ids': r['delivery_note_ids'],
            'invoice_date': parse_date(r['invoice_date']),
            'payment_deadline': parse_date(r['payment_deadline']),
            'total_amount': Decimal(r['total_amount']),
            'tax_amount': Decimal(r['tax_amount']),
            'payment_status': r['payment_status'],
            'remarks': r['remarks']
        })

        # 2. 导入发票明细表
        load_csv_to_model('instance/invoice_item.csv', InvoiceItem, lambda r: {
            'invoice_id': r['invoice_id'],
            'item_no': int(r['item_no']),
            'delivery_item_id': r['delivery_item_id'],
            'sales_order_item_id': r['sales_order_item_id'],
            'material_id': r['material_id'],
            'invoiced_quantity': Decimal(r['invoiced_quantity']),
            'unit_price': Decimal(r['unit_price']),
            'tax_amount': Decimal(r['tax_amount']),
            'item_amount': Decimal(r['item_amount']),
            'unit': r['unit']
        })

        # 3. 导入收款记录表
        load_csv_to_model('instance/customer_payment.csv', CustomerPayment, lambda r: {
            'payment_id': r['payment_id'],
            'customer_id': r['customer_id'],
            'invoice_id': r['invoice_id'],
            'payment_date': parse_date(r['payment_date']),
            'payment_amount': Decimal(r['payment_amount']),
            'payment_method': r['payment_method'],
            'write_off_amount': Decimal(r['write_off_amount']),
            'status': r['status'],
            'remarks': r['remarks']
        })

if __name__ == '__main__':
    import_all()
