"""Extract page-preserving Markdown and an answer-free practice index."""
import hashlib
import json
import re
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '题库/speaking/2026年9-12月口语题库'
OUT = BASE / 'Markdown'


def read_pages(path):
    return [(page.extract_text() or '').strip() for page in PdfReader(path).pages]


def parse_topics(pages):
    topics = []
    current = None
    section = '新题'
    part = 1
    mode = 'questions'
    variant = ''
    orphan = []
    for page, text in enumerate(pages, 1):
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line == '---':
                continue  # Source section separator, not part of a question.
            if line == 'Part 1':
                continue
            if line == 'Part1 万年老题':
                section = '万年老题'
                continue
            if line == 'Part2 & Part3':
                part = 2
                current = None
                continue
            if line in ('Part2 本季新题', '新题（10 道）'):
                section = '新题'
                continue
            if line in ('Part2 保留题', '保留题（16 道）'):
                section = '保留题'
                continue
            if line in ('**Part2**', '**Part3**'):
                mode = 'cue' if line == '**Part2**' else 'questions'
                continue
            if line in ('学生版', '工作版') and current is not None:
                variant = line
                continue
            numbered = re.match(r'^(\d+)\s*[.．、]\s*(.+)$', line)
            heading = False
            if numbered:
                tail = numbered[2]
                if part == 2:
                    heading = bool(re.search(r'[\u4e00-\u9fff]', tail))
                else:
                    heading = not re.match(r'(?i)^(do|did|does|is|are|was|were|have|has|had|can|could|would|will|should|what|when|where|which|who|why|how|please)\b', tail) and '?' not in tail
            if heading:
                variant = ''
                code = {'新题': 'N', '保留题': 'R', '万年老题': 'C'}[section]
                current = {'id': f'S26-P{part}-{code}{int(numbered[1]):02d}',
                           'part': part, 'section': section, 'topic': numbered[2],
                           'start_page': page, 'end_page': page, 'cue_lines': [], 'questions': []}
                topics.append(current)
                mode = 'questions' if part == 1 else 'cue'
                continue
            if current is None:
                if page != 1:
                    orphan.append({'page': page, 'text': line})
                continue
            current['end_page'] = page
            if mode == 'cue':
                # Preserve cue-point boundaries; join only wrapped continuations.
                if line.startswith(('-', 'You should say:', 'And explain', 'Describe')) or not current['cue_lines']:
                    current['cue_lines'].append(line)
                else:
                    current['cue_lines'][-1] += ' ' + line
            elif numbered:
                qpart = 1 if part == 1 else 3
                suffix = {'学生版': '-S', '工作版': '-W', '': ''}[variant]
                qid = current['id'].replace(f'-P{part}-', f'-P{qpart}-') + suffix + f'-Q{int(numbered[1]):02d}'
                current['questions'].append({'id': qid, 'number': int(numbered[1]),
                                            'text': numbered[2], 'variant': variant, 'start_page': page, 'end_page': page})
            elif current['questions']:
                current['questions'][-1]['text'] += ' ' + line
                current['questions'][-1]['end_page'] = page
            else:
                orphan.append({'page': page, 'text': line})
    assert not orphan, f'Unassigned text: {orphan}'
    return topics


