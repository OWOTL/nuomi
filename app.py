import streamlit as st
import pandas as pd
import io
from datetime import datetime

# --- 页面配置 ---
st.set_page_config(page_title="凭证大师 21.0 - GitHub 严谨版", layout="wide")

# --- 样式美化 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #0052cc; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; background-color: #36b37e; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 数据初始化逻辑 ---
# 线上版本数据存储在 Session 中，如需跨Session永久存储，建议连接数据库，此处为严谨模拟Web逻辑
if 'coa' not in st.session_state:
    st.session_state.coa = pd.DataFrame(columns=["科目编码", "科目名称"])
if 'cust' not in st.session_state:
    st.session_state.cust = pd.DataFrame(columns=["客户编码", "客户名称"])
if 'rules' not in st.session_state:
    st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

# --- 通用函数：CSV编码纠错读取 ---
def smart_read_csv(file):
    try:
        return pd.read_csv(file, encoding='utf-8')
    except:
        return pd.read_csv(file, encoding='gbk')

# --- 侧边栏 ---
with st.sidebar:
    st.title("🛡️ 凭证大师系统")
    st.info("版本：V21.0 企业级")
    menu = st.radio("功能模块", ["⚡ 流水生成凭证", "⚙️ 匹配规则设置", "📒 科目档案管理", "👥 客户档案管理"])
    st.divider()
    if st.button("🛑 重置所有临时缓存"):
        st.session_state.clear()
        st.rerun()

# --- 1. 科目档案管理 ---
if menu == "📒 科目档案管理":
    st.header("📒 科目档案管理")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("批量导入")
        f = st.file_uploader("上传科目表 (前两列必为编码和名称)", type=['xlsx', 'csv'], key="u1")
        if f:
            df = pd.read_excel(f) if f.name.endswith('xlsx') else smart_read_csv(f)
            new_data = df.iloc[:, [0, 1]].copy()
            new_data.columns = ["科目编码", "科目名称"]
            st.session_state.coa = pd.concat([st.session_state.coa, new_data]).drop_duplicates(subset=['科目编码']).reset_index(drop=True)
            st.success(f"已成功追加 {len(new_data)} 条科目")
    
    with c2:
        st.subheader("在线维护")
        edited = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True, key="ed1")
        if st.button("确认保存科目变更"):
            st.session_state.coa = edited
            st.toast("科目档案已更新")

# --- 2. 客户档案管理 ---
elif menu == "👥 客户档案管理":
    st.header("👥 客户档案管理")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("批量导入")
        f = st.file_uploader("上传客户表 (前两列必为编码和名称)", type=['xlsx', 'csv'], key="u2")
        if f:
            df = pd.read_excel(f) if f.name.endswith('xlsx') else smart_read_csv(f)
            new_data = df.iloc[:, [0, 1]].copy()
            new_data.columns = ["客户编码", "客户名称"]
            st.session_state.cust = pd.concat([st.session_state.cust, new_data]).drop_duplicates(subset=['客户编码']).reset_index(drop=True)
            st.success(f"已成功追加 {len(new_data)} 条客户")
    
    with c2:
        st.subheader("在线维护")
        edited = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True, key="ed2")
        if st.button("确认保存客户变更"):
            st.session_state.cust = edited
            st.toast("客户档案已更新")

# --- 3. 匹配规则设置 ---
elif menu == "⚙️ 匹配规则设置":
    st.header("⚙️ 凭证自动匹配规则")
    if st.session_state.coa.empty:
        st.warning("请先去『科目档案管理』导入科目表，否则无法选择科目！")
    else:
        coa_options = (st.session_state.coa["科目编码"].astype(str) + " " + st.session_state.coa["科目名称"]).tolist()
        edited_rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_options),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_options),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="ed3"
        )
        if st.button("保存匹配逻辑"):
            st.session_state.rules = edited_rules
            st.success("匹配规则保存成功！")

# --- 4. 流水生成凭证 (最严谨模块) ---
elif menu == "⚡ 流水生成凭证":
    st.header("⚡ 业务流水映射生成系统")
    
    with st.expander("📝 导入要求说明（请阅读）", expanded=False):
        st.write("Excel/CSV 必须包含以下四列，顺序不限：**时间、摘要、金额、单位**")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        start_no = st.number_input("起始凭证号 (如输入 3 则生成 003)", min_value=1, value=1)
    with col_b:
        bank_f = st.file_uploader("导入流水文件", type=['xlsx', 'csv'], key="u3")

    if bank_f:
        bank_df = pd.read_excel(bank_f) if bank_f.name.endswith('xlsx') else smart_read_csv(bank_f)
        
        if st.button("🚀 开始生成记账分录"):
            # 字段严谨校验
            required_cols = ["时间", "摘要", "金额", "单位"]
            missing = [c for c in required_cols if c not in bank_df.columns]
            
            if missing:
                st.error(f"流水文件缺失关键列：{', '.join(missing)}")
            elif st.session_state.rules.empty:
                st.error("规则库为空，请先设置匹配规则！")
            else:
                results = []
                cur_no = start_no
                
                for _, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 匹配规则
                    matched = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc)]
                    
                    if not matched.empty:
                        rule = matched.iloc[0]
                        unit = str(row["单位"])
                        # 查找客户编码
                        c_match = st.session_state.cust[st.session_state.cust["客户名称"] == unit]
                        c_code = c_match["客户编码"].values[0] if not c_match.empty else "未匹配"
                        
                        no_str = str(cur_no).zfill(3)
                        
                        # 借方
                        results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["借方科目"], "借方": row["金额"], "贷方": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷方
                        results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["贷方科目"], "借方": 0, "贷方": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                        cur_no += 1
                
                if results:
                    final_df = pd.DataFrame(results)
                    st.success(f"成功生成 {len(final_df)//2} 笔凭证（合计 {len(final_df)} 条分录）")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # 导出 Excel 内存流
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_df.to_excel(writer, index=False, sheet_name='凭证结果')
                    st.download_button(
                        label="📥 点击下载凭证结果文件",
                        data=output.getvalue(),
                        file_name=f"凭证结果_{datetime.now().strftime('%m%d%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("导入成功，但根据现有规则未匹配到任何数据，请检查『摘要关键词』。")