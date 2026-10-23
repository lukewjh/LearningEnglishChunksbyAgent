"""Import the source without changing it; refuse to overwrite learning state."""
import csv
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = next(ROOT.glob('*.txt'))
TARGET = ROOT / '表达库.csv'


def clean(text):
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].replace('""', '"')
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', text))).strip()


def cjk(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def main():
    if TARGET.exists():
        raise SystemExit('表达库已存在，停止导入，避免覆盖学习记录。')
    pairs = {}
    canonical = {}
    invalid = []
    count = 0
    for number, line in enumerate(SOURCE.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        count += 1
        parts = line.split('\t', 1)
        if len(parts) != 2:
            invalid.append(number)
            continue
        a, b = map(clean, parts)
        en, zh = (a, b) if cjk(a) <= cjk(b) else (b, a)
        key = canonical.setdefault(tuple(sorted((a, b))), (en, zh))
        pairs.setdefault(key, []).append(number)

    translations = {}
    for en, zh in pairs:
        translations.setdefault(en.casefold(), set()).add(zh)
    fields = ['ID', '原文表达', '原文释义', '建议表达', '建议释义', '主题', '适用场景',
              '材料审核', '审核说明', '是否学过', '掌握状态', '首次学习', '最近练习',
              '练习次数', '独立成功次数', '下次复习', '当前复习间隔天', '个人例句', '常见错误', '记录链接', '来源行号']
    rows = []
    for index, ((en, zh), lines) in enumerate(pairs.items(), 1):
        row = dict.fromkeys(fields, '')
        notes = []
        if not cjk(zh):
            notes.append('原文为英文同义表达，中文释义需补充')
        if len(translations[en.casefold()]) > 1:
            notes.append('同一英文存在多种释义，使用前核对')
        if en.casefold() == 'vandalism' and zh == '受审':
            notes.append('明确错配：vandalism 指故意毁坏财物；受审为 stand trial。此条停用')
        row.update({'ID': f'E{index:04d}', '原文表达': en, '原文释义': zh,
                    '主题': '待分类', '适用场景': '待审核',
                    '材料审核': '停用' if '此条停用' in ';'.join(notes) else '待审核',
                    '审核说明': '；'.join(notes), '是否学过': '否', '掌握状态': '未学',
                    '练习次数': '0', '独立成功次数': '0',
                    '来源行号': ','.join(map(str, lines))})
        rows.append(row)
    with TARGET.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = {'source': SOURCE.name, 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'data_rows': count, 'normalized_pairs': len(rows), 'invalid_lines': invalid,
              'multiple_translation_entries': sum(bool(r['审核说明']) for r in rows),
              'disabled_entries': sum(r['材料审核'] == '停用' for r in rows)}
    (ROOT / '材料导入报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
