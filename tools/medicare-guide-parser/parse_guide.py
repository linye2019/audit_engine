import pandas as pd
import os
import re
import json
from typing import Dict, List, Optional


def extract_code_15(val) -> str:
    if not val or str(val).strip() in ['nan', '']:
        return ''
    val = str(val).strip()
    if '-' in val:
        parts = val.split('-')
        if len(parts[0]) == 15 and parts[0].isdigit():
            return parts[0]
    if len(val) == 15 and val.isdigit():
        return val
    digits = ''.join(c for c in val if c.isdigit())
    if len(digits) >= 15:
        return digits[:15]
    return ''


def find_header_row(raw_df, max_scan: int = 25) -> Optional[int]:
    for i in range(min(max_scan, len(raw_df))):
        row_vals = [str(v).strip() for v in raw_df.iloc[i] if pd.notna(v)]
        if not row_vals:
            continue
        if '序号' in row_vals:
            if len(row_vals) >= 3 and all(len(v) < 50 for v in row_vals):
                return i
        key_cols = ['项目代码', '项目名称', '国家结算编码', '服务产出', '价格构成', '计价单位']
        if sum(1 for k in key_cols if k in row_vals) >= 2:
            if all(len(v) < 50 for v in row_vals):
                return i
    return None


def choose_code_column(df) -> Optional[str]:
    if '项目代码' in df.columns:
        sample = df['项目代码'].dropna().head(20)
        if sum(1 for v in sample if len(str(v).replace('.0', '')) == 15) >= 5:
            return '项目代码'
    for c in ['国家结算编码', '项目编码']:
        if c in df.columns:
            return c
    return None


def categorize_by_suffix(code_15: str, name: str) -> str:
    if not code_15 or code_15 in ['nan', '']:
        return '其他_无编码'
    if len(code_15) != 15 or not code_15.isdigit():
        return '异常_过滤'
    suffix = code_15[-4:]
    if suffix == '0000':
        return '主项'
    elif suffix in ['0001', '0011', '0021']:
        if '儿童' in name:
            return '儿童加收项'
        if '减收' in name:
            return '减收项'
        return '加收项'
    elif suffix in ['0100', '0200']:
        return '扩展项'
    else:
        return '其他分项'


def scan_and_classify(file_path: str) -> Dict:
    fname = os.path.basename(file_path)
    category_patterns = [
        r'(.+?)类立项指南',
        r'(.+?)类医项目对应',
        r'(.+?)类项拟定价格',
        r'(.+?)类映射项目',
        r'(.+?)类医药科测算',
        r'(.+?)类立项指南对应',
        r'(.+?)类立项指南项目',
    ]
    category = '未知类别'
    for pat in category_patterns:
        m = re.search(pat, fname)
        if m:
            category = m.group(1)
            break
    if '泉州' in fname or '福建省' in fname:
        source = '福建省/泉州市'
    elif '征求意见稿' in fname:
        source = '国家医保局（征求意见稿）'
    elif '医药科测算' in fname or '映射' in fname:
        source = '地方医保局测算稿'
    else:
        source = '未知来源'
    return {'file_path': file_path, 'filename': fname, 'category': category, 'source': source}


def parse_guide_excel(file_path: str) -> pd.DataFrame:
    xls = pd.ExcelFile(file_path)
    sheet_name = xls.sheet_names[0]
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)
    header_row = find_header_row(raw, max_scan=25)
    if header_row is None:
        header_row = 2
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row, dtype=str)
    code_col = choose_code_column(df)
    name_col = None
    for c in df.columns:
        if c == '项目名称':
            name_col = c
            break
    if not name_col:
        for c in df.columns:
            if '项目名称' in c and '.1' not in c:
                name_col = c
                break
    if code_col and name_col:
        mask = (df[code_col].notna() & (df[code_col] != 'nan') & (df[code_col] != '')) & \
               (df[name_col].notna() & (df[name_col] != 'nan') & (df[name_col] != ''))
        df = df[mask].copy()
    return df.reset_index(drop=True), code_col, name_col


def categorize_items(df: pd.DataFrame, code_col: str) -> pd.DataFrame:
    types = []
    codes_15 = []
    for _, row in df.iterrows():
        raw_code = str(row.get(code_col, ''))
        code_15 = extract_code_15(raw_code)
        name = str(row.get('项目名称', ''))
        types.append(categorize_by_suffix(code_15, name))
        codes_15.append(code_15)
    df['项目类型'] = types
    df['代码后缀'] = [c[-4:] if len(c) == 15 else '' for c in codes_15]
    df['立项指南编码_15位'] = codes_15
    return df


def link_parent_child(df: pd.DataFrame) -> pd.DataFrame:
    df['所属主项代码'] = ''
    df['所属主项名称'] = ''
    main_items = df[df['项目类型'] == '主项']
    for pos in range(len(df)):
        if df.iloc[pos]['项目类型'] == '主项':
            continue
        sub_code = str(df.iloc[pos].get('立项指南编码_15位', ''))
        if not sub_code or len(sub_code) != 15:
            continue
        prefix = sub_code[:11]
        for _, main in main_items.iterrows():
            main_code = str(main.get('立项指南编码_15位', ''))
            if main_code.startswith(prefix):
                df.at[df.index[pos], '所属主项代码'] = main_code
                df.at[df.index[pos], '所属主项名称'] = main.get('项目名称', '')
                break
    return df


