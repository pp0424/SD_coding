-- SQLite
PRAGMA foreign_keys = ON;

-- 删除（先子表再父表）
DROP TABLE IF EXISTS DeliveryItem;
DROP TABLE IF EXISTS PickingTaskItem;
DROP TABLE IF EXISTS DeliveryNote;
DROP TABLE IF EXISTS PickingTask;
DROP TABLE IF EXISTS StockChangeLog;

-- PickingTask
CREATE TABLE PickingTask (
    task_id         TEXT PRIMARY KEY,
    sales_order_id  TEXT NOT NULL,
    warehouse_code  TEXT NOT NULL,
    status          TEXT DEFAULT '已创建',
    picker          TEXT,
    assigned_at     TEXT,
    start_time      TEXT,
    complete_time   TEXT,
    remarks         TEXT,
    FOREIGN KEY (sales_order_id) REFERENCES SalesOrder(sales_order_id)
);

-- DeliveryNote
CREATE TABLE DeliveryNote (
    delivery_note_id TEXT PRIMARY KEY,
    picking_task_id  TEXT NOT NULL,
    sales_order_id   TEXT NOT NULL,
    delivery_date    TEXT NOT NULL,
    warehouse_code   TEXT NOT NULL,
    status           TEXT DEFAULT '已创建',
    posted_by        TEXT,
    posted_at        TEXT,
    remarks          TEXT,
    FOREIGN KEY (picking_task_id) REFERENCES PickingTask(task_id),
    FOREIGN KEY (sales_order_id)  REFERENCES SalesOrder(sales_order_id)
);


-- PickingTaskItem
CREATE TABLE PickingTaskItem (
    task_id             TEXT NOT NULL,
    item_no             INTEGER NOT NULL,
    sales_order_item_no INTEGER NOT NULL,
    material_id         TEXT NOT NULL,
    required_quantity   NUMERIC(10,2),
    picked_quantity     NUMERIC(10,2),
    unit                TEXT,
    storage_location    TEXT,
    PRIMARY KEY (task_id, item_no),
    FOREIGN KEY (task_id)     REFERENCES PickingTask(task_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES Material(material_id)
);

-- DeliveryItem
CREATE TABLE DeliveryItem (
    delivery_note_id         TEXT NOT NULL,
    item_no                  INTEGER NOT NULL,
    sales_order_item_no      INTEGER NOT NULL,
    material_id              TEXT NOT NULL,
    planned_delivery_quantity NUMERIC(10,2),
    actual_delivery_quantity  NUMERIC(10,2),
    unit                     TEXT,
    PRIMARY KEY (delivery_note_id, item_no),
    FOREIGN KEY (delivery_note_id) REFERENCES DeliveryNote(delivery_note_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id)      REFERENCES Material(material_id)
);

-- StockChangeLog
CREATE TABLE StockChangeLog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id     TEXT NOT NULL,
    change_time     TEXT DEFAULT (datetime('now')),
    change_type     TEXT NOT NULL,
    quantity_change NUMERIC(10,2) NOT NULL,
    before_quantity NUMERIC(10,2),
    after_quantity  NUMERIC(10,2),
    reference_doc   TEXT,
    operator        TEXT,
    warehouse_code  TEXT,
    FOREIGN KEY (material_id) REFERENCES Material(material_id)
);

--Material
-- 启用外键（习惯性写上）
PRAGMA foreign_keys = ON;

-- 添加 physical_stock 列，默认值 0.0
ALTER TABLE Material 
ADD COLUMN physical_stock NUMERIC(10,2) DEFAULT 0.00;  -- 账面总库存

-- 添加 allocated_stock 列，默认值 0.0
ALTER TABLE Material 
ADD COLUMN allocated_stock NUMERIC(10,2) DEFAULT 0.00;  -- 已分配库存

UPDATE Material SET physical_stock = 0 WHERE available_stock IS NULL;
UPDATE Material SET allocated_stock = 0 WHERE allocated_stock IS NULL;

-- ========== 开始迁移 ==========

-- 1) 先关闭外键约束检查并开始事务
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 2) 为 StockChangeLog 新增列（SQLite 支持 ADD COLUMN）
ALTER TABLE StockChangeLog ADD COLUMN before_available NUMERIC;
ALTER TABLE StockChangeLog ADD COLUMN after_available NUMERIC;
ALTER TABLE StockChangeLog ADD COLUMN before_allocated NUMERIC;
ALTER TABLE StockChangeLog ADD COLUMN after_allocated NUMERIC;
ALTER TABLE StockChangeLog ADD COLUMN before_physical NUMERIC;
ALTER TABLE StockChangeLog ADD COLUMN after_physical NUMERIC;

