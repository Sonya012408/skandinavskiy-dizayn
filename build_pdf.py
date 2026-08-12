# -*- coding: utf-8 -*-
"""Сборка PDF: рендер Chrome -> карта страниц -> номера в содержании -> колонтитулы -> закладки."""
import io, os, re, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
import fitz, pypdf
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HERE   = os.path.dirname(os.path.abspath(__file__))
SRC    = os.path.join(HERE, "print.html")
BASE   = os.path.join(HERE, "base.pdf")
OUT    = os.path.join(HERE, "skandinavskiy-dizayn.pdf")
URL    = "file:///" + SRC.replace("\\", "/").replace(" ", "%20")

def render():
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", "--virtual-time-budget=30000",
                    "--run-all-compositor-stages-before-draw",
                    "--print-to-pdf=" + BASE, URL],
                   capture_output=True, timeout=300)
    return fitz.open(BASE)

def flat(s):            # убираем пробелы: letter-spacing рвёт слова при извлечении
    return re.sub(r"\s+", "", s).casefold()

def page_texts(doc):
    return [flat(p.get_text()) for p in doc]

# ---------- 1. первый проход: где что лежит ----------
doc = render()
texts = page_texts(doc)
n = doc.page_count
src = open(SRC, encoding="utf-8").read()
anchors = re.findall(r'data-toc="([^"]+)"', src)

toc_page = next(i for i, t in enumerate(texts) if "содержание" in t)   # 0-based
mapping = {}
for a in anchors:
    k = flat(a)
    hit = next((i + 1 for i, t in enumerate(texts) if i > toc_page and k in t), None)
    if hit is None:
        sys.exit("не найден якорь: " + a)
    mapping[a] = hit

src = re.sub(r'<span class="p" data-toc="([^"]+)">[^<]*</span>',
             lambda m: '<span class="p" data-toc="%s">%d</span>' % (m.group(1), mapping[m.group(1)]),
             src)
open(SRC, "w", encoding="utf-8").write(src)
doc.close()

# ---------- 2. второй проход: финальная вёрстка ----------
doc = render()
texts = page_texts(doc)
n = doc.page_count

MARKS = [("содержание", "Содержание"), ("пролог", "Пролог"),
         ("случайизпрактики", "Часть I · Случаи из практики"),
         ("предмет-эталон", "Часть II · Предметы-эталоны"),
         ("частьiii·устройство", "Часть III · Устройство"),
         ("частьiv·первоисточник", "Часть IV · Первоисточник"),
         ("приложение", "Приложения"), ("колофон", "Колофон")]
running, cur = [], ""
for t in texts:
    for key, label in MARKS:
        if t.startswith(key) or t[:60].find(key) != -1:
            cur = label
            break
    running.append(cur)

# ---------- 3. колонтитулы ----------
pdfmetrics.registerFont(TTFont("GeoB", r"C:\Windows\Fonts\georgiab.ttf"))
pdfmetrics.registerFont(TTFont("Seg",  r"C:\Windows\Fonts\segoeui.ttf"))
W, H = A4; M = 51.0
buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
for p in range(1, n + 1):
    if p > 2:
        c.setStrokeColor(HexColor("#D9D1BF")); c.setLineWidth(.4); c.line(M, 52, W - M, 52)
        c.setFillColor(HexColor("#8B8E80")); c.setFont("Seg", 6.6)
        c.drawString(M, 40, running[p - 1].upper())
        c.setFont("GeoB", 9.5); c.setFillColor(HexColor("#4F5F3A"))
        c.drawRightString(W - M, 39, str(p))
    c.showPage()
c.save(); buf.seek(0)

reader = pypdf.PdfReader(BASE); ov = pypdf.PdfReader(buf); w = pypdf.PdfWriter()
for i, pg in enumerate(reader.pages):
    pg.merge_page(ov.pages[i]); w.add_page(pg)
tmp = os.path.join(HERE, "_stamped.pdf")
with open(tmp, "wb") as f: w.write(f)

# ---------- 4. закладки, метаданные, сжатие ----------
d = fitz.open(tmp)
LBL = {"Детская ванная":"01 · Детская ванная","Обеденные стулья":"02 · Обеденные стулья",
 "Акцентная стена":"03 · Акцентная стена","Наследство":"04 · Наследство",
 "Выбор палитры":"05 · Выбор палитры","Вечерние посиделки":"06 · Вечерние посиделки",
 "Wishbone Ханса Вегнера":"07 · Wishbone Вегнера","PH-лампа Поуля":"08 · PH-лампа",
 "Savoy Алвара Аалто":"09 · Ваза Savoy","Бруно Матссон и физика":"10 · Бруно Матссон",
 "Morris":"11 · Morris & Co","Julstjärna":"12 · Julstjärna","Два белых":"Два белых",
 "Почему диммер":"Свет","вынести всего одно понятие":"Средняя линия интерьера",
 "Почему 50/50":"Пропорция 80/20","Эллен Кей":"Эллен Кей",
 "Карин и Карл Ларссоны":"Карин и Карл Ларссоны","Не пыль":"Не пыль решает",
 "Девять сквозных правил":"Девять правил","сегодня вечером":"Что сделать вечером",
 "Числовые ориентиры":"Числовые ориентиры","Источники и лицензии":"Источники и лицензии"}
toc = [[1, "Обложка", 1], [1, "Содержание", toc_page + 1], [1, "Пролог", toc_page + 2]]
for a in anchors:
    toc.append([2, LBL.get(a, a), mapping[a]])
toc = [r for r in toc if 1 <= r[2] <= n]
d.set_toc(toc)
d.set_metadata({"title": "Скандинавский дизайн — разбор книги Кати Карлинг",
                "author": "Разбор книги Кати Карлинг «Скандинавский дизайн»",
                "subject": "12 кейсов, числовые ориентиры, источники",
                "keywords": "скандинавский дизайн, интерьер, Карлинг, стокгольмский белый"})
d.save(OUT, garbage=4, deflate=True); d.close()
os.remove(tmp)

d = fitz.open(OUT)
print("страниц:", d.page_count, "| закладок:", len(d.get_toc()),
      "| размер:", round(os.path.getsize(OUT) / 1048576, 1), "МБ")
for a in anchors: print("  %-30s %s" % (a[:30], mapping[a]))
