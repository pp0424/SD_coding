PRAGMA foreign_keys = ON;

CREATE TABLE `Customer` (
  `customer_id` varchar(255) PRIMARY KEY COMMENT '客户编号，唯一键（如“CUST-CN00001”）',
  `customer_name` varchar(255) NOT NULL COMMENT '客户名称，全称',
  `customer_type` varchar(255) NOT NULL COMMENT '客户类型，分为person/group/organization',
  `address` varchar(255) NOT NULL COMMENT '注册或经营地址',
  `phone` varchar(255) NOT NULL COMMENT '固定办公电话',
  `email` varchar(255) NOT NULL COMMENT '官方邮箱',
  `credit_limit` decimal DEFAULT 0 COMMENT '信用额度，非负数',
  `payment_terms_code` varchar(255) COMMENT '付款条件代码',
  `sales_region_code` varchar(255) COMMENT '销售区域代码',
  `status` varchar(255) COMMENT '客户状态（“正常”“已停用”“已注销”）',
  `created_at` datetime COMMENT '创建时间，可自动生成'
);

CREATE TABLE `ContactPerson` (
  `contact_id` varchar(255) PRIMARY KEY COMMENT '联系人ID，唯一键（如“CONT-00001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '所属客户编号',
  `first_name` varchar(255) NOT NULL COMMENT '名',
  `last_name` varchar(255) NOT NULL COMMENT '姓',
  `country_language` varchar(255) COMMENT '国家/语言',
  `contact_info` varchar(255) NOT NULL COMMENT '办公电话/手机/邮箱（至少一项）',
  `position` varchar(255) COMMENT '职位',
  `status` varchar(255) COMMENT '联系人状态（“有效”“无效”）'
);

CREATE TABLE `BPRelationship` (
  `relationship_id` varchar(255) PRIMARY KEY COMMENT '关系ID，唯一键（如“BPREL-00001”）',
  `main_customer_id` varchar(255) NOT NULL COMMENT '主客户编号',
  `relationship_type` varchar(255) NOT NULL COMMENT '关系类型（如“分销商”“代理商”）',
  `description` varchar(255) COMMENT '关系描述',
  `effective_date` date COMMENT '生效日期',
  `expiry_date` date COMMENT '失效日期',
  `status` varchar(255) COMMENT '关系状态（“有效”“已终止”）'
);

CREATE TABLE `Inquiry` (
  `inquiry_id` varchar(255) PRIMARY KEY COMMENT '询价单号，唯一键（如“INQ-20250716-001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '客户编号',
  `inquiry_date` datetime NOT NULL COMMENT '询价日期',
  `expected_delivery_date` date COMMENT '期望交货日期',
  `status` varchar(255) COMMENT '询价状态（“草稿”“已评审”“已失效”）',
  `expected_total_amount` decimal COMMENT '客户期望总金额',
  `salesperson_id` varchar(255) COMMENT '负责销售员编号',
  `remarks` varchar(255) COMMENT '备注'
);

CREATE TABLE `InquiryItem` (
  `inquiry_id` varchar(255) NOT NULL COMMENT '所属询价单号',
  `item_no` int NOT NULL COMMENT '行项号（在询价单内唯一）',
  `material_id` varchar(255) NOT NULL COMMENT '物料编号',
  `inquiry_quantity` decimal NOT NULL COMMENT '询价数量',
  `unit` varchar(255) COMMENT '物料单位（取自物料主数据）',
  `expected_unit_price` decimal COMMENT '客户期望单价',
  `item_remarks` varchar(255) COMMENT '行项备注',
  PRIMARY KEY (`inquiry_id`, `item_no`)
);

CREATE TABLE `Quotation` (
  `quotation_id` varchar(255) PRIMARY KEY COMMENT '报价单号，唯一键（如“QUO-20250717-001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '客户编号',
  `inquiry_id` varchar(255) COMMENT '关联询价单号（可选）',
  `quotation_date` datetime NOT NULL COMMENT '报价日期',
  `valid_until_date` datetime NOT NULL COMMENT '有效期至',
  `status` varchar(255) COMMENT '报价状态（“草稿”“已发送”“已确认”“已失效”）',
  `total_amount` decimal NOT NULL COMMENT '总金额（计算值）',
  `salesperson_id` varchar(255) COMMENT '负责销售员编号',
  `remarks` varchar(255) COMMENT '备注'
);

