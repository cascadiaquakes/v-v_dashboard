# Adaptive line plot resolution

Time-series lines and surface cross sections send at most 2,000 vertices per
curve and 100,000 per graph. Configure these defaults with `POINTS_PER_CURVE`
and `POINTS_PER_GRAPH` in `callbacks/line_sampling.py`. Plotting helpers also
accept `viewport`, `per_curve`, and `total` keyword arguments. Scatter plots
and surfaces keep their existing rendering behavior; benchmark templates do
not need changes.

The overview uses original samples selected by source-order buckets retaining
endpoints and local minima/maxima. Each variable is sampled independently.
Zooming or panning requests samples intersecting the visible x-range, including
segment boundary neighbors. Below the budget, every original vertex is shown.
Reset returns to the overview. Sampling uses displayed coordinates, so time-unit
conversion is applied consistently before both selection and rendering.

Sample order is preserved for looping/nonmonotonic x values. Gaps and discarded
excursions receive explicit breaks. If there are more disconnected runs than
the budget can represent, representative runs are retained with breaks between
them; an overview cannot preserve every event in such heavily fragmented data.
The displayed/available count indicates whether sampling is active. Counts
exclude gap separators; the hard vertex limits include them.

Original arrays and uploaded inputs stay in the existing server cache, with
opaque per-generation tokens and a one-hour inactivity timeout. Zoom requests
refresh retention. Cache misses rebuild the saved selection, preferring retained
uploads and falling back to the browser upload only if its digest matches. If
both expired and the upload changed, the plot remains visible with a reload
message. New selections remove the previous session's cached plot and upload.
The existing SimpleCache is process-local: multiple workers/replicas should use
a shared Flask-Caching backend to avoid repeated rebuilds between workers.

Requests are debounced for 150 ms and combine both graph viewports. Generation
and sequence checks discard stale responses. Only sampled arrays and small
metadata cross the network during zoom. Client-side patch application retains
axis and legend state; cache recovery explicitly restores visibility and y
ranges. Original source loading and server memory still scale with raw data.

## Verification

Use the project's configured interpreter for these commands:

```text
python -m unittest discover -s tests -v
node --test tests/line_plots.test.js
python -m tests.benchmark_line_sampling
python -m tests.line_sampling_app
```

The last command starts an offline synthetic-data fixture at
`http://127.0.0.1:8057/`. With a separate Chromium test profile open at that URL
and remote debugging enabled on port 9227, run
`node tests/line_plots.browser.cjs` using Node 22 or newer. It verifies actual graph arrays, reset,
legend/y state, cross sections, cache recovery, unit changes, multiple datasets,
and absence of browser errors. The fixture's cache-expiry route exists only
in the offline test app.

An initial local benchmark reduced one million samples from 24.4 MB of figure
JSON to 66 KB, with about 61 ms for overview sampling and 46 ms for a narrow
full-resolution selection. Four million points across four curves took about
171 ms/132 ms respectively. These exclude caching, network transfer, and browser
rendering; tune budgets against representative datasets and deployment hardware.

The native Dash loading spinner observes both server response stores and graph
figures. It appears after 250 ms of pending work for plot generation or viewport
refreshes, while keeping the existing plots visible. The browser check adds
network latency to verify that the animation appears and clears after completion.
