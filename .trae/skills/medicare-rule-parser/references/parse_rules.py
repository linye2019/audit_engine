#!/usr/bin/env python3
"""
医保智能监管规则知识点明细解析脚本模板
支持药品类、医疗服务项目类、中药饮片类、项目对类四种文件类型

修复记录:
- 修复项目代码被读为float的问题（统一用str读取）
- 修复"备注："行被误解析为数据的问题
- 新增项目对(project_pair)文件类型（第七批重复收费9列结构）
- 新增重复文件去重（第十批两个完全相同的文件）
- 修复子批次号提取（优先从Sheet名提取，更权威）
- 修复第八批-4周期超频次的8列结构（频次上限+周期）
"""
import pandas as pd
import os, re, json, glob
from datetime import datetime


# ============================================================
# 1. 文件扫描与自动分类
# ============================================================

def scan_files(directory):
    """扫描目录下所有知识点明细 Excel 文件并自动分类"""
    results = []
    seen_rule_names = {}  # 用于去重
    for f in sorted(glob.glob(os.path.join(directory, '*.xlsx'))):
        info = classify_file(f)
        if not info:
            continue
        # 去重：相同批次+规则名称的文件只保留第一个
        dedup_key = f"{info['batch']}_{info['rule_name']}"
        if dedup_key in seen_rule_names:
            print(f"  [SKIP] 重复文件已跳过: {os.path.basename(f)[:50]}")
            continue
        seen_rule_names[dedup_key] = True
        results.append(info)
    return results


def classify_file(file_path):
    """识别文件的批次、规则名称、类型"""
    fname = os.path.basename(file_path)
    xls = pd.ExcelFile(file_path)
    sheets = xls.sheet_names

    # 跳过非规则文件（ICD9/ICD10 对照表）
    if 'ICD9' in fname or 'ICD10' in fname:
        return None

    # 提取批次号（含子批次号）
    batch_match = re.search(r'(第[一二三四五六七八九十]+批[-]?\d*)', fname)
    batch = batch_match.group(1) if batch_match else None

    # 如果文件名没有子批次号，尝试从 Sheet 名提取
    if batch and '-' not in batch and sheets:
        sheet_batch = re.search(r'(第[一二三四五六七八九十]+批[-]?\d*)', sheets[0])
        if sheet_batch and '-' in sheet_batch.group(1):
            batch = sheet_batch.group(1)

    # 如果 Sheet 名有子批次但文件名没有，用 Sheet 名的
    if sheets:
        sheet_batch_full = re.search(r'(第[一二三四五六七八九十]+批[-]?\d*)', sheets[0])
        if sheet_batch_full:
            batch = batch or sheet_batch_full.group(1)
            # Sheet 名的子批次号更权威（处理第十一批文件名/Sheet名矛盾）
            if '-' in sheet_batch_full.group(1):
                batch = sheet_batch_full.group(1)

    # 提取规则名称（支持中英文引号）
    rule_name = None
    for src in [fname, sheets[0] if sheets else '']:
        rule_match = re.search(r'[""\u201c\u201d](.+?)[""\u201c\u201d]', src)
        if rule_match:
            rule_name = rule_match.group(1)
            break

    # 判断文件类型
    sheet_text = ' '.join(sheets)
    if '药品代码' in sheet_text:
        ftype = 'drug'
    elif '中药饮片' in fname or '中药饮片' in sheet_text:
        ftype = 'herbal'
    elif '重复收费' in fname or '重复收费' in sheet_text:
        ftype = 'project_pair'
    elif '手术' in fname or '折价' in fname:
        ftype = 'project'
    elif '医疗服务项目' in fname or '医疗服务项目' in sheet_text:
        ftype = 'project'
    else:
        ftype = 'unknown'

    if not batch and not rule_name:
        return None

    return {
        'file_path': file_path,
        'filename': fname,
        'batch': batch or '未知',
        'rule_name': rule_name or '未知',
        'file_type': ftype,
        'sheets': sheets
    }


# ============================================================
# 2. 通用解析器
# ============================================================

