import base64
from concurrent.futures import ThreadPoolExecutor
import datetime
import io
import json
import re
import sqlite3
from openai import OpenAI
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
    .main-header {font-size:20px; font-weight:bold; color:#1F4E79; margin-bottom:10px;}
    
    .mobile-card {
        background-color: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        margin-bottom: 12px;
    }
    
    .alert-card-danger {background-color:#FFD2D2; border-left:4px solid #D8000C; padding:10px; border-radius:4px; margin-bottom:8px;}
    .alert-card-warning {background-color:#FFF3CD; border-left:4px solid #856404; padding:10px; border-radius:4px; margin-bottom:8px;}
    
    .rank-box {
        background: #ffffff;
        border-radius: 6px;
        padding: 6px 10px;
        border: 1px solid #e2e8f0;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .rank-title {
        font-size: 13px;
        font-weight: bold;
        color: #1F4E79;
        margin-bottom: 4px;
        border-bottom: 1px solid #1F4E79;
        padding-bottom: 2px;
    }
    .rank-item-top1 { font-weight: bold; color: #D4AF37; margin: 2px 0; font-size: 12px; line-height: 1.2; }
    .rank-item-top2 { font-weight: bold; color: #708090; margin: 2px 0; font-size: 12px; line-height: 1.2; }
    .rank-item-top3 { font-weight: bold; color: #B87333; margin: 2px 0; font-size: 12px; line-height: 1.2; }
    .rank-item-normal { font-weight: normal; color: #495057; margin: 2px 0; font-size: 12px; line-height: 1.2; }
    
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        height: 40px;
        font-weight: bold;
    }
    
    .user-badge {
        padding: 4px 10px;
        background-color: #e9ecef;
        border-radius: 16px;
        font-size: 12px;
        font-weight: bold;
        color: #1F4E79;
        margin-bottom: 12px;
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

PLATFORM_OPTIONS = [
    "易德Boss1号",
    "易德Boss2号",
    "易德Boss3号",
    "呼叫中心Boss",
    "人保Boss",
    "智联招聘",
    "51job",
]

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
DB_PATH = "recruitment_data.db"

QWEN_CONFIG = {
    "api_key": "sk-eogrtqfwedttonwhabcvsvswmmfnncjqlzbesnhtbqlanrzy",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen3.6-35B-A3B",
    "enable_thinking": False,
}

TARGET_HEADERS = [
    "我看过",
    "看过我",
    "我打招呼",
    "牛人新招呼",
    "我沟通",
    "收获简历",
    "交换电话微信",
    "接受面试",
]


# ---------------------------------------------------------
# 2. 数据库初始化与 LLM 客户端初始化
# ---------------------------------------------------------
@st.cache_resource
def get_llm_client():
    return OpenAI(
        api_key=QWEN_CONFIG["api_key"], base_url=QWEN_CONFIG["base_url"]
    )


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS platform_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT, 
                        employee_name TEXT, 
                        platform_version TEXT,
                        i_looked INTEGER DEFAULT 0,
                        seen_me INTEGER DEFAULT 0, 
                        i_greeted INTEGER DEFAULT 0,
                        candidate_greeted INTEGER DEFAULT 0,
                        i_communicated INTEGER DEFAULT 0,
                        received_resumes INTEGER DEFAULT 0, 
                        exchanged_contact INTEGER DEFAULT 0,
                        accepted_interview INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date, employee_name, platform_version)
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
                        month_trainees INTEGER DEFAULT 0,
                        UNIQUE(date, employee_name)
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
            c.execute("SELECT COUNT(*) FROM users WHERE real_name = ?", (name,))
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

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


def verify_login(username, password):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT username, real_name, role FROM users WHERE username = ? AND password = ?",
            (username.strip(), password.strip()),
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
        with st.form(key="login_form", clear_on_submit=False):
            login_user = st.text_input("账号 / 员工姓名")
            login_pwd = st.text_input("密码", type="password")
            btn_login = st.form_submit_button("🔐 登录系统", type="primary")

            if btn_login:
                if not login_user or not login_pwd:
                    st.warning("⚠️ 请输入账号和密码！")
                else:
                    user_info = verify_login(login_user, login_pwd)
                    if user_info:
                        st.session_state.logged_in = True
                        st.session_state.username = user_info[0]
                        st.session_state.real_name = user_info[1]
                        st.session_state.role = user_info[2]
                        st.success("登录成功！正在跳转...")
                        st.rerun()
                    else:
                        st.error("❌ 账号或密码错误！")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------
# 4. 辅助函数与视觉 AI OCR 及大模型诊断引擎
# ---------------------------------------------------------
def mock_employee_ocr(image: Image.Image) -> dict:
    default_result = {
        "i_looked": 0,
        "seen_me": 0,
        "i_greeted": 0,
        "candidate_greeted": 0,
        "i_communicated": 0,
        "received_resumes": 0,
        "exchanged_contact": 0,
        "accepted_interview": 0,
    }
    try:
        client = get_llm_client()
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = """
        你是一个精准的数据提取与 OCR 视觉专家。图片中是招聘平台的数据概览看板。
        【必须提取的固定 8 个数据表头】：
        1. 我看过  2. 看过我  3. 我打招呼  4. 牛人新招呼  5. 我沟通  6. 收获简历  7. 交换电话微信  8. 接受面试
        必须且只能输出严格的纯 JSON 格式。
        """

        response = client.chat.completions.create(
            model=QWEN_CONFIG["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.01,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed_data = json.loads(content)
        mapping = {
            "我看过": "i_looked",
            "看过我": "seen_me",
            "我打招呼": "i_greeted",
            "牛人新招呼": "candidate_greeted",
            "我沟通": "i_communicated",
            "收获简历": "received_resumes",
            "交换电话微信": "exchanged_contact",
            "接受面试": "accepted_interview",
        }
        for header_name, key_name in mapping.items():
            if header_name in parsed_data:
                match = re.search(r"\d+", str(parsed_data[header_name]))
                if match:
                    default_result[key_name] = int(match.group())
        return default_result
    except Exception:
        return default_result


def llm_supervisor_ocr(image: Image.Image, members: list) -> pd.DataFrame:
    try:
        client = get_llm_client()
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = f"""
        你是一个专业的数据提取助手。请识别图片中表格包含的招聘数据。
        【目标员工列表】：{json.dumps(members, ensure_ascii=False)}
        输出严格的 JSON 数组结构，包含键："员工姓名", "邀约数", "到面数", "参培数(内单全职)", "参培数(内单兼职)", "参培数(外单全职)", "参培数(外单兼职)"
        """
        response = client.chat.completions.create(
            model=QWEN_CONFIG["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data_list = json.loads(content)
        df_raw = pd.DataFrame(data_list)
        base_df = pd.DataFrame({"员工姓名": members})
        df = (
            pd.merge(base_df, df_raw, on="员工姓名", how="left")
            if "员工姓名" in df_raw.columns
            else base_df.copy()
        )

        required_cols = [
            "邀约数",
            "到面数",
            "参培数(内单全职)",
            "参培数(内单兼职)",
            "参培数(外单全职)",
            "参培数(外单兼职)",
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            )

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
    except Exception:
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


def check_existing_record(date_str, emp_name, platform):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT created_at FROM platform_data WHERE date = ? AND employee_name = ? AND platform_version = ?",
            (date_str, emp_name, platform),
        )
        res = c.fetchone()
        return res[0] if res else None


def _call_llm_diagnosis(
    name, level, time_tag, data_str, metrics_summary, reason_fallback, action_fallback
):
    client = get_llm_client()
    prompt = f"""
你是一位资深招聘效能专家。请根据以下过程数据做精准归因诊断与改进建议。
【员工姓名】：{name}
【时间维度】：{time_tag}
【预警类别】：{level}
【关键数据】：{metrics_summary}
输出严格的 JSON 结构：
{{"reason": "诊断", "action": "建议"}}
"""
    try:
        response = client.chat.completions.create(
            model=QWEN_CONFIG["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的 HR 数据效能分析助手。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        res_text = response.choices[0].message.content.strip()
        if res_text.startswith("```"):
            lines = res_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            res_text = "\n".join(lines).strip()
        parsed = json.loads(res_text)
        return parsed.get("reason", reason_fallback), parsed.get(
            "action", action_fallback
        )
    except Exception:
        return reason_fallback, action_fallback


def run_alert_engine(df_summary, is_monthly=False):
    tasks = []
    time_tag = "全月" if is_monthly else "当日"
    for _, row in df_summary.iterrows():
        name = row["员工姓名"]
        if name == "合计":
            continue
        comm = int(row.get("我沟通", 0))
        resumes = int(row.get("收获简历", 0))
        wx = int(row.get("交换电话微信", 0))
        invites = int(row.get("邀约数", 0))
        interviews = int(row.get("到面数", 0))
        trainees = int(row.get("参培数", 0))
        metrics_summary = f"主动沟通:{comm}人, 收获简历:{resumes}份, 私域留存:{wx}个, 邀约:{invites}人, 到面:{interviews}人, 参培:{trainees}人"

        if is_monthly and invites < 30:
            tasks.append({
                "name": name,
                "level": "🚨 产能预警：月度招聘产能严重不足",
                "issue": f"{time_tag}累计邀约仅 {invites} 人",
                "data": f"月邀约 {invites} 人 ➔ 到面 {interviews} 人",
                "metrics_summary": metrics_summary,
                "time_tag": time_tag,
                "reason_fallback": "月度整体招聘动作极少，活动量不达标",
                "action_fallback": "建议拉通一对一辅导，明确每日KPI",
            })
        if comm > 100 and (resumes + wx) < 30:
            tasks.append({
                "name": name,
                "level": "🚨 触达预警：画像匹配度待优化",
                "issue": f"{time_tag}沟通 {comm} 人，私域仅获取 {wx} 个",
                "data": f"沟通 {comm} 人 ➔ 微信仅 {wx} 人",
                "metrics_summary": metrics_summary,
                "time_tag": time_tag,
                "reason_fallback": "打招呼多但私域留存少，岗位匹配度不够",
                "action_fallback": "建议抽查交流话术，优化精准画像",
            })
    if not tasks:
        return []
    alerts = []
    with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
        futures = [
            executor.submit(
                _call_llm_diagnosis,
                t["name"],
                t["level"],
                t["time_tag"],
                t["data"],
                t["metrics_summary"],
                t["reason_fallback"],
                t["action_fallback"],
            )
            for t in tasks
        ]
        for t, future in zip(tasks, futures):
            reason, action = future.result()
            t["reason"] = reason
            t["action"] = action
            alerts.append(t)
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
                else "🥉 第3名" if i == 2 else f"&nbsp;&nbsp;&nbsp;第{i+1}名"
            )
        )
        val_str = f"{val:.1f}{unit}" if unit == "%" else f"{int(val)}{unit}"
        html += (
            f'<div class="{rank_class}">{prefix}: <b>{name}</b> ({val_str})</div>'
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
        emp_name = st.selectbox(
            "👤 选择填报员工（管理员代传模式）", all_team_members, index=0
        )

    record_date = st.date_input(
        "数据日期（默认昨天）", YESTERDAY, key="upload_date_picker"
    )
    date_str = record_date.strftime("%Y-%m-%d")

    platform_ver = st.selectbox("选择账号版本/平台", PLATFORM_OPTIONS)

    existing_time = check_existing_record(date_str, emp_name, platform_ver)
    if existing_time:
        st.info(
            f"💡 提示：检测到您在 **{date_str}** 已提交过 **[{platform_ver}]**"
            f" 的数据（提交时间：{existing_time}）。**再次提交将自动覆盖替换**。"
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
    st.subheader("2️⃣ 上传平台截图")
    uploaded_file = st.file_uploader(
        "点击上传或手机拍照",
        type=["jpg", "png", "jpeg"],
        key=f"uploader_{st.session_state.uploader_key}",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    submit_btn = st.button("🚀 立即提交保存", type="primary")

    if submit_btn:
        if uploaded_file is None:
            st.warning("⚠️ 请先选择并上传一张平台截图！")
        else:
            image = Image.open(uploaded_file)
            with st.spinner(
                "🤖 正在调用通义千问大模型精准抓取截图数据，请稍候..."
            ):
                ocr = mock_employee_ocr(image)

            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute(
                    """INSERT OR REPLACE INTO platform_data 
                       (date, employee_name, platform_version, i_looked, seen_me, i_greeted, candidate_greeted, i_communicated, received_resumes, exchanged_contact, accepted_interview, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        date_str,
                        emp_name,
                        platform_ver,
                        ocr["i_looked"],
                        ocr["seen_me"],
                        ocr["i_greeted"],
                        ocr["candidate_greeted"],
                        ocr["i_communicated"],
                        ocr["received_resumes"],
                        ocr["exchanged_contact"],
                        ocr["accepted_interview"],
                    ),
                )
                conn.commit()

            st.session_state.uploader_key += 1
            st.balloons()
            st.success("🎉 提交成功！数据已更新覆盖！")
            st.rerun()

# ---------------------------------------------------------
# 模块二：数据看板（含历史日报表导入功能）
# ---------------------------------------------------------
elif page == "📊 业务预警与数据看板":
    st.markdown(
        "<div class='main-header'>📊 招聘全链路过程数据监控看板</div>",
        unsafe_allow_html=True,
    )

    # =========================================================
    # 🌟 新增：历史日报表上传导入功能（严格执行以最后一版为准，不合并累计）
    # =========================================================
    with st.expander(
        "📥 【历史数据补充】上传历史日报表（支持覆盖导入历史数据）",
        expanded=False,
    ):
        st.markdown(
            "如果之前的数据丢失或需要重新导入之前从平台下载的日报表模板，可在此处上传。**注意：上传后将直接以最后一版导入的日报表数据为准对目标日期进行覆盖**。"
        )
        uploaded_history_file = st.file_uploader(
            "上传历史日报表文件 (支持 .xlsx / .csv)",
            type=["xlsx", "csv"],
            key="history_report_uploader",
        )

        if uploaded_history_file is not None:
            try:
                if uploaded_history_file.name.endswith(".csv"):
                    df_history = pd.read_csv(uploaded_history_file)
                else:
                    df_history = pd.read_excel(uploaded_history_file)

                st.write("📋 成功读取历史日报表预览（前5行）：")
                st.dataframe(df_history.head(), use_container_width=True)

                if st.button("🚀 确认按最后一版覆盖导入历史日报表", type="primary"):
                    success_count = 0
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        for _, row in df_history.iterrows():
                            # 自动适配模板中的字段名
                            date_val = str(
                                row.get(
                                    "具体日期",
                                    row.get("日期", datetime.date.today()),
                                )
                            ).strip()
                            emp_val = str(row.get("员工姓名", "")).strip()

                            if (
                                not emp_val
                                or emp_val == "合计"
                                or emp_val == "nan"
                            ):
                                continue

                            # 提取平台过程数据指标（支持容错默认0）
                            i_looked = int(row.get("我看过", 0) or 0)
                            seen_me = int(row.get("看过我", 0) or 0)
                            i_greeted = int(row.get("我打招呼", 0) or 0)
                            candidate_greeted = int(
                                row.get("牛人新招呼", 0) or 0
                            )
                            i_communicated = int(row.get("我沟通", 0) or 0)
                            received_resumes = int(row.get("收获简历", 0) or 0)
                            exchanged_contact = int(
                                row.get("交换电话微信", 0) or 0
                            )
                            accepted_interview = int(
                                row.get("接受面试", 0) or 0
                            )

                            # 1. 写入/覆盖 platform_data（以导入版本为准，先清理该日期该员工的旧数据或直接REPLACE）
                            c.execute(
                                """INSERT OR REPLACE INTO platform_data 
                                   (date, employee_name, platform_version, i_looked, seen_me, i_greeted, candidate_greeted, i_communicated, received_resumes, exchanged_contact, accepted_interview, created_at)
                                   VALUES (?, ?, '导入备份版', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                                (
                                    date_val,
                                    emp_val,
                                    i_looked,
                                    seen_me,
                                    i_greeted,
                                    candidate_greeted,
                                    i_communicated,
                                    received_resumes,
                                    exchanged_contact,
                                    accepted_interview,
                                ),
                            )

                            # 提取业绩指标
                            invites = int(row.get("邀约数", 0) or 0)
                            interviews = int(row.get("到面数", 0) or 0)
                            inner_ft = int(row.get("参培数(内单全职)", 0) or 0)
                            inner_pt = int(row.get("参培数(内单兼职)", 0) or 0)
                            outer_ft = int(row.get("参培数(外单全职)", 0) or 0)
                            outer_pt = int(row.get("参培数(外单兼职)", 0) or 0)
                            trainees = int(row.get("参培数", 0) or 0)

                            # 2. 写入/覆盖 performance_data（以最后一版导入数据为准）
                            c.execute(
                                """INSERT OR REPLACE INTO performance_data 
                                   (date, employee_name, invites, interviews, inner_ft, inner_pt, outer_ft, outer_pt, trainees)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    date_val,
                                    emp_val,
                                    invites,
                                    interviews,
                                    inner_ft,
                                    inner_pt,
                                    outer_ft,
                                    outer_pt,
                                    trainees,
                                ),
                            )
                            success_count += 1
                        conn.commit()
                    st.success(
                        f"🎉 成功导入历史日报表！共处理并覆盖更新了 {success_count} 条记录（已严格按照最后一版覆盖，不累加）。"
                    )
                    st.rerun()
            except Exception as e:
                st.error(
                    f"❌ 导入失败，请检查文件格式是否与标准日报表模板一致。错误信息：{e}"
                )

    st.write("---")

    col_view, col_date, col_filter = st.columns([1, 1.2, 1.8])
    view_mode = col_view.radio(
        "数据维度", ["📅 当日全链路", "📆 单月累计业绩"], horizontal=True
    )

    if "单月" in view_mode:
        col_y, col_m = col_date.columns(2)
        selected_year = col_y.selectbox("年份", [2026, 2025], index=0)
        selected_m_str = col_m.selectbox(
            "月份",
            [f"{m:02d}月" for m in range(1, 13)],
            index=YESTERDAY.month - 1,
        )
        month_str = f"{selected_year}-{selected_m_str.replace('月', '')}"
        date_filter_p = f"{month_str}%"
        date_filter_perf = f"{month_str}%"
        current_time_tag = month_str
    else:
        selected_date = col_date.date_input("选择统计日期", YESTERDAY)
        date_str = selected_date.strftime("%Y-%m-%d")
        date_filter_p = date_str
        date_filter_perf = date_str
        current_time_tag = date_str

    if not is_admin:
        selected_employees = [st.session_state.real_name]
        col_filter.info(
            f"🔒 数据范围：已锁定当前登录员工 **[{st.session_state.real_name}]**"
        )
    else:
        selected_employees = col_filter.multiselect(
            "筛选员工姓名", all_team_members, default=all_team_members
        )

    with sqlite3.connect(DB_PATH) as conn:
        if "单月" in view_mode:
            df_p = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, SUM(i_looked) as 我看过, SUM(seen_me) as 看过我,
                          SUM(i_greeted) as 我打招呼, SUM(candidate_greeted) as 牛人新招呼,
                          SUM(i_communicated) as 我沟通, SUM(received_resumes) as 收获简历,
                          SUM(exchanged_contact) as 交换电话微信, SUM(accepted_interview) as 接受面试
                   FROM platform_data WHERE date LIKE ? GROUP BY employee_name""",
                conn,
                params=[date_filter_p],
            )
            df_perf = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, 
                          SUM(invites) as 邀约数, SUM(interviews) as 到面数,
                          SUM(inner_ft) as "参培数(内单全职)", SUM(inner_pt) as "参培数(内单兼职)",
                          SUM(outer_ft) as "参培数(外单全职)", SUM(outer_pt) as "参培数(外单兼职)",
                          SUM(trainees) as 参培数
                   FROM performance_data WHERE date LIKE ? GROUP BY employee_name""",
                conn,
                params=[date_filter_perf],
            )
        else:
            df_p = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, SUM(i_looked) as 我看过, SUM(seen_me) as 看过我,
                          SUM(i_greeted) as 我打招呼, SUM(candidate_greeted) as 牛人新招呼,
                          SUM(i_communicated) as 我沟通, SUM(received_resumes) as 收获简历,
                          SUM(exchanged_contact) as 交换电话微信, SUM(accepted_interview) as 接受面试
                   FROM platform_data WHERE date = ? GROUP BY employee_name""",
                conn,
                params=[date_filter_p],
            )
            df_perf = pd.read_sql_query(
                """SELECT employee_name as 员工姓名, 
                          SUM(invites) as 邀约数, SUM(interviews) as 到面数,
                          SUM(inner_ft) as "参培数(内单全职)", SUM(inner_pt) as "参培数(内单兼职)",
                          SUM(outer_ft) as "参培数(外单全职)", SUM(outer_pt) as "参培数(外单兼职)",
                          SUM(trainees) as 参培数
                   FROM performance_data WHERE date = ? GROUP BY employee_name""",
                conn,
                params=[date_filter_perf],
            )

    df_base = pd.DataFrame({"员工姓名": selected_employees})
    df_summary = pd.merge(df_base, df_p, on="员工姓名", how="left")
    df_summary = pd.merge(df_summary, df_perf, on="员工姓名", how="left").fillna(
        0
    )

    df_summary["到面转化率数值"] = df_summary.apply(
        lambda r: (
            (r["到面数"] / r["邀约数"] * 100)
            if r.get("邀约数", 0) > 0
            else 0.0
        ),
        axis=1,
    )

    numeric_cols_to_sum = [
        "我看过",
        "看过我",
        "我打招呼",
        "牛人新招呼",
        "我沟通",
        "收获简历",
        "交换电话微信",
        "接受面试",
        "邀约数",
        "到面数",
        "参培数(内单全职)",
        "参培数(内单兼职)",
        "参培数(外单全职)",
        "参培数(外单兼职)",
        "参培数",
    ]

    total_row = {"员工姓名": "合计"}
    for col in numeric_cols_to_sum:
        total_row[col] = df_summary[col].sum()

    total_invites = total_row["邀约数"]
    total_interviews = total_row["到面数"]
    total_row["到面转化率数值"] = (
        (total_interviews / total_invites * 100) if total_invites > 0 else 0.0
    )

    df_display = pd.concat(
        [df_summary, pd.DataFrame([total_row])], ignore_index=True
    )
    df_display["到面转化率"] = df_display["到面转化率数值"].apply(
        lambda x: f"{x:.1f}%"
    )

    final_cols = [
        "员工姓名",
        "我看过",
        "看过我",
        "我打招呼",
        "牛人新招呼",
        "我沟通",
        "收获简历",
        "交换电话微信",
        "接受面试",
        "邀约数",
        "到面数",
        "参培数(内单全职)",
        "参培数(内单兼职)",
        "参培数(外单全职)",
        "参培数(外单兼职)",
        "参培数",
        "到面转化率",
    ]

    st.subheader(f"📋 招聘全链路汇总表 ({current_time_tag})")
    df_board_show = df_display[final_cols].copy()
    df_board_show.index = range(1, len(df_board_show) + 1)
    st.dataframe(
        df_board_show,
        height=250 if not is_admin else 400,
        use_container_width=True,
    )

    date_col_name = "周期月份" if "单月" in view_mode else "具体日期"
    df_export = df_display[final_cols].copy()
    df_export.insert(0, date_col_name, current_time_tag)

    st.markdown("##### 📥 导出数据")
    col_exp1, col_exp2 = st.columns([1, 1])
    report_type_name = "月报表" if "单月" in view_mode else "日报表"

    with col_exp1:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_export.to_excel(
                writer, index=False, sheet_name=report_type_name
            )
        st.download_button(
            label=f"📊 导出 {report_type_name} Excel (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=(
                f"招聘{report_type_name}_{st.session_state.real_name}_{current_time_tag}.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    with col_exp2:
        csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=f"📄 导出 {report_type_name} CSV (.csv)",
            data=csv_bytes,
            file_name=(
                f"招聘{report_type_name}_{st.session_state.real_name}_{current_time_tag}.csv"
            ),
            mime="text/csv",
        )

    if is_admin and len(df_summary) > 1:
        st.write("---")
        st.subheader("📊 招聘关键过程与结果指标团队排名")
        r1_col1, r1_col2, r1_col3 = st.columns(3)
        with r1_col1:
            render_full_ranking(df_summary, "看过我", "看过我人数", "人")
        with r1_col2:
            render_full_ranking(
                df_summary, "我打招呼", "我打招呼次数", "次"
            )
        with r1_col3:
            render_full_ranking(
                df_summary, "牛人新招呼", "牛人新招呼数", "个"
            )

        r2_col1, r2_col2, r2_col3 = st.columns(3)
        with r2_col1:
            render_full_ranking(df_summary, "我沟通", "我沟通人数", "人")
        with r2_col2:
            render_full_ranking(
                df_summary, "交换电话微信", "交换电话微信数", "人"
            )
        with r2_col3:
            render_full_ranking(
                df_summary, "收获简历", "收获简历数量", "份"
            )

        r3_col1, r3_col2, r3_col3 = st.columns(3)
        with r3_col1:
            render_full_ranking(df_summary, "邀约数", "新增邀约数", "人")
        with r3_col2:
            render_full_ranking(df_summary, "到面数", "到面数", "人")
        with r3_col3:
            render_full_ranking(df_summary, "参培数", "参培数", "人")

    st.write("---")
    st.subheader("🤖 智能过程漏斗卡点诊断与预警 (AI 大模型引擎)")
    with st.spinner("🤖 通义千问大模型正在分析招聘过程漏斗，撰写归因诊断..."):
        alerts = run_alert_engine(
            df_summary, is_monthly=("单月" in view_mode)
        )

    if alerts:
        for a in alerts:
            card_class = (
                "alert-card-danger"
                if "🚨" in a["level"]
                else "alert-card-warning"
            )
            st.markdown(
                f"<div class='{card_class}'><b>【{a['level']}】{a['name']} -"
                f" {a['issue']}</b><br/>• <b>卡点数据：</b>"
                f" {a['data']}<br/>• <b>AI 归因诊断：</b>"
                f" {a['reason']}<br/>• <b>AI 建议动作：</b>"
                f" {a['action']}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("🎉 全员数据表现正常，暂无过程卡点预警！")

# ---------------------------------------------------------
# 模块三：数据端
# ---------------------------------------------------------
elif page == "📋 数据端：智能识图/录入业绩" and is_admin:
    st.markdown(
        "<div class='main-header'>📋 数据端：部门业绩汇总与智能识图录入</div>",
        unsafe_allow_html=True,
    )
    col_type, col_date = st.columns(2)
    data_type = col_type.radio(
        "📌 选择上传的数据表类型：",
        ["📅 日度业绩表", "📆 单月累计业绩表"],
        horizontal=True,
    )
    p_date_img = col_date.date_input("选择业绩数据日期", YESTERDAY)
    date_str = p_date_img.strftime("%Y-%m-%d")

    st.write("---")
    img_type_label = "【日度】" if "日度" in data_type else "【单月累计】"
    uploaded_perf_img = st.file_uploader(
        f"上传{img_type_label}表格截图", type=["jpg", "png", "jpeg"]
    )

    if uploaded_perf_img is not None:
        image = Image.open(uploaded_perf_img)
        st.image(image, caption="已上传截图", width=400)
        with st.spinner("🤖 正在调用通义千问视觉大模型识别表格数据..."):
            df_extracted = llm_supervisor_ocr(image, all_team_members)

        edited_df = st.data_editor(df_extracted, num_rows="dynamic")
        edited_df["参培数"] = (
            edited_df["参培数(内单全职)"]
            + edited_df["参培数(内单兼职)"]
            + edited_df["参培数(外单全职)"]
            + edited_df["参培数(外单兼职)"]
        )

        if st.button(f"💾 确认提交{img_type_label}数据入库"):
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                for _, row in edited_df.iterrows():
                    emp = row["员工姓名"]
                    c.execute(
                        "SELECT id FROM performance_data WHERE date = ? AND employee_name = ?",
                        (date_str, emp),
                    )
                    exist = c.fetchone()
                    if "日度" in data_type:
                        if exist:
                            c.execute(
                                """UPDATE performance_data SET invites=?, interviews=?, inner_ft=?, inner_pt=?, outer_ft=?, outer_pt=?, trainees=? WHERE id=?""",
                                (
                                    int(row["邀约数"]),
                                    int(row["到面数"]),
                                    int(row["参培数(内单全职)"]),
                                    int(row["参培数(内单兼职)"]),
                                    int(row["参培数(外单全职)"]),
                                    int(row["参培数(外单兼职)"]),
                                    int(row["参培数"]),
                                    exist[0],
                                ),
                            )
                        else:
                            c.execute(
                                """INSERT INTO performance_data (date, employee_name, invites, interviews, inner_ft, inner_pt, outer_ft, outer_pt, trainees) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    date_str,
                                    emp,
                                    int(row["邀约数"]),
                                    int(row["到面数"]),
                                    int(row["参培数(内单全职)"]),
                                    int(row["参培数(内单兼职)"]),
                                    int(row["参培数(外单全职)"]),
                                    int(row["参培数(外单兼职)"]),
                                    int(row["参培数"]),
                                ),
                            )
                conn.commit()
            st.success(f"🎉 成功更新覆盖 {date_str} 的业绩数据！")
            st.rerun()

# ---------------------------------------------------------
# 模块四：管理端
# ---------------------------------------------------------
elif page == "⚙️ 管理端：账号管理与记录维护" and is_admin:
    st.markdown(
        "<div class='main-header'>⚙️ 后台管理中心 (管理员权限)</div>",
        unsafe_allow_html=True,
    )
    tab1, tab2 = st.tabs(["👤 员工与账号管理", "🗑️ 数据记录删除与维护"])
    with tab1:
        st.subheader("📋 现有人员与账号列表")
        with sqlite3.connect(DB_PATH) as conn:
            df_users = pd.read_sql_query(
                "SELECT id as 用户编号, username as 账号, real_name as 姓名, role as 角色 FROM users",
                conn,
            )
        st.dataframe(df_users, use_container_width=True)
    with tab2:
        st.subheader("📋 所有平台上传记录维护")
        with sqlite3.connect(DB_PATH) as conn:
            df_records = pd.read_sql_query(
                "SELECT id as 记录编号, date as 归属日期, employee_name as 员工姓名 FROM platform_data ORDER BY id DESC",
                conn,
            )
        st.dataframe(df_records, use_container_width=True)