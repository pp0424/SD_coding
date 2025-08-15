CREATE TABLE IF NOT EXISTS Inventory (
    material_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    base_unit TEXT NOT NULL,
    storage_location TEXT NOT NULL,
    available_stock NUMERIC(18,4) NOT NULL DEFAULT 0,
    physical_stock NUMERIC(18,4) NOT NULL DEFAULT 0,
    allocated_stock NUMERIC(18,4) NOT NULL DEFAULT 0,
    pending_outbound NUMERIC(18,4) NOT NULL DEFAULT 0
);

-- 列出所有触发器的名字和作用表
SELECT name, tbl_name
FROM sqlite_master
WHERE type = 'trigger';

-- 查看触发器的完整创建语句
SELECT name, sql
FROM sqlite_master
WHERE type = 'trigger';

SELECT sqlite_version();


-- 确保锁表存在
CREATE TABLE IF NOT EXISTS sync_lock (
  lock_id INTEGER PRIMARY KEY CHECK(lock_id = 1),
  locked  INTEGER NOT NULL DEFAULT 0 CHECK(locked IN (0,1))
);
INSERT OR IGNORE INTO sync_lock(lock_id, locked) VALUES (1, 0);
SELECT * FROM sync_lock;

-- 为 Inventory 表创建 INSERT 触发器
CREATE TRIGGER IF NOT EXISTS sync_inventory_insert
AFTER INSERT ON Inventory
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock) = 0
BEGIN
    -- 设置锁防止递归
    UPDATE sync_lock SET locked = 1;
    
    -- 插入或更新 Material 表（处理主键冲突）
    INSERT INTO Material (
        material_id,
        description,
        base_unit,
        storage_location,
        allocated_stock
    ) VALUES (
        NEW.material_id,
        NEW.description,
        NEW.base_unit,
        NEW.storage_location,
        NEW.allocated_stock
    ) ON CONFLICT(material_id) DO UPDATE SET
        description = NEW.description,
        base_unit = NEW.base_unit,
        storage_location = NEW.storage_location,
        allocated_stock = NEW.allocated_stock;
    
    -- 释放锁
    UPDATE sync_lock SET locked = 0;
END;

-- UPDATE 触发器
CREATE TRIGGER IF NOT EXISTS sync_inventory_update
AFTER UPDATE ON Inventory
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock WHERE lock_id = 1) = 0 AND (
    OLD.description <> NEW.description OR
    OLD.base_unit <> NEW.base_unit OR
    OLD.storage_location <> NEW.storage_location OR
    OLD.allocated_stock <> NEW.allocated_stock
)
BEGIN
    UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;
    
    UPDATE OR IGNORE Material SET
        description = NEW.description,
        base_unit = NEW.base_unit,
        storage_location = NEW.storage_location,
        allocated_stock = NEW.allocated_stock
    WHERE material_id = NEW.material_id;
    
    UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;

--Inventory → Material : DELETE 同步
CREATE TRIGGER IF NOT EXISTS sync_inventory_delete
AFTER DELETE ON Inventory
WHEN COALESCE((SELECT locked FROM sync_lock WHERE lock_id = 1), 0) = 0
BEGIN
  UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;

  DELETE FROM Material WHERE material_id = OLD.material_id;

  UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;


----------------------
-- 更新 Inventory 多行
UPDATE Inventory
SET physical_stock   = abs(random() % 10000),
    allocated_stock  = abs(random() % (IFNULL(physical_stock, 0) / 2 + 1)),
    pending_outbound = abs(random() % (IFNULL(allocated_stock, 0) + 1)),
    available_stock  = IFNULL(physical_stock,0) - IFNULL(allocated_stock,0) - IFNULL(pending_outbound,0);

-- 对照行数（两边受影响的行数应该一致或接近）
SELECT changes() AS inventory_changes;
SELECT COUNT(*) FROM Material; -- 或抽查几条 material_id 的值是否一致

----------------------------
----------------------------
SELECT * FROM Material;
SELECT * FROM Inventory;
PRAGMA table_info(Inventory);

-------------------------------
PRAGMA foreign_keys = OFF;
DROP TABLE IF EXISTS PickingTask;
DROP TABLE IF EXISTS PickingTaskItem;
DROP TABLE IF EXISTS DeliveryNote;
DROP TABLE IF EXISTS DeliveryItem;
DROP TABLE IF EXISTS StockChangeLog;

PRAGMA foreign_keys = ON;
-- PickingTask
CREATE TABLE PickingTask (
    task_id            VARCHAR(255) PRIMARY KEY,
    sales_order_id     VARCHAR(255) NOT NULL,
    warehouse_code     VARCHAR(255) NOT NULL,
    status             VARCHAR(50),
    picker             VARCHAR(255),
    assigned_at        DATETIME,
    start_time         DATETIME,
    complete_time      DATETIME,
    remarks            TEXT,
    FOREIGN KEY (sales_order_id) REFERENCES SalesOrder (sales_order_id)
);
 