def find_header_row(raw_df, keyword='序号', max_scan=10):
    """在 DataFrame 中查找包含关键词的行作为列头行"""
    for i in range(min(max_scan, len(raw_df))):
        row_vals = [str(v).strip() for v in raw_df.iloc[i].values]
        if keyword in row_vals:
            return i
    return 3


def parse_sheet(file_path, sheet_name, header_keyword='序号', dtype=None):
    """解析指定 Sheet，自动定位列头，统一用str读取避免float问题"""
    raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    hr = find_header_row(raw, header_keyword)
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=hr, dtype=str)
    # 去掉全空行
    df = df.dropna(how='all').reset_index(drop=True)
    # 去掉序号为空的行
    first_col = df.columns[0]
    df = df[df[first_col].notna()].reset_index(drop=True)
    # 去掉"合计"行
    df = df[~df[first_col].astype(str).str.contains('合计', na=False)].reset_index(drop=True)
    # 去掉"备注："开头的行（非数据行）
    df = df[~df[first_col].astype(str).str.startswith('备注', na=False)].reset_index(drop=True)
    # 去掉"说明："开头的行（非数据行）
    df = df[~df[first_col].astype(str).str.startswith('说明', na=False)].reset_index(drop=True)
    return df


# ============================================================
# 3. 药品类规则解析
# ============================================================

def parse_drug_file(file_path):
    """解析药品类规则文件（含知识点明细 + 药品代码两个 Sheet）"""
    xls = pd.ExcelFile(file_path)
    sheets = xls.sheet_names

    # Sheet 1: 知识点明细（可能叫"知识点明细"或"知识点对应药品明细"等变体）
    kp_sheet = [s for s in sheets if '知识点' in s and '药品代码' not in s][0]
    kp_df = parse_sheet(file_path, kp_sheet, '序号')

    # Sheet 2: 药品代码
    code_sheet = [s for s in sheets if '药品代码' in s]
    code_df = None
    if code_sheet:
        raw = pd.read_excel(file_path, sheet_name=code_sheet[0], header=None, dtype=str)
        hr = find_header_row(raw, '对应知识点序号')
        code_df = pd.read_excel(file_path, sheet_name=code_sheet[0], header=hr, dtype=str)
        code_df = code_df.dropna(how='all')
        # 前向填充合并单元格
        first_col = code_df.columns[0]
        code_df[first_col] = code_df[first_col].ffill()
        second_col = code_df.columns[1]
        code_df[second_col] = code_df[second_col].ffill()
        code_df = code_df[code_df[code_df.columns[2]].notna()].reset_index(drop=True)
        code_df = code_df[~code_df[first_col].astype(str).str.contains('合计', na=False)].reset_index(drop=True)

    # 合并知识点与药品代码（按列名动态匹配，兼容不同列数）
    knowledge_points = []
    for _, row in kp_df.iterrows():
        cols = {str(c).strip(): i for i, c in enumerate(kp_df.columns)}

        # 按列名查找，兼容不同结构
        def get_val(row, possible_names, fuzzy=False):
            for name in possible_names:
                if fuzzy:
                    for col_name, col_idx in cols.items():
                        if name in col_name:
                            v = row.iloc[col_idx]
                            return str(v).strip() if pd.notna(v) and str(v) != 'nan' else None
                elif name in cols:
                    v = row.iloc[cols[name]]
                    return str(v).strip() if pd.notna(v) and str(v) != 'nan' else None
            return None

        seq_raw = get_val(row, ['序号'])
        seq_str = str(seq_raw).replace('.0', '') if seq_raw else ''
        count_raw = get_val(row, ['知识点对应'], fuzzy=True)
        count_str = str(count_raw).replace('.0', '') if count_raw else ''

        kp = {
            'seq': int(seq_str) if seq_str.isdigit() else None,
            'drug_name': get_val(row, ['药品通用名']),
            'detection_logic': get_val(row, ['检出逻辑']),
            'policy_basis': get_val(row, ['逻辑依据'], fuzzy=True),
            'drug_code_count': int(count_str) if count_str and count_str.isdigit() else None,
            'drug_codes': []
        }
        # 附加字段（如限定性别、是否2024目录等）
        for col_name, col_idx in cols.items():
            if col_name not in ('序号', '药品通用名', '检出逻辑') \
               and '知识点对应' not in col_name \
               and '逻辑依据' not in col_name:
                v = row.iloc[col_idx]
                kp[col_name] = str(v).strip() if pd.notna(v) and str(v) != 'nan' else None

        if code_df is not None and kp['seq'] is not None:
            codes = code_df[code_df[code_df.columns[0]].astype(str) == str(kp['seq'])][code_df.columns[3]].tolist()
            kp['drug_codes'] = [str(c).strip() for c in codes if pd.notna(c) and str(c) != 'nan']
        knowledge_points.append(kp)

    return knowledge_points


