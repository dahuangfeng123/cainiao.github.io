import csv, re
from collections import Counter

with open(r'd:\MyProjects\Moring_Read\data\关系.txt', 'r', encoding='utf-8') as f:
    text = f.read()

rows = []
seen = set()

def add(w1, rel, w2):
    w1 = w1.strip().strip("'").strip()
    w2 = w2.strip().strip("'").strip()
    if not w1 or not w2:
        return
    if len(w1) == 1 and w1.isupper():
        return
    if len(w1) <= 2 and w1.isalpha() and w1[0].isupper() and len(w1) == 2 and w1[0].lower() == w1[1].lower():
        return
    key = (w1.lower(), rel, w2.lower())
    if key not in seen:
        seen.add(key)
        rows.append([w1, rel, w2])

# 1. 同音词
homophone_sections = re.findall(r'同音词(.+?)(?=近义词|反义词|对应词|词形|$)', text, re.DOTALL)
for sec in homophone_sections:
    groups = re.findall(r"[a-zA-Z']+(?:\s*[\(（][^)）]+[\)）])?(?:\s*[-—]+\s*[a-zA-Z']+(?:\s*[\(（][^)）]+[\)）])?)+", sec)
    for g in groups:
        words = re.split(r'\s*[-—]+\s*', g)
        words = [re.sub(r'[\(（][^)）]+[\)）]', '', w).strip() for w in words if w.strip()]
        words = [w for w in words if len(w) > 1 or (len(w) == 1 and w.lower() in ('i', 'a'))]
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                add(words[i], '同音词', words[j])

# 2. 近义词 - 先手动修复原文中的格式问题，再逐行解析
synonym_sections = re.findall(r'近义词(.+?)(?=同音词|反义词|对应词|词形|$)', text, re.DOTALL)
for sec in synonym_sections:
    # 修复原文中缺少分隔符的词对
    sec = sec.replace('airplane learn', 'airplane  learn')
    sec = sec.replace('study beautiful', 'study  beautiful')
    # 短语用下划线连接，防止被空格拆分
    sec = sec.replace('near—beside—near to', 'near—beside—near_to')
    sec = sec.replace('near--beside--near to', 'near--beside--near_to')
    sec = sec.replace('near to', 'near_to')
    sec = sec.replace('of course', 'of_course')
    sec = sec.replace('be from', 'be_from')
    sec = sec.replace('come from', 'come_from')
    sec = sec.replace('take a bus', 'take_a_bus')
    sec = sec.replace('by bus', 'by_bus')
    sec = sec.replace('would like', 'would_like')
    sec = sec.replace('go home', 'go_home')
    sec = sec.replace('come home', 'come_home')
    sec = sec.replace('a moment ago', 'a_moment_ago')
    sec = sec.replace('just now', 'just_now')
    sec = sec.replace('a lot of', 'a_lot_of')
    sec = sec.replace('lots of', 'lots_of')
    sec = sec.replace('be good at', 'be_good_at')
    sec = sec.replace('do well in', 'do_well_in')
    sec = sec.replace('take a walk', 'take_a_walk')
    sec = sec.replace('go for a walk', 'go_for_a_walk')
    sec = sec.replace('look for', 'look_for')
    sec = sec.replace('say--talk', 'say  talk')
    sec = sec.replace('say—talk', 'say  talk')

    lines = sec.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or not re.search(r'[a-zA-Z]', line):
            continue
        # 按两个以上空格分割成独立的词对/词链
        groups = re.split(r'\s{2,}', line)
        for grp in groups:
            grp = grp.strip()
            if not grp or not re.search(r'[a-zA-Z]', grp):
                continue
            # 按 -- 或 — 拆分成词链
            chain = re.split(r'\s*[-—]+\s*', grp)
            chain = [w.strip().replace('-', ' ').replace('_', ' ') for w in chain if w.strip()]
            chain = [w for w in chain if re.search(r'[a-zA-Z]', w)]
            for i in range(len(chain)):
                for j in range(i + 1, len(chain)):
                    w1 = chain[i].strip()
                    w2 = chain[j].strip()
                    if w1.lower() in ('a', 'i') or w2.lower() in ('a', 'i'):
                        continue
                    if w1.lower() == w2.lower():
                        continue
                    add(w1, '近义词', w2)

