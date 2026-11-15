# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Display formatting shared by the dashboard and the PDF charts."""
from math import ceil


PROFILE_COLOURS = ('#c62828', '#1565c0')


def opponent_ticks(extent):
    step = max(5, 5 * ceil(extent / 10))
    return (-2 * step, -step, 0, step, 2 * step)


def tick_label(value):
    return '0' if abs(value) < 1e-12 else f'{value:.3g}'


def lightness_limits(values):
    low, high = min(values), max(values)
    return (low if low < -1e-12 else 0, high if high > 100 + 1e-12 else 100)


def lab_label(value, signed=False):
    if round(value, 2) == 0:
        return '0.00'
    return f'{value:+.2f}' if signed else f'{value:.2f}'