# ============================================================
# 4. 医疗服务项目类规则解析
# ============================================================

def parse_project_file(file_path):
    """解析医疗服务项目类规则文件（仅 1 个 Sheet，通用结构）"""
    xls = pd.ExcelFile(file_path)
    sheet = xls.sheet_names[0]

    # 统一用 str 读取，避免项目代码变为 float
    raw = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str)
    if raw.iloc[0, 0] == '序号':
        df = pd.read_excel(file_path, sheet_name=sheet, header=0, dtype=str)
    else:
        hr = find_header_row(raw, '序号')
        df = pd.read_excel(file_path, sheet_name=sheet, header=hr, dtype=str)

    df = df.dropna(how='all').reset_index(drop=True)
    first_col = df.columns[0]
    df = df[df[first_col].notna()].reset_index(drop=True)
    df = df[~df[first_col].astype(str).str.contains('合计', na=False)].reset_index(drop=True)
    # 过滤全空行（所有有效字段都为空）
    df = df.dropna(subset=[c for c in df.columns[1:4]], how='all').reset_index(drop=True)
    df = df[~df[first_col].astype(str).str.startswith('备注', na=False)].reset_index(drop=True)

    knowledge_points = []
    for _, row in df.iterrows():
        kp = {}
        for i, col in enumerate(df.columns):
            val = row.iloc[i]
            kp[str(col).strip()] = str(val).strip() if pd.notna(val) else None
        knowledge_points.append(kp)

    return knowledge_points


# ============================================================
# 5. 项目对类规则解析（第七批重复收费专用）
# ============================================================

def parse_project_pair_file(file_path):
    """解析项目对类规则文件（第七批重复收费，9列：项目A vs 项目B）"""
    xls = pd.ExcelFile(file_path)
    sheet = xls.sheet_names[0]

    raw = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str)
    hr = find_header_row(raw, '序号')
    df = pd.read_excel(file_path, sheet_name=sheet, header=hr, dtype=str)

    df = df.dropna(how='all').reset_index(drop=True)
    first_col = df.columns[0]
    df = df[df[first_col].notna()].reset_index(drop=True)
    df = df[~df[first_col].astype(str).str.contains('合计', na=False)].reset_index(drop=True)
    # 过滤有效字段全空的行（序号有值但项目名/代码都为空）
    df = df.dropna(subset=[c for c in df.columns[1:5] if c], how='all').reset_index(drop=True)

    knowledge_points = []
    for _, row in df.iterrows():
        # 标准化列名
        seq = row.iloc[0]
        seq_str = str(seq).replace('.0', '') if pd.notna(seq) else ''
        kp = {
            'seq': int(seq_str) if seq_str.isdigit() else None,
            'time_range': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None,
            'project_a_name': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None,
            'project_a_code': str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None,
            'project_b_name': str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None,
            'project_b_code': str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else None,
            'detection_logic': str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else None,
            'policy_basis': str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else None,
        }
        knowledge_points.append(kp)

    return knowledge_points


# ============================================================
# 6. 中药饮片类规则解析
# ============================================================

def parse_herbal_file(file_path):
    """解析中药饮片类规则文件"""
    return parse_project_file(file_path)


# ============================================================
# 7. 统一入口：批量解析所有文件
# ============================================================

