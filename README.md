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
