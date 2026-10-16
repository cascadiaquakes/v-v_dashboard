"""Bounded, viewport-aware sampling of original line vertices.

No interpolation or averaging: every finite output vertex is an original sample.
"""

import numpy as np

POINTS_PER_CURVE = 2_000
POINTS_PER_GRAPH = 100_000


def viewport_indices(x, y, viewport=None):
    """Select intersecting segments, preserving order, boundaries and gaps."""
    x, y = np.asarray(x), np.asarray(y)
    finite = np.isfinite(x) & np.isfinite(y)
    keep = finite.copy()
    if viewport is not None:
        lo, hi = sorted(viewport)
        keep &= (x >= lo) & (x <= hi)
        # Include both vertices of segments crossing a boundary, even if
        # neither endpoint lies in the viewport (parametric curves included).
        intersect = (finite[:-1] & finite[1:]
                     & (np.minimum(x[:-1], x[1:]) <= hi)
                     & (np.maximum(x[:-1], x[1:]) >= lo))
        keep[:-1] |= intersect
        keep[1:] |= intersect
    indices = np.flatnonzero(keep)
    if not len(indices):
        return indices
    # -1 represents an explicit break, including excursions outside the view.
    breaks = np.flatnonzero(np.diff(indices) > 1) + 1
    return np.insert(indices, breaks, -1)


def sample_indices(x, y, budget, viewport=None):
    """Bucket in source order; retain endpoints and local extrema within budget.

    Extremely fragmented data can have more gaps than the entire budget. In
    that case, select representative runs and separate them explicitly rather
    than falsely connecting disconnected runs.
    """
    candidates = viewport_indices(x, y, viewport)
    available = int(np.count_nonzero(candidates >= 0))
    if budget < 1:
        return np.empty(0, dtype=int), available
    if len(candidates) <= budget:
        return candidates, available
    runs = np.split(candidates, np.flatnonzero(candidates == -1))
    runs = [run[run >= 0] for run in runs if np.any(run >= 0)]
    # Reserve endpoints and separators before allocating interior samples.
    max_runs = max(1, (budget + 1) // 3)
    if len(runs) > max_runs:
        selected = np.unique(np.linspace(0, len(runs) - 1, max_runs, dtype=int))
        runs = [runs[i] for i in selected]
    remaining = budget - (len(runs) - 1)
    allocations = np.minimum([len(run) for run in runs], 2)
    if allocations.sum() > remaining:  # budgets of one or two
        return runs[0][:remaining], available
    spare = remaining - int(allocations.sum())
    capacities = np.array([len(run) for run in runs]) - allocations
    # Allocate proportionally, then distribute rounding leftovers.
    if capacities.sum() and spare:
        extras = np.minimum(capacities, (spare * capacities / capacities.sum()).astype(int))
        allocations += extras
        spare -= int(extras.sum())
        for i in np.flatnonzero(allocations < np.array([len(run) for run in runs])):
            if not spare:
                break
            allocations[i] += 1
            spare -= 1
    result = []
    y = np.asarray(y)
    for run, count in zip(runs, allocations, strict=True):
        if result:
            result.append(-1)
        if len(run) <= count:
            result.extend(run)
            continue
        chosen = [run[0], run[-1]]
        # Each bucket consumes at most four slots. Preserve first/last as
        # well as extrema, ordered by original index, never by x coordinate.
        buckets = (int(count) - 2) // 4
        if buckets:
            for bucket in np.array_split(run[1:-1], buckets):
                if len(bucket):
                    values = y[bucket]
                    chosen.extend([bucket[0], bucket[-1],
                                   bucket[np.argmin(values)], bucket[np.argmax(values)]])
        else:
            interior = run[1:-1]
            if count >= 3 and len(interior):
                chosen.append(interior[np.argmax(np.abs(y[interior] - y[run[0]]))])
            if count >= 4 and len(interior):
                chosen.extend([interior[np.argmin(y[interior])]])
        result.extend(sorted(set(chosen)))
    return np.asarray(result, dtype=int), available


def sample_arrays(x, y, budget, viewport=None):
    indices, available = sample_indices(x, y, budget, viewport)
    valid = indices >= 0
    sx, sy = np.full(len(indices), np.nan), np.full(len(indices), np.nan)
    sx[valid], sy[valid] = np.asarray(x)[indices[valid]], np.asarray(y)[indices[valid]]
    return sx, sy, available


def sample_figure(source, viewport=None, per_curve=POINTS_PER_CURVE, total=POINTS_PER_GRAPH):
    """Copy a Plotly figure, replacing only line arrays and adding count metadata."""
    import plotly.graph_objects as go

    fig = go.Figure(source)
    lines = [trace for trace in fig.data
             if trace.type in ('scatter', 'scattergl') and trace.mode == 'lines']
    budget = min(per_curve, total // len(lines)) if lines else per_curve
    displayed = available = 0
    full = True
    for trace in lines:
        sx, sy, count = sample_arrays(trace.x, trace.y, budget, viewport)
        trace.x, trace.y = sx, sy
        shown = int(np.count_nonzero(np.isfinite(sx)))
        displayed += shown
        available += count
        full &= shown == count
    fig.update_layout(meta={**(fig.layout.meta or {}), 'line_sampling': {
        'displayed': displayed, 'available': available, 'full_resolution': full,
    }})
    return fig
