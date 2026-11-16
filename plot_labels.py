# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Display formatting shared by the dashboard and the PDF charts."""
from math import ceil, floor, log10


PROFILE_COLOURS = ('#c62828', '#1565c0')
RAMP_X_TICKS = tuple(range(0, 101, 20))


def opponent_ticks(extent):
    step = max(5, 5 * ceil(extent / 10))
    return (-2 * step, -step, 0, step, 2 * step)


def tick_label(value):
    return '0' if abs(value) < 1e-12 else f'{value:.3g}'


def ramp_y_ticks(metric, values):
    if metric == 'Hue h°':
        return (0, 90, 180, 270, 360)

    low, high = min(values), max(values)
    if metric == 'L*':
        low = 0 if low >= -1e-12 else low
        high = 100 if high <= 100 + 1e-12 else high
    low = min(low, 0)
    high = max(high, .01)

    target = (high - low) / 4
    magnitude = 10 ** floor(log10(target))
    # Round both ends outward while keeping at most five labelled positions.
    for factor in (1, 2, 2.5, 5, 10, 20):
        step = factor * magnitude
        first, last = floor(low / step), ceil(high / step)
        if last - first <= 4:
            return tuple(i * step for i in range(first, last + 1))


def lab_label(value, signed=False):
    if round(value, 2) == 0:
        return '0.00'
    return f'{value:+.2f}' if signed else f'{value:.2f}'
