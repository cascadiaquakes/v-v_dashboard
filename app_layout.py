import dash_bootstrap_components as dbc
from dash import dcc
from dash import html


def get_main_page():
    init_datasets = []
    return html.Div(
        id="root",
        style={'width': '100%', 'overflowX': 'hidden'},  # Ensures no horizontal scroll
        children=[
            dcc.Location(id='url', refresh=False),
            dcc.Location(id='redirect', refresh=True),
            dbc.Navbar(
                dbc.Row(  # Use dbc.Row to properly align columns
                    [
                        dbc.Col(
                            html.A(
                                href="https://cascadiaquakes.org/",
                                children=[
                                    html.Img(
                                        src='assets/Crescent_Logo.png', style={'height': '60px'}
                                    ),
                                ]
                            ),
                            width={"size": 3, "offset": 1},
                        ),
                        dbc.Col(
                            html.H1(
                                "Code Verification Platform",
                                style={
                                    'textAlign': 'center',
                                    'color': 'white'
                                }
                            ),
                            width={"size": 5, "offset": 0}
                        ),
                        dbc.Col(
                            html.A(
                                href="https://www.nsf.gov",
                                children=[
                                    html.Img(
                                        src='assets/USNSF_Logo.png',
                                        style={'height': '90px'}
                                    ),
                                ]
                            ),
                            width={"size": 3, "offset": 0},
                        ),
                    ],
                    align="center",  # Center the content vertically
                    style={'width': '100%', 'margin': '0'}  # Full width, no margin
                ),
                color="#26505A",
                dark=True,
                style={
                    'marginBottom': '1rem',
                    'height': '100px',
                    'width': '100%',  # Ensures full-width navbar
                    'padding': '0'  # Remove padding to prevent overflow
                }
            ),
            dbc.Container(
                id="app-container",
                fluid=True,
                children=[
                    dbc.Row(
                        children=[
                            dbc.Col(
                                [
                                    html.H3("Control panel", style={
                                        'textAlign': 'center',
                                        'color': 'black'
                                    }),
                                    dcc.Tabs(id="tabs-example-graph", value='tab-dataset', children=[
                                        dcc.Tab(label='Dataset selection', value='tab-dataset', children=[
                                            dbc.Row(
                                                children=[
                                                    dbc.Col(
                                                        children=[
                                                            dbc.Label("Dataset choice"),
                                                            dbc.Checklist(
                                                                id='dataset-choice',
                                                                options=init_datasets,
                                                                value=[],
                                                            ),
                                                        ],
                                                    ),
                                                    dbc.Col(
                                                        children=[
                                                            dbc.Label("Choose the file type"),
                                                            dbc.Select(
                                                                id='file-type-selector',
                                                                options=[],
                                                                value=''
                                                            ),
                                                            dbc.Label("Choose the receiver"),
                                                            dbc.Select(
                                                                id='receiver-selector',
                                                                options=[],
                                                                value=''
                                                            ),
                                                        ],
                                                    ),
                                                    dbc.Button('Show graphs', id="show-graphs",
                                                               color="primary", style={'margin': '10px'}),
                                                ]
                                            ),
                                            html.Hr(),
                                            dbc.Row(
                                                children=[
                                                    dbc.Col(children=[
                                                        dcc.Upload(id='upload-data',
                                                                   children=[
                                                                       dbc.Button('Upload File', color="secondary"),
                                                                   ],
                                                                   multiple=False,
                                                                   style={'margin': '10px'}
                                                                   ),
                                                        dbc.Alert(
                                                            "Warning: Single file upload is not supported for surface files.",
                                                            color="warning",
                                                            dismissable=True,
                                                            style={'margin': '10px'}
                                                        ),
                                                        html.Div([html.H5("Uploaded file:", style={'color': '#000000'}),
                                                                  html.P(id="upload-filename")])
                                                    ]
                                                    )
                                                ]
                                            ),
                                            html.Hr(),
                                            dbc.Row(
                                                children=[
                                                    dbc.Col(children=[
                                                        html.Div([html.H5(
                                                            "List selected datasets, click for information:",
                                                            style={'color': '#000000'}),
                                                            html.Div(id='links-container'),  # Container for links
                                                            # Bootstrap modal
                                                            dbc.Modal(
                                                                [
                                                                    dbc.ModalHeader(
                                                                        dbc.ModalTitle("File Metadata")),
                                                                    dbc.ModalBody(html.Pre(id='popup-content', style={"maxHeight": "70vh", "overflowY": "auto"})),
                                                                    # JSON content display
                                                                    dbc.ModalFooter(
                                                                        dbc.Button("Close", id="close-popup",
                                                                                   className="ms-auto",
                                                                                   n_clicks=0)
                                                                    ),
                                                                ],
                                                                id="popup-modal",
                                                                is_open=False,
                                                                size="xl",
                                                            ), ])
                                                    ]
                                                    )
                                                ]
                                            ),
                                        ]),
                                        dcc.Tab(label='Graph control', value='tab-graphcontrol',
                                                children=[
                                                    dbc.Row(
                                                        id='graph-control-surface',
                                                        children=[
                                                            dbc.Col(children=[
                                                                dbc.Label("surface plot type"),
                                                                dbc.Select(
                                                                    id="surface-plot-type",
                                                                    options=[
                                                                        {"label": "3D surface", "value": "3d_surface"},
                                                                        {"label": "Heatmap", "value": "heatmap"},
                                                                    ],
                                                                    value="heatmap"
                                                                ),
                                                                dbc.Label("Variable selection"),
                                                                dbc.Select(
                                                                    id="surface-plot-var",
                                                                    options=[],
                                                                    value=""
                                                                ),
                                                                dbc.Label("Colorbar custom range"),
                                                                html.Div([
                                                                    dbc.Row([
                                                                        dbc.Col(
                                                                            dbc.Input(id="colorbar-min", type="number",
                                                                                      placeholder="Min", step=0.1),
                                                                            width=6),
                                                                        dbc.Col(
                                                                            dbc.Input(id="colorbar-max", type="number",
                                                                                      placeholder="Max", step=0.1),
                                                                            width=6)
                                                                    ])
                                                                ]),
                                                                dbc.Label("Cross section axis (hold constant)"),
                                                                dbc.Select(
                                                                    id="surface-cross-axis",
                                                                    options=[],
                                                                    # filled dynamically from template grid keys
                                                                    value=""
                                                                ),

                                                                dbc.Checklist(
                                                                    id="surface-switch-axis",
                                                                    options=[
                                                                        {"label": "Switch axis", "value": "switch"}],
                                                                    value=[],
                                                                    switch=True,
                                                                ),
                                                                dbc.Label(id="surface-slider-label"),
                                                                dcc.Slider(id='slider-gc-surface',
                                                                           min=-100,
                                                                           max=100,
                                                                           step=5000,
                                                                           value=0,
                                                                           marks={i: str(i) for i in
                                                                                  range(-100, 100 + 1,
                                                                                        (100 + 100) // 10)}
                                                                           ),  # For cross-section update
                                                            ]
                                                            )
                                                        ],
                                                        style={"display": "none"}
                                                    ),
                                                    dbc.Row(
                                                        id='graph-control-time',
                                                        children=[
                                                            dbc.Col([
                                                                dbc.Label("Choose x axis variable"),
                                                                dbc.Select(
                                                                    id="time-xaxis-var",
                                                                    options=[
                                                                        {"label": "Time", "value": "t"},
                                                                    ],
                                                                    value="t"
                                                                )]
                                                            )
                                                        ],
                                                        style={"display": "none"}
                                                    ),
                                                    dbc.Button('Update graphs', id="update-graphs",
                                                               color="primary", style={'margin': '10px'}),
                                                ])
                                    ]
                                             ),
                                ],
                                align="start",
                                width=3,
                            ),
                            dbc.Col([
                                dcc.Loading(id="ls-loading-1", children=[
                                    dcc.Graph(
                                        id='main-graph',
                                        style={'responsive': True,
                                               'width': '100%',
                                               'height': '85vh'},
                                        animate=False,
                                        config={'displayModeBar': True,
                                                'displaylogo': False,
                                                'scrollZoom': True,
                                                'toImageButtonOptions': {
                                                    'format': 'png',  # one of png, svg, jpeg, webp
                                                    'filename': 'export_plots',
                                                    'scale': 3
                                                    # Multiply title/legend/axis/canvas sizes by this factor
                                                }
                                                }
                                    ),
                                ], type="default"),
                                dcc.Loading(id="ls-loading-2", children=[
                                    dcc.Graph(
                                        id='sub-graph',
                                        style={'responsive': True,
                                               'width': '100%',
                                               'height': '50vh'},
                                        animate=False,
                                        config={'displayModeBar': True,
                                                'displaylogo': False,
                                                'scrollZoom': True,
                                                'toImageButtonOptions': {
                                                    'format': 'png',  # one of png, svg, jpeg, webp
                                                    'filename': 'export_plots',
                                                    'scale': 3
                                                }
                                                }
                                    ),
                                ], type="default")
                            ],
                                align="start",
                                width=9)
                        ])
                ]),
            dbc.Modal(
                id="welcome-modal",
                is_open=False,
                centered=True,
                size="lg",
                children=[
                    dbc.ModalHeader(dbc.ModalTitle("Welcome to the DET platform")),
                    dbc.ModalBody([
                        html.P("Pick a benchmark to get started:"),
                        html.Div(id="benchmarks-list-ui"),
                        html.Hr(),
                        html.P([
                            "Main website: ",
                            html.A(
                                "https://cascadiaquakes.org/det/",
                                href="https://cascadiaquakes.org/det/",
                                target="_blank",
                                rel="noopener noreferrer",
                            )
                        ])
                    ]),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="welcome-close", color="secondary")
                    ),
                ],
            ),
            # store user's dataset
            dcc.Store(id='benchmark-params'),
            dcc.Store(id="benchmarks-list-store")
        ])
