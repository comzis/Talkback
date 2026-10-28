(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.TalkbackStream = api;
})(typeof window !== 'undefined' ? window : null, function () {
    // Split an SSE buffer into events; returns the unfinished trailing chunk.
    function consumeSseBuffer(buffer, onEvent) {
        const parts = buffer.split('\n\n');
        const rest = parts.pop();
        parts.forEach(part => {
            if (!part.trim()) return;
            let eventName = 'message';
            const dataLines = [];
            part.split('\n').forEach(line => {
                if (line.startsWith('event:')) eventName = line.slice(6).trim();
                else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
            });
            if (!dataLines.length) return;
            onEvent(eventName, JSON.parse(dataLines.join('\n')));
        });
        return rest;
    }

    function initialStreamState() {
        return {
            streamed: '',
            sawToken: false,
            footnote: '',
            sources: [],
            notice: '',
            status: '',
            error: '',
        };
    }

    // Pure reducer: returns a new state and never mutates the input.
    function applyStreamEvent(state, eventName, data) {
        const payload = data || {};
        const next = Object.assign({}, state);
        if (eventName === 'token') {
            if (!state.sawToken) next.streamed = '';
            next.sawToken = true;
            next.streamed += payload.text || '';
        } else if (eventName === 'footnote') {
            next.footnote = payload.text || '';
        } else if (eventName === 'sources') {
            next.sources = payload.sources || [];
            if (typeof payload.text === 'string') next.streamed = payload.text;
        } else if (eventName === 'notice') {
            next.notice = payload.text || '';
        } else if (eventName === 'error') {
            next.error = payload.detail || 'The query could not be completed.';
        } else if (eventName === 'retrieved') {
            const count = Number(payload.count) || (payload.sources || []).length;
            next.status = `${count} passage${count === 1 ? '' : 's'} found`;
        } else if (eventName === 'status') {
            next.status = payload.text || '';
        }
        return next;
    }

    return { consumeSseBuffer, applyStreamEvent, initialStreamState };
});
