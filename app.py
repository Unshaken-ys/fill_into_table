from flask import Flask, render_template, request, redirect, url_for, session, send_file
from io import BytesIO
import pymysql
import math
import os
from config  import DB_CONFIG
# from config_exemple import DB_CONFIG
from openpyxl import Workbook, load_workbook
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'decorator_train_secret_key'


# 数据库配置


PAGE_SIZE = 10

# 学生表查询字段与表头（保持一致）
STUDENT_COLUMNS = "student_id, student_name, college, gender, class_condition"
HEADERS = ['学号', '姓名', '学院', '性别','选课情况']


# ====== 数据库操作 ======
def db_query(sql, params=None):
    """执行查询并返回所有行"""
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()


def db_query_one(sql, params=None):
    """执行查询并返回第一行"""
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()


def db_execute(sql, params=None):
    """执行写操作（增删改）并提交"""
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()


# ====== 请求参数与分页工具 ======
def get_page():
    return request.args.get('page', 1, type=int)


def get_search_params():
    """统一获取学号/姓名/学院三个搜索条件"""
    return (
        request.args.get('student_id', '').strip(),
        request.args.get('student_name', '').strip(),
        request.args.get('college', '').strip(),
    )


def calc_total_page(total_count):
    return max(1, math.ceil(total_count / PAGE_SIZE))


def clamp_page(page, total_page):
    """边界防止页码越界"""
    return max(1, min(page, total_page))


def _merge_course_draft(select_id, submitted_ids, page_ids):
    """把当前课程页的勾选合并进 session 中的选课草稿（跨页保留，不依赖 JS）。
    当前页上的课程以本次提交为准（未勾选即退选），其它页保持原值。"""
    if not select_id:
        return
    draft = session.get('course_draft') or {}
    selected = set(draft.get(select_id) or [])
    page_set = set(page_ids or [])
    selected = (selected - page_set) | set(submitted_ids or [])
    draft[select_id] = list(selected)
    session['course_draft'] = draft


# ====== 分页获取学生数据 ======
def get_user_by_page(page, page_size):
    offset = (page - 1) * page_size
    rows = db_query(
        f"SELECT {STUDENT_COLUMNS} FROM student LIMIT %s, %s",
        (offset, page_size)
    )
    return rows


# ====== 构造查询条件：学号/姓名/学院均模糊匹配 ======
def build_student_filter(student_id, student_name, college):
    conditions = []
    params = []
    if student_id:
        conditions.append("student_id LIKE %s")
        params.append(f'%{student_id}%')
    if student_name:
        conditions.append("student_name LIKE %s")
        params.append(f'%{student_name}%')
    if college:
        conditions.append("college LIKE %s")
        params.append(f'%{college}%')

    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_sql, params


# ====== 起始欢迎界面 ======
@app.route('/')
def index():
    return render_template('welcome.html')


# ====== 学生列表（分页，需登录） ======
@app.route('/student/list')
def student_list():
    page = get_page()

    total_count = db_query_one("SELECT COUNT(*) FROM student")[0]
    total_page = calc_total_page(total_count)
    page = clamp_page(page, total_page)

    value_list = get_user_by_page(page, PAGE_SIZE)

    return render_template(
        'index.html',
        key_list=HEADERS,
        value_list=value_list,
        page=page,
        total_page=total_page
    )


# ====== 搜索 ======
@app.route('/student/search')
def student_search():
    student_id, student_name, college = get_search_params()
    page = get_page()

    # 至少输入一个搜索条件，否则直接回到学生列表
    if not student_id and not student_name and not college:
        return redirect('/student/list')

    # 动态拼接查询条件：学号/姓名/学院均模糊匹配
    where_sql, params = build_student_filter(student_id, student_name, college)

    total_count = db_query_one(f"SELECT COUNT(*) FROM student{where_sql}", params)[0]
    total_page = calc_total_page(total_count)
    page = clamp_page(page, total_page)

    offset = (page - 1) * PAGE_SIZE
    rows = db_query(
        f"SELECT {STUDENT_COLUMNS} FROM student{where_sql} LIMIT %s, %s",
        params + [offset, PAGE_SIZE]
    )

    message = f'找到 {total_count} 条记录' if total_count else '未找到匹配的学生'

    # 搜索结果直接渲染在 index 页面
    return render_template('index.html',
                           key_list=HEADERS, value_list=rows,
                           page=page, total_page=total_page, message=message,
                           student_id=student_id, student_name=student_name, college=college,
                           is_search=True)


