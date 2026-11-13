"""Build the formatted dissertation from DISSERTATION_DRAFT.md."""

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
DRAFT = ROOT / "DISSERTATION_DRAFT.md"
DOCX = ROOT / "Final_MSc_Dissertation.docx"
FIGURES = ROOT / "FIGURES"

NAVY = (31, 78, 121)
PALE = (231, 238, 245)
LINE = (31, 78, 121)
INK = (20, 20, 20)


def font(size):
    for name in ("times.ttf", "timesbd.ttf", "arial.ttf", "calibri.ttf"):
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=fnt) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def box(draw, xy, text, fnt, fill=PALE):
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=LINE, width=2)
    x1, y1, x2, y2 = xy
    lines = wrap(draw, text, fnt, x2 - x1 - 16)
    total = len(lines) * 18
    y = y1 + (y2 - y1 - total) / 2
    for line in lines:
        w = draw.textlength(line, font=fnt)
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=INK)
        y += 18


def arrow(draw, start, end):
    draw.line([start, end], fill=NAVY, width=2)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 8, ey - 5), (ex - 8, ey + 5)], fill=NAVY)


def new_canvas():
    image = Image.new("RGB", (1400, 720), "white")
    return image, ImageDraw.Draw(image)


def save(image, name):
    FIGURES.mkdir(exist_ok=True)
    image.save(FIGURES / name, "PNG")


def draw_figures():
    fnt = font(18)
    small = font(16)

    image, draw = new_canvas()
    box(draw, (40, 250, 280, 420), "Browser\nNext.js interface", fnt)
    box(draw, (400, 180, 700, 330), "FastAPI service\nauthentication, RAG, scoring", small)
    box(draw, (820, 80, 1320, 210), "PostgreSQL and pgvector\nprofiles, documents, trials", small)
    box(draw, (820, 280, 1320, 410), "Local upload store\nPDF and text files", small)
    box(draw, (820, 480, 1320, 620), "Model provider\nchat and embeddings", small)
    arrow(draw, (280, 335), (400, 255))
    arrow(draw, (700, 230), (820, 145))
    arrow(draw, (700, 280), (820, 345))
    arrow(draw, (700, 300), (820, 520))
    save(image, "figure1-architecture.png")

    image, draw = new_canvas()
    labels = [
        (40, "Upload\nPDF or TXT"),
        (300, "Extract, chunk\nand embed"),
        (560, "Store chunks\nwith access label"),
        (820, "Search the\nallow-list"),
        (1080, "Generate,\nthen check"),
    ]
    for x, label in labels:
        box(draw, (x, 260, x + 220, 430), label, small)
    for x in (260, 520, 780, 1040):
        arrow(draw, (x, 345), (x + 40, 345))
    save(image, "figure2-rag.png")

    image, draw = new_canvas()
    steps = [
        (40, "Sign in with\nSupabase Auth"),
        (330, "Send bearer\ntoken to the API"),
        (620, "Verify token\nand load profile role"),
        (910, "Allow or deny\nthe document"),
    ]
    for x, label in steps:
        box(draw, (x, 260, x + 250, 430), label, small)
    for x in (290, 580, 870):
        arrow(draw, (x, 345), (x + 40, 345))
    save(image, "figure3-auth.png")

    image, draw = new_canvas()
    box(draw, (80, 80, 620, 180), "Baseline", fnt, fill=(255, 243, 224))
    box(draw, (80, 220, 620, 560), "System message contains the retrieved chunks and tells the model to follow the documents and the user. The answer is not redacted.", small)
    box(draw, (760, 80, 1320, 180), "Secured", fnt, fill=(226, 240, 230))
    box(draw, (760, 220, 1320, 560), "System message is a fixed trusted instruction. Retrieved chunks sit in the user message as untrusted references. Unauthorised markers are redacted.", small)
    save(image, "figure4-configs.png")

    image, draw = new_canvas()
    labels = [
        (30, "Official\ntest case"),
        (280, "Resolve the\nsynthetic actor"),
        (530, "Run baseline\nor secured"),
        (780, "Classify the\nstored observation"),
        (1030, "Keep the trial\nand the rate"),
    ]
    for x, label in labels:
        box(draw, (x, 260, x + 220, 440), label, small)
    for x in (250, 500, 750, 1000):
        arrow(draw, (x, 350), (x + 30, 350))
    save(image, "figure5-evaluation.png")


