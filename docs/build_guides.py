# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate Swedish and English Analyzer guides."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer
from analysis_pdf import BODY, TITLE, HEADING, paragraph

RELEASE = 'https://github.com/chto0703009/ICCProfileAnalyzer/releases/tag/v1.0.0'
ICON = Path(__file__).resolve().parents[1] / 'resources/analyzer-header.png'

GUIDES = {
    'SV': ('Användarguide', [
        ('Installera på Mac', 'Öppna DMG-filen för Apple Silicon. Dra ICC Profile Analyzer till Program och öppna appen därifrån. Ikonen syns även i huvudfönstret.'),
        ('Öppna profiler', 'Välj Open ICC och öppna en ICC- eller ICM-fil (v2 eller v4). Välj Compare with ICC för att lägga till profil B. Turkos visar profil A och lila profil B.'),
        ('Läs jämförelsen', 'Comparison and Curves visar bedömningen överst. Dra i reglaget för att välja L*. Färgpunkterna visar modellens a* och b* inom ± 2,5 L*.'),
        ('Studera kurvorna', 'Välj en ramp och ett värde, exempelvis L*, kroma, nyans eller färgsteg. Rendering styr om kurvorna visar enhetsvärden direkt eller sRGB genom profilen. BPC är svartpunktskompensation.'),
        ('Jämför mot en mätfil', 'Välj Open Measurements och ange en CGATS- eller TI3-fil med skrivar-RGB (0-100) och Lab D50 eller XYZ D50 (Y-skala 0-100). Ange om underlaget är en oberoende mätning eller träningsdata. ΔE00 jämför samma RGB i absolut Lab D50.'),
        ('Spara rapporten', 'Välj Save PDF för en engelsk rapport med jämförelse, L*-snitt, alla kurvor för valt återgivningsläge, mätstatistik och ICC-taggar. Save JSON sparar en maskinläsbar logg.'),
        ('Avsluta', 'Klicka på Quit uppe till höger i huvudfönstret.'),
        ('Tolka resultatet', 'Gamutvolymen bygger på ett konvext hölje av samplade värden. Utskriftens träffsäkerhet bedöms med oberoende mätningar under samma utskriftsvillkor.'),
    ]),
    'EN': ('User guide', [
        ('Install on Mac', 'Open the Apple Silicon disk image. Drag ICC Profile Analyzer to Applications and open it from there. The application icon also appears in the main window.'),
        ('Open profiles', 'Choose Open ICC and select an ICC or ICM profile (v2 or v4). Choose Compare with ICC to add profile B. Teal identifies profile A and purple identifies profile B.'),
        ('Read the comparison', 'Comparison and Curves shows the assessment above the charts. Drag the lightness slider to see sampled a* and b* within ± 2.5 L* of the selected level.'),
        ('Inspect the curves', 'Choose a ramp and a metric such as L*, chroma, hue or color steps. Rendering selects direct device ramps or sRGB rendered through the profile. BPC stands for black point compensation.'),
        ('Compare with measurements', 'Choose Open Measurements and select a CGATS or TI3 file containing device RGB (0-100) and Lab D50 or XYZ D50 (Y scale 0-100). Record whether the file contains independent or training measurements. ΔE00 compares matching RGB values in absolute Lab D50.'),
        ('Save the report', 'Choose Save PDF for an English report with the comparison, lightness slices, all curves for the selected rendering mode, measurement statistics and ICC tags. Save JSON exports a machine-readable log.'),
        ('Quit', 'Click Quit at the top right of the main window.'),
        ('Interpret the results', 'The gamut volume is a convex hull estimate from sampled values. Use independent measurements under matching print conditions to assess print accuracy.'),
    ]),
}

for lang, (title, sections) in GUIDES.items():
    path = Path(__file__).with_name(f'ICC-Profile-Analyzer-{lang}.pdf')
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=f'ICC Profile Analyzer | {title}',
                            topMargin=55, bottomMargin=52, leftMargin=57, rightMargin=57)
    story = [Image(str(ICON), width=39, height=39, hAlign='LEFT'), Spacer(1,6),
             paragraph('ICC Profile Analyzer', TITLE), paragraph(f'{title} | 1.0.0', HEADING), Spacer(1,8)]
    for heading, body in sections:
        story.extend((paragraph(heading, HEADING), paragraph(body)))
    label = 'Hämta appen på GitHub' if lang == 'SV' else 'Download the app on GitHub'
    story.append(Paragraph(f'<link href="{RELEASE}" color="#008478">{label}</link>', BODY))
    doc.build(story)
