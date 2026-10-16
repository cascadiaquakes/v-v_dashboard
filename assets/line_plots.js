/* Only small request metadata lives here; original arrays stay on the server. */
(function () {
    const runtime = {generation: null, sequence: 0,
        ranges: {main: null, sub: null}, pending: {}};
    const noUpdate = () => window.dash_clientside.no_update;
    const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    const newGeneration = () => Array.from(window.crypto.getRandomValues(new Uint8Array(16)),
        byte => byte.toString(16).padStart(2, '0')).join('');

    function applyPatch(figure, patch) {
        // Dash's server response path handles Patch objects; clientside
        // callback returns must be actual figures. Clone only the bounded
        // browser figure and apply the server's Assign operations locally.
        const updated = structuredClone(figure);
        for (const operation of patch.operations) {
            let target = updated;
            for (const key of operation.location.slice(0, -1)) {
                target[key] = target[key] || {};
                target = target[key];
            }
            target[operation.location.at(-1)] = operation.params.value;
        }
        return updated;
    }

    function restoreView(figure, graph) {
        const root = document.getElementById(graph + '-graph');
        const plot = root && root.querySelector('.js-plotly-plot');
        if (!plot || !plot.data) return figure;
        const updated = structuredClone(figure);
        const key = trace => JSON.stringify([trace.name, trace.legendgroup,
            trace.xaxis || 'x', trace.yaxis || 'y']);
        const visible = new Map(plot.data.map(trace => [key(trace), trace.visible]));
        for (const trace of updated.data) {
            const value = visible.get(key(trace));
            if (value !== undefined) trace.visible = value;
        }
        for (const [axis, value] of Object.entries(plot.layout)) {
            if (/^yaxis\d*$/.test(axis) && Array.isArray(value.range)) {
                updated.layout[axis] = {...updated.layout[axis],
                    range: [...value.range], autorange: value.autorange};
            }
        }
        return updated;
    }

    function axisRange(event) {
        if (!event) return undefined;
        for (const key of Object.keys(event)) {
            if (!/^xaxis\d*(\.|$)/.test(key)) continue;
            const axis = key.split('.')[0];
            if (event[axis + '.autorange'] === true) return null;
            const range = event[axis + '.range'] ||
                [event[axis + '.range[0]'], event[axis + '.range[1]']];
            if (range.length === 2 && range.every(Number.isFinite)) return range;
        }
        return undefined;
    }

    window.dash_clientside = Object.assign({}, window.dash_clientside, {
        linePlots: {
            loadRequest: function (_show, _update, _params, recovery) {
                const trigger = window.dash_clientside.callback_context.triggered_id;
                const recovering = trigger === 'plot-recover' && recovery;
                runtime.generation = newGeneration();
                runtime.sequence = 0;
                runtime.ranges = recovering ? recovery.viewports : {main: null, sub: null};
                for (const pending of Object.values(runtime.pending)) {
                    clearTimeout(pending.timer);
                }
                runtime.pending = {};
                return {generation: runtime.generation,
                    recovery: recovering ? recovery.context : null,
                    viewports: runtime.ranges,
                    uirevision: recovering ? recovery.uirevision : runtime.generation};
            },

            viewportRequest: function (mainEvent, subEvent, state) {
                if (!state || state.generation !== runtime.generation) return noUpdate();
                const graph = window.dash_clientside.callback_context.triggered_id ===
                    'sub-graph' ? 'sub' : 'main';
                if (!state.active[graph]) return noUpdate();
                const range = axisRange(graph === 'main' ? mainEvent : subEvent);
                if (range === undefined || equal(range, runtime.ranges[graph])) return noUpdate();
                runtime.ranges[graph] = range;
                const sequence = ++runtime.sequence;
                const previous = runtime.pending.viewport;
                if (previous) {
                    clearTimeout(previous.timer);
                }
                // Do not return a pending Promise: an unrelated autosize event
                // would supersede it in Dash and discard the eventual request.
                const timer = setTimeout(() => {
                    delete runtime.pending.viewport;
                    window.dash_clientside.set_props('plot-viewport-request', {data: {
                        generation: state.generation, token: state.token,
                        upload_token: state.context.upload_token,
                        sequence: sequence, ranges: {...runtime.ranges}}});
                }, 150);
                runtime.pending.viewport = {timer: timer};
                return noUpdate();
            },

            applyResponse: function (loaded, zoomed, state, mainFigure, subFigure) {
                const result = Array(7).fill(noUpdate());
                const trigger = window.dash_clientside.callback_context.triggered_id;
                const response = trigger === 'plot-viewport-response' ? zoomed : loaded;
                if (!response || response.generation !== runtime.generation) return result;
                if (trigger === 'plot-viewport-response') {
                    if (!state || state.generation !== response.generation ||
                        response.sequence !== runtime.sequence) return result;
                    if (response.recover) {
                        window.dash_clientside.set_props('plot-recover', {data: {
                            context: state.context, viewports: runtime.ranges,
                            uirevision: state.uirevision, nonce: Date.now()}});
                        return result;
                    }
                    for (const [graph, update] of Object.entries(response.updates)) {
                        result[graph === 'main' ? 0 : 2] = applyPatch(
                            graph === 'main' ? mainFigure : subFigure, update.patch);
                        result[graph === 'main' ? 5 : 6] = update.status;
                    }
                    return result;
                }
                if (response.error) {
                    result[5] = response.error;
                    return result;
                }
                const nextState = {generation: response.generation, token: response.token,
                    context: response.context, uirevision: response.uirevision,
                    active: {main: !!response.statuses.main, sub: !!response.statuses.sub}};
                const figures = response.recovered ? {
                    main: restoreView(response.figures.main, 'main'),
                    sub: restoreView(response.figures.sub, 'sub')} : response.figures;
                return [figures.main, response.styles.main,
                    figures.sub, response.styles.sub, nextState,
                    response.statuses.main, response.statuses.sub];
            }
        }
    });
}());
