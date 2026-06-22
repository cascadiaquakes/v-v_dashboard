
from callbacks.utils import generate_color_mapping
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np


TIME_UNIT_FACTORS = {
    "s": 1.0,
    "min": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "yr": 365.25 * 86400.0,
}

TIME_UNIT_LABELS = {
    "s": "s",
    "min": "min",
    "h": "h",
    "d": "d",
    "yr": "yr",
}


def time_axis_factor(time_axis_unit):
    return TIME_UNIT_FACTORS.get(time_axis_unit, TIME_UNIT_FACTORS["s"])


def time_axis_label(time_axis_unit):
    return TIME_UNIT_LABELS.get(time_axis_unit, TIME_UNIT_LABELS["s"])


def _axis_unit(axis_name, axis_meta, time_axis_unit):
    if axis_name == "t":
        return time_axis_label(time_axis_unit)
    return axis_meta.get(axis_name, {}).get("unit", "")


def _axis_label(axis_name, axis_meta, time_axis_unit):
    unit = _axis_unit(axis_name, axis_meta, time_axis_unit)
    return f"{axis_name} ({unit})" if unit else axis_name


def _axis_display_values(values, axis_name, time_axis_unit):
    if axis_name == "t":
        return values / time_axis_factor(time_axis_unit)
    return values


def _axis_display_value(value, axis_name, time_axis_unit):
    if axis_name == "t":
        return value / time_axis_factor(time_axis_unit)
    return value


def _axis_raw_value(value, axis_name, time_axis_unit):
    if axis_name == "t":
        return value * time_axis_factor(time_axis_unit)
    return value


def _match_subplot_axes(fig, *, x=False, y=False):
    # Plotly warns when the primary axis is set to match itself.
    if x:
        fig.update_xaxes(matches="x")
        fig.layout.xaxis.matches = None
    if y:
        fig.update_yaxes(matches="y")
        fig.layout.yaxis.matches = None


