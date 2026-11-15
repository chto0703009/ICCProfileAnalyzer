# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""English PDF export of the completed analysis."""
from datetime import datetime
from io import BytesIO
import json

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, LongTable, PageBreak, Paragraph, SimpleDocTemplate, TableStyle

from profile_analysis import curve_series, lightness_slice

INK = colors.HexColor('#182c40')
GRID = colors.HexColor('#d9e3ec')
PALE = colors.HexColor('#eff5f8')
TRACE = (colors.HexColor('#008478'), colors.HexColor('#7350b4'))
METRICS = ('L*', 'a* and b*', 'Chroma C*', 'Hue h°', 'Step ΔE76')
pdfmetrics.registerFont(TTFont('DejaVu', str(Path(__file__).resolve().parent / 'resources/DejaVuSans.ttf')))
BODY = ParagraphStyle('body', fontName='DejaVu', fontSize=9.0, leading=13, textColor=INK, spaceAfter=3, splitLongWords=True)
CELL = ParagraphStyle('cell', parent=BODY, fontSize=8, leading=10, spaceAfter=0)
TITLE = ParagraphStyle('title', parent=BODY, fontName='Helvetica-Bold', fontSize=24, leading=28, spaceAfter=12, keepWithNext=True)
HEADING = ParagraphStyle('heading', parent=BODY, fontName='Helvetica-Bold', fontSize=13, leading=17, spaceBefore=10, spaceAfter=5, keepWithNext=True)


def paragraph(text, style=BODY):
    return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)


def table(rows, widths):
    grid = LongTable([[paragraph(value, CELL) for value in row] for row in rows],
                     colWidths=widths, repeatRows=1, splitInRow=1, hAlign='LEFT')
    grid.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE), ('VALIGN',(0,0),(-1,-1),'TOP'),
                             ('LINEBELOW',(0,0),(-1,-1),0.25,GRID)]))
    return grid


def fmt(number):
    return '-' if number is None else f'{number:.2f}'


def draw_axes(c, x, y, width, height, xlim, ylim, title, x_label):
    def xp(v):
        return x + width * (v - xlim[0]) / (xlim[1] - xlim[0])

    def yp(v):
        return y + height * (v - ylim[0]) / (ylim[1] - ylim[0])

    c.setLineWidth(.4)
    c.setFont('Helvetica', 7)
    for i in range(5):
        xv = xlim[0] + (xlim[1]-xlim[0]) * i/4
        yv = ylim[0] + (ylim[1]-ylim[0]) * i/4
        c.setStrokeColor(GRID)
        c.line(xp(xv), y, xp(xv), y+height)
        c.line(x, yp(yv), x+width, yp(yv))
        c.setFillColor(INK)
        c.drawCentredString(xp(xv), y-10, f'{xv:.3g}')
        c.drawRightString(x-4, yp(yv)-2, f'{yv:.3g}')
    c.setFont('DejaVu', 8)
    c.drawString(x, y+height+8, title)
    c.setFont('Helvetica', 7)
    c.drawCentredString(x+width/2, y-20, x_label)
    return xp, yp


