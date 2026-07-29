import streamlit as st
import sqlite3
import hashlib
import pandas as pd
from datetime import date

# -----------------------------------------------------------------------------
# 1. 数据库基础配置与初始化
# -----------------------------------------------------------------------------
DB_FILE = 'data.db'

def get_db_connection():
    """建立与 SQLite 数据库的连接"""
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    """初始化用户表与招聘数据表"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. 创建用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            role TEXT
        )
    ''')
    
    # 2. 创建招聘数据表
    c.execute('''
        CREATE TABLE IF NOT EXISTS recruitment_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT,
            project_name TEXT,
            interviews_count INTEGER,
            offers_count INTEGER,
            onboarding_count INTEGER,
            operator TEXT
        )
    ''')
    
    # 3. 检查并初始化默认管理员和普通账号
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES ('admin', ?, 'admin')", (admin_hash,))
        
        user_hash = hashlib.sha256("123456".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES ('user1', ?, 'user')", (user_hash,))
        
        conn.commit()
    conn.close()

def hash_password(password):
    """SHA-256 密码哈希加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """验证用户登录"""
    conn = get_db_connection()
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_users():
    """获取所有注册用户列表"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def update_user_password(target_user, new_password):
    """管理员修改指定用户的密码"""
    conn = get_db_connection()
    c = conn.cursor()
    new_hash = hash_password(new_password)
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, target_user))
    conn.commit()
    conn.close()

# 执行初始化
init_db()

# -----------------------------------------------------------------------------
# 2. 页面基础配置与 Session 状态管理
# -----------------------------------------------------------------------------
st.set_page_config(page_title="招聘数据管理与权限系统", page_icon="📊", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'role' not in st.session_state:
    st.session_state['role'] = None

# -----------------------------------------------------------------------------
# 3. 登录界面
# -----------------------------------------------------------------------------
if not st.session_state['logged_in']:
    st.title("🔐 招聘业务系统 - 用户登录")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_form"):
            username_input = st.text_input("用户名")
            password_input = st.text_input("密码", type="password")
            login_btn = st.form_submit_button("登录系统")
            
            if login_btn:
                if not username_input or not password_input:
                    st.error("请输入用户名和密码！")
                else:
                    role = verify_user(username_input, password_input)
                    if role:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username_input
                        st.session_state['role'] = role
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误！")

        st.info("💡 **默认管理员账号**：`admin` / **密码**：`admin123`  \n💡 **默认普通账号**：`user1` / **密码**：`123456`")

# -----------------------------------------------------------------------------
# 4. 系统主界面（登录后）
# -----------------------------------------------------------------------------
else:
    # 侧边栏
    st.sidebar.title("📌 控制面板")
    st.sidebar.markdown(f"**当前用户**：`{st.session_state['username']}`")
    st.sidebar.markdown(f"**身份角色**：`{st.session_state['role']}`")
    
    if st.sidebar.button("退出登录"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.session_state['role'] = None
        st.rerun()

    # 选项卡导航
    if st.session_state['role'] == 'admin':
        tab1, tab2, tab3 = st.tabs(["📊 招聘数据汇总", "📝 新增招聘数据", "⚙️ 管理员设置（修改账号密码）"])
    else:
        tab1, tab2 = st.tabs(["📊 招聘数据汇总", "📝 新增招聘数据"])

    # -------------------------------------------------------------------------
    # TAB 1: 招聘数据汇总查看
    # -------------------------------------------------------------------------
    with tab1:
        st.header("📊 招聘数据汇总与看板")
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM recruitment_data", conn)
        conn.close()

        if df.empty:
            st.warning("目前暂无招聘数据，请先前往【新增招聘数据】录入！")
        else:
            # 关键指标展示
            col1, col2, col3 = st.columns(3)
            col1.metric("总面试人数", int(df['interviews_count'].sum()))
            col2.metric("总发 Offer 数", int(df['offers_count'].sum()))
            col3.metric("总入职人数", int(df['onboarding_count'].sum()))

            st.markdown("---")
            st.subheader("详细数据明细表")
            st.dataframe(df, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: 新增招聘数据录入
    # -------------------------------------------------------------------------
    with tab2:
        st.header("📝 录入每日招聘数据")
        with st.form("recruitment_form"):
            rec_date = st.date_input("记录日期", date.today())
            project_name = st.text_input("项目名称", placeholder="例如：电信宿州招聘项目")
            interviews = st.number_input("面试人数", min_value=0, step=1)
            offers = st.number_input("Offer 发送数", min_value=0, step=1)
            onboarding = st.number_input("实际入职人数", min_value=0, step=1)
            
            submit_rec = st.form_submit_button("提交数据")

            if submit_rec:
                if not project_name:
                    st.error("项目名称不能为空！")
                else:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute('''
                        INSERT INTO recruitment_data (record_date, project_name, interviews_count, offers_count, onboarding_count, operator)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (str(rec_date), project_name, interviews, offers, onboarding, st.session_state['username']))
                    conn.commit()
                    conn.close()
                    st.success("招聘数据录入成功！")
                    st.rerun()

    # -------------------------------------------------------------------------
    # TAB 3: 管理员专属功能 — 修改所有人账号密码
    # -------------------------------------------------------------------------
    if st.session_state['role'] == 'admin':
        with tab3:
            st.header("⚙️ 管理员控制台：重置所有人账号密码")
            
            all_users = get_all_users()
            
            with st.form("admin_pwd_reset_form"):
                selected_user = st.selectbox("选择要重置密码的目标账号", all_users)
                new_pwd = st.text_input("请输入新密码", type="password")
                confirm_pwd = st.text_input("请再次确认新密码", type="password")
                
                reset_btn = st.form_submit_button("确认重置密码")
                
                if reset_btn:
                    if not new_pwd or not confirm_pwd:
                        st.error("密码输入不能为空！")
                    elif new_pwd != confirm_pwd:
                        st.error("两次输入的密码不一致！")
                    elif len(new_pwd) < 6:
                        st.warning("密码安全长度不能低于 6 位！")
                    else:
                        update_user_password(selected_user, new_pwd)
                        st.success(f"🎉 成功将账号 **{selected_user}** 的密码重置！")