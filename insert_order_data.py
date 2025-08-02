import csv
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker('zh_CN')

NUM_RECORDS = 1000

# 预生成基础主数据
materials = [f"MAT-{10000+i}" for i in range(1, 51)]
customers = [f"CUST-CN{str(i).zfill(5)}" for i in range(1, 21)]
salespersons = [f"SALES-{str(i).zfill(3)}" for i in range(1, 11)]
units = ['个', '箱', '件', '套']

today = datetime(2025, 7, 1)

def write_csv(filename, fieldnames, rows):
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# 1. Material
material_data = []
for mid in materials:
    material_data.append({
        'material_id': mid,
        'description': fake.word() + fake.random_element(['耳机', '显示器', '鼠标', '键盘']),
        'base_unit': random.choice(units),
        'storage_location': f"WH-{fake.province()}",
        'available_stock': random.randint(100, 10000)
    })
write_csv('instance\Material.csv', list(material_data[0].keys()), material_data)

# 2. Inquiry
inquiry_data = []
inquiry_ids = []
for i in range(NUM_RECORDS):
    iid = f"INQ-202507{str(i//3+1).zfill(2)}-{str(i%3+1).zfill(3)}"
    inquiry_ids.append(iid)
    inquiry_data.append({
        'inquiry_id': iid,
        'customer_id': random.choice(customers),
        'inquiry_date': (today + timedelta(days=i)).strftime('%Y-%m-%d'),
        'expected_delivery_date': (today + timedelta(days=i+10)).strftime('%Y-%m-%d'),
        'status': random.choice(['草稿', '已评审']),
        'expected_total_amount': random.randint(10000, 80000),
        'salesperson_id': random.choice(salespersons),
        'remarks': fake.sentence(nb_words=5)
    })
write_csv('instance\Inquiry.csv', list(inquiry_data[0].keys()), inquiry_data)

# 3. InquiryItem
inquiry_item_data = []
for iid in inquiry_ids:
    for item_no in range(1, 4):  # 每个询价单3条
        mat = random.choice(materials)
        inquiry_item_data.append({
            'inquiry_id': iid,
            'item_no': item_no,
            'material_id': mat,
            'inquiry_quantity': random.randint(10, 500),
            'unit': random.choice(units),
            'expected_unit_price': round(random.uniform(10, 500), 2),
            'item_remarks': fake.word()
        })
write_csv('instance\InquiryItem.csv', list(inquiry_item_data[0].keys()), inquiry_item_data)

# 4. Quotation
quotation_data = []
quotation_ids = []
for i, iid in enumerate(inquiry_ids):
    qid = iid.replace('INQ', 'QUO')
    quotation_ids.append(qid)
    quotation_data.append({
        'quotation_id': qid,
        'customer_id': inquiry_data[i]['customer_id'],
        'inquiry_id': iid,
        'quotation_date': (today + timedelta(days=i+1)).strftime('%Y-%m-%d'),
        'valid_until_date': (today + timedelta(days=i+30)).strftime('%Y-%m-%d'),
        'status': random.choice(['草稿', '已发送']),
        'total_amount': random.randint(15000, 90000),
        'salesperson_id': inquiry_data[i]['salesperson_id'],
        'remarks': fake.sentence()
    })
write_csv('instance\Quotation.csv', list(quotation_data[0].keys()), quotation_data)

# 5. QuotationItem
quotation_item_data = []
for i, qid in enumerate(quotation_ids):
    for item_no in range(1, 4):
        mat = random.choice(materials)
        price = round(random.uniform(50, 300), 2)
        qty = random.randint(5, 200)
        quotation_item_data.append({
            'quotation_id': qid,
            'item_no': item_no,
            'inquiry_item_id': f"{inquiry_ids[i]}-{item_no}",
            'material_id': mat,
            'quotation_quantity': qty,
            'unit_price': price,
            'discount_rate': round(random.uniform(0, 0.15), 2),
            'item_amount': round(price * qty, 2),
            'unit': random.choice(units)
        })
write_csv('instance\QuotationItem.csv', list(quotation_item_data[0].keys()), quotation_item_data)

# 6. SalesOrder
sales_order_data = []
order_ids = []
for i, qid in enumerate(quotation_ids[:NUM_RECORDS]):
    oid = qid.replace("QUO", "SO")
    order_ids.append(oid)
    sales_order_data.append({
        'sales_order_id': oid,
        'customer_id': quotation_data[i]['customer_id'],
        'quotation_id': qid,
        'order_date': (today + timedelta(days=i+2)).strftime('%Y-%m-%d'),
        'required_delivery_date': (today + timedelta(days=i+10)).strftime('%Y-%m-%d'),
        'status': random.choice(['草稿','已创建']),
        'total_amount': quotation_data[i]['total_amount'],
        'credit_check_result': random.choice(['通过', '待审核']),
        'remarks': fake.sentence()
    })
write_csv('instance\SalesOrder.csv', list(sales_order_data[0].keys()), sales_order_data)

# 7. OrderItem
order_item_data = []
for i, oid in enumerate(order_ids):
    for item_no in range(1, 4):
        qty = random.randint(10, 200)
        price = round(random.uniform(30, 250), 2)
        order_item_data.append({
            'sales_order_id': oid,
            'item_no': item_no,
            'material_id': random.choice(materials),
            'order_quantity': qty,
            'sales_unit_price': price,
            'shipped_quantity': 0,
            'unshipped_quantity': qty,
            'item_amount': round(qty * price, 2),
            'unit': random.choice(units)
        })
write_csv('instance\OrderItem.csv', list(order_item_data[0].keys()), order_item_data)

print("✅ 所有CSV文件已生成！")