CREATE TABLE `QuotationItem` (
  `quotation_id` varchar(255) NOT NULL COMMENT '所属报价单号',
  `item_no` int NOT NULL COMMENT '行项号（在报价单内唯一）',
  `inquiry_item_id` varchar(255) COMMENT '关联询价单行项号（可选，格式为“询价单号-行项号”）',
  `material_id` varchar(255) NOT NULL COMMENT '物料编号',
  `quotation_quantity` decimal NOT NULL COMMENT '报价数量',
  `unit_price` decimal NOT NULL COMMENT '单价',
  `discount_rate` decimal DEFAULT 0 COMMENT '折扣率（0-100%）',
  `item_amount` decimal COMMENT '行项金额（计算值）',
  `unit` varchar(255) COMMENT '物料单位（取自物料主数据）',
  PRIMARY KEY (`quotation_id`, `item_no`)
);

CREATE TABLE `SalesOrder` (
  `sales_order_id` varchar(255) PRIMARY KEY COMMENT '订单编号，唯一键（如“SO-20250720-001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '客户编号',
  `quotation_id` varchar(255) COMMENT '关联报价单号（可选）',
  `order_date` datetime NOT NULL COMMENT '订单日期',
  `required_delivery_date` date NOT NULL COMMENT '要求交货日期',
  `status` varchar(255) COMMENT '订单状态（“已创建”“已审核”“部分发货”“已完成”“已取消”）',
  `total_amount` decimal NOT NULL COMMENT '总金额（计算值）',
  `credit_check_result` varchar(255) COMMENT '信用检查结果（“通过”“未通过”）',
  `remarks` varchar(255) COMMENT '备注'
);

CREATE TABLE `OrderItem` (
  `sales_order_id` varchar(255) NOT NULL COMMENT '所属订单编号',
  `item_no` int NOT NULL COMMENT '行项号（在订单内唯一）',
  `material_id` varchar(255) NOT NULL COMMENT '物料编号',
  `order_quantity` decimal NOT NULL COMMENT '订单数量',
  `sales_unit_price` decimal NOT NULL COMMENT '销售单价',
  `shipped_quantity` decimal COMMENT '已发货数量（计算值）',
  `unshipped_quantity` decimal COMMENT '未发货数量（计算值）',
  `item_amount` decimal COMMENT '行项金额（计算值）',
  `unit` varchar(255) COMMENT '物料单位（取自物料主数据）',
  PRIMARY KEY (`sales_order_id`, `item_no`)
);

CREATE TABLE `Material` (
  `material_id` varchar(255) PRIMARY KEY COMMENT '物料编号，唯一键（如“MAT-01001A”）',
  `description` varchar(255) NOT NULL COMMENT '物料描述（名称及规格）',
  `base_unit` varchar(255) NOT NULL COMMENT '基本计量单位',
  `storage_location` varchar(255) NOT NULL COMMENT '存储位置',
  `available_stock` decimal COMMENT '当前可用库存（计算值）'
);

CREATE TABLE `DeliveryNote` (
  `delivery_note_id` varchar(255) PRIMARY KEY COMMENT '发货单编号，唯一键（如“DN-SO250704001-01”）',
  `sales_order_id` varchar(255) NOT NULL COMMENT '关联销售订单编号',
  `delivery_date` datetime NOT NULL COMMENT '发货日期',
  `warehouse_code` varchar(255) NOT NULL COMMENT '发货仓库代码',
  `status` varchar(255) COMMENT '发货单状态（“已发货”“已过账”“已取消”）',
  `posted_by` varchar(255) COMMENT '过账人',
  `posted_at` datetime COMMENT '过账时间',
  `remarks` varchar(255) COMMENT '备注'
);

CREATE TABLE `DeliveryItem` (
  `delivery_note_id` varchar(255) NOT NULL COMMENT '所属发货单编号',
  `item_no` int NOT NULL COMMENT '行项号（在发货单内唯一）',
  `sales_order_item_no` int NOT NULL COMMENT '关联销售订单行项号',
  `material_id` varchar(255) NOT NULL COMMENT '物料编号',
  `planned_delivery_quantity` decimal COMMENT '计划发货数量',
  `actual_delivery_quantity` decimal NOT NULL COMMENT '实际发货数量',
  `unit` varchar(255) COMMENT '物料单位（取自物料主数据）',
  PRIMARY KEY (`delivery_note_id`, `item_no`)
);

CREATE TABLE `CustomerInvoice` (
  `invoice_id` varchar(255) PRIMARY KEY COMMENT '发票编号，唯一键（如“INV-20250725-001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '客户编号',
  `sales_order_id` varchar(255) NOT NULL COMMENT '关联销售订单编号',
  `delivery_note_ids` varchar(255) COMMENT '关联发货单号（可填多个，逗号分隔）',
  `invoice_date` datetime NOT NULL COMMENT '开票日期',
  `payment_deadline` date NOT NULL COMMENT '付款期限',
  `total_amount` decimal NOT NULL COMMENT '总金额（计算值，含税额）',
  `tax_amount` decimal NOT NULL COMMENT '税额（计算值）',
  `payment_status` varchar(255) COMMENT '付款状态（“未收款”“部分收款”“已结清”）',
  `remarks` varchar(255) COMMENT '备注'
);