# 3. 反义词 - 详细版 (英文+中文混合格式)
antonym_sections = re.findall(r'反义词(.+?)(?=同音词|近义词|对应词|词形|$)', text, re.DOTALL)
for sec in antonym_sections:
    # 预处理多词短语
    sec = sec.replace('in front of', 'in_front_of')
    sec = sec.replace('out of', 'out_of')
    lines = sec.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or not re.search(r'[a-zA-Z]', line):
            continue
        # 处理 '/' 分隔的多个目标词 (如 start/begin)
        line = re.sub(r'([a-zA-Z_]+)/([a-zA-Z_]+)', r'\1, \2', line)
        # 按两个以上空格分割成独立词对
        groups = re.split(r'\s{2,}', line)
        for grp in groups:
            grp = grp.strip()
            if not grp or not re.search(r'[a-zA-Z]', grp):
                continue
            # 尝试匹配 "英文 中文 -- 英文 中文" 格式
            m = re.match(r'([a-zA-Z_]+)\s*[\u4e00-\u9fff，、；]*\s*[-—]+\s*([a-zA-Z_]+(?:\s*[,，]\s*[a-zA-Z_]+)*)\s*[\u4e00-\u9fff，、；]*', grp)
            if m:
                w1 = m.group(1).strip().replace('_', ' ')
                w2s = re.split(r'\s*[,，]\s*', m.group(2).strip())
                for w2 in w2s:
                    add(w1, '反义词', w2.strip().replace('_', ' '))
            else:
                parts = re.split(r'\s*[-—]+\s*', grp)
                parts = [re.sub(r'[\u4e00-\u9fff，、；].*$', '', p).strip().replace('_', ' ') for p in parts]
                parts = [p for p in parts if p and re.match(r'^[a-zA-Z]', p)]
                if len(parts) >= 2:
                    add(parts[0], '反义词', parts[1])

# 4. 对应词 -> 反义词
counterpart_sections = re.findall(r'对应词(.+?)(?=同音词|近义词|反义词|词形|$)', text, re.DOTALL)
for sec in counterpart_sections:
    pairs = re.findall(r"([a-zA-Z']+)\s*[-—]+\s*([a-zA-Z']+)", sec)
    for w1, w2 in pairs:
        add(w1, '反义词', w2)

# 5. 不规则动词过去式 -> 词形变化
verb_sections = re.findall(r'不规则动词(.+?)(?=复数|不可数|同音词|近义词|反义词|$)', text, re.DOTALL)
verb_words = set()
for sec in verb_sections:
    pairs = re.findall(r'([a-zA-Z]+)\s*[\(（][a-zA-Z\s]+[\)）]?\s*[-—]+\s*([a-zA-Z]+)', sec)
    for w1, w2 in pairs:
        verb_words.add(w1.lower())
        verb_words.add(w2.lower())
        add(w1, '词形变化', w2)
    pairs2 = re.findall(r'([a-zA-Z]+)\s*[-—]+\s*([a-zA-Z]+)', sec)
    for w1, w2 in pairs2:
        if w1.lower() != w2.lower():
            verb_words.add(w1.lower())
            verb_words.add(w2.lower())
            add(w1, '词形变化', w2)

# 6. 复数形式 -> 词形变化
plural_sections = re.findall(r'复数形式(.+?)(?=不可数|不规则|同音词|近义词|反义词|$)', text, re.DOTALL)
plural_words = set()
for sec in plural_sections:
    pairs = re.findall(r'([a-zA-Z]+)\s*[-—]+\s*([a-zA-Z]+)', sec)
    for w1, w2 in pairs:
        plural_words.add(w1.lower())
        plural_words.add(w2.lower())
        add(w1, '词形变化', w2)

# 修正：不规则动词和复数的配对不应是反义词，移除错误分类
form_change_pairs = set()
for r in rows:
    if r[1] == '词形变化':
        form_change_pairs.add((r[0].lower(), r[2].lower()))
rows = [r for r in rows if not (r[1] == '反义词' and (r[0].lower(), r[2].lower()) in form_change_pairs)]

# 7. 词形转换
transform_section = re.findall(r'词形转换(.+?)$', text, re.DOTALL)
for sec in transform_section:
    lines = sec.strip().split('\n')
    for line in lines:
        line = line.strip()
        m = re.match(r'\d+\.?\s*([a-zA-Z]+)\s*[（(](.+?)[）)]\s*([a-zA-Z]+)', line)
        if m:
            w1, rtype, w2 = m.group(1), m.group(2), m.group(3)
            rtype = rtype.strip()
            if rtype == '反义词':
                add(w1, '反义词', w2)
            elif rtype == '同音词':
                add(w1, '同音词', w2)
            elif rtype in ('三单', '复数', '现代分词', '副词', '形容词', '序数词', '过去式'):
                add(w1, '词形变化', w2)
            elif rtype == '近义词':
                add(w1, '近义词', w2)

# 后处理：移除明显错误的数据
rows = [r for r in rows if not (
    r[1] == '反义词' and r[0].lower() == r[2].lower()
)]
rows = [r for r in rows if not (
    r[1] == '反义词' and r[0] == 'behind' and r[2] == 'in'
)]

with open(r'd:\MyProjects\Moring_Read\danci\relations.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['原词', '关系类型', '目标词'])
    writer.writerows(rows)

print(f'生成 {len(rows)} 条关系记录')
c = Counter(r[1] for r in rows)
for k, v in c.most_common():
    print(f'  {k}: {v} 条')
