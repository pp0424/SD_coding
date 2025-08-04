# 每个模块需要完成的大概有前端表单+后端函数+数据表（如果数据库比较难实现的话）
# 大家在本地写完代码之后可以通过github desktop实时fetch到仓库里
# 尽量不改动其他模块的代码
# 及时更新《进度说明》
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
├── customer/           # 客户管理模块  负责成员：陈超然 张诣佳
├── order/              # 订单管理模块  负责成员：黄藝萍 何嘉
├── delivery/           # 发货模块      负责成员：李兰 周星贞
├── finance/            # 财务模块      负责成员：邹一凡 成小东
└── tests/              # 单元测试
```
## 文件结构
/customer/
    ├── models.py
    ├── views.py
    ├── forms.py
/templates/             #每个模块的html文件存放在这个文件夹里
    └── customer/
        ├── list.html
        └── create.html

## 开发说明（代码组通用）

- 每个模块文件结构：
  /<模块名>/
      models.py
      views.py
      forms.py

- 大家可以参考 `customer` 模块作为开发模板。
- 蓝图注册麻烦和我说一下，我来统一加进 `app.py`~

