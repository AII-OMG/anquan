# -*- coding: utf-8 -*-
# 正式修复: 从源docx补回丢失选项/修复题干, 处理死题, 标准JSON读写
import zipfile, re, json, glob, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r'C:\Users\liuru\Desktop\新建文件夹\测试'
SITE = os.path.join(BASE, '安管人员刷题系统')

def paras(p):
    xml = zipfile.ZipFile(p).read('word/document.xml').decode('utf-8')
    out = []
    for para in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S):
        t = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)).strip()
        if t:
            out.append(t)
    return out

TRANS = str.maketrans({',': '，', '(': '（', ')': '）', ':': '：', ';': '；', '?': '？', '!': '！', '.': '．'})
def norm(s):
    s = re.sub(r'\s+', '', s)
    s = s.translate(TRANS)
    if s.startswith('题目：'):
        s = s[3:]
    return s

def clean_text(s):
    return re.sub(r'\s+', ' ', s).strip()

def parse(p):
    qs, cur = [], None
    for t in paras(p):
        if re.match(r'^题目\s*[:：]', t):
            if cur and cur['opts']:
                qs.append(cur)
            cur = {'stem': re.sub(r'^题目\s*[:：]\s*', '', t), 'opts': []}
        else:
            m = re.match(r'^([A-E])\s*[、,，.．]\s*(.*)$', t)
            if m and cur is not None:
                cur['opts'].append((m.group(1), m.group(2).strip()))
            elif cur is not None and not cur['opts']:
                cur['stem'] += t
    if cur and cur['opts']:
        qs.append(cur)
    return qs

# ---------- 1. 源题池(按题型分池: 同一题干在单选/多选文档里选项结构不同, 严禁跨池匹配) ----------
def file_type(path):
    b = os.path.basename(path)
    for t in ('判断', '单选', '多选'):
        if t in b:
            return t
    return None

pools = {'判断': {}, '单选': {}, '多选': {}}
for f in glob.glob(os.path.join(BASE, '题库', '**', '*.docx'), recursive=True):
    if os.path.basename(f).startswith('~'):
        continue
    ft = file_type(f)
    if not ft:
        continue
    pool = pools[ft]
    for q in parse(f):
        key = norm(q['stem'])
        if key not in pool or len(q['opts']) > len(pool[key]['opts']):
            pool[key] = {'opts': q['opts'], 'stem': clean_text(q['stem'])}

# 前缀索引(前16字符); 匹配规则:
#   精确命中; 或 LCP>=30; 或 LCP覆盖两串中较短者(容差2字符, 且>=14)
PFX = 16
prefix_idxs = {}
for ft, pool in pools.items():
    idx = prefix_idxs[ft] = {}
    for key in pool:
        idx.setdefault(key[:PFX], []).append(key)

def find_src(stem, qtype):
    pool = pools.get(qtype, {})
    key = norm(stem)
    if key in pool:
        return pool[key]
    bucket = prefix_idxs.get(qtype, {}).get(key[:PFX], [])
    best, best_lcp = None, 0
    for cand in bucket:
        lcp = 0
        for a, b in zip(key, cand):
            if a != b:
                break
            lcp += 1
        if lcp > best_lcp:
            best, best_lcp = cand, lcp
    if best:
        shorter = min(len(key), len(best))
        if best_lcp >= 30 or (best_lcp >= 14 and best_lcp >= shorter - 2):
            return pool[best]
    return None

# ---------- 2. 手工修复表(死题+已确认答案错误题, 一律按"正确选项文本"定位, 不依赖字母) ----------
DELETE = [norm('在悬空部位作业时，操作人员应')[:14]]  # 选项数据已烂(两项黏连), 删除

def should_delete(stem):
    key = norm(stem)
    return any(key.startswith(p) for p in DELETE)

# 按"正确选项文本"定位答案(法条/规范原文可100%确认的):
# 《建筑法》第十条: 中止施工一个月内报告发证机关; 领取施工许可证三个月内开工
# 《建设工程质量管理条例》: 涉及建筑主体和承重结构变动的装修工程须委托设计
# 《安全生产许可证条例》: 国家对建筑施工企业实行安全生产许可制度
# 塔式起重机基本工作机构: 起升/变幅/回转/行走(大车运行)
# JGJ59 文明施工检查评定一般项目含生活设施(围挡/材料管理/办公住宿均为保证项目)
ANSWER_BY_TEXT = [
    (norm('在建的建筑工程因故中止施工的，建设单位应当自中止施工之日起')[:24], re.compile(r'^一个月$|^一$')),
    (norm('建设单位应当自领取施工许可证之日起')[:15], re.compile(r'^三个月$|^三$')),
    (norm('涉及（）的装修工程，建设单位应当在施工前委托原设计单位')[:20], re.compile(r'承重结构')),
    (norm('国家对（）实行安全生产许可制度')[:15], re.compile(r'^建筑施工企业$')),
    (norm('塔式起重机最基本的工作机构包括')[:15], re.compile(r'变幅.*行走|行走.*变幅')),
    (norm('房屋建筑工程施工的安全管理检查评定时，下列选项中属于文明施工检查评定的一般项目')[:30], re.compile(r'^生活设施$')),
]
def apply_text_answer(q):
    key = norm(q['stem'])
    for pfx, rx in ANSWER_BY_TEXT:
        if key.startswith(pfx):
            for i, o in enumerate(q['options']):
                t = re.sub(r'\s+', '', re.sub(r'^[A-E]\s*[、,，.．]\s*', '', o))
                if rx.search(t):
                    if q['answer'] != chr(65 + i):
                        q['answer'] = chr(65 + i)
                        return True
                    return False
    return False

