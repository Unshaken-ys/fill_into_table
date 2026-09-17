# 学生教务系统 — 软件设计文档

| 项目 | 说明 |
| --- | --- |
| 项目名称 | 学生教务系统（fill_into_table） |
| 版本 | v1.0（对应 git 提交「第六次修改，文件管理规范化」） |
| 文档日期 | 2026-09-01 |
| 技术栈 | Flask 3.1 + PyMySQL + MySQL 8 + openpyxl + Jinja2 |

---

## 1. 项目概述

本系统是一个基于 Flask 的**前后端一体化小型 Web 应用**，面向教务管理员，提供：

- 学生信息的**增删改查**、分页列表与多条件模糊搜索；
- 学生数据的 **Excel 批量导入 / 导出**（.xlsx）；
- **学生选课**：学生与课程的多对多关系维护，支持单人全量改选与多人批量选课；
- 管理员**注册 / 登录 / 退出**（基于 session 的简单认证）。

系统不使用任何前端 JS 框架，全部交互通过 HTML 表单（GET / POST）+ 服务端渲染完成。

## 2. 总体架构

### 2.1 架构风格

采用经典的**单体三层架构**，目前所有后端代码集中在单文件 `app.py` 中（未拆分蓝图 Blueprint）：

```
┌─────────────────────────────────────────────────────┐
│  浏览器（HTML 表单 / 链接，无 JS 框架）                │
└───────────────┬─────────────────────────────────────┘
                │ HTTP（GET/POST，表单编码）
┌───────────────▼─────────────────────────────────────┐
│  表现层：Jinja2 模板（templates/）+ CSS（static/）    │
├─────────────────────────────────────────────────────┤
│  控制层：Flask 路由函数（app.py）                     │
│   · 参数解析  · 分页/搜索工具  · 业务逻辑  · 重定向    │
├─────────────────────────────────────────────────────┤
│  数据访问层：db_query / db_query_one / db_execute     │
│   （PyMySQL，参数化 SQL，每次请求短连接，with 自动关闭）│
├─────────────────────────────────────────────────────┤
│  数据库：MySQL 8（decorator_train）                   │
│   admin / student / course / student_course + 触发器  │
└─────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
fill_into_table/
├── app.py                # Flask 应用：全部路由、数据访问、工具函数（约 530 行）
├── config.py             # 真实数据库配置（gitignore，不入库）
├── config_example.py     # 数据库配置模板（入库）
├── requirements.txt      # Python 依赖
├── docs/
│   ├── mysql.md          # 建库建表 SQL（含触发器）
│   └── design.md         # 本文档
├── templates/            # Jinja2 模板
│   ├── _nav.html                # 共享顶部导航栏（被各页面 include）
│   ├── welcome.html             # 欢迎页（/）
│   ├── index.html               # 学生列表 + 搜索结果（/student/list、/student/search）
│   ├── student_insert.html      # 新增学生表单
│   ├── student_update.html      # 修改学生表单
│   ├── student_choose_class.html# 选课页（左课程 / 右学生）
│   ├── student_login.html       # 管理员登录
│   └── student_register.html    # 管理员注册
├── static/css/           # 样式表
│   ├── base.css          # 全局 + 顶部导航
│   ├── form.css          # 卡片式表单（新增/修改/登录/注册）
│   ├── welcome.css / student_list.css / choose_class.css  # 各页面专属
└── export/               # Excel 导出产物目录（运行时生成，gitignore）
```

## 3. 数据库设计

数据库名 `decorator_train`，共 4 张表 + 1 个触发器。建表 SQL 见 [docs/mysql.md](mysql.md)。

### 3.1 ER 关系

```
┌──────────────┐         ┌────────────────────┐         ┌──────────────┐
│    admin     │         │   student_course   │         │    course    │
│──────────────│         │────────────────────│         │──────────────│
│ username (PK)│         │ student_id (PK,FK) │◄──┐     │ course_id(PK)│
│ real_name    │         │ course_id  (PK,FK) │   │     │ course_name  │
│ password_hash│         │ score              │   │     │ teacher      │
└──────────────┘         └─────────┬──────────┘   │     │ credit       │
                                   │              │     └──────┬───────┘
                    (student_id)───┘              └────(course_id)
                                   │                            │
                          ┌────────▼─────────┐                  │
                          │     student      │                  │
                          │──────────────────│                  │
                          │ student_id (PK)  │                  │
                          │ student_name     │                  │
                          │ college          │                  │
                          │ gender           │                  │
                          │ class_condition  │（冗余状态字段）   │
                          └──────────────────┘                  │
```

- `student` 与 `course` 为**多对多**关系，通过中间表 `student_course` 关联；
- 中间表以 `(student_id, course_id)` 为**联合主键**，天然防止同一学生重复选同一门课；
- 两个外键均配置 `ON DELETE CASCADE / ON UPDATE CASCADE`：删除学生或课程时，其选课记录自动级联删除；
- `admin` 表与业务表无外键关系，独立用于认证。

