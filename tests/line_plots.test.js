const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const settle = () => new Promise(resolve => setTimeout(resolve, 180));

function harness() {
    const noUpdate = {noUpdate: true};
    const updates = [];
    const dash = {no_update: noUpdate, callback_context: {},
        set_props: (...args) => updates.push(args)};
    const context = {window: {dash_clientside: dash, crypto: crypto},
        setTimeout, clearTimeout, structuredClone};
    vm.runInNewContext(fs.readFileSync('assets/line_plots.js', 'utf8'), context);
    const api = context.window.dash_clientside.linePlots;
    const trigger = name => { dash.callback_context.triggered_id = name; };
    trigger('show-graphs');
    const request = api.loadRequest(1, 0, {}, null);
    const loaded = {generation: request.generation, token: 'token', context: {},
        figures: {main: {}, sub: {}}, styles: {main: {}, sub: {}},
        statuses: {main: 'sampled', sub: 'sampled'}};
    trigger('plot-load-response');
    const state = api.applyResponse(loaded, null, null)[4];
    return {api, state, loaded, trigger, noUpdate, updates};
}

test('debounce merges both graphs and rejects older viewport responses', async () => {
    const {api, state, trigger, noUpdate, updates} = harness();
    trigger('main-graph');
    const canceled = api.viewportRequest({'xaxis2.range[0]': 10, 'xaxis2.range[1]': 20}, null, state);
    trigger('sub-graph');
    api.viewportRequest(null, {'xaxis.range': [30, 40]}, state);
    assert.equal(canceled, noUpdate);
    trigger('main-graph');
    api.viewportRequest({autosize: true}, null, state);
    await settle();
    assert.equal(updates.length, 1);
    const request = updates[0][1].data;
    assert.deepEqual(JSON.parse(JSON.stringify(request.ranges)), {main: [10, 20], sub: [30, 40]});
    trigger('plot-viewport-response');
    const stale = api.applyResponse(null, {generation: state.generation,
        sequence: request.sequence - 1, updates: {main: {patch: 'stale'}}}, state);
    assert.ok(stale.every(value => value === noUpdate));
    const patch = value => ({operations: [{location: ['data', 0, 'x'], params: {value}}]});
    const figure = {data: [{x: [0]}], layout: {}};
    const accepted = api.applyResponse(null, {...request,
        updates: {main: {patch: patch([10]), status: 'detail'},
            sub: {patch: patch([20]), status: 'detail'}}}, state, figure, figure);
    assert.deepEqual(accepted[0].data[0].x, [10]);
    assert.deepEqual(accepted[2].data[0].x, [20]);
    assert.deepEqual(figure.data[0].x, [0]);
});

test('ignores camera/y-only events, redundant ranges, and handles reset', async () => {
    const {api, state, trigger, noUpdate, updates} = harness();
    trigger('main-graph');
    assert.equal(api.viewportRequest({'scene.camera': {}}, null, state), noUpdate);
    assert.equal(api.viewportRequest({'yaxis.range': [1, 3]}, null, state), noUpdate);
    api.viewportRequest({'xaxis.range': [1, 3]}, null, state);
    assert.equal(api.viewportRequest({'xaxis.range': [1, 3]}, null, state), noUpdate);
    api.viewportRequest({'xaxis.autorange': true}, null, state);
    await settle();
    const reset = updates[0][1].data;
    assert.equal(reset.ranges.main, null);
});

test('new selection cancels pending work and rejects stale loads and zooms', async () => {
    const {api, state, loaded, trigger, noUpdate, updates} = harness();
    trigger('main-graph');
    const pending = api.viewportRequest({'xaxis.range': [1, 3]}, null, state);
    trigger('update-graphs');
    api.loadRequest(1, 1, {}, null);
    assert.equal(pending, noUpdate);
    await settle();
    assert.equal(updates.length, 0);
    trigger('plot-load-response');
    assert.ok(api.applyResponse(loaded, null, state).every(v => v === noUpdate));
    trigger('plot-viewport-response');
    assert.ok(api.applyResponse(null, {generation: state.generation, sequence: 1}, state)
        .every(v => v === noUpdate));
});

test('cache miss queues recovery with saved selection and current viewports', async () => {
    const {api, state, trigger, updates} = harness();
    trigger('main-graph');
    api.viewportRequest({'xaxis.range': [1, 3]}, null, state);
    await settle();
    const request = updates[0][1].data;
    trigger('plot-viewport-response');
    api.applyResponse(null, {...request, recover: true}, state);
    assert.equal(updates[1][0], 'plot-recover');
    assert.equal(updates[1][1].data.context, state.context);
    trigger('plot-recover');
    const recovery = api.loadRequest(1, 1, {}, updates[1][1].data);
    assert.equal(recovery.recovery, state.context);
    assert.deepEqual(Array.from(recovery.viewports.main), [1, 3]);
});
