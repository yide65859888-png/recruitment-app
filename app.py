import datetime
import io
import sqlite3
import pandas as pd
from PIL import Image
import streamlit as st

# ---------------------------------------------------------
# 1. 页面基本配置
# ---------------------------------------------------------
st.set_page_config(
    page_title="招聘全链路数据监控与智能预警系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stDeployButton {display:none;}
    .main-header {font-size:22px; font-weight:bold; color:#1F4E79; margin-bottom:10px;}
    
    .mobile-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 15px;
    }
    
    .alert-card-danger {background-color:#FFD2D2; border-left:6px solid #D8000C; padding:12px; border-radius:4px; margin-bottom:10px;}
    .alert-card-warning {background-color:#FFF3CD; border-left:6px solid #856404; padding:12px; border-radius:4px; margin-bottom:10px;}
    
    .rank-box {
        background: linear-gradient(135deg, #ffffff 0%, #f1f3f5 100%);
        border-radius: 8px;
        padding: 10px;
        border: 1px solid #ced4da;
        margin-bottom: 15px;
    }
    .rank-title {
        font-size: 14px;
        font-weight: bold;
        color: #1F4E79;
        margin-bottom: 8px;
        border-bottom: 2px solid #1F4E79;
        padding-bottom: 3px;
    }
    .rank-item-top1 { font-weight: bold; color: #D4AF37; margin: 3px 0; font-size: 12px; }
    .rank-item-top2 { font-weight: bold; color: #708090; margin: 3px 0; font-size: 12px; }
    .rank-item-top3 { font-weight: bold; color: #B87333; margin: 3px 0; font-size: 12px; }
    .rank-item-normal { font-weight: normal; color: #495057; margin: 3px 0; font-size: 12px; }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 45px;
        font-weight: bold;
    }
    
    .user-badge {
        padding: 6px 12px;
        background-color: #e9ecef;
        border-radius: 20px;
        font-size: 13px;
        font-weight: bold;
        color: #1F4E79;
        margin-bottom: 15px;
    }
</style>
""",
    unsafe_allow_html=True,
)

DEFAULT_MEMBERS = [
    "储郑燃", "刘春雨", "唐凯", "孙衍", "王俊丽",
    "王小兰", "王肖", "王莉莹", "栗阳阳", "罗悦", "薛丽丽"
]

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
MAX_DAILY_UPLOADS = 3
DB_PATH = "recruitment_data.db"

# ---------------------------------------------------------
# 2. 数据库纯净初始化
# ---------------------------------------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute("""CREATE TABLE IF NOT EXISTS platform_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT, 
                        employee_name TEXT, 
                        platform_version TEXT,
                        seen_me INTEGER DEFAULT 0, 
                        i_communicated INTEGER DEFAULT 0,
                        received_resumes INTEGER DEFAULT 0, 
                        exchanged_contact INTEGER DEFAULT 0,
                        exchanged_phone INTEGER DEFAULT 0, 
                        proposed_interview INTEGER DEFAULT 0,
                        accepted_interview INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")

        c.execute("""CREATE TABLE IF NOT EXISTS performance_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT, employee_name TEXT,
                        inner_invites INTEGER DEFAULT 0, outer_invites INTEGER DEFAULT 0, invites INTEGER DEFAULT 0,
                        inner_interviews INTEGER DEFAULT 0, outer_interviews INTEGER DEFAULT 0, interviews INTEGER DEFAULT 0,
                        inner_trainees INTEGER DEFAULT 0, outer_trainees INTEGER DEFAULT 0, trainees INTEGER DEFAULT 0,
                        month_inner_invites INTEGER DEFAULT 0, month_outer_invites INTEGER DEFAULT 0, month_invites INTEGER DEFAULT 0,
                        month_inner_interviews INTEGER DEFAULT 0, month_outer_interviews INTEGER DEFAULT 0, month_interviews INTEGER DEFAULT 0,
                        month_inner_trainees INTEGER DEFAULT 0, month_outer_trainees INTEGER DEFAULT 0, month_trainees INTEGER DEFAULT 0
                    )""")

        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        real_name TEXT,
                        role TEXT DEFAULT 'employee'
                    )""")
        
        c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (username, password, real_name, role) VALUES ('admin', 'admin123', '系统管理员', 'admin')")
        
        for name in DEFAULT_MEMBERS:
            c.execute("SELECT COUNT(*) FROM users WHERE real_name = ?", (name,))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO users (username, password, real_name, role) VALUES (?, '123456', ?, 'employee')", (name, name))
        conn.commit()

init_db()

def get_all_employee_names():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT real_name FROM users WHERE role = 'employee'")
        names = [r[0] for r in c.fetchall()]
    return names if names else DEFAULT_MEMBERS

# ---------------------------------------------------------
# 3. 登录认证逻辑与 Session 状态
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.real_name = ""
    st.session_state.role = ""

def verify_login(username, password):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT username, real_name, role FROM users WHERE username = ? AND password = ?", (username, password))
        return c.fetchone()

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #1F4E79;'>🔒 招聘全链路监控系统 - 用户登录</h2>", unsafe_allow_html=True)
    
    login_col1, login_col2, login_col3 = st.columns([1, 1.5, 1])
    with login_col2:
        st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
        login_user = st.text_input("账号 / 员工姓名")
        login_pwd = st.text_input("密码", type="password")
        btn_login = st.button("🔐 登录系统", type="primary")
        
        if btn_login:
            user_info = verify_login(login_user, login_pwd)
            if user_info:
                st.session_state.logged_in = True
                st.session_state.username = user_info[0]
                st.session_state.real_name = user_info[1]
                st.session_state.role = user_info[2]
                st.success("登录成功！正在跳转...")
                st.rerun()
            else:
                st.error("❌ 账号或密码错误！(默认员工密码为 123456，管理员账号 admin/admin123)")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------
# 4. 辅助函数与 Mock OCR
# ---------------------------------------------------------
def mock_employee_ocr(image):
    return {
        "seen_me": 593, "i_communicated": 319, "received_resumes": 29,
        "exchanged_contact": 14, "exchanged_phone": 8,
        "proposed_interview": 5, "accepted_interview": 3,
    }

def mock_supervisor_ocr_daily(image, members):
    return pd.DataFrame({
        "员工姓名": members,
        "内单邀约": [4, 12, 1, 2, 8, 2, 1, 3, 0, 6, 4][:len(members)],
        "外单邀约": [2, 5, 1, 1, 4, 1, 0, 1, 0, 3, 2][:len(members)],
        "当日邀约总计": [6, 17, 2, 3, 12, 3, 1, 4, 0, 9, 6][:len(members)],
        "内单到面": [7, 15, 6, 8, 20, 6, 12, 14, 0, 15, 13][:len(members)],
        "外单到面": [4, 6, 3, 5, 10, 3, 6, 6, 0, 8, 7][:len(members)],
        "当日到面总计": [11, 21, 9, 13, 30, 9, 18, 20, 0, 23, 20][:len(members)],
        "内单参培": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0][:len(members)],
        "外单参培": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0][:len(members)],
        "当日参培总计": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0][:len(members)],
    })

def mock_supervisor_ocr_monthly(image, members):
    return pd.DataFrame({
        "员工姓名": members,
        "月内单邀约": [80, 140, 55, 60, 120, 50, 40, 70, 10, 90, 85][:len(members)],
        "月外单邀约": [40, 70, 30, 30, 60, 25, 20, 40, 5, 50, 45][:len(members)],
        "月度邀约总计": [120, 210, 85, 90, 180, 75, 60, 110, 15, 140, 130][:len(members)],
        "月内单到面": [50, 100, 32, 40, 85, 30, 22, 45, 3, 60, 55][:len(members)],
        "月外单到面": [30, 50, 18, 20, 45, 15, 13, 25, 2, 35, 30][:len(members)],
        "月度到面总计": [80, 150, 50, 60, 130, 45, 35, 70, 5, 95, 85][:len(members)],
        "月内单参培": [8, 15, 4, 5, 12, 3, 2, 7, 0, 10, 8][:len(members)],
        "月外单参培": [4, 7, 2, 3, 7, 2, 2, 4, 0, 5, 4][:len(members)],
        "月度参培总计": [12, 22, 6, 8, 19, 5, 4, 11, 0, 15, 12][:len(members)],
    })

def get_upload_count_today(date_str, emp_name, platform):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM platform_data WHERE date = ? AND employee_name = ? AND platform_version = ?",
            (date_str, emp_name, platform)
        )
        return c.fetchone()[0]

def run_alert_engine(df_summary, is_monthly=False):
    alerts = []
    for _, row in df_summary.iterrows():
        name = row["员工姓名"]
        comm = row.get("主动沟通", 0)
        resumes = row.get("收获简历", 0)
        wx = row.get("交换微信", 0)
        invites = row.get("单月累计邀约", 0) if is_monthly else row.get("当日邀约", 0)
        interviews = row.get("单月累计到面", 0) if is_monthly else row.get("当日到面", 0)
        trainees = row.get("单月累计参培", 0) if is_monthly else row.get("当日参培", 0)
        time_tag = "全月" if is_monthly else "当日"

        if is_monthly and invites < 30:
            alerts.append({
                "name": name, "level": "🚨 产能预警：月度招聘产能严重不足",
                "issue": f"{time_tag}累计邀约仅 {invites} 人，到面 {interviews} 人",
                "data": f"月邀约 {invites} 人 ➔ 到面 {interviews} 人 ➔ 参培 {trainees} 人",
                "reason": "月度整体招聘动作极少，业务活动量严重不达标，未能建立起有效的招聘漏斗基数",
                "action": "建议拉通一对一辅导，明确每日打招呼、私域跟进与约面的最低过程 KPI",
            })

        if comm > 100 and (resumes + wx) < 30:
            alerts.append({
                "name": name, "level": "🚨 触达预警：开场白与画像匹配度待优化",
                "issue": f"{time_tag}主动沟通 {comm} 人，但私域仅获取 {wx} 个微信",
                "data": f"沟通 {comm} 人 ➔ 微信仅 {wx} 人",
                "reason": "打招呼量较大但私域留存偏低，可能存在推送职位与求职者意向不匹配或交流话术吸引力不足",
                "action": "建议抽查交流话术，优化精准画像筛选，提升有效沟通率",
            })

        min_invites = 5 if is_monthly else 1
        if wx >= 10 and invites < min_invites:
            alerts.append({
                "name": name, "level": "⚠️ 跟进预警：私域候选人转化滞后",
                "issue": f"{time_tag}获取微信 {wx} 个，但实际邀约仅 {invites} 人",
                "data": f"微信 {wx} 人 ➔ 邀约 {invites} 人",
                "reason": "私域留存资源较丰富但尚未形成有效约面，可能存在跟进及时性不足或约面促成临门一脚欠缺",
                "action": "建议梳理私域待跟进列表，通过电话复核提高直接邀约率",
            })

        trainee_rate = (trainees / interviews * 100) if interviews > 0 else 0
        if interviews >= (15 if is_monthly else 20) and (trainees == 0 or trainee_rate < 10.0):
            alerts.append({
                "name": name, "level": "🚨 转化预警：到面至参培漏斗断层",
                "issue": f"{time_tag}到面 {interviews} 人，但参培仅 {trainees} 人 (转化率仅 {trainee_rate:.1f}%)",
                "data": f"到面 {interviews} 人 ➔ 参培仅 {trainees} 人",
                "reason": "到场人数较多但后续参培流失率极高，可能存在前期求职意向确认不足、或现场宣讲/面试预期管理差距较大",
                "action": "建议加强现场面试反馈复盘，提高前期邀约精准度与求职意向深度确认",
            })

        if invites > 0 and interviews >= (invites * 2):
            alerts.append({
                "name": name, "level": "🛠️ 规范预警：过程数据同步延迟",
                "issue": f"{time_tag}到面数({interviews}) 显著高于 邀约记录数({invites})",
                "data": f"到面转化率异常达到 {((interviews/invites)*100):.1f}%",
                "reason": "可能存在事前邀约数据录入不及时、求职者到场后才集中补录的情况",
                "action": "建议规范“事前录入邀约、事后核到面”的数据更新节奏，确保过程数据实时准确",
            })
    return alerts

def render_full_ranking(df, col_name, title_name, unit=""):
    df_sorted = df.sort_values(by=col_name, ascending=False).reset_index(drop=True)
    html = f'<div class="rank-box"><div class="rank-title">🏆 {title_name}</div>'
    for i in range(len(df_sorted)):
        val = df_sorted.loc[i, col_name]
        name = df_sorted.loc[i, "员工姓名"]
        rank_class = (
            "rank-item-top1" if i == 0
            else ("rank-item-top2" if i == 1 else "rank-item-top3" if i == 2 else "rank-item-normal")
        )
        prefix = (
            "🥇 第1名" if i == 0
            else ("🥈 第2名" if i == 1 else "🥉 第3名" if i == 2 else f"&nbsp;&nbsp;&nbsp;第{i+1}名")
        )
        val_str = f"{val:.1f}{unit}" if unit == "%" else f"{int(val)}{unit}"
        html += f'<div class="{rank_class}">{prefix}: <b>{name}</b> ({val_str})</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. 侧边栏导航与权限控制
# ---------------------------------------------------------
all_team_members = get_all_employee_names()
is_admin = (st.session_state.role == "admin")

st.sidebar.title("📌 招聘监控系统")
st.sidebar.markdown(f"<div class='user-badge'>👤 当前登录：{st.session_state.real_name} ({'管理员' if is_admin else '员工'})</div>", unsafe_allow_html=True)

menu_options = ["📱 员工端：手机填报与截图上传", "📊 业务预警与数据看板"]
if is_admin:
    menu_options.extend([
        "📋 数据端：智能识图/录入业绩",
        "⚙️ 管理端：账号管理与记录维护"
    ])

page = st.sidebar.radio("选择模块：", menu_options)

if st.sidebar.button("🚪 退出登录"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.real_name = ""
    st.session_state.role = ""
    st.rerun()

# ---------------------------------------------------------
# 模块一：员工端
# ---------------------------------------------------------
if page == "📱 员工端：手机填报与截图上传":
    st.markdown("<div class='main-header'>📱 员工每日平台数据快捷填报</div>", unsafe_allow_html=True)

    st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
    st.subheader("1️⃣ 基本信息确认")
    
    if not is_admin:
        emp_name = st.session_state.real_name
        st.info(f"👤 填报员工：**{emp_name}**（自动绑定当前登录账号）")
    else:
        emp_name = st.selectbox("选择填报员工", all_team_members, index=0)

    record_date = st.date_input("数据日期（默认昨天）", YESTERDAY, key="upload_date_picker")
    
    platform_ver = st.selectbox(
        "选择账号版本/平台",
        ["易德Boss", "呼叫中心Boss", "人保Boss", "智联招聘", "51job"]
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
    st.subheader("2️⃣ 上传平台截图")
    uploaded_file = st.file_uploader("点击上传或手机拍照", type=["jpg", "png", "jpeg"])
    st.markdown("</div>", unsafe_allow_html=True)

    submit_btn = st.button("🚀 立即提交保存", type="primary")

    if submit_btn:
        date_str = record_date.strftime("%Y-%m-%d")
        current_count = get_upload_count_today(date_str, emp_name, platform_ver)
        if current_count >= MAX_DAILY_UPLOADS:
            st.error(f"🛑 上传受限：【{emp_name}】在【{date_str}】对【{platform_ver}】已提交过 {current_count} 次，触发每日上限（最多 {MAX_DAILY_UPLOADS} 次）！如有误填请联系管理员。")
        elif uploaded_file is None:
            st.warning("⚠️ 请先选择并上传一张平台截图！")
        else:
            image = Image.open(uploaded_file)
            ocr = mock_employee_ocr(image)
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute(
                    """INSERT INTO platform_data 
                       (date, employee_name, platform_version, seen_me, i_communicated, received_resumes, exchanged_contact, exchanged_phone, proposed_interview, accepted_interview)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date_str, emp_name, platform_ver,
                        ocr["seen_me"], ocr["i_communicated"], ocr["received_resumes"],
                        ocr["exchanged_contact"], ocr["exchanged_phone"],
                        ocr["proposed_interview"], ocr["accepted_interview"],
                    ),
                )
                conn.commit()
            st.balloons()
            st.success(f"🎉 提交成功！[{emp_name}] 的 [{date_str}] [{platform_ver}] 数据已保存！（当日已提交 {current_count + 1}/{MAX_DAILY_UPLOADS} 次）")

# ---------------------------------------------------------
# 模块二：数据看板
# ---------------------------------------------------------
elif page == "📊 业务预警与数据看板":
    st.markdown("<div class='main-header'>📊 招聘全链路过程数据监控看板</div>", unsafe_allow_html=True)

    col_view, col_date, col_filter = st.columns([1, 1.2, 1.8])
    view_mode = col_view.radio("数据维度", ["📅 当日全链路", "📆 单月累计业绩"], horizontal=True)

    if "单月" in view_mode:
        col_y, col_m = col_date.columns(2)
        selected_year = col_y.selectbox("年份", [2026, 2025], index=0)
        selected_m_str = col_m.selectbox("月份", [f"{m:02d}月" for m in range(1, 13)], index=YESTERDAY.month - 1)
        month_str = f"{selected_year}-{selected_m_str.replace('月', '')}"
        date_filter_p = f"{month_str}%"
        date_filter_perf = f"{month_str}%"
    else:
        selected_date = col_date.date_input("选择统计日期", YESTERDAY)
        date_str = selected_date.strftime("%Y-%m-%d")
        date_filter_p = date_str
        date_filter_perf = date_str

    if not is_admin:
        selected_employees = [st.session_state.real_name]
        col_filter.info(f"🔒 数据范围：已锁定当前登录员工 **[{st.session_state.real_name}]**")
    else:
        selected_employees = col_filter.multiselect("筛选员工姓名", all_team_members, default=all_team_members)

    with sqlite3.connect(DB_PATH) as conn:
        if "单月" in view_mode:
            df_p = pd.read_sql_query(
                "SELECT employee_name as 员工姓名, SUM(seen_me) as 看过我, SUM(i_communicated) as 主动沟通, SUM(received_resumes) as 收获简历, SUM(exchanged_contact) as 交换微信, SUM(exchanged_phone) as 交换电话, SUM(proposed_interview) as 拟约面, SUM(accepted_interview) as 接受面试 FROM platform_data WHERE date LIKE ? GROUP BY employee_name",
                conn, params=(date_filter_p,)
            )
            df_perf = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, 
                          MAX(month_inner_invites) as 月内单邀约, MAX(month_outer_invites) as 月外单邀约, MAX(month_invites) as 单月累计邀约,
                          MAX(month_inner_interviews) as 月内单到面, MAX(month_outer_interviews) as 月外单到面, MAX(month_interviews) as 单月累计到面,
                          MAX(month_inner_trainees) as 月内单参培, MAX(month_outer_trainees) as 月外单参培, MAX(month_trainees) as 单月累计参培
                   FROM performance_data WHERE date LIKE ? GROUP BY employee_name""",
                conn, params=(date_filter_perf,)
            )
        else:
            df_p = pd.read_sql_query(
                "SELECT employee_name as 员工姓名, SUM(seen_me) as 看过我, SUM(i_communicated) as 主动沟通, SUM(received_resumes) as 收获简历, SUM(exchanged_contact) as 交换微信, SUM(exchanged_phone) as 交换电话, SUM(proposed_interview) as 拟约面, SUM(accepted_interview) as 接受面试 FROM platform_data WHERE date = ? GROUP BY employee_name",
                conn, params=(date_filter_p,)
            )
            df_perf = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, 
                          SUM(inner_invites) as 内单邀约, SUM(outer_invites) as 外单邀约, SUM(invites) as 当日邀约,
                          SUM(inner_interviews) as 内单到面, SUM(outer_interviews) as 外单到面, SUM(interviews) as 当日到面,
                          SUM(inner_trainees) as 内单参培, SUM(outer_trainees) as 外单参培, SUM(trainees) as 当日参培
                   FROM performance_data WHERE date = ? GROUP BY employee_name""",
                conn, params=(date_filter_perf,)
            )

    df_base = pd.DataFrame({"员工姓名": selected_employees})
    df_summary = pd.merge(df_base, df_p, on="员工姓名", how="left")
    df_summary = pd.merge(df_summary, df_perf, on="员工姓名", how="left").fillna(0)

    df_summary["到面转化率数值"] = df_summary.apply(
        lambda r: ((r["单月累计到面"] / r["单月累计邀约"] * 100) if "单月" in view_mode and r.get("单月累计邀约", 0) > 0 else ((r["当日到面"] / r["当日邀约"] * 100) if r.get("当日邀约", 0) > 0 else 0.0)),
        axis=1
    )
    df_summary["到面转化率"] = df_summary["到面转化率数值"].apply(lambda x: f"{x:.1f}%")

    if "单月" in view_mode:
        st.subheader(f"📆 招聘单月全链路累计汇总表 ({month_str})")
        final_cols = ["员工姓名", "看过我", "主动沟通", "收获简历", "交换微信", "交换电话", "拟约面", "接受面试", 
                      "月内单邀约", "月外单邀约", "单月累计邀约", 
                      "月内单到面", "月外单到面", "单月累计到面", 
                      "月内单参培", "月外单参培", "单月累计参培", "到面转化率"]
    else:
        st.subheader(f"📋 招聘当日全链路数据整合表 ({date_str})")
        final_cols = ["员工姓名", "看过我", "主动沟通", "收获简历", "交换微信", "交换电话", "拟约面", "接受面试", 
                      "内单邀约", "外单邀约", "当日邀约", 
                      "内单到面", "外单到面", "当日到面", 
                      "内单参培", "外单参培", "当日参培", "到面转化率"]

    st.dataframe(df_summary[final_cols], height=200 if not is_admin else 350)

    st.markdown("##### 📥 导出数据")
    col_exp1, col_exp2 = st.columns([1, 1])

    with col_exp1:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_summary[final_cols].to_excel(writer, index=False, sheet_name="招聘数据")
        st.download_button(
            label="📊 导出 Excel 表格 (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=f"招聘数据_{st.session_state.real_name}_{month_str if '单月' in view_mode else date_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col_exp2:
        csv_bytes = df_summary[final_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📄 导出 CSV 文件 (.csv)",
            data=csv_bytes,
            file_name=f"招聘数据_{st.session_state.real_name}_{month_str if '单月' in view_mode else date_str}.csv",
            mime="text/csv"
        )

    if is_admin and len(df_summary) > 1:
        st.write("---")
        st.subheader("📊 招聘关键过程指标 (KPI) 团队排名")
        p1_col1, p1_col2, p1_col3, p1_col4 = st.columns(4)
        with p1_col1: render_full_ranking(df_summary, "看过我", "看过我人数", "人")
        with p1_col2: render_full_ranking(df_summary, "主动沟通", "主动沟通人数", "人")
        with p1_col3: render_full_ranking(df_summary, "收获简历", "收获简历数量", "份")
        with p1_col4: render_full_ranking(df_summary, "交换微信", "交换微信数量", "人")

        inv_col = "单月累计邀约" if "单月" in view_mode else "当日邀约"
        int_col = "单月累计到面" if "单月" in view_mode else "当日到面"
        tra_col = "单月累计参培" if "单月" in view_mode else "当日参培"

        p2_col1, p2_col2, p2_col3, p2_col4 = st.columns(4)
        with p2_col1: render_full_ranking(df_summary, inv_col, f"{inv_col}人数", "人")
        with p2_col2: render_full_ranking(df_summary, int_col, f"{int_col}人数", "人")
        with p2_col3: render_full_ranking(df_summary, tra_col, f"{tra_col}人数", "人")
        with p2_col4: render_full_ranking(df_summary, "到面转化率数值", "到面转化率", "%")

    st.write("---")
    st.subheader("🚨 智能过程漏斗卡点诊断与预警")
    alerts = run_alert_engine(df_summary, is_monthly=("单月" in view_mode))
    if alerts:
        for a in alerts:
            card_class = "alert-card-danger" if "🚨" in a["level"] else "alert-card-warning"
            st.markdown(
                f"<div class='{card_class}'><b>【{a['level']}】{a['name']} - {a['issue']}</b><br/>• <b>卡点数据：</b> {a['data']}<br/>• <b>归因诊断：</b> {a['reason']}<br/>• <b>建议动作：</b> {a['action']}</div>",
                unsafe_allow_html=True
            )
    else:
        st.success("🎉 数据表现正常，暂无过程卡点预警！")

# ---------------------------------------------------------
# 模块三：识图录入端（管理员专用）
# ---------------------------------------------------------
elif page == "📋 数据端：智能识图/录入业绩" and is_admin:
    st.markdown("<div class='main-header'>📋 数据端：部门业绩汇总与智能识图录入 (管理员专用)</div>", unsafe_allow_html=True)
    col_type, col_date = st.columns(2)
    data_type = col_type.radio("📌 选择上传的数据表类型：", ["📅 日度新增业绩表", "📆 单月累计业绩表"], horizontal=True)
    p_date_img = col_date.date_input("选择业绩数据日期", YESTERDAY)

    st.write("---")
    if "日度" in data_type:
        daily_img = st.file_uploader("上传【日度】表格截图 (包含内单/外单)", type=["jpg", "png", "jpeg"])
        if daily_img is not None:
            image = Image.open(daily_img)
            st.image(image, caption="已上传截图", width=400)
            df_extracted = mock_supervisor_ocr_daily(image, all_team_members)
            st.info("💡 请在下方核对识图抓取结果，可直接在线修改：")
            
            edited_df = st.data_editor(df_extracted, num_rows="dynamic")
            edited_df["当日邀约总计"] = edited_df["内单邀约"] + edited_df["外单邀约"]
            edited_df["当日到面总计"] = edited_df["内单到面"] + edited_df["外单到面"]
            edited_df["当日参培总计"] = edited_df["内单参培"] + edited_df["外单参培"]

            if st.button("💾 确认提交【日度】数据入库"):
                date_str = p_date_img.strftime("%Y-%m-%d")
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    for idx, row in edited_df.iterrows():
                        c.execute(
                            """INSERT INTO performance_data 
                               (date, employee_name, inner_invites, outer_invites, invites, inner_interviews, outer_interviews, interviews, inner_trainees, outer_trainees, trainees) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                date_str, row["员工姓名"],
                                int(row["内单邀约"]), int(row["外单邀约"]), int(row["当日邀约总计"]),
                                int(row["内单到面"]), int(row["外单到面"]), int(row["当日到面总计"]),
                                int(row["内单参培"]), int(row["外单参培"]), int(row["当日参培总计"])
                            )
                        )
                    conn.commit()
                st.balloons()
                st.success(f"🎉 成功保存 {date_str} 日度业绩数据！")
    else:
        monthly_img = st.file_uploader("上传【单月累计】表格截图 (包含内单/外单)", type=["jpg", "png", "jpeg"])
        if monthly_img is not None:
            image = Image.open(monthly_img)
            st.image(image, caption="已上传截图", width=400)
            df_extracted = mock_supervisor_ocr_monthly(image, all_team_members)
            st.info("💡 请在下方核对识图抓取结果，可直接在线修改：")

            edited_df = st.data_editor(df_extracted, num_rows="dynamic")
            edited_df["月度邀约总计"] = edited_df["月内单邀约"] + edited_df["月外单邀约"]
            edited_df["月度到面总计"] = edited_df["月内单到面"] + edited_df["月外单到面"]
            edited_df["月度参培总计"] = edited_df["月内单参培"] + edited_df["月外单参培"]

            if st.button("💾 确认提交【单月累计】数据入库"):
                date_str = p_date_img.strftime("%Y-%m-%d")
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    for idx, row in edited_df.iterrows():
                        c.execute(
                            """INSERT INTO performance_data 
                               (date, employee_name, month_inner_invites, month_outer_invites, month_invites, month_inner_interviews, month_outer_interviews, month_interviews, month_inner_trainees, month_outer_trainees, month_trainees) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                date_str, row["员工姓名"],
                                int(row["月内单邀约"]), int(row["月外单邀约"]), int(row["月度邀约总计"]),
                                int(row["月内单到面"]), int(row["月外单到面"]), int(row["月度到面总计"]),
                                int(row["月内单参培"]), int(row["月外单参培"]), int(row["月度参培总计"])
                            )
                        )
                    conn.commit()
                st.balloons()
                st.success(f"🎉 成功保存 {date_str} 月度业绩数据！")

# ---------------------------------------------------------
# 模块四：管理端（管理员专用）
# ---------------------------------------------------------
elif page == "⚙️ 管理端：账号管理与记录维护" and is_admin:
    st.markdown("<div class='main-header'>⚙️ 后台管理中心 (管理员权限)</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 员工与账号管理", "🗑️ 数据记录删除与维护"])

    with tab1:
        st.subheader("➕ 新增员工账号")
        col_u1, col_u2, col_u3, col_u4 = st.columns([1.5, 1.5, 1.5, 1])
        new_username = col_u1.text_input("登录账号 (如: zhangsan)")
        new_realname = col_u2.text_input("员工真实姓名 (如: 张三)")
        new_password = col_u3.text_input("初始密码", value="123456")
        
        if col_u4.button("➕ 创建账号"):
            if new_username and new_realname and new_password:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO users (username, password, real_name, role) VALUES (?, ?, ?, 'employee')",
                                  (new_username, new_password, new_realname))
                        conn.commit()
                    st.success(f"✅ 成功创建员工账号：{new_realname} ({new_username})")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("❌ 该登录账号已存在，请更换其他账号名！")
            else:
                st.warning("⚠️ 请填满所有账号信息！")

        st.write("---")
        st.subheader("📋 现有人员与账号列表")
        with sqlite3.connect(DB_PATH) as conn:
            df_users = pd.read_sql_query("SELECT id as 用户编号, username as 账号, real_name as 姓名, role as 角色, password as 密码 FROM users", conn)
        st.dataframe(df_users, use_container_width=True)

        st.write("---")
        st.subheader("🗑️ 删除员工账号")
        col_del_u, col_del_ubtn = st.columns([2, 1])
        user_list = df_users[df_users["角色"] != "admin"]
        
        if not user_list.empty:
            del_user_id = col_del_u.selectbox(
                "选择需要删除的员工账号：",
                options=user_list["用户编号"].tolist(),
                format_func=lambda x: f"编号 #{x} | 姓名: {user_list[user_list['用户编号']==x]['姓名'].values[0]} | 账号: {user_list[user_list['用户编号']==x]['账号'].values[0]}"
            )
            if col_del_ubtn.button("🔥 确认删除账号", type="primary"):
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM users WHERE id = ?", (del_user_id,))
                    conn.commit()
                st.success("✅ 账号删除成功！")
                st.rerun()

    with tab2:
        st.subheader("📋 所有平台上传记录维护")
        with sqlite3.connect(DB_PATH) as conn:
            df_records = pd.read_sql_query(
                """SELECT id as 记录编号, date as 归属日期, employee_name as 员工姓名, platform_version as 平台,
                          seen_me as 看过我, i_communicated as 主动沟通, received_resumes as 收到简历,
                          exchanged_contact as 微信, exchanged_phone as 电话, created_at as 提交时间
                   FROM platform_data ORDER BY id DESC""",
                conn
            )

        if not df_records.empty:
            col_f1, col_f2 = st.columns(2)
            filter_name = col_f1.selectbox("按员工筛选记录", ["全部"] + all_team_members)
            
            df_show = df_records.copy()
            if filter_name != "全部":
                df_show = df_show[df_show["员工姓名"] == filter_name]

            st.dataframe(df_show, use_container_width=True, height=300)

            st.write("---")
            st.subheader("⚠️ 彻底删除指定的错误提交记录")
            col_del_id, col_del_btn = st.columns([2, 1])

            record_options = df_show["记录编号"].tolist()
            if record_options:
                selected_id = col_del_id.selectbox(
                    "选择需要删除的记录编号 (ID):",
                    options=record_options,
                    format_func=lambda x: f"编号 #{x} | {df_show[df_show['记录编号']==x]['归属日期'].values[0]} | {df_show[df_show['记录编号']==x]['员工姓名'].values[0]} | {df_show[df_show['记录编号']==x]['平台'].values[0]}"
                )

                if col_del_btn.button("🔥 确认删除记录", type="primary"):
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute("DELETE FROM platform_data WHERE id = ?", (selected_id,))
                        conn.commit()
                    st.success(f"✅ 记录 #{selected_id} 已彻底删除！")
                    st.rerun()
        else:
            st.info("ℹ️ 暂无平台提交记录。")