import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 页面级严谨配置 ---
st.set_page_config(page_title="凭证大师 Pro 24.0", layout="wide", initial_sidebar_state="expanded")

# --- 2. 核心状态持久化逻辑 ---
def init_state():
    if 'coa_data' not in st.session_state: st.session_state.coa_data = pd.DataFrame(columns=["编码", "名称"])
    if 'cust_data' not in st.session_state: st.session_state.cust_data = pd.DataFrame(columns=["编码", "名称"])
    if 'rules_data' not in st.session_state: st.session_state.rules_data = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

init_state()

# --- 3. 严谨读取工具 ---
def load_any_file(file):
    if file.name.endswith('xlsx'):
        return pd.read_excel(file)
    else:
        # 依次尝试常见编码，解决乱码投诉
        content = file.read()
        for enc in ['utf-8-sig', 'gbk', 'gb2312']:
            try:
                return pd.read_csv(io.BytesIO(content), encoding=enc)
            except: continue
        return pd.read_csv(io.BytesIO(content))

# --- 4. 侧边栏：档案保险箱（防止丢失的终极方案） ---
with st.sidebar:
    st.title("🛡️ 系统保险箱")
    st.markdown("---")
    
    # 导出备份：把当前所有辛苦配好的数据打包
    bundle = {
        "coa": st.session_state.coa_data.to_dict('records'),
        "cust": st.session_state.cust_data.to_dict('records'),
        "rules": st.session_state.rules_data.to_dict('records')
    }
    st.download_button(
        label="💾 下载全量档案备份",
        data=json.dumps(bundle, ensure_ascii=False, indent=2),
        file_name=f"Voucher_Master_Backup_{datetime.now().strftime('%m%d')}.json",
        mime="application/json"
    )
    
    # 恢复备份
    restore = st.file_uploader("📂 还原档案备份", type=['json'])
    if restore:
        try:
            d = json.load(restore)
            st.session_state.coa_data = pd.DataFrame(d['coa'])
            st.session_state.cust_data = pd.DataFrame(d['cust'])
            st.session_state.rules_data = pd.DataFrame(d['rules'])
            st.success("✅ 还原成功！")
        except: st.error("还原文件格式不正确")

    st.markdown("---")
    menu = st.radio("导航", ["⚡ 凭证自动化生成", "⚙️ 匹配逻辑配置", "📒 科目档案", "👥 客户档案"])

# --- 5. 功能模块 ---

if menu == "📒 科目档案":
    st.header("📒 科目档案（支持 400+ 条目）")
    f = st.file_uploader("上传科目 Excel/CSV", type=['xlsx', 'csv'], key="coa_f")
    if f:
        df = load_any_file(f)
        new_df = df.iloc[:, [0, 1]].astype(str)
        new_df.columns = ["编码", "名称"]
        st.session_state.coa_data = pd.concat([st.session_state.coa_data, new_df]).drop_duplicates(subset=['编码']).reset_index(drop=True)
    
    st.session_state.coa_data = st.data_editor(st.session_state.coa_data, num_rows="dynamic", use_container_width=True)

elif menu == "👥 客户档案":
    st.header("👥 客户档案")
    f = st.file_uploader("上传客户档案", type=['xlsx', 'csv'], key="cust_f")
    if f:
        df = load_any_file(f)
        new_df = df.iloc[:, [0, 1]].astype(str)
        new_df.columns = ["编码", "名称"]
        st.session_state.cust_data = pd.concat([st.session_state.cust_data, new_df]).drop_duplicates(subset=['编码']).reset_index(drop=True)
        
    st.session_state.cust_data = st.data_editor(st.session_state.cust_data, num_rows="dynamic", use_container_width=True)

elif menu == "⚙️ 匹配逻辑配置":
    st.header("⚙️ 关键词自动匹配逻辑")
    if st.session_state.coa_data.empty:
        st.warning("⚠️ 请先在『科目档案』导入科目！")
    else:
        coa_options = (st.session_state.coa_data["编码"] + " " + st.session_state.coa_data["名称"]).tolist()
        st.session_state.rules_data = st.data_editor(
            st.session_state.rules_data,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_options),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_options)
            },
            num_rows="dynamic",
            use_container_width=True
        )

elif menu == "⚡ 凭证自动化生成":
    st.header("⚡ 凭证自动化生成")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        start_no = st.number_input("起始凭证号", min_value=1, value=1, step=1)
    with col2:
        bank_f = st.file_uploader("导入流水 (必须含列：时间, 摘要, 金额, 单位)", type=['xlsx', 'csv'])

    if bank_f:
        bank_df = load_any_file(bank_f)
        if st.button("🚀 执行全量映射生成"):
            # 字段严谨性检查
            cols = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in cols):
                st.error(f"流水表头必须包含: {cols}")
            elif st.session_state.rules_data.empty:
                st.error("匹配规则为空！")
            else:
                voucher_list = []
                # 核心循环：绝不漏掉一条流水
                for i, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 匹配规则
                    matched = st.session_state.rules_data[st.session_state.rules_data['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not matched.empty:
                        rule = matched.iloc[0]
                        unit = str(row["单位"])
                        # 匹配客户
                        c_match = st.session_state.cust_data[st.session_state.cust_data["名称"] == unit]
                        c_code = c_match["编码"].values[0] if not c_match.empty else "未匹配"
                        
                        v_no = str(int(start_no + len(voucher_list)/2)).zfill(3)
                        
                        # 借方
                        voucher_list.append({
                            "凭证号": v_no, "日期": row["时间"], "摘要": desc,
                            "科目": rule["借方科目"], "借方金额": row["金额"], "贷方金额": 0,
                            "客户编码": c_code, "客户名称": unit
                        })
                        # 贷方
                        voucher_list.append({
                            "凭证号": v_no, "日期": row["时间"], "摘要": desc,
                            "科目": rule["贷方科目"], "借方金额": 0, "贷方金额": row["金额"],
                            "客户编码": c_code, "客户名称": unit
                        })
                
                if voucher_list:
                    res_df = pd.DataFrame(voucher_list)
                    st.success(f"处理完成！生成 {len(res_df)} 行分录。")
                    st.dataframe(res_df, use_container_width=True)
                    
                    # 导出 Excel
                    output = io.BytesIO()
                    res_df.to_excel(output, index=False)
                    st.download_button("📥 导出 Excel 结果", data=output.getvalue(), file_name="凭证生成结果.xlsx")
                else:
                    st.warning("导入成功，但没有流水匹配到现有规则。")
