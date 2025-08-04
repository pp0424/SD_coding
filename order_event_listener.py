import os
import csv
from sqlalchemy import event
from order.models import (
    Inquiry, InquiryItem,
    Quotation, QuotationItem,
    SalesOrder, OrderItem,
    Material
)

def export_table_to_csv(model_class, csv_filename):
    """
    导出指定模型类对应表的数据到 CSV 文件
    """
    from database import db
    folder_path = "Instance"  # ✅ 存到已有的 Instance 文件夹
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, csv_filename)

    columns = [col.name for col in model_class.__table__.columns]
    records = db.session.query(model_class).all()

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in records:
            writer.writerow([getattr(row, col) for col in columns])


def attach_csv_export_listeners():
    """
    绑定所有模型类的插入、更新、删除事件
    """
    model_csv_map = {
        Inquiry: "Inquiry.csv",
        InquiryItem: "InquiryItem.csv",
        Quotation: "Quotation.csv",
        QuotationItem: "QuotationItem.csv",
        SalesOrder: "SalesOrder.csv",
        OrderItem: "OrderItem.csv",
        Material: "Material.csv"
    }

    for model_class, csv_name in model_csv_map.items():
        for action in ["after_insert", "after_update", "after_delete"]:
            event.listen(
                model_class,
                action,
                lambda mapper, connection, target, m=model_class, f=csv_name: export_table_to_csv(m, f)
            )
