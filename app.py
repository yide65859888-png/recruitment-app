import base64
import datetime
import io
import json
import sqlite3
import pandas as pd
from openai import OpenAI
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
    "储郑燃",
    "刘春雨",
    "唐凯",
    "孙衍",
    "王俊丽",
    "王小兰",
    "王肖",
    "王莉莹",
    "栗阳阳",
    "罗悦",
    "薛丽丽",
]

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
MAX_DAILY_UPLOADS = 3
DB_PATH = "recruitment_data.db"

# 通义千问视觉识别配置（阿里云百炼平台）
QWEN_CONFIG = {
    'api_key': 'sk-eogrtqfwedttonwhabcvsvswmmfnncjqlzbesnhtbqlanrzy',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen-vl-max',
}


# ---------------------------------------------------------
# 2. 数据库初始化（升级为新表头架构）
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
                        date TEXT, 
                        employee_name TEXT,
                        invites INTEGER DEFAULT 0, 
                        interviews INTEGER DEFAULT 0, 
                        inner_ft INTEGER DEFAULT 0, 
                        inner_pt INTEGER DEFAULT 0, 
                        outer_ft INTEGER DEFAULT 0, 
                        outer_pt INTEGER DEFAULT 0, 
                        trainees INTEGER DEFAULT 0,
                        month_invites INTEGER DEFAULT 0, 
                        month_interviews INTEGER DEFAULT 0, 
                        month_inner_ft INTEGER DEFAULT 0, 
                        month_inner_pt INTEGER DEFAULT 0, 
                        month_outer_ft INTEGER DEFAULT 0, 
                        month_outer_pt INTEGER DEFAULT 0, 
                        month_trainees INTEGER DEFAULT 0
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
            c.execute(
                "INSERT INTO users (username, password, real_name, role) VALUES ('admin', 'admin123', '系统管理员', 'admin')"
            )

        for name in DEFAULT_MEMBERS:
            c.execute(
                "SELECT COUNT(*) FROM users WHERE real_name = ?", (name,)
            )
            if c.fetchone()[0] == 0:
                c.execute(
                    "INSERT INTO users (username, password, real_name, role) VALUES (?, '123456', ?, 'employee')",
                    (name, name),
                )
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
        c.execute(
            "SELECT username, real_name, role FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        return c.fetchone()


if not st.session_state.logged_in:
    st.markdown(
        "<h2 style='text-align: center; color: #1F4E79;'>🔒 招聘全链路监控系统 - 用户登录</h2>",
        unsafe_allow_html=True,
    )

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
                st.error(
                    "❌ 账号或密码错误！(默认员工密码为 123456，管理员账号 admin/admin123)"
                )
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------
# 4. 辅助函数与通义千问大模型 OCR
# ---------------------------------------------------------
def mock_employee_ocr(image):
    return {
        "seen_me": 593,
        "i_communicated": 319,
        "received_resumes": 29,
        "exchanged_contact": 14,
        "exchanged_phone": 8,
        "proposed_interview": 5,
        "accepted_interview": 3,
    }


def llm_supervisor_ocr(image: Image.Image, members: list) -> pd.DataFrame:
    """使用阿里云通义千问 qwen-vl-max 多模态大模型识别招聘数据表格"""
    try:
        client = OpenAI(
            api_key=QWEN_CONFIG['api_key'], base_url=QWEN_CONFIG['base_url']
        )

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = f"""
        你是一个专业的数据提取助手。请仔细识别图片中表格包含的招聘数据。

        【目标员工列表】：
        {json.dumps(members, ensure_ascii=False)}

        【提取规则】：
        1. 请仔细读取图片中每一行员工对应的【邀约数】、【到面数】以及各个参培拆分项数值。
        2. 识别提取目标员工列表中各成员的数据。
        3. 如果图片中某项数值为空或未填写，默认设为 0。
        4. 必须只输出严格的 JSON 数组结构，不要包含任何 markdown 标签、解释文字或思考过程。

        【输出 JSON 字段结构】：
        [
          {{
            "员工姓名": "张三",
            "邀约数": 10,
            "到面数": 5,
            "参培数(内单全职)": 0,
            "参培数(内单兼职)": 0,
            "参培数(外单全职)": 1,
            "参培数(外单兼职)": 0
          }}
        ]
        """

        response = client.chat.completions.create(
            model=QWEN_CONFIG['model'],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            }],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        # 清理可能附带的 markdown 格式包裹
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data_list = json.loads(content)
        df = pd.DataFrame(data_list)

        required_cols = [
            "员工姓名",
            "邀约数",
            "到面数",
            "参培数(内单全职)",
            "参培数(内单兼职)",
            "参培数(外单全职)",
            "参培数(外单兼职)",
        ]
        for col in required_cols:
            if col not in df.columns:
                if col == "员工姓名":
                    df["员工姓名"] = members
                else:
                    df[col] = 0

        numeric_cols = [
            "邀约数",
            "到面数",
            "参培数(内单全职)",
            "参培数(内单兼职)",
            "参培数(外单全职)",
            "参培数(外单兼职)",
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        df["参培数"] = (
            df["参培数(内单全职)"]
            + df["参培数(内单兼职)"]
            + df["参培数(外单全职)"]
            + df["参培数(外单兼职)"]
        )
        return df[
            [
                "员工姓名",
                "邀约数",
                "到面数",
                "参培数(内单全职)",
                "参培数(内单兼职)",
                "参培数(外单全职)",
                "参培数(外单兼职)",
                "参培数",
            ]
        ]

    except Exception as e:
        st.error(f"⚠️ 大模型识别出现异常 ({e})，已切换至基础表结构，请手动补全修改。")
        return pd.DataFrame({
            "员工姓名": members,
            "邀约数": 0,
            "到面数": 0,
            "参培数(内单全职)": 0,
            "参培数(内单兼职)": 0,
            "参培数(外单全职)": 0,
            "参培数(外单兼职)": 0,
            "参培数": 0,
        })


def get_upload_count_today(date_str, emp_name, platform):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM platform_data WHERE date = ? AND employee_name = ? AND platform_version = ?",
            (date_str, emp_name, platform),
        )
        return c.fetchone()[0]


