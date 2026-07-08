# -*- coding: utf-8 -*-
# 判断题答案专业审核: 用公认无争议的安全规范硬性规定, 核对题干断言与现有答案是否一致
# 只对"我有十足把握"的具体事实做判定, 一律输出候选清单供复核, 不做模糊臆断
import json, re, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SITE = r'C:\Users\liuru\Desktop\新建文件夹\测试\安管人员刷题系统'
CATS = ['A', 'B', 'C1', 'C2']

def norm(s):
    return re.sub(r'\s+', '', s)

# 每条规则: (name, 匹配整段题干的正则, 判定函数(text)->'A'/'B'/None)
# 'A'=正确 'B'=错误; 判定函数拿到的是已按空白归一化的文本
RULES = []
def rule(name, pat, fn):
    RULES.append((name, re.compile(pat), fn))

# 1. 未竣工建筑物设集体宿舍 —— 严禁
rule('未竣工建筑设宿舍', r'尚未竣工的建筑物内.{0,6}(设置|作为).{0,6}(员工)?(集体)?宿舍',
     lambda t: 'B')

# 2. 高处作业定义高度: 坠落高度基准面2m及以上
rule('高处作业2m定义', r'(高处作业|坠落高度基准面).{0,10}(\d+(?:\.\d+)?)\s*m(?:及以上|以上)',
     lambda t: None)  # 交由下面专门函数处理(需要提取具体数字)

def high_work_def(t):
    m = re.search(r'(高处作业|坠落高度基准面).{0,10}(\d+(?:\.\d+)?)\s*m(?:及以上|以上)', t)
    if not m:
        return None
    num = float(m.group(2))
    # 若题干明确是在"定义/界定"高处作业起点, 唯一正确值是2m
    if re.search(r'(定义|指|界定|即为高处作业|属于高处作业|称为高处作业)', t):
        return 'A' if num == 2 else 'B'
    return None
RULES[-1] = ('高处作业2m定义', RULES[-1][1], high_work_def)

# 3. TN-S系统: 工作零线与保护零线始终分开, 不得合并
rule('TNS零线分开', r'TN-?S.{0,20}(工作零线|N线).{0,10}(保护零线|PE线).{0,10}(合并|共用|连接在一起)',
     lambda t: 'B')
rule('TNS零线始终分开', r'TN-?S.{0,20}(工作零线|N线).{0,15}(保护零线|PE线).{0,15}(始终|全部|全程)?分开',
     lambda t: 'A')

# 4. 末级开关箱漏电保护器: 额定动作电流≤30mA, 动作时间≤0.1s
def leak_protect(t):
    m = re.search(r'漏电.{0,6}(保护器|断路器).{0,15}额定.{0,4}动作电流.{0,4}(不大于|不超过|小于等于|≤)\s*(\d+(?:\.\d+)?)\s*mA', t)
    ok = True
    if m and float(m.group(3)) != 30:
        ok = False
    m2 = re.search(r'额定.{0,4}动作时间.{0,4}(不大于|不超过|小于等于|≤)\s*(\d+(?:\.\d+)?)\s*s', t)
    if m2 and float(m2.group(2)) != 0.1:
        ok = False
    if not m and not m2:
        return None
    return 'A' if ok else 'B'
rule('漏电保护参数', r'漏电.{0,6}(保护器|断路器).{0,15}额定.{0,4}动作', leak_protect)

# 5. 基坑支护危大工程: 开挖深度3m及以上(专项方案)/5m及以上(专家论证)
def foundation_pit(t):
    m3 = re.search(r'(基坑|槽).{0,6}(开挖)?深度.{0,6}(\d+(?:\.\d+)?)\s*m.{0,6}(及以上|以上).{0,20}(专项(施工)?方案|危险性较大|危大)', t)
    if m3:
        return 'A' if float(m3.group(3)) == 3 else 'B'
    m5 = re.search(r'(基坑|槽).{0,6}(开挖)?深度.{0,6}(\d+(?:\.\d+)?)\s*m.{0,6}(及以上|以上).{0,20}(专家论证)', t)
    if m5:
        return 'A' if float(m5.group(3)) == 5 else 'B'
    return None
rule('基坑危大界限', r'(基坑|槽).{0,6}(开挖)?深度.{0,6}\d', foundation_pit)

