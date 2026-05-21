#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRT 字幕解析脚本
将本地 SRT 文件解析成 DEFAULT_ARTICLES 格式
使用方法：python parse_srt.py <srt文件目录> <输出文件>
"""

import os
import re
import sys

def parse_srt(srt_path):
    """
    解析 SRT 文件，提取台词文本
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(srt_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except:
            continue
    else:
        print(f"无法读取文件: {srt_path}")
        return []
    
    # SRT 格式: 序号 -> 时间码 -> 文本 -> 空行
    pattern = re.compile(r'\d+\n[\d:,]+\s*-->\s*[\d:,]+\n([\s\S]*?)(?=\n\n|\n\d+\n|$)')
    matches = pattern.findall(content)
    
    lines = []
    for match in matches:
        # 去除 HTML 标签和多余空格
        text = re.sub(r'<[^>]+>', '', match)
        text = re.sub(r'\s+', ' ', text).strip()
        # 只保留英文台词（过滤纯数字、特殊字符等）
        if text and re.search(r'[a-zA-Z]', text):
            lines.append(text)
    
    return lines

def extract_words(lines, max_words=10):
    """
    从台词中提取关键词
    """
    word_counts = {}
    
    for line in lines:
        # 提取单词
        words = re.findall(r'[a-zA-Z]+', line.lower())
        for word in words:
            # 过滤短词和常见词
            if len(word) >= 3 and word not in {'the', 'and', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                                              'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                                              'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
                                              'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                                              'from', 'as', 'into', 'through', 'during', 'before', 'after',
                                              'above', 'below', 'between', 'under', 'again', 'further', 'then',
                                              'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
                                              'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
                                              'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
                                              'just', 'but', 'if', 'or', 'because', 'until', 'while', 'this',
                                              'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
                                              'they', 'what', 'which', 'who', 'whom', 'me', 'him', 'her', 'us',
                                              'them', 'my', 'your', 'his', 'its', 'our', 'their'}:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    # 按频率排序，取前 max_words 个
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    top_words = [word for word, count in sorted_words[:max_words]]
    
    return ','.join(top_words)

def main():
    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python parse_srt.py <srt文件目录> <输出文件>")
        print("  python parse_srt.py ./srt_files output.js")
        sys.exit(1)
    
    srt_dir = sys.argv[1]
    output_file = sys.argv[2]
    
    # 查找所有 SRT 文件
    srt_files = []
    for root, dirs, files in os.walk(srt_dir):
        for f in files:
            if f.lower().endswith('.srt'):
                srt_files.append(os.path.join(root, f))
    
    if not srt_files:
        print(f"在 {srt_dir} 中未找到 SRT 文件")
        sys.exit(1)
    
    print(f"找到 {len(srt_files)} 个 SRT 文件")
    
    articles = []
    start_id = 1
    
    # 手动输入标题和分类
    title = input("请输入标题（如：辛普森一家 第三十七季）: ")
    category = input("请输入分类（如：辛普森一家）: ")
    
    for idx, srt_file in enumerate(srt_files):
        print(f"\n处理: {os.path.basename(srt_file)}")
        
        lines = parse_srt(srt_file)
        if not lines:
            print("  跳过（无有效台词）")
            continue
        
        # 合并台词为文本
        text = '\n'.join(lines)
        
        # 提取关键词
        words = extract_words(lines)
        
        article = {
            'id': start_id + idx,
            'title': f"{title} - Part {idx + 1}",
            'words': words,
            'category': category,
            'text': text
        }
        articles.append(article)
        
        print(f"  台词数量: {len(lines)}")
        print(f"  关键词: {words}")
    
    # 输出 JavaScript 格式
    output_content = "const DEFAULT_ARTICLES = [\n"
    for article in articles:
        escaped_text = article['text'].replace('\\', '\\\\').replace('\"', '\\"')
        output_content += f"  {{id:{article['id']},title:\"{article['title']}\",words:\"{article['words']}\",category:\"{article['category']}\",text:\"{escaped_text}\"}},\n"
    output_content += "];\n"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    print(f"\n✅ 输出完成！文件: {output_file}")
    print(f"生成文章数量: {len(articles)}")

if __name__ == '__main__':
    main()