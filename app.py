import streamlit as st
import sqlite3
import hashlib

# -----------------------------------------------------------------------------
# 1. 数据库基础配置与操作函数
# -----------------------------------------------------------------------------
DB_FILE = 'users.db'

def get_db_connection():
    """建立与 SQLite 数据库的连接"""
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    """初始化用户表，如果数据库为空则自动创建管理员账号和初始用户"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            role TEXT
        )
    ''')
    
    # 检查是否已包含默认管理员账号，若无则初始化
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        # 默认管理员账号：admin，默认密码：admin123
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES ('admin', ?, 'admin')", (admin_hash,))
        
        # 默认测试普通用户：user1，默认密码：123456
        user_hash = hashlib.sha256("123456".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES ('user1', ?, 'user')", (user_hash,))
        
        conn.commit()
    conn.close()

def hash_password(password):
    """使用 SHA-256 对密码进行哈希加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """校验用户登录"""
    conn = get_db_connection()
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_users():
    """获取所有注册用户的用户名列表"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def update_user_password(target_user, new_password):
    """更新指定用户的密码"""
    conn = get_db_connection()
    c = conn.cursor()
    new_hash = hash_password(new_password)
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, target_user))
    conn.commit()
    conn.close()

# 执行数据库初始化
init_db()

# -----------------------------------------------------------------------------
# 2. 页面基础设置与 Session 状态初始化
# -----------------------------------------------------------------------------
st.set_page_config(page_title="账号与权限管理系统", page_icon="🔑", layout="centered")

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
    st.title("🔐 系统登录")
    
    with st.form("login_form"):
        username_input = st.text_input("用户名")
        password_input = st.text_input("密码", type="password")
        login_btn = st.form_submit_button("登录")
        
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
# 4. 登录后的主界面
# -----------------------------------------------------------------------------
else:
    # 侧边栏用户状态与退出按钮
    st.sidebar.markdown(f"**当前登录用户**：`{st.session_state['username']}`")
    st.sidebar.markdown(f"**当前用户角色**：`{st.session_state['role']}`")
    
    if st.sidebar.button("退出登录"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.session_state['role'] = None
        st.rerun()

    st.title("🎉 欢迎进入主系统")

    # -------------------------------------------------------------------------
    # 5. 管理员专属功能：修改所有人账号密码
    # -------------------------------------------------------------------------
    if st.session_state['role'] == 'admin':
        st.markdown("---")
        st.header("⚙️ 管理员控制台：重置账号密码")
        
        # 1. 动态获取系统内所有用户
        all_users = get_all_users()
        
        # 2. 表单控制区
        with st.form("admin_reset_password_form"):
            selected_user = st.selectbox("选择要修改密码的目标用户", all_users)
            new_password = st.text_input("设置新密码", type="password")
            confirm_password = st.text_input("再次确认新密码", type="password")
            
            submit_btn = st.form_submit_button("确认修改密码")
            
        # 3. 表单提交校验
        if submit_btn:
            if not new_password or not confirm_password:
                st.error("密码不能为空！")
            elif new_password != confirm_password:
                st.error("两次输入的密码不一致！")
            elif len(new_password) < 6:
                st.warning("为保证安全，密码长度不能少于 6 位！")
            else:
                update_user_password(selected_user, new_password)
                st.success(f"✅ 已成功将用户 **{selected_user}** 的密码重置！")

    # -------------------------------------------------------------------------
    # 普通用户界面显示
    # -------------------------------------------------------------------------
    else:
        st.info("您当前为普通用户，无权访问管理员后台。")