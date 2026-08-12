import datetime
import os
import sqlite3
import pandas as pd
import streamlit as st

# 页面基本配置
st.set_page_config(page_title="招聘监控系统", page_icon="📌", layout="wide")

# 数据库初始化
DB_NAME = "recruitment_monitor.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 1. 员工填报及历史导入表（增加版本/平台兼容及唯一性控制，支持INSERT OR REPLACE覆盖）
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT,
            employee_name TEXT,
            platform_version TEXT,
            views_mine INTEGER DEFAULT 0,
            views_other INTEGER DEFAULT 0,
            greetings INTEGER DEFAULT 0,
            new_greetings INTEGER DEFAULT 0,
            chats INTEGER DEFAULT 0,
            resumes INTEGER DEFAULT 0,
            phones INTEGER DEFAULT 0,
            interviews_accepted INTEGER DEFAULT 0,
            invites INTEGER DEFAULT 0,
            interview_count INTEGER DEFAULT 0,
            train_in_full INTEGER DEFAULT 0,
            train_in_part INTEGER DEFAULT 0,
            train_out_full INTEGER DEFAULT 0,
            train_out_part INTEGER DEFAULT 0,
            train_total INTEGER DEFAULT 0,
            conversion_rate TEXT,
            UNIQUE(report_date, employee_name, platform_version)
        )
    """)

  # 2. 系统用户表
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            role TEXT
        )
    """)

  # 初始化默认管理员及员工
  cursor.execute(
      "INSERT OR IGNORE INTO users (username, role) VALUES ('系统管理员', '管理员')"
  )
  default_employees = ["储郑燃", "刘春雨", "唐凯", "孙衍", "王俊丽"]
  for emp in default_employees:
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, role) VALUES (?, '员工')", (emp,)
    )

  conn.commit()
  conn.close()


init_db()

# 侧边栏导航
st.sidebar.markdown("📌 **招聘监控系统**")
st.sidebar.markdown("---")
current_user = st.sidebar.selectbox("当前登录:", ["系统管理员", "储郑燃", "刘春雨"])

