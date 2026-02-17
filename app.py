import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 页面严谨设置 ---
st.set_page_config(page_title="凭证大师 26.0 - 财务严谨版", layout="wide")

# --- 2. 状态持久化（解决丢失问题） ---
def init_all_states():
    if 'coa' not in st.session_state: st.session_state.coa = pd.DataFrame(columns=["科目编码", "科目名称"])
    if 'cust' not in st.session_state: st.session_state.cust = pd.DataFrame(columns=["客户编码", "客户名称"])
    if 'rules' not in st.session_state: st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

init_all_states()

# --- 3. 核心工具：保护前导零的读取器 ---
def financial_read(file):
    """
    针对大哥的 000001 编码进行特殊保护，防止变成数字 1
    """
    content = file.read()
    df = None
    # 尝试多种编码方案，彻底解决 CSV 乱码
    for enc in ['utf-8-sig', 'gbk', 'gb18030', 'utf-8']:
        try:
            # dtype=str 是精髓，保证科目编码 10020101 不会被科学计数法破坏
            df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype=str)
            break
        except: continue
    if df is None:
        df = pd.read_excel(io.BytesIO(content), dtype=str)
    
    # 清理列名空格，防止因为表头有个空格导致匹配失败
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 4. 侧边栏：档案保险箱（核心：解决线上数据不持久） ---
with st.sidebar:
    st.title("🛡️ 档案保险箱")
    st.warning("线上版刷新会清空。请在导入 425 个科目后，点击下方备份！")
    
    # 导出
    config_bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button(
        "💾 导出全量备份 (.json)",
        data=json.dumps(config_bundle, ensure_ascii=False),
        file_name=f"backup_{datetime.now().strftime('%m%d')}.json",
        mime="application/json"
    )
    
    # 导入
    uploaded_json = st.file_uploader("📂 还原备份文件", type=['json'])
    if uploaded_json:
        data = json.load(uploaded_json)
        st.session_state.coa = pd.DataFrame(data['coa'])
        st.session_state.cust = pd.DataFrame(data['cust'])
        st.session_state.rules = pd.DataFrame(data['rules'])
        st.success("✅ 配置已瞬间还原！")

    st.divider()
    menu = st.radio("导航", ["⚡ 凭证自动化生成", "⚙️ 规则引擎配置", "📒 科目档案管理", "👥 客户档案管理"])

# --- 5. 模块：科目档案 ---
if menu == "📒 科目档案管理":
    st.header("📒 科目档案")
    f = st.file_uploader("导入《科目表.csv》", type=['csv', 'xlsx'])
    if f:
        df = financial_read(f)
        # 严格对齐大哥提供的文件列名
        st.session_state.coa = df[['科目编码', '科目名称']].copy()
        st.success(f"已载入 {len(st.session_state.coa)} 条科目")
    st.session_state.coa = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True)

# --- 6. 模块：客户档案 ---
elif menu == "👥 客户档案管理":
    st.header("👥 客户档案")
    f = st.file_uploader("导入《客户档案信息.csv》", type=['csv', 'xlsx'])
    if f:
        df = financial_read(f)
        # 严格对齐：客户编码, 客户名称
        st.session_state.cust = df[['客户编码', '客户名称']].copy()
        st.success(f"已载入 {len(st.session_state.cust)} 条客户")
    st.session_state.cust = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True)

# --- 7. 模块：规则设置 ---
elif menu == "⚙️ 规则引擎配置":
    st.header("⚙️ 关键词映射逻辑")
    if st.session_state.coa.empty:
        st.error("❌ 请先上传科目表！")
    else:
        # 下拉列表：10020101 农村商业银行...
        coa_options = (st.session_state.coa["科目编码"] + " " + st.session_state.coa["科目名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_options),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_options),
            },
            num_rows="dynamic", use_container_width=True
        )

# --- 8. 核心模块：流水生成 ---
elif menu == "⚡ 凭证自动化生成":
    st.header("⚡ 凭证生成")
    col1, col2 = st.columns([1, 2])
    with col1:
        start_no = st.number_input("起始凭证号", min_value=1, value=1)
    with col2:
        bank_f = st.file_uploader("导入业务流水 (必含：时间, 摘要, 金额, 单位)", type=['csv', 'xlsx'])

    if bank_f:
        bank_df = financial_read(bank_f)
        if st.button("🚀 开始生成分录"):
            # 严谨校验
            needed = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in needed):
                st.error(f"流水列名必须包含: {needed}")
            else:
                final_vouchers = []
                # 准确实现：每一行流水生成一借一贷
                for i, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 匹配规则
                    matched = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not matched.empty:
                        r = matched.iloc[0]
                        unit = str(row["单位"]).strip()
                        # 核心：客户编码匹配逻辑
                        c_match = st.session_state.cust[st.session_state.cust["客户名称"] == unit]
                        c_code = c_match["客户编码"].values[0] if not c_match.empty else "未匹配"
                        
                        # 凭证号格式化：001, 002...
                        p_no = str(int(start_no + (len(final_vouchers)/2))).zfill(3)
                        
                        # 借方
                        final_vouchers.append({
                            "凭证号": p_no, "时间": row["时间"], "摘要": desc,
                            "科目": r["借方科目"], "借方": row["金额"], "贷方": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷方
                        final_vouchers.append({
                            "凭证号": p_no, "时间": row["时间"], "摘要": desc,
                            "科目": r["贷方科目"], "借方": 0, "贷方": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                
                if final_vouchers:
                    res_df = pd.DataFrame(final_vouchers)
                    st.dataframe(res_df, use_container_width=True)
                    # 导出
                    output = io.BytesIO()
                    res_df.to_excel(output, index=False)
                    st.download_button("📥 导出结果", data=output.getvalue(), file_name="凭证结果.xlsx")
