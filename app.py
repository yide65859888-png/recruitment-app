import io
import sqlite3
import pandas as pd
import streamlit as st

# ==================== 1. 页面基本配置 ====================
st.set_page_config(
    page_title="招聘数据管理与预警系统", page_icon="📊", layout="wide"
)

st.title("📊 招聘数据汇总与预警系统")
st.markdown("---")


# ==================== 2. 数据库初始化 ====================
def init_db():
    conn = sqlite3.connect("recruitment_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recruitment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT,
            project_name TEXT,
            recruiter TEXT,
            channel TEXT,
            resume_count INTEGER,
            interview_count INTEGER,
            pass_count INTEGER,
            offer_count INTEGER,
            entry_count INTEGER,
            remark TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# 数据库读取函数
def load_data():
    conn = sqlite3.connect("recruitment_data.db")
    df = pd.read_sql_query(
        "SELECT * FROM recruitment_logs ORDER BY id DESC", conn
    )
    conn.close()
    return df


# 数据库插入函数
def insert_data(
    record_date,
    project_name,
    recruiter,
    channel,
    resume_count,
    interview_count,
    pass_count,
    offer_count,
    entry_count,
    remark,
):
    conn = sqlite3.connect("recruitment_data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO recruitment_logs (
            record_date, project_name, recruiter, channel, 
            resume_count, interview_count, pass_count, offer_count, entry_count, remark
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            str(record_date),
            project_name,
            recruiter,
            channel,
            resume_count,
            interview_count,
            pass_count,
            offer_count,
            entry_count,
            remark,
        ),
    )
    conn.commit()
    conn.close()


# ==================== 3. 侧边栏与页面导航 ====================
st.sidebar.header("📌 功能导航")
menu = st.sidebar.radio(
    "请选择功能模块：",
    ["📝 数据日常填报", "📈 全链路数据总表与导出", "⚙️ 系统说明"],
)

# ==================== 模块一：数据日常填报 ====================
if menu == "📝 数据日常填报":
    st.subheader("📝 招聘日常数据录入")

    with st.form(key="recruitment_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            record_date = st.date_input("填报日期")
            project_name = st.text_input(
                "项目名称/岗位名称", placeholder="例如：宿州电信项目"
            )
            recruiter = st.text_input(
                "招聘负责人/顾问", placeholder="例如：张三"
            )

        with col2:
            channel = st.selectbox(
                "招聘渠道",
                ["线上网招", "线下代理商", "校园招聘", "内部推荐", "其他"],
            )
            resume_count = st.number_input(
                "获取简历数", min_value=0, value=0, step=1
            )
            interview_count = st.number_input(
                "约面/面试人数", min_value=0, value=0, step=1
            )

        with col3:
            pass_count = st.number_input(
                "面试通过人数", min_value=0, value=0, step=1
            )
            offer_count = st.number_input(
                "发 Offer 人数", min_value=0, value=0, step=1
            )
            entry_count = st.number_input(
                "实际入职人数", min_value=0, value=0, step=1
            )

        remark = st.text_area(
            "备注说明/异常反馈", placeholder="例如：某渠道流量偏低..."
        )

        submit_button = st.form_submit_button(
            label="🚀 提交数据", use_container_width=True
        )

        if submit_button:
            if not project_name or not recruiter:
                st.error("⚠️ 请填写“项目名称”和“招聘负责人”！")
            else:
                insert_data(
                    record_date,
                    project_name,
                    recruiter,
                    channel,
                    resume_count,
                    interview_count,
                    pass_count,
                    offer_count,
                    entry_count,
                    remark,
                )
                st.success("✅ 数据提交成功！可在“全链路数据总表”中查看与导出。")

# ==================== 模块二：全链路数据总表与一键导出 ====================
elif menu == "📈 全链路数据总表与导出":
    st.subheader("📈 招聘数据汇总总表")

    df = load_data()

    if df.empty:
        st.info("💡 暂无提交的数据，请先在“数据日常填报”页面录入数据。")
    else:
        # 重命名表头方便查看
        rename_dict = {
            "id": "记录ID",
            "record_date": "日期",
            "project_name": "项目/岗位",
            "recruiter": "负责人",
            "channel": "渠道",
            "resume_count": "简历数",
            "interview_count": "面试数",
            "pass_count": "通过数",
            "offer_count": "Offer数",
            "entry_count": "入职数",
            "remark": "备注",
        }
        df_display = df.rename(columns=rename_dict)

        # 核心指标统计卡片
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("总简历量", f"{df['resume_count'].sum()} 份")
        col_m2.metric("总面试量", f"{df['interview_count'].sum()} 人")
        col_m3.metric("总通过量", f"{df['pass_count'].sum()} 人")
        col_m4.metric("总入职量", f"{df['entry_count'].sum()} 人")

        st.markdown("---")

        # 数据表格展示
        st.dataframe(df_display, use_container_width=True)

        st.markdown("### 📥 一键导出数据")
        col_exp1, col_exp2 = st.columns(2)

        # 1. 导出 Excel 格式
        with col_exp1:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_display.to_excel(
                    writer, index=False, sheet_name="招聘数据汇总"
                )

            st.download_button(
                label="📊 导出为 Excel 表格 (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name="招聘数据汇总表.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # 2. 导出 CSV 格式
        with col_exp2:
            csv_bytes = df_display.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📄 导出为 CSV 文件 (.csv)",
                data=csv_bytes,
                file_name="招聘数据汇总表.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ==================== 模块三：系统说明 ====================
elif menu == "⚙️ 系统说明":
    st.subheader("⚙️ 关于本系统")
    st.markdown("""
    * **数据采集**：支持按项目、负责人、渠道录入 recruiter 的全流程招聘数据。
    * **数据导出**：支持一键导出包含 `utf-8-sig` 编码的 Excel / CSV 表格，确保用 Excel 打开中文不乱码。
    * **数据安全**：云端自动汇总，可随时在线导出备份。
    """)