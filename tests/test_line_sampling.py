import unittest
from itertools import pairwise

import numpy as np
import plotly.graph_objects as go

from callbacks.line_sampling import sample_arrays, sample_figure, viewport_indices


class TestLineSampling(unittest.TestCase):
    def test_overview_preserves_peaks_and_endpoints(self):
        x = np.arange(100_000, dtype=float)
        y = np.zeros_like(x)
        y[12345], y[54321] = 100, -90
        sx, sy, available = sample_arrays(x, y, 2000)
        assert len(sx) <= 2000
        assert available == len(x)
        assert sx[0] == 0 and sx[-1] == x[-1]
        assert sy.max() == 100 and sy.min() == -90
        assert np.all(np.diff(sx) > 0)


    def test_zoom_recovers_exact_samples_and_boundary_neighbors(self):
        x = np.arange(100_000, dtype=float)
        sx, sy, count = sample_arrays(x, x ** 2, 2000, (500.25, 510.75))
        np.testing.assert_array_equal(sx, np.arange(500, 512))
        np.testing.assert_array_equal(sy, sx ** 2)
        assert count == 12


    def test_segment_crossing_viewport_without_vertex_inside(self):
        sx, sy, count = sample_arrays([0, 100], [2, 4], 2000, (40, 60))
        np.testing.assert_array_equal(sx, [0, 100])
        np.testing.assert_array_equal(sy, [2, 4])
        assert count == 2


    def test_parametric_curve_keeps_original_order_and_separates_excursions(self):
        x = np.array([0, 5, 10, 20, 30, 20, 10, 5, 0])
        y = np.arange(len(x))
        sx, sy, _ = sample_arrays(x, y, 2000, (4, 6))
        np.testing.assert_array_equal(sx, [0, 5, 10, np.nan, 10, 5, 0])
        np.testing.assert_array_equal(sy, [0, 1, 2, np.nan, 6, 7, 8])


    def test_gaps_are_not_connected_and_duplicates_are_retained(self):
        x = [0, 1, 1, 2, 3, 4]
        y = [0, 2, 3, np.nan, 5, 6]
        sx, sy, count = sample_arrays(x, y, 2000)
        np.testing.assert_array_equal(sx, [0, 1, 1, np.nan, 3, 4])
        assert count == 5
        assert np.isnan(sy[3])


    def check_fragmented_inputs(self, budget):
        x = np.arange(10000, dtype=float)
        y = np.sin(x)
        y[2::3] = np.nan
        sx, sy, _ = sample_arrays(x, y, budget)
        assert len(sx) <= budget
        valid = np.flatnonzero(np.isfinite(sx))
        for first, second in pairwise(valid):
            if second == first + 1:
                assert sx[second] == sx[first] + 1
        assert len(sy) == len(sx)


    def test_empty_outside_and_reversed_ranges(self):
        assert len(viewport_indices([], [], (0, 1))) == 0
        assert len(viewport_indices([1, 2], [3, 4], (10, 20))) == 0
        np.testing.assert_array_equal(viewport_indices([1, 2, 3], [3, 4, 5], (3, 1)), [0, 1, 2])


    def test_total_budget_independent_variable_sampling_and_unchanged_sources(self):
        x = np.arange(10_000)
        source = go.Figure()
        for i in range(6):
            y = np.zeros(len(x))
            y[100 + i * 1000] = 100 + i
            source.add_scattergl(x=x, y=y, mode='lines', name=str(i))
        sampled = sample_figure(source, per_curve=2000, total=6000)
        assert sum(len(t.x) for t in sampled.data) <= 6000
        assert all(max(t.y) == 100 + i for i, t in enumerate(sampled.data))
        assert len(source.data[0].x) == 10_000
        assert not sampled.layout.meta['line_sampling']['full_resolution']
        detail = sample_figure(source, viewport=(90, 110), total=6000)
        assert detail.layout.meta['line_sampling']['full_resolution']


    def test_scatter_and_surface_arrays_unchanged(self):
        source = go.Figure([go.Scattergl(x=np.arange(5000), y=np.arange(5000), mode='markers'),
                            go.Surface(z=[[1, 2], [3, 4]])])
        result = sample_figure(source)
        np.testing.assert_array_equal(result.data[0].x, source.data[0].x)
        np.testing.assert_array_equal(result.data[1].z, source.data[1].z)

    def test_fragmented_inputs_still_obey_hard_budget(self):
        for budget in [0, 1, 2, 3, 4, 5, 10, 100, 2000]:
            with self.subTest(budget=budget):
                self.check_fragmented_inputs(budget)
