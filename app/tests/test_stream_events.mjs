import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { consumeSseBuffer, applyStreamEvent, initialStreamState } = require(
    '../static/stream_events.js',
);

test('tokens append', () => {
    let state = initialStreamState();
    state = applyStreamEvent(state, 'token', { text: 'Hello' });
    state = applyStreamEvent(state, 'token', { text: ', world' });
    assert.equal(state.streamed, 'Hello, world');
    assert.equal(state.sawToken, true);
});

test('reducer does not mutate its input', () => {
    const state = initialStreamState();
    applyStreamEvent(state, 'token', { text: 'x' });
    assert.deepEqual(state, initialStreamState());
});

test('sources with data.text rewrite the streamed answer (citation renumbering)', () => {
    let state = initialStreamState();
    state = applyStreamEvent(state, 'token', { text: 'Fact [3] and [5].' });
    const cards = [{ source: 'a.pdf' }, { source: 'b.pdf' }];
    state = applyStreamEvent(state, 'sources', {
        sources: cards,
        text: 'Fact [1] and [2].',
    });
    assert.equal(state.streamed, 'Fact [1] and [2].');
    assert.deepEqual(state.sources, cards);
});

test('sources without text keep the streamed answer', () => {
    let state = applyStreamEvent(initialStreamState(), 'token', { text: 'Answer' });
    state = applyStreamEvent(state, 'sources', { sources: [] });
    assert.equal(state.streamed, 'Answer');
    assert.deepEqual(state.sources, []);
});

test('footnote short note', () => {
    const state = applyStreamEvent(initialStreamState(), 'footnote', {
        text: 'Not found in your documents.',
    });
    assert.equal(state.footnote, 'Not found in your documents.');
});

test('notice, status, retrieved and error events', () => {
    let state = initialStreamState();
    state = applyStreamEvent(state, 'notice', { text: 'Heads up' });
    assert.equal(state.notice, 'Heads up');
    state = applyStreamEvent(state, 'status', { text: 'Searching…' });
    assert.equal(state.status, 'Searching…');
    state = applyStreamEvent(state, 'retrieved', { count: 1 });
    assert.equal(state.status, '1 passage found');
    state = applyStreamEvent(state, 'retrieved', { sources: [{}, {}] });
    assert.equal(state.status, '2 passages found');
    state = applyStreamEvent(state, 'error', {});
    assert.equal(state.error, 'The query could not be completed.');
    state = applyStreamEvent(state, 'error', { detail: 'boom' });
    assert.equal(state.error, 'boom');
});

test('SSE buffer framing keeps an incomplete trailing chunk', () => {
    const seen = [];
    const onEvent = (name, data) => seen.push([name, data]);

    let rest = consumeSseBuffer(
        'event: token\ndata: {"text":"a"}\n\nevent: token\ndata: {"te',
        onEvent,
    );
    assert.deepEqual(seen, [['token', { text: 'a' }]]);
    assert.equal(rest, 'event: token\ndata: {"te');

    rest = consumeSseBuffer(rest + 'xt":"b"}\n\n', onEvent);
    assert.deepEqual(seen, [
        ['token', { text: 'a' }],
        ['token', { text: 'b' }],
    ]);
    assert.equal(rest, '');
});

test('SSE framing defaults event name and skips data-less frames', () => {
    const seen = [];
    const rest = consumeSseBuffer(
        ': keepalive\n\ndata: {"x":1}\n\n',
        (name, data) => seen.push([name, data]),
    );
    assert.deepEqual(seen, [['message', { x: 1 }]]);
    assert.equal(rest, '');
});