def set_run_font(run, size=12, bold=False, italic=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def style_paragraph(paragraph, *, center=False, after=8, before=0, size=12, line=1.5):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    fmt = paragraph.paragraph_format
    fmt.space_after = Pt(after)
    fmt.space_before = Pt(before)
    fmt.line_spacing = line
    for run in paragraph.runs:
        set_run_font(run, size=size)


def add_text(paragraph, text, size=12, bold=False, italic=False):
    pattern = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            set_run_font(run, size=size, bold=bold, italic=italic)
        token = match.group(0)
        run = paragraph.add_run(token[2:-2] if token.startswith("**") else token[1:-1])
        set_run_font(run, size=size, bold=bold or token.startswith("**"), italic=italic or token.startswith("*"))
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run_font(run, size=size, bold=bold, italic=italic)


def shade_cell(cell):
    tc = cell._tePr if hasattr(cell, "_tePr") else cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "1F4E79")
    shd.set(qn("w:val"), "clear")
    tc_pr.append(shd)


def add_table(document, rows):
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.autofit = True
    for r_index, row in enumerate(rows):
        for c_index, value in enumerate(row):
            cell = table.rows[r_index].cells[c_index]
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_text(paragraph, value.replace("**", ""), size=10, bold=r_index == 0)
            if r_index == 0:
                shade_cell(cell)
                for run in paragraph.runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)
    document.add_paragraph()


def add_toc(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)
    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = r' TOC \o "1-2" \h \z \u '
    run._r.append(instr)
    run = paragraph.add_run()
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_sep)
    run = paragraph.add_run("Right-click and update this field in Word if the entries are not yet filled.")
    set_run_font(run, size=12, italic=True)
    run = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_end)


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)
    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    run._r.append(instr)
    run = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_end)
    set_run_font(paragraph.runs[0], size=10)


def configure(document):
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)
    section.different_first_page_header_footer = True
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header.add_run("Security controls in a RAG web application")
    set_run_font(run, size=10, italic=True)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_number(footer)
    styles = document.styles
    for name, size, bold, before, after in (
        ("Heading 1", 16, True, 0, 12),
        ("Heading 2", 13, True, 12, 6),
    ):
        style = styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor(31, 78, 121)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.15
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(8)


def is_table_line(line):
    return line.startswith("|") and line.endswith("|")


def parse_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def build():
    document = Document()
    configure(document)
    lines = DRAFT.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip() or line.strip() == "---" or line.strip().startswith("<!--"):
            i += 1
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            if title.startswith("Evaluating Security"):
                p = document.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(72)
                add_text(p, title, size=20, bold=True)
                i += 1
                continue
            document.add_page_break()
            document.add_heading(title, level=1)
            i += 1
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            major = heading in {"Abstract", "Declaration", "Acknowledgements", "References"}
            if major:
                document.add_page_break()
            document.add_heading(heading, level=1 if major else 2)
            if heading == "Table of contents":
                p = document.add_paragraph()
                add_toc(p)
                while i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    i += 1
                    if lines[i].startswith("## ") or lines[i].startswith("# "):
                        i -= 1
                        break
            i += 1
            continue
        if line.startswith("### "):
            document.add_heading(line[4:].strip(), level=2)
            i += 1
            continue
        if line.startswith("!["):
            match = re.search(r"\(([^)]+)\)", line)
            if match:
                picture = ROOT / match.group(1)
                if picture.exists():
                    p = document.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.add_run().add_picture(str(picture), width=Cm(15.5))
            i += 1
            continue
        if is_table_line(line):
            rows = []
            while i < len(lines) and is_table_line(lines[i].rstrip()):
                current = lines[i].rstrip()
                if not re.match(r"^\|\s*-+", current):
                    rows.append(parse_row(current))
                i += 1
            if rows:
                width = max(len(row) for row in rows)
                rows = [row + [""] * (width - len(row)) for row in rows]
                add_table(document, rows)
            continue
        if line.startswith("- "):
            while i < len(lines) and lines[i].startswith("- "):
                p = document.add_paragraph(style=None)
                p.paragraph_format.left_indent = Cm(1)
                p.paragraph_format.line_spacing = 1.5
                add_text(p, lines[i][2:].strip(), size=12)
                i += 1
            continue
        if line.startswith("**Figure") or line.startswith("**Table"):
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            add_text(p, line, size=11, bold=True)
            i += 1
            continue
        if line.startswith("**") and line.endswith("**"):
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text(p, line, size=12)
            i += 1
            continue
        p = document.add_paragraph()
        add_text(p, line, size=12)
        style_paragraph(p)
        i += 1
    document.save(DOCX)
    print(DOCX)


if __name__ == "__main__":
    build()
