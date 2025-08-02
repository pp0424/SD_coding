#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加示例数据到客户管理系统
"""

from app import app, db
from customer.models import Customer, ContactPerson, BPRelationship
from datetime import datetime, date


def add_sample_data():
    with app.app_context():
        # 清空现有数据
        BPRelationship.query.delete()
        ContactPerson.query.delete()
        Customer.query.delete()

        # 添加示例客户
        customers = [
            Customer(
                customer_id="CUST-CN00001",
                customer_name="北京科技有限公司",
                customer_type="organization",
                address="北京市朝阳区科技园区1号",
                phone="010-12345678",
                email="info@bjtech.com",
                credit_limit=100000.00,
                payment_terms_code="NET30",
                sales_region_code="BJ001",
                status="正常"
            ),
            Customer(
                customer_id="CUST-CN00002",
                customer_name="上海贸易集团",
                customer_type="group",
                address="上海市浦东新区陆家嘴金融区",
                phone="021-87654321",
                email="contact@shtrade.com",
                credit_limit=200000.00,
                payment_terms_code="NET15",
                sales_region_code="SH001",
                status="正常"
            ),
            Customer(
                customer_id="CUST-CN00003",
                customer_name="张三",
                customer_type="person",
                address="广州市天河区珠江新城",
                phone="020-11111111",
                email="zhangsan@email.com",
                credit_limit=50000.00,
                payment_terms_code="COD",
                sales_region_code="GZ001",
                status="正常"
            )
        ]

        for customer in customers:
            db.session.add(customer)

        # 添加示例联系人
        contacts = [
            ContactPerson(
                contact_id="CONT-00001",
                customer_id="CUST-CN00001",
                first_name="李",
                last_name="经理",
                country_language="中国/中文",
                contact_info="13800138001",
                position="销售经理",
                status="有效"
            ),
            ContactPerson(
                contact_id="CONT-00002",
                customer_id="CUST-CN00001",
                first_name="王",
                last_name="总监",
                country_language="中国/中文",
                contact_info="wangzj@bjtech.com",
                position="技术总监",
                status="有效"
            ),
            ContactPerson(
                contact_id="CONT-00003",
                customer_id="CUST-CN00002",
                first_name="陈",
                last_name="主管",
                country_language="中国/中文",
                contact_info="13900139002",
                position="采购主管",
                status="有效"
            )
        ]

        for contact in contacts:
            db.session.add(contact)

        # 添加示例业务伙伴关系
        relationships = [
            BPRelationship(
                relationship_id="BPREL-00001",
                main_customer_id="CUST-CN00001",
                contact_id="CONT-00001",  # 关联到李经理
                relationship_type="分销商",
                description="华北地区主要分销商",
                effective_date=date(2024, 1, 1),
                expiry_date=date(2024, 12, 31),
                status="有效"
            ),
            BPRelationship(
                relationship_id="BPREL-00002",
                main_customer_id="CUST-CN00002",
                contact_id="CONT-00003",  # 关联到陈主管
                relationship_type="代理商",
                description="华东地区独家代理商",
                effective_date=date(2024, 1, 1),
                status="有效"
            )
        ]

        for relationship in relationships:
            db.session.add(relationship)

        # 提交所有更改
        db.session.commit()
        print("示例数据添加成功！")
        print(f"添加了 {len(customers)} 个客户")
        print(f"添加了 {len(contacts)} 个联系人")
        print(f"添加了 {len(relationships)} 个业务伙伴关系")


if __name__ == "__main__":
    add_sample_data()
