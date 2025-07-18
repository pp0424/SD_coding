# SD 项目结构初始化

## 快速开始

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 项目结构

```
sd_project/
├── app.py              # 主程序入口
├── database.py         # 数据库初始化
├── templates/          # HTML模板
├── static/             # 静态资源
├── customer/           # 客户管理模块
├── order/              # 订单管理模块
├── delivery/           # 发货模块
├── finance/            # 财务模块
└── tests/              # 单元测试
```
## 文件结构
/customer/
    ├── models.py
    ├── views.py
    ├── forms.py
/templates/
    └── customer/
        ├── list.html
        └── create.html

## 开发说明（代码组通用）

- 每个模块文件结构：
  /<模块名>/
      models.py
      views.py
      forms.py

- 请每人复制 `customer` 模块作为开发模板。
- 蓝图注册麻烦和我说一下，我来统一加进 `app.py`~