# 6. 安全生产许可证: 有效期3年; 若题干还提到延期申请时限, 须为"期满前3个月"
def license_years(t):
    m = re.search(r'安全生产许可证.{0,10}有效期.{0,6}(\d+)\s*年', t)
    if not m:
        return None
    ok = int(m.group(1)) == 3
    m2 = re.search(r'期满前\s*(\d+)\s*个?月.{0,25}(申请|办理).{0,6}延期', t)
    if m2 and int(m2.group(1)) != 3:
        ok = False
    return 'A' if ok else 'B'
rule('许可证有效期3年', r'安全生产许可证.{0,10}有效期', license_years)

# 7. 专职安全生产管理人员配备: 特级≥6人, 一级≥4人, 二级及以下≥3人
def safety_officer_count(t):
    m = re.search(r'(特级|一级|二级(?:及以下)?).{0,6}(?:资质)?.{0,10}专职安全(?:生产管理)?人员.{0,6}(不得少于|不少于|至少|不低于)\s*(\d+)\s*人', t)
    if not m:
        return None
    grade, _, num = m.group(1), m.group(2), int(m.group(3))
    truth = {'特级': 6, '一级': 4, '二级': 3, '二级及以下': 3}
    want = truth.get(grade)
    if want is None:
        return None
    return 'A' if num == want else 'B'
rule('专职安全员配备人数', r'(特级|一级|二级(?:及以下)?).{0,6}(?:资质)?.{0,10}专职安全(?:生产管理)?人员', safety_officer_count)

# 8. 应急预案演练: 综合/专项预案每年至少一次, 现场处置方案每半年至少一次
def drill_freq(t):
    m1 = re.search(r'(综合|专项)(应急)?预案.{0,10}演练.{0,6}每.?(半)?年.{0,6}(至少|不少于)\s*([一1])\s*次', t)
    if m1:
        return 'B' if m1.group(3) else 'A'  # 若"半年"字样出现在综合/专项预案上, 应为错误(它们是每年)
    m2 = re.search(r'现场处置方案.{0,10}演练.{0,6}每.?(半)?年.{0,6}(至少|不少于)\s*([一1])\s*次', t)
    if m2:
        return 'A' if m2.group(1) else 'B'  # 现场处置方案应是"每半年"
    return None
rule('应急演练频次', r'(综合|专项)(应急)?预案.{0,10}演练|现场处置方案.{0,10}演练', drill_freq)

# 9. 意外伤害保险: 由施工单位(总承包单位)支付, 不得由职工个人承担
def insurance_payer(t):
    if re.search(r'意外伤害保险.{0,15}(个人|职工自己|从业人员)(自行)?(承担|缴纳|支付)', t):
        return 'B'
    if re.search(r'意外伤害保险.{0,15}(施工单位|总承包单位|建筑施工企业)(负责)?(承担|缴纳|支付)', t):
        return 'A'
    return None
rule('意外险由单位支付', r'意外伤害保险.{0,20}(个人|职工自己|从业人员|施工单位|总承包单位|建筑施工企业).{0,10}(承担|缴纳|支付)', insurance_payer)

# 10. 工伤保险: 由用人单位缴纳, 个人不缴费
def gs_insurance(t):
    if re.search(r'工伤保险.{0,15}(个人|职工|从业人员).{0,6}(缴纳|承担|支付)(?!.{0,4}(不需要|无需|不用))', t) and not re.search(r'(单位|企业).{0,6}(全部|全额)?(缴纳|承担|支付)', t):
        return 'B'
    if re.search(r'工伤保险.{0,15}(用人单位|施工单位|企业).{0,6}(全部|全额)?(缴纳|承担|支付)', t):
        return 'A'
    return None
rule('工伤保险单位缴费', r'工伤保险.{0,20}(个人|职工|从业人员|用人单位|施工单位|企业).{0,10}(缴纳|承担|支付)', gs_insurance)

# 11. 特种作业人员必须持证上岗
def special_worker(t):
    if re.search(r'特种作业人员.{0,10}(必须|应当)?.{0,6}(持证上岗|取得.{0,6}资格证书)', t):
        return 'A'
    if re.search(r'特种作业人员.{0,15}(可以|无需|不需要).{0,10}(不.{0,4}持证|无证)(上岗|作业)', t):
        return 'B'
    return None
