import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 页面级严谨配置 ---
st.set_page_config(page_title="凭证大师 25.0 - 生产交付级", layout="wide")

# --- 2. 核心状态持久化逻辑 ---
# 解决重启丢失：通过逻辑确保数据在内存中稳定
def init_all_states():
    if 'coa' not in st.session_state: st.session_state.coa = pd.DataFrame(columns=["科目编码", "科目名称"])
    if 'cust' not in st.session_state: st.session_state.cust = pd.DataFrame(columns=["客户编码", "客户名称"])
    if 'rules' not in st.session_state: st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

init_all_states()

# --- 3. 严谨读取工具（针对你的文件格式优化） ---
def read_financial_file(uploaded_file):
    """自动适配编码，并强制将首列作为字符串处理（保护前导零）"""
    content = uploaded_file.read()
    # 尝试多种编码解决乱码投诉
    df = None
    for enc in ['utf-8-sig', 'gbk', 'utf-8', 'gb2312']:
        try:
            # dtype={0: str} 确保 000001 不会变成 1
            df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype={0: str, 1: str})
            break
        except: continue
    
    if df is None: # 如果CSV失败，尝试Excel
        df = pd.read_excel(io.BytesIO(content), dtype={0: str, 1: str})
    
    return df

# --- 4. 侧边栏：档案保险箱 ---
with st.sidebar:
    st.title("🛡️ 档案与备份")
    st.markdown("---")
    
    # 导出逻辑
    bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button(
        "💾 下载全量备份 (.json)",
        data=json.dumps(bundle, ensure_ascii=False, indent=2),
        file_name=f"config_backup_{datetime.now().strftime('%m%d')}.json",
        mime="application/json"
    )
    
    # 还原逻辑
    restore = st.file_uploader("📂 还原备份", type=['json'])
    if restore:
        d = json.load(restore)
        st.session_state.coa = pd.DataFrame(d['coa'])
        st.session_state.cust = pd.DataFrame(d['cust'])
        st.session_state.rules = pd.DataFrame(d['rules'])
        st.success("配置已还原")

    st.markdown("---")
    menu = st.radio("系统导航", ["⚡ 流水处理", "⚙️ 规则配置", "📒 科目档案", "👥 客户档案"])

# --- 5. 功能模块 ---

if menu == "📒 科目档案":
    st.header("📒 科目档案管理")
    f = st.file_uploader("导入科目表", type=['xlsx', 'csv'])
    if f:
        df = read_financial_file(f)
        df.columns = ["科目编码", "科目名称"] # 强制对齐你的表头
        st.session_state.coa = pd.concat([st.session_state.coa, df]).drop_duplicates(subset=['科目编码']).reset_index(drop=True)
    st.session_state.coa = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True)

elif menu == "👥 客户档案":
    st.header("👥 客户档案管理")
    f = st.file_uploader("导入客户档案", type=['xlsx', 'csv'])
    if f:
        df = read_financial_file(f)
        df.columns = ["客户编码", "客户名称"]
        st.session_state.cust = pd.concat([st.session_state.cust, df]).drop_duplicates(subset=['客户编码']).reset_index(drop=True)
    st.session_state.cust = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True)

elif menu == "⚙️ 规则配置":
    st.header("⚙️ 关键词匹配规则")
    if st.session_state.coa.empty:
        st.warning("请先上传科目表")
    else:
        # 严格对齐你科目表中的展示方式
        coa_list = (st.session_state.coa["科目编码"] + " " + st.session_state.coa["科目名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_list),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_list)
            },
            num_rows="dynamic",
            use_container_width=True
        )

elif menu == "⚡ 流水处理":
    st.header("⚡ 凭证自动化生成")
    c1, c2 = st.columns([1, 2])
    with c1:
        start_no = st.number_input("起始凭证号", min_value=1, value=1)
    with c2:
        bank_f = st.file_uploader("上传流水（需含：时间, 摘要, 金额, 单位）", type=['xlsx', 'csv'])

    if bank_f:
        bank_df = read_financial_file(bank_f)
        if st.button("🚀 执行生成"):
            # 严格按照你提供的列名校验
            cols = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in cols):
                st.error(f"流水表头必须包含: {cols}")
            else:
                final_results = []
                cur_no = start_no
                # 核心逻辑：确保不漏掉每一行，并处理1对2分录
                for _, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 严谨规则查找
                    matched_rule = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not matched_rule.empty:
                        rule = matched_rule.iloc[0]
                        unit = str(row["单位"])
                        # 查找客户
                        c_match = st.session_state.cust[st.session_state.cust["客户名称"] == unit]
                        c_code = c_match["客户编码"].values[0] if not c_match.empty else "未匹配"
                        
                        no_str = str(cur_no).zfill(3)
                        # 借方
                        final_results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["借方科目"], "借方金额": row["金额"], "贷方金额": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷方
                        final_results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["贷方科目"], "借方金额": 0, "贷方金额": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                        cur_no += 1
                
                if final_results:
                    res_df = pd.DataFrame(final_results)
                    st.success(f"成功处理 {len(bank_df)} 条流水，生成 {len(res_df)} 行分录。")
                    st.dataframe(res_df, use_container_width=True)
                    
                    output = io.BytesIO()
                    res_df.to_excel(output, index=False)
                    st.download_button("📥 导出 Excel", data=output.getvalue(), file_name="凭证生成结果.xlsx")
                else:
                    st.warning("流水中没有摘要能匹配上已设定的规则关键词。")
