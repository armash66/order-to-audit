"""Render the design Markdown as a two-page submission PDF (pip install reportlab pypdf)."""

from html import escape
from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


# Use an embedded TrueType font so the rupee symbol survives display and text extraction.
def fonts():
    candidates = [
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
         Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont('Design', str(regular)))
            pdfmetrics.registerFont(TTFont('DesignBold', str(bold)))
            return
    raise RuntimeError('Install Arial or DejaVu Sans before rendering.')


def render():
    fonts()
    body = ParagraphStyle('Body', fontName='Design', fontSize=9.4, leading=13.2, spaceAfter=9)
    heading = ParagraphStyle('Heading', fontName='DesignBold', fontSize=13, leading=17, spaceBefore=8, spaceAfter=8)
    title = ParagraphStyle('Title', parent=heading, fontSize=20, leading=24)
    cell = ParagraphStyle('Cell', parent=body, fontSize=8, leading=10, spaceAfter=0)
    source = (ROOT / 'docs/design.md').read_text(encoding='utf-8')
    blocks = source.split('\n\n')
    story = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith('```mermaid'):
            rows = [['Parent', 'Child', 'Relationship (1 to many unless stated)']]
            for line in block.splitlines():
                match = re.match(r'\s*(\w+)\s+(\S+)\s+(\w+)\s*:\s*(\w+)', line)
                if match:
                    parent, cardinality, child, relation = match.groups()
                    label = relation.replace('_', ' ')
                    if cardinality == '||--o|':
                        label += ' (0 or 1)'
                    rows.append([parent, child, label])
            table = Table([[Paragraph(escape(value), cell) for value in row] for row in rows], colWidths=[120, 130, 255])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e1eeeb')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8f8')]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LINEBELOW', (0, 0), (-1, 0), 0.7, colors.HexColor('#246458')),
            ]))
            story.extend([table, Spacer(1, 10)])
        elif block == '## Posting and lifecycle':
            story.extend([PageBreak(), Paragraph('Posting, quantities and valuation', heading)])
        elif block.startswith('# '):
            story.append(Paragraph(escape(block[2:]), title))
        elif block.startswith('## '):
            story.append(Paragraph(escape(block[3:]), heading))
        else:
            story.append(Paragraph(escape(block.replace('`', '').replace('\n', ' ')), body))
    output = ROOT / 'output/pdf/design-note.pdf'
    output.parent.mkdir(parents=True, exist_ok=True)

    def footer(canvas, doc):
        canvas.setFont('Design', 8)
        canvas.setFillColor(colors.HexColor('#526364'))
        canvas.drawString(45, 25, 'Order-to-Audit | CDI NIT Trichy | Design note')
        canvas.drawRightString(A4[0] - 45, 25, str(doc.page))

    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=45, rightMargin=45,
                      topMargin=35, bottomMargin=40, title='Order-to-Audit design note',
                      author='Order-to-Audit').build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(output)
    assert len(reader.pages) == 2, f'Design note must be two pages, got {len(reader.pages)}'
    assert '₹43.125/kg' in '\n'.join(page.extract_text() for page in reader.pages)
    print(f'PASS: {output} (2 pages, embedded rupee glyph)')


if __name__ == '__main__':
    render()
