# generate_index.py
import re
import json
from html.parser import HTMLParser
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTFILE = Path("index.json")

# Русские месяцы (любые падежи/варианты)
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
YEAR_RX = re.compile(r"(20\d{2})")

# --- HTML парсер для title/h1 ---
class SimpleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.title, self.h1 = [], []
        self.all_text = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "title": self.in_title = True
        if t == "h1":    self.in_h1 = True

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "title": self.in_title = False
        if t == "h1":    self.in_h1 = False

    def handle_data(self, data):
        s = data.strip()
        if not s: return
        self.all_text.append(s)
        if self.in_title: self.title.append(s)
        if self.in_h1:    self.h1.append(s)

# --- Вспомогательные функции ---
def split_name_from_filename(stem: str) -> str:
    """
    'Анашкина Ольга - Отчёт за Июль 2025' → 'Анашкина Ольга'
    Разделители: -, – (en dash), — (em dash)
    """
    parts = re.split(r"\s*[-–—]\s*", stem, maxsplit=1)
    return parts[0].strip()

def extract_month_year_from_filename(stem: str):
    """
    Ищем месяц и год в имени файла (без .html).
    Примеры:
      '... Отчёт за Июль 2025' → (7, 'Июль', 2025)
      '... Отчёт за Июль'      → (7, 'Июль', None)
    """
    # месяц
    month_num = None
    month_name = None
    for num, ru_name, rx in MONTH_RX:
        m = rx.search(stem)
        if m:
            month_num = num
            month_name = ru_name
            # ищем год рядом (или вообще в строке)
            after = stem[m.end(): m.end() + 40]
            ym = YEAR_RX.search(after) or YEAR_RX.search(stem)
            year = int(ym.group(1)) if ym else None
            return month_num, month_name, year
    # если месяц не нашли — None
    return None, None, None

def extract_from_html(html: str):
    """
    Пытаемся вытащить месяц/год из meta/title/h1.
    """
    # <meta name="report-month" content="YYYY-MM">
    meta = re.search(r'<meta\s+name=["\']report-month["\']\s+content=["\'](\d{4})-(\d{2})["\']', html, re.I)
    if meta:
        y, m = int(meta.group(1)), int(meta.group(2))
        return m, MONTHS[m][1], y

    p = SimpleParser()
    p.feed(html)
    blob = " ".join(p.all_text)

    # месяц
    for num, ru_name, rx in MONTH_RX:
        m = rx.search(blob)
        if m:
            # год ищем рядом
            window = blob[max(0, m.start()-40): m.end()+40]
            ym = YEAR_RX.search(window)
            y = int(ym.group(1)) if ym else None
            return num, ru_name, y
    return None, None, None

# --- Основной генератор ---
def main():
    items = []
    for html_path in sorted(REPORTS_DIR.glob("*.html")):
        stem = html_path.stem  # имя без .html

        # Имя сотрудника — до первого дефиса
        name = split_name_from_filename(stem)
        name = re.sub(r"\s+", " ", name).strip()

        # 1) Сначала пробуем вытащить месяц/год из ИМЕНИ файла
        m, mname, y = extract_month_year_from_filename(stem)

        # 2) Если не получилось — читаем HTML и ищем там
        if m is None or mname is None:
            text = html_path.read_text(encoding="utf-8", errors="ignore")
            m2, mname2, y2 = extract_from_html(text)
            m = m if m is not None else m2
            mname = mname if mname is not None else mname2
            y = y if y is not None else y2

        items.append({
            "name": name,
            "url": f"reports/{html_path.name}",
            "month": m,
            "month_name": mname,
            "year": y
        })

    OUTFILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTFILE} with {len(items)} entries")

if __name__ == "__main__":
    main()
