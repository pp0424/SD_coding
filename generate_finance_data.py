import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import random
import uuid
import csv
from decimal import Decimal
# 设置随机种子以确保可重现性
np.random.seed(42)
random.seed(42)

# 基础数据配置
CUSTOMERS = ['CUST-CN00011', 'CUST-CN00001', 'CUST-CN00012', 'CUST-CN00005', 'CUST-CN00009', 'CUST-CN00010', 'CUST-CN00007', 'CUST-CN00008']
MATERIALS = ['MTL-A001', 'MTL-A002', 'MTL-B001', 'MTL-B002', 'MTL-C001', 'MTL-C002', 
             'MTL-D001', 'MTL-D002', 'MTL-E001', 'MTL-E002']
UNITS = ['件', '个', 'kg', 'm', 'L', '套', '台', '箱']
PAYMENT_METHODS = ['银行转账', '现金', '支票', '承兑汇票', '信用证']
PAYMENT_STATUS = ['未付款', '部分付款', '已付款']
INVOICE_STATUS = ['未付款', '部分付款', '已付款']

def generate_invoice_id(year, month, sequence):
    """生成发票编号：INV-YYMM + 5位顺序号"""
    return f"INV-{year:02d}{month:02d}{sequence:05d}"

def generate_payment_id(year, month, sequence):
    """生成收款编号：PAY-YYMM + 5位顺序号"""
    return f"PAY-{year:02d}{month:02d}{sequence:05d}"

def generate_order_id():
    """生成订单编号"""
    return f"SO-{random.randint(2024, 2025)}-{random.randint(1000, 9999)}"

def generate_delivery_id():
    """生成发货单编号"""
    return f"DN-{random.randint(2024, 2025)}-{random.randint(1000, 9999)}"

# 生成100条发票数据
print("正在生成客户发票数据...")

invoices = []
invoice_items = []
payments = []

# 生成发票数据
for i in range(100):
    # 随机选择年月（2024年1月至2025年8月）
    if i < 60:  # 前60条设置为2024年的数据
        year = 24
        month = random.randint(1, 12)
    else:  # 后40条设置为2025年的数据
        year = 25
        month = random.randint(1, 8)
    
    # 生成发票基本信息
    invoice_id = generate_invoice_id(year, month, i + 1)
    customer_id = random.choice(CUSTOMERS)
    sales_order_id = generate_order_id()
    delivery_note_ids = generate_delivery_id()
    
    # 生成日期
    invoice_date = datetime(2000 + year, month, random.randint(1, 28))
    payment_deadline = invoice_date + timedelta(days=random.randint(30, 90))
    
    # 生成金额（1000-50000之间）
    base_amount = round(random.uniform(1000, 50000), 2)
    tax_amount = round(base_amount * 0.13, 2)
    total_amount = round(base_amount + tax_amount, 2)
    
    # 随机选择付款状态
    payment_status = random.choice(INVOICE_STATUS)
    
    invoice = {
        'invoice_id': invoice_id,
        'customer_id': customer_id,
        'sales_order_id': sales_order_id,
        'delivery_note_ids': delivery_note_ids,
        'invoice_date': invoice_date.strftime('%Y-%m-%d'),
        'payment_deadline': payment_deadline.strftime('%Y-%m-%d'),
        'total_amount': total_amount,
        'tax_amount': tax_amount,
        'payment_status': payment_status,
        'remarks': f'发票备注{i+1}' if random.random() > 0.7 else ''
    }
    
    invoices.append(invoice)
    
    # 为每张发票生成1-5个明细项目
    item_count = random.randint(1, 5)
    for j in range(item_count):
        material_id = random.choice(MATERIALS)
        quantity = round(random.uniform(1, 100), 2)
        unit_price = round(random.uniform(10, 500), 2)
        unit = random.choice(UNITS)
        
        item_amount_before_tax = round(quantity * unit_price, 2)
        item_tax = round(item_amount_before_tax * 0.13, 2)
        item_amount_total = round(item_amount_before_tax + item_tax, 2)
        
        invoice_item = {
            'invoice_id': invoice_id,
            'item_no': j + 1,
            'delivery_item_id': f"{delivery_note_ids}-{j+1}",
            'sales_order_item_id': f"{sales_order_id}-{j+1}",
            'material_id': material_id,
            'invoiced_quantity': quantity,
            'unit_price': unit_price,
            'tax_amount': item_tax,
            'item_amount': item_amount_total,
            'unit': unit
        }
        
        invoice_items.append(invoice_item)

# 为部分发票生成收款记录
print("正在生成收款记录数据...")

