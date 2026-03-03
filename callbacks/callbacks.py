import dash
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from callbacks.plots import main_time_plot_dynamic, main_surface_plot_dynamic_v2, cross_section_plots
from callbacks.utils import get_df, get_upload_df, fetch_group_names_for_benchmark, get_metadata, get_benchmark_params, \
    get_plots_from_json, get_benchmarks_list
from dash import ctx, no_update, html
import dash_bootstrap_components as dbc



# some helpers

def _axes_from_file_params(file_params: dict) -> tuple[str, str]:
    grid = file_params.get("grid", {}) or {}
    axes = list(grid.keys())
    if len(axes) != 2:
        # legacy fallback
        return ("x", "y")
    return axes[0], axes[1]  # preserve JSON order


def _axis_meta_from_file_params(file_params: dict) -> dict:
    # build a {varname: {unit, description}} mapping from var_list
    meta = {}
    for v in (file_params.get("var_list") or []):
        name = v.get("name")
        if name:
            meta[name] = {"unit": v.get("unit", ""), "description": v.get("description", "")}
    return meta

def get_callbacks(app):
    @app.callback(dash.dependencies.Output('main-graph', 'figure'),
                  dash.dependencies.Output('main-graph', 'style'),
                  dash.dependencies.Output('sub-graph', 'figure'),
                  dash.dependencies.Output('sub-graph', 'style'),
                  [
                      dash.dependencies.Input('show-graphs', "n_clicks"),
                      dash.dependencies.Input('update-graphs', 'n_clicks'),
                      dash.dependencies.Input('benchmark-params', 'data'), ],
                  [
                      dash.dependencies.State('file-type-selector', "value"),
                      dash.dependencies.State('dataset-choice', "value"),
                      dash.dependencies.State('receiver-selector', "value"),
                      dash.dependencies.State('url', "search"),
                      dash.dependencies.State('slider-gc-surface', 'value'),
                      dash.dependencies.State('surface-plot-type', 'value'),
                      dash.dependencies.State('surface-plot-var', "value"),
                      dash.dependencies.State('time-xaxis-var', "value"),
                      dash.dependencies.State('main-graph', 'figure'),
                      dash.dependencies.State('upload-data', "contents"),
                      dash.dependencies.State('upload-data', 'filename'),
                      dash.dependencies.State('colorbar-min', 'value'),
                      dash.dependencies.State('colorbar-max', 'value'),
                      dash.dependencies.State('surface-cross-axis', 'value'),
                      dash.dependencies.State('surface-switch-axis', 'value'),
                  ]
                  )
    def display_plots(ds_update_clicks, graph_control_nclick, benchmark_params, file_type_name, dataset_list, receiver,
                      benchmark_id, slider_gc_surface, surface_plot_type, surface_plot_var, x_axis_sel, current_fig, upload_data,
                      filename, colorbar_min, colorbar_max,surface_cross_axis , surface_switch_axis ):
        """
        Update the time-series graph based on user inputs.

        Parameters:
        ds_update (str): JSON string of the dataset.
        click (int): Number of times the submit button has been clicked.
        year_start (int): Start year for the time series.
        year_end (int): End year for the time series.
        time_unit (str): Time unit for the x-axis.

        Returns:
        dict: Figure object for the time-series graph.
        """
        if benchmark_params is None or file_type_name == '':
            print("benchmark_params is not loaded yet.")
            return {
                "data": [],
                "layout": {
                    "title": "Time-Series Graph",
                    "xaxis": {"title": "Time"},
                    "yaxis": {"title": "Value"},
                }
            }, {'width': '100%', 'height': '85hv'}, {}, {'display': 'none'}

        list_df = []
        plot_type = next((file['graph_type'] for file in benchmark_params['files'] if file['name'] == file_type_name),
                         None)
        file_params = next((f for f in benchmark_params["files"] if f["name"] == file_type_name), None)
        plots_list = get_plots_from_json(benchmark_params, file_type_name)
        if ds_update_clicks is not None or graph_control_nclick is not None:
            selected_df = get_df(benchmark_id, dataset_list, receiver)
            # suface 1 file upload not supported for now due to interpolations needs
            if plot_type != 'surface':
                upload_df = get_upload_df(upload_data, filename, plots_list)
            else:
                upload_df = None
            if upload_df is not None:
                list_df.append(upload_df)
            if selected_df is not None:
                list_df.append(selected_df)
            if len(list_df) > 0:
                ds_update = pd.concat(list_df)
            else:
                ds_update = pd.DataFrame()
        else:
            ds_update = pd.DataFrame()

        if plot_type == 'surface':
            fig = go.Figure()
            slider_only = False

            plot_params = [item for item in plots_list if item["name"] == surface_plot_var][0]

            # derive axes from the file template JSON
            axes = _axes_from_file_params(file_params) if file_params else ("x", "y")
            if "switch" in (surface_switch_axis or []):
                axes = (axes[1], axes[0])
            axis_meta = _axis_meta_from_file_params(file_params) if file_params else {}

            cross_section_value = slider_gc_surface

            main_graph, main_graph_style = main_surface_plot_dynamic_v2(
                ds_update,
                fig,
                plot_params,
                surface_plot_type,
                cross_section_value,
                slider_only,
                colorbar_min,
                colorbar_max,
                axes=axes,
                cross_axis=surface_cross_axis,
                axis_meta=axis_meta,
            )

            sub_graph = cross_section_plots(
                ds_update,
                plot_params,
                cross_section_value,
                axes=axes,
                cross_axis=surface_cross_axis,
                axis_meta=axis_meta,
            )
            sub_graph_style = {"display": "block"}
        else:
            x_axis = next((item for item in plots_list if item['name'] == x_axis_sel), plots_list[0])

            main_graph, main_graph_style = main_time_plot_dynamic(ds_update, plots_list, x_axis)
            sub_graph = go.Figure()
            sub_graph_style = {'display': 'none'}

        return main_graph, main_graph_style, sub_graph, sub_graph_style

    ### Callback 1: Generate Links Based on Dataset Choice and Benchmark ID
    @app.callback(
        dash.dependencies.Output('links-container', 'children'),
        dash.dependencies.Input('show-graphs', 'n_clicks'),
        dash.dependencies.State('dataset-choice', 'value'),
        prevent_initial_call=True
    )
    def update_links(show_graph_update, dataset_list):
        # Generate the links dynamically
        links = [
            html.Div(
                children=[
                    html.Span("Metadata: "),
                    html.A(file, href='#', id={'type': 'file-link', 'index': file}),
                ],
                style={'marginBottom': '10px'}
            )
            for file in dataset_list or []  # Handle case if dataset_list is None
        ]
        return links

    ### Callback 2: Handle Modal Open/Close Logic
    @app.callback(
        dash.dependencies.Output('popup-content', 'children'),
        dash.dependencies.Output('popup-modal', 'is_open'),
        dash.dependencies.Input({'type': 'file-link', 'index': dash.dependencies.ALL}, 'n_clicks'),
        dash.dependencies.Input('close-popup', 'n_clicks'),
        dash.dependencies.State('popup-modal', 'is_open'),
        dash.dependencies.State('url', 'search'),
        prevent_initial_call=True
    )
    def handle_modal(file_clicks, close_click, is_open, benchmark_id):
        triggered = ctx.triggered
        # Debug: Check what triggered the callback
        if not triggered:
            return "", False  # No valid trigger, return modal closed.

        # Check if a file link was clicked
        if "file-link" in triggered[0]['prop_id'] and triggered[0]['value']:
            file_name = eval(triggered[0]['prop_id'].rsplit('.', 1)[0])['index']
            # Fetch and format metadata
            metadata = get_metadata(benchmark_id, file_name)
            return metadata, True  # Open modal with metadata

        # Close modal if the close button was clicked
        return "", False

    @app.callback(dash.dependencies.Output('upload-filename', 'children'),
                  dash.dependencies.Input('upload-data', 'contents'),
                  dash.dependencies.State('upload-data', 'filename'))
    def print_upload_filename(upload_data, filename):
        """
        Display the filename of the uploaded data.

        Parameters:
        upload_data (str): Contents of the uploaded data.
        filename (str): Name of the uploaded file.

        Returns:
        str: Filename of the uploaded file.
        """
        return filename

    @app.callback(
        dash.dependencies.Output('dataset-choice', 'options'),
        [dash.dependencies.Input('url', 'search')]
    )
    def update_dataset_selection(search):
        """
        Update the dataset selection options based on the benchmark_id in the URL.

        Parameters:
        search (str): Name of the selected benchmark in the url

        Returns:
        list: List of available dataset options.
        """
        datasets = fetch_group_names_for_benchmark(search)
        links = [
            {'label': html.Span([file, html.A(": info", href='#', id={'type': 'file-link', 'index': file})]),
             'value': file}
            for file in datasets or []  # Handle case if dataset_list is None
        ]
        return links

    @app.callback(
        dash.dependencies.Output("benchmark-params", "data"),
        dash.dependencies.Output("redirect", "href"),
        dash.dependencies.Output("welcome-modal", "is_open"),
        dash.dependencies.Output("benchmarks-list-store", "data"),
        dash.dependencies.Input("url", "search"),
        dash.dependencies.Input("welcome-close", "n_clicks"),
        dash.dependencies.State("welcome-modal", "is_open"),
        prevent_initial_call=False,
    )
    def load_benchmark_params(search, close_clicks, modal_is_open):
        # Which input triggered?
        trigger = dash.callback_context.triggered[0]["prop_id"].split(".")[
            0] if dash.callback_context.triggered else None

        # 1) Close button wins: just close the modal, don't touch anything else
        if trigger == "welcome-close":
            return no_update, no_update, False, no_update

        # 2) Otherwise, we're here because url.search fired (initial load or navigation)
        try:
            benchmark_params = get_benchmark_params(search)  # unchanged
            return benchmark_params, no_update, False, no_update
        except Exception as e:
            print(f"Error fetching benchmark params: {e}")

            try:
                blist = get_benchmarks_list()
            except Exception as e2:
                print(f"Error loading benchmarks list: {e2}")
                blist = None

            return None, no_update, True, blist

    @app.callback(
        dash.dependencies.Output("benchmarks-list-ui", "children"),
        dash.dependencies.Input("benchmarks-list-store", "data"),
    )
    def render_benchmark_links(blist):
        if not blist:
            return dbc.Alert("Could not load benchmark list.", color="warning")

        public_items = (blist.get("groups", {}).get("public", []) or [])
        if not public_items:
            return dbc.Alert("No public benchmarks found.", color="warning")

        # Each link is a plain href that sets the querystring like you said
        return dbc.ListGroup([
            dbc.ListGroupItem(
                html.A(item["id"], href=f"?benchmark_id={item['id']}")
            )
            for item in public_items
        ])


    @app.callback(
        dash.dependencies.Output('file-type-selector', 'options'),
        dash.dependencies.Output('file-type-selector', 'value'),
        [dash.dependencies.Input('benchmark-params', 'data')]
    )
    def update_file_type_selector(benchmark_params):
        """
        Update the file type selector based on the benchmark_params.

        Parameters:
        benchmark_params (list): List of available files type.

        Returns:
        list: List of available files type.
        """
        if benchmark_params is None:
            return no_update
        list_files = [file['name'] for file in benchmark_params['files']]
        return list_files, list_files[0]

    @app.callback(
        [dash.dependencies.Output('receiver-selector', 'options'),
         dash.dependencies.Output('receiver-selector', 'value'),
         dash.dependencies.Output('surface-plot-var', 'options'),
         dash.dependencies.Output('surface-plot-var', 'value'),
         dash.dependencies.Output('time-xaxis-var', 'options'),
         dash.dependencies.Output('time-xaxis-var', 'value'),
         dash.dependencies.Output('surface-cross-axis', 'options'),
         dash.dependencies.Output('surface-cross-axis', 'value'),
         dash.dependencies.Output('surface-switch-axis', 'value'),
         ],

        [dash.dependencies.Input('file-type-selector', 'value')],
        [dash.dependencies.State('benchmark-params', 'data')]
    )
    def update_receiver_selector(file_selected, benchmark_params):
        """
        Update the file type selector based on the benchmark_params.

        Parameters:
        benchmark_params (list): List of available files type.

        Returns:
        list: List of available receivers.
        """
        if benchmark_params is None:
            return no_update
        if file_selected is None:
            return no_update
        for file in benchmark_params['files']:
            if file['name'] == file_selected:
                list_vars = [var['name'] for var in get_plots_from_json(benchmark_params, file_selected)]

                # axes from template grid keys (preserve order)
                grid = file.get("grid", {}) or {}
                axes = list(grid.keys())

                cross_axis_opts = [{"label": a, "value": a} for a in axes] if len(axes) == 2 else []
                default_cross_axis = axes[1] if len(axes) == 2 else ""  # default: keep your old "y-like" behavior

                # build meta from var_list so we can label slider units nicely
                xaxis_options = list_vars.copy()
                if 't' not in xaxis_options:
                    xaxis_options.append('t')
                return (
                    file['list_of_receivers'], file['list_of_receivers'][0],
                    list_vars, list_vars[-1],
                    xaxis_options, 't',
                    cross_axis_opts, default_cross_axis,
                    [],  # reset switch checkbox
                )
        return no_update

    @app.callback(
        dash.dependencies.Output('graph-control-surface', 'style'),
        dash.dependencies.Output('graph-control-time', 'style'),
        [dash.dependencies.Input('file-type-selector', 'value')],
        [dash.dependencies.State('benchmark-params', 'data')]
    )
    def update_graph_control(file_selected, benchmark_params):
        graph_type = ''
        if benchmark_params is None:
            return no_update
        if file_selected is None:
            return no_update
        for file in benchmark_params['files']:
            if file['name'] == file_selected:
                graph_type = file['graph_type']

        if graph_type == "surface":
            return {"display": "block"}, {"display": "none"}
        else:
            return {"display": "none"}, {"display": "block"}

    @app.callback(
        dash.dependencies.Output("slider-gc-surface", "min"),
        dash.dependencies.Output("slider-gc-surface", "max"),
        dash.dependencies.Output("slider-gc-surface", "step"),
        dash.dependencies.Output("slider-gc-surface", "marks"),
        dash.dependencies.Output("slider-gc-surface", "value"),
        dash.dependencies.Output("surface-slider-label", "children"),
        dash.dependencies.Input("file-type-selector", "value"),
        dash.dependencies.Input("surface-cross-axis", "value"),
        dash.dependencies.Input("surface-switch-axis", "value"),
        dash.dependencies.State("benchmark-params", "data"),
        dash.dependencies.State("slider-gc-surface", "value"),
    )
    def update_surface_slider(file_type_name, cross_axis, switch_axis_value,
                              benchmark_params, current_value):

        # ---- Basic guards ----
        if not benchmark_params or not file_type_name:
            return -100.0, 100.0, 1.0, {}, 0.0, "Cross section slider"

        file_params = next(
            (f for f in benchmark_params.get("files", [])
             if f.get("name") == file_type_name),
            None
        )
        if not file_params:
            return -100.0, 100.0, 1.0, {}, 0.0, "Cross section slider"

        grid = file_params.get("grid", {}) or {}
        axes = list(grid.keys())
        if len(axes) != 2:
            return -100.0, 100.0, 1.0, {}, 0.0, "Cross section slider"

        a0, a1 = axes[0], axes[1]
        if switch_axis_value and "switch" in switch_axis_value:
            a0, a1 = a1, a0

        if not cross_axis or cross_axis not in (a0, a1):
            cross_axis = a1

        g = grid.get(cross_axis)
        if not g:
            return -100.0, 100.0, 1.0, {}, 0.0, f"Cross section slider along {cross_axis}"

        vmin = float(g["min"])
        vmax = float(g["max"])

        # ---- Optional: adaptive m → km conversion ----
        meta = {v.get("name"): v for v in (file_params.get("var_list") or [])}
        unit = (meta.get(cross_axis, {}) or {}).get("unit", "")

        ui_min = vmin
        ui_max = vmax
        ui_unit = unit if unit else "units"

        span = ui_max - ui_min if ui_max != ui_min else 1.0

        # ---- Step: smooth but not insane ----
        ui_step = span / 500.0  # about 500 drag positions

        # ---- 9 evenly spaced ticks ----
        tick_vals = np.linspace(ui_min, ui_max, 9)

        def fmt_compact(x: float) -> str:
            x = float(x)
            ax = abs(x)

            if ax >= 1_000_000_000:
                return f"{x / 1_000_000_000:.3g}B"
            if ax >= 1_000_000:
                return f"{x / 1_000_000:.3g}M"
            if ax >= 1_000:
                return f"{x / 1_000:.3g}k"

            # small numbers
            if span >= 10:
                return f"{x:.1f}".rstrip("0").rstrip(".")
            return f"{x:.2f}".rstrip("0").rstrip(".")

        marks = {int(v): fmt_compact(v) for v in tick_vals}

        # ---- Clamp value ----
        if current_value is None:
            ui_value = float((ui_min + ui_max) / 2.0)
        else:
            ui_value = float(current_value)
            ui_value = max(ui_min, min(ui_max, ui_value))

        label = f"Cross section slider (hold {cross_axis} constant) in {ui_unit}"

        return float(ui_min), float(ui_max), float(ui_step), marks, float(ui_value), label
