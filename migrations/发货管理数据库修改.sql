-- 1. 删除所有触发器
DROP TRIGGER IF EXISTS sync_material_insert;
DROP TRIGGER IF EXISTS sync_material_update;
DROP TRIGGER IF EXISTS sync_material_delete;
DROP TRIGGER IF EXISTS sync_inventory_update;

-- 2. 删除锁表
DROP TABLE IF EXISTS sync_lock;

DROP TABLE IF EXISTS Inventory;

-- 创建持久化的锁表（替代临时表）
CREATE TABLE IF NOT EXISTS sync_lock (
    lock_id INTEGER PRIMARY KEY DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO sync_lock (lock_id, locked) VALUES (1, 0);

-- 创建 Inventory 表
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

-- 为 Material 表创建同步触发器
-- INSERT 触发器
CREATE TRIGGER IF NOT EXISTS sync_material_insert
AFTER INSERT ON Material
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock WHERE lock_id = 1) = 0
BEGIN
    UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;
    
    REPLACE INTO Inventory (
        material_id,
        description,
        base_unit,
        storage_location,
        available_stock,
        physical_stock,
        allocated_stock,
        pending_outbound
    ) VALUES (
        NEW.material_id,
        NEW.description,
        NEW.base_unit,
        NEW.storage_location,
        NEW.available_stock,
        NEW.physical_stock,
        NEW.allocated_stock,
        NEW.pending_outbound
    );
    
    UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;

-- UPDATE 触发器
CREATE TRIGGER IF NOT EXISTS sync_material_update
AFTER UPDATE ON Material
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock WHERE lock_id = 1) = 0
BEGIN
    UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;
    
    UPDATE Inventory SET
        description = NEW.description,
        base_unit = NEW.base_unit,
        storage_location = NEW.storage_location,
        available_stock = NEW.available_stock,
        physical_stock = NEW.physical_stock,
        allocated_stock = NEW.allocated_stock,
        pending_outbound = NEW.pending_outbound
    WHERE material_id = NEW.material_id;
    
    UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;

-- DELETE 触发器
CREATE TRIGGER IF NOT EXISTS sync_material_delete
AFTER DELETE ON Material
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock WHERE lock_id = 1) = 0
BEGIN
    UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;
    
    DELETE FROM Inventory WHERE material_id = OLD.material_id;
    
    UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;

-- 为 Inventory 表创建同步触发器
CREATE TRIGGER IF NOT EXISTS sync_inventory_update
AFTER UPDATE ON Inventory
FOR EACH ROW
WHEN (SELECT locked FROM sync_lock WHERE lock_id = 1) = 0 AND (
    OLD.description <> NEW.description OR
    OLD.base_unit <> NEW.base_unit OR
    OLD.storage_location <> NEW.storage_location OR
    OLD.available_stock <> NEW.available_stock OR
    OLD.physical_stock <> NEW.physical_stock OR
    OLD.allocated_stock <> NEW.allocated_stock OR
    OLD.pending_outbound <> NEW.pending_outbound
)
BEGIN
    UPDATE sync_lock SET locked = 1 WHERE lock_id = 1;
    
    UPDATE OR IGNORE Material SET
        description = NEW.description,
        base_unit = NEW.base_unit,
        storage_location = NEW.storage_location,
        available_stock = NEW.available_stock,
        physical_stock = NEW.physical_stock,
        allocated_stock = NEW.allocated_stock,
        pending_outbound = NEW.pending_outbound
    WHERE material_id = NEW.material_id;
    
    UPDATE sync_lock SET locked = 0 WHERE lock_id = 1;
END;

-- 初始化数据同步
-- 第一步: 更新现有记录
UPDATE Inventory
SET
    description = (SELECT description FROM Material WHERE Material.material_id = Inventory.material_id),
    base_unit = (SELECT base_unit FROM Material WHERE Material.material_id = Inventory.material_id),
    storage_location = (SELECT storage_location FROM Material WHERE Material.material_id = Inventory.material_id),
    available_stock = (SELECT available_stock FROM Material WHERE Material.material_id = Inventory.material_id),
    physical_stock = (SELECT physical_stock FROM Material WHERE Material.material_id = Inventory.material_id),
    allocated_stock = (SELECT allocated_stock FROM Material WHERE Material.material_id = Inventory.material_id),
    pending_outbound = (SELECT pending_outbound FROM Material WHERE Material.material_id = Inventory.material_id)
WHERE EXISTS (
    SELECT 1 FROM Material
    WHERE Material.material_id = Inventory.material_id
);

-- 第二步: 插入新记录
INSERT OR IGNORE INTO Inventory (
    material_id,
    description,
    base_unit,
    storage_location,
    available_stock,
    physical_stock,
    allocated_stock,
    pending_outbound
)
SELECT 
    material_id,
    description,
    base_unit,
    storage_location,
    available_stock,
    physical_stock,
    allocated_stock,
    pending_outbound
FROM Material;

SELECT * FROM Material;
SELECT * FROM Inventory;


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