/* Manual integration check. Start python -m tests.line_sampling_app and a headless
 * Chromium browser with --remote-debugging-port=9227 at http://127.0.0.1:8057/.
 * Run: node tests/line_plots.browser.cjs
 */
const assert = require('node:assert/strict');

(async function () {
    const pages = await (await fetch('http://127.0.0.1:9227/json/list')).json();
    const page = pages.find(p => p.url === 'http://127.0.0.1:8057/');
    assert.ok(page, 'Open the offline line-sampling app in the debugging browser');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(resolve => ws.addEventListener('open', resolve, {once: true}));
    let sequence = 0;
    const pending = new Map();
    const browserErrors = [];
    ws.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        if (message.id) {
            pending.get(message.id)?.(message);
            pending.delete(message.id);
        }
        if (message.method === 'Runtime.exceptionThrown' ||
            (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error')) {
            browserErrors.push(message.params);
        }
    });
    async function evaluate(expression) {
        const result = await new Promise(resolve => {
            const id = ++sequence;
            pending.set(id, resolve);
            ws.send(JSON.stringify({id, method: 'Runtime.evaluate',
                params: {expression: `Promise.resolve(eval(${JSON.stringify(expression)}))
                    .then(value => value instanceof Element ? true : value)`,
                    returnByValue: true, awaitPromise: true}}));
        });
        if (result.error || result.result.exceptionDetails) throw new Error(JSON.stringify(result));
        return result.result.result.value;
    }
    async function until(expression) {
        const deadline = Date.now() + 15000;
        while (Date.now() < deadline) {
            if (await evaluate(expression)) return;
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw new Error('Timed out: ' + expression);
    }
    const graph = name => `document.querySelector('#${name}-graph .js-plotly-plot')`;
    const status = name => `(document.getElementById('${name}-line-status')?.textContent || '')`;
    try {
        await new Promise(resolve => {
            const id = ++sequence;
            pending.set(id, resolve);
            ws.send(JSON.stringify({id, method: 'Runtime.enable'}));
        });
        browserErrors.length = 0;
        await evaluate('window.__smokeReload = true; location.reload()');
        await until(`window.__smokeReload !== true && ${status('main')}.includes('zoom in')`);
        // Plotly populates _fullData before dcc.Graph attaches its event
        // handlers. Wait for those handlers before sending a synthetic zoom.
        for (const name of ['main', 'sub']) {
            await until(`${graph(name)}?._ev?.listeners('plotly_relayout').length > 0`);
        }
        console.log('Plotly.js:', await evaluate('Plotly.version'));
        assert.ok(await evaluate(`${graph('main')}._fullData[0].x.length <= 2000`));
        const started = Date.now();
        await evaluate(`Plotly.relayout(${graph('main')}, {
            'xaxis2.range': [49990, 50010], 'yaxis.range': [0, 20]})`);
        await until(`${status('main')}.includes('full resolution')`);
        assert.equal(await evaluate(`${graph('main')}._fullData[0].x.length`), 23);
        assert.deepEqual(await evaluate(`${graph('main')}.layout.yaxis.range`), [0, 20]);
        console.log('Browser zoom to original samples, ms:', Date.now() - started);
        await evaluate(`Plotly.restyle(${graph('main')}, {visible: 'legendonly'}, [0])`);
        await evaluate(`Plotly.relayout(${graph('sub')}, {'xaxis.range': [60, 80]})`);
        await until(`${status('sub')}.includes('full resolution')`);
        assert.deepEqual(await evaluate(`${graph('main')}.layout.xaxis.range`), [49990, 50010]);
        assert.equal(await evaluate(`${graph('main')}._fullData[0].visible`), 'legendonly');
        await evaluate(`Plotly.relayout(${graph('main')}, {'xaxis.autorange': true})`);
        await until(`${status('main')}.includes('zoom in')`);
        await fetch('http://127.0.0.1:8057/expire-plot-cache', {method: 'POST'});
        await evaluate(`Plotly.relayout(${graph('main')}, {'xaxis.range': [10, 20]})`);
        await until(`${status('main')}.includes('full resolution')`);
        assert.deepEqual(await evaluate(`${graph('main')}.layout.xaxis.range`), [10, 20]);
        assert.equal(await evaluate(`${graph('main')}._fullData[0].visible`), 'legendonly');
        await evaluate(`window.dash_clientside.set_props('time-axis-unit', {value: 'min'});
            window.dash_clientside.set_props('dataset-choice', {value: ['one', 'two']});`);
        await new Promise(resolve => setTimeout(resolve, 200));
        await evaluate(`document.getElementById('update-graphs').click()`);
        await until(`${status('main')}.includes('400,000')`);
        await evaluate(`Plotly.relayout(${graph('main')}, {'xaxis.range': [1000/60, 1010/60]})`);
        await until(`${status('main')}.includes('full resolution')`);
        await until(`${graph('main')}._fullData.length === 4 &&
            ${graph('main')}._fullData[0].x.length === 13`);
        assert.equal(await evaluate(`${graph('main')}._fullData.length`), 4);
        assert.equal(await evaluate(`${graph('main')}._fullData[0].x.length`), 13);
        assert.equal(browserErrors.length, 0, 'No browser errors during the workflow');
        console.log('PASS: overview, zoom, legend/y state, cross section, reset, cache recovery, units, datasets');
    } catch (error) {
        console.error('Browser errors:', JSON.stringify(browserErrors));
        throw error;
    } finally {
        ws.close();
    }
}()).catch(error => { console.error(error); process.exitCode = 1; });
