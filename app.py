# 替换管理端 Tab3: 历史数据导入(平台+业绩全量导入)
    with tab3:
        st.subheader("📥 批量导入平台历史日报表 (包含全链路所有类目)")
        st.warning(
            "⚠️ 注意：本次导入为**单次全量覆盖**模式！导入所选具体日期的数据时，系统将自动清空该日期已存在的平台数据与业绩数据，并全量写入最新表格数据。"
        )

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

                # 清理表头与文本空格
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
                    # 字段映射字典（兼容各类表头名称）
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

                    # 匹配实际表头
                    matched_cols = {}
                    for target, candidates in field_mapping.items():
                        found = None
                        for cand in candidates:
                            if cand in df_history.columns:
                                found = cand
                                break
                        matched_cols[target] = found

                    if not matched_cols["员工姓名"]:
                        st.error(
                            "❌ 表格中缺失【员工姓名】列，请检查表格文件！"
                        )
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

                            # 1. 解析平台过程数据
                            i_looked = get_num("我看过")
                            seen_me = get_num("看过我")
                            i_greeted = get_num("我打招呼")
                            candidate_greeted = get_num("牛人新招呼")
                            i_communicated = get_num("我沟通")
                            received_resumes = get_num("收获简历")
                            exchanged_contact = get_num("交换电话微信")
                            accepted_interview = get_num("接受面试")

                            platform_rows.append((
                                import_date_str,
                                emp_name,
                                platform_val,
                                i_looked,
                                seen_me,
                                i_greeted,
                                candidate_greeted,
                                i_communicated,
                                received_resumes,
                                exchanged_contact,
                                accepted_interview,
                            ))

                            # 2. 解析业绩结果数据
                            invites = get_num("邀约数")
                            interviews = get_num("到面数")
                            inner_ft = get_num("参培数(内单全职)")
                            inner_pt = get_num("参培数(内单兼职)")
                            outer_ft = get_num("参培数(外单全职)")
                            outer_pt = get_num("参培数(外单兼职)")
                            trainees = get_num("参培数")

                            # 若未单独提供总参培数，自动计算相加
                            if trainees == 0:
                                trainees = (
                                    inner_ft + inner_pt + outer_ft + outer_pt
                                )

                            performance_rows.append((
                                import_date_str,
                                emp_name,
                                invites,
                                interviews,
                                inner_ft,
                                inner_pt,
                                outer_ft,
                                outer_pt,
                                trainees,
                            ))

                        if platform_rows:
                            with sqlite3.connect(DB_PATH) as conn:
                                c = conn.cursor()

                                # A. 清理该日期的旧数据
                                c.execute(
                                    "DELETE FROM platform_data WHERE date = ?",
                                    (import_date_str,),
                                )
                                c.execute(
                                    "DELETE FROM performance_data WHERE date = ?",
                                    (import_date_str,),
                                )

                                # B. 批量写入平台过程表
                                c.executemany(
                                    """INSERT INTO platform_data 
                                       (date, employee_name, platform_version, i_looked, seen_me, i_greeted, candidate_greeted, i_communicated, received_resumes, exchanged_contact, accepted_interview, created_at)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                                    platform_rows,
                                )

                                # C. 批量写入业绩结果表
                                c.executemany(
                                    """INSERT INTO performance_data 
                                       (date, employee_name, invites, interviews, inner_ft, inner_pt, outer_ft, outer_pt, trainees)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                    performance_rows,
                                )

                                conn.commit()

                            st.balloons()
                            st.success(
                                f"🎉 成功同步覆盖导入 {import_date_str} 的全链路数据（平台过程数据 {len(platform_rows)} 条 + 业绩结果数据 {len(performance_rows)} 条）！"
                            )
                            st.rerun()
                        else:
                            st.warning("⚠️ 未提取到有效的员工数据。")

            except Exception as e:
                st.error(f"❌ 读取或写入数据失败: {e}")