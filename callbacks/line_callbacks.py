"""Server-side originals and guarded client-side figure updates for line plots."""

import hashlib
import uuid

import plotly.graph_objects as go
from dash import ClientsideFunction, Input, Output, Patch, State

from callbacks.line_sampling import sample_figure

SOURCE_TTL = 3600


def _upload_digest(contents):
    return hashlib.sha256((contents or '').encode()).hexdigest()


def _status(figure):
    info = (figure.layout.meta or {}).get('line_sampling') or {}
    if not info or not any(t.type in ('scatter', 'scattergl') and t.mode == 'lines'
                           for t in figure.data):
        return ''
    detail = 'full resolution' if info['full_resolution'] else 'zoom in for more detail'
    return f"{info['displayed']:,} / {info['available']:,} samples — {detail}"


def store_sources(figures):
    from callbacks.utils import cache

    token = uuid.uuid4().hex
    # The cache is server-side only, shared with revision-aware source loading.
    # Plotly 6's to_dict/pickle encode arrays as binary JSON dictionaries.
    # Put the original arrays back before caching so they remain sampleable.
    sources = {}
    for name, fig in figures.items():
        packed = fig.to_dict()
        for original, trace in zip(fig.data, packed['data'], strict=True):
            if original.type in ('scatter', 'scattergl') and original.mode == 'lines':
                trace['x'], trace['y'] = original.x, original.y
        sources[name] = packed
    cache.set('line_source:' + token, sources, timeout=SOURCE_TTL)
    return token


def viewport_response(request):
    from callbacks.utils import cache

    result = {key: request[key] for key in ('generation', 'sequence')}
    key = 'line_source:' + request['token']
    sources = cache.get(key)
    if sources is None:
        return {**result, 'recover': True}
    cache.set(key, sources, timeout=SOURCE_TTL)
    upload_token = request.get('upload_token')
    if upload_token:
        upload_key = 'line_upload:' + upload_token
        contents = cache.get(upload_key)
        if contents is not None:
            cache.set(upload_key, contents, timeout=SOURCE_TTL)
    updates = {}
    for name, source in sources.items():
        source = go.Figure(source)
        sampled = sample_figure(source, request.get('ranges', {}).get(name))
        updates[name] = {'patch': _viewport_patch(source, sampled,
                                               request.get('ranges', {}).get(name)),
                         'status': _status(sampled)}
    return {**result, 'updates': updates}


def _viewport_patch(source, sampled, viewport):
    patch = Patch()
    for i, trace in enumerate(sampled.data):
        if trace.type in ('scatter', 'scattergl') and trace.mode == 'lines':
            patch['data'][i]['x'] = trace.x
            patch['data'][i]['y'] = trace.y
    patch['layout']['meta'] = sampled.layout.meta
    # Explicit ranges preserve the user's view during data replacement. Other
    # layout fields (including manual y ranges and legend state) are untouched.
    for name in source.layout:
        if name.startswith('xaxis') and source.layout[name] is not None:
            if viewport is None:
                patch['layout'][name]['autorange'] = True
            else:
                patch['layout'][name]['range'] = viewport
                patch['layout'][name]['autorange'] = False
    return patch.to_plotly_json()


