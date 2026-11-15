# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""ICC metadata and sampled device-to-Lab diagnostics."""
import ctypes as C
from ctypes.util import find_library
from contextlib import ExitStack
from hashlib import sha256
from itertools import product
from math import atan2, degrees, dist, hypot, isfinite
from pathlib import Path
from statistics import median
import struct
import shlex
import numpy as np
from scipy.spatial import ConvexHull, QhullError
from colour_math import delta_e00, xyz_to_lab
import sys

FORMATS = {'RGB ': (4, 3, 1), 'GRAY': (3, 1, 1), 'CMYK': (6, 4, 100)}
INTENTS = {'Absolute colorimetric': 3, 'Relative colorimetric': 1}
RAMPS = {
    'RGB ': [('Neutral RGB', (1, 1, 1)), ('Red', (1, 0, 0)), ('Green', (0, 1, 0)),
             ('Blue', (0, 0, 1)), ('Cyan', (0, 1, 1)), ('Magenta', (1, 0, 1)), ('Yellow', (1, 1, 0))],
    'GRAY': [('Gray', (1,))],
    'CMYK': [('Black (K)', (0, 0, 0, 1)), ('Cyan', (1, 0, 0, 0)), ('Magenta', (0, 1, 0, 0)),
             ('Yellow', (0, 0, 1, 0)), ('C+M+Y', (1, 1, 1, 0))],
}


def signature(data):
    return data.decode('ascii', errors='replace')


def metadata(data):
    if len(data) < 132 or data[36:40] != b'acsp':
        raise ValueError('The file has no valid ICC header.')
    if data[8] not in (2, 4):
        raise ValueError('Only ICC versions 2 and 4 are supported.')
    size = struct.unpack_from('>I', data)[0]
    count = struct.unpack_from('>I', data, 128)[0]
    end = 132 + count * 12
    if not end <= size <= len(data):
        raise ValueError('The ICC profile size or tag table is invalid.')
    tags = []
    names = set()
    for tag, offset, length in struct.iter_unpack('>4sII', data[132:end]):
        if tag in names or offset < end or length < 8 or offset + length > size:
            raise ValueError(f'Invalid ICC tag: {signature(tag)}.')
        names.add(tag)
        block = data[offset:offset + length]
        entry = dict(tag=signature(tag), type=signature(block[:4]), offset=offset,
                     bytes=length, sha256=sha256(block).hexdigest())
        if block[:4] == b'XYZ ' and (length - 8) % 12 == 0:
            entry['XYZ'] = [[x / 65536 for x in row] for row in struct.iter_unpack('>iii', block[8:])]
        if tag in (b'desc', b'cprt'):
            entry['text'] = tag_text(block)
        tags.append(entry)
    return dict(version=f'{data[8]}.{data[9] >> 4}.{data[9] & 15}',
                profile_class=signature(data[12:16]), colour_space=signature(data[16:20]),
                pcs=signature(data[20:24]), header_intent=struct.unpack_from('>I', data, 64)[0],
                profile_id=data[84:100].hex() if data[8] == 4 else None,
                declared_bytes=size, file_bytes=len(data), sha256=sha256(data).hexdigest(), tags=tags)


def tag_text(block):
    if block[:4] == b'text':
        return block[8:].rstrip(b'\0').decode('ascii', errors='replace')
    if block[:4] == b'desc' and len(block) >= 12:
        count = struct.unpack_from('>I', block, 8)[0]
        return block[12:12 + count].rstrip(b'\0').decode('ascii', errors='replace')
    if block[:4] == b'mluc' and len(block) >= 16:
        count, stride = struct.unpack_from('>II', block, 8)
        if stride < 12 or 16 + count * stride > len(block):
            return None
        result = {}
        for index in range(count):
            locale, length, offset = struct.unpack_from('>4sII', block, 16 + index * stride)
            if length % 2 == 0 and 16 + count * stride <= offset <= len(block) - length:
                result[signature(locale)] = block[offset:offset + length].decode('utf-16-be', errors='replace')
        return result
    return None


