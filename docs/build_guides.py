# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate Swedish and English Analyzer guides."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer
from analysis_pdf import BODY, TITLE, HEADING, paragraph

RELEASE = 'https://github.com/chto0703009/ICCProfileAnalyzer/releases/tag/v1.0.2'
ICON = Path(__file__).resolve().parents[1] / 'resources/analyzer-header.png'
SECTION = ParagraphStyle('guide-section', parent=HEADING, spaceBefore=5, spaceAfter=3)

GUIDES = {
    'SV': ('Användarguide', [
        ('Installera på Mac', 'Välj DMG-filen för Apple Silicon om din Mac har ett Apple-chip, eller Intel om den har en Intel-processor. Intel-versionen kräver macOS 14 eller senare. Öppna DMG-filen och dra appen till Program.'),
        ('Öppna profiler', 'Välj Open ICC och öppna en ICC- eller ICM-fil (v2 eller v4). Välj Compare with ICC för att lägga till profil B. Rött visar profil A och blått profil B.'),
        ('Läs jämförelsen', 'Comparison and Curves visar bedömningen överst. Dra i reglaget för att välja L*. Färgpunkterna visar modellens a* och b* inom ± 2,5 L*.'),
        ('Studera kurvorna', 'Välj en ramp och ett värde, exempelvis L*, kroma, nyans eller färgsteg. Rendering styr om kurvorna visar enhetsvärden direkt eller sRGB genom profilen. BPC är svartpunktskompensation.'),
        ('Tolka a*, b* och färgton h°', 'a* går från grönt (minus) till rött (plus). b* går från blått (minus) till gult (plus). Där båda är noll är färgen neutral. Färgtonen h° är vinkeln i a*/b*-planet. 0° pekar mot rött, 90° mot gult, 180° mot grönt och 270° mot blått. 360° är samma riktning som 0°. Appen döljer h° vid C* under 1.'),
        ('Tolka Chroma C*', 'Kroma C* är avståndet från neutralt grått vid samma ljushet L*. Beräkna C* = √(a*² + b*²). Med a* = 30 och b* = 40 blir C* = 50. Välj Neutral RGB och Chroma C*. Värden nära noll betyder att profilens beräknade gråtoner är nära neutrala. Högre värden visar starkare färgstick. Läs a*/b*-kurvorna eller färgtonen h° för att se åt vilket håll färgen drar.'),
        ('Jämför mot en mätfil', 'Välj Open Measurements och ange en CGATS- eller TI3-fil med skrivar-RGB (0-100) och Lab D50 eller XYZ D50 (Y-skala 0-100). Ange om underlaget är en oberoende mätning eller träningsdata. ΔE00 jämför samma RGB i absolut Lab D50.'),
        ('Spara rapporten', 'Välj Save PDF för en engelsk rapport med jämförelse, L*-snitt, alla kurvor för valt återgivningsläge, mätstatistik och ICC-taggar. Save JSON sparar en maskinläsbar logg.'),
        ('Avsluta', 'Klicka på Quit uppe till höger i huvudfönstret.'),
        ('Senast använda mappar', 'Filväljarna börjar på skrivbordet. Appen minns ICC-mapp, mätmapp och sparmapp mellan starter. Den första exporten föreslås i mappen för senaste öppnade fil.'),
        ('Tolka resultatet', 'Gamutvolymen bygger på ett konvext hölje av samplade värden. Utskriftens träffsäkerhet bedöms med oberoende mätningar under samma utskriftsvillkor.'),
    ]),
    'EN': ('User guide', [
        ('Install on Mac', 'Choose the Apple Silicon disk image for a Mac with an Apple chip, or the Intel disk image for an Intel Mac. The Intel build requires macOS 14 or later. Open the disk image and drag the app to Applications.'),
        ('Open profiles', 'Choose Open ICC and select an ICC or ICM profile (v2 or v4). Choose Compare with ICC to add profile B. Red identifies profile A and blue identifies profile B.'),
        ('Read the comparison', 'Comparison and Curves shows the assessment above the charts. Drag the lightness slider to see sampled a* and b* within ± 2.5 L* of the selected level.'),
        ('Inspect the curves', 'Choose a ramp and a metric such as L*, chroma, hue or color steps. Rendering selects direct device ramps or sRGB rendered through the profile. BPC stands for black point compensation.'),
        ('Interpret a*, b*, and hue h°', 'a* runs from green (negative) to red (positive). b* runs from blue (negative) to yellow (positive). When both are zero, the color is neutral. Hue h° is the angle in the a*/b* plane. 0° points toward red, 90° toward yellow, 180° toward green, and 270° toward blue. 360° is the same direction as 0°. The app hides hue below C* = 1.'),
        ('Interpret Chroma C*', 'Chroma C* is the distance from neutral gray at the same lightness L*. Calculate C* = √(a*² + b*²). If a* = 30 and b* = 40, C* = 50. Select Neutral RGB and Chroma C*. Values near zero indicate near-neutral grays in the profile prediction. Higher values indicate a stronger color cast. Use the a*/b* curves or hue h° to identify the direction of the cast.'),
        ('Compare with measurements', 'Choose Open Measurements and select a CGATS or TI3 file containing device RGB (0-100) and Lab D50 or XYZ D50 (Y scale 0-100). Record whether the file contains independent or training measurements. ΔE00 compares matching RGB values in absolute Lab D50.'),
        ('Save the report', 'Choose Save PDF for an English report with the comparison, lightness slices, all curves for the selected rendering mode, measurement statistics and ICC tags. Save JSON exports a machine-readable log.'),
        ('Quit', 'Click Quit at the top right of the main window.'),
        ('Recent folders', 'File pickers start on the Desktop. The app remembers your ICC, measurement and save folders between launches. The first export defaults to the last opened file’s folder.'),
        ('Interpret the results', 'The gamut volume is a convex hull estimate from sampled values. Use independent measurements under matching print conditions to assess print accuracy.'),
    ]),
}

for lang, (title, sections) in GUIDES.items():
    path = Path(__file__).with_name(f'ICC-Profile-Analyzer-{lang}.pdf')
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=f'ICC Profile Analyzer | {title}',
                            topMargin=40, bottomMargin=40, leftMargin=57, rightMargin=57)
    story = [Image(str(ICON), width=39, height=39, hAlign='LEFT'), Spacer(1,6),
             paragraph('ICC Profile Analyzer', TITLE), paragraph(f'{title} | 1.0.2', HEADING), Spacer(1,8)]
    for heading, body in sections:
        story.extend((paragraph(heading, SECTION), paragraph(body)))
    label = 'Hämta appen på GitHub' if lang == 'SV' else 'Download the app on GitHub'
    story.append(Paragraph(f'<link href="{RELEASE}" color="#008478">{label}</link>', BODY))
    doc.build(story)
