# ICC Profile Analyzer

<img src="resources/analyzer-header.png" alt="ICC Profile Analyzer app icon" width="72">

A standalone macOS app for numerical analysis of ICC v2 and v4 profiles. Open one profile or compare two side by side. Export the analysis as an English PDF report or a JSON file.

## Install on macOS

Download the [Apple Silicon disk image](https://github.com/chto0703009/ICCProfileAnalyzer/releases/latest), open it, and drag the app to **Applications**.

[English PDF guide](docs/ICC-Profile-Analyzer-EN.pdf) · [Swedish PDF guide](docs/ICC-Profile-Analyzer-SV.pdf)

- **Assessment** shows white and black points, lightness range, estimated absolute and relative gamut volumes, and observations about neutrality and curve smoothness.
- **Gamut by L\*** plots the profile’s a\*/b\* samples at the selected lightness. When comparing profiles, it reports the difference in maximum sampled chroma by hue sector.
- **Curves and smoothness** shows lightness, a\*/b\*, chroma, hue, and color difference between steps. In perceptual mode and relative mode with black point compensation, the analysis maps sRGB through device values to absolute Lab D50.
- **ICC Tags** shows the header, tag types, sizes, offsets, checksums, and decoded text and XYZ fields.
- **Open Measurements** compares RGB printer profiles with CGATS or TI3 data containing device RGB values from 0 to 100 and Lab D50 or XYZ D50 with reference-white Y = 100. Declare whether the data is for training or independent verification. Results include mean, p95, and maximum ΔE00, with separate statistics for shadows and near-neutral colors.

Curve and gamut analysis supports RGB, CMYK, and grayscale device profiles. Other ICC v2/v4 profiles are displayed as metadata. CMYK sampling uses a 300% total ink limit and reports pure K as the black endpoint. The gamut volume is estimated from a convex hull of the sampled Lab points, which can bridge concavities. Use independent print measurements to assess accuracy.

**Save PDF** includes the assessment, measurement statistics, gamut slices, curves for the selected rendering mode, and ICC tags. Each chart has a color-matched legend. Measurement comparisons record the source file and checksums for traceability.

The disk image includes both guides. File dialogs start on the Desktop and remember the last ICC, measurement, and export folders.

Filväljarna börjar på skrivbordet. Appen minns senaste ICC-mapp (delad med jämförelsen), mätmapp och sparmapp mellan starter. Den första exporten föreslås i mappen för senast öppnade fil. PDF och JSON delar sparmapp.

## Run from source and build the app

Use Python with Tkinter and LittleCMS 2. The Apple Silicon build uses Homebrew’s LittleCMS library and bundles it with PyInstaller.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller==6.20.0
.venv/bin/python app.py
.venv/bin/python -m PyInstaller --windowed --name 'ICC Profile Analyzer' --icon resources/Analyzer.icns \
  --osx-bundle-identifier se.borgasundsfotografiska.iccprofileanalyzer \
  --add-binary /opt/homebrew/lib/liblcms2.2.dylib:. \
  --collect-submodules scipy._external.array_api_compat \
  --add-data LittleCMS-LICENSE.txt:. --add-data resources:resources app.py
```

Run the tests with `.venv/bin/python -m unittest`. Rebuild the PDF guides with `PYTHONPATH=. .venv/bin/python docs/build_guides.py`. On macOS, regenerate the icon with `.venv/bin/python tools/build_icon.py`.

## License

The application and the color math from InkProf are licensed under [GNU GPL version 3 or later](LICENSE) (`GPL-3.0-or-later`). [LittleCMS is MIT-licensed](LittleCMS-LICENSE.txt). See the [DejaVu font notices](resources/DejaVuSans.ttf.notices.txt) for the embedded report font.