def main():
    OUT.mkdir(exist_ok=True)
    reports = []
    question_pages = None
    for source in sorted(BASE.glob('*.pdf')):
        pages = read_pages(source)
        if '纯题目' in source.name:
            name = '口语题库-纯题目-逐页.md'
            question_pages = pages
        elif 'Part1' in source.name:
            name = '口语Part1-题目与参考答案-逐页.md'
        else:
            name = '口语Part2及Part3-题目与参考答案-逐页.md'
        content = [f'# {source.name.removesuffix(".pdf.pdf")}', '',
                   f'来源：[{source.name}](../{source.name})；共{len(pages)}页。', '',
                   '本文件按PDF物理页码保留正文与换行，便于回查。保留原文措辞，不自动纠正题目或参考答案；答案仅供参考。', '']
        for number, text in enumerate(pages, 1):
            content += [f'## PDF第{number}页', '', text.replace('\n', '  \n') if text else '> 本页无可提取文字，需查看原PDF。', '']
        target = OUT / name
        target.write_text('\n'.join(content), encoding='utf-8')
        # Verify extraction losslessly modulo Markdown hard line breaks.
        extracted = target.read_text(encoding='utf-8')
        assert len(re.findall(r'^## PDF第\d+页$', extracted, re.M)) == len(pages)
        for text in pages:
            assert not text or text.replace('\n', '  \n') in extracted
        reports.append({'source': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'pages': len(pages), 'empty_pages': [i for i, t in enumerate(pages, 1) if not t],
                        'replacement_character_pages': [i for i, t in enumerate(pages, 1) if '\ufffd' in t],
                        'markdown': name})
    assert question_pages is not None
    topics = parse_topics(question_pages)
    ids = [t['id'] for t in topics] + [q['id'] for t in topics for q in t['questions']]
    assert len(ids) == len(set(ids))
    assert sum(t['part'] == 1 for t in topics) == 31
    assert sum(t['part'] == 2 for t in topics) == 54
    for topic in topics:
        assert topic['questions']
        for variant in {q['variant'] for q in topic['questions']}:
            subset = [q for q in topic['questions'] if q['variant'] == variant]
            assert [q['number'] for q in subset] == list(range(1, len(subset) + 1)), topic
        if topic['part'] == 2:
            assert topic['cue_lines'][0].startswith('Describe'), topic
            assert any('You should say:' in l for l in topic['cue_lines']), topic
    data = {'source': next(r['source'] for r in reports if '纯题目' in r['source']),
            'note': '题目原文不代表已纠错；题目ID用于练习记录，题库标签沿用材料，非官方覆盖保证。', 'topics': topics}
    warnings = {
        'S26-P1-R01-Q01': '原题语法疑点：缺少表示听音乐的动词；出题时注明原文并给出修正，不按错句教学。',
        'S26-P3-N10-Q01': '原材料该条仅为陈述句，可能缺少提问部分；保留溯源，暂停选作练习题。',
    }
    for topic in topics:
        for q in topic['questions']:
            if q['id'] in warnings:
                q['review_note'] = warnings[q['id']]
                q['selectable'] = q['id'] != 'S26-P3-N10-Q01'
    (OUT / '练习题目索引.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sections = []
    counts = {'Part1话题': 31, 'Part1问题': 0, 'Part2题卡': 54, 'Part3问题': 0}
    for part, label in [(1, 'Part 1'), (2, 'Part 2 与 Part 3')]:
        sections += [f'## {label}', '']
        for topic in (t for t in topics if t['part'] == part):
            sections += [f'### {topic["id"]}｜{topic["section"]}｜{topic["topic"]}', '',
                         f'来源：纯题目版PDF第{topic["start_page"]}—{topic["end_page"]}页。', '']
            if part == 2:
                sections += ['#### Part 2 题卡', '']
                for cue in topic['cue_lines']:
                    sections += [cue, '']
                sections += ['#### Part 3 追问', '']
            previous_variant = ''
            for q in topic['questions']:
                if q['variant'] and q['variant'] != previous_variant:
                    sections += ['', f'#### {q["variant"]}', '']
                previous_variant = q['variant']
                sections += [f'- **{q["id"]}** {q["text"]}（PDF第{q["start_page"]}' + (f'—{q["end_page"]}' if q['end_page'] != q['start_page'] else '') + '页）']
                if 'review_note' in q:
                    sections += ['', f'> 核对标记：{q["review_note"]}', '']
            sections += ['']
            counts['Part1问题' if part == 1 else 'Part3问题'] += len(topic['questions'])
    (OUT / '口语练习题库.md').write_text('\n'.join(['# 2026年9—12月口语练习题库', '',
        '来源：同目录上一级纯题目PDF。按话题重组并合并跨页折行；题目措辞保留原文，原文问题不静默修正。答案不混入此文件。', '',
        '新题、保留题等为来源材料的分类。练习记录使用题目ID及PDF页码；抽取结果未将任何题目标记为已练。', '',
        '例如原题 “Do you prefer to sad or happy music?” 存在语法疑点，教学时明确注明原题与建议修正。', ''] + sections), encoding='utf-8')
    report = {'files': reports, 'counts': counts, 'known_source_issues': warnings,
              'checks': ['逐页文本完整保留', '没有无归属正文', '题目ID唯一', '每话题问题编号连续', 'Part2题卡含Describe及You should say'],
              'visual_review': '抽查纯题目第2、18、36、67页及两份答案版第3页；未逐字校对564页原文的语言质量。'}
    (OUT / '转换核对报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