# ---------- 3. 修复 ----------
def opt_prefix(o):
    m = re.match(r'^([A-E])\s*[、,，.．]', o)
    return m.group(1) if m else None

def is_valid(q):
    prefixes = [opt_prefix(o) for o in q['options']]
    aligned = all(p is None or p == chr(65 + i) for i, p in enumerate(prefixes))
    in_range = all(ord(L) - 65 < len(q['options']) for L in q['answer'])
    single_multi = q['type'] == '单选' and len(q['answer']) > 1
    return aligned and in_range and not single_multi

stats = {'ok': 0, 'src_repaired': 0, 'remapped': 0, 'manual': 0, 'deleted': 0}
deleted_log = []
for cat in ['A', 'B', 'C1', 'C2']:
    path = os.path.join(SITE, 'questions_%s.json' % cat)
    data = json.load(open(path, encoding='utf-8'))
    out = []
    for q in data:
        if is_valid(q) and not should_delete(q['stem']):
            if apply_text_answer(q):
                stats['ans_fixed'] = stats.get('ans_fixed', 0) + 1
            stats['ok'] += 1
            out.append(q)
            continue
        if should_delete(q['stem']):
            stats['deleted'] += 1
            deleted_log.append(q['id'] + ' [黏连选项] ' + q['stem'][:30])
            continue
        # 3a. 源文档修复(替换选项与题干), 再按文本规则修正答案
        src = find_src(q['stem'], q['type'])
        if src:
            letters = [L for L, _ in src['opts']]
            if letters == [chr(65 + i) for i in range(len(letters))]:
                q['options'] = ['%s、%s' % (L, t) for L, t in src['opts']]
                q['stem'] = src['stem']
                if apply_text_answer(q):
                    stats['ans_fixed'] = stats.get('ans_fixed', 0) + 1
                if is_valid(q):
                    stats['src_repaired'] += 1
                    out.append(q)
                    continue
        # 3a-2. 源不可用(未匹配/字母不规整)时, 按现有选项文本修答案
        if apply_text_answer(q):
            stats['ans_fixed'] = stats.get('ans_fixed', 0) + 1
            if is_valid(q):
                out.append(q)
                continue
        # 3b. 重映射: 答案字母在幸存前缀中 -> 换算成位置字母
        prefixes = [opt_prefix(o) for o in q['options']]
        if all(prefixes) and all(L in prefixes for L in q['answer']) and (q['type'] != '单选' or len(q['answer']) == 1):
            q['answer'] = ''.join(sorted(chr(65 + prefixes.index(L)) for L in q['answer']))
            q['options'] = ['%s、%s' % (chr(65 + i), re.sub(r'^[A-E]\s*[、,，.．]\s*', '', o)) for i, o in enumerate(q['options'])]
            if is_valid(q):
                stats['remapped'] += 1
                out.append(q)
                continue
        # 3c. 从题干里抢救被吞掉的选项("...（）。A 、xxB 、yy...")
        def salvage(q):
            s = q['stem']
            ms = list(re.finditer(r'([A-E])\s*[、,，.．]', s))
            if len(ms) < 2:
                return False
            letters = [x.group(1) for x in ms]
            if letters != [chr(65 + i) for i in range(len(letters))]:
                return False
            stem_clean = s[:ms[0].start()].strip()
            if len(stem_clean) < 8:
                return False
            opts = []
            for i, x in enumerate(ms):
                end = ms[i + 1].start() if i + 1 < len(ms) else len(s)
                t = s[x.end():end].strip()
                if not t:
                    return False
                opts.append((x.group(1), t))
            q['options'] = ['%s、%s' % (L, clean_text(t)) for L, t in opts]
            q['stem'] = clean_text(stem_clean)
            return True
        if salvage(q) and is_valid(q):
            stats['salvaged'] = stats.get('salvaged', 0) + 1
            out.append(q)
            continue
        # 3d. 无法修复 -> 删除
        stats['deleted'] += 1
        deleted_log.append(q['id'] + ' [无法修复] ' + q['stem'][:30])
    txt = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    json.loads(txt)  # 写盘前自校验
    open(path, 'w', encoding='utf-8').write(txt)
    print(cat, '写入', len(out), '题')

print('统计:', stats)
print('--- 删除清单(%d) ---' % len(deleted_log))
for x in deleted_log[:40]:
    print(' ', x)
if len(deleted_log) > 40:
    print('  ...共', len(deleted_log), '条')

# ---------- 4. 终验: 全库不允许再有损坏题 ----------
bad = 0
for cat in ['A', 'B', 'C1', 'C2']:
    data = json.load(open(os.path.join(SITE, 'questions_%s.json' % cat), encoding='utf-8'))
    for q in data:
        if not is_valid(q):
            bad += 1
print('终验损坏题数:', bad)