def parse_all_files(directory):
    """批量解析目录下所有知识点明细文件"""
    files_info = scan_files(directory)
    all_rules = []

    for info in files_info:
        try:
            if info['file_type'] == 'drug':
                kps = parse_drug_file(info['file_path'])
            elif info['file_type'] == 'project_pair':
                kps = parse_project_pair_file(info['file_path'])
            elif info['file_type'] == 'project':
                kps = parse_project_file(info['file_path'])
            elif info['file_type'] == 'herbal':
                kps = parse_herbal_file(info['file_path'])
            else:
                kps = parse_project_file(info['file_path'])

            all_rules.append({
                'batch': info['batch'],
                'rule_name': info['rule_name'],
                'file_type': info['file_type'],
                'file_path': info['file_path'],
                'knowledge_point_count': len(kps),
                'knowledge_points': kps,
                'issues': []  # 复查发现的问题
            })
        except Exception as e:
            print(f"[ERROR] 解析失败: {info['filename']} -> {e}")

    # 二次复查纠偏
    all_rules = verify_and_fix(all_rules)

    return all_rules


# ============================================================
# 8. 二次复查纠偏
# ============================================================

def verify_and_fix(all_rules):
    """对解析结果进行二次复查纠偏，自动修复可修复的问题，报告无法自动修复的问题"""
    total_issues = 0
    auto_fixed = 0
    manual_needed = 0

    for rule in all_rules:
        issues = []
        kps = rule['knowledge_points']

        for idx, kp in enumerate(kps):
            # --- 检查1: 必填字段缺失 ---
            if rule['file_type'] == 'drug':
                for field in ['drug_name', 'detection_logic', 'policy_basis']:
                    if not kp.get(field) or kp[field] in ('None', 'nan', ''):
                        issues.append(f"第{idx+1}条: {field} 为空")

                # --- 检查2: 药品代码数量不一致 ---
                declared = kp.get('drug_code_count')
                actual = len(kp.get('drug_codes', []))
                if declared is not None and actual != declared:
                    if actual == 0 and declared > 0:
                        issues.append(f"第{idx+1}条[{kp.get('drug_name')}]: 声明{declared}个代码但实际0个（可能代码Sheet缺失或序号未匹配）")
                        manual_needed += 1
                    elif actual > 0:
                        # 自动修复：以实际代码数为准
                        kp['drug_code_count'] = actual
                        issues.append(f"第{idx+1}条[{kp.get('drug_name')}]: 声明{declared}个代码，实际{actual}个，已自动修正")
                        auto_fixed += 1

                # --- 检查3: 药品代码格式异常 ---
                for code in kp.get('drug_codes', []):
                    if not code or code in ('None', 'nan'):
                        kp['drug_codes'] = [c for c in kp['drug_codes'] if c and c not in ('None', 'nan')]
                        auto_fixed += 1
                    elif not re.match(r'^[XZT][A-Z0-9]+$', str(code)):
                        issues.append(f"第{idx+1}条[{kp.get('drug_name')}]: 代码格式异常 '{code}'（应以X/Z/T开头）")
                        manual_needed += 1

            elif rule['file_type'] == 'project_pair':
                # --- 检查4: 项目代码变 float（如 1.103e+13） ---
                for code_field in ['project_a_code', 'project_b_code']:
                    code_val = kp.get(code_field)
                    if code_val and ('e+' in str(code_val).lower() or '.0' in str(code_val)):
                        issues.append(f"第{idx+1}条: {code_field} 疑似float '{code_val}'")
                        manual_needed += 1
                    elif code_val and not re.match(r'^\d{15}$', str(code_val)):
                        issues.append(f"第{idx+1}条: {code_field} 非标准15位 '{code_val}'")
                        manual_needed += 1

                # --- 检查5: 项目对名称为空 ---
                if not kp.get('project_a_name') or not kp.get('project_b_name'):
                    issues.append(f"第{idx+1}条: 项目A或B名称为空")

            elif rule['file_type'] in ('project', 'herbal'):
                # --- 检查6: 项目类代码变 float ---
                for val in kp.values():
                    if val and isinstance(val, str) and ('e+' in val.lower() or ('.0' in val and val.count('.') == 1)):
                        issues.append(f"第{idx+1}条: 疑似项目代码float '{val}'")
                        manual_needed += 1

                # --- 检查7: 检出逻辑为空 ---
                detection = kp.get('检出逻辑') or kp.get('detection_logic')
                if not detection or detection in ('None', 'nan', ''):
                    issues.append(f"第{idx+1}条: 检出逻辑为空")

            # --- 检查8: 序号重复 ---
            if idx > 0:
                prev_seq = kps[idx-1].get('seq')
                curr_seq = kp.get('seq')
                if prev_seq is not None and curr_seq is not None and prev_seq == curr_seq:
                    issues.append(f"第{idx+1}条: 序号{curr_seq}与上一条重复")

            # --- 检查9: 非数据行残留 ---
            first_val = str(list(kp.values())[0]) if kp else ''
            if first_val.startswith('备注') or first_val == '合计' or first_val.startswith('注：'):
                issues.append(f"第{idx+1}条: 疑似非数据行残留 '{first_val[:20]}'")
                manual_needed += 1

        # --- 检查10: 序号连续性 ---
        seqs = [kp.get('seq') for kp in kps if kp.get('seq') is not None]
        if seqs:
            expected = list(range(1, len(seqs) + 1))
            if seqs != expected:
                gaps = [i+1 for i in range(len(seqs)) if i+1 not in seqs]
                if gaps:
                    issues.append(f"序号不连续，缺失: {gaps[:10]}{'...' if len(gaps)>10 else ''}")

        rule['issues'] = issues
        total_issues += len(issues)

    # 打印复查报告
    print(f"\n{'='*80}")
    print(f"二次复查纠偏报告")
    print(f"{'='*80}")
    print(f"  总计发现 {total_issues} 个问题")
    print(f"  自动修复: {auto_fixed} 个")
    print(f"  需人工确认: {manual_needed} 个")

    if total_issues > 0:
        print(f"\n--- 问题明细 ---")
        for rule in all_rules:
            if rule['issues']:
                print(f"\n  [{rule['batch']} {rule['rule_name']}] {len(rule['issues'])} 个问题:")
                for issue in rule['issues'][:10]:
                    print(f"    {issue}")
                if len(rule['issues']) > 10:
                    print(f"    ... 共 {len(rule['issues'])} 个问题")
    else:
        print(f"  所有知识点数据校验通过，无异常。")

    return all_rules


