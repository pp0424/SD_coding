import os
import csv
from sqlalchemy import event
from finance.models import CustomerInvoice, InvoiceItem, CustomerPayment  # 替换为你真实的导入路径

def export_table_to_csv(model_class, csv_filename):
    from database import db  # 替换成你项目中 db session 的导入
    folder_path = "Instance"
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, csv_filename)

    columns = [col.name for col in model_class.__table__.columns]
    records = db.session.query(model_class).all()

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in records:
            writer.writerow([getattr(row, col) for col in columns])

def make_listener(model_class, csv_name):
    def listener(mapper, connection, target):
        export_table_to_csv(model_class, csv_name)
    return listener

def f_attach_csv_export_listeners():
    model_csv_map = {
        CustomerInvoice: "customer_invoice.csv",
        InvoiceItem: "invoice_item.csv",
        CustomerPayment: "customer_payment.csv"
    }

    for model_class, csv_name in model_csv_map.items():
        for action in ["after_insert", "after_update", "after_delete"]:
            event.listen(
                model_class,
                action,
                make_listener(model_class, csv_name)
            )

# 在你的程序初始化或者 app 启动时调用
# attach_csv_export_listeners()
