"""Offline diagnostic: python -m tests.benchmark_line_sampling."""

import json
from time import perf_counter

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from callbacks.line_sampling import sample_figure


def run(points, curves):
    x = np.arange(points, dtype=float)
    source = go.Figure()
    for curve in range(curves):
        y = np.sin(x / 100 + curve)
        y[points // 2] = 10 + curve
        source.add_scattergl(x=x, y=y, mode='lines')
    started = perf_counter()
    overview = sample_figure(source)
    overview_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    detail = sample_figure(source, (points // 2 - 50, points // 2 + 50))
    detail_ms = (perf_counter() - started) * 1000
    return {'source_points': points * curves, 'curves': curves,
            'overview_points': sum(len(t.x) for t in overview.data),
            'overview_ms': round(overview_ms, 1), 'zoom_ms': round(detail_ms, 1),
            'source_json_bytes': len(pio.to_json(source).encode()),
            'overview_json_bytes': len(pio.to_json(overview).encode()),
            'zoom_full_resolution': detail.layout.meta['line_sampling']['full_resolution']}


if __name__ == '__main__':
    sample_figure(go.Figure())  # warm Plotly's validators
    for points, curves in [(1_000_000, 1), (1_000_000, 4), (20_000, 60)]:
        print(json.dumps(run(points, curves)), flush=True)
