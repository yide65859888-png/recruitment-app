import base64
from concurrent.futures import ThreadPoolExecutor
import datetime
import io
import json
import re
from openai import OpenAI
import pandas as pd
from PIL import Image
import streamlit as st

# 导入 Supabase SDK
from supabase import create_client, Client

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

QWEN_CONFIG = {
    "api_key": "sk-eogrtqfwedttonwhabcvsvswmmfnncjqlzbesnhtbqlanrzy",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen3.6-35B-A3B",
    "enable_thinking": False,
}

# ---------------------------------------------------------
# 2. Supabase 云数据库与 LLM 初始化
# ---------------------------------------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase_client()


@st.cache_resource
def get_llm_client():
    return OpenAI(
        api_key=QWEN_CONFIG["api_key"], base_url=QWEN_CONFIG["base_url"]
    )


def get_all_employee_names():
    try:
        res = (
            supabase.table("users")
            .select("real_name")
            .eq("role", "employee")
            .execute()
        )
        names = [r["real_name"] for r in res.data]
        return names if names else DEFAULT_MEMBERS
    except Exception:
        return DEFAULT_MEMBERS


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
    res = (
        supabase.table("users")
        .select("username, real_name, role")
        .eq("username", username.strip())
        .eq("password", password.strip())
        .execute()
    )
    if res.data:
        u = res.data[0]
        return u["username"], u["real_name"], u["role"]
    return None


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
# 4. 视觉 AI OCR 及大模型诊断引擎
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
        你是一个精准的数据提取与 OCR 视觉专家。图片中是招聘平台（如 Boss 直聘）的数据概览看板。
        【必须提取的固定 8 个数据表头】：
        1. 我看过  2. 看过我  3. 我打招呼  4. 牛人新招呼  5. 我沟通  6. 收获简历  7. 交换电话微信  8. 接受面试
        输出纯 JSON 格式。
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
        st.warning(f"⚠️ 视觉模型识别波动 ({e})")
        return default_result


def llm_supervisor_ocr(image: Image.Image, members: list) -> pd.DataFrame:
    try:
        client = get_llm_client()
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = f"""
        请识别图片中表格招聘数据。
        【目标员工列表】：{json.dumps(members, ensure_ascii=False)}
        必须输出 JSON 数组，字段格式：
        "员工姓名", "邀约数", "到面数", "参培数(内单全职)", "参培数(内单兼职)", "参培数(外单全职)", "参培数(外单兼职)"
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

        df_raw = pd.DataFrame(json.loads(content))
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
        st.error(f"⚠️ 识别异常 ({e})")
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
    res = (
        supabase.table("platform_data")
        .select("created_at")
        .eq("date", date_str)
        .eq("employee_name", emp_name)
        .eq("platform_version", platform)
        .execute()
    )
    return res.data[0]["created_at"] if res.data else None


def generate_enhanced_ai_diagnosis(df_summary, is_monthly=False):
    client = get_llm_client()
    time_tag = "月度" if is_monthly else "日度"
    df_filtered = df_summary[df_summary["员工姓名"] != "合计"].copy()
    summary_data_json = df_filtered.to_json(
        orient="records", force_ascii=False
    )

    prompt = f"""
你是一位资深招聘效能专家。请根据以下员工的【{time_tag}】数据进行分析，输出 JSON 数组格式：
【全员招聘数据】：{summary_data_json}

