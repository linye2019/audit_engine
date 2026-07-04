---
name: "medicare-guide-parser"
description: "解析国家医保局及各省市发布的医疗服务价格项目立项指南Excel文件，区分主项、加收项、扩展项、减收项，生成结构化解析结果。Invoke when user uploads 立项指南/价格拟定/项目对应 Excel files or asks to parse/analyze medical service price project guide data."
files:
  - ../../tools/medicare-guide-parser/parse_guide.py
---

# 医疗服务价格项目立项指南解析器

本 Skill 专门用于解析国家医保局及各省市医保局发布的医疗服务价格项目立项指南（征求意见稿/正式稿）Excel 文件，自动识别主项、加收项、扩展项、减收项等项目类型，并以结构化方式输出解析结果。

## 适用场景

- 用户上传立项指南相关 Excel 文件（文件名含"立项指南""项目对应""拟定价格""价格拟定"等关键词）
- 用户要求解析、归纳、总结医疗服务价格项目立项指南数据
- 用户需要区分主项与分项（加收项/扩展项/减收项）
- 用户需要将立项指南数据导入数据库或生成项目清单
- 用户需要分析某类别立项指南的项目结构、价格构成、计价规则

## 文件识别

### 文件命名规律

立项指南文件通常遵循以下命名格式：

```
YYYYMMDD_【地区】XX类立项指南项目对应及拟定情况（征求意见稿）.xlsx
YYYYMMDD_【地区】XX类项拟定价格情况.xlsx
附件N_XX类立项指南对应情况及价格拟定.xlsx
XX类立项指南映射项目表.xlsx
XX类医药科测算用.xlsx
```

示例：
- `20260310_心血管系统类立项指南项目对应及拟定情况（征求意见稿）.xlsx`
- `20250930_（泉州）中医骨伤及特殊疗法拟定价格.xlsx`
- `附件2_神经系统类立项指南项目价格拟定情况.xlsx`
- `体被系统类映射项目表（医药科测算用）.xlsx`

### 已知类别清单

| 类别 | 典型文件特征 | 说明 |
|------|------------|------|
| **心血管系统类** | 含心脏电生理、介入治疗、手术等项目 | 项目数量多，加收项复杂 |
| **神经系统类** | 含颅脑手术、神经调控、功能检查等 | 技术难度分级明显 |
| **呼吸系统类** | 含支气管镜、肺功能、呼吸治疗等 | 内镜操作项目集中 |
| **消化系统类** | 含内镜诊疗、消化介入、手术等 | 与疝甲乳类常合并发布 |
| **泌尿系统类** | 含泌尿外科手术、腔内治疗等 | 结石/肿瘤治疗项目多 |
| **骨骼肌肉系统类** | 含骨科手术、关节置换、脊柱手术等 | 手术分级最细 |
| **体被系统类** | 含皮肤、烧伤、整形相关项目 | 创面修复项目多 |
| **眼科类** | 含白内障、青光眼、眼底手术等 | 显微手术为主 |
| **耳鼻喉科类** | 含听力、鼻内镜、咽喉手术等 | 功能检查项目多 |
| **口腔类** | 含牙体牙髓、修复、正畸、种植等 | 细分专业多 |
| **口腔种植类** | 仅含种植相关项目 | 单独成册 |
| **颌面外科类** | 含颌面整形、创伤、肿瘤手术等 | 与口腔类有交叉 |
| **妇科类** | 含妇科手术、内镜、产科相关等 | 与产科类常合并 |
| **产科类** | 含分娩、产科手术、新生儿相关等 | 产后康复项目 |
| **麻醉类** | 含各类麻醉、镇痛、监测等 | 麻醉分级与时长关联 |
| **病理类** | 含病理检查、分子病理、细胞学等 | 技术方法分类细 |
| **放射检查类** | 含X线、CT、MRI、核医学检查等 | 设备参数影响价格 |
| **超声检查类** | 含各部位超声、介入超声等 | 按部位和深度分级 |
| **放射治疗类** | 含外照射、内照射、质子重离子等 | 技术迭代最快 |
| **物理治疗类** | 含康复理疗、运动治疗、作业治疗等 | 疗程化项目多 |
| **康复类** | 含功能评估、康复训练、辅助器具等 | 按功能障碍类型分 |
| **中医骨伤类** | 含手法整复、夹板固定、推拿等 | 儿童加收项多 |
| **中医针法类** | 含各类针刺、电针、温针等 | 按针法和部位分 |
| **中医灸法拔罐推拿类** | 含艾灸、拔罐、推拿等项目 | 传统疗法标准化 |
| **中医外治类** | 含敷贴、熏洗、药浴等 | 药物配伍影响价格 |
| **中医特殊疗法类** | 含小针刀、穴位注射、埋线等 | 创新疗法纳入 |
| **护理类** | 含分级护理、专科护理、特殊护理等 | 与等级护理制度衔接 |
| **综合诊查类** | 含门诊诊查、住院诊查、急诊诊查等 | 按医师级别分档 |
| **临床量表评估类** | 含各类心理、认知、功能量表评估 | 按评估时长和复杂度分 |
| **精神治疗类** | 含心理治疗、物理治疗、康复治疗等 | 疗程化特征明显 |
| **辅助生殖类** | 含人工授精、试管婴儿相关项目 | 技术步骤拆分细 |
| **器官移植类** | 含供体获取、移植手术、术后管理等 | 伦理审查关联 |
| **手术和治疗辅助操作类** | 含手术辅助、体位摆放、标本处理等 | 支持性项目 |
| **一般治疗类** | 含注射、输液、输血、氧疗等基础治疗 | 基础护理关联 |
| **药学类** | 含处方审核、用药指导、药物重整等 | 药学服务转型 |
| **美容整形类** | 含各类美容外科手术、非手术治疗等 | 自费项目为主 |
| **血液系统类** | 含输血、血液净化、造血干细胞采集等 | 按治疗次数和时长分 |
| **血管淋巴系统类** | 含血管手术、淋巴手术、静脉曲张治疗等 | 与心血管类有交叉 |

