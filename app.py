# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop interface for ICC Profile Analyzer."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import atan2, degrees
from pathlib import Path
import json
import sys
from dialog_locations import DialogLocations
from plot_labels import PROFILE_COLOURS, RAMP_X_TICKS, lab_label, opponent_ticks, ramp_y_ticks, tick_label
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from profile_analysis import (INTENTS, analyse, chroma, curve_series, hue_sectors, hull_volume,
                              lightness_slice, measurement_file, measurement_fit,
                              metadata, source_ramps)

MODES = [*INTENTS, 'sRGB to profile: perceptual', 'sRGB to profile: relative + BPC']
COLOURS = PROFILE_COLOURS
LEVELS = range(10, 100, 10)
UNKNOWN_REFERENCE = "Unknown reference"


def read_profile(path):
    data = path.read_bytes()
    return dict(path=str(path), info=metadata(data), data=data)


def calculate(paths, reference_path, relationship, mode):
    profiles = [read_profile(path) for path in paths]
    reference = measurement_file(reference_path) if reference_path else None
    intent = INTENTS.get(mode, 3)
    for profile in profiles:
        info, data = profile['info'], profile.pop('data')
        try:
            results = {key: analyse(data, info, key) for key in (3, 1)}
        except (OSError, ValueError) as error:
            profile['error'] = str(error)
            continue
        profile['result'] = results[intent]
        # A single-channel profile traces a line in Lab and has no volume.
        profile['volume'] = {key: None if info['colour_space'] == 'GRAY' else hull_volume(result['cloud'])
                             for key, result in results.items()}
        if mode not in INTENTS:
            try:
                profile['result']['curves'] = source_ramps(data, info['colour_space'],
                                                          1 if mode == MODES[3] else 0, mode == MODES[3])
            except ValueError as error:
                profile['curve_error'] = str(error)
                profile['result']['curves'] = []
        profile['sectors'] = {level: hue_sectors(profile['result']['cloud'], level) for level in LEVELS}
        if reference and info['colour_space'] == 'RGB ':
            try:
                profile['measurement_fit'] = measurement_fit(data, reference)
                profile['measurement_fit']['reference'] = {
                    'file': reference['file'], 'sha256': reference['sha256'],
                    'space': reference['space'], 'declared_relationship': relationship,
                }
            except (OSError, ValueError) as error:
                profile['measurement_error'] = str(error)
    return profiles, ({key: value for key, value in reference.items() if key not in ('rgb', 'lab')}
                      | {'relationship': relationship} if reference else None)