def summarize_guide(df: pd.DataFrame, file_info: Dict) -> Dict:
    main_items = df[df['项目类型'] == '主项']
    stats = df['项目类型'].value_counts()
    report = {
        'file_info': file_info,
        'total_rows': len(df),
        'main_count': len(main_items),
        'sub_count': len(df) - len(main_items),
        'type_stats': stats.to_dict(),
        'main_items': []
    }
    for _, main in main_items.iterrows():
        subs = df[(df['所属主项代码'] == main.get('立项指南编码_15位', '')) & (df['项目类型'] != '主项')]
        sub_stats = subs['项目类型'].value_counts().to_dict() if len(subs) > 0 else {}
        report['main_items'].append({
            'seq': main.get('序号', ''),
            'code': main.get('立项指南编码_15位', ''),
            'name': main.get('项目名称', ''),
            'category': main.get('归集口径', ''),
            'unit': main.get('计价单位', ''),
            'sub_count': len(subs),
            'sub_stats': sub_stats
        })
    return report


def generate_markdown_report(report: Dict) -> str:
    lines = []
    lines.append(f"=== {report['file_info']['category']}类立项指南解析结果 ===")
    lines.append(f"文件名: {report['file_info']['filename']}")
    lines.append(f"数据来源: {report['file_info']['source']}")
    lines.append(f"总数据行数: {report['total_rows']}")
    lines.append(f"主项数: {report['main_count']}")
    lines.append(f"子项数: {report['sub_count']}")
    lines.append("")
    lines.append("=== 按项目类型统计 ===")
    for item_type, count in report['type_stats'].items():
        lines.append(f"  {item_type}: {count} 个")
    lines.append("")
    lines.append("=== 主项列表 ===")
    for i, main in enumerate(report['main_items'], 1):
        lines.append(f"  {i}. {main['name']} ({main['code']}) — {main['sub_count']}个子项")
    if report['main_items']:
        lines.append("")
        lines.append("=== 各主项的子项明细 ===")
        for i, main in enumerate(report['main_items'], 1):
            lines.append(f"【{i}. {main['name']}】")
            lines.append(f"  归集口径: {main['category']}")
            lines.append(f"  计价单位: {main['unit']}")
            lines.append(f"  子项统计: {main['sub_stats']}")
    return '\n'.join(lines)


def export_excel(df: pd.DataFrame, output_path: str):
    stats_df = df['项目类型'].value_counts().reset_index()
    stats_df.columns = ['项目类型', '数量']
    stats_df['占比'] = (stats_df['数量'] / len(df) * 100).round(2).astype(str) + '%'
    suffix_df = df.groupby(['代码后缀', '项目类型']).size().reset_index(name='数量')
    main_sub_df = df[df['项目类型'] != '主项'][
        ['所属主项名称', '所属主项代码', '项目类型', '立项指南编码_15位', '项目名称', '代码后缀', '计价单位']
    ].rename(columns={
        '所属主项名称': '主项名称',
        '所属主项代码': '主项代码',
        '立项指南编码_15位': '子项代码',
        '项目名称': '子项名称'
    })
    with pd.ExcelWriter(output_path) as writer:
        df.to_excel(writer, sheet_name='全部数据', index=False)
        stats_df.to_excel(writer, sheet_name='按类型汇总', index=False)
        suffix_df.to_excel(writer, sheet_name='后缀规律分析', index=False)
        main_sub_df.to_excel(writer, sheet_name='主项子项对照', index=False)


def parse_single_file(file_path: str, output_dir: str = None) -> Dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    file_info = scan_and_classify(file_path)
    df, code_col, name_col = parse_guide_excel(file_path)
    df = categorize_items(df, code_col)
    df = link_parent_child(df)
    report = summarize_guide(df, file_info)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        excel_path = os.path.join(output_dir, f"{base_name}_解析结果.xlsx")
        export_excel(df, excel_path)
        md_path = os.path.join(output_dir, f"{base_name}_解析报告.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(generate_markdown_report(report))
        report['output_files'] = {'excel': excel_path, 'markdown': md_path}
    return report


def batch_parse(input_dir: str, output_dir: str = None) -> List[Dict]:
    results = []
    for fname in os.listdir(input_dir):
        if not fname.endswith('.xlsx') and not fname.endswith('.xls'):
            continue
        file_path = os.path.join(input_dir, fname)
        try:
            report = parse_single_file(file_path, output_dir)
            results.append(report)
            print(f"✓ 解析成功: {fname}")
        except Exception as e:
            print(f"✗ 解析失败: {fname} — {str(e)}")
            results.append({'file_info': {'filename': fname}, 'error': str(e)})
    if output_dir and results:
        summary_path = os.path.join(output_dir, '批量解析汇总.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='医疗服务价格项目立项指南解析器')
    parser.add_argument('input', help='输入文件路径或目录')
    parser.add_argument('--output', '-o', help='输出目录')
    parser.add_argument('--batch', '-b', action='store_true', help='批量解析模式')
    args = parser.parse_args()
    if args.batch or os.path.isdir(args.input):
        results = batch_parse(args.input, args.output)
        print(f"\n批量解析完成，共处理 {len(results)} 个文件")
    else:
        report = parse_single_file(args.input, args.output)
        print(generate_markdown_report(report))