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
    
    /* 需求3优化：将排名表边框改窄、收紧内边距与边距，减少不必要的空白 */
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
    """全局单例 LLM 客户端，避免重复建立 HTTP 连接"""
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

        c.execute("PRAGMA table_info(platform_data)")
        existing_cols = [col[1] for col in c.fetchall()]

        required_cols = {
            "i_looked": "INTEGER DEFAULT 0",
            "seen_me": "INTEGER DEFAULT 0",
            "i_greeted": "INTEGER DEFAULT 0",
            "candidate_greeted": "INTEGER DEFAULT 0",
            "i_communicated": "INTEGER DEFAULT 0",
            "received_resumes": "INTEGER DEFAULT 0",
            "exchanged_contact": "INTEGER DEFAULT 0",
            "accepted_interview": "INTEGER DEFAULT 0",
        }

        for col_name, col_type in required_cols.items():
            if col_name not in existing_cols:
                try:
                    c.execute(
                        f"ALTER TABLE platform_data ADD COLUMN {col_name} {col_type}"
                    )
                except Exception:
                    pass

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
                        st.error(
                            "❌ 账号或密码错误！(默认员工密码为 123456，管理员账号 admin/admin123)"
                        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------
# 4. 辅助函数与视觉 AI OCR 及大模型诊断引擎
# ---------------------------------------------------------
def mock_employee_ocr(image: Image.Image) -> dict:
    """接入通义千问大模型精准抓取截图数据，以固定8个数据表头为主锚点"""
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
        你是一个精准的数据提取与 OCR 视觉专家。图片中是招聘平台（如 Boss 直聘）的数据概览看板。

        【必须提取的固定 8 个数据表头】：
        1. 我看过  2. 看过我  3. 我打招呼  4. 牛人新招呼  5. 我沟通  6. 收获简历  7. 交换电话微信  8. 接受面试

        【输出格式要求】：
        必须且只能输出严格的纯 JSON 格式，不要包含任何 markdown 标签或多余文字。例如：
        {
            "我看过": 27,
            "看过我": 268,
            "我打招呼": 113,
            "牛人新招呼": 27,
            "我沟通": 217,
            "收获简历": 2,
            "交换电话微信": 10,
            "接受面试": 0
        }
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
            extra_body={"enable_thinking": QWEN_CONFIG["enable_thinking"]},
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
                raw_val = str(parsed_data[header_name])
                match = re.search(r"\d+", raw_val)
                if match:
                    default_result[key_name] = int(match.group())

        return default_result

    except Exception as e:
        st.warning(
            f"⚠️ 视觉模型识别出现波动 ({e})，系统已采用缺省填报架构。"
        )
        return default_result


def llm_supervisor_ocr(image: Image.Image, members: list) -> pd.DataFrame:
    """使用 SiliconFlow 通义千问多模态模型识别招聘数据表格（含自动对齐与长度校验防报错）"""
    try:
        client = get_llm_client()

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = f"""
        你是一个专业的数据提取助手。请仔细识别图片中表格包含的招聘数据。
        【目标员工列表】：{json.dumps(members, ensure_ascii=False)}
        必须只输出严格的 JSON 数组结构，数组中每个元素为一个对象，包含以下键：
        - "员工姓名"
        - "邀约数"
        - "到面数"
        - "参培数(内单全职)"
        - "参培数(内单兼职)"
        - "参培数(外单全职)"
        - "参培数(外单兼职)"
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
            extra_body={"enable_thinking": QWEN_CONFIG["enable_thinking"]},
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

        if "员工姓名" in df_raw.columns:
            df_raw["员工姓名"] = df_raw["员工姓名"].astype(str).str.strip()
            df = pd.merge(base_df, df_raw, on="员工姓名", how="left")
        else:
            df = base_df.copy()

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

    except Exception as e:
        st.error(f"⚠️ 大模型识别出现异常 ({e})，已切换至基础表结构。")
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


def generate_enhanced_ai_diagnosis(df_summary, is_monthly=False):
    """
    升级版 AI 诊断引擎：涵盖过程影响分析、三维预警（引流/产能/跟进）、优缺点及下一步安排
    """
    client = get_llm_client()
    time_tag = "月度" if is_monthly else "日度"

    # 过滤掉“合计”行，转换纯数据 JSON
    df_filtered = df_summary[df_summary["员工姓名"] != "合计"].copy()
    summary_data_json = df_filtered.to_json(
        orient="records", force_ascii=False
    )

    prompt = f"""
你是一位资深招聘效能专家与数据分析师。请根据以下员工的【{time_tag}】招聘全链路过程与结果数据进行深度诊断分析。

【全员招聘数据】：
{summary_data_json}

【分析任务要求】：
请针对表格中的每一位招聘专员，从以下三个维度进行分析，并输出严格的 JSON 格式数据：

1. **过程数据对结果数的影响分析**：
   - 评估该员工的平台使用数据（我看过、我打招呼、我沟通、交换微信/简历）对其最终【邀约数】、【到面数】、【参培数】的核心影响点。
2. **个人优缺点与三大预警诊断**：
   - **优点**：分析其表现突出的过程或结果指标。
   - **缺点/卡点**：分析其转化率较低或漏斗断层的地方。
   - **引流预警（平台流量异常）**：分析其“看过我”、“牛人新招呼”或“我打招呼”是否偏低或回复率异常。
   - **产能预警（实际参训数）**：评估其实际参培数是否达标（月度<3人或日度=0为预警）。
   - **跟进预警（私域与邀约）**：评估“交换微信/简历”后未能转化为“邀约数”或“到面数”的跟进滞后问题。
3. **下一步具体优化安排**：
   - 给出 2-3 条极具操作性的落地改进计划（如：调整招呼话术、提高私域 2 小时跟进率、优化匹配画像等）。

【输出格式要求】：
必须且只能输出严格的 JSON 数组，格式如下（严禁包含 markdown 标记或多余文字）：
[
  {{
    "name": "员工姓名",
    "influence_analysis": "平台数据（如打招呼偏低）直接限制了私域获取，进而导致邀约基数不足...",
    "pros": "主动沟通量高，私域留存率表现优秀",
    "cons": "私域到邀约转化率偏低，到面参培率有待提升",
    "traffic_alert": "正常 / ⚠️ 流量预警：曝光量及牛人主动招呼量显著低于团队均值",
    "capacity_alert": "正常 / 🚨 产能预警：本期参培人数为0，产出严重不足",
    "followup_alert": "正常 / ⚠️ 跟进预警：已留存微信15人但仅邀约2人，跟进闭环存在滞后",
    "next_steps": [
      "1. 针对留存微信未邀约人员，在24小时内进行电话二次复核；",
      "2. 重新梳理招呼话术，提升打招呼到沟通的转化率。"
    ]
  }}
]
"""
    try:
        response = client.chat.completions.create(
            model=QWEN_CONFIG["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的 HR 数据效能分析与团队管理专家。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            extra_body={"enable_thinking": QWEN_CONFIG["enable_thinking"]},
        )

        res_text = response.choices[0].message.content.strip()
        if res_text.startswith("```"):
            lines = res_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            res_text = "\n".join(lines).strip()

        return json.loads(res_text)
    except Exception as e:
        st.error(f"⚠️ AI 诊断分析生成波动: {e}")
        return []


def render_full_ranking(df, col_name, title_name, unit=""):
    """需求3优化：渲染边框更窄、留白更紧凑的排名卡片"""
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
            f" 的数据（提交时间：{existing_time}）。**再次提交将自动覆盖替换上一张数据**。"
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
    st.subheader("2️⃣ 上传平台截图")

    # 需求1优化：使用动态 key 绑定的 file_uploader，上传成功后重置该 key 即可自动清空文件
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

            # 需求1：提交成功后累加 uploader_key，促使图片框自动清空
            st.session_state.uploader_key += 1

            st.balloons()
            st.success(
                f"🎉 提交成功！[{emp_name}] 在 [{date_str}] 的 [{platform_ver}]"
                " 数据已更新覆盖！图片上传框已清空。"
            )
            st.rerun()

    st.write("---")
    st.subheader("📜 个人历史数据上传记录与维护")
    with sqlite3.connect(DB_PATH) as conn:
        emp_records_df = pd.read_sql_query(
            """SELECT id as 记录编号, date as 数据日期, platform_version as 平台账号, 
                      i_looked as 我看过, seen_me as 看过我, i_greeted as 我打招呼, candidate_greeted as 牛人新招呼,
                      i_communicated as 我沟通, received_resumes as 收获简历, 
                      exchanged_contact as 交换电话微信, accepted_interview as 接受面试, created_at as 提交时间 
               FROM platform_data WHERE employee_name = ? ORDER BY id DESC""",
            conn,
            params=[emp_name],
        )

    if not emp_records_df.empty:
        emp_records_df.index = range(1, len(emp_records_df) + 1)
        st.dataframe(emp_records_df, use_container_width=True)

        col_del1, col_del2 = st.columns([3, 1])
        with col_del1:
            record_to_del = st.selectbox(
                "选择要删除的错误提交记录：",
                options=emp_records_df["记录编号"].tolist(),
                format_func=lambda x: (
                    f"记录编号 #{x} | 日期:"
                    f" {emp_records_df[emp_records_df['记录编号']==x]['数据日期'].values[0]}"
                    " | 平台:"
                    f" {emp_records_df[emp_records_df['记录编号']==x]['平台账号'].values[0]}"
                ),
            )
        with col_del2:
            st.write("")
            st.write("")
            if st.button("🗑️ 删除选中的记录", type="primary"):
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute(
                        "DELETE FROM platform_data WHERE id = ?",
                        (record_to_del,),
                    )
                    conn.commit()
                st.success(f"✅ 记录 #{record_to_del} 已成功删除！")
                st.rerun()
    else:
        st.info("ℹ️ 暂无历史上传记录。")

# ---------------------------------------------------------
# 模块二：数据看板（包含最新 9 大 KPI 指标排名区与 AI 深度诊断）
# ---------------------------------------------------------
elif page == "📊 业务预警与数据看板":
    st.markdown(
        "<div class='main-header'>📊 招聘全链路过程数据监控看板</div>",
        unsafe_allow_html=True,
    )

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
        current_time_tag = month_str  # 用于导出的周期标识 (YYYY-MM)
    else:
        selected_date = col_date.date_input("选择统计日期", YESTERDAY)
        date_str = selected_date.strftime("%Y-%m-%d")
        date_filter_p = date_str
        date_filter_perf = date_str
        current_time_tag = date_str  # 用于导出的具体日期标识 (YYYY-MM-DD)

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
                          MAX(month_invites) as 邀约数, MAX(month_interviews) as 到面数,
                          MAX(month_inner_ft) as "参培数(内单全职)", MAX(month_inner_pt) as "参培数(内单兼职)",
                          MAX(month_outer_ft) as "参培数(外单全职)", MAX(month_outer_pt) as "参培数(外单兼职)",
                          MAX(month_trainees) as 参培数
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

    # 需求2优化：在导出的 Dataframe 中注入时间字段（日报表显示具体日期，月报表显示周期月份）
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

    # ---------------------------------------------------------
    # 📌 精简后的 9 大 KPI 团队排名面板
    # ---------------------------------------------------------
    if is_admin and len(df_summary) > 1:
        st.write("---")
        st.subheader("📊 招聘关键过程与结果指标团队排名")

        # 第一排：曝光与主动动作（3个）
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

        # 第二排：沟通与留存转化（3个）
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

        # 第三排：邀约与终局结果（3个）
        r3_col1, r3_col2, r3_col3 = st.columns(3)
        with r3_col1:
            render_full_ranking(df_summary, "邀约数", "新增邀约数", "人")
        with r3_col2:
            render_full_ranking(df_summary, "到面数", "到面数", "人")
        with r3_col3:
            render_full_ranking(df_summary, "参培数", "参培数", "人")

    # ---------------------------------------------------------
    # 🤖 AI 大模型诊断与下一步优化安排模块
    # ---------------------------------------------------------
    st.write("---")
    st.subheader("🤖 全链路数据诊断与下一步优化安排 (AI 引擎)")

    with st.spinner(
        "🤖 通义千问大模型正在进行平台影响分析、三大预警诊断与下一步排期..."
    ):
        analysis_results = generate_enhanced_ai_diagnosis(
            df_summary, is_monthly=("单月" in view_mode)
        )

    if analysis_results:
        for item in analysis_results:
            with st.expander(
                f"👤 **{item['name']}** 的深度效能诊断与优化排期",
                expanded=True,
            ):
                col_a, col_b = st.columns([1.2, 1])

                with col_a:
                    st.markdown(
                        "**📌 过程数据对结果影响：**\n"
                        f"{item['influence_analysis']}"
                    )
                    st.markdown(f"**👍 个人优势：** {item['pros']}")
                    st.markdown(f"**⚠️ 薄弱环节：** {item['cons']}")

                with col_b:
                    st.markdown("**🚨 三维诊断预警：**")
                    st.caption(
                        f"• **引流预警（平台流量）：** {item['traffic_alert']}"
                    )
                    st.caption(
                        f"• **跟进预警（转化闭环）：** {item['followup_alert']}"
                    )
                    st.caption(
                        f"• **产能预警（实际参培）：** {item['capacity_alert']}"
                    )

                st.markdown("---")
                st.markdown("**🎯 下一步具体优化安排：**")
                for step in item.get("next_steps", []):
                    st.markdown(f"- {step}")
    else:
        st.info("ℹ️ 暂无诊断数据，请检查数据提交情况。")

# ---------------------------------------------------------
# 模块三：数据端
# ---------------------------------------------------------
elif page == "📋 数据端：智能识图/录入业绩" and is_admin:
    st.markdown(
        "<div class='main-header'>📋 数据端：部门业绩汇总与智能识图录入"
        " (管理员专用)</div>",
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

        with st.spinner(
            "🤖 正在调用通义千问视觉大模型识别表格数据，请稍候..."
        ):
            df_extracted = llm_supervisor_ocr(image, all_team_members)

        st.info(
            "💡"
            " 请在下方核对识图抓取结果（数据重复上传将自动按日期和员工覆盖历史记录）："
        )
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
                for idx, row in edited_df.iterrows():
                    emp = row["员工姓名"]
                    c.execute(
                        "SELECT id FROM performance_data WHERE date = ? AND"
                        " employee_name = ?",
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
                    else:
                        if exist:
                            c.execute(
                                """UPDATE performance_data SET month_invites=?, month_interviews=?, month_inner_ft=?, month_inner_pt=?, month_outer_ft=?, month_outer_pt=?, month_trainees=? WHERE id=?""",
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
                                """INSERT INTO performance_data (date, employee_name, month_invites, month_interviews, month_inner_ft, month_inner_pt, month_outer_ft, month_outer_pt, month_trainees) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            st.balloons()
            st.success(
                f"🎉 成功更新覆盖 {date_str} 的{img_type_label}业绩数据！"
            )
            st.rerun()

    st.write("---")
    st.subheader("🔍 历史业绩数据查询与单条删除维护")
    with sqlite3.connect(DB_PATH) as conn:
        perf_records_df = pd.read_sql_query(
            """SELECT id as 记录编号, date as 数据日期, employee_name as 员工姓名, 
                      invites as 日邀约, interviews as 日到面, trainees as 日参培,
                      month_invites as 月邀约, month_interviews as 月到面, month_trainees as 月参培
               FROM performance_data ORDER BY id DESC""",
            conn,
        )

    if not perf_records_df.empty:
        perf_records_df.index = range(1, len(perf_records_df) + 1)
        st.dataframe(perf_records_df, use_container_width=True)

        col_del_p1, col_del_p2 = st.columns([3, 1])
        with col_del_p1:
            perf_id_to_del = st.selectbox(
                "选择需要删除的历史业绩记录 ID：",
                options=perf_records_df["记录编号"].tolist(),
                format_func=lambda x: (
                    f"记录编号 #{x} | 日期:"
                    f" {perf_records_df[perf_records_df['记录编号']==x]['数据日期'].values[0]}"
                    " | 员工:"
                    f" {perf_records_df[perf_records_df['记录编号']==x]['员工姓名'].values[0]}"
                ),
            )
        with col_del_p2:
            st.write("")
            st.write("")
            if st.button("🗑️ 删除选中记录", type="primary"):
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute(
                        "DELETE FROM performance_data WHERE id = ?",
                        (perf_id_to_del,),
                    )
                    conn.commit()
                st.success(f"✅ 业绩记录 #{perf_id_to_del} 已清除！")
                st.rerun()
    else:
        st.info("ℹ️ 暂无历史业绩表数据。")

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
                        c.execute(
                            "INSERT INTO users (username, password, real_name,"
                            " role) VALUES (?, ?, ?, 'employee')",
                            (new_username, new_password, new_realname),
                        )
                        conn.commit()
                    st.success(
                        f"✅ 成功创建员工账号：{new_realname} ({new_username})"
                    )
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("❌ 该登录账号已存在，请更换其他账号名！")
            else:
                st.warning("⚠️ 请填满所有账号信息！")

        st.write("---")

        st.subheader("📋 现有人员与账号列表")
        with sqlite3.connect(DB_PATH) as conn:
            df_users = pd.read_sql_query(
                "SELECT id as 用户编号, username as 账号, real_name as 姓名, role"
                " as 角色, password as 密码 FROM users",
                conn,
            )
        df_users.index = range(1, len(df_users) + 1)
        st.dataframe(df_users, use_container_width=True)

        st.write("---")
        st.subheader("✏️ 修改账号信息 / 重置密码")

        if not df_users.empty:
            edit_user_id = st.selectbox(
                "选择需要修改的账号：",
                options=df_users["用户编号"].tolist(),
                format_func=lambda x: (
                    f"编号 #{x} | 账号:"
                    f" {df_users[df_users['用户编号']==x]['账号'].values[0]} |"
                    " 姓名:"
                    f" {df_users[df_users['用户编号']==x]['姓名'].values[0]}"
                ),
            )

            current_user = df_users[
                df_users["用户编号"] == edit_user_id
            ].iloc[0]

            col_e1, col_e2, col_e3, col_e4 = st.columns([1.5, 1.5, 1.5, 1])
            edit_username = col_e1.text_input(
                "登录账号", value=current_user["账号"], key="edit_username"
            )
            edit_realname = col_e2.text_input(
                "真实姓名", value=current_user["姓名"], key="edit_realname"
            )
            edit_password = col_e3.text_input(
                "密码", value=current_user["密码"], key="edit_password"
            )

            if col_e4.button("💾 保存修改", type="primary"):
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute(
                            "UPDATE users SET username = ?, real_name = ?,"
                            " password = ? WHERE id = ?",
                            (
                                edit_username,
                                edit_realname,
                                edit_password,
                                edit_user_id,
                            ),
                        )
                        conn.commit()
                    st.success("✅ 账号信息更新成功！")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("❌ 更改后的登录账号与已有其他账号冲突！")

        st.write("---")
        st.subheader("🗑️ 删除员工账号")
        col_del_u, col_del_ubtn = st.columns([2, 1])
        user_list = df_users[df_users["角色"] != "admin"]

        if not user_list.empty:
            del_user_id = col_del_u.selectbox(
                "选择需要删除的员工账号：",
                options=user_list["用户编号"].tolist(),
                format_func=lambda x: (
                    f"编号 #{x} | 姓名:"
                    f" {user_list[user_list['用户编号']==x]['姓名'].values[0]} |"
                    " 账号:"
                    f" {user_list[user_list['用户编号']==x]['账号'].values[0]}"
                ),
            )
            if col_del_ubtn.button("🔥 确认删除账号", type="primary"):
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute(
                        "DELETE FROM users WHERE id = ?", (del_user_id,)
                    )
                    conn.commit()
                st.success("✅ 账号删除成功！")
                st.rerun()

    with tab2:
        st.subheader("📋 所有平台上传记录维护")
        with sqlite3.connect(DB_PATH) as conn:
            df_records = pd.read_sql_query(
                """SELECT id as 记录编号, date as 归属日期, employee_name as 员工姓名, platform_version as 平台账号,
                          i_looked as 我看过, seen_me as 看过我, i_greeted as 我打招呼, candidate_greeted as 牛人新招呼,
                          i_communicated as 我沟通, received_resumes as 收到简历,
                          exchanged_contact as 交换电话微信, accepted_interview as 接受面试, created_at as 更新时间
                   FROM platform_data ORDER BY id DESC""",
                conn,
            )

        if not df_records.empty:
            col_f1, col_f2 = st.columns(2)
            filter_name = col_f1.selectbox(
                "按员工筛选记录", ["全部"] + all_team_members
            )

            df_show = df_records.copy()
            if filter_name != "全部":
                df_show = df_show[df_show["员工姓名"] == filter_name]

            df_show.index = range(1, len(df_show) + 1)
            st.dataframe(df_show, use_container_width=True, height=300)

            st.write("---")
            st.subheader("⚠️ 彻底删除指定的错误提交记录")
            col_del_id, col_del_btn = st.columns([2, 1])

            record_options = df_show["记录编号"].tolist()
            if record_options:
                selected_id = col_del_id.selectbox(
                    "选择需要删除的记录编号 (ID):",
                    options=record_options,
                    format_func=lambda x: (
                        f"编号 #{x} |"
                        f" {df_show[df_show['记录编号']==x]['归属日期'].values[0]}"
                        " |"
                        f" {df_show[df_show['记录编号']==x]['员工姓名'].values[0]}"
                        " |"
                        f" {df_show[df_show['记录编号']==x]['平台账号'].values[0]}"
                    ),
                )
                if col_del_btn.button("🔥 确认删除记录", type="primary"):
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute(
                            "DELETE FROM platform_data WHERE id = ?",
                            (selected_id,),
                        )
                        conn.commit()
                    st.success(f"✅ 记录 #{selected_id} 已彻底删除！")
                    st.rerun()
        else:
            st.info("ℹ️ 暂无平台提交记录。")