CREATE TABLE `InvoiceItem` (
  `invoice_id` varchar(255) NOT NULL COMMENT '所属发票编号',
  `item_no` int NOT NULL COMMENT '行项号（在发票内唯一）',
  `delivery_item_id` varchar(255) NOT NULL COMMENT '关联发货单行项号（格式为“发货单号-行项号”）',
  `sales_order_item_id` varchar(255) NOT NULL COMMENT '关联订单行项号（格式为“订单编号-行项号”）',
  `material_id` varchar(255) NOT NULL COMMENT '物料编号',
  `invoiced_quantity` decimal NOT NULL COMMENT '开票数量',
  `unit_price` decimal NOT NULL COMMENT '单价（取自订单行项）',
  `tax_amount` decimal COMMENT '税额（计算值）',
  `item_amount` decimal COMMENT '行项金额（计算值）',
  `unit` varchar(255) COMMENT '物料单位（取自物料主数据）',
  PRIMARY KEY (`invoice_id`, `item_no`)
);

CREATE TABLE `CustomerPayment` (
  `payment_id` varchar(255) PRIMARY KEY COMMENT '收款凭证编号，唯一键（如“PAY-20250805-001”）',
  `customer_id` varchar(255) NOT NULL COMMENT '客户编号',
  `invoice_id` varchar(255) NOT NULL COMMENT '关联发票编号',
  `payment_date` datetime NOT NULL COMMENT '收款日期',
  `payment_amount` decimal NOT NULL COMMENT '收款金额',
  `payment_method` varchar(255) NOT NULL COMMENT '收款方式（“银行转账”“现金”等）',
  `write_off_amount` decimal NOT NULL COMMENT '核销金额',
  `status` varchar(255) COMMENT '收款状态（“已确认”“已取消”）',
  `remarks` varchar(255) COMMENT '备注'
);

ALTER TABLE `ContactPerson` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `BPRelationship` ADD FOREIGN KEY (`main_customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `Inquiry` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `InquiryItem` ADD FOREIGN KEY (`inquiry_id`) REFERENCES `Inquiry` (`inquiry_id`);

ALTER TABLE `InquiryItem` ADD FOREIGN KEY (`material_id`) REFERENCES `Material` (`material_id`);

ALTER TABLE `Quotation` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `Quotation` ADD FOREIGN KEY (`inquiry_id`) REFERENCES `Inquiry` (`inquiry_id`);

ALTER TABLE `QuotationItem` ADD FOREIGN KEY (`quotation_id`) REFERENCES `Quotation` (`quotation_id`);

ALTER TABLE `QuotationItem` ADD FOREIGN KEY (`material_id`) REFERENCES `Material` (`material_id`);

ALTER TABLE `SalesOrder` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `SalesOrder` ADD FOREIGN KEY (`quotation_id`) REFERENCES `Quotation` (`quotation_id`);

ALTER TABLE `OrderItem` ADD FOREIGN KEY (`sales_order_id`) REFERENCES `SalesOrder` (`sales_order_id`);

ALTER TABLE `OrderItem` ADD FOREIGN KEY (`material_id`) REFERENCES `Material` (`material_id`);

ALTER TABLE `DeliveryNote` ADD FOREIGN KEY (`sales_order_id`) REFERENCES `SalesOrder` (`sales_order_id`);

ALTER TABLE `DeliveryItem` ADD FOREIGN KEY (`delivery_note_id`) REFERENCES `DeliveryNote` (`delivery_note_id`);

ALTER TABLE `DeliveryItem` ADD FOREIGN KEY (`sales_order_item_no`) REFERENCES `OrderItem` (`item_no`);

ALTER TABLE `DeliveryItem` ADD FOREIGN KEY (`material_id`) REFERENCES `Material` (`material_id`);

ALTER TABLE `CustomerInvoice` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `CustomerInvoice` ADD FOREIGN KEY (`sales_order_id`) REFERENCES `SalesOrder` (`sales_order_id`);

ALTER TABLE `InvoiceItem` ADD FOREIGN KEY (`invoice_id`) REFERENCES `CustomerInvoice` (`invoice_id`);

ALTER TABLE `InvoiceItem` ADD FOREIGN KEY (`material_id`) REFERENCES `Material` (`material_id`);

ALTER TABLE `CustomerPayment` ADD FOREIGN KEY (`customer_id`) REFERENCES `Customer` (`customer_id`);

ALTER TABLE `CustomerPayment` ADD FOREIGN KEY (`invoice_id`) REFERENCES `CustomerInvoice` (`invoice_id`);