## 核心数据结构

### 项目类型分类体系

立项指南 Excel 中，项目代码（15位国家编码）的后4位编码后缀严格区分项目类型。**后缀法是经过跨类别验证的权威分类方法**（已在物理治疗类、泌尿系统类等多个类别中验证，差异率为0）。

#### 编码后缀分类规则（主要方法）

| 代码后缀（后4位） | 项目类型 | 说明 | 示例 |
|-----------------|---------|------|------|
| `0000` | **主项** | 独立的医疗服务价格项目基准 | `012411000010000` 肾盂内压检查费 |
| `0001` | **加收项** | 在主项价格基础上加收（第1级） | `012411000060001` 血浆置换费-双重血浆置换（加收） |
| `0011` | **加收项** | 在主项价格基础上加收（第2级） | — |
| `0021` | **加收项** | 在主项价格基础上加收（第3级） | — |
| `0100` | **扩展项** | 不额外加价，扩展适用范围 | `012411000040100` 输尿管镜-精囊镜检查（扩展） |
| `0200` | **扩展项** | 扩展（第2级） | — |
| 其他后缀 | **其他分项** | 按特定部位或方式细分 | 通过项目名称或上下文判断 |

#### 项目名称辅助细分

在后缀法分类基础上，通过"项目名称"进一步细分加收项子类型：

| 项目名称特征 | 子项类型 | 计价规则 | 典型示例 |
|------------|---------|---------|---------|
| 后缀0001/0011/0021 + 名称含"儿童" | **儿童加收项** | 6岁及以下未成年人加收 | `手法整复术-儿童（加收）` |
| 后缀0001/0011/0021 + 名称含"减收" | **减收项** | 在主项价格基础上减收 | `放疗模拟定位-简易模拟定位（减收）` |
| 后缀0001/0011/0021 + 其他名称 | **加收项** | 在主项价格基础上加收 | `放疗模拟定位-运动管理（加收）` |
| 后缀0100/0200 | **扩展项** | 不额外加价，扩展适用范围 | — |
| 后缀非0000/0001/0011/0021/0100/0200 | **其他分项** | 按特定部位或方式细分 | `尿流动力学检查费（尿流率检测）` |

#### 编码列选择优先级

部分Excel中存在多个编码列，必须按以下优先级选择：

1. **"项目代码"列**（15位立项指南原始编码） — 优先使用，后缀法依赖此列
2. **"国家结算编码"列**（格式为 `15位编码-9位编码`，如 `003402000140000-340200014`） — 仅在无"项目代码"列时使用，需提取前15位
3. **"项目编码"列**（9位地方编码） — 不适用于后缀分类

#### 序号与后缀交叉验证规则（必须遵守）

部分类别的"分项"行（序号为"分项"）**使用与主项相同的15位编码**（后缀同为0000），单纯后缀法会将这些子项误判为主项。**必须用序号格式做交叉验证**：

1. **序号为"分项"** → 一定不是主项，按项目名称判断子类型（儿童加收/减收/加收/扩展/其他分项）
2. **序号非纯数字** → 同上处理
3. **序号为纯数字** → 按后缀法分类（0000=主项，0001=加收项，0100=扩展项等）

> **注意**：对于无"项目代码"列的文件（如康复类、拟调价项目），只能从"国家结算编码"提取前15位，但该编码可能不严格遵循后缀规律。