# ============================================================
# 9. 生成规则清单汇总
# ============================================================

def generate_rule_summary(all_rules):
    """生成规则清单汇总表"""
    rows = []
    for rule in all_rules:
        rows.append({
            '批次': rule['batch'],
            '规则名称': rule['rule_name'],
            '规则大类': classify_rule_category(rule['rule_name']),
            '适用对象': '药品' if rule['file_type'] == 'drug' else ('中药饮片' if rule['file_type'] == 'herbal' else '医疗服务项目'),
            '知识点数量': rule['knowledge_point_count'],
        })
    return pd.DataFrame(rows)


def classify_rule_category(rule_name):
    """根据规则名称自动归类"""
    category_map = {
        '区分性别使用': '性别限定',
        '儿童专用': '人群限定-儿童专用',
        '限儿童使用': '人群限定-限儿童',
        '限工伤保险': '药品-险种限定',
        '限生育保险': '药品-险种限定',
        '限就医方式': '药品-就医方式限定',
        '限医疗机构级别': '药品-机构级别限定',
        '限适应症': '药品-适应症限定',
        '限二线使用': '药品-使用顺序限定',
        '限支付疗程': '药品/项目-疗程限定',
        '超互联网医院': '药品-渠道限定',
        '单方使用不予支付': '中药饮片-支付限定',
        '单复方均不予支付': '中药饮片-支付限定',
        '限定频次': '医疗服务项目-频次限定',
        '周期超频次': '医疗服务项目-频次限定',
        '限年龄': '医疗服务项目-人群限定-限年龄',
        '重复收费': '医疗服务项目-重复收费',
        '折价收费': '医疗服务项目-折价收费',
    }
    for keyword, category in category_map.items():
        if keyword in rule_name:
            return category
    return '未分类'


# ============================================================
# 10. 保存/加载 JSON（支持独立复查）
# ============================================================

def save_to_json(all_rules, output_path):
    """将解析结果保存到 JSON 文件，供人工确认后复查使用"""
    # 移除 issues 字段（复查时会重新生成）
    export_data = []
    for rule in all_rules:
        r = {k: v for k, v in rule.items() if k != 'issues'}
        export_data.append(r)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"已保存 {len(export_data)} 批规则到 {output_path}")
    total_kp = sum(r['knowledge_point_count'] for r in export_data)
    print(f"共 {total_kp} 条知识点")