### 3.2 表结构

**admin（管理员）**

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| username | varchar(20) | PK | 登录账号 |
| real_name | varchar(20) | | 真实姓名 |
| password_hash | varchar(200) | NOT NULL | werkzeug 生成的密码哈希（明文不落库） |

**student（学生）**

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| student_id | varchar(4) | PK | 学号 |
| student_name | varchar(4) | | 姓名 |
| college | varchar(20) | | 学院 |
| gender | varchar(2) | | 性别 |
| class_condition | varchar(10) | 默认 '未选课' | 选课情况冗余字段，由触发器/业务代码维护为「未选课 / 已选课」 |

**course（课程）**

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| course_id | varchar(6) | PK | 课程编号 |
| course_name | varchar(30) | NOT NULL | 课程名称 |
| teacher | varchar(10) | | 授课教师 |
| credit | int | | 学分 |

**student_course（选课中间表）**

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| student_id | varchar(4) | PK, FK→student | 学号 |
| course_id | varchar(6) | PK, FK→course | 课程编号 |
| score | decimal(5,2) | | 考试分数（预留，当前业务未使用） |

### 3.3 触发器设计

`tr_after_insert_student_course`（AFTER INSERT ON student_course）：

```sql
create trigger tr_after_insert_student_course
after insert on student_course
for each row
begin
    update student
    set class_condition = '已选课'
    where student_id = NEW.student_id
      and class_condition = '未选课';
end
```

**设计意图**：选课记录一旦插入，数据库层面自动把学生状态置为「已选课」，保证状态与选课数据一致，不依赖应用代码是否记得回写。应用层在批量选课之后另有一条 `UPDATE ... WHERE student_id IN (...)` 作为**兜底**（双保险）；单人退课时则由应用代码显式回写为「未选课」（触发器只覆盖 insert，不覆盖 delete）。

## 4. 后端设计（app.py）

### 4.1 数据访问层

三个通用函数封装 PyMySQL，统一使用 `with` 管理连接/游标，**写操作自动 commit**：

| 函数 | 用途 | 返回 |
| --- | --- | --- |
| `db_query(sql, params)` | 查询多行 | `fetchall()` 元组列表 |
| `db_query_one(sql, params)` | 查询单行/聚合计数 | `fetchone()` 元组 |
| `db_execute(sql, params)` | 增删改 | 无（内部 commit） |

所有 SQL 均使用 `%s` 占位符的**参数化查询**（PyMySQL 转义），避免 SQL 注入。每次调用新建短连接，请求结束即关闭，无需连接池（教学级规模）。

数据库连接参数从 `config.py` 的 `DB_CONFIG` 读取（host/port/user/password/database/charset=utf8mb4），真实配置不入库，`config_example.py` 为模板。

### 4.2 通用工具函数

| 函数 | 职责 |
| --- | --- |
| `get_page()` | 从查询串取 `page`，默认 1（`type=int` 自动转型） |
| `get_search_params()` | 统一取学号/姓名/学院三个搜索词并 `strip()` |
| `calc_total_page(total_count)` | `ceil(总数 / PAGE_SIZE)`，至少为 1 |
| `clamp_page(page, total_page)` | 页码越界钳制：`max(1, min(page, total_page))` |
| `build_student_filter(...)` | 动态拼接 `WHERE` 子句：三个条件均为 `LIKE '%xx%'` 模糊匹配，用 `AND` 连接；无条件时返回空串 |
| `get_user_by_page(page, size)` | 按 `LIMIT offset, size` 取当前页学生 |
| `_cell_to_str(value)` | Excel 单元格转字符串：`None→''`，浮点整数（如学号 1.0）→`'1'`，去空格 |

常量：`PAGE_SIZE = 10`；`STUDENT_COLUMNS`（查询字段串）与 `HEADERS`（中文表头）一一对应，导出 Excel 与列表展示共用。

### 4.3 路由表