### 三者在价格体系中的关系

```
立项指南价格项目体系
├── 主项（基准价格）
│   ├── 加收项 — 在基准价格上按比例/固定金额加收
│   │   ├── 技术加收（如调强、图像引导、自适应放疗）
│   │   ├── 场景加收（如儿童、急诊、夜间）
│   │   └── 复杂加收（如超长靶区、超高剂量率）
│   ├── 减收项 — 在基准价格上按比例/固定金额减收
│   │   └── 简化减收（如简易模拟定位）
│   └── 其他分项 — 按特定部位/方式执行，价格可能等于主项或单独定价
│       ├── 部位细分（如指间关节 vs 大关节）
│       └── 方式细分（如二维 vs 三维计划）
```

### 核心字段说明

| 字段名 | 说明 | 用途 |
|--------|------|------|
| **序号** | 项目序号或"分项"标识 | 区分主项/分项 |
| **项目代码** | 国家医保局统一结算编码（15位） | 唯一标识，关联数据库 |
| **项目名称** | 规范化的项目名称 | 展示与检索 |
| **归集口径** | 收费类别（手术费/检查费/治疗费等） | 财务归集与统计 |
| **服务产出** | 项目的服务内容与产出描述 | 界定项目边界 |
| **价格构成** | 价格涵盖的资源消耗说明 | 定价测算依据 |
| **计价单位** | 次/部位/疗程/日/小时等 | 计费单位 |
| **计价说明** | 加收/减收条件、除外内容等 | 临床执行指导 |
| **拟定价格(市级/县级/基层)** | 各级医疗机构拟定执行价格 | 实际收费基准 |

### 与医保智能审核规则的关联

立项指南数据可与医保智能审核系统的规则库关联：

```
立项指南数据                    医保审核规则
├── 项目代码 ──────────────→  FW.med_list_codg
├── 项目名称 ──────────────→  FW.med_list_name
├── 计价说明（加收条件）────→  rule_items.conditions（加收规则）
├── 计价说明（除外内容）────→  rule_items.conditions（互斥规则）
├── 归集口径 ──────────────→  FW.category_id → project_category
└── 服务产出 ──────────────→  FW.service_output
```

## 解析流程

### 步骤 1：扫描文件并识别类别

```python
import pandas as pd
import os, re

def scan_and_classify(file_path):
    """扫描 Excel 文件，自动识别立项指南类别"""
    fname = os.path.basename(file_path)
    
    # 提取类别名称
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
    
    # 判断文件来源
    if '泉州' in fname or '福建省' in fname:
        source = '福建省/泉州市'
    elif '征求意见稿' in fname:
        source = '国家医保局（征求意见稿）'
    elif '医药科测算' in fname or '映射' in fname:
        source = '地方医保局测算稿'
    else:
        source = '未知来源'
    
    return {
        'file_path': file_path,
        'filename': fname,
        'category': category,
        'source': source,
    }
```

### 步骤 2：动态定位列头并读取数据

```python
def extract_code_15(val):
    """从各种编码格式中提取15位立项指南编码"""
    if not val or val in ['nan', '']:
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

def find_header_row(raw_df, max_scan=25):
    """动态查找列头行"""
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

def choose_code_column(df):
    """选择最佳编码列：优先'项目代码'（15位），其次'国家结算编码'"""
    if '项目代码' in df.columns:
        sample = df['项目代码'].dropna().head(20)
        if sum(1 for v in sample if len(str(v).replace('.0','')) == 15) >= 5:
            return '项目代码'
    for c in ['国家结算编码', '项目编码']:
        if c in df.columns:
            return c
    return None

def parse_guide_excel(file_path):
    """解析立项指南 Excel，自动定位列头行"""
    xls = pd.ExcelFile(file_path)
    sheet_name = xls.sheet_names[0]
    
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)
    header_row = find_header_row(raw, max_scan=25)
    if header_row is None:
        header_row = 2
    
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row, dtype=str)
    
    # 过滤空行：编码列和名称列必须同时非空
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
```

### 步骤 3：基于编码后缀分类

```python
def categorize_by_suffix(code_15, name):
    """基于15位编码后缀严格分类"""
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

def categorize_items(df, code_col):
    """为每行数据应用后缀分类"""
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
```

### 步骤 4：建立主项-子项关联

