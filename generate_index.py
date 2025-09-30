# generate_index.py
import re
import json
from html.parser import HTMLParser
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTFILE = Path("index.json")

# Карта русских месяцев: разные падежи и общие опечатки
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

# Скомпилируем паттерн с именованными группами: (?P<m7>июль|июля|…)
MONTH_COMPILED = []
for num, (pat, name) in MONTHS.items():
    MONTH_COMPILED.append((num, name, re.compile(pat, re.I | re.U)))

YEAR_RE = re.compile(r"(20\d{2})")

class SimpleTitleH1Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.title_text = []
        self.h1_text = []
        self.all_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "h1":
            self.in_h1 = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() == "h1":
            self.in_h1 = False

    def handle_data(self, data):
        s = data.strip()
        if not s:
            return
        self.all_text.append(s)
        if self.in_title:
            self.title_text.append(s)
        if self.in_h1:
            self.h1_text.append(s)

def extract_name_from_html(text: str) -> str | None:
    p = SimpleTitleH1Parser()
    p.feed(text)
    title = " ".join(p.title_text).strip()
    if title:
        # Пробуем забрать имя из конца тайтла: "Отчет ...: Фамилия Имя"
        m = re.search(r"[:\-–]\s*([А-ЯA-ZЁ][^|<>()]{2,})$", title)
        if m:
            return m.group(1).strip()
        return title
    h1 = " ".join(p.h1_text).strip()
    if h1:
        return h1
    return None

def extract_month_year(text: str) -> tuple[int | None, int | None, str | None]:
    """
    Ищем месяц (в любых русских формах) и ближайший год.
    Возвращаем (month_num, year, month_pretty).
    """
    # Сначала ищем в <meta name="report-month" content="YYYY-MM">
    meta = re.search(r'<meta\s+name=["\']report-month["\']\s+content=["\'](\d{4})-(\d{2})["\']', text, re.I)
    if meta:
        y, m = int(meta.group(1)), int(meta.group(2))
        pretty = MONTHS.get(m, (None, None))[1]
        return (m, y, pretty)

    # Иначе ищем по видимому тексту
    p = SimpleTitleH1Parser()
    p.feed(text)
    blob = " ".join(p.all_text)

    found_month = None
    found_month_name = None
    pos = None
    for num, name, rx in MONTH_COMPILED:
        m = rx.search(blob)
        if m:
            found_month = num
            found_month_name = name
            pos = m.start()
            break

    if found_month is None:
        return (None, None, None)

    # Пытаемся найти год рядом (±40 символов)
    window_start = max(0, pos - 40)
    window_end = min(len(blob), pos + 40)
    around = blob[window_start:window_end]
    ym = YEAR_RE.search(around)
    year = int(ym.group(1)) if ym else None

    return (found_month, year, found_month_name)

def humanize_from_filename(path: Path) -> str:
    stem = path.stem
    parts = re.split(r"[_\-\.]+", stem)
    return " ".join(s.capitalize() for s in parts if s)

def main():
    items = []
    for html_path in sorted(REPORTS_DIR.glob("*.html")):
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        name = extract_name_from_html(text) or humanize_from_filename(html_path)
        name = re.sub(r"\s+", " ", name).strip()

        month, year, month_name = extract_month_year(text)

        items.append({
            "name": name,
            "url": f"reports/{html_path.name}",
            "month": month,              # 1..12 или null
            "month_name": month_name,    # "Июль" или null
            "year": year                 # 2025 или null
        })

    OUTFILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTFILE} with {len(items)} entries")

if __name__ == "__main__":
    main()