class Analyzer:
    def __init__(self, root):
        self.root = root
        self.locations = DialogLocations("ICC Profile Analyzer")
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.paths = []
        self.reference_path = None
        self.relationship = tk.StringVar(value=UNKNOWN_REFERENCE)
        self.mode = tk.StringVar(value=MODES[0])
        self.level = tk.DoubleVar(value=50)
        self.ramp = tk.StringVar()
        self.metric = tk.StringVar(value='L*')
        self.status = tk.StringVar(value='Open an ICC profile to begin.')
        self.profiles = []
        self.completed_mode = None
        self.reference = None
        root.title('ICC Profile Analyzer')
        root.protocol('WM_DELETE_WINDOW', self.quit)
        root.geometry('1100x790')
        root.minsize(830, 620)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        header = ttk.Frame(frame)
        header.pack(fill='x', pady=(0, 10))
        icon_path = Path(__file__).resolve().parent / 'resources/analyzer-header.png'
        self.header_icon = tk.PhotoImage(file=icon_path).subsample(3)
        ttk.Label(header, image=self.header_icon).pack(side='left', padx=(0, 8))
        ttk.Label(header, text='ICC Profile Analyzer', font='TkHeadingFont').pack(side='left')
        ttk.Button(header, text='Quit', command=self.quit).pack(side='right')
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.open_button = ttk.Button(row, text='Open ICC…', command=self.open_profile)
        self.compare_button = ttk.Button(row, text='Compare with ICC…', command=lambda: self.open_profile(True))
        self.measure_button = ttk.Button(row, text='Open Measurements…', command=self.open_reference)
        self.clear_button = ttk.Button(row, text='Clear Measurements', command=self.clear_reference)
        self.save_button = ttk.Button(row, text='Save JSON…', command=self.save_report)
        self.pdf_button = ttk.Button(row, text='Save PDF…', command=self.save_pdf)
        for button in (self.open_button, self.compare_button, self.measure_button, self.clear_button,
                       self.pdf_button, self.save_button):
            button.pack(side='left', padx=(0, 6))
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(10, 6))
        ttk.Label(row, text='Rendering').pack(side='left')
        self.mode_box = ttk.Combobox(row, textvariable=self.mode, values=MODES, state='readonly', width=36)
        self.mode_box.pack(side='left', padx=(8, 16))
        self.mode_box.bind('<<ComboboxSelected>>', lambda _: self.run())
        ttk.Label(row, text='Measurement source').pack(side='left')
        self.relationship_box = ttk.Combobox(row, textvariable=self.relationship, state='readonly', width=28,
            values=(UNKNOWN_REFERENCE, 'Independent verification', 'Training data for profile A', 'Training data for profile B',
                    'Training data for both'))
        self.relationship_box.pack(side='left', padx=8)
        self.relationship_box.bind('<<ComboboxSelected>>', lambda _: self.run())
        ttk.Label(frame, textvariable=self.status, wraplength=1000).pack(anchor='w', pady=(0, 8))
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill='both', expand=True)
        dashboard = ttk.Frame(self.tabs)
        self.tabs.add(dashboard, text='Comparison and Curves')
        layout = ttk.Panedwindow(dashboard, orient='vertical')
        layout.pack(fill='both', expand=True)
        overview = ttk.Labelframe(layout, text='Assessment')
        layout.add(overview, weight=1)
        self.summary = self.text_field(overview, height=8)
        charts = ttk.Panedwindow(layout, orient='horizontal')
        layout.add(charts, weight=3)
        self.slice_panel = ttk.Labelframe(charts, text='Gamut by L*', padding=8)
        charts.add(self.slice_panel, weight=1)
        level_row = ttk.Frame(self.slice_panel)
        level_row.pack(fill='x')
        self.slice_title = ttk.Label(level_row)
        self.slice_title.pack(side='left', padx=(0, 8))
        ttk.Scale(level_row, from_=0, to=100, variable=self.level,
                  command=lambda _: self.draw_slice()).pack(side='left', fill='x', expand=True)
        self.slice_canvas = self.chart(self.slice_panel, self.draw_slice)
        self.sectors = ttk.Label(self.slice_panel, wraplength=430)
        self.sectors.pack(anchor='w')
        self.curve_panel = ttk.Labelframe(charts, text='Curves and smoothness', padding=8)
        charts.add(self.curve_panel, weight=1)
        options = ttk.Frame(self.curve_panel)
        options.pack(fill='x')
        self.ramp_box = ttk.Combobox(options, textvariable=self.ramp, state='readonly', width=18)
        self.ramp_box.pack(side='left', padx=(0, 10))
        self.ramp_box.bind('<<ComboboxSelected>>', lambda _: self.draw_curves())
        metric = ttk.Combobox(options, textvariable=self.metric, state='readonly', width=15,
                             values=('L*', 'a* and b*', 'Chroma C*', 'Hue h°', 'Step ΔE76'))
        metric.pack(side='left')
        metric.bind('<<ComboboxSelected>>', lambda _: self.draw_curves())
        self.curve_canvas = self.chart(self.curve_panel, self.draw_curves)
        self.curve_details = ttk.Label(self.curve_panel, wraplength=430)
        self.curve_details.pack(anchor='w')
        self.tags = self.text_tab('ICC Tags')
        bar = tk.Menu(root)
        file_menu = tk.Menu(bar, tearoff=False)
        bar.add_cascade(label='File', menu=file_menu)
        actions = (('Open ICC…', self.open_profile), ('Compare with ICC…', lambda: self.open_profile(True)),
                   ('Open Measurements…', self.open_reference), ('Clear Measurements', self.clear_reference),
                   ('Save PDF…', self.save_pdf), ('Save JSON…', self.save_report))
        for label, action in actions:
            file_menu.add_command(label=label, command=action)
        root.configure(menu=bar)
        self.file_menu = file_menu
        self.set_buttons(False)

    def quit(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def text_tab(self, label):
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=label)
        return self.text_field(frame)

    @staticmethod
    def text_field(frame, **options):
        bar = ttk.Scrollbar(frame)
        bar.pack(side='right', fill='y')
        field = tk.Text(frame, wrap='word', padx=18, pady=14, yscrollcommand=bar.set,
                        state='disabled', font='TkDefaultFont', **options)
        bar.configure(command=field.yview)
        field.pack(fill='both', expand=True)
        return field

    @staticmethod
    def chart(panel, draw):
        canvas = tk.Canvas(panel, background='white', highlightthickness=0)
        canvas.pack(fill='both', expand=True, pady=8)
        canvas.bind('<Configure>', lambda _: draw())
        return canvas

    def set_buttons(self, busy):
        actions = ((self.open_button, True), (self.compare_button, bool(self.paths)),
                   (self.measure_button, bool(self.paths)), (self.clear_button, bool(self.reference_path)),
                   (self.pdf_button, bool(self.profiles)), (self.save_button, bool(self.profiles)))
        for i, (button, ready) in enumerate(actions):
            state = 'normal' if ready and not busy else 'disabled'
            button.configure(state=state)
            self.file_menu.entryconfigure(i, state=state)
        for box in (self.mode_box, self.relationship_box):
            box.configure(state='disabled' if busy else 'readonly')

    def open_profile(self, comparison=False):
        value = filedialog.askopenfilename(
            parent=self.root, title='Compare with ICC' if comparison else 'Open ICC',
            initialdir=self.locations.directory('icc'), filetypes=[('ICC profile', ('*.icc', '*.icm'))],
        )
        if value:
            paths = [*self.paths[:1], Path(value)] if comparison else [Path(value)]
            relationship = self.relationship.get()
            if self.reference_path and (not comparison or relationship in
                                        ('Training data for profile B', 'Training data for both')):
                relationship = UNKNOWN_REFERENCE
            self.change_inputs(paths, self.reference_path, relationship,
                               on_success=lambda: self.locations.remember("icc", value, opened=True))

    def open_reference(self):
        value = filedialog.askopenfilename(
            parent=self.root, title='Open Measurements', initialdir=self.locations.directory('measurements'),
            filetypes=[('CGATS', ('*.ti3', '*.cgats', '*.txt')), ('All files', '*')],
        )
        if value:
            self.change_inputs(self.paths, Path(value), UNKNOWN_REFERENCE,
                               on_success=lambda: self.locations.remember("measurements", value, opened=True))

    def clear_reference(self):
        self.change_inputs(self.paths, None, UNKNOWN_REFERENCE)

    def change_inputs(self, paths, reference_path, relationship, on_success=None):
        old_paths, old_reference = self.paths, self.reference_path
        old_relationship = self.relationship.get()
        self.paths, self.reference_path = paths, reference_path
        self.relationship.set(relationship)

        def restore():
            self.paths, self.reference_path = old_paths, old_reference
            self.relationship.set(old_relationship)

        self.run(rollback=restore, on_success=on_success)

    def run(self, rollback=None, on_success=None):
        if not self.paths:
            return
        self.set_buttons(True)
        self.status.set('Analyzing profiles…')
        mode = self.mode.get()
        task = self.pool.submit(calculate, self.paths[:], self.reference_path, self.relationship.get(), mode)

        def finish():
            if not task.done():
                self.root.after(80, finish)
                return
            try:
                self.profiles, self.reference = task.result()
            except Exception as error:
                if rollback:
                    rollback()
                if self.completed_mode:
                    self.mode.set(self.completed_mode)
                if self.reference:
                    self.relationship.set(self.reference['relationship'])
                self.status.set('Analysis could not be completed.')
                messagebox.showerror('ICC Profile Analyzer', str(error), parent=self.root)
            else:
                if on_success:
                    on_success()
                self.completed_mode = mode
                self.status.set('  |  '.join(f'{letter}: {Path(p["path"]).name}' for letter,p in zip('AB',self.profiles)))
                self.refresh()
            finally:
                self.set_buttons(False)
        self.root.after(50, finish)

    @staticmethod
    def fill(field, text):
        field.configure(state='normal')
        field.delete('1.0', 'end')
        field.insert('1.0', text)
        field.configure(state='disabled')

    def refresh(self):
        lines, tags, names = [], [], []
        if self.reference:
            lines += [f'Measurements: {Path(self.reference["file"]).name} · {self.reference["relationship"]}',
                      'ΔE00 compares the same device RGB values in absolute Lab D50. A profile built from this file is evaluated against its own training data.', '']
        for letter, p in zip('AB', self.profiles):
            info = p['info']
            lines += [f'{letter}  {Path(p["path"]).name}',
                      f'ICC {info["version"]} · class {info["profile_class"]} · {info["colour_space"].strip()} → {info["pcs"].strip()}']
            tags += [f'PROFILE {letter} · {p["path"]}', json.dumps(info, ensure_ascii=False, indent=2), '']
            if 'error' in p:
                lines += [p['error'], '']
                continue
            r = p['result']
            lines += [f'White point  {lab_text(r["white"])}',
                      f'Black point ({r["black_definition"]})  {lab_text(r["black"])}',
                      f'Lightness range ΔL* {r["white"][0]-r["black"][0]:.2f} · black chroma {chroma(r["black"]):.2f}',
                      f'Gamut volume (convex hull): absolute {volume(p["volume"][3])} · relative {volume(p["volume"][1])} Lab³']
            if r['total_ink_limit_percent']:
                lines.append('CMYK sampling uses a 300% total ink cap. The black point uses pure K.')
            if m := p.get('measurement_fit'):
                lines.append(f'Profile {letter} compared with {Path(m["reference"]["file"]).name} in absolute Lab D50.')
                lines.append(f'ΔE00 for {m["count"]} patches: mean {m["mean"]:.2f} · p95 {m["p95"]:.2f} · max {m["max"]:.2f}')
                if white := m.get('measured_white'):
                    lines.append(f'Measured white  {lab_text(white)}')
                if bias := m.get('saturated_bias'):
                    lines.append(f'Saturated patches C* ≥ 35 ({bias["count"]} patches), model minus measurement: ΔL* {bias["delta_l"]:+.2f}, ΔC* {bias["delta_c"]:+.2f}')
                for key, label in [('shadows', 'Shadows L* ≤ 30'), ('neutrals', 'Near neutrals C* ≤ 5')]:
                    if group := m[key]:
                        lines.append(f'{label}: mean {group["mean"]:.2f} ({group["count"]} patches)')
            elif self.reference:
                lines.append(p.get('measurement_error', 'Measurement comparison is available for RGB profiles.'))
            if 'curve_error' in p:
                lines.append(p['curve_error'])
            if r['curves']:
                names.extend(x['name'] for x in r['curves'])
                neutral = r['curves'][0]
                worst = max(r['curves'], key=lambda x: x['metrics']['max_step_change'])
                nm = neutral['metrics']
                lines.append(f'{neutral["name"]}: midpoint {lab_text(neutral["lab"][128])}.')
                if nm['lightness_reversals']:
                    lines.append(f'Review: {neutral["name"]} has {nm["lightness_reversals"]} local L* reversals. The largest is {nm["largest_reversal"]:.3f} L*.')
                else:
                    lines.append(f'Strength on this ramp: {neutral["name"]} has no L* reversals greater than 0.02 per step.')
                lines.append(f'Largest change between adjacent color steps: {worst["name"].lower()} ({worst["metrics"]["max_step_change"]:.3f} ΔE76).')
            lines.append('')
        if len(self.profiles)==2:
            a,b=self.profiles
            if 'volume' in a and 'volume' in b and a['info']['colour_space']==b['info']['colour_space']:
                lines.append('Estimated gamut volume, B compared with A')
                for intent,label in ((3,'Absolute'),(1,'Relative')):
                    va,vb=a['volume'][intent],b['volume'][intent]
                    if va and vb:
                        lines.append(f'{label}: {(vb/va-1)*100:+.2f} %')
                if 'measurement_fit' in a and 'measurement_fit' in b:
                    lines.append(f'Mean ΔE00 on matched patches, B minus A: {b["measurement_fit"]["mean"]-a["measurement_fit"]["mean"]:+.2f}')
                lines.append('')
        lines += ['Method and interpretation',
                  'Gamut volume is estimated from a convex hull of sampled Lab values. The hull can span concavities. Each L* slice shows model samples within the selected band.',
                  'sRGB curves use sRGB to device to absolute Lab D50. White, black and gamut still describe the device profile.',
                  'Smoothness and gamut describe the profile model. Independent print measurements under matching conditions are needed to evaluate print accuracy.']
        self.fill(self.summary, '\n'.join(lines))
        self.fill(self.tags, '\n'.join(tags))
        names = list(dict.fromkeys(names))
        self.ramp_box.configure(values=names)
        if self.ramp.get() not in names:
            self.ramp.set(names[0] if names else '')
        self.draw_slice()
        self.draw_curves()

    def draw_slice(self):
        if not hasattr(self, 'slice_canvas'):
            return
        level = round(float(self.level.get()))
        self.slice_title.configure(text=f'L* {level} ± 2.5')
        canvas = self.slice_canvas
        canvas.delete('all')
        subsets = [lightness_slice(p.get('result', {}).get('cloud', []), level) for p in self.profiles]
        extent = max(10, max((abs(v) for s in subsets for row in s for v in row[1:]), default=0) * 1.08)
        ticks = opponent_ticks(extent)
        width, height = canvas.winfo_width(), canvas.winfo_height()
        half = max(1, min(width - 74, height - 60) / 2)
        x, y = axes(canvas, width/2-half, height/2+half, 2*half, 2*half,
                    ticks, ticks, 'a*', 'b*', opponent_grid=True)
        lines = []
        for i, s in enumerate(subsets):
            hue = hue_sectors(s, level)
            lines.append(f'{"AB"[i]}: {len(s)} model samples · maximum C* {max((chroma(p) for p in s),default=0):.1f}' if s else f'{"AB"[i]}: no model samples in this band')
            # Draw only one marker per screen pixel.
            pixels = {(round(x(a)), round(y(b))) for _,a,b in s}
            for px,py in pixels:
                canvas.create_rectangle(px,py,px+1,py+1,fill=COLOURS[i],outline='')
            if len(subsets)==2 and i==1:
                first = hue_sectors(subsets[0],level)
                diffs = [(b-a,j) for j,(a,b) in enumerate(zip(first,hue)) if a is not None and b is not None]
                if diffs:
                    hi,lo=max(diffs),min(diffs)
                    lines.append(f'Maximum C* difference by hue sector, B minus A: {lo[0]:+.1f} at {30*lo[1]}–{30*(lo[1]+1)}° to {hi[0]:+.1f} at {30*hi[1]}–{30*(hi[1]+1)}°.')
        legend(canvas, subsets)
        self.sectors.configure(text='\n'.join(lines))

    def draw_curves(self):
        if not hasattr(self, 'curve_canvas'):
            return
        canvas = self.curve_canvas
        canvas.delete('all')
        metric = self.metric.get()
        traces, notes, active = [], [], [None]*len(self.profiles)
        for i,p in enumerate(self.profiles):
            for curve in p.get('result', {}).get('curves', []):
                if curve['name'] != self.ramp.get():
                    continue
                lab = curve['lab']
                active[i]=True
                m=curve['metrics']
                notes.append(f'{"AB"[i]} · max step {m["max_delta_e76"]:.3f} ΔE76 · largest step change {m["max_step_change"]:.3f} · {m["lightness_reversals"]} L* reversals · {m["near_flat_steps"]} near-flat steps')
                channels = curve_series(lab, metric)
                traces.extend((i,j,values) for j,values in enumerate(channels))
                point = lab[128]
                notes.append(f'{"AB"[i]} at 50 %: {lab_text(point)} · C* {chroma(point):.2f}'
                             + (f' · h° {degrees(atan2(point[2], point[1])) % 360:.1f}' if chroma(point) >= 1 else ''))
        self.curve_details.configure(text='\n'.join(notes))
        values=[v for _,_,series in traces for v in series if v is not None]
        if not values:
            return
        x,y=axes(canvas,62,canvas.winfo_height()-42,max(1,canvas.winfo_width()-90),
                 max(1,canvas.winfo_height()-78), RAMP_X_TICKS, ramp_y_ticks(metric, values),
                 'Ramp position (%)', metric)
        for i,j,series in traces:
            coords=[]
            previous=None
            for k,v in enumerate([*series,None]):
                if v is None or (previous is not None and metric=='Hue h°' and abs(v-previous)>180):
                    if len(coords)>=4:
                        canvas.create_line(*coords,fill=COLOURS[i],width=1,dash=(5,3) if j else ())
                    coords=[]
                if v is not None:
                    coords.extend((x(100*k/(len(series)-1)),y(v)))
                previous=v
        legend(canvas,active)
        if metric=='a* and b*':
            canvas.create_text(70,24,text='Solid: a*   Dashed: b*',anchor='nw',fill='#334155')

    def report_filename(self, extension):
        profile = Path(self.profiles[0]['path'])
        return f'{profile.stem}_Analyze{extension}'

    def save_pdf(self):
        from analysis_pdf import save_analysis
        path = filedialog.asksaveasfilename(parent=self.root, title='Save Analysis PDF',
            initialdir=self.locations.save_directory(), initialfile=self.report_filename('.pdf'),
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
        if not path:
            return
        try:
            self.check_export_target(path, '.pdf')
            save_analysis(Path(path), self.profiles, self.reference, self.completed_mode,
                          self.summary.get('1.0', 'end-1c'), round(self.level.get()))
        except (OSError, ValueError) as error:
            messagebox.showerror('Could not save PDF', str(error), parent=self.root)
        else:
            self.locations.remember('save', path)
            self.status.set(f'Analysis PDF saved: {path}')

    def save_report(self):
        filename = filedialog.asksaveasfilename(parent=self.root, initialdir=self.locations.save_directory(), initialfile=self.report_filename('.json'),
                                               defaultextension='.json', filetypes=[('JSON', '*.json')])
        if not filename:
            return
        profiles=[]
        for p in self.profiles:
            item=dict(p)
            if 'result' in item:
                item['result']={k:v for k,v in item['result'].items() if k!='cloud'}
            profiles.append(item)
        log=dict(created=datetime.now().astimezone().isoformat(), mode=self.completed_mode, profiles=profiles,
                 measurements=self.reference, methodology='Lab D50; sampled convex hull Lab³; hue bands L* ± 2.5; 257 ramp samples; ΔE00 against measurement file.')
        try:
            self.check_export_target(filename, '.json')
            # Serialise first so a failure never leaves a half-written file.
            text = json.dumps(log,ensure_ascii=False,indent=2,allow_nan=False)
            Path(filename).write_text(text+'\n', encoding='utf-8')
        except (OSError, ValueError) as error:
            messagebox.showerror('Could not save the analysis log',str(error),parent=self.root)
        else:
            self.locations.remember('save', filename)
            self.status.set(f'Analysis log saved: {filename}')

    def check_export_target(self, filename, extension):
        path = Path(filename)
        if path.suffix.lower() != extension:
            raise ValueError(f'Use the {extension} file extension.')
        sources = self.paths + ([self.reference_path] if self.reference_path else [])
        if any(path.resolve() == source.resolve() or
               (path.exists() and source.exists() and path.samefile(source)) for source in sources):
            raise ValueError('Choose a different filename to avoid replacing an input file.')


def volume(value):
    return '–' if value is None else f'{value:,.0f}'.replace(',', ' ')


def lab_text(lab):
    return f'L* {lab_label(lab[0])}   a* {lab_label(lab[1], signed=True)}   b* {lab_label(lab[2], signed=True)}'


def axes(c,left,bottom,width,height,x_ticks,y_ticks,xlabel,ylabel,*,opponent_grid=False):
    def x(v): return left+width*(v-x_ticks[0])/(x_ticks[-1]-x_ticks[0])
    def y(v): return bottom-height*(v-y_ticks[0])/(y_ticks[-1]-y_ticks[0])
    for xv in x_ticks:
        grid = '#94a3b8' if opponent_grid and xv == 0 else '#e2e8f0'
        c.create_line(x(xv),bottom,x(xv),bottom-height,fill=grid)
        c.create_text(x(xv),bottom+12,text=tick_label(xv),fill='#334155')
    for yv in y_ticks:
        grid = '#94a3b8' if yv == 0 and y_ticks[0] < 0 < y_ticks[-1] else '#e2e8f0'
        c.create_line(left,y(yv),left+width,y(yv),fill=grid)
        c.create_text(left-7,y(yv),text=tick_label(yv),anchor='e',fill='#334155')
    c.create_text(left+width/2,bottom+28,text=xlabel,fill='#152638')
    c.create_text(left,bottom-height-15,text=ylabel,fill='#152638',anchor='w')
    return x,y


def legend(canvas, series):
    for i,data in enumerate(series):
        if data:
            canvas.create_text(canvas.winfo_width()-20-70*(1-i),12,
                               anchor='ne',text=f'Profile {"AB"[i]}',fill=COLOURS[i])


if __name__ == '__main__':
    root = tk.Tk()
    editor = Analyzer(root)
    if len(sys.argv) == 2:
        editor.paths = [Path(sys.argv[1])]
        root.after_idle(editor.run)
    root.mainloop()