-- PickingTaskItem
CREATE TABLE PickingTaskItem (
    task_id             VARCHAR(255) NOT NULL,
    item_no             INTEGER NOT NULL,
    sales_order_item_no INTEGER NOT NULL,
    material_id         VARCHAR(255) NOT NULL,
    required_quantity   NUMERIC(10, 2),
    picked_quantity     NUMERIC(10, 2),
    unit                VARCHAR(50),
    storage_location    VARCHAR(255),
    PRIMARY KEY (task_id, item_no),
    FOREIGN KEY (task_id) REFERENCES PickingTask (task_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES Material (material_id)
);

-- DeliveryNote
CREATE TABLE DeliveryNote (
    delivery_note_id VARCHAR(255) PRIMARY KEY,
    picking_task_id  VARCHAR(255) NOT NULL,
    sales_order_id   VARCHAR(255) NOT NULL,
    delivery_date    DATETIME NOT NULL,
    warehouse_code   VARCHAR(255) NOT NULL,
    status           TEXT NOT NULL DEFAULT '已创建' CHECK (status IN ('已创建','已拣货','已发货','已过账','已取消')),
    posted_by        VARCHAR(255),
    posted_at        DATETIME,
    created_by       VARCHAR(255),
    remarks          TEXT,
    FOREIGN KEY (picking_task_id) REFERENCES PickingTask (task_id),
    FOREIGN KEY (sales_order_id)  REFERENCES SalesOrder (sales_order_id)
);

-- DeliveryItem
CREATE TABLE DeliveryItem (
    delivery_note_id          VARCHAR(255) NOT NULL,
    item_no                   INTEGER NOT NULL,
    sales_order_item_no       INTEGER NOT NULL,
    material_id               VARCHAR(255) NOT NULL,
    planned_delivery_quantity NUMERIC(18, 4),
    actual_delivery_quantity  NUMERIC(18, 4),
    unit                      VARCHAR(50),
    PRIMARY KEY (delivery_note_id, item_no),
    FOREIGN KEY (delivery_note_id) REFERENCES DeliveryNote (delivery_note_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id)     REFERENCES Material (material_id)
);

-- StockChangeLog
CREATE TABLE StockChangeLog (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id               VARCHAR(255) NOT NULL,
    change_time               DATETIME DEFAULT CURRENT_TIMESTAMP,
    change_type               VARCHAR(50) NOT NULL,
    quantity_change           NUMERIC(18, 4) NOT NULL,
    before_available          NUMERIC(18, 4),
    after_available           NUMERIC(18, 4),
    before_allocated          NUMERIC(18, 4),
    after_allocated           NUMERIC(18, 4),
    before_physical           NUMERIC(18, 4),
    after_physical            NUMERIC(18, 4),
    before_pending_outbound   NUMERIC(18, 4),
    after_pending_outbound    NUMERIC(18, 4),
    reference_doc             VARCHAR(255),
    operator                  VARCHAR(255),
    warehouse_code            VARCHAR(255),
    FOREIGN KEY (material_id) REFERENCES Material (material_id)
);

CREATE TABLE users (
    id INTEGER NOT NULL, 
    username VARCHAR(80) NOT NULL, 
    password_hash VARCHAR(256) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (username)
);

INSERT INTO users (id, username, password_hash) VALUES
(1, 'admin', '123456')


SELECT * FROM Material;
SELECT * FROM Inventory;
SELECT * FROM users;
SELECT * FROM PickingTask;
SELECT * FROM PickingTaskItem;
SELECT * FROM DeliveryNote;
SELECT * FROM DeliveryItem;
SELECT * FROM StockChangeLog;
UPDATE DeliveryNote SET warehouse_code='WH001、WH002、WH003' WHERE delivery_note_id='DN20250813-001';
SELECT * FROM DeliveryNote WHERE delivery_note_id='DN20250813-001';

SELECT * from SalesOrder;
PRAGMA TABLE_INFO(SalesOrder);

UPDATE Inventory
SET  physical_stock = abs(random() %10000 );

UPDATE Inventory
SET allocated_stock = abs(random() % (IFNULL(physical_stock, 0) / 2 + 1));

UPDATE Inventory
SET pending_outbound = abs(random() % (IFNULL(allocated_stock, 0) + 1));

UPDATE Inventory
SET available_stock = IFNULL(physical_stock, 0) 
                      - IFNULL(allocated_stock, 0) 
                      - IFNULL(pending_outbound, 0);

UPDATE Inventory SET 
    physical_stock = 1125.0,
    available_stock = 525.0,
    allocated_stock=500.0,
    pending_outbound = 100.0
WHERE material_id = 'MAT-10002';

-- 验证不同步
SELECT 'Test 5: Inventory Unique Field Update -> No Sync' AS test_case;
SELECT 
    (SELECT physical_stock FROM Material) AS mat_physical,  -- 应返回NULL
    (SELECT available_stock FROM Material) AS mat_available; -- 应返回NULL