rule('特种作业持证', r'特种作业人员.{0,20}(持证|无证|资格证书)', special_worker)

# 12b. 事故等级人数阈值(死亡): 一般<3, 较大3-10, 重大10-30, 特别重大>=30
# 注意中文语序是"N人以下/以上 死亡"(数字在前, 死亡/遇难在后), 不是反过来
def accident_grade(t):
    m = re.search(r'(\d+)\s*人(以下|以上).{0,4}(死亡|遇难)', t)
    if not m:
        return None
    num, direction = int(m.group(1)), m.group(2)
    grade = None
    for gm in re.finditer(r'(一般|较大|重大|特别重大)事故', t):
        if gm.start() < m.start():
            grade = gm.group(1)
    if not grade:
        return None
    truth = {('一般', '以下'): 3, ('较大', '以上'): 3, ('重大', '以上'): 10, ('特别重大', '以上'): 30}
    want = truth.get((grade, direction))
    if want is None:
        return None
    return 'A' if num == want else 'B'
rule('事故等级人数阈值', r'\d+\s*人(以下|以上).{0,4}(死亡|遇难)', accident_grade)

# 13. 事故报告时限: 单位负责人接报后1小时内上报
def report_hour(t):
    m = re.search(r'(单位)?负责人.{0,10}接.{0,4}报告.{0,4}后.{0,4}(\d+)\s*小时内.{0,10}(上报|报告)', t)
    if not m:
        return None
    return 'A' if int(m.group(2)) == 1 else 'B'
rule('事故1小时上报', r'负责人.{0,10}接.{0,4}报告.{0,4}后.{0,4}\d+\s*小时内', report_hour)

# 14. 剪刀撑与地面夹角45°~60°
def brace_angle(t):
    m = re.search(r'剪刀撑.{0,10}(与|和)?.{0,4}地面.{0,4}(倾角|夹角).{0,6}(\d+)\s*(°|度).{0,4}(至|~|-|到)\s*(\d+)\s*(°|度)', t)
    if not m:
        return None
    lo, hi = int(m.group(3)), int(m.group(6))
    return 'A' if (lo, hi) == (45, 60) else 'B'
rule('剪刀撑角度45-60', r'剪刀撑.{0,10}(与|和)?.{0,4}地面.{0,4}(倾角|夹角)', brace_angle)

# 15. 安全带"高挂低用"是正确用法, "低挂高用"是错误用法
def belt_use(t):
    if re.search(r'安全带.{0,15}(应|应当|须|要求)?.{0,4}高挂低用', t):
        return 'A'
    if re.search(r'安全带.{0,15}(可以|应|应当)?.{0,4}低挂高用', t):
        return 'B'
    return None
rule('安全带高挂低用', r'安全带.{0,20}(高挂低用|低挂高用)', belt_use)

# 16. 密目式安全立网不能代替平网(立网只能挡, 不能兜人)
def net_type(t):
    if re.search(r'(密目式)?(安全)?立网.{0,10}(可以)?.{0,4}代替.{0,4}平网', t):
        return 'B'
    return None
rule('立网不能代替平网', r'立网.{0,15}代替.{0,10}平网', net_type)

# 17. 塔式起重机顶升作业时严禁回转起吊
def tower_crane_lift(t):
    if re.search(r'塔.{0,4}(式)?起重机.{0,10}顶升.{0,10}(严禁|不得|禁止).{0,6}回转.{0,4}(起吊|作业)', t):
        return 'A'
    if re.search(r'塔.{0,4}(式)?起重机.{0,10}顶升.{0,10}(可以|允许).{0,6}回转.{0,4}(起吊|作业)', t):
        return 'B'
    return None
rule('塔吊顶升严禁回转', r'塔.{0,4}(式)?起重机.{0,10}顶升.{0,15}回转', tower_crane_lift)

# 18. 物料提升机(龙门架/井架)严禁乘人
def hoist_no_people(t):
    if re.search(r'(物料提升机|龙门架|井架).{0,15}(严禁|不得|禁止).{0,6}(乘人|载人|人员搭乘)', t):
        return 'A'
    if re.search(r'(物料提升机|龙门架|井架).{0,15}(可以|允许).{0,6}(乘人|载人|人员搭乘)', t):
        return 'B'
    return None