--（可选）把已有 quantity_change 的 NULL 填为 0（如需要）
UPDATE StockChangeLog SET quantity_change = 0 WHERE quantity_change IS NULL;

-- 3) 备份现有 Material 表的 schema（建议事先手动保存 .schema Material 输出）
--    然后创建新表 Material_new（包含 NOT NULL 与默认值）
CREATE TABLE IF NOT EXISTS Material_new (
    material_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    base_unit TEXT NOT NULL,
    storage_location TEXT NOT NULL,
    physical_stock NUMERIC NOT NULL DEFAULT 0.0000,
    available_stock NUMERIC NOT NULL DEFAULT 0.0000,
    allocated_stock NUMERIC NOT NULL DEFAULT 0.0000
);

-- 4) 将旧表数据导入新表（使用 ROUND(...,4) 并用 COALESCE 避免 NULL）
INSERT INTO Material_new (
    material_id,
    description,
    base_unit,
    storage_location,
    physical_stock,
    available_stock,
    allocated_stock
)
SELECT
    material_id,
    description,
    base_unit,
    storage_location,
    COALESCE(ROUND(CAST(physical_stock AS NUMERIC), 4), 0.0000) AS physical_stock,
    COALESCE(ROUND(CAST(available_stock AS NUMERIC), 4), 0.0000) AS available_stock,
    COALESCE(ROUND(CAST(allocated_stock AS NUMERIC), 4), 0.0000) AS allocated_stock
FROM Material;

-- 5) 检查数据是否正确拷贝（你也可以手动跑查询确认）
--    示例检查：行数是否一致
-- SELECT count(*) FROM Material;
-- SELECT count(*) FROM Material_new;

-- 6) 删除旧表并把新表重命名为原表名
DROP TABLE Material;
ALTER TABLE Material_new RENAME TO Material;

-- 7) 如果你有为 Material 创建的 index / trigger，需要重新创建（无法自动恢复）
--    建议在迁移前用 `.schema Material` 把原来的索引/触发器/外键语句保存下来，
--    然后在这里执行这些 CREATE INDEX / CREATE TRIGGER / ALTER TABLE ... (重新建立约束)。
--    示例（如果你有索引，请在此处执行）：
-- CREATE INDEX IF NOT EXISTS idx_material_storage ON Material (storage_location);

-- 8) 事务提交并重新开启外键
COMMIT;
PRAGMA foreign_keys = ON;

-- ========== 迁移完成 ==========

-- 1) 检查新列存在
PRAGMA table_info('StockChangeLog');

-- 2) 检查 Material 列定义和默认值
PRAGMA table_info('Material');

-- 3) 随机抽查某些数值是否合理
SELECT material_id, physical_stock, available_stock, allocated_stock FROM Material LIMIT 20;

-- 4) 确保没有 NULL 值（因为我们在新表里设置 NOT NULL）
SELECT COUNT(*) FROM Material WHERE physical_stock IS NULL OR available_stock IS NULL OR allocated_stock IS NULL;

--现有的 StockChangeLog 表里加上两列
ALTER TABLE StockChangeLog
ADD COLUMN before_pending_outbound NUMERIC(10, 2);

ALTER TABLE StockChangeLog
ADD COLUMN after_pending_outbound NUMERIC(10, 2);

--Material增加列名pending_outbound
ALTER TABLE Material
ADD COLUMN pending_outbound NUMERIC NOT NULL DEFAULT 0.0000;

--DeliveryNote增加列名created_by
ALTER TABLE DeliveryNote ADD COLUMN created_by TEXT;

UPDATE DeliveryNote SET status = '已创建';
UPDATE PickingTask SET status = '待拣货';

BEGIN TRANSACTION;

-- 1. 创建新表（去掉 status 的 DEFAULT）
CREATE TABLE PickingTask_new (
    task_id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    warehouse_code TEXT NOT NULL,
    status TEXT, -- 去掉默认值
    picker TEXT,
    assigned_at TEXT,
    start_time TEXT,
    complete_time TEXT,
    remarks TEXT
);

-- 2. 迁移数据
INSERT INTO PickingTask_new
SELECT * FROM PickingTask;

-- 3. 删除旧表
DROP TABLE PickingTask;

-- 4. 重命名新表为旧表名
ALTER TABLE PickingTask_new RENAME TO PickingTask;

COMMIT;


