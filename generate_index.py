# generate_index.py
import re
import json
from html.parser import HTMLParser
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTFILE = Path("index.json")

# Месяцы (русские, любые падежи/сокращения)
MONTHS = {
    1:  (r"янв(?:арь|аря|\.?)", "Январь"),
    2:  (r"февр?(?:аль|аля|\.?)", "Февраль"),
    3:  (r"март(?:а)?", "Март"),
    4:  (r"апрел(?:ь|я|\.?)", "Апрель"),
    5:  (r"ма[йя]", "Май"),
    6:  (r"июн(?:ь|я)", "Июнь"),
    7:  (r"июл(?:ь|я)", "Июль"),
    8:  (r"август(?:а)?", "Август"),
    9:  (r"сентябр(?:ь|я)", "Сентябрь"),
    10: (r"октябр(?:ь|я)", "Октябрь"),
    11: (r"ноябр(?:ь|я)", "Ноябрь"),
    12: (r"декабр(?:ь|я)", "Декабрь"),
}
MONTH_RX = [(num, name, re.compile(pat, re.I | re.U)) for num, (pat, name) in MONTHS.items()]

YEAR_ANYWHERE = re.compile(r"(20\d{2})")  # найдёт 2025/2026 где угодно

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = self.in_h1 = False
        self.title, self.h1, self.all = [], [], []
    def handle_starttag(self, t, a):
        t=t.lower()
        if t=="title": self.in_title=True
        if t=="h1":    self.in_h1=True
    def handle_endtag(self, t):
        t=t.lower()
        if t=="title": self.in_title=False
        if t=="h1":    self.in_h1=False
    def handle_data(self, d):
        s=d.strip()
        if not s: return
        self.all.append(s)
        if self.in_title: self.title.append(s)
        if self.in_h1:    self.h1.append(s)

def employee_from_stem(stem: str) -> str:
    # "ФИО - Отчет ..." → "ФИО" (любой дефис: -, – или —)
    import re
    parts = re.split(r"\s*[-–—]\s*", stem, maxsplit=1)
    return parts[0].strip()

def month_year_from_stem(stem: str):
    # Ищем месяц + год прямо в имени файла (без .html)
    mnum = mname = year = None
    for num, name, rx in MONTH_RX:
        if rx.search(stem):
            mnum, mname = num, name
            break
    y = YEAR_ANYWHERE.search(stem)
    if y:
        year = int(y.group(1))
    return mnum, mname, year

def month_year_from_html(text: str):
    # meta приоритетнее всего
    meta = re.search(r'<meta\s+name=["\']report-month["\']\s+content=["\'](\d{4})-(\d{2})["\']', text, re.I)
    if meta:
        y, m = int(meta.group(1)), int(meta.group(2))
        return m, MONTHS[m][1], y

    p = P(); p.feed(text); blob = " ".join(p.all)

    mnum = mname = year = None
    for num, name, rx in MONTH_RX:
        m = rx.search(blob)
        if m:
            mnum, mname = num, name
            # год ищем рядом, а если нет — везде
            window = blob[max(0, m.start()-40): m.end()+40]
            y = YEAR_ANYWHERE.search(window) or YEAR_ANYWHERE.search(blob)
            if y:
                year = int(y.group(1))
            break
    return mnum, mname, year

def main():
    items = []
    for path in sorted(REPORTS_DIR.glob("*.html")):
        stem = path.stem  # без .html
        name = employee_from_stem(stem)

        # 1) сначала из имени файла
        m, mname, y = month_year_from_stem(stem)

        # 2) если чего-то не хватает — смотрим HTML
        if m is None or mname is None or y is None:
            html = path.read_text(encoding="utf-8", errors="ignore")
            m2, mname2, y2 = month_year_from_html(html)
            m = m if m is not None else m2
            mname = mname if mname is not None else mname2
            y = y if y is not None else y2

        items.append({
            "name": name,
            "url": f"reports/{path.name}",
            "month": m,
            "month_name": mname,
            "year": y
        })

        # Диагностика в логах
        print(f"[OK] {path.name} -> name='{name}', month='{mname or '?'}', year={y or 'None'}")

    OUTFILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    years = sorted({it["year"] for it in items if it.get("year")}, reverse=True)
    print(f"Wrote {OUTFILE} with {len(items)} entries. YEARS FOUND: {years}")

if __name__ == "__main__":
    main()
