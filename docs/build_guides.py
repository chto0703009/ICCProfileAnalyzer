# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate Swedish and English Analyzer guides."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Spacer
from analysis_pdf import TITLE, HEADING, paragraph

GUIDES = {
    'SV': ('Användarguide', [
        ('Öppna profiler', 'Välj Open ICC och öppna en ICC- eller ICM-fil (v2 eller v4). Välj Compare with ICC för att lägga till profil B. Turkos visar profil A och lila profil B.'),
        ('Läs jämförelsen', 'Comparison and Curves visar bedömningen överst. Dra i reglaget för att välja L*. Färgpunkterna visar modellens a* och b* inom ± 2,5 L*.'),
        ('Studera kurvorna', 'Välj en ramp och ett värde, exempelvis L*, kroma, nyans eller färgsteg. Rendering styr om kurvorna visar enhetsvärden direkt eller sRGB genom profilen. BPC är svartpunktskompensation.'),
        ('Jämför mot en mätfil', 'Välj Open Measurements och ange en CGATS- eller TI3-fil med skrivar-RGB (0-100) och Lab D50 eller XYZ D50 (Y-skala 0-100). Ange om underlaget är en oberoende mätning eller träningsdata. ΔE00 jämför samma RGB i absolut Lab D50.'),
        ('Spara rapporten', 'Välj Save PDF för en engelsk rapport med jämförelse, L*-snitt, alla kurvor för valt återgivningsläge, mätstatistik och ICC-taggar. Save JSON sparar en maskinläsbar logg.'),
        ('Tolka resultatet', 'Gamutvolymen bygger på ett konvext hölje av samplade värden. Utskriftens träffsäkerhet bedöms med oberoende mätningar under samma utskriftsvillkor.'),
    ]),
    'EN': ('User guide', [
        ('Open profiles', 'Choose Open ICC and select an ICC or ICM profile (v2 or v4). Choose Compare with ICC to add profile B. Teal identifies profile A and purple identifies profile B.'),
        ('Read the comparison', 'Comparison and Curves shows the assessment above the charts. Drag the lightness slider to see sampled a* and b* within ± 2.5 L* of the selected level.'),
        ('Inspect the curves', 'Choose a ramp and a metric such as L*, chroma, hue or color steps. Rendering selects direct device ramps or sRGB rendered through the profile. BPC stands for black point compensation.'),
        ('Compare with measurements', 'Choose Open Measurements and select a CGATS or TI3 file containing device RGB (0-100) and Lab D50 or XYZ D50 (Y scale 0-100). Record whether the file contains independent or training measurements. ΔE00 compares matching RGB values in absolute Lab D50.'),
        ('Save the report', 'Choose Save PDF for an English report with the comparison, lightness slices, all curves for the selected rendering mode, measurement statistics and ICC tags. Save JSON exports a machine-readable log.'),
        ('Interpret the results', 'The gamut volume is a convex hull estimate from sampled values. Use independent measurements under matching print conditions to assess print accuracy.'),
    ]),
}

for lang, (title, sections) in GUIDES.items():
    path = Path(__file__).with_name(f'ICC-Profile-Analyzer-{lang}.pdf')
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=f'ICC Profile Analyzer | {title}',
                            topMargin=55, bottomMargin=52, leftMargin=57, rightMargin=57)
    story = [paragraph('ICC Profile Analyzer', TITLE), paragraph(title, HEADING), Spacer(1,8)]
    for heading, body in sections:
        story.extend((paragraph(heading, HEADING), paragraph(body)))
    doc.build(story)
