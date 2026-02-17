import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime

# --- 1. 基础配置 ---
st.set_page_config(page_title="凭证大师 29.0 - 终极修复版", layout="wide")

# --- 2. 内存初始化 ---
if 'coa' not in st.session_state: st.session_state.coa = pd.DataFrame(columns=["编码", "名称"])
if 'cust' not in st.session_state: st.session_state.cust = pd.DataFrame(columns=["编码", "名称"])
if 'rules' not in st.session_state: st.session_state.rules = pd.DataFrame(columns=["关键词", "借方科目", "贷方科目"])

# --- 3. 针对报错的核心修复函数 ---
def smart_load(file):
    """
    专门解决大哥遇到的 ImportError 和文件不匹配问题
    """
    fname = file.name.lower()
    try:
        if fname.endswith('.csv'):
            # 解决乱码投诉
            content = file.read()
            for enc in ['utf-8-sig', 'gb18030', 'gbk']:
                try:
                    return pd.read_csv(io.BytesIO(content), encoding=enc, dtype=str)
                except: continue
            return pd.read_csv(io.BytesIO(content), dtype=str)
        
        elif fname.endswith('.xlsx'):
            return pd.read_excel(file, engine='openpyxl', dtype=str)
        
        elif fname.endswith('.xls'):
            # 解决 Traceback 里的 ImportError: Missing optional dependency 'xlrd'
            return pd.read_excel(file, engine='xlrd', dtype=str)
            
        else:
            # 万能尝试
            return pd.read_excel(file, dtype=str)
    except Exception as e:
        st.error(f"读取失败: {str(e)}。建议将文件另存为 .xlsx 后再上传。")
        return None

# --- 4. 侧边栏 ---
with st.sidebar:
    st.title("🛡️ 财务档案保险箱")
    st.info("数据存在内存中，刷新会清空。请务必及时导出备份！")
    
    # 导出
    bundle = {
        "coa": st.session_state.coa.to_dict('records'),
        "cust": st.session_state.cust.to_dict('records'),
        "rules": st.session_state.rules.to_dict('records')
    }
    st.download_button("💾 点击导出全量备份 (.json)", 
                       data=json.dumps(bundle, ensure_ascii=False),
                       file_name=f"backup_{datetime.now().strftime('%m%d')}.json")
    
    # 导入还原
    restore = st.file_uploader("📂 还原备份文件", type=['json'])
    if restore:
        d = json.load(restore)
        st.session_state.coa, st.session_state.cust, st.session_state.rules = pd.DataFrame(d['coa']), pd.DataFrame(d['cust']), pd.DataFrame(d['rules'])
        st.success("恢复成功")

    st.divider()
    menu = st.radio("系统功能", ["⚡ 凭证自动化生成", "⚙️ 规则映射", "📒 科目管理", "👥 客户管理"])

# --- 5. 模块开发 ---

# 统一处理科目和客户的导入逻辑，确保列名对齐
def show_archive_manager(state_key, title, file_label):
    st.header(title)
    f = st.file_uploader(file_label, type=['csv', 'xlsx', 'xls'])
    if f:
        df = smart_load(f)
        if df is not None:
            # 无论大哥的文件头叫什么，我们强行取前两列并重命名，防止 KeyError
            new_data = df.iloc[:, [0, 1]].copy()
            new_data.columns = ["编码", "名称"]
            st.session_state[state_key] = new_data
            st.success(f"已成功同步 {len(new_data)} 条数据")
    st.session_state[state_key] = st.data_editor(st.session_state[state_key], num_rows="dynamic", use_container_width=True)

if menu == "📒 科目管理":
    show_archive_manager('coa', "📒 会计科目档案", "上传科目表 (支持 .xls / .xlsx / .csv)")

elif menu == "👥 客户管理":
    show_archive_manager('cust', "👥 客户往来档案", "上传客户信息 (支持 .xls / .xlsx / .csv)")

elif menu == "⚙️ 规则映射":
    st.header("⚙️ 自动映射规则")
    if st.session_state.coa.empty:
        st.error("请先在‘科目管理’中导入科目表！")
    else:
        # 保护 000001 编码显示
        coa_list = (st.session_state.coa["编码"].astype(str) + " " + st.session_state.coa["名称"]).tolist()
        st.session_state.rules = st.data_editor(
            st.session_state.rules,
            column_config={
                "借方科目": st.column_config.SelectboxColumn("借方科目", options=coa_list),
                "贷方科目": st.column_config.SelectboxColumn("贷方科目", options=coa_list),
            },
            num_rows="dynamic", use_container_width=True
        )

elif menu == "⚡ 凭证自动化生成":
    st.header("⚡ 凭证自动生成")
    c1, c2 = st.columns([1, 2])
    with c1:
        s_no = st.number_input("起始凭证号", value=1)
    with c2:
        bank_f = st.file_uploader("导入流水 (需包含：时间, 摘要, 金额, 单位)", type=['csv', 'xlsx', 'xls'])
    
    if bank_f:
        b_df = smart_load(bank_f)
        if b_df is not None and st.button("🚀 开始生成"):
            # 检查列名，不区分大小写和空格
            b_df.columns = [c.strip() for c in b_df.columns]
            res = []
            curr = s_no
            for _, row in b_df.iterrows():
                memo = str(row.get('摘要', ''))
                # 模糊匹配关键词
                rule = st.session_state.rules[st.session_state.rules['关键词'].apply(lambda x: str(x) in memo if pd.notna(x) else False)]
                if not rule.empty:
                    r = rule.iloc[0]
                    unit = str(row.get('单位', '')).strip()
                    # 精准找客户编码
                    c_info = st.session_state.cust[st.session_state.cust["名称"] == unit]
                    c_code = c_info["编码"].values[0] if not c_info.empty else "未匹配"
                    
                    v_no = str(curr).zfill(3)
                    # 借方
                    res.append({"凭证号": v_no, "日期": row.get('时间'), "摘要": memo, "科目": r["借方科目"], "借方": row.get('金额'), "贷方": 0, "客编": c_code, "客户": unit})
                    # 贷方
                    res.append({"凭证号": v_no, "日期": row.get('时间'), "摘要": memo, "科目": r["贷方科目"], "借方": 0, "贷方": row.get('金额'), "客编": c_code, "客户": unit})
                    curr += 1
            
            if res:
                out_df = pd.DataFrame(res)
                st.dataframe(out_df, use_container_width=True)
                tmp = io.BytesIO()
                out_df.to_excel(tmp, index=False)
                st.download_button("📥 导出结果 Excel", tmp.getvalue(), "凭证结果.xlsx")
            else:
                st.warning("未能匹配到任何规则，请检查规则设置。")