class RampCharts(Flowable):
    def __init__(self, ramps):
        super().__init__()
        self.width, self.height = 480, 478
        self.ramps = ramps

    def draw(self):
        for index, metric in enumerate(METRICS):
            traces = [(i, component, series) for i, curve in self.ramps
                      for component, series in enumerate(curve_series(curve['lab'], metric))]
            values = [value for _, _, series in traces for value in series if value is not None]
            if not values:
                continue
            lo, hi = (0, 360) if metric == 'Hue h°' else (min(0,min(values)), max(.01,max(values)))
            x, y = 34 + (index % 2)*239, 343 - (index//2)*150
            xp, yp = draw_axes(self.canv,x,y,190,107,(0,100),(lo,hi),metric,'Ramp position (%)')
            for i, component, series in traces:
                path = self.canv.beginPath()
                previous = None
                for step, value in enumerate(series):
                    if value is None:
                        previous = None
                        continue
                    xx, yy = xp(100*step/(len(series)-1)), yp(value)
                    if previous is None or (metric=='Hue h°' and abs(value-previous)>180):
                        path.moveTo(xx, yy)
                    else:
                        path.lineTo(xx, yy)
                    previous = value
                self.canv.setStrokeColor(TRACE[i])
                self.canv.setLineWidth(1)
                self.canv.setDash([3,2] if component else [])
                self.canv.drawPath(path)
            self.canv.setDash([])


class GamutCharts(Flowable):
    def __init__(self, profiles, levels):
        super().__init__()
        self.width, self.height = 480, 522
        self.clouds = [p.get('result', {}).get('cloud', []) for p in profiles]
        self.levels = levels

    def draw(self):
        groups = [[lightness_slice(cloud, level) for cloud in self.clouds] for level in self.levels]
        bound = max(5, max((abs(v) for group in groups for points in group
                           for row in points for v in row[1:]), default=0))
        bound = 10 * (int(bound/10)+1)
        for index, (level, group) in enumerate(zip(self.levels, groups)):
            x, y = 30 + (index%3)*160, 370 - (index//3)*169
            xp, yp = draw_axes(self.canv,x,y,109,109,(-bound,bound),(-bound,bound),f'L* {level} | b*','a*')
            for i, samples in enumerate(group):
                self.canv.setFillColor(TRACE[i])
                # Coalesce markers at print scale. Hue tables still use every sample.
                points = {(2.5*round(xp(a)/2.5), 2.5*round(yp(b)/2.5)) for _,a,b in samples}
                dots = self.canv.beginPath()
                for px, py in sorted(points):
                    dots.rect(px-.55,py-.55,1.1,1.1)
                self.canv.drawPath(dots, stroke=0, fill=1)
            if not any(group):
                self.canv.setFont('Helvetica', 8)
                self.canv.setFillColor(INK)
                self.canv.drawCentredString(x+54.5,y+54.5,'No samples')


def footer(c, document):
    c.setFillColor(INK)
    c.setFont('Helvetica', 8)
    c.drawString(53, 29, 'ICC Profile Analyzer')
    c.drawRightString(A4[0]-53, 29, str(document.page))


def save_analysis(path, profiles, reference, mode, summary, selected_level):
    """Build in memory so report formatting errors cannot leave a partial export."""
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=52, rightMargin=52, topMargin=44,
                                 bottomMargin=47, title='ICC profile analysis', lang='en')
    story = [paragraph('ICC profile analysis', TITLE),
             paragraph(f'{mode} | {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}')]
    for i, profile in enumerate(profiles):
        story.append(paragraph(f'Profile {"AB"[i]}: {Path(profile["path"]).name}'))
    if len(profiles)==2:
        story.append(paragraph("Charts: Profile A (teal), Profile B (purple)."))
    else:
        story.append(paragraph('Charts: Profile A (teal).'))
    for line in summary.splitlines():
        if line:
            story.append(paragraph(line, HEADING if line in ('Method and interpretation', 'Estimated gamut volume, B compared with A') else BODY))
    if reference:
        story.append(paragraph(f'Measurement file SHA-256: {reference["sha256"]}'))
        story.append(paragraph(f'Measurement encoding: {reference["space"]}'))
    if any('result' in p for p in profiles):
        levels = list(range(10,100,10))
        story.extend((PageBreak(), paragraph('Gamut by lightness', TITLE),
                      paragraph(f'{"Relative" if mode == "Relative colorimetric" else "Absolute"} Lab D50. Each slice shows L* ± 2.5. Selected L*: {selected_level}.'),
                      GamutCharts(profiles,levels)))
        if selected_level not in levels:
            story.extend((PageBreak(), paragraph(f'Selected L* slice: {selected_level}', TITLE),
                          GamutCharts(profiles,[selected_level])))
        story.extend((PageBreak(), paragraph('Maximum sampled chroma by hue', TITLE),
                      paragraph('Each hue sector covers 30°. The tables show the highest sampled C* at L* ± 2.5. A dash means the sector had no samples.')))
        for i, p in enumerate(profiles):
            if not p.get('sectors'):
                continue
            story.append(paragraph(f'Profile {"AB"[i]}', HEADING))
            rows = [['L*'] + [f'{j}°' for j in range(0,360,30)]]
            rows.extend([level]+[fmt(c) for c in values] for level,values in p['sectors'].items())
            story.append(table(rows,[30]+[37]*12))
        names = dict.fromkeys(c['name'] for p in profiles for c in p.get('result',{}).get('curves',[]))
        for name in names:
            ramps = [(i,c) for i,p in enumerate(profiles)
                     for c in p.get('result',{}).get('curves',[]) if c['name']==name]
            story.extend((PageBreak(), paragraph(name, TITLE),
                          paragraph('257 ramp samples. Solid a* and dashed b* in the paired component plot. Hue is omitted below C* = 1.'),
                          RampCharts(ramps)))
            rows = [['Profile','Median ΔE76','Max ΔE76','Max step change','L* reversals','Near-flat steps']]
            for i, c in ramps:
                m = c['metrics']
                rows.append(['AB'[i], fmt(m['median_delta_e76']), fmt(m['max_delta_e76']),
                             fmt(m['max_step_change']),m['lightness_reversals'],m['near_flat_steps']])
            story.append(table(rows,[49,77,75,95,84,94]))
    for i, p in enumerate(profiles):
        info=p['info']
        story.extend((PageBreak(), paragraph(f'ICC tags: Profile {"AB"[i]}', TITLE), paragraph(Path(p['path']).name)))
        for key,value in info.items():
            if key!='tags':
                story.append(paragraph(f'{key.replace("_"," ").capitalize()}: {value}'))
        rows=[['Tag','Type','Offset','Bytes','SHA-256 and decoded values']]
        for tag in info['tags']:
            details = [tag['sha256']]
            details.extend(json.dumps(tag[key], ensure_ascii=False) for key in ('text','XYZ') if key in tag)
            rows.append([tag['tag'],tag['type'],tag['offset'],tag['bytes'],'\n'.join(details)])
        story.append(table(rows,[39,39,45,45,306]))
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    Path(path).write_bytes(buffer.getvalue())
