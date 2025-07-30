import csv
from datetime import datetime
from decimal import Decimal

from app import app, db  # ❗替换为你项目实际的 Flask 应用上下文
from order.models import Inquiry, InquiryItem, Quotation, QuotationItem, Material, SalesOrder, OrderItem

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
        db.session.query(OrderItem).delete()
        db.session.query(SalesOrder).delete()
        db.session.query(QuotationItem).delete()
        db.session.query(Quotation).delete()
        db.session.query(InquiryItem).delete()
        db.session.query(Inquiry).delete()
        db.session.query(Material).delete()
        db.session.commit()

        # 1. Material
        load_csv_to_model('D:\GIT\SD_coding\instance\Material.csv', Material, lambda r: {
            'material_id': r['material_id'],
            'description': r['description'],
            'base_unit': r['base_unit'],
            'storage_location': r['storage_location'],
            'available_stock': Decimal(r['available_stock'] or 0)
        })

        # 2. Inquiry
        load_csv_to_model('D:\GIT\SD_coding\instance\Inquiry.csv', Inquiry, lambda r: {
            'inquiry_id': r['inquiry_id'],
            'customer_id': r['customer_id'],
            'inquiry_date': parse_date(r['inquiry_date']),
            'expected_delivery_date': parse_date(r['expected_delivery_date']),
            'status': r['status'],
            'expected_total_amount': float(r['expected_total_amount'] or 0),
            'salesperson_id': r['salesperson_id'],
            'remarks': r['remarks']
        })

        # 3. InquiryItem
        load_csv_to_model('D:\GIT\SD_coding\instance\InquiryItem.csv', InquiryItem, lambda r: {
            'inquiry_id': r['inquiry_id'],
            'item_no': int(r['item_no']),
            'material_id': r['material_id'],
            'inquiry_quantity': float(r['inquiry_quantity']),
            'unit': r['unit'],
            'expected_unit_price': float(r['expected_unit_price'] or 0),
            'item_remarks': r['item_remarks']
        })

        # 4. Quotation
        load_csv_to_model('D:\GIT\SD_coding\instance\Quotation.csv', Quotation, lambda r: {
            'quotation_id': r['quotation_id'],
            'customer_id': r['customer_id'],
            'inquiry_id': r['inquiry_id'],
            'quotation_date': parse_date(r['quotation_date']),
            'valid_until_date': parse_date(r['valid_until_date']),
            'status': r['status'],
            'total_amount': float(r['total_amount']),
            'salesperson_id': r['salesperson_id'],
            'remarks': r['remarks']
        })

        # 5. QuotationItem
        load_csv_to_model('D:\GIT\SD_coding\instance\QuotationItem.csv', QuotationItem, lambda r: {
            'quotation_id': r['quotation_id'],
            'item_no': int(r['item_no']),
            'inquiry_item_id': r['inquiry_item_id'],
            'material_id': r['material_id'],
            'quotation_quantity': float(r['quotation_quantity']),
            'unit_price': float(r['unit_price']),
            'discount_rate': float(r['discount_rate'] or 0),
            'item_amount': float(r['item_amount'] or 0),
            'unit': r['unit']
        })

        # 6. SalesOrder
        load_csv_to_model('D:\GIT\SD_coding\instance\SalesOrder.csv', SalesOrder, lambda r: {
            'sales_order_id': r['sales_order_id'],
            'customer_id': r['customer_id'],
            'quotation_id': r['quotation_id'],
            'order_date': parse_date(r['order_date']),
            'required_delivery_date': parse_date(r['required_delivery_date']),
            'status': r['status'],
            'total_amount': Decimal(r['total_amount']),
            'credit_check_result': r['credit_check_result'],
            'remarks': r['remarks']
        })

        # 7. OrderItem
        load_csv_to_model('D:\GIT\SD_coding\instance\OrderItem.csv', OrderItem, lambda r: {
            'sales_order_id': r['sales_order_id'],
            'item_no': int(r['item_no']),
            'material_id': r['material_id'],
            'order_quantity': Decimal(r['order_quantity']),
            'sales_unit_price': Decimal(r['sales_unit_price']),
            'shipped_quantity': Decimal(r['shipped_quantity'] or 0),
            'unshipped_quantity': Decimal(r['unshipped_quantity'] or 0),
            'item_amount': Decimal(r['item_amount'] or 0),
            'unit': r['unit']
        })

if __name__ == '__main__':
    import_all()