st.sidebar.markdown("选择模块:")
module = st.sidebar.radio(
    "选择模块",
    [
        "📱 员工端: 手机填报与截图上传",
        "📊 业务预警与数据看板",
        "🤖 数据端: 智能识图/录入业绩",
        "📦 历史数据导入与恢复",
        "⚙️ 管理端: 账号管理与记录维护",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 退出登录"):
  st.toast("已退出登录", icon="ℹ️")

# ==========================================
# 模块一：员工端填报
# ==========================================
if "📱 员工端" in module:
  st.subheader("📱 员工每日平台数据快捷填报")
  st.markdown("---")

  st.markdown("### 1 基本信息确认")
  emp_name = st.selectbox(
      "选择填报员工 (管理员代传模式)", ["储郑燃", "刘春雨", "唐凯", "孙衍", "王俊丽"]
  )
  report_date = st.date_input(
      "数据日期 (默认昨天)", datetime.date.today() - datetime.timedelta(days=1)
  )
  platform_version = st.selectbox("选择账号版本/平台", ["易德Boss1号", "易德Boss2号"])

  st.markdown("### 2 业绩数据填报")
  col1, col2, col3 = st.columns(3)
  with col1:
    views_mine = st.number_input("我看过", min_value=0, value=0)
    greetings = st.number_input("我打招呼", min_value=0, value=0)
    chats = st.number_input("我沟通", min_value=0, value=0)
    phones = st.number_input("交换电话微信", min_value=0, value=0)
    invites = st.number_input("邀约数", min_value=0, value=0)
  with col2:
    views_other = st.number_input("看过我", min_value=0, value=0)
    new_greetings = st.number_input("牛人新招呼", min_value=0, value=0)
    resumes = st.number_input("收获简历", min_value=0, value=0)
    interviews_accepted = st.number_input("接受面试", min_value=0, value=0)
    interview_count = st.number_input("到面数", min_value=0, value=0)
  with col3:
    train_in_full = st.number_input("参培数(内单全职)", min_value=0, value=0)
    train_in_part = st.number_input("参培数(内单兼职)", min_value=0, value=0)
    train_out_full = st.number_input("参培数(外单全职)", min_value=0, value=0)
    train_out_part = st.number_input("参培数(外单兼职)", min_value=0, value=0)

  train_total = (
      train_in_full + train_in_part + train_out_full + train_out_part
  )
  conversion_rate = (
      f"{(interview_count / invites * 100):.1f}%" if invites > 0 else "0.0%"
  )

  st.info(f"📊 自动计算：总参培数 = {train_total} | 到面转化率 = {conversion_rate}")

  if st.button("💾 确认提交并保存", type="primary"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
      cursor.execute(
          """
                INSERT OR REPLACE INTO daily_reports (
                    report_date, employee_name, platform_version,
                    views_mine, views_other, greetings, new_greetings, chats,
                    resumes, phones, interviews_accepted, invites, interview_count,
                    train_in_full, train_in_part, train_out_full, train_out_part,
                    train_total, conversion_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              str(report_date),
              emp_name,
              platform_version,
              views_mine,
              views_other,
              greetings,
              new_greetings,
              chats,
              resumes,
              phones,
              interviews_accepted,
              invites,
              interview_count,
              train_in_full,
              train_in_part,
              train_out_full,
              train_out_part,
              train_total,
              conversion_rate,
          ),
      )
      conn.commit()
      st.success(
          f"✅ 成功提交并更新 【{report_date}】 {emp_name} ({platform_version})"
          " 的数据！"
      )
    except Exception as e:
      st.error(f"保存失败: {e}")
    finally:
      conn.close()

# ==========================================
# 模块二：业务预警与数据看板
# ==========================================
elif "📊 业务预警" in module:
  st.subheader("📊 业务预警与数据看板")
  st.markdown("---")

  conn = sqlite3.connect(DB_NAME)
  df_all = pd.read_sql_query("SELECT * FROM daily_reports", conn)
  conn.close()

  if df_all.empty:
    st.warning(
        "⚠️ 当前数据库暂无任何业绩数据。请前往【📦 历史数据导入与恢复】板块上传您下载的日报表进行数据恢复！"
    )
  else:
    st.dataframe(df_all, use_container_width=True)

# ==========================================
# 模块三：数据端智能识图
# ==========================================
elif "🤖 数据端" in module:
  st.subheader("🤖 数据端：智能识图/录入业绩")
  st.markdown("---")
  st.info(
      "在此处可上传手机截图进行大模型OCR智能识别并自动录入，如需补录旧数据请直接使用左侧的【📦"
      " 历史数据导入与恢复】板块。"
  )

# ==========================================
# 模块四：📦 历史数据导入与恢复（独立新增板块）
# ==========================================
elif "📦 历史数据" in module:
  st.subheader("📦 历史数据导入与恢复（日报表批量上传）")
  st.markdown("---")
  st.markdown(
      ">"
      " **功能说明**：专门用于恢复因系统异常或重置而丢失的历史数据。直接上传您之前导出的标准系统日报表（如"
      " `招聘日报表_系统管理员_YYYY-MM-DD.xlsx`），系统将自动校验并整批恢复至数据库中。"
  )

  uploaded_file = st.file_uploader(
      "选择系统导出的日报表文件 (Excel 格式)", type=["xlsx", "xls"]
  )

  if uploaded_file is not None:
    try:
      df_import = pd.read_excel(uploaded_file)
      st.success(
          f"✅ 文件成功解析！共读取到 {len(df_import)} 条历史记录数据。"
      )

      st.markdown("#### 📋 导入数据预览（前5行）：")
      st.dataframe(df_import.head(), use_container_width=True)

      import_mode = st.radio(
          "请选择数据写入冲突策略：",
          [
              (
                  "覆盖更新（若同一天、同一员工已有数据，则自动用上传文件中的最新数据替换）"
              ),
              ("追加合并（直接写入数据库，保留所有历史提交）"),
          ],
      )

      if st.button("🚀 开始批量导入并恢复数据", type="primary"):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        success_count = 0
        for _, row in df_import.iterrows():
          # 兼容处理字段映射
          r_date = str(row.get("具体日期", datetime.date.today()))[:10]
          e_name = str(row.get("员工姓名", "未知员工"))
          p_version = str(
              row.get("平台版本", "易德Boss1号")
          )  # 如果没有此列则默认

          if import_mode.startswith("覆盖更新"):
            cursor.execute(
                """
                            INSERT OR REPLACE INTO daily_reports (
                                report_date, employee_name, platform_version,
                                views_mine, views_other, greetings, new_greetings, chats,
                                resumes, phones, interviews_accepted, invites, interview_count,
                                train_in_full, train_in_part, train_out_full, train_out_part,
                                train_total, conversion_rate
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    r_date,
                    e_name,
                    p_version,
                    int(row.get("我看过", 0)),
                    int(row.get("看过我", 0)),
                    int(row.get("我打招呼", 0)),
                    int(row.get("牛人新招呼", 0)),
                    int(row.get("我沟通", 0)),
                    int(row.get("收获简历", 0)),
                    int(row.get("交换电话微信", 0)),
                    int(row.get("接受面试", 0)),
                    int(row.get("邀约数", 0)),
                    int(row.get("到面数", 0)),
                    int(row.get("参培数(内单全职)", 0)),
                    int(row.get("参培数(内单兼职)", 0)),
                    int(row.get("参培数(外单全职)", 0)),
                    int(row.get("参培数(外单兼职)", 0)),
                    int(row.get("参培数", 0)),
                    str(row.get("到面转化率", "0.0%")),
                ),
            )
          else:
            cursor.execute(
                """
                            INSERT INTO daily_reports (
                                report_date, employee_name, platform_version,
                                views_mine, views_other, greetings, new_greetings, chats,
                                resumes, phones, interviews_accepted, invites, interview_count,
                                train_in_full, train_in_part, train_out_full, train_out_part,
                                train_total, conversion_rate
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                (
                    r_date,
                    e_name,
                    p_version,
                    int(row.get("我看过", 0)),
                    int(row.get("看过我", 0)),
                    int(row.get("我打招呼", 0)),
                    int(row.get("牛人新招呼", 0)),
                    int(row.get("我沟通", 0)),
                    int(row.get("收获简历", 0)),
                    int(row.get("交换电话微信", 0)),
                    int(row.get("接受面试", 0)),
                    int(row.get("邀约数", 0)),
                    int(row.get("到面数", 0)),
                    int(row.get("参培数(内单全职)", 0)),
                    int(row.get("参培数(内单兼职)", 0)),
                    int(row.get("参培数(外单全职)", 0)),
                    int(row.get("参培数(外单兼职)", 0)),
                    int(row.get("参培数", 0)),
                    str(row.get("到面转化率", "0.0%")),
                ),
            )
          success_count += 1

        conn.commit()
        conn.close()
        st.success(
            f"🎉 成功导入并恢复了 {success_count} 条历史记录！您现在可以前往【📊"
            " 业务预警与数据看板】查看恢复后的数据。"
        )

    except Exception as e:
      st.error(f"❌ 文件解析或导入出错，请确认上传的是正确的系统日报表。错误信息: {e}")

# ==========================================
# 模块五：管理端维护
# ==========================================
elif "⚙️ 管理端" in module:
  st.subheader("⚙️ 管理端：账号管理与记录维护")
  st.markdown("---")
  st.info("系统管理员专用维护面板。")