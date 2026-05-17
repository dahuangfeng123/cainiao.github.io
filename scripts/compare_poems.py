import json
import re
import os

# 读取shici.json
with open(os.path.join(os.path.dirname(__file__), '..', 'shici', 'shici.json'), 'r', encoding='utf-8') as f:
    json_poems = json.load(f)
json_titles = set()
for p in json_poems:
    key = (p['title'], p.get('author', ''))
    json_titles.add(key)

# 解析shici.txt
txt_titles = set()
with open(os.path.join(os.path.dirname(__file__), '..', 'shici', 'shici.txt'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('第') and '部分' in line:
            continue
        if not line:
            continue
        match = re.match(r'^(.+?)（(.+?)）$', line)
        if match:
            title, author = match.groups()
        else:
            title, author = line, ''
        txt_titles.add((title.strip(), author.strip()))

# 对比
txt_only = txt_titles - json_titles
json_only = json_titles - txt_titles

print(f'shici.json诗词数: {len(json_titles)}')
print(f'shici.txt诗词数: {len(txt_titles)}')
print()
print('=' * 50)
print(f'shici.txt中有但shici.json没有的诗词 ({len(txt_only)} 首):')
for title, author in sorted(txt_only):
    if author:
        print(f'  {title}（{author}）')
    else:
        print(f'  {title}')
print()
print('=' * 50)
print(f'shici.json中有但shici.txt没有的诗词 ({len(json_only)} 首):')
for title, author in sorted(json_only):
    if author:
        print(f'  {title}（{author}）')
    else:
        print(f'  {title}')