# ====== 返回指定页面 ======
@app.route('/student/back')
def back_to_page():
    page = get_page()
    return redirect(f'/student/list?page={page}')


# ====== 删除 ======
@app.route('/student/delete')
def student_delete():
    student_id = request.args.get('id')
    page = get_page()

    db_execute("DELETE FROM student WHERE student_id = %s", (student_id,))

    return redirect(f'/student/list?page={page}')


# ====== 修改界面（GET） ======
@app.route('/student/update', methods=['GET'])
def student_update():
    student_id = request.args.get('id')
    page = get_page()

    if not student_id:
        return "缺少学生ID", 400

    student = db_query_one(
        f"SELECT {STUDENT_COLUMNS} FROM student WHERE student_id = %s",
        (student_id,)
    )

    if not student:
        return "学生不存在", 404

    return render_template('student_update.html', student=student, page=page)


# ====== 执行修改（POST） ======
@app.route('/student/update', methods=['POST'])
def student_update_post():
    # 优先从表单取（隐藏字段），兼容从 URL 参数取
    student_id = request.form.get('student_id') or request.args.get('id')
    page = get_page()

    student_name = request.form.get('student_name')
    college = request.form.get('college')
    gender = request.form.get('gender')

    db_execute(
        "UPDATE student SET student_name=%s, college=%s, gender=%s WHERE student_id=%s",
        (student_name, college, gender, student_id)
    )

    return redirect(f'/student/list?page={page}')


# ====== 新增界面（GET）======
@app.route('/student/insert', methods=['GET'])
def student_insert_page():
    page = get_page()

    rows = db_query("SELECT student_id FROM student")
    # 转成一维列表
    student_id_list = [row[0] for row in rows]

    return render_template('student_insert.html', page=page, student_id_list=student_id_list)


# ====== 执行新增（POST） ======
@app.route('/student/insert', methods=['POST'])
def student_insert():
    page = get_page()
    student_id = request.form.get('student_id')
    student_name = request.form.get('student_name')
    college = request.form.get('college')
    gender = request.form.get('gender')

    # 后端查重
    if db_query_one("SELECT 1 FROM student WHERE student_id = %s", (student_id,)):
        return "学号重复，无法新增！<a href='javascript:history.back()'>返回</a>"

    db_execute(
        "INSERT INTO student (student_id, student_name, college, gender) VALUES (%s, %s, %s, %s)",
        (student_id, student_name, college, gender)
    )

    return redirect(f'/student/list?page={page}')


# ====== 导出excel ======
@app.route('/student/to_excel')
def to_excel():
    # 文件名（表单为 GET 提交，参数在 URL 上）
    file_name = request.args.get('file_name', '').strip()

    # 搜索条件下发（在搜索页导出时携带，用于导出筛选结果）
    student_id, student_name, college = get_search_params()

    if not file_name:
        file_name = '学生列表.xlsx'
    if not file_name.endswith('.xlsx'):
        file_name += '.xlsx'

    # 仅保留纯文件名，防止路径穿越
    file_name = os.path.basename(file_name)

    where_sql, params = build_student_filter(student_id, student_name, college)

    rows = db_query(f"SELECT {STUDENT_COLUMNS} FROM student{where_sql}", params)

    # 用 openpyxl 生成 Excel 文件
    wb = Workbook()
    ws = wb.active
    ws.title = '学生列表'
    ws.append(HEADERS)
    for row in rows:
        ws.append(list(row))

    # 保存到本地 export 目录
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'export')
    os.makedirs(export_dir, exist_ok=True)

    file_path = os.path.join(export_dir, file_name)
    wb.save(file_path)

    return f"导出成功！文件已写入：{file_path}<br><a href='javascript:history.back()'>返回</a>"