payment_sequence = 1
for invoice in invoices:
    # 60%的概率生成收款记录
    if random.random() < 0.6:
        invoice_total = invoice['total_amount']
        
        # 根据发票状态确定收款情况
        if invoice['payment_status'] == '已付款':
            # 已付款的发票，生成1-2笔收款记录，总额等于发票金额
            payment_count = random.randint(1, 2)
            remaining_amount = invoice_total
            
            for k in range(payment_count):
                if k == payment_count - 1:  # 最后一笔收款
                    payment_amount = remaining_amount
                else:
                    payment_amount = round(remaining_amount * random.uniform(0.3, 0.8), 2)
                    remaining_amount -= payment_amount
                
                # 从发票日期中提取年月
                invoice_date = datetime.strptime(invoice['invoice_date'], '%Y-%m-%d')
                payment_year = invoice_date.year % 100
                payment_month = min(invoice_date.month + random.randint(0, 2), 12)
                
                payment_id = generate_payment_id(payment_year, payment_month, payment_sequence)
                payment_sequence += 1
                
                payment_date = invoice_date + timedelta(days=random.randint(1, 60))
                
                payment = {
                    'payment_id': payment_id,
                    'customer_id': invoice['customer_id'],
                    'invoice_id': invoice['invoice_id'],
                    'payment_date': payment_date.strftime('%Y-%m-%d'),
                    'payment_amount': payment_amount,
                    'payment_method': random.choice(PAYMENT_METHODS),
                    'write_off_amount': 0.0,
                    'status': '已确认',
                    'remarks': f'收款备注{payment_sequence}' if random.random() > 0.8 else ''
                }
                
                payments.append(payment)
        
        elif invoice['payment_status'] == '部分付款':
            # 部分付款的发票，生成1笔收款记录，金额为发票金额的30%-80%
            payment_amount = round(invoice_total * random.uniform(0.3, 0.8), 2)
            
            # 从发票日期中提取年月
            invoice_date = datetime.strptime(invoice['invoice_date'], '%Y-%m-%d')
            payment_year = invoice_date.year % 100
            payment_month = min(invoice_date.month + random.randint(0, 1), 12)
            
            payment_id = generate_payment_id(payment_year, payment_month, payment_sequence)
            payment_sequence += 1
            
            payment_date = invoice_date + timedelta(days=random.randint(1, 30))
            
            payment = {
                'payment_id': payment_id,
                'customer_id': invoice['customer_id'],
                'invoice_id': invoice['invoice_id'],
                'payment_date': payment_date.strftime('%Y-%m-%d'),
                'payment_amount': payment_amount,
                'payment_method': random.choice(PAYMENT_METHODS),
                'write_off_amount': 0.0,
                'status': '已确认',
                'remarks': f'收款备注{payment_sequence}' if random.random() > 0.8 else ''
            }
            
            payments.append(payment)

# 创建DataFrame
df_invoices = pd.DataFrame(invoices)
df_invoice_items = pd.DataFrame(invoice_items)
df_payments = pd.DataFrame(payments)

# 保存为CSV文件
print("正在保存CSV文件...")

# 客户发票表
df_invoices.to_csv('instance\customer_invoice.csv', index=False, encoding='utf-8-sig')
print(f"已生成 customer_invoice.csv - {len(df_invoices)} 条记录")

# 发票明细表
df_invoice_items.to_csv('instance\invoice_item.csv', index=False, encoding='utf-8-sig')
print(f"已生成 invoice_item.csv - {len(df_invoice_items)} 条记录")

# 收款记录表
df_payments.to_csv('instance\customer_payment.csv', index=False, encoding='utf-8-sig')
print(f"已生成 customer_payment.csv - {len(df_payments)} 条记录")

# 显示数据统计信息
print("\n=== 数据统计信息 ===")
print(f"发票总数: {len(df_invoices)}")
print(f"发票明细总数: {len(df_invoice_items)}")
print(f"收款记录总数: {len(df_payments)}")

print("\n发票状态分布:")
status_counts = df_invoices['payment_status'].value_counts()
for status, count in status_counts.items():
    print(f"  {status}: {count}条 ({count/len(df_invoices)*100:.1f}%)")

print("\n客户分布:")
customer_counts = df_invoices['customer_id'].value_counts()
for customer, count in customer_counts.items():
    print(f"  {customer}: {count}条")

print("\n发票金额统计:")
print(f"  总金额范围: {df_invoices['total_amount'].min():.2f} - {df_invoices['total_amount'].max():.2f}")
print(f"  平均金额: {df_invoices['total_amount'].mean():.2f}")
print(f"  总计金额: {df_invoices['total_amount'].sum():.2f}")

print("\n收款金额统计:")
if len(df_payments) > 0:
    print(f"  收款金额范围: {df_payments['payment_amount'].min():.2f} - {df_payments['payment_amount'].max():.2f}")
    print(f"  平均收款: {df_payments['payment_amount'].mean():.2f}")
    print(f"  总收款额: {df_payments['payment_amount'].sum():.2f}")

print("\n收款方式分布:")
if len(df_payments) > 0:
    method_counts = df_payments['payment_method'].value_counts()
    for method, count in method_counts.items():
        print(f"  {method}: {count}笔")

# 显示样本数据
print("\n=== 样本数据预览 ===")
print("\n客户发票表前5条:")
print(df_invoices.head().to_string(index=False))

print("\n发票明细表前5条:")
print(df_invoice_items.head().to_string(index=False))

print("\n收款记录表前5条:")
print(df_payments.head().to_string(index=False))

print("\n✅ 数据生成完成！生成的CSV文件可以直接导入数据库使用。")