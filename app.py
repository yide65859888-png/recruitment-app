import io
from datetime import datetime
import pandas as pd
import streamlit as st

# ==========================================
# 1. 页面基本配置
# ==========================================
st.set_page_config(
    page_title="招聘数据管理与报表系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# 2. 初始化 Session State
# ==========================================
if "real_name" not in st.session_state:
    st.session_state["real_name"] = "张三"  # 默认招聘专员姓名

# ==========================================
# 3. 侧边栏：筛选与设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 报表导出设置")

    # 用户姓名设置
    user_name_input = st.text_input(
        "招聘专员姓名", value=st.session_state["real_name"]
    )
    st.session_state["real_name"] = user_name_input

    st.divider()

    # 报表类型选择
    report_type = st.radio(
        "报表类型", ["单月数据", "累计数据"], index=0, help="选择导出的数据范围类型"
    )

    # 月份选择
    selected_date = st.date_input("选择月份", datetime.now())
    month_str = selected_date.strftime("%Y年%m月")

# ==========================================
# 4. 主页面：看板展示与数据表格
# ==========================================
st.title("📈 招聘数据管理系统")
st.caption(f"当前操作人：{st.session_state['real_name']} | 当前选定周期：{month_str}")

# 模拟数据源 (实际业务中可替换为数据库查询或读取本地 Excel/CSV)
@st.cache_data
def load_data():
    return pd.DataFrame(
        {
            "招聘专员": [
                st.session_state["real_name"],
                st.session_state["real_name"],
                st.session_state["real_name"],
                "李四",
            ],
            "项目名称": ["电信项目", "苏州落地项目", "常规招聘", "技术岗位招聘"],
            "简历推荐数": [45, 30, 25, 12],
            "面试人数": [20, 15, 10, 5],
            "拟录用人数": [8, 5, 4, 2],
            "实际入职人数": [5, 3, 3, 1],
            "月份": [month_str, month_str, "2026年06月", month_str],
        }
    )

df_all = load_data()

# 根据侧边栏筛选数据
if "单月" in report_type:
    df_filtered = df_all[
        (df_all["招聘专员"] == st.session_state["real_name"])
        & (df_all["月份"] == month_str)
    ]
else:
    df_filtered = df_all[df_all["招聘专员"] == st.session_state["real_name"]]

# 核心数据指标展示 (Metrics Cards)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("简历推荐总数", df_filtered["简历推荐数"].sum())
with col2:
    st.metric("面试总人数", df_filtered["面试人数"].sum())
with col3:
    st.metric("拟录用人数", df_filtered["拟录用人数"].sum())
with col4:
    st.metric("实际入职人数", df_filtered["实际入职人数"].sum())

st.divider()

# 数据明细表格展示
st.subheader("📋 招聘明细数据")
st.dataframe(df_filtered, use_container_width=True)

# ==========================================
# 5. 导出与下载逻辑 (含 Line 668 修复项)
# ==========================================
st.subheader("📥 导出报表")

# 修复后的动态文件名生成逻辑（补全了 if-else 与 } 闭合符）
file_name = f"招聘数据_{st.session_state.real_name}_{month_str if '单月' in report_type else '全量'}.xlsx"

# 将 DataFrame 转换为 Excel 字节流
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_filtered.to_excel(writer, index=False, sheet_name="招聘明细数据")
excel_bytes = buffer.getvalue()

# Streamlit 下载按钮
st.download_button(
    label=f"📄 点击下载 Excel 报表 ({file_name})",
    data=excel_bytes,
    file_name=file_name,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)