# ====== 学生选课系统（GET：选课界面） ======
@app.route('/student/choose_class')
def choose_class():
    # 左侧：课程列表（课程编号、课程名称）—— 分页
    course_page = request.args.get('course_page', 1, type=int)
    course_total = db_query_one("SELECT COUNT(*) FROM course")[0]
    course_total_page = calc_total_page(course_total)
    course_page = clamp_page(course_page, course_total_page)
    course_offset = (course_page - 1) * PAGE_SIZE
    courses = db_query(
        "SELECT course_id, course_name FROM course ORDER BY course_id LIMIT %s, %s",
        (course_offset, PAGE_SIZE)
    )

    # 右侧：学生列表（学号、姓名、学院）—— 支持模糊查询 + 分页
    student_id, student_name, college = get_search_params()
    where_sql, params = build_student_filter(student_id, student_name, college)

    student_page = request.args.get('student_page', 1, type=int)
    student_total = db_query_one(
        f"SELECT COUNT(*) FROM student{where_sql}", params)[0]
    student_total_page = calc_total_page(student_total)
    student_page = clamp_page(student_page, student_total_page)
    student_offset = (student_page - 1) * PAGE_SIZE
    students = db_query(
        f"SELECT student_id, student_name, college FROM student{where_sql} "
        f"ORDER BY student_id LIMIT %s, %s",
        params + [student_offset, PAGE_SIZE]
    )

    # 已保存到数据库的选课记录（供未编辑过的学生显示已选状态）
    selected_map = {}
    for sid, cid in db_query("SELECT student_id, course_id FROM student_course"):
        selected_map.setdefault(sid, []).append(cid)

    # 选课提交后跳回时携带：当前学生与提示信息
    select_id = request.args.get('select_id', '').strip()
    message = request.args.get('msg', '').strip()

    search_message = f'找到 {student_total} 条学生记录' if (student_id or student_name or college) else ''

    # 以当前学生的草稿覆盖已保存记录（草稿里的内容是用户在各页的最新勾选）
    if select_id:
        draft = session.get('course_draft') or {}
        if select_id in draft:
            selected_map[select_id] = draft[select_id]

    return render_template(
        'student_choose_class.html',
        courses=courses,
        students=students,
        selected_map=selected_map,
        select_id=select_id,
        message=message,
        student_id=student_id,
        student_name=student_name,
        college=college,
        search_message=search_message,
        course_page=course_page,
        course_total_page=course_total_page,
        student_page=student_page,
        student_total_page=student_total_page,
        page_size=PAGE_SIZE,
    )


# ====== 切换学生（POST）：保存当前学生本页勾选进草稿，再按新学生重定向 ======
@app.route('/student/choose_class/switch', methods=['POST'])
def choose_class_switch():
    current_select_id = request.form.get('current_select_id', '').strip()
    new_select_id = request.form.get('new_student_id', '').strip()
    submitted_ids = request.form.getlist('course_ids')
    page_ids = request.form.getlist('page_course_ids')
    if current_select_id:
        _merge_course_draft(current_select_id, submitted_ids, page_ids)

    return redirect(url_for(
        'choose_class',
        select_id=new_select_id,
        course_page=request.form.get('course_page', 1, type=int),
        student_page=request.form.get('student_page', 1, type=int),
        student_id=request.form.get('q_student_id', '').strip(),
        student_name=request.form.get('q_student_name', '').strip(),
        college=request.form.get('q_college', '').strip(),
    ))


# ====== 课程翻页（POST）：先把当前页勾选合并进草稿，再重定向到目标页 ======
@app.route('/student/choose_class/course_page', methods=['POST'])
def choose_class_course_page():
    select_id = request.form.get('student_id', '').strip()
    submitted_ids = request.form.getlist('course_ids')
    page_ids = request.form.getlist('page_course_ids')
    _merge_course_draft(select_id, submitted_ids, page_ids)

    return redirect(url_for(
        'choose_class',
        select_id=select_id,
        course_page=request.form.get('target_page', 1, type=int),
        student_page=request.form.get('student_page', 1, type=int),
        student_id=request.form.get('q_student_id', '').strip(),
        student_name=request.form.get('q_student_name', '').strip(),
        college=request.form.get('q_college', '').strip(),
    ))