def run_alert_engine(df_summary, is_monthly=False):
    alerts = []
    for _, row in df_summary.iterrows():
        name = row["员工姓名"]
        comm = row.get("主动沟通", 0)
        resumes = row.get("收获简历", 0)
        wx = row.get("交换微信", 0)
        invites = row.get("邀约数", 0)
        interviews = row.get("到面数", 0)
        trainees = row.get("参培数", 0)
        time_tag = "全月" if is_monthly else "当日"

        if is_monthly and invites < 30:
            alerts.append({
                "name": name,
                "level": "🚨 产能预警：月度招聘产能严重不足",
                "issue": f"{time_tag}累计邀约仅 {invites} 人，到面 {interviews} 人",
                "data": f"月邀约 {invites} 人 ➔ 到面 {interviews} 人 ➔ 参培 {trainees} 人",
                "reason": (
                    "月度整体招聘动作极少，业务活动量严重不达标，未能建立起有效的招聘漏斗基数"
                ),
                "action": (
                    "建议拉通一对一辅导，明确每日打招呼、私域跟进与约面的最低过程 KPI"
                ),
            })

        if comm > 100 and (resumes + wx) < 30:
            alerts.append({
                "name": name,
                "level": "🚨 触达预警：开场白与画像匹配度待优化",
                "issue": (
                    f"{time_tag}主动沟通 {comm} 人，但私域仅获取 {wx} 个微信"
                ),
                "data": f"沟通 {comm} 人 ➔ 微信仅 {wx} 人",
                "reason": (
                    "打招呼量较大但私域留存偏低，可能存在推送职位与求职者意向不匹配或交流话术吸引力不足"
                ),
                "action": (
                    "建议抽查交流话术，优化精准画像筛选，提升有效沟通率"
                ),
            })

        min_invites = 5 if is_monthly else 1
        if wx >= 10 and invites < min_invites:
            alerts.append({
                "name": name,
                "level": "⚠️ 跟进预警：私域候选人转化滞后",
                "issue": f"{time_tag}获取微信 {wx} 个，但实际邀约仅 {invites} 人",
                "data": f"微信 {wx} 人 ➔ 邀约 {invites} 人",
                "reason": (
                    "私域留存资源较丰富但尚未形成有效约面，可能存在跟进及时性不足或约面促成临门一脚欠缺"
                ),
                "action": (
                    "建议梳理私域待跟进列表，通过电话复核提高直接邀约率"
                ),
            })

        trainee_rate = (
            (trainees / interviews * 100) if interviews > 0 else 0
        )
        if interviews >= (15 if is_monthly else 20) and (
            trainees == 0 or trainee_rate < 10.0
        ):
            alerts.append({
                "name": name,
                "level": "🚨 转化预警：到面至参培漏斗断层",
                "issue": f"{time_tag}到面 {interviews} 人，但参培仅 {trainees} 人 (转化率仅 {trainee_rate:.1f}%)",
                "data": f"到面 {interviews} 人 ➔ 参培仅 {trainees} 人",
                "reason": (
                    "到场人数较多但后续参培流失率极高，可能存在前期求职意向确认不足、或现场宣讲/面试预期管理差距较大"
                ),
                "action": (
                    "建议加强现场面试反馈复盘，提高前期邀约精准度与求职意向深度确认"
                ),
            })

        if invites > 0 and interviews >= (invites * 2):
            alerts.append({
                "name": name,
                "level": "🛠️ 规范预警：过程数据同步延迟",
                "issue": (
                    f"{time_tag}到面数({interviews}) 显著高于"
                    f" 邀约记录数({invites})"
                ),
                "data": (
                    f"到面转化率异常达到 {((interviews/invites)*100):.1f}%"
                ),
                "reason": (
                    "可能存在事前邀约数据录入不及时、求职者到场后才集中补录的情况"
                ),
                "action": (
                    "建议规范“事前录入邀约、事后核到面”的数据更新节奏，确保过程数据实时准确"
                ),
            })
    return alerts