rule('物料提升机严禁乘人', r'(物料提升机|龙门架|井架).{0,20}(乘人|载人|人员搭乘)', hoist_no_people)

# 19. 起重"十不吊": 超载不吊/斜拉斜吊不吊
def ten_no_lift(t):
    if re.search(r'(超载|斜拉|斜吊).{0,10}(可以|允许).{0,4}(吊|起吊)', t):
        return 'B'
    if re.search(r'(超载|斜拉斜吊).{0,10}(不吊|不得|禁止|严禁)', t):
        return 'A'
    return None
rule('十不吊超载斜吊', r'(超载|斜拉斜吊).{0,15}(吊|不吊|禁止|严禁|可以|允许)', ten_no_lift)

# 20. 施工总承包对现场安全生产负总责; 分包单位服从总包管理, 不能说"与总包无关"
def subcontract_resp(t):
    if re.search(r'分包.{0,10}(区域|范围)?.{0,6}(安全|事故).{0,10}(与|和)总(承包|包).{0,6}无关', t):
        return 'B'
    if re.search(r'总(承包|包).{0,10}(对|负).{0,10}(施工现场)?安全生产.{0,6}(负|承担).{0,4}总责', t):
        return 'A'
    return None
rule('总包负安全总责', r'(总(承包|包).{0,15}(总责|无关)|分包.{0,15}(总包|总承包).{0,10}无关)', subcontract_resp)

# 21. 三级安全教育: 公司(企业)级、项目(工地)级、班组级, 缺一不可
def three_level_edu(t):
    if re.search(r'新(入职|进场)?(工人|员工|职工).{0,10}(只需|无需|可以不).{0,10}(公司|项目|班组)级.{0,10}教育', t):
        return 'B'
    return None
rule('三级教育缺一不可', r'新(入职|进场)?(工人|员工|职工).{0,20}(公司|项目|班组)级.{0,10}教育', three_level_edu)

# 22. 特种作业人员证书需要按期复审/延期
def cert_review(t):
    if re.search(r'特种作业.{0,10}(操作)?证.{0,10}(长期有效|无需|不需要).{0,6}(复审|延期|复核)', t):
        return 'B'
    return None
rule('特种作业证书需复审', r'特种作业.{0,15}证.{0,15}(长期有效|复审|延期|复核)', cert_review)

# 12. 扫地杆距底座上皮不大于200mm
def sweep_bar(t):
    m = re.search(r'(纵向)?扫地杆.{0,15}距.{0,6}(底座|地面).{0,6}(不大于|不超过|≤)\s*(\d+)\s*mm', t)
    if not m:
        return None
    return 'A' if int(m.group(4)) == 200 else 'B'
rule('扫地杆200mm', r'扫地杆.{0,15}距.{0,6}(底座|地面)', sweep_bar)

# ---------- 扫描 ----------
groups = {}
for cat in CATS:
    data = json.load(open(os.path.join(SITE, 'questions_%s.json' % cat), encoding='utf-8'))
    for q in data:
        if q['type'] != '判断':
            continue
        key = norm(q['stem'])
        groups.setdefault(key, []).append({'cat': cat, 'id': q['id'], 'ans': q['answer'], 'stem': q['stem']})

proposals = []
for key, items in groups.items():
    t = key
    for name, pat, fn in RULES:
        if not pat.search(t):
            continue
        expected = fn(t)
        if expected is None:
            continue
        cur_answers = set(x['ans'] for x in items)
        if cur_answers == {expected}:
            continue  # 已经全部正确, 无需改动
        proposals.append({'rule': name, 'expected': expected, 'stem': items[0]['stem'], 'items': items})
        break  # 每题只由第一条命中的规则判定, 避免规则互相覆盖

print('唯一判断题题干数:', len(groups))
print('候选修正数:', len(proposals))
for p in proposals:
    print('===', p['rule'], '→ 应为', '正确' if p['expected'] == 'A' else '错误')
    print(p['stem'][:80])
    print(' 现状:', ', '.join(x['cat'] + ':' + ('正确' if x['ans'] == 'A' else '错误') + '(' + x['id'] + ')' for x in p['items']))

json.dump(proposals, open(os.environ.get('TMP', '/tmp') + '/judge_proposals.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