def main_time_plot_dynamic(df, variable_list, x_axis=dict({'name':'t', 'unit':'s', 'description':'Time'}), time_axis_unit="s"):
    """
    Generate a dynamic plot with subplots based on a list of variable dictionaries.

    Parameters:
    df (pd.DataFrame): DataFrame containing the dataset.
    variable_list (list): List of dictionaries with keys 'name', 'unit', and 'description'.
    Returns:
    FigureResampler: Plotly figure object with dynamic resampling enabled.
    """
    try:
        # Calculate the number of rows needed for a 2-column layout
        filtered_list = [item for item in variable_list if item['name'] != x_axis['name']]
        print(f"x_axis variable name: {x_axis['name']}")
        print(f"Filtered list: {filtered_list}")
        num_vars = len(filtered_list)
        num_rows = (num_vars + 1) // 2  # Round up to ensure enough rows
        print(f"Number of variables: {num_vars}, number of rows: {num_rows}")
        # Get unique datasets in the file
        datasets = df['dataset_name'].unique()

        # Generate color mapping for each dataset
        color_mapping = generate_color_mapping(datasets)

        fig = make_subplots(
            rows=num_rows, cols=2, shared_xaxes=True,
            subplot_titles=[f"{var['description']} ({var['unit']})" for var in filtered_list],
            vertical_spacing=0.1, horizontal_spacing=0.08
        )

        for dataset_name, group in df.groupby('dataset_name'):
            color = color_mapping[dataset_name]
            legend_name = dataset_name.split('_rec', 1)[0]

            for idx, var in enumerate(filtered_list):
                row = (idx // 2) + 1
                col = (idx % 2) + 1

                fig.add_trace(
                    go.Scatter(
                        mode='lines',
                        name=legend_name,
                        line=dict(color=color),
                        showlegend=idx == 0,  # Show legend only for the first subplot
                        legendgroup=dataset_name,
                    ),
                    row=row, col=col
                )

                # Append data to the traces
                x_values = group[x_axis['name']]
                if x_axis['name'] == "t":
                    x_values = x_values / time_axis_factor(time_axis_unit)
                fig.data[-1].update({'x': x_values, 'y': group[var['name']]})

        # Update layout with title and shared x-axis range
        for idx in range(0, len(variable_list) + 1):
            row = (idx // 2) + 1
            col = (idx % 2) + 1
            x_axis_unit = time_axis_label(time_axis_unit) if x_axis['name'] == "t" else x_axis['unit']
            fig.update_xaxes(title_text=f"{x_axis['description']} ({x_axis_unit})", row=row, col=col, showticklabels=True)
        _match_subplot_axes(fig, x=True)
        for idx, var in enumerate(filtered_list):
            row = (idx // 2) + 1
            col = (idx % 2) + 1
            fig.update_yaxes(title_text=f"{var['description']} ({var['unit']})", row=row, col=col)

        # Update layout to include legend and global settings
        fig.update_layout(
            showlegend=True
        )

    except Exception as e:
        print(f"error plotting dataset: {e}")
        # Fallback plot in case of error
        fig = make_subplots(
            rows=num_rows, cols=2, shared_xaxes=True,
            subplot_titles=[f"{var['description']} ({var['unit']})" for var in variable_list],
            vertical_spacing=0.04, horizontal_spacing=0.05
        )
        for idx, var in enumerate(variable_list):
            row = (idx // 2) + 1
            col = (idx % 2) + 1
            fig.add_trace(
                go.Scatter(x=[0, 1, 2, 3], y=[0, 1, 2, 3], mode='lines', name="test_name", showlegend=idx == 0,
                           legendgroup="code_name"),
                row=row, col=col
            )
        fig.update_layout(
            showlegend=True,
        )
    dynamic_height = f'{min(85 + (num_rows - 2) * 20, 150)}vh'  # Scale with num_rows
    return fig, {'width': '100%', 'height': dynamic_height}


def main_surface_plot_dynamic_v2(
    df,
    old_fig,
    variable_dict,
    plot_type="3d_surface",
    slider=0,
    slider_only=False,
    colorbar_min=None,
    colorbar_max=None,
    *,
    axes=("x", "y"),
    cross_axis=None,
    axis_meta=None,
    time_axis_unit="s",
):
    """
    axes: (a0, a1) are the two grid axes in df. Slider is applied along a1.
    """
    try:
        a0, a1 = axes
        axis_meta = axis_meta or {}

        if cross_axis is None:
            cross_axis = a1  # preserve old behavior

        if cross_axis not in (a0, a1):
            print(f"[WARN] cross_axis={cross_axis!r} not in axes={axes}; defaulting to {a1!r}")
            cross_axis = a1

        datasets = df["dataset_name"].unique()
        num_ds = len(datasets)
        num_rows = num_ds // 2 + num_ds % 2
        num_cols = 1 if num_ds == 1 else 2

        if colorbar_max is None:
            colorbar_max = df[variable_dict["name"]].max()
        if colorbar_min is None:
            colorbar_min = df[variable_dict["name"]].min()

        fig = make_subplots(
            rows=num_rows,
            cols=num_cols,
            specs=[[{"type": "surface" if plot_type == "3d_surface" else "heatmap"}] * num_cols]
            if num_ds == 1
            else [[{"type": "surface" if plot_type == "3d_surface" else "heatmap"} for _ in range(num_cols)]
                  for _ in range(num_rows)],
            subplot_titles=[f"Dataset: {name}" for name in datasets],
            vertical_spacing=0.1,
            horizontal_spacing=0.08,
        )

        for i, dataset_name in enumerate(datasets):
            row = (i // num_cols) + 1
            col = (i % num_cols) + 1
            dataset_df = df[df["dataset_name"] == dataset_name]

            cross_vals = np.sort(dataset_df[cross_axis].unique())
            raw_slider = _axis_raw_value(slider, cross_axis, time_axis_unit)
            slider_val = cross_vals[np.abs(cross_vals - raw_slider).argmin()]

            a0_unique = np.sort(dataset_df[a0].unique())
            a1_unique = np.sort(dataset_df[a1].unique())
            a0_display = _axis_display_values(a0_unique, a0, time_axis_unit)
            a1_display = _axis_display_values(a1_unique, a1, time_axis_unit)
            slider_display = _axis_display_value(slider_val, cross_axis, time_axis_unit)

            v_2d = dataset_df.pivot(index=a1, columns=a0, values=variable_dict["name"]).values

            if plot_type == "3d_surface":
                fig.add_trace(
                    go.Surface(
                        x=a0_display,
                        y=a1_display,
                        z=v_2d,
                        colorscale="RdBu_r",
                        cmin=colorbar_min,
                        cmax=colorbar_max,
                        colorbar=dict(title=f"{variable_dict['name']} ({variable_dict['unit']})"),
                    ),
                    row=row,
                    col=col,
                )

                scene_key = f"scene{i + 1}" if i > 0 else "scene"

                # cross-section line at a1 = slider_val
                if cross_axis == a1:
                    # constant a1 (horizontal slice), vary a0
                    a1_index = np.abs(a1_unique - slider_val).argmin()
                    const_val = a1_unique[a1_index]
                    line_df = dataset_df[dataset_df[a1] == const_val].sort_values(a0)

                    fig.add_trace(go.Scatter3d(
                        x=_axis_display_values(line_df[a0].to_numpy(), a0, time_axis_unit),
                        y=np.full(len(line_df), _axis_display_value(const_val, a1, time_axis_unit)),
                        z=line_df[variable_dict["name"]].to_numpy(),
                        mode="lines",
                        line=dict(color="black", width=3),
                        showlegend=False,
                        scene=scene_key,
                    ), row=row, col=col)

                else:
                    # constant a0 (vertical slice), vary a1
                    a0_index = np.abs(a0_unique - slider_val).argmin()
                    const_val = a0_unique[a0_index]
                    line_df = dataset_df[dataset_df[a0] == const_val].sort_values(a1)

                    fig.add_trace(go.Scatter3d(
                        x=np.full(len(line_df), _axis_display_value(const_val, a0, time_axis_unit)),
                        y=_axis_display_values(line_df[a1].to_numpy(), a1, time_axis_unit),
                        z=line_df[variable_dict["name"]].to_numpy(),
                        mode="lines",
                        line=dict(color="black", width=3),
                        showlegend=False,
                        scene=scene_key,
                    ), row=row, col=col)

                fig.update_layout(
                    {
                        scene_key: dict(
                            xaxis=dict(title=_axis_label(a0, axis_meta, time_axis_unit)),
                            yaxis=dict(title=_axis_label(a1, axis_meta, time_axis_unit)),
                            zaxis=dict(title=f"{variable_dict['name']} ({variable_dict['unit']})"),
                        )
                    }
                )

            elif plot_type == "heatmap":
                fig.add_trace(
                    go.Heatmap(
                        x=a0_display,
                        y=a1_display,
                        z=v_2d,
                        zmin=colorbar_min,
                        zmax=colorbar_max,
                        colorscale="RdBu_r",
                        colorbar=dict(title=f"{variable_dict['name']} ({variable_dict['unit']})"),
                    ),
                    row=row,
                    col=col,
                )

                if cross_axis == a1:
                    # horizontal line at y = slider_val
                    fig.add_trace(go.Scatter(
                        x=[a0_display.min(), a0_display.max()],
                        y=[slider_display, slider_display],
                        mode="lines",
                        line=dict(color="black", width=1),
                        showlegend=False,
                    ), row=row, col=col)
                else:
                    # vertical line at x = slider_val
                    fig.add_trace(go.Scatter(
                        x=[slider_display, slider_display],
                        y=[a1_display.min(), a1_display.max()],
                        mode="lines",
                        line=dict(color="black", width=1),
                        showlegend=False,
                    ), row=row, col=col)

                xaxis_key = f"xaxis{i + 1}" if i > 0 else "xaxis"
                yaxis_key = f"yaxis{i + 1}" if i > 0 else "yaxis"
                same_units = (
                        _axis_unit(a0, axis_meta, time_axis_unit) ==
                        _axis_unit(a1, axis_meta, time_axis_unit)
                )

                if same_units:
                    fig.update_layout({
                        xaxis_key: dict(
                            title=_axis_label(a0, axis_meta, time_axis_unit),
                            scaleanchor=f"y{i + 1}" if i > 0 else "y",
                        ),
                        yaxis_key: dict(title=_axis_label(a1, axis_meta, time_axis_unit)),
                    })
                else:
                    fig.update_layout({
                        xaxis_key: dict(title=_axis_label(a0, axis_meta, time_axis_unit)),
                        yaxis_key: dict(title=_axis_label(a1, axis_meta, time_axis_unit)),
                    })

        if plot_type == "3d_surface":
            fig.update_layout(
                title=f"Surface Plot of {_axis_label(a0, axis_meta, time_axis_unit)} vs {_axis_label(a1, axis_meta, time_axis_unit)} colored by {variable_dict['name']} [{variable_dict['unit']}] (Re-gridded)",
                template="plotly_white",
            )
        else:
            fig.update_layout(
                title=f"Heatmap of {_axis_label(a0, axis_meta, time_axis_unit)} vs {_axis_label(a1, axis_meta, time_axis_unit)} colored by {variable_dict['name']} [{variable_dict['unit']}] (Re-gridded)",
                template="plotly_white",
            )

            # Only match axes when we're NOT locking aspect.
            same_units = (
                    _axis_unit(a0, axis_meta, time_axis_unit) ==
                    _axis_unit(a1, axis_meta, time_axis_unit)
            )
            if not same_units:
                # safe: consistent scales across subplots without aspect lock
                _match_subplot_axes(fig, x=True, y=True)

    except Exception as e:
        print(f"Error plotting dataset: {e}")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="plot error"))

        num_rows = 1

    dynamic_height = f"{min(85 + (num_rows - 2) * 20, 150)}vh"
    return fig, {"width": "100%", "height": dynamic_height}


def cross_section_plots(df, variable_dict, slider=0, *, axes=("x", "y"), cross_axis=None, axis_meta=None, time_axis_unit="s"):
    try:
        a0, a1 = axes
        axis_meta = axis_meta or {}

        # default: preserve old behavior (slice at a1)
        if cross_axis is None:
            cross_axis = a1
        if cross_axis not in (a0, a1):
            print(f"[WARN] cross_axis={cross_axis!r} not in axes={axes}; defaulting to {a1!r}")
            cross_axis = a1

        profile_axis = a0 if cross_axis == a1 else a1

        # Choose nearest value along cross_axis
        cross_vals = np.sort(df[cross_axis].unique())
        if len(cross_vals) == 0:
            return go.Figure()

        raw_slider = _axis_raw_value(slider, cross_axis, time_axis_unit)
        slider_val = cross_vals[np.abs(cross_vals - raw_slider).argmin()]
        slider_display = _axis_display_value(slider_val, cross_axis, time_axis_unit)

        # Filter for the selected slice
        df_cross = df[df[cross_axis] == slider_val]
        fig = go.Figure()

        # Add traces for each dataset_name
        for dataset in df_cross["dataset_name"].unique():
            dataset_df = df_cross[df_cross["dataset_name"] == dataset].sort_values(profile_axis)

            fig.add_trace(
                go.Scattergl(
                    x=_axis_display_values(dataset_df[profile_axis], profile_axis, time_axis_unit),
                    y=dataset_df[variable_dict["name"]],
                    mode="lines",
                    name=dataset,
                    line=dict(width=2),
                )
            )

        fig.update_layout(
            title=f"Cross section of {variable_dict['name']} at {_axis_label(cross_axis, axis_meta, time_axis_unit)}={slider_display:.6g}",
            xaxis_title=_axis_label(profile_axis, axis_meta, time_axis_unit),
            yaxis_title=f"{variable_dict['name']} ({variable_dict['unit']})",
            legend_title="Dataset Name",
            template="plotly_white",
        )

        return fig

    except Exception as e:
        print(f"error plotting dataset: {e}")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1, 2, 3], y=[0, 1, 2, 3], mode="lines", name="fallback"))
        return fig