```python
def link_parent_child(df):
    """基于编码前缀（前11位）为每个子项找到对应的主项"""
    df['所属主项代码'] = ''
    df['所属主项名称'] = ''
    
    main_items = df[df['项目类型'] == '主项']
    
    for pos in range(len(df)):
        if df.iloc[pos]['项目类型'] == '主项':
            continue
        sub_code = str(df.iloc[pos].get('立项指南编码_15位', ''))
        if not sub_code or len(sub_code) != 15:
            continue
        
        # 提取前11位作为主项前缀
        prefix = sub_code[:11]
        
        # 查找匹配的主项
        for _, main in main_items.iterrows():
            main_code = str(main.get('立项指南编码_15位', ''))
            if main_code.startswith(prefix):
                df.at[df.index[pos], '所属主项代码'] = main_code
                df.at[df.index[pos], '所属主项名称'] = main.get('项目名称', '')
                break
    
    return df
```

### 步骤 5：汇总统计与输出

```python
def summarize_guide(df):
    """生成立项指南解析汇总报告"""
    main_items = df[df['项目类型'] == '主项']
    stats = df['项目类型'].value_counts()
    
    report = {
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
```

## 输出格式

### 解析汇总报告（Markdown）

```
=== XX类立项指南解析结果 ===
总数据行数: N

=== 按项目类型统计 ===
  主项: X 个
  加收项: Y 个
  减收项: Z 个
  扩展项: W 个
  其他分项: V 个

=== 主项列表 ===
  1. 项目名称 (项目代码) — N个子项
  2. 项目名称 (项目代码) — N个子项
  ...

=== 各主项的子项明细 ===
【1. 项目名称】
  加收项 (N个):
    - 子项名称 (子项代码)
  减收项 (N个):
    - 子项名称 (子项代码)
```

### 结构化 Excel 输出

解析完成后生成包含 4 个 Sheet 的 Excel 文件：

| Sheet | 列定义 | 说明 |
|-------|--------|------|
| **全部数据** | 序号, 项目类型, 代码后缀, 所属主项代码, 所属主项名称, 项目代码, 项目名称, 归集口径, 服务产出, 价格构成, 计价单位, 计价说明 | 所有项目完整数据，保留立项指南原始核心字段 |
| **按类型汇总** | 项目类型, 数量, 占比 | 各类型数量及占比统计表 |
| **后缀规律分析** | 代码后缀, 数量, 对应类型, 示例 | 展示该类别的编码后缀分布规律 |
| **主项子项对照** | 主项序号, 主项名称, 主项代码, 子项类型, 子项代码, 子项名称, 代码后缀, 计价单位 | 主项与子项的树形对照关系 |

> **关键要求**：全部数据Sheet必须保留立项指南原始核心字段（序号/项目代码/项目名称/归集口径/服务产出/价格构成/计价单位/计价说明），不能只输出编码+名称+类型三列。

### 数据库导入映射

| 目标表 | 关键字段 | 数据来源 |
|--------|---------|---------|
| `FW` | med_list_codg, med_list_name, category_id, billing_unit, service_output | 立项指南主项 |
| `pricing_rules` | parent_code, sub_code, sub_type, price_adjustment | 立项指南分项（加收/减收规则） |
| `rule_items` | conditions（加收条件/互斥条件） | 计价说明中的加收/减收条件 |

## 注意事项

1. **列头行不固定**：不同地区、不同版本的立项指南文件，列头行可能在第 2~4 行，必须动态检测
2. **序号格式多样**：大部分文件用纯数字表示主项、"分项"表示子项，少数文件用"1a""1b"等扩展编号
3. **空行处理**：原始 Excel 中主项和分项之间常有空行（合并单元格导致），需过滤
4. **项目代码重复**：部分文件中，子项的项目代码可能与主项相同（仅通过项目名称区分），需特别注意
5. **价格列名差异**：不同文件的价格列名可能为"拟定价格""测算平移价格""省属三甲价格"等，需动态匹配
6. **多 Sheet 文件**：部分文件包含"项目对应表""变更记录""差额分析"等多个 Sheet，主数据通常在第一个 Sheet
7. **儿童加收统一模式**：中医骨伤类、护理类等文件中，儿童加收项高度统一（一般为基准价的 30%）
8. **技术加收复杂度**：放射治疗类、骨科手术类等技术迭代快的类别，加收项层级最多、规则最复杂

## 典型工作流

```bash
# 步骤1：解析单个立项指南文件
python parse_guide.py <excel文件路径>

# 步骤2：批量解析目录下所有立项指南文件
python parse_guide.py <目录路径> --batch

# 步骤3：生成汇总对比报告（多类别对比）
python parse_guide.py <目录路径> --batch --compare
```

**典型输出**：
1. 单个文件解析 → `XX类立项指南解析.xlsx`（3个Sheet）
2. 批量解析 → 每个文件生成对应的解析结果
3. 对比报告 → `立项指南多类别对比报告.xlsx`（含各类别项目数、子项类型分布、价格区间等）
