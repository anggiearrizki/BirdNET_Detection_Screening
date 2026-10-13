"""Convert a BirdNET TXT audit to an A4 report. No API calls.
Requires reportlab. On Windows, uses installed Arial fonts by default.
"""
import argparse
import html
import os
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--font-dir', type=Path, help='Directory containing arial.ttf and arialbd.ttf.')
    args = parser.parse_args()
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    except ImportError:
        parser.error('Install the PDF dependency with: python -m pip install reportlab')
    font_dir = args.font_dir or Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    regular, bold = font_dir / 'arial.ttf', font_dir / 'arialbd.ttf'
    if not regular.exists() or not bold.exists():
        parser.error('Arial fonts not found. Use --font-dir with a folder containing arial.ttf and arialbd.ttf.')
    pdfmetrics.registerFont(TTFont('AuditArial', str(regular)))
    pdfmetrics.registerFont(TTFont('AuditArialBold', str(bold)))
    raw = args.input.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    body = ParagraphStyle('Body', fontName='AuditArial', fontSize=12, leading=16,
                          alignment=TA_JUSTIFY, spaceAfter=8, textColor=colors.black)
    meta = ParagraphStyle('Metadata', parent=body, alignment=TA_LEFT, spaceAfter=8)
    heading = ParagraphStyle('Heading', parent=meta, fontName='AuditArialBold',
                             spaceBefore=14, spaceAfter=8, keepWithNext=True)
    label = ParagraphStyle('Label', parent=heading, spaceBefore=6, spaceAfter=4)
    title = ParagraphStyle('Title', parent=heading, alignment=TA_CENTER, spaceBefore=0, spaceAfter=16)
    def p(value, style=body):
        return Paragraph(html.escape(str(value)).replace('\n', '<br/>'), style)
    story = [p('BirdNET Historical Detection Review Audit', title),
             p('Source: ' + args.input.name, meta),
             p('This report preserves the saved local audit. Gemini assessments and recommendations are screening outputs for human review, not confirmed species observations. Posted status unchanged means the comment was accepted and verification status was unchanged.'),
             p('Assessment guide', heading),
             p('Consistent: the audio supports the proposed identification. Inconsistent: the audible evidence conflicts with it. Uncertain: the available audio is insufficient for a reliable assessment.')]
    blocks = re.split(r'(?m)^STATION: ', text)
    if len(blocks) == 1:
        parser.error('No STATION sections found. Supply output from birdnet_audit_reviews.py.')
    number = 0
    for block in blocks[1:]:
        station = block.splitlines()[0].strip()
        story += [PageBreak(), p(station.replace('_', ' ').title(), heading)]
        parts = re.split(r'(?m)^CANDIDATE: ', block)
        for line in parts[0].splitlines()[1:]:
            if line.strip():
                story.append(p(line.strip(), meta))
        for group in parts[1:]:
            group_title = group.splitlines()[0]
            story.append(p(group_title, heading))
            pattern = r'(?m)^(\d+) (\d{4}-\d{2}-\d{2}) (\S+) audio: (\S+) recommendation: (.*?) coordinates: (.*?)\r?\n(http[^\r\n]+)\r?\n'
            matches = list(re.finditer(pattern, group))
            if not matches:
                # Preserve unusual source formatting rather than silently discarding it.
                story.append(p('\n'.join(group.splitlines()[1:]), meta))
            for i, match in enumerate(matches):
                detection, date, state, assessment, recommendation, coordinates, url = match.groups()
                end = matches[i+1].start() if i+1 < len(matches) else len(group)
                note = group[match.end():end].strip()
                note = note.split('Local queue audit only:')[0].strip()
                story.append(p('Detection ' + detection, heading))
                story.append(p(f'Recording date: {date}\nAudio assessment: {assessment}\nWriteback status: {state}\nStation coordinates: {coordinates}', meta))
                story.append(Paragraph(f'<link href="{html.escape(url, quote=True)}" color="black">{html.escape(url)}</link>', meta))
                if note:
                    story += [p('Gemini audio explanation', label), p(note)]
                story += [p('Model recommendation', label), p(recommendation)]
                number += 1
    output = args.output or args.input.with_suffix('.pdf')
    if output.resolve() == args.input.resolve():
        parser.error('Output must differ from the input TXT file.')
    output.parent.mkdir(parents=True, exist_ok=True)
    def page_number(canvas, doc):
        canvas.setFont('AuditArial', 12)
        canvas.setFillColor(colors.black)
        canvas.drawCentredString(A4[0]/2, 1.25*cm, str(doc.page))
    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=2.54*cm, rightMargin=2.54*cm,
                      topMargin=2.54*cm, bottomMargin=2.54*cm,
                      title='BirdNET Historical Detection Review Audit').build(story, onFirstPage=page_number, onLaterPages=page_number)
    print('PDF:', output.resolve())
    print('Formatted assessment entries:', number)
    print('Input TXT preserved. API calls: NO. Operational changes: NO.')


if __name__ == '__main__':
    main()