结构要求：
[
  {{
    "name": "员工姓名",
    "influence_analysis": "平台过程对结果影响...",
    "pros": "优势...",
    "cons": "短板...",
    "traffic_alert": "正常 / 流量预警",
    "capacity_alert": "正常 / 产能预警",
    "followup_alert": "正常 / 跟进预警",
    "next_steps": ["1. ...", "2. ..."]
  }}
]
"""
    try:
        response = client.chat.completions.create(
            model=QWEN_CONFIG["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的 HR 数据效能分析专家。",
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
        st.error(f"⚠️ AI 诊断生成波动: {e}")
        return []


def render_full_ranking(df, col_name, title_name, unit=""):
    if col_name not in df.columns:
        return
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

            payload = {
                "date": date_str,
                "employee_name": emp_name,
                "platform_version": platform_ver,
                "i_looked": ocr["i_looked"],
                "seen_me": ocr["seen_me"],
                "i_greeted": ocr["i_greeted"],
                "candidate_greeted": ocr["candidate_greeted"],
                "i_communicated": ocr["i_communicated"],
                "received_resumes": ocr["received_resumes"],
                "exchanged_contact": ocr["exchanged_contact"],
                "accepted_interview": ocr["accepted_interview"],
            }
            # 利用 Supabase upsert 功能（需把 date, employee_name, platform_version 设为复合主键/唯一索引）
            supabase.table("platform_data").upsert(payload).execute()

            st.session_state.uploader_key += 1
            st.balloons()
            st.success(
                f"🎉 提交成功！[{emp_name}] 在 [{date_str}] 的 [{platform_ver}]"
                " 数据已同步至云端！"
            )
            st.rerun()

    st.write("---")
    st.subheader("📜 个人历史数据上传记录与维护")
    res_p = (
        supabase.table("platform_data")
        .select("*")
        .eq("employee_name", emp_name)
        .order("id", desc=True)
        .execute()
    )

    if res_p.data:
        emp_records_df = pd.DataFrame(res_p.data)
        emp_records_df = emp_records_df.rename(
            columns={
                "id": "记录编号",
                "date": "数据日期",
                "platform_version": "平台账号",
                "i_looked": "我看过",
                "seen_me": "看过我",
                "i_greeted": "我打招呼",
                "candidate_greeted": "牛人新招呼",
                "i_communicated": "我沟通",
                "received_resumes": "收获简历",
                "exchanged_contact": "交换电话微信",
                "accepted_interview": "接受面试",
                "created_at": "提交时间",
            }
        )
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
                supabase.table("platform_data").delete().eq(
                    "id", record_to_del
                ).execute()
                st.success(f"✅ 记录 #{record_to_del} 已成功删除！")
                st.rerun()
    else:
        st.info("ℹ️ 暂无历史上传记录。")

# ---------------------------------------------------------
# 模块二：数据看板
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
        date_filter = month_str
        current_time_tag = month_str
    else:
        selected_date = col_date.date_input("选择统计日期", YESTERDAY)
        date_str = selected_date.strftime("%Y-%m-%d")
        date_filter = date_str
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

    # 抽取 Supabase 数据逻辑
    if "单月" in view_mode:
        res_p = (
            supabase.table("platform_data")
            .select("*")
            .gte("date", f"{date_filter}-01")
            .lte("date", f"{date_filter}-31")
            .execute()
        )
        res_perf = (
            supabase.table("performance_data")
            .select("*")
            .gte("date", f"{date_filter}-01")
            .lte("date", f"{date_filter}-31")
            .execute()
        )
    else:
        res_p = (
            supabase.table("platform_data")
            .select("*")
            .eq("date", date_filter)
            .execute()
        )
        res_perf = (
            supabase.table("performance_data")
            .select("*")
            .eq("date", date_filter)
            .execute()
        )

    df_p_raw = pd.DataFrame(res_p.data) if res_p.data else pd.DataFrame()
    df_perf_raw = (
        pd.DataFrame(res_perf.data) if res_perf.data else pd.DataFrame()
    )

    df_base = pd.DataFrame({"员工姓名": selected_employees})

    if not df_p_raw.empty:
        df_p_grouped = (
            df_p_raw.groupby("employee_name")
            .agg({
                "i_looked": "sum",
                "seen_me": "sum",
                "i_greeted": "sum",
                "candidate_greeted": "sum",
                "i_communicated": "sum",
                "received_resumes": "sum",
                "exchanged_contact": "sum",
                "accepted_interview": "sum",
            })
            .reset_index()
            .rename(
                columns={
                    "employee_name": "员工姓名",
                    "i_looked": "我看过",
                    "seen_me": "看过我",
                    "i_greeted": "我打招呼",
                    "candidate_greeted": "牛人新招呼",
                    "i_communicated": "我沟通",
                    "received_resumes": "收获简历",
                    "exchanged_contact": "交换电话微信",
                    "accepted_interview": "接受面试",
                }
            )
        )
    else:
        df_p_grouped = pd.DataFrame(columns=["员工姓名"])

    if not df_perf_raw.empty:
        if "单月" in view_mode:
            df_perf_grouped = (
                df_perf_raw.groupby("employee_name")
                .agg({
                    "month_invites": "max",
                    "month_interviews": "max",
                    "month_inner_ft": "max",
                    "month_inner_pt": "max",
                    "month_outer_ft": "max",
                    "month_outer_pt": "max",
                    "month_trainees": "max",
                })
                .reset_index()
                .rename(
                    columns={
                        "employee_name": "员工姓名",
                        "month_invites": "邀约数",
                        "month_interviews": "到面数",
                        "month_inner_ft": "参培数(内单全职)",
                        "month_inner_pt": "参培数(内单兼职)",
                        "month_outer_ft": "参培数(外单全职)",
                        "month_outer_pt": "参培数(外单兼职)",
                        "month_trainees": "参培数",
                    }
                )
            )
        else:
            df_perf_grouped = (
                df_perf_raw.groupby("employee_name")
                .agg({
                    "invites": "sum",
                    "interviews": "sum",
                    "inner_ft": "sum",
                    "inner_pt": "sum",
                    "outer_ft": "sum",
                    "outer_pt": "sum",
                    "trainees": "sum",
                })
                .reset_index()
                .rename(
                    columns={
                        "employee_name": "员工姓名",
                        "invites": "邀约数",
                        "interviews": "到面数",
                        "inner_ft": "参培数(内单全职)",
                        "inner_pt": "参培数(内单兼职)",
                        "outer_ft": "参培数(外单全职)",
                        "outer_pt": "参培数(外单兼职)",
                        "trainees": "参培数",
                    }
                )
            )
    else:
        df_perf_grouped = pd.DataFrame(columns=["员工姓名"])

    df_summary = pd.merge(df_base, df_p_grouped, on="员工姓名", how="left")
    df_summary = pd.merge(
        df_summary, df_perf_grouped, on="员工姓名", how="left"
    ).fillna(0)

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

    # 兼容处理：确保所有指标列均存在并补充默认值 0
    for col in numeric_cols_to_sum:
        if col not in df_summary.columns:
            df_summary[col] = 0

    df_summary["到面转化率数值"] = df_summary.apply(
        lambda r: (
            (r["到面数"] / r["邀约数"] * 100)
            if r.get("邀约数", 0) > 0
            else 0.0
        ),
        axis=1,
    )

    total_row = {"员工姓名": "合计"}
    for col in numeric_cols_to_sum:
        total_row[col] = df_summary[col].sum() if not df_summary.empty else 0

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
        st.info("ℹ️ 暂无诊断数据。")

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

        st.info("💡 请在下方核对识图抓取结果：")
        edited_df = st.data_editor(df_extracted, num_rows="dynamic")
        edited_df["参培数"] = (
            edited_df["参培数(内单全职)"]
            + edited_df["参培数(内单兼职)"]
            + edited_df["参培数(外单全职)"]
            + edited_df["参培数(外单兼职)"]
        )

        if st.button(f"💾 确认提交{img_type_label}数据入库"):
            for idx, row in edited_df.iterrows():
                emp = row["员工姓名"]
                if "日度" in data_type:
                    payload = {
                        "date": date_str,
                        "employee_name": emp,
                        "invites": int(row["邀约数"]),
                        "interviews": int(row["到面数"]),
                        "inner_ft": int(row["参培数(内单全职)"]),
                        "inner_pt": int(row["参培数(内单兼职)"]),
                        "outer_ft": int(row["参培数(外单全职)"]),
                        "outer_pt": int(row["参培数(外单兼职)"]),
                        "trainees": int(row["参培数"]),
                    }
                else:
                    payload = {
                        "date": date_str,
                        "employee_name": emp,
                        "month_invites": int(row["邀约数"]),
                        "month_interviews": int(row["到面数"]),
                        "month_inner_ft": int(row["参培数(内单全职)"]),
                        "month_inner_pt": int(row["参培数(内单兼职)"]),
                        "month_outer_ft": int(row["参培数(外单全职)"]),
                        "month_outer_pt": int(row["参培数(外单兼职)"]),
                        "month_trainees": int(row["参培数"]),
                    }
                supabase.table("performance_data").upsert(payload).execute()

            st.balloons()
            st.success(
                f"🎉 成功同步更新 {date_str} 的{img_type_label}业绩数据至 Supabase！"
            )
            st.rerun()

    st.write("---")
    st.subheader("🔍 历史业绩数据查询与单条删除维护")
    res_perf_all = (
        supabase.table("performance_data")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    if res_perf_all.data:
        perf_records_df = pd.DataFrame(res_perf_all.data)
        perf_records_df = perf_records_df.rename(
            columns={
                "id": "记录编号",
                "date": "数据日期",
                "employee_name": "员工姓名",
                "invites": "日邀约",
                "interviews": "日到面",
                "trainees": "日参培",
                "month_invites": "月邀约",
                "month_interviews": "月到面",
                "month_trainees": "月参培",
            }
        )
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
                supabase.table("performance_data").delete().eq(
                    "id", perf_id_to_del
                ).execute()
                st.success(f"✅ 业绩记录 #{perf_id_to_del} 已从云端清除！")
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

    tab1, tab2, tab3 = st.tabs(
        ["👤 员工与账号管理", "🗑️ 数据记录删除与维护", "📥 历史数据导入(平台+业绩日报表)"]
    )

    with tab1:
        st.subheader("➕ 新增员工账号")
        col_u1, col_u2, col_u3, col_u4 = st.columns([1.5, 1.5, 1.5, 1])
        new_username = col_u1.text_input("登录账号 (如: zhangsan)")
        new_realname = col_u2.text_input("员工真实姓名 (如: 张三)")
        new_password = col_u3.text_input("初始密码", value="123456")

        if col_u4.button("➕ 创建账号"):
            if new_username and new_realname and new_password:
                try:
                    supabase.table("users").insert({
                        "username": new_username,
                        "password": new_password,
                        "real_name": new_realname,
                        "role": "employee",
                    }).execute()
                    st.success(
                        f"✅ 成功创建员工账号：{new_realname} ({new_username})"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 创建失败：账号名可能重复 ({e})")
            else:
                st.warning("⚠️ 请填满所有账号信息！")

        st.write("---")
        st.subheader("📋 现有人员与账号列表")
        res_users = supabase.table("users").select("*").execute()
        df_users = (
            pd.DataFrame(res_users.data) if res_users.data else pd.DataFrame()
        )

        if not df_users.empty:
            df_users = df_users.rename(
                columns={
                    "id": "用户编号",
                    "username": "账号",
                    "real_name": "姓名",
                    "role": "角色",
                    "password": "密码",
                }
            )
            df_users.index = range(1, len(df_users) + 1)
            st.dataframe(df_users, use_container_width=True)

            st.write("---")
            st.subheader("✏️ 修改账号信息 / 重置密码")
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
                supabase.table("users").update({
                    "username": edit_username,
                    "real_name": edit_realname,
                    "password": edit_password,
                }).eq("id", edit_user_id).execute()
                st.success("✅ 账号信息更新成功！")
                st.rerun()

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
                    supabase.table("users").delete().eq(
                        "id", del_user_id
                    ).execute()
                    st.success("✅ 账号删除成功！")
                    st.rerun()

    with tab2:
        st.subheader("📋 所有平台上传记录维护")
        res_all_platform = (
            supabase.table("platform_data")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        if res_all_platform.data:
            df_records = pd.DataFrame(res_all_platform.data)
            df_records = df_records.rename(
                columns={
                    "id": "记录编号",
                    "date": "归属日期",
                    "employee_name": "员工姓名",
                    "platform_version": "平台账号",
                    "i_looked": "我看过",
                    "seen_me": "看过我",
                    "i_greeted": "我打招呼",
                    "candidate_greeted": "牛人新招呼",
                    "i_communicated": "我沟通",
                    "received_resumes": "收到简历",
                    "exchanged_contact": "交换电话微信",
                    "accepted_interview": "接受面试",
                    "created_at": "更新时间",
                }
            )

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
                    supabase.table("platform_data").delete().eq(
                        "id", selected_id
                    ).execute()
                    st.success(f"✅ 云端记录 #{selected_id} 已彻底删除！")
                    st.rerun()
        else:
            st.info("ℹ️ 暂无平台提交记录。")

    with tab3:
        st.subheader("📥 批量导入平台历史日报表 (包含全链路所有类目)")
        st.warning("⚠️ 注意：本次导入为**单次全量覆盖**模式！")

        col_import_date, col_import_file = st.columns([1, 2])
        import_date = col_import_date.date_input(
            "选择历史日报表归属日期",
            YESTERDAY,
            key="history_import_date",
        )
        import_date_str = import_date.strftime("%Y-%m-%d")

        uploaded_history_file = col_import_file.file_uploader(
            "上传全链路历史日报表 (.xlsx / .csv)",
            type=["xlsx", "xls", "csv"],
            key="history_daily_uploader",
        )

        if uploaded_history_file is not None:
            try:
                if uploaded_history_file.name.endswith(".csv"):
                    df_history = pd.read_csv(uploaded_history_file)
                else:
                    df_history = pd.read_excel(uploaded_history_file)

                df_history.columns = [
                    str(c).strip() for c in df_history.columns
                ]
                for col in df_history.select_dtypes(
                    include=["object"]
                ).columns:
                    df_history[col] = df_history[col].astype(str).str.strip()

                st.markdown("##### 🔍 导入前数据预览：")
                st.dataframe(df_history, use_container_width=True)

                if st.button("🚀 确认同步导入平台及业绩数据", type="primary"):
                    field_mapping = {
                        "员工姓名": [
                            "员工姓名",
                            "员工",
                            "姓名",
                            "招聘专员",
                        ],
                        "平台账号": [
                            "平台账号",
                            "平台",
                            "账号",
                            "平台版本",
                        ],
                        "我看过": ["我看过"],
                        "看过我": ["看过我"],
                        "我打招呼": ["我打招呼"],
                        "牛人新招呼": ["牛人新招呼"],
                        "我沟通": ["我沟通"],
                        "收获简历": ["收获简历", "收到简历"],
                        "交换电话微信": [
                            "交换电话微信",
                            "交换微信/电话",
                            "交换电话/微信",
                            "留存微信",
                        ],
                        "接受面试": ["接受面试"],
                        "邀约数": ["邀约数", "邀约人数"],
                        "到面数": ["到面数", "到面人数"],
                        "参培数(内单全职)": [
                            "参培数(内单全职)",
                            "内单全职参培",
                            "内单全职",
                        ],
                        "参培数(内单兼职)": [
                            "参培数(内单兼职)",
                            "内单兼职参培",
                            "内单兼职",
                        ],
                        "参培数(外单全职)": [
                            "参培数(外单全职)",
                            "外单全职参培",
                            "外单全职",
                        ],
                        "参培数(外单兼职)": [
                            "参培数(外单兼职)",
                            "外单兼职参培",
                            "外单兼职",
                        ],
                        "参培数": ["参培数", "总参培数", "参培人数"],
                    }

                    matched_cols = {}
                    for target, candidates in field_mapping.items():
                        found = None
                        for cand in candidates:
                            if cand in df_history.columns:
                                found = cand
                                break
                        matched_cols[target] = found

                    if not matched_cols["员工姓名"]:
                        st.error("❌ 表格中缺失【员工姓名】列！")
                    else:
                        platform_rows = []
                        performance_rows = []

                        for _, row in df_history.iterrows():
                            emp_name = str(row[matched_cols["员工姓名"]]).strip()
                            if not emp_name or emp_name in ["合计", "nan"]:
                                continue

                            platform_val = (
                                str(row[matched_cols["平台账号"]]).strip()
                                if matched_cols["平台账号"]
                                else "易德Boss1号"
                            )

                            def get_num(key):
                                col = matched_cols[key]
                                if col and col in row:
                                    val = str(row[col])
                                    m = re.search(r"\d+", val)
                                    return int(m.group()) if m else 0
                                return 0

                            platform_rows.append({
                                "date": import_date_str,
                                "employee_name": emp_name,
                                "platform_version": platform_val,
                                "i_looked": get_num("我看过"),
                                "seen_me": get_num("看过我"),
                                "i_greeted": get_num("我打招呼"),
                                "candidate_greeted": get_num("牛人新招呼"),
                                "i_communicated": get_num("我沟通"),
                                "received_resumes": get_num("收获简历"),
                                "exchanged_contact": get_num("交换电话微信"),
                                "accepted_interview": get_num("接受面试"),
                            })

                            invites = get_num("邀约数")
                            interviews = get_num("到面数")
                            inner_ft = get_num("参培数(内单全职)")
                            inner_pt = get_num("参培数(内单兼职)")
                            outer_ft = get_num("参培数(外单全职)")
                            outer_pt = get_num("参培数(外单兼职)")
                            trainees = get_num("参培数")
                            if trainees == 0:
                                trainees = (
                                    inner_ft + inner_pt + outer_ft + outer_pt
                                )

                            performance_rows.append({
                                "date": import_date_str,
                                "employee_name": emp_name,
                                "invites": invites,
                                "interviews": interviews,
                                "inner_ft": inner_ft,
                                "inner_pt": inner_pt,
                                "outer_ft": outer_ft,
                                "outer_pt": outer_pt,
                                "trainees": trainees,
                            })

                        if platform_rows:
                            # 清理旧数据并批量写入 Supabase
                            supabase.table("platform_data").delete().eq(
                                "date", import_date_str
                            ).execute()
                            supabase.table("performance_data").delete().eq(
                                "date", import_date_str
                            ).execute()

                            supabase.table("platform_data").insert(
                                platform_rows
                            ).execute()
                            supabase.table("performance_data").insert(
                                performance_rows
                            ).execute()

                            st.balloons()
                            st.success(
                                f"🎉 成功导入 {import_date_str} 的历史数据至云端！"
                            )
                            st.rerun()

            except Exception as e:
                st.error(f"❌ 读取或写入数据失败: {e}")