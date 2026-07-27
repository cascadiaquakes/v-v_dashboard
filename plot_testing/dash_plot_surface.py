import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output

# Assuming your dataframe is named df
df = pd.read_csv("../resources/fabian_examples/surfdef_tpv36.csv", comment='#', delim_whitespace=True)
# df['years'], df['days'], df['hours'], df['seconds'] = convert_seconds_to_time(df['t'])
df['x [km]'] = df.x/1000
df['z [km]'] = df.z/1000

# Create the Dash app
app = dash.Dash(__name__)

# Initial scatter plot (empty, will be updated dynamically)
fig = go.Figure(data=go.Scattergl(
    x=[],
    y=[],
    mode='markers',
    marker={
        "color": [],
        "colorscale": 'RdBu_r',  # Reversed RdBu colormap
        "colorbar": {"title": 'v-disp'},
        "showscale": True,
        "cmin": df['v-disp'].min(),
        "cmax": df['v-disp'].max(),
        "size": 5  # Default marker size
    }
))

# Update layout
fig.update_layout(
    title='Scatter Plot of x vs z colored by h-disp (Dynamic Resampling)',
    xaxis={"title": 'x'},
    yaxis={"title": 'z'},
    template='plotly_white',
    width=800,
    height=800
)

# Define the app layout
app.layout = html.Div([
    dcc.Graph(id='scatter-plot', figure=fig)
])

# Callback to update the scatter plot based on zoom level
@app.callback(
    Output('scatter-plot', 'figure'),
    Input('scatter-plot', 'relayoutData')
)
def update_scatter_plot(relayout_data):
    # Default zoom level (full dataset)
    x_min, x_max = df['x'].min(), df['x'].max()
    z_min, z_max = df['z'].min(), df['z'].max()

    # Check if the user has zoomed in
    if relayout_data and 'xaxis.range[0]' in relayout_data:
        x_min = relayout_data['xaxis.range[0]']
        x_max = relayout_data['xaxis.range[1]']
        z_min = relayout_data['yaxis.range[0]']
        z_max = relayout_data['yaxis.range[1]']

    # Filter the dataframe to the visible range
    filtered_df = df[
        (df['x'] >= x_min) & (df['x'] <= x_max) &
        (df['z'] >= z_min) & (df['z'] <= z_max)
    ]

    # Subsample the data based on the zoom level
    zoom_level = (x_max - x_min) / (df['x'].max() - df['x'].min())
    print(f"Zoom level: {zoom_level}")
    subsample_fraction = min(1.0, 0.2 / zoom_level)
    print(f"Subsample fraction: {subsample_fraction}")
    subsampled_df = filtered_df.sample(frac=subsample_fraction)
    print(f"size df: {len(subsampled_df)}")
    # Update the scatter plot
    fig.update_traces(
        x=subsampled_df['x'],
        y=subsampled_df['z'],
        marker={
            "color": subsampled_df['v-disp'],
            "size": 3  # Adjust marker size if needed
        }
    )

    return fig

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)