def register_line_callbacks(app, build_plots):
    app.clientside_callback(
        ClientsideFunction(namespace='linePlots', function_name='loadRequest'),
        Output('plot-load-request', 'data'),
        Input('show-graphs', 'n_clicks'), Input('update-graphs', 'n_clicks'),
        Input('benchmark-params', 'data'), Input('plot-recover', 'data'),
    )

    # Positional order matches the existing plot builder. Full-resolution line arrays
    # are deliberately absent from callback State and all browser stores.
    controls = [
        ('file-type-selector', 'value'), ('dataset-choice', 'value'),
        ('receiver-selector', 'value'), ('url', 'search'),
        ('slider-gc-surface', 'value'), ('surface-plot-type', 'value'),
        ('surface-plot-var', 'value'), ('time-xaxis-var', 'value'),
        ('time-axis-unit', 'value'), ('upload-data', 'contents'),
        ('upload-data', 'filename'), ('colorbar-min', 'value'),
        ('colorbar-max', 'value'), ('surface-cross-axis', 'value'),
        ('surface-switch-axis', 'value'),
    ]

    @app.callback(
        Output('plot-load-response', 'data'), Input('plot-load-request', 'data'),
        State('benchmark-params', 'data'), State('plot-state', 'data'),
        *[State(component, prop) for component, prop in controls],
        prevent_initial_call=True,
    )
    def load(request, params, previous_state, *values):
        from callbacks.utils import cache

        if not request:
            return {}
        values = list(values)
        recovery = request.get('recovery')
        if recovery:
            saved_upload = cache.get('line_upload:' + recovery.get('upload_token', ''))
            if saved_upload is not None:
                upload = saved_upload
            elif recovery['upload_digest'] == _upload_digest(values[9]):
                upload = values[9]
            else:
                return {'generation': request['generation'], 'error':
                        'Plot data expired and the upload changed. Select Show Graphs to reload.'}
            values = list(recovery['values'])
            values[9] = upload
            params = recovery['params']
        context_values = list(values)
        context_values[9] = None
        upload_token = uuid.uuid4().hex if values[9] is not None else ''
        if upload_token:
            cache.set('line_upload:' + upload_token, values[9], timeout=SOURCE_TTL)
        context = {'params': params, 'values': context_values,
                   'upload_digest': _upload_digest(values[9]), 'upload_token': upload_token}
        # The legacy builder accepts a current figure between units and upload;
        # it does not use it. Keep that internal call compatible without sending
        # the displayed figure back to the server on every request.
        args = values[:9] + [None] + values[9:]
        main, main_style, sub, sub_style = build_plots(1, 1, params, *args)
        sources = {'main': go.Figure(main), 'sub': go.Figure(sub)}
        token = store_sources({name: fig for name, fig in sources.items()
                               if any(t.mode == 'lines' for t in fig.data
                                      if t.type in ('scatter', 'scattergl'))})
        if previous_state and previous_state.get('token'):
            cache.delete('line_source:' + previous_state['token'])
            previous_upload = previous_state.get('context', {}).get('upload_token')
            if previous_upload:
                cache.delete('line_upload:' + previous_upload)
        figures = {name: sample_figure(fig, request.get('viewports', {}).get(name))
                   for name, fig in sources.items()}
        revision = request.get('uirevision', request['generation'])
        for name, fig in figures.items():
            fig.update_layout(uirevision=revision)
            viewport = request.get('viewports', {}).get(name)
            if viewport is not None:
                fig.update_xaxes(range=viewport, autorange=False)
        return {'generation': request['generation'], 'token': token,
                'uirevision': revision,
                'recovered': bool(recovery),
                'context': context, 'figures': figures,
                'styles': {'main': main_style, 'sub': sub_style},
                'statuses': {name: _status(fig) for name, fig in figures.items()}}

    app.clientside_callback(
        ClientsideFunction(namespace='linePlots', function_name='viewportRequest'),
        Output('plot-viewport-request', 'data'),
        Input('main-graph', 'relayoutData'), Input('sub-graph', 'relayoutData'),
        State('plot-state', 'data'), prevent_initial_call=True,
    )

    @app.callback(Output('plot-viewport-response', 'data'),
                  Input('plot-viewport-request', 'data'), prevent_initial_call=True)
    def viewport(request):
        return viewport_response(request) if request else {}

    # This is the sole writer of both graph figures. It gates all server
    # responses against the most recently issued generation and viewport.
    app.clientside_callback(
        ClientsideFunction(namespace='linePlots', function_name='applyResponse'),
        Output('main-graph', 'figure'), Output('main-graph', 'style'),
        Output('sub-graph', 'figure'), Output('sub-graph', 'style'),
        Output('plot-state', 'data'), Output('main-line-status', 'children'),
        Output('sub-line-status', 'children'),
        Input('plot-load-response', 'data'), Input('plot-viewport-response', 'data'),
        State('plot-state', 'data'), State('main-graph', 'figure'),
        State('sub-graph', 'figure'), prevent_initial_call=True,
    )
