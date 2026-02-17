import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 页面严谨配置 ---
st.set_page_config(page_title="凭证大师 V22.0 - 线上生产版", layout="wide")

# 强制美化：统一按钮高度和配色
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #0052cc; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; background-color: #36b37e; color: white; }
    div[data-testid="stExpander"] { border: 1px solid #ddd; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 严谨的 Session 数据初始化 ---
# 确保在 Streamlit 运行期间，数据在不同页面切换时不丢失
for key in ['coa', 'cust', 'rules']:
    if key not in st.session_state:
        if key == 'rules':
            st.session_state[key] = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])
        else:
            # 这里的列名严格对应你上传的“科目编码”“科目名称”
            st.session_state[key] = pd.DataFrame(columns=["编码", "名称"])

# --- 3. 辅助功能：自动识别编码读取 CSV ---
def strict_read_csv(file):
    content = file.read()
    for enc in ['utf-8', 'gbk', 'gb2312', 'utf-16']:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except:
            continue
    return pd.read_csv(io.BytesIO(content))

# --- 4. 侧边栏及配置备份 (核心解决数据丢失) ---
with st.sidebar:
    st.title("🛡️ 凭证大师系统")
    st.info("线上版数据存在内存中，重启会重置。请务必使用下方的备份功能。")
    
    # 导出备份
    config_bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button(
        "💾 导出全量配置备份",
        data=json.dumps(config_bundle, ensure_ascii=False),
        file_name=f"config_backup_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json"
    )
    
    # 导入备份
    ref_file = st.file_uploader("📂 还原备份文件", type=['json'])
    if ref_file:
        data = json.load(ref_file)
        st.session_state.coa = pd.DataFrame(data['coa'])
        st.session_state.cust = pd.DataFrame(data['cust'])
        st.session_state.rules = pd.DataFrame(data['rules'])
        st.success("配置已全量还原！")
    
    st.divider()
    menu = st.radio("系统功能", ["⚡ 流水生成凭证", "⚙️ 匹配规则设置", "📒 科目档案管理", "👥 客户档案管理"])

# --- 5. 模块逻辑 ---

# 📒 科目档案管理
if menu == "📒 科目档案管理":
    st.header("📒 科目档案管理")
    f = st.file_uploader("批量上传科目表 (Excel/CSV)", type=['xlsx', 'csv'])
    if f:
        df = pd.read_excel(f) if f.name.endswith('xlsx') else strict_read_csv(f)
        # 严谨处理：根据你提供的文件，取前两列并重命名为标准格式
        new_coa = df.iloc[:, [0, 1]].copy()
        new_coa.columns = ["编码", "名称"]
        st.session_state.coa = pd.concat([st.session_state.coa, new_coa]).drop_duplicates(subset=['编码']).reset_index(drop=True)
        st.success(f"已同步 {len(st.session_state.coa)} 条科目记录")
    
    st.session_state.coa = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True)

# 👥 客户档案管理
elif menu == "👥 客户档案管理":
    st.header("👥 客户档案管理")
    f = st.file_uploader("批量上传客户档案", type=['xlsx', 'csv'])
    if f:
        df = pd.read_excel(f) if f.name.endswith('xlsx') else strict_read_csv(f)
        new_cust = df.iloc[:, [0, 1]].copy()
        new_cust.columns = ["编码", "名称"]
        st.session_state.cust = pd.concat([st.session_state.cust, new_cust]).drop_duplicates(subset=['编码']).reset_index(drop=True)
        st.success(f"已同步 {len(st.session_state.cust)} 条客户记录")
    
    st.session_state.cust = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True)

# ⚙️ 匹配规则设置
elif menu == "⚙️ 匹配规则设置":
    st.header("⚙️ 凭证匹配逻辑设置")
    if st.session_state.coa.empty:
        st.warning("⚠️ 请先导入科目表，否则无法选择科目！")
    else:
        coa_options = (st.session_state.coa["编码"].astype(str) + " " + st.session_state.coa["名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_options, width="medium"),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_options, width="medium"),
                "关键词": st.column_config.TextColumn("摘要包含关键词", placeholder="如：货款")
            },
            num_rows="dynamic",
            use_container_width=True
        )

# ⚡ 流水生成凭证 (核心功能)
elif menu == "⚡ 流水生成凭证":
    st.header("⚡ 流水生成凭证")
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        start_no = st.number_input("起始凭证号", min_value=1, value=1)
    with col_b:
        bank_f = st.file_uploader("上传流水 (必须含列：时间, 摘要, 金额, 单位)", type=['xlsx', 'csv'])

    if bank_f:
        bank_df = pd.read_excel(bank_f) if bank_f.name.endswith('xlsx') else strict_read_csv(bank_f)
        
        if st.button("🚀 开始执行映射生成"):
            # 1. 严谨校验列名
            needed = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in needed):
                st.error(f"流水文件格式错误！必须包含列名：{needed}")
            elif st.session_state.rules.empty:
                st.error("匹配规则库为空！")
            else:
                results = []
                cur_no = start_no
                
                # 2. 映射逻辑
                for _, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 匹配关键词
                    match = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not match.empty:
                        rule = match.iloc[0]
                        unit = str(row["单位"])
                        # 匹配客户编码
                        c_match = st.session_state.cust[st.session_state.cust["名称"] == unit]
                        c_code = c_match["编码"].values[0] if not c_match.empty else "未匹配"
                        
                        no_str = str(cur_no).zfill(3)
                        # 借
                        results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["借方科目"], "借方金额": row["金额"], "贷方金额": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷
                        results.append({
                            "凭证号": no_str, "日期": row["时间"], "摘要": desc,
                            "科目": rule["贷方科目"], "借方金额": 0, "贷方金额": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                        cur_no += 1
                
                # 3. 结果输出
                if results:
                    res_df = pd.DataFrame(results)
                    st.dataframe(res_df, use_container_width=True)
                    
                    # 导出 Excel 内存流
                    towrite = io.BytesIO()
                    res_df.to_excel(towrite, index=False, engine='openpyxl')
                    st.download_button(
                        label="📥 下载生成的凭证结果 Excel",
                        data=towrite.getvalue(),
                        file_name=f"凭证结果_{datetime.now().strftime('%m%d%H%M')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.warning("未能匹配到任何结果，请核对『关键词』和流水中的『摘要』。")
