import datetime
import io
import sqlite3
import pandas as pd
from PIL import Image
import streamlit as st

# 1. 页面基本配置
st.set_page_config(
    page_title="招聘全链路数据监控与智能预警系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 样式适配（支持手机端卡片与大按钮）
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
</style>
""",
    unsafe_allow_html=True,
)

TEAM_MEMBERS = [
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


# 2. 初始化数据库
def init_db():
    conn = sqlite3.connect("recruitment_data.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS platform_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, employee_name TEXT, platform_version TEXT,
                    seen_me INTEGER DEFAULT 0, i_communicated INTEGER DEFAULT 0,
                    received_resumes INTEGER DEFAULT 0, exchanged_contact INTEGER DEFAULT 0,
                    exchanged_phone INTEGER DEFAULT 0, proposed_interview INTEGER DEFAULT 0,
                    accepted_interview INTEGER DEFAULT 0
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS performance_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, employee_name TEXT,
                    invites INTEGER DEFAULT 0, interviews INTEGER DEFAULT 0, trainees INTEGER DEFAULT 0,
                    month_invites INTEGER DEFAULT 0, month_interviews INTEGER DEFAULT 0, month_trainees INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()


init_db()


# 识图模拟函数
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


def mock_supervisor_ocr_daily(image):
    return pd.DataFrame({
        "员工姓名": TEAM_MEMBERS,
        "当日邀约": [6, 17, 2, 3, 12, 3, 1, 4, 0, 9, 6],
        "当日到面": [11, 21, 9, 13, 30, 9, 18, 20, 0, 23, 20],
        "当日参培": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
    })


def mock_supervisor_ocr_monthly(image):
    return pd.DataFrame({
        "员工姓名": TEAM_MEMBERS,
        "单月累计邀约": [120, 210, 85, 90, 180, 75, 60, 110, 15, 140, 130],
        "单月累计到面": [80, 150, 50, 60, 130, 45, 35, 70, 5, 95, 85],
        "单月累计参培": [12, 22, 6, 8, 19, 5, 4, 11, 0, 15, 12],
    })


def run_alert_engine(df_summary, is_monthly=False):
    alerts = []
    for _, row in df_summary.iterrows():
        name = row["员工姓名"]
        comm = row.get("主动沟通", 0)
        resumes = row.get("收获简历", 0)
        wx = row.get("交换微信", 0)

        invites = (
            row.get("单月累计邀约", 0) if is_monthly else row.get("当日邀约", 0)
        )
        interviews = (
            row.get("单月累计到面", 0) if is_monthly else row.get("当日到面", 0)
        )
        trainees = (
            row.get("单月累计参培", 0) if is_monthly else row.get("当日参培", 0)
        )

        time_tag = "全月" if is_monthly else "当日"

        if is_monthly and invites < 30:
            alerts.append({
                "name": name,
                "level": "🚨 产能预警：月度招聘产能严重不足",
                "issue": f"{time_tag}累计邀约仅 {invites} 人，到面 {interviews} 人",
                "data": (
                    f"月邀约 {invites} 人 ➔ 到面 {interviews} 人 ➔ 参培"
                    f" {trainees} 人"
                ),
                "reason": (
                    "月度整体招聘动作极少，业务活动量严重不达标，未能建立起有效的招聘漏斗基数"
                ),
                "action": (
                    "建议拉通一对一辅导，明确每日打招呼、私域跟进与约面的最低过程"
                    " KPI"
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
                "issue": (
                    f"{time_tag}获取微信 {wx} 个，但实际邀约仅 {invites} 人"
                ),
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
                "issue": (
                    f"{time_tag}到面 {interviews} 人，但参培仅 {trainees} 人"
                    f" (转化率仅 {trainee_rate:.1f}%)"
                ),
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
                    "到面转化率异常达到"
                    f" {((interviews/invites)*100):.1f}%"
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
            f"🥇 第1名"
            if i == 0
            else (
                f"🥈 第2名"
                if i == 1
                else f"🥉 第3名" if i == 2 else f"&nbsp;&nbsp;&nbsp;第{i+1}名"
            )
        )
        val_str = f"{val:.1f}{unit}" if unit == "%" else f"{int(val)}{unit}"
        html += f'<div class="{rank_class}">{prefix}: <b>{name}</b> ({val_str})</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# 侧边栏导航
st.sidebar.title("📌 招聘系统")
page = st.sidebar.radio(
    "选择模块：",
    [
        "📱 员工端：手机填报与截图上传",
        "📊 业务预警与全链路数据总表",
        "📋 数据端：智能识图/录入业绩",
    ],
)

st.sidebar.write("---")
st.sidebar.info(
    "🌐 公网云端已上线\n手机输入网址或用微信直接打开即可填报！"
)

# 页面路由
if page == "📱 员工端：手机填报与截图上传":
    st.markdown(
        "<div class='main-header'>📱 员工每日平台数据快捷填报</div>",
        unsafe_allow_html=True,
    )
    st.info(
        "💡 在手机浏览器或微信中打开本链接，随时截图上传填报。"
    )

    with st.form("employee_upload_form", clear_on_submit=True):
        st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
        st.subheader("1️⃣ 基本信息")
        emp_name = st.selectbox("选择您的姓名", TEAM_MEMBERS)
        record_date = st.date_input(
            "数据日期", datetime.date(2026, 7, 21)
        )
        platform_ver = st.selectbox(
            "选择账号版本/平台",
            [
                "易德Boss",
                "呼叫中心Boss",
                "人保Boss",
                "智联招聘",
                "51job",
            ],
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='mobile-card'>", unsafe_allow_html=True)
        st.subheader("2️⃣ 上传平台截图")
        uploaded_file = st.file_uploader(
            "点击上传或手机拍照", type=["jpg", "png", "jpeg"]
        )
        st.markdown("</div>", unsafe_allow_html=True)

        submit_btn = st.form_submit_button("🚀 立即提交保存")

    if submit_btn:
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            ocr = mock_employee_ocr(image)
            conn = sqlite3.connect("recruitment_data.db")
            c = conn.cursor()
            c.execute(
                "INSERT INTO platform_data (date, employee_name, platform_version,"
                " seen_me, i_communicated, received_resumes, exchanged_contact,"
                " exchanged_phone, proposed_interview, accepted_interview)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_date.strftime("%Y-%m-%d"),
                    emp_name,
                    platform_ver,
                    ocr["seen_me"],
                    ocr["i_communicated"],
                    ocr["received_resumes"],
                    ocr["exchanged_contact"],
                    ocr["exchanged_phone"],
                    ocr["proposed_interview"],
                    ocr["accepted_interview"],
                ),
            )
            conn.commit()
            conn.close()
            st.balloons()
            st.success(
                f"🎉 提交成功！[{emp_name}] 的 [{platform_ver}]"
                " 数据已自动识图保存！"
            )
        else:
            st.error("⚠️ 请先上传一张平台截图！")

elif page == "📊 业务预警与全链路数据总表":
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
            "月份", [f"{m:02d}月" for m in range(1, 13)], index=6
        )
        month_str = f"{selected_year}-{selected_m_str.replace('月', '')}"
        date_filter_p = f"{month_str}%"
        date_filter_perf = f"{month_str}%"
    else:
        selected_date = col_date.date_input(
            "选择统计日期", datetime.date(2026, 7, 21)
        )
        date_str = selected_date.strftime("%Y-%m-%d")
        date_filter_p = date_str
        date_filter_perf = date_str

    selected_employees = col_filter.multiselect(
        "筛选员工姓名", TEAM_MEMBERS, default=TEAM_MEMBERS
    )

    conn = sqlite3.connect("recruitment_data.db")
    if "单月" in view_mode:
        df_p = pd.read_sql_query(
            "SELECT employee_name as 员工姓名, SUM(seen_me) as 看过我,"
            " SUM(i_communicated) as 主动沟通, SUM(received_resumes) as"
            " 收获简历, SUM(exchanged_contact) as 交换微信, SUM(exchanged_phone)"
            " as 交换电话, SUM(proposed_interview) as 拟约面,"
            " SUM(accepted_interview) as 接受面试 FROM platform_data WHERE date"
            " LIKE ? GROUP BY employee_name",
            conn,
            params=(date_filter_p,),
        )
        df_perf = pd.read_sql_query(
            "SELECT employee_name as 员工姓名, MAX(month_invites) as"
            " 单月累计邀约, MAX(month_interviews) as 单月累计到面,"
            " MAX(month_trainees) as 单月累计参培 FROM performance_data WHERE date"
            " LIKE ? GROUP BY employee_name",
            conn,
            params=(date_filter_perf,),
        )
    else:
        df_p = pd.read_sql_query(
            "SELECT employee_name as 员工姓名, SUM(seen_me) as 看过我,"
            " SUM(i_communicated) as 主动沟通, SUM(received_resumes) as"
            " 收获简历, SUM(exchanged_contact) as 交换微信, SUM(exchanged_phone)"
            " as 交换电话, SUM(proposed_interview) as 拟约面,"
            " SUM(accepted_interview) as 接受面试 FROM platform_data WHERE date"
            " = ? GROUP BY employee_name",
            conn,
            params=(date_filter_p,),
        )
        df_perf = pd.read_sql_query(
            "SELECT employee_name as 员工姓名, SUM(invites) as 当日邀约,"
            " SUM(interviews) as 当日到面, SUM(trainees) as 当日参培 FROM"
            " performance_data WHERE date = ? GROUP BY employee_name",
            conn,
            params=(date_filter_perf,),
        )
    conn.close()

    df_base = pd.DataFrame({"员工姓名": TEAM_MEMBERS})
    df_summary = pd.merge(df_base, df_p, on="员工姓名", how="left")
    df_summary = pd.merge(df_summary, df_perf, on="员工姓名", how="left").fillna(
        0
    )

    if selected_employees:
        df_summary = df_summary[df_summary["员工姓名"].isin(selected_employees)]

    df_summary["到面转化率数值"] = df_summary.apply(
        lambda r: (
            (r["单月累计到面"] / r["单月累计邀约"] * 100)
            if "单月" in view_mode and r["单月累计邀约"] > 0
            else (
                (r["当日到面"] / r["当日邀约"] * 100)
                if r.get("当日邀约", 0) > 0
                else 0.0
            )
        ),
        axis=1,
    )
    df_summary["到面转化率"] = df_summary["到面转化率数值"].apply(
        lambda x: f"{x:.1f}%"
    )

    if "单月" in view_mode:
        st.subheader(
            f"📆 招聘单月全链路累计汇总大表 ({month_str})"
        )
        final_cols = [
            "员工姓名",
            "看过我",
            "主动沟通",
            "收获简历",
            "交换微信",
            "交换电话",
            "拟约面",
            "接受面试",
            "单月累计邀约",
            "单月累计到面",
            "单月累计参培",
            "到面转化率",
        ]
    else:
        st.subheader(
            f"📋 招聘当日全链路整合数据一览表 ({date_str})"
        )
        final_cols = [
            "员工姓名",
            "看过我",
            "主动沟通",
            "收获简历",
            "交换微信",
            "交换电话",
            "拟约面",
            "接受面试",
            "当日邀约",
            "当日到面",
            "当日参培",
            "到面转化率",
        ]

    st.dataframe(df_summary[final_cols], height=350)

    # ==================== 🛠️ 新增：无缝嵌入数据导出功能 ====================
    st.markdown("##### 📥 导出当前数据表")
    col_exp1, col_exp2 = st.columns([1, 1])

    # 1. 导出 Excel
    with col_exp1:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_summary[final_cols].to_excel(
                writer, index=False, sheet_name="招聘全链路数据"
            )
        st.download_button(
            label="📊 导出 Excel 表格 (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=f"招聘数据_{month_str if '单月' in view_mode else date_str}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    # 2. 导出 CSV
    with col_exp2:
        csv_bytes = (
            df_summary[final_cols].to_csv(index=False).encode("utf-8-sig")
        )
        st.download_button(
            label="📄 导出 CSV 文件 (.csv)",
            data=csv_bytes,
            file_name=f"招聘数据_{month_str if '单月' in view_mode else date_str}.csv",
            mime="text/csv",
        )
    # =======================================================================

    st.write("---")

    st.subheader("📊 招聘关键过程指标 (KPI) 排名看板")
    p1_col1, p1_col2, p1_col3, p1_col4 = st.columns(4)
    with p1_col1:
        render_full_ranking(df_summary, "看过我", "看过我人数", "人")
    with p1_col2:
        render_full_ranking(df_summary, "主动沟通", "主动沟通人数", "人")
    with p1_col3:
        render_full_ranking(df_summary, "收获简历", "收获简历数量", "份")
    with p1_col4:
        render_full_ranking(df_summary, "交换微信", "交换微信数量", "人")

    inv_col = "单月累计邀约" if "单月" in view_mode else "当日邀约"
    int_col = "单月累计到面" if "单月" in view_mode else "当日到面"
    tra_col = "单月累计参培" if "单月" in view_mode else "当日参培"

    p2_col1, p2_col2, p2_col3, p2_col4 = st.columns(4)
    with p2_col1:
        render_full_ranking(df_summary, inv_col, f"{inv_col}人数", "人")
    with p2_col2:
        render_full_ranking(df_summary, int_col, f"{int_col}人数", "人")
    with p2_col3:
        render_full_ranking(df_summary, tra_col, f"{tra_col}人数", "人")
    with p2_col4:
        render_full_ranking(
            df_summary, "到面转化率数值", "到面转化率", "%"
        )

    st.write("---")
    st.subheader("🚨 智能全链路漏斗预警与过程卡点诊断")
    alerts = run_alert_engine(df_summary, is_monthly=("单月" in view_mode))
    if alerts:
        for a in alerts:
            card_class = (
                "alert-card-danger"
                if "🚨" in a["level"]
                else "alert-card-warning"
            )
            st.markdown(
                f"<div class='{card_class}'><b>【{a['level']}】{a['name']} -"
                f" {a['issue']}</b><br/>• <b>卡点数据：</b> {a['data']}<br/>•"
                f" <b>归因诊断：</b> {a['reason']}<br/>• <b>建议动作：</b>"
                f" {a['action']}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("🎉 当前全链路数据表现顺畅，暂无卡点预警！")

elif page == "📋 数据端：智能识图/录入业绩":
    st.markdown(
        "<div class='main-header'>📋 数据端：部门业绩汇总与智能识图录入</div>",
        unsafe_allow_html=True,
    )
    col_type, col_date = st.columns(2)
    data_type = col_type.radio(
        "📌 选择上传的数据表类型：",
        ["📅 日度新增业绩表", "📆 单月累计业绩表"],
        horizontal=True,
    )
    p_date_img = col_date.date_input(
        "选择业绩数据日期", datetime.date(2026, 7, 21)
    )

    st.write("---")
    if "日度" in data_type:
        daily_img = st.file_uploader(
            "上传【日度】表格截图", type=["jpg", "png", "jpeg"]
        )
        if daily_img is not None:
            image = Image.open(daily_img)
            st.image(image, caption="已上传截图", width=400)
            df_extracted = mock_supervisor_ocr_daily(image)
            edited_df = st.data_editor(df_extracted, num_rows="dynamic")
            if st.button("💾 确认提交【日度】数据入库"):
                conn = sqlite3.connect("recruitment_data.db")
                c = conn.cursor()
                date_str = p_date_img.strftime("%Y-%m-%d")
                for idx, row in edited_df.iterrows():
                    if row["员工姓名"] in TEAM_MEMBERS:
                        c.execute(
                            "INSERT INTO performance_data (date, employee_name,"
                            " invites, interviews, trainees) VALUES (?, ?,"
                            " ?, ?, ?)",
                            (
                                date_str,
                                row["员工姓名"],
                                int(row["当日邀约"]),
                                int(row["当日到面"]),
                                int(row["当日参培"]),
                            ),
                        )
                conn.commit()
                conn.close()
                st.balloons()
                st.success(f"🎉 成功保存 {date_str} 数据！")
    else:
        monthly_img = st.file_uploader(
            "上传【单月累计】表格截图", type=["jpg", "png", "jpeg"]
        )
        if monthly_img is not None:
            image = Image.open(monthly_img)
            st.image(image, caption="已上传截图", width=400)
            df_extracted = mock_supervisor_ocr_monthly(image)
            edited_df = st.data_editor(df_extracted, num_rows="dynamic")
            if st.button("💾 确认提交【单月累计】数据入库"):
                conn = sqlite3.connect("recruitment_data.db")
                c = conn.cursor()
                date_str = p_date_img.strftime("%Y-%m-%d")
                for idx, row in edited_df.iterrows():
                    if row["员工姓名"] in TEAM_MEMBERS:
                        c.execute(
                            "INSERT INTO performance_data (date, employee_name,"
                            " month_invites, month_interviews, month_trainees)"
                            " VALUES (?, ?, ?, ?, ?)",
                            (
                                date_str,
                                row["员工姓名"],
                                int(row["单月累计邀约"]),
                                int(row["单月累计到面"]),
                                int(row["单月累计参培"]),
                            ),
                        )
                conn.commit()
                conn.close()
                st.balloons()
                st.success(f"🎉 成功保存 {date_str} 数据！")