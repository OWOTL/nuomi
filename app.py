import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 财务级页面配置 ---
st.set_page_config(page_title="凭证大师 27.0 - 终极交付版", layout="wide")

# --- 2. 状态持久化（确保科目和规则刷新不丢） ---
def init_states():
    if 'coa' not in st.session_state: st.session_state.coa = pd.DataFrame(columns=["科目编码", "科目名称"])
    if 'cust' not in st.session_state: st.session_state.cust = pd.DataFrame(columns=["客户编码", "客户名称"])
    if 'rules' not in st.session_state: st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

init_states()

# --- 3. 严谨读取器：针对大哥的文件格式优化 ---
def read_financial_file(uploaded_file):
    """
    强制使用 string 类型读取，保护 000001 不变成 1
    """
    content = uploaded_file.read()
    # 自动探测编码，解决 GBK 乱码
    df = None
    for enc in ['utf-8-sig', 'gbk', 'gb18030', 'utf-8']:
        try:
            # dtype=str 是核心，确保所有编码不被截断或转义
            df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype=str)
            break
        except: continue
    
    if df is None:
        df = pd.read_excel(io.BytesIO(content), dtype=str)
    
    # 清理表头空格
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 4. 侧边栏：档案保险箱 ---
with st.sidebar:
    st.title("🛡️ 财务档案保险箱")
    st.markdown("---")
    
    # 导出备份包（JSON 格式最稳定）
    bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button(
        "💾 导出全量档案备份",
        data=json.dumps(bundle, ensure_ascii=False, indent=2),
        file_name=f"Voucher_Master_Backup_{datetime.now().strftime('%m%d')}.json",
        mime="application/json"
    )
    
    # 导入备份包
    restore = st.file_uploader("📂 还原备份文件", type=['json'])
    if restore:
        try:
            d = json.load(restore)
            st.session_state.coa = pd.DataFrame(d['coa'])
            st.session_state.cust = pd.DataFrame(d['cust'])
            st.session_state.rules = pd.DataFrame(d['rules'])
            st.success("✅ 档案已恢复，无需重新导入 CSV")
        except: st.error("备份文件损坏")

    st.markdown("---")
    menu = st.radio("系统功能", ["⚡ 凭证生成", "⚙️ 规则设置", "📒 科目档案", "👥 客户档案"])

# --- 5. 业务模块：档案同步 ---
if menu == "📒 科目档案":
    st.header("📒 科目档案同步")
    f = st.file_uploader("上传《科目表.csv》", type=['csv', 'xlsx'])
    if f:
        df = read_financial_file(f)
        # 严格取前两列对齐大哥的 CSV
        st.session_state.coa = df.iloc[:, [0, 1]].copy()
        st.session_state.coa.columns = ["科目编码", "科目名称"]
        st.success(f"已同步 {len(st.session_state.coa)} 条科目")
    st.session_state.coa = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True)

elif menu == "👥 客户档案":
    st.header("👥 客户档案同步")
    f = st.file_uploader("上传《客户档案信息.csv》", type=['csv', 'xlsx'])
    if f:
        df = read_financial_file(f)
        st.session_state.cust = df.iloc[:, [0, 1]].copy()
        st.session_state.cust.columns = ["客户编码", "客户名称"]
        st.success(f"已同步 {len(st.session_state.cust)} 条客户")
    st.session_state.cust = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True)

# --- 6. 业务模块：规则设置 ---
elif menu == "⚙️ 规则设置":
    st.header("⚙️ 关键词映射逻辑")
    if st.session_state.coa.empty:
        st.warning("⚠️ 请先在左侧菜单上传科目档案！")
    else:
        # 拼接展示：10020101 农村商业银行...
        coa_list = (st.session_state.coa["科目编码"] + " " + st.session_state.coa["科目名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_list),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_list),
            },
            num_rows="dynamic", use_container_width=True
        )

# --- 7. 核心：流水生成凭证 ---
elif menu == "⚡ 凭证生成":
    st.header("⚡ 凭证自动化生成")
    col1, col2 = st.columns([1, 2])
    with col1:
        start_no = st.number_input("起始凭证号", min_value=1, value=1, step=1)
    with col2:
        bank_f = st.file_uploader("上传业务流水 (包含列：时间, 摘要, 金额, 单位)", type=['csv', 'xlsx'])

    if bank_f:
        bank_df = read_financial_file(bank_f)
        if st.button("🚀 执行全量映射"):
            needed = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in needed):
                st.error(f"流水表头缺失，必须包含: {needed}")
            else:
                voucher_results = []
                cur_no = start_no
                
                for _, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 严谨匹配关键词
                    rule = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not rule.empty:
                        r = rule.iloc[0]
                        unit = str(row["单位"]).strip()
                        # 客户编码精准匹配
                        c_match = st.session_state.cust[st.session_state.cust["客户名称"] == unit]
                        c_code = c_match["客户编码"].values[0] if not c_match.empty else "未匹配"
                        
                        no_str = str(cur_no).zfill(3)
                        
                        # 借方分录
                        voucher_results.append({
                            "号数": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": r["借方科目"], "借方金额": row["金额"], "贷方金额": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷方分录
                        voucher_results.append({
                            "号数": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": r["贷方科目"], "借方金额": 0, "贷方金额": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                        cur_no += 1
                
                if voucher_results:
                    final_df = pd.DataFrame(voucher_results)
                    st.success(f"匹配成功！共处理 {len(bank_df)} 条流水，生成 {len(final_df)} 行分录。")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # 导出 Excel
                    output = io.BytesIO()
                    final_df.to_excel(output, index=False)
                    st.download_button("📥 下载凭证 Excel", data=output.getvalue(), file_name=f"凭证结果_{datetime.now().strftime('%H%M')}.xlsx")
                else:
                    st.warning("⚠️ 匹配结束，但没有流水符合当前的匹配规则。")
