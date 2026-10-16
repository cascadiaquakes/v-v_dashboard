"""Offline browser fixture: python -m tests.line_sampling_app."""

import os

os.environ.setdefault('AWS_EC2_METADATA_DISABLED', 'true')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-west-2')

import dash
import numpy as np
import pandas as pd
from dash import dcc, html
from flask_caching import Cache

from callbacks.line_callbacks import register_line_callbacks
from callbacks.plots import cross_section_plots, main_time_plot_dynamic
from callbacks.utils import set_cache

app = dash.Dash(__name__, assets_folder=os.path.abspath('assets'))
cache = Cache(app.server, config={'CACHE_TYPE': 'SimpleCache'})
set_cache(cache)
variables = [{'name': 't', 'unit': 's', 'description': 'Time'},
             {'name': 'v', 'unit': 'm', 'description': 'Value'},
             {'name': 'w', 'unit': 'm2', 'description': 'Squared value'}]
app.layout = html.Div([
    html.Button('Show Graphs', id='show-graphs'),
    html.Button('Update Graphs', id='update-graphs'),
    dcc.Dropdown(id='dataset-choice', options=['one', 'two'], value=['one'], multi=True),
    dcc.Dropdown(id='time-axis-unit', options=['s', 'min'], value='s'),
    dcc.Graph(id='main-graph'), html.Div(id='main-line-status'),
    dcc.Graph(id='sub-graph'), html.Div(id='sub-line-status'),
    dcc.Location(id='url'), dcc.Upload(id='upload-data'),
    dcc.Store(id='benchmark-params', data={'files': []}),
    *[dcc.Store(id=name) for name in ['plot-load-request', 'plot-load-response',
      'plot-viewport-request', 'plot-viewport-response', 'plot-state', 'plot-recover']],
    *[dcc.Input(id=name, value=value) for name, value in [
      ('file-type-selector', 'line'), ('receiver-selector', 'receiver'),
      ('slider-gc-surface', 0), ('surface-plot-type', ''), ('surface-plot-var', 'v'),
      ('time-xaxis-var', 't'), ('colorbar-min', 0), ('colorbar-max', 1),
      ('surface-cross-axis', 'slice')]],
    dcc.Checklist(id='surface-switch-axis', options=[], value=[]),
])


def build(*args):
    unit = args[11]
    datasets = args[4] or ['one']
    frames = []
    for i, dataset in enumerate(datasets):
        t = np.arange(100_000, dtype=float)
        v = np.sin(t / 100) + i
        v[50000] = 15 + i
        frames.append(pd.DataFrame({'t': t, 'v': v, 'w': v ** 2,
                                    'slice': 0, 'dataset_name': dataset}))
    df = pd.concat(frames, ignore_index=True)
    main, style = main_time_plot_dynamic(df, variables, time_axis_unit=unit, sampling=False)
    sub = cross_section_plots(df, variables[1], axes=('t', 'slice'), cross_axis='slice',
                              time_axis_unit=unit, sampling=False)
    return main, style, sub, {'display': 'block', 'height': '50vh'}


register_line_callbacks(app, build)


@app.server.post('/expire-plot-cache')
def expire():
    cache.clear()
    return {'expired': True}


if __name__ == '__main__':
    app.run(port=8057, debug=False)
