import dash
import dash_bootstrap_components as dbc
from flask_caching import Cache

import app_layout
from callbacks.callbacks import get_callbacks
from callbacks.utils import set_cache

app = dash.Dash(external_stylesheets=[dbc.themes.CERULEAN], title="DET code verification platform")

server = app.server

# Configure Flask-Caching with SimpleCache
cache = Cache(server, config={
    'CACHE_TYPE': 'SimpleCache',  # Use in-memory caching
    'CACHE_DEFAULT_TIMEOUT': 3600,  # Cache timeout in seconds (1 hour)
    'CACHE_THRESHOLD': 50
})

# Pass the cache object to your utility function
set_cache(cache)

app.layout = app_layout.get_main_page()

get_callbacks(app)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8081)