# ====== 学生选课系统（POST：保存选课结果） ======
@app.route('/student/choose_class/submit', methods=['POST'])
def choose_class_submit():
    student_id = request.form.get('student_id', '').strip()
    submitted_ids = request.form.getlist('course_ids')
    page_ids = request.form.getlist('page_course_ids')

    if not student_id:
        return redirect(url_for('choose_class', msg='请先选择一名学生'))

    if not db_query_one("SELECT 1 FROM student WHERE student_id = %s", (student_id,)):
        return redirect(url_for('choose_class', msg='学生不存在'))

    # 合并当前页勾选项，得到该学生所有页的最终选课集合
    _merge_course_draft(student_id, submitted_ids, page_ids)
    course_ids = (session.get('course_draft') or {}).get(student_id, [])
    course_ids = [cid for cid in course_ids if db_query_one(
        "SELECT 1 FROM course WHERE course_id = %s", (cid,))]

    # 该学生当前已选课程编号
    existing_ids = [row[0] for row in db_query(
        "SELECT course_id FROM student_course WHERE student_id = %s", (student_id,))]

    # 退选：已选但本次未勾选
    removed = 0
    for cid in existing_ids:
        if cid not in course_ids:
            db_execute(
                "DELETE FROM student_course WHERE student_id = %s AND course_id = %s",
                (student_id, cid)
            )
            removed += 1

    # 新增：本次勾选但尚未选
    added = 0
    for cid in course_ids:
        if cid in existing_ids:
            continue
        db_execute(
            "INSERT INTO student_course (student_id, course_id) VALUES (%s, %s)",
            (student_id, cid)
        )
        added += 1

    # 退选后回写选课状态：仍有课程则「已选课」，全部退掉则恢复「未选课」
    remaining = db_query_one(
        "SELECT COUNT(*) FROM student_course WHERE student_id = %s", (student_id,))[0]
    db_execute(
        "UPDATE student SET class_condition = %s WHERE student_id = %s",
        ('已选课' if remaining else '未选课', student_id)
    )

    # 保存成功，清掉该学生的草稿
    draft = session.get('course_draft') or {}
    draft.pop(student_id, None)
    session['course_draft'] = draft

    msg = f'选课已保存：新增 {added} 门，退选 {removed} 门'
    # 回到提交前所在的分页/搜索条件
    return redirect(url_for(
        'choose_class',
        select_id=student_id,
        msg=msg,
        course_page=request.form.get('course_page', 1, type=int),
        student_page=request.form.get('student_page', 1, type=int),
        student_id=request.form.get('q_student_id', '').strip(),
        student_name=request.form.get('q_student_name', '').strip(),
        college=request.form.get('q_college', '').strip(),
    ))
# ====== 管理员登录 ======
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        row = db_query_one("SELECT password_hash FROM admin WHERE username = %s", (username,))
        if row and check_password_hash(row[0], password):
            session['admin'] = username
            return redirect('/')

        return render_template('student_login.html', message='账号或密码错误')

    return render_template('student_login.html')


# ====== 管理员注册 ======
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        real_name = request.form.get('real_name', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not password:
            return render_template('student_register.html', message='账号和密码不能为空')
        if password != password2:
            return render_template('student_register.html', message='两次输入的密码不一致')
        if db_query_one("SELECT 1 FROM admin WHERE username = %s", (username,)):
            return render_template('student_register.html', message='账号已存在')

        db_execute(
            "INSERT INTO admin (username, real_name, password_hash) VALUES (%s, %s, %s)",
            (username, real_name, generate_password_hash(password))
        )
        return render_template('student_login.html', message='注册成功，请登录')

    return render_template('student_register.html')
# ====== 导入信息（Excel 批量导入学生） ======
# 首行为表头（学号、姓名、学院、性别），第二行起为数据；选课情况由系统维护

#处理
def _cell_to_str(value):
    """把 Excel 单元格值转成去空格的字符串；数字学号（如 1.0）转成 '1'。"""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


@app.route('/student/import', methods=['POST'])
def student_import():
    f = request.files.get('uploadFile')

    if not f or not f.filename or not f.filename.endswith('.xlsx'):
        return "请选择 .xlsx 格式文件！<a href='javascript:history.back()'>返回</a>"

    try:
        wb = load_workbook(f, read_only=True, data_only=True)
    except Exception:
        return "Excel 文件解析失败！<a href='javascript:history.back()'>返回</a>"

    # 逐行导入：学号为空或已存在的行直接跳过
    success = 0
    skip = 0
    for row in wb.active.iter_rows(min_row=2, values_only=True):
        cells = (list(row) + [None] * 4)[:4]
        student_id, student_name, college, gender = (_cell_to_str(v) for v in cells)

        if not student_id or db_query_one(
                "SELECT 1 FROM student WHERE student_id = %s", (student_id,)):
            skip += 1
            continue

        db_execute(
            "INSERT INTO student (student_id, student_name, college, gender) "
            "VALUES (%s, %s, %s, %s)",
            (student_id, student_name, college, gender)
        )
        success += 1

    wb.close()
    return f"导入完成：成功 {success} 条，跳过 {skip} 条（空行或学号重复）。" \
           f"<br><a href='javascript:history.back()'>返回</a>"





# ====== 退出登录 ======
@app.route('/student/logout')
def student_logout():
    session.pop('admin', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
