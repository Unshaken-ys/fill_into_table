# 学生教务系统

基于 Flask 的学生教务管理小系统：学生信息的增删改查、分页搜索、Excel 导入/导出，以及学生选课（学生—课程多对多）。

## 技术栈

- **后端**：Flask 3（单文件 `app.py`，模板渲染 + 表单提交，无前端 JS 框架）
- **数据库**：MySQL 8 + PyMySQL（库名 `decorator_train`）
- **Excel**：openpyxl（导入/导出 `.xlsx`）
- **密码**：werkzeug 自带哈希（`generate_password_hash` / `check_password_hash`）

## 目录结构

```
fill_into_table/
├── app.py                # Flask 应用：全部路由、数据库操作、工具函数
├── config_example.py     # 数据库配置模板（入库）
├── config.py             # 真实数据库配置（含密码，不入库，需自行创建）
├── requirements.txt      # Python 依赖
├── docs/
│   └── mysql.md          # 建库建表 SQL（含选课触发器）
├── templates/            # Jinja2 模板（列表/新增/修改/选课/登录/注册/欢迎页）
├── static/
│   └── css/              # 样式表（base 基础+导航 / form 卡片表单 / 各页面专属）
└── export/               # Excel 导出目录（运行时自动生成，产物不入库）
```

## 快速开始

1. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

2. **准备数据库**

   启动 MySQL，依次执行 [docs/mysql.md](docs/mysql.md) 中的 SQL 建库建表（数据库 `decorator_train`，含 `admin` / `student` / `course` / `student_course` 四张表和选课触发器）。

3. **配置数据库连接**

   复制配置模板并填入自己的数据库密码：

   ```bash
   copy config_example.py config.py      # Windows
   # cp config_example.py config.py      # macOS / Linux
   ```

4. **启动应用**

   ```bash
   python app.py
   ```

   浏览器访问 <http://127.0.0.1:5000/> ，先在「注册」页创建管理员账号，再登录使用。

## 主要功能

| 功能 | 路由 |
| --- | --- |
| 欢迎页 | `/` |
| 学生列表（分页）/ 模糊搜索 | `/student/list`、`/student/search` |
| 新增 / 修改 / 删除学生 | `/student/insert`、`/student/update`、`/student/delete` |
| Excel 导出 / 导入 | `/student/to_excel`、`/student/import` |
| 学生选课（多对多，支持批量） | `/student/choose_class` |
| 管理员登录 / 注册 / 退出 | `/student/login`、`/student/register`、`/student/logout` |
