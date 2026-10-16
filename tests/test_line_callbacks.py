import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import plotly.graph_objects as go
from cachelib import SimpleCache

from callbacks.line_callbacks import (
    register_line_callbacks,
    store_sources,
    viewport_response,
)


class RecordingApp:
    def __init__(self):
        self.server_callbacks = []

    def clientside_callback(self, *args, **kwargs):
        pass

    def callback(self, *args, **kwargs):
        def record(function):
            self.server_callbacks.append(function)
            return function
        return record


def source():
    return go.Figure(go.Scattergl(x=np.arange(10000), y=np.arange(10000), mode='lines'))


class TestLineCallbacks(unittest.TestCase):
    def setUp(self):
        import callbacks
        self.cache = SimpleCache()
        fake_utils = SimpleNamespace(cache=self.cache)
        modules = patch.dict(sys.modules, {'callbacks.utils': fake_utils})
        attribute = patch.object(callbacks, 'utils', fake_utils, create=True)
        modules.start()
        attribute.start()
        self.addCleanup(modules.stop)
        self.addCleanup(attribute.stop)


    def test_viewport_response_is_partial_and_cache_miss_requests_recovery(self):
        cache = self.cache
        token = store_sources({'main': source()})
        request = {'token': token, 'generation': 'session-a', 'sequence': 2,
                   'ranges': {'main': [20, 30]}}
        result = viewport_response(request)
        operations = result['updates']['main']['patch']['operations']
        x_operation = next(op for op in operations if op['location'] == ['data', 0, 'x'])
        np.testing.assert_array_equal(x_operation['params']['value'], np.arange(19, 32))
        assert all('yaxis' not in op['location'] and 'visible' not in op['location']
                   for op in operations)
        assert 'full resolution' in result['updates']['main']['status']
        reset = viewport_response({**request, 'ranges': {}})
        reset_operations = reset['updates']['main']['patch']['operations']
        assert not any(op['location'][-1] == 'range' and op['params']['value'] is None
                       for op in reset_operations)
        cache.delete('line_source:' + token)
        assert viewport_response(request)['recover']


    def test_tokens_isolate_sessions_and_refresh_ttl(self):
        cache = self.cache
        first = store_sources({'main': source()})
        second = store_sources({'sub': source()})
        assert first != second
        result = viewport_response({'token': second, 'generation': 'b', 'sequence': 1, 'ranges': {}})
        assert set(result['updates']) == {'sub'}
        assert cache.get('line_source:' + first) is not None


    def test_initial_load_and_recovery_use_saved_selection_and_original_upload(self):

        app = RecordingApp()
        calls = []

        def builder(*args):
            calls.append(args)
            return source(), {}, go.Figure(), {'display': 'none'}

        register_line_callbacks(app, builder)
        load = app.server_callbacks[0]
        values = ['time', ['dataset'], 'receiver', '?benchmark_id=a', 0, '', '', 't', 's',
                  'original-upload', 'data.txt', None, None, '', []]
        initial = load({'generation': 'a'}, {'files': []}, None, *values)
        assert len(initial['figures']['main'].data[0].x) <= 2000
        assert initial['context']['values'][9] is None
        assert calls[0][12] is None  # current figure is never sent back
        assert calls[0][13] == 'original-upload'
        values[1] = ['unsaved-other-dataset']
        recovered = load({'generation': 'b', 'recovery': initial['context'],
                          'viewports': {'main': [20, 30]}}, {}, None, *values)
        assert calls[-1][4] == ['dataset']
        assert recovered['figures']['main'].layout.meta['line_sampling']['full_resolution']
        values[9] = 'different-upload'
        reused = load({'generation': 'c', 'recovery': initial['context']}, {}, None, *values)
        assert 'error' not in reused
        assert calls[-1][13] == 'original-upload'
        self.cache.delete('line_upload:' + initial['context']['upload_token'])
        rejected = load({'generation': 'c', 'recovery': initial['context']}, {}, None, *values)
        assert 'error' in rejected