| 方法 | 路径 | 函数 | 功能 |
| --- | --- | --- | --- |
| GET | `/` | `index` | 欢迎页 |
| GET | `/student/list` | `student_list` | 学生分页列表 |
| GET | `/student/search` | `student_search` | 多条件模糊搜索（结果复用 index.html） |
| GET | `/student/back` | `back_to_page` | 带页码返回列表 |
| GET | `/student/delete?id=&page=` | `student_delete` | 删除学生（选课记录级联删除） |
| GET | `/student/update?id=&page=` | `student_update` | 修改表单页（查不到返回 404） |
| POST | `/student/update` | `student_update_post` | 执行修改 |
| GET | `/student/insert?page=` | `student_insert_page` | 新增表单页（携带全部已有学号供前端查重） |
| POST | `/student/insert` | `student_insert` | 执行新增（后端学号查重） |
| GET | `/student/to_excel` | `to_excel` | 按当前搜索条件导出 xlsx 到 `export/` |
| POST | `/student/import` | `student_import` | 上传 xlsx 批量导入学生 |
| GET | `/student/choose_class` | `choose_class` | 选课页（课程全列 + 学生分页/搜索/勾选） |
| POST | `/student/choose_class/submit` | `choose_class_submit` | 保存选课结果 |
| GET/POST | `/student/login` | `student_login` | 管理员登录 |
| GET/POST | `/student/register` | `student_register` | 管理员注册 |
| GET | `/student/logout` | `student_logout` | 退出登录 |

### 4.4 核心流程设计

#### 4.4.1 分页列表与搜索

- 列表：`COUNT(*)` 求总数 → 算总页数 → `clamp_page` 防越界 → `LIMIT (page-1)*10, 10` 取数据。
- 搜索：三个搜索词**任意组合**，`build_student_filter` 动态拼 WHERE；无任何条件时直接 `redirect` 回列表，避免空搜索。
- 搜索与列表**渲染同一个模板** `index.html`，通过 `is_search`、`message`（「找到 N 条 / 未找到」）及回填的搜索词区分状态；分页链接携带搜索条件，翻页不丢筛选。
- 所有写操作（增/改/删）完成后都 `redirect` 回 `/student/list?page=N`，**POST-REDIRECT-GET** 模式避免重复提交。

#### 4.4.2 新增 / 修改 / 删除

- **新增**：前后端双重学号查重——GET 页携带全部已存在学号供前端提示；POST 时后端再查一次，重复则返回错误页。插入时不写 `class_condition`，走数据库默认值「未选课」。
- **修改**：GET 按学号查学生记录预填表单；POST 更新姓名/学院/性别（学号为主键不可改）。表单用隐藏域携带 `student_id` 与 `page`，提交后回到原页码。
- **删除**：GET 链接携带 `id` 与 `page`；`DELETE FROM student` 后，中间表选课记录由外键 `ON DELETE CASCADE` 自动清理。

#### 4.4.3 Excel 导出 / 导入（openpyxl）

**导出** `GET /student/to_excel`：

1. 文件名取 `file_name` 参数，默认「学生列表.xlsx」，自动补 `.xlsx` 后缀；
2. `os.path.basename()` 只保留纯文件名，**防止路径穿越**；
3. 复用 `get_search_params()` + `build_student_filter()`，支持「导出当前搜索筛选结果」；
4. `Workbook` 写入表头 `HEADERS` 与数据行，保存到应用目录下 `export/`（不存在则创建）。

**导入** `POST /student/import`：

1. 校验上传文件存在且扩展名为 `.xlsx`；`load_workbook(read_only=True, data_only=True)` 流式读取；
2. 约定首行为表头、第二行起为数据，每行取前 4 列（不足补 `None`）；
3. `_cell_to_str` 处理数字学号（Excel 常把学号读成 `1.0`）；
4. **逐行导入**：学号为空或已存在的行跳过计数，其余插入；最后返回「成功 N 条，跳过 M 条」。

#### 4.4.4 学生选课（多对多，系统最复杂模块）

**页面（GET `/student/choose_class`）**——纯表单、无 JS：

- **左侧**：全部课程一次性列出（复选框 `name="course_ids"`，不分页）；
- **右侧**：学生列表分页 + 模糊搜索，复选框 `name="select_id"`；
- 学生勾选后点「确定选择」以 **GET** 提交刷新，选中状态通过 URL 上多个 `select_id=a&select_id=b` 参数保留；`dict.fromkeys(...)` 去重保序；
- **跨页/跨搜索保留选中项**：不在当前页的已选学生用**隐藏域**携带翻页，避免丢失；「全选本页 / 清空选择」用链接实现；
- **课程回显**：仅当选中**一名**学生时，查 `student_course` 回显其已选课程（勾选态）；选中多名学生时课程区留空（各人已选不同，无法统一回显）。

**保存（POST `/student/choose_class/submit`）**——按选中学生人数分两种策略：

| 场景 | 策略 | SQL | 语义 |
| --- | --- | --- | --- |
| 单选 1 名学生 | **全量替换** | 先 `DELETE FROM student_course WHERE student_id=%s`，再逐条插入本次勾选 | 勾选中没出现的课即**退课**；全部退完则回写 `class_condition='未选课'`，否则「已选课」 |
| 多选学生 | **批量添加** | 双重循环 `INSERT IGNORE INTO student_course ...` | 联合主键冲突自动跳过，**不影响**各生已有选课；触发器置「已选课」+ `UPDATE ... IN (...)` 兜底 |

