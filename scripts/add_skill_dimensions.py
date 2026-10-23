"""One-time, additive migration; preserve all existing learning state."""
import csv
from pathlib import Path

path = Path(__file__).resolve().parents[1] / '表达库.csv'
with path.open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    fields = list(reader.fieldnames)
    rows = list(reader)
assert len({r['ID'] for r in rows}) == len(rows)
extra = ['阅读状态', '阅读最近练习', '阅读下次复习', '写作状态', '写作最近练习', '写作下次复习']
for field in extra:
    if field not in fields:
        fields.append(field)
for row in rows:
    row.setdefault('阅读状态', '未测')
    row.setdefault('阅读最近练习', '')
    row.setdefault('阅读下次复习', '')
    row.setdefault('写作状态', row['掌握状态'])
    row.setdefault('写作最近练习', row['最近练习'])
    row.setdefault('写作下次复习', row['下次复习'])
with path.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
with path.open(encoding='utf-8-sig', newline='') as f:
    saved = list(csv.DictReader(f))
assert saved == rows
print(f'Verified {len(saved)} entries; reading and writing states stored separately.')