class ColourEngine:
    def __init__(self):
        bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'liblcms2.2.dylib'
        candidates = (str(bundled), '/opt/homebrew/lib/liblcms2.2.dylib',
                      '/usr/local/lib/liblcms2.2.dylib', find_library('lcms2'))
        for path in filter(None, candidates):
            try:
                self.lib = C.CDLL(path)
                break
            except OSError:
                continue
        else:
            raise OSError('LittleCMS 2 is unavailable for this processor. Use the macOS app or install lcms2.')
        pointer, integer = C.c_void_p, C.c_uint32
        declarations = {
            'cmsGetEncodedCMMversion': ([], integer),
            'cmsOpenProfileFromMem': ([pointer, integer], pointer),
            'cmsCreate_sRGBProfile': ([], pointer),
            'cmsCreateLab4Profile': ([pointer], pointer),
            'cmsCreateTransform': ([pointer, integer, pointer, integer, integer, integer], pointer),
            'cmsDoTransform': ([pointer, pointer, pointer, integer], None),
            'cmsDeleteTransform': ([pointer], None),
            'cmsCloseProfile': ([pointer], C.c_int),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result

    def convert(self, data, space, intent, points):
        colour, channels, scale = FORMATS[space]
        def pixel_type(colour_id, count):
            return (1 << 22) | (colour_id << 16) | (count << 3)
        lib = self.lib
        source = (C.c_double * (len(points) * channels))(*(v * scale for row in points for v in row))
        output = (C.c_double * (len(points) * 3))()
        with ExitStack() as cleanup:
            buffer = C.create_string_buffer(data)
            profile = lib.cmsOpenProfileFromMem(buffer, len(data))
            if not profile:
                raise ValueError('LittleCMS could not read the profile.')
            cleanup.callback(lib.cmsCloseProfile, profile)
            lab = lib.cmsCreateLab4Profile(None)
            if not lab:
                raise ValueError('LittleCMS could not create a Lab D50 profile.')
            cleanup.callback(lib.cmsCloseProfile, lab)
            transform = lib.cmsCreateTransform(profile, pixel_type(colour, channels),
                                               lab, pixel_type(10, 3), intent, 0x0140)
            if not transform:
                raise ValueError('The selected colorimetric conversion to Lab is unavailable.')
            cleanup.callback(lib.cmsDeleteTransform, transform)
            lib.cmsDoTransform(transform, source, output, len(points))
        if not all(map(isfinite, output)):
            raise ValueError('The conversion returned invalid Lab values.')
        return list(zip(output[0::3], output[1::3], output[2::3]))


def ramp_metrics(lab, expected_direction):
    steps = [dist(a, b) for a, b in zip(lab, lab[1:])]
    delta_l = [expected_direction * (b[0] - a[0]) for a, b in zip(lab, lab[1:])]
    jitter = [abs(b - a) for a, b in zip(steps, steps[1:])]
    reversals = [i for i, value in enumerate(delta_l) if value < -0.02]
    return dict(median_delta_e76=median(steps), max_delta_e76=max(steps),
                max_step_change=max(jitter), lightness_reversals=len(reversals),
                largest_reversal=max((-delta_l[i] for i in reversals), default=0),
                near_flat_steps=sum(value < 0.01 for value in steps))


def analyse(data, info, intent):
    space = info['colour_space']
    if space not in FORMATS or info['profile_class'] in ('link', 'nmcl', 'abst'):
        raise ValueError('Curve analysis requires an RGB, CMYK or grayscale device profile. The tag log is available.')
    _, channels, _ = FORMATS[space]
    grid = {1: 257, 3: 41, 4: 15}[channels]
    points = list(product((i / (grid - 1) for i in range(grid)), repeat=channels))
    # Exclude heavy CMYK combinations from the sample and report the exact cap.
    limit = 3.0 if space == 'CMYK' else None
    if limit is not None:
        points = [row for row in points if sum(row) <= limit + 1e-10]
    size = len(points)
    for _, endpoint in RAMPS[space]:
        points.extend(tuple(value * i / 256 for value in endpoint) for i in range(257))
    engine = ColourEngine()
    lab = engine.convert(data, space, intent, points)
    zero = lab[size]
    neutral_end = lab[size + 256]
    white, black = (zero, neutral_end) if space == 'CMYK' else (neutral_end, zero)
    curves = []
    for index, (name, _) in enumerate(RAMPS[space]):
        start = size + index * 257
        samples = lab[start:start + 257]
        curves.append(dict(name=name, lab=samples,
                           metrics=ramp_metrics(samples, -1 if space == 'CMYK' else 1)))
    return dict(intent=intent, engine_version=engine.lib.cmsGetEncodedCMMversion(),
                white=white, black=black, black_definition='100 % K' if limit else '0% on all channels',
                grid=grid, total_ink_limit_percent=None if limit is None else 100 * limit,
                sample_count=size, cloud=lab[:size], curves=curves)


def lightness_slice(cloud, lightness, half_width=2.5):
    return [row for row in cloud if abs(row[0] - lightness) <= half_width]


def chroma(lab):
    return hypot(lab[1], lab[2])


def hull_volume(cloud):
    if len(cloud) < 4:
        return None
    try:
        return float(ConvexHull(cloud).volume)
    except QhullError:
        return None


def measurement_file(path):
    raw = path.read_bytes()
    try:
        lines = raw.decode('utf-8-sig').splitlines()
    except UnicodeDecodeError:
        lines = raw.decode('latin-1').splitlines()
    lines = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
    try:
        start = lines.index('BEGIN_DATA_FORMAT')
        end = lines.index('END_DATA_FORMAT', start)
        fields = shlex.split(' '.join(lines[start + 1:end]))
        start = lines.index('BEGIN_DATA', end)
        end = lines.index('END_DATA', start)
    except ValueError:
        raise ValueError('The CGATS file is missing a complete data format or data block.') from None
    rgb = ['RGB_R', 'RGB_G', 'RGB_B']
    lab = ['LAB_L', 'LAB_A', 'LAB_B']
    xyz = ['XYZ_X', 'XYZ_Y', 'XYZ_Z']
    colour = lab if set(lab) <= set(fields) else xyz
    if not set(rgb + colour) <= set(fields):
        raise ValueError('The measurement file must contain device RGB (0–100) and Lab or XYZ (D50, Y scale 0–100).')
    indices = [fields.index(key) for key in rgb + colour]
    rows = [shlex.split(line, comments=True) for line in lines[start + 1:end]]
    if not rows or any(len(row) != len(fields) for row in rows):
        raise ValueError('A measurement row has missing or extra fields.')
    samples = np.array([[float(row[i]) for i in indices] for row in rows])
    if not np.isfinite(samples).all() or np.any((samples[:, :3] < 0) | (samples[:, :3] > 100)):
        raise ValueError('The measurement file contains invalid RGB or measurement values.')
    measured = samples[:, 3:] if colour == lab else xyz_to_lab(samples[:, 3:])
    return dict(file=str(path), sha256=sha256(raw).hexdigest(), space='Lab D50' if colour == lab else 'XYZ D50 (Y=100)',
                rgb=(samples[:, :3] / 100).tolist(), lab=measured)


def measurement_fit(data, reference):
    predicted = np.array(ColourEngine().convert(data, 'RGB ', 3, reference['rgb']))
    lab = reference['lab']
    errors = delta_e00(predicted, lab)
    result = dict(count=len(errors), mean=float(errors.mean()),
                  p95=float(np.percentile(errors, 95)), max=float(errors.max()))
    measured_c = np.hypot(lab[:, 1], lab[:, 2])
    saturated = measured_c >= 35
    if saturated.any():
        predicted_c = np.hypot(predicted[:, 1], predicted[:, 2])
        result['saturated_bias'] = dict(count=int(saturated.sum()),
            delta_l=float((predicted[:, 0]-lab[:, 0])[saturated].mean()),
            delta_c=float((predicted_c-measured_c)[saturated].mean()))
    white = np.all(np.asarray(reference['rgb']) >= 0.999999, axis=1)
    if white.any():
        result['measured_white'] = lab[white].mean(axis=0).tolist()
    for key, mask in [('shadows', lab[:, 0] <= 30), ('neutrals', np.hypot(lab[:, 1], lab[:, 2]) <= 5)]:
        result[key] = dict(count=int(mask.sum()), mean=float(errors[mask].mean())) if mask.any() else None
    return result


def hue_sectors(cloud, lightness):
    points = np.asarray(lightness_slice(cloud, lightness))
    if not len(points):
        return [None] * 12
    c = np.hypot(points[:, 1], points[:, 2])
    sector = (np.degrees(np.arctan2(points[:, 2], points[:, 1])) % 360 // 30).astype(int)
    return [float(c[sector == i].max()) if np.any(sector == i) else None for i in range(12)]


def source_ramps(data, space, intent, bpc):
    """sRGB -> device -> absolute Lab using LittleCMS. Includes B2A mapping."""
    engine = ColourEngine()
    lib = engine.lib
    colour, channels, scale = FORMATS[space]
    rgb_type = (1 << 22) | (4 << 16) | (3 << 3)
    device_type = (1 << 22) | (colour << 16) | (channels << 3)
    paths = [(name, endpoint, (0, 0, 0)) for name, endpoint in RAMPS['RGB ']]
    paths += [('White to ' + name.lower(), endpoint, (1, 1, 1)) for name, endpoint in RAMPS['RGB '][1:]]
    points = [tuple(a+(b-a)*i/256 for a,b in zip(start,end))
              for _,end,start in paths for i in range(257)]
    source = (C.c_double * (3 * len(points)))(*(v for p in points for v in p))
    device = (C.c_double * (channels * len(points)))()
    with ExitStack() as cleanup:
        buffer = C.create_string_buffer(data)
        srgb = lib.cmsCreate_sRGBProfile()
        if not srgb:
            raise ValueError('LittleCMS could not create an sRGB profile.')
        cleanup.callback(lib.cmsCloseProfile, srgb)
        profile = lib.cmsOpenProfileFromMem(buffer, len(data))
        if not profile:
            raise ValueError('LittleCMS could not read the profile.')
        cleanup.callback(lib.cmsCloseProfile, profile)
        transform = lib.cmsCreateTransform(srgb, rgb_type, profile, device_type,
                                           intent, 0x0140 | (0x2000 if bpc else 0))
        if not transform:
            raise ValueError('The selected rendering intent could not be used to convert sRGB to device values.')
        cleanup.callback(lib.cmsDeleteTransform, transform)
        lib.cmsDoTransform(transform, source, device, len(points))
    # Float transforms through matrix profiles are unbounded; keep to what the device can produce.
    values = [tuple(min(1, max(0, v/scale)) for v in device[i:i+channels]) for i in range(0,len(device),channels)]
    labs = engine.convert(data, space, 3, values)
    ramps = []
    for index, (name, _, _) in enumerate(paths):
        part = labs[index*257:(index+1)*257]
        direction = 1 if part[-1][0]>=part[0][0] else -1
        ramps.append(dict(name=name, lab=part, metrics=ramp_metrics(part,direction)))
    return ramps


def curve_series(lab, metric):
    if metric == 'L*':
        return [[row[0] for row in lab]]
    if metric == 'a* and b*':
        return [[row[i] for row in lab] for i in (1, 2)]
    if metric == 'Chroma C*':
        return [[chroma(row) for row in lab]]
    if metric == 'Hue h°':
        return [[degrees(atan2(row[2], row[1])) % 360 if chroma(row) >= 1 else None for row in lab]]
    if metric == 'Step ΔE76':
        return [[dist(a, b) for a, b in zip(lab, lab[1:])]]
    raise ValueError(f'Unknown curve metric: {metric}')