提交前对学号、课程编号分别做**存在性校验**（过滤非法/已删除数据）并去重；未选学生、学生不存在等情况通过 `msg` 参数重定向回选课页提示。保存后重定向时带回 `student_page` 与搜索条件（表单中以 `q_student_id` 等隐藏域命名，避免与右侧学生勾选框同名冲突），并把有效学生列表作为 `select_id` 传回，保持勾选状态。

#### 4.4.5 管理员认证

- **注册**：校验账号/密码非空、两次密码一致、账号未被占用；密码经 `werkzeug.security.generate_password_hash` 哈希后存入 `admin.password_hash`。
- **登录**：按 username 取哈希，`check_password_hash` 校验；成功则写 `session['admin'] = username`，重定向首页。
- **退出**：`session.pop('admin')` 后回首页。
- 导航栏 `_nav.html` 根据 `session.get('admin')` 显示「欢迎，xxx / 退出登录」或「登录 / 注册」。
- `app.secret_key` 硬编码于 `app.py`（用于 session 签名）。

## 5. 前端设计

- **服务端渲染**：Jinja2 模板，基础风格为卡片式表单 + 顶部导航；无前端 JS 框架，页面间跳转全部靠链接与表单。
- **模板复用**：`_nav.html` 为共享导航，各页 `{% include %}`；导航当前项用 `request.path` 加 `active` 高亮。
- **样式组织**：`base.css`（全局/导航）+ `form.css`（四类表单页共用卡片样式）+ 每个功能页一张专属 CSS，模板中以 `url_for('static', filename='css/xxx.css')` 引用。
- **状态保持靠 HTML 原生机制**：分页/搜索用 GET 查询串；跨页勾选靠隐藏域；POST 后统一重定向（PRG 模式）。

## 6. 安全设计

| 措施 | 实现位置 |
| --- | --- |
| SQL 注入防护 | 全部 SQL 参数化（`%s` 占位 + params 元组），无字符串拼接用户输入 |
| 密码安全 | 明文不落库，werkzeug 哈希存储 + 校验 |
| 路径穿越防护 | 导出文件名经 `os.path.basename()` 处理 |
| 文件上传校验 | 限定 `.xlsx` 扩展名，解析异常捕获 |
| 业务数据校验 | 新增/导入学号查重；选课提交校验学号、课程编号存在性 |
| 外键约束 | 联合主键防重复选课；级联删除防脏数据 |

## 7. 已知局限与改进方向

当前版本为教学/练习项目，以下为可改进点（按优先级）：

1. **登录态未实际强制**：虽有 session 登录，但各业务路由**未加登录校验装饰器**，未登录也可直接访问 `/student/list` 等。建议加 `@login_required` 装饰器统一拦截。
2. **删除操作用 GET**：`/student/delete` 通过 GET 链接触发写操作，不符合 REST 规范且易被 CSRF/预加载触发。建议改 POST + 确认表单。
3. **无 CSRF 防护**：所有 POST 表单无 CSRF token（可引入 Flask-WTF）。
4. **密钥与 debug 模式**：`secret_key` 硬编码、`debug=True` 且监听 `0.0.0.0`，生产环境应改为环境变量配置并关闭 debug。
5. **单文件结构**：`app.py` 集中全部路由，规模增长后建议按蓝图拆分（`student` / `course` / `auth`），数据访问层抽为独立模块。
6. **每次请求新建数据库连接**：高并发下建议引入连接池（如 DBUtils）。
7. **选课 N+1 写入**：批量选课为双重循环逐条 INSERT/SELECT，可改为批量 `INSERT IGNORE ... VALUES (...),(...)` 单条 SQL 提升性能。
8. **score 字段未使用**：中间表预留了成绩字段，尚无成绩录入/查询功能。
9. **输入校验较弱**：学号长度、性别枚举、课程学分等依赖数据库字段长度截断，缺少前端/后端显式校验与友好错误提示。

---

## 附：一次典型请求的调用链（选课保存）

```
浏览器 POST /student/choose_class/submit
  （form: student_id×N[勾选框+隐藏域], course_ids×M, student_page, q_*）
        │
        ▼
choose_class_submit()
  ├─ getlist 收取并去重学生/课程编号
  ├─ 校验学生存在性 → valid_student_ids
  ├─ 校验课程存在性 → valid_course_ids
  ├─ 分支：
  │   ├─ 单人：DELETE 旧选课 → INSERT 新选课 → 回写 class_condition
  │   └─ 多人：循环 INSERT IGNORE → 触发器置「已选课」→ UPDATE 兜底
  └─ redirect → /student/choose_class?select_id=...&msg=...&student_page=...&q_*
        │
        ▼
choose_class()（GET）重新渲染：课程列表 + 学生分页 + 勾选/回显状态
```