def load_from_json(input_path):
    """从 JSON 文件加载已修正的规则数据，用于二次复查"""
    with open(input_path, 'r', encoding='utf-8') as f:
        all_rules = json.load(f)
    # 补回 issues 字段
    for rule in all_rules:
        rule['issues'] = []
    print(f"已从 {input_path} 加载 {len(all_rules)} 批规则")
    total_kp = sum(r['knowledge_point_count'] for r in all_rules)
    print(f"共 {total_kp} 条知识点")
    return all_rules


def reverify_only(json_path):
    """独立复查入口：加载已修正的 JSON 数据，只执行复查纠偏，不重新解析 Excel"""
    print(f"加载已修正数据: {json_path}")
    all_rules = load_from_json(json_path)

    all_rules = verify_and_fix(all_rules)

    print(f"\n{'='*80}")
    print(f"复查后规则清单")
    print(f"{'='*80}")
    summary = generate_rule_summary(all_rules)
    print(summary.to_string(index=False))

    # 统计仍有问题的批次
    problem_rules = [r for r in all_rules if r['issues']]
    if problem_rules:
        print(f"\n仍有问题的批次: {len(problem_rules)} 个")
        print("请继续修正后重新执行: python parse_rules.py --reverify <json_path>")
    else:
        print(f"\n所有数据校验通过，可安全导入数据库。")

    return all_rules


# ============================================================
# 11. 主函数
# ============================================================

def main():
    import sys

    # 命令行模式：
    #   python parse_rules.py <directory>             # 解析 + 复查
    #   python parse_rules.py <directory> --save <json> # 解析 + 复查 + 保存JSON
    #   python parse_rules.py --reverify <json_path>   # 仅复查（从JSON加载）
    if len(sys.argv) >= 2 and sys.argv[1] == '--reverify':
        if len(sys.argv) < 3:
            print("用法: python parse_rules.py --reverify <json_path>")
            return
        reverify_only(sys.argv[2])
        return

    directory = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '/Users/linye/.trae-cn/attachments/6a411f4fd4ca28c1828ee8c3'

    # 检查是否需要保存 JSON
    save_path = None
    if '--save' in sys.argv:
        idx = sys.argv.index('--save')
        if idx + 1 < len(sys.argv):
            save_path = sys.argv[idx + 1]

    print(f"扫描目录: {directory}")
    all_rules = parse_all_files(directory)

    print(f"\n{'='*80}")
    print(f"解析完成: 共 {len(all_rules)} 批规则")
    print(f"{'='*80}")

    summary = generate_rule_summary(all_rules)
    print(summary.to_string(index=False))

    print(f"\n{'='*80}")
    print("各批次知识点明细:")
    print(f"{'='*80}")
    for rule in all_rules:
        print(f"\n--- {rule['batch']} {rule['rule_name']} ({rule['knowledge_point_count']} 条) ---")
        for kp in rule['knowledge_points'][:5]:
            if rule['file_type'] == 'drug':
                codes = kp.get('drug_codes', [])
                print(f"  [{kp.get('seq')}] {kp.get('drug_name')} | {kp.get('detection_logic')[:40]}... | 代码数: {kp.get('drug_code_count')} | 实际代码: {len(codes)}")
            elif rule['file_type'] == 'project_pair':
                print(f"  [{kp.get('seq')}] {kp.get('time_range')} | {kp.get('project_a_name')}({kp.get('project_a_code')}) vs {kp.get('project_b_name')}({kp.get('project_b_code')}) | {kp.get('detection_logic')}")
            else:
                vals = [str(v) for v in kp.values() if v and v != 'None' and v != 'nan'][:5]
                print(f"  {' | '.join(vals)[:90]}")
        if rule['knowledge_point_count'] > 5:
            print(f"  ... 共 {rule['knowledge_point_count']} 条")

    # 保存 JSON
    if save_path:
        save_to_json(all_rules, save_path)
        print(f"\n修正后复查请执行:")
        print(f"  python parse_rules.py --reverify {save_path}")


if __name__ == '__main__':
    main()