def render_full_ranking(df, col_name, title_name, unit=""):
    df_sorted = df.sort_values(by=col_name, ascending=False).reset_index(
        drop=True
    )
    html = f'<div class="rank-box"><div class="rank-title">🏆 {title_name}</div>'
    for i in range(len(df_sorted)):
        val = df_sorted.loc[i, col_name]
        name = df_sorted.loc[i, "员工姓名"]
        rank_class = (
            "rank-item-top1"
            if i == 0
            else (
                "rank-item-top2"
                if i == 1
                else "rank-item-top3" if i == 2 else "rank-item-normal"
            )
        )
        prefix = (
            "🥇 第1名"
            if i == 0
            else (
                "🥈 第2名"
                if i == 1
                else (
                    "🥉 第3名"
                    if i == 2
                    else f"&nbsp;&nbsp;&nbsp;第{i+1}名"
                )
            )
        )
        val_str = f"{val:.1f}{unit}" if unit == "%" else f"{int(val)}{unit}"
        html += (
            f'<div class="{rank_class}">{prefix}: <b>{name}</b>'
            f' ({val_str})</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------
# 5. 侧边栏导航与权限控制
# ---------------------------------------------------------
all_team_members = get_all_employee_names()
is_admin = st.session_state.role == "admin"

st.sidebar.title("📌 招聘监控系统")
st.sidebar.markdown(
    f"<div class='user-badge'>👤 当前登录：{st.session_state.real_name}"
    f" ({'管理员' if is_admin else '员工'})</div>",
    unsafe_allow_html=True,
)

menu_options = ["📱 员工端：手机填报与截图上传", "📊 业务预警与数据看板"]
if is_admin:
    menu_options.extend(
        ["📋 数据端：智能识图/录入业绩", "⚙️ 管理端：账号管理与记录维护"]
    )

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
    st.markdown(
        "<div class='main-header'>📱 员工每日平台数据快捷填报</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
    st.subheader("1️⃣ 基本信息确认")

    if not is_admin:
        emp_name = st.session_state.real_name
        st.info(f"👤 填报员工：**{emp_name}**（自动绑定当前登录账号）")
    else:
        emp_name = st.selectbox("👤 选择填报员工（管理员代传模式）", all_team_members, index=0)

    record_date = st.date_input(
        "数据日期（默认昨天）", YESTERDAY, key="upload_date_picker"
    )