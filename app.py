import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 页面级严谨配置 ---
st.set_page_config(page_title="凭证大师 28.0 - 终极交付版", layout="wide")

# --- 2. 核心持久化与初始化 ---
# 解决“数据丢失”投诉：即使页面刷新，只要不关闭浏览器窗口，数据在 Session 内存中是稳定的。
# 跨天使用请务必使用侧边栏的“导出备份”功能。
def init_storage():
    if 'coa' not in st.session_state: st.session_state.coa = pd.DataFrame(columns=["科目编码", "科目名称"])
    if 'cust' not in st.session_state: st.session_state.cust = pd.DataFrame(columns=["客户编码", "客户名称"])
    if 'rules' not in st.session_state: st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

init_storage()

# --- 3. 核心工具：保护前导零与多重编码适配 ---
def financial_read(file):
    """
    针对大哥的 000001 编码进行保护。强制所有读取内容为字符串，绝不让财务编码受损。
    """
    content = file.read()
    df = None
    # 财务文件常见编码：GB18030(兼容GBK/GB2312), UTF-8-SIG(带BOM)
    for enc in ['utf-8-sig', 'gb18030', 'utf-8', 'gbk']:
        try:
            # dtype=str 是保护 000001 不变成 1 的关键！
            df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype=str)
            break
        except: continue
    
    if df is None:
        try:
            df = pd.read_excel(io.BytesIO(content), dtype=str)
        except:
            st.error("无法识别文件格式，请确保是标准的 CSV 或 Excel")
            return None
            
    # 清理所有表头和内容的空格，防止“宁波陆尊 ”和“宁波陆尊”匹配不上
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].str.strip()
        
    return df

# --- 4. 侧边栏：档案保险箱（针对“数据会丢”的终极对策） ---
with st.sidebar:
    st.title("🛡️ 财务档案保险箱")
    st.markdown("---")
    
    # 导出全量配置（JSON 格式最稳定，包含你的 425 个科目）
    bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button(
        "💾 导出全量配置备份 (.json)",
        data=json.dumps(bundle, ensure_ascii=False, indent=2),
        file_name=f"Voucher_Master_Backup_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        help="点击下载你录入的所有科目和规则，下次导入此文件即可恢复。"
    )
    
    # 还原备份
    restore_file = st.file_uploader("📂 还原备份文件", type=['json'])
    if restore_file:
        try:
            data = json.load(restore_file)
            st.session_state.coa = pd.DataFrame(data['coa'])
            st.session_state.cust = pd.DataFrame(data['cust'])
            st.session_state.rules = pd.DataFrame(data['rules'])
            st.success("✅ 档案配置已全量还原！")
        except: st.error("备份文件损坏或格式错误")

    st.divider()
    menu = st.radio("系统功能模块", ["⚡ 流水批量生成凭证", "⚙️ 规则映射设置", "📒 科目档案同步", "👥 客户档案同步"])

# --- 5. 模块：档案同步（1:1 对齐你的文件） ---
if menu == "📒 科目档案同步":
    st.header("📒 科目档案管理")
    f = st.file_uploader("上传《科目表.csv》", type=['csv', 'xlsx'])
    if f:
        df = financial_read(f)
        if df is not None:
            # 严格根据你提供的文件列名：科目编码, 科目名称
            st.session_state.coa = df[['科目编码', '科目名称']].copy()
            st.success(f"同步成功：共计载入 {len(st.session_state.coa)} 个会计科目")
    
    st.session_state.coa = st.data_editor(st.session_state.coa, num_rows="dynamic", use_container_width=True)

elif menu == "👥 客户档案同步":
    st.header("👥 客户档案管理")
    f = st.file_uploader("上传《客户档案信息.csv》", type=['csv', 'xlsx'])
    if f:
        df = financial_read(f)
        if df is not None:
            # 严格根据你提供的文件列名：客户编码, 客户名称
            st.session_state.cust = df[['客户编码', '客户名称']].copy()
            st.success(f"同步成功：共计载入 {len(st.session_state.cust)} 个客户档案")
    
    st.session_state.cust = st.data_editor(st.session_state.cust, num_rows="dynamic", use_container_width=True)

# --- 6. 模块：规则映射 ---
elif menu == "⚙️ 规则映射设置":
    st.header("⚙️ 关键词自动匹配逻辑")
    if st.session_state.coa.empty:
        st.warning("⚠️ 请先上传科目表，否则无法选择科目！")
    else:
        # 下拉菜单显示：10020101 农村商业银行-龙山支行...
        coa_options = (st.session_state.coa["科目编码"] + " " + st.session_state.coa["科目名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_options, width="large"),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_options, width="large"),
            },
            num_rows="dynamic", use_container_width=True
        )

# --- 7. 核心功能：凭证批量生成 ---
elif menu == "⚡ 流水批量生成凭证":
    st.header("⚡ 凭证生成控制台")
    col1, col2 = st.columns([1, 2])
    with col1:
        start_no = st.number_input("起始凭证号", min_value=1, value=1, step=1)
    with col2:
        bank_f = st.file_uploader("上传业务流水 (列名必须包含：时间, 摘要, 金额, 单位)", type=['csv', 'xlsx'])

    if bank_f:
        bank_df = financial_read(bank_f)
        if st.button("🚀 执行全量映射（生成所有匹配行）"):
            needed = ["时间", "摘要", "金额", "单位"]
            if not all(c in bank_df.columns for c in needed):
                st.error(f"流水表头缺失核心列！必须包含: {needed}")
            elif st.session_state.rules.empty:
                st.error("匹配规则库为空，请先设置规则！")
            else:
                voucher_data = []
                # 准确实现流水号逻辑
                current_v_no = start_no
                
                for _, row in bank_df.iterrows():
                    desc = str(row["摘要"])
                    # 精准关键词寻找
                    match_rules = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in desc if pd.notna(x) else False)]
                    
                    if not match_rules.empty:
                        rule = match_rules.iloc[0] # 取匹配到的第一个规则
                        unit_name = str(row["单位"])
                        # 客户编码精准匹配（000001 格式保护）
                        c_match = st.session_state.cust[st.session_state.cust["客户名称"] == unit_name]
                        c_code = c_match["客户编码"].values[0] if not c_match.empty else "未匹配"
                        
                        v_no_str = str(current_v_no).zfill(3)
                        
                        # 借方分录
                        voucher_data.append({
                            "凭证号": v_no_str, "时间": row["时间"], "摘要": desc,
                            "科目": rule["借方科目"], "借方金额": row["金额"], "贷方金额": 0,
                            "客户编码": c_code, "客户名称": unit_name
                        })
                        # 贷方分录
                        voucher_data.append({
                            "凭证号": v_no_str, "时间": row["时间"], "摘要": desc,
                            "科目": rule["贷方科目"], "借方金额": 0, "贷方金额": row["金额"],
                            "客户编码": c_code, "客户名称": unit_name
                        })
                        current_v_no += 1
                
                if voucher_data:
                    final_df = pd.DataFrame(voucher_data)
                    st.success(f"处理成功！生成 {len(final_df)} 行会计分录。")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # 导出 Excel
                    towrite = io.BytesIO()
                    final_df.to_excel(towrite, index=False)
                    st.download_button("📥 下载生成结果 Excel", data=towrite.getvalue(), file_name=f"凭证结果_{datetime.now().strftime('%m%d%H%M')}.xlsx")
                else:
                    st.warning("⚠️ 匹配结束：0笔流水符合关键词规则。")
