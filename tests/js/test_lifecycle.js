/**
 * Lifecycle, reconnect, and connect-time tests for the hardened
 * notifications.js client.
 *
 * Driven via FakeWebSocket (a real EventTarget set up in setup.js) so we
 * can synthesise open/close/error/message events without a real network.
 * sinon's fake timers stand in for setTimeout so reconnect backoff is
 * deterministic.
 */

const QUnit = require("qunit");
const sinon = require("sinon");

function tearDown() {
    channelsBroadcast.close({ silent: true });
    FakeWebSocket.resetTracking();
}

QUnit.module("channelsBroadcast.init — URL construction", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("no extraChannels, no token — bare path", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("string extraChannels passed through verbatim", function (assert) {
    channelsBroadcast.init('["a", "b"]', { reconnect: false });
    assert.equal(
        FakeWebSocket.last.url,
        "ws://localhost/asgi/notifications/?extraChannels=" + encodeURIComponent('["a", "b"]')
    );
});

QUnit.test("array extraChannels gets auto-stringified (fixes BPP-era footgun)", function (assert) {
    channelsBroadcast.init(["a", "b"], { reconnect: false });
    // Should send valid JSON, NOT the CSV "a,b" that Array.toString() produces.
    var url = FakeWebSocket.last.url;
    var match = url.match(/extraChannels=([^&]+)/);
    assert.ok(match, "extraChannels in URL");
    var decoded = decodeURIComponent(match[1]);
    assert.deepEqual(JSON.parse(decoded), ["a", "b"]);
});

QUnit.test("subscription token + extraChannels together", function (assert) {
    channelsBroadcast.init(["c1"], { subscriptionToken: "abc.def.ghi", reconnect: false });
    var url = FakeWebSocket.last.url;
    assert.ok(url.indexOf("extraChannels=") !== -1);
    assert.ok(url.indexOf("subscription_token=abc.def.ghi") !== -1);
});

QUnit.test("custom path option overrides /asgi/notifications/", function (assert) {
    channelsBroadcast.init(null, { path: "/ws/notif/", reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/ws/notif/");
});

QUnit.test("non-array/non-string extraChannels is silently dropped", function (assert) {
    channelsBroadcast.init(42, { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("empty array drops the param (no ?extraChannels=%5B%5D)", function (assert) {
    channelsBroadcast.init([], { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("'[]' string (already-JSON empty list) drops the param", function (assert) {
    channelsBroadcast.init("[]", { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("'\"\"' from {{ undefined|json_script }} drops the param (no %22%22)", function (assert) {
    // Django's {{ extraChannels|json_script }} on an undefined var renders
    // json.dumps('') === '""'. That used to leak as ?extraChannels=%22%22.
    channelsBroadcast.init('""', { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("'null' string (already-JSON null) drops the param", function (assert) {
    channelsBroadcast.init("null", { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("whitespace-only string drops the param", function (assert) {
    channelsBroadcast.init("   ", { reconnect: false });
    assert.equal(FakeWebSocket.last.url, "ws://localhost/asgi/notifications/");
});

QUnit.test("non-JSON string still passes through verbatim (legacy contract)", function (assert) {
    // A caller that hand-built a non-JSON channel token keeps working.
    channelsBroadcast.init("ch-token", { reconnect: false });
    assert.equal(
        FakeWebSocket.last.url,
        "ws://localhost/asgi/notifications/?extraChannels=ch-token"
    );
});


QUnit.module("channelsBroadcast.init — re-entrant", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("calling init twice closes the previous socket", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    var first = FakeWebSocket.last;
    assert.equal(first.readyState, FakeWebSocket.CONNECTING);
    channelsBroadcast.init(null, { reconnect: false });
    var second = FakeWebSocket.last;
    assert.notStrictEqual(first, second, "second init opened a new socket");
    assert.equal(first.readyState, FakeWebSocket.CLOSED, "first socket was closed");
});

QUnit.test("close() stops further reconnect attempts", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 100, maxDelay: 100, backoffFactor: 1 },
        });
        var initialCount = FakeWebSocket.constructed.length;
        FakeWebSocket.last.__emitClose(1006); // unexpected close → schedules reconnect
        channelsBroadcast.close();
        clock.tick(1000);
        assert.equal(
            FakeWebSocket.constructed.length, initialCount,
            "no new sockets after explicit close()"
        );
    } finally {
        clock.restore();
    }
});


QUnit.module("channelsBroadcast — reconnect with backoff", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("unexpected close schedules reconnect after initialDelay", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 500, maxDelay: 5000, backoffFactor: 2 },
        });
        var firstCount = FakeWebSocket.constructed.length;
        FakeWebSocket.last.__emitClose(1006);
        // No new socket yet:
        assert.equal(FakeWebSocket.constructed.length, firstCount, "no immediate reconnect");
        clock.tick(499);
        assert.equal(FakeWebSocket.constructed.length, firstCount, "not yet at delay");
        clock.tick(1);
        assert.equal(FakeWebSocket.constructed.length, firstCount + 1, "reconnected at delay");
    } finally {
        clock.restore();
    }
});

QUnit.test("backoff doubles on repeated failures", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 100, maxDelay: 60000, backoffFactor: 2 },
        });
        assert.equal(FakeWebSocket.constructed.length, 1, "1 initial socket");

        // Trigger close → schedule attempt 1 (delay 100)
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(99);
        assert.equal(FakeWebSocket.constructed.length, 1, "not yet at 100ms");
        clock.tick(1);
        assert.equal(FakeWebSocket.constructed.length, 2, "reconnect at 100ms");

        // Trigger close → schedule attempt 2 (delay 200)
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(199);
        assert.equal(FakeWebSocket.constructed.length, 2, "not yet at 200ms");
        clock.tick(1);
        assert.equal(FakeWebSocket.constructed.length, 3, "reconnect at 200ms");

        // Trigger close → schedule attempt 3 (delay 400)
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(399);
        assert.equal(FakeWebSocket.constructed.length, 3, "not yet at 400ms");
        clock.tick(1);
        assert.equal(FakeWebSocket.constructed.length, 4, "reconnect at 400ms");
    } finally {
        clock.restore();
    }
});

QUnit.test("backoff respects maxDelay cap", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 100, maxDelay: 250, backoffFactor: 3 },
        });
        // Attempt 1: delay 100 (100*3^0). Attempt 2: 300→capped to 250.
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(100);
        var afterFirst = FakeWebSocket.constructed.length;
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(249);
        assert.equal(FakeWebSocket.constructed.length, afterFirst, "not yet at capped delay");
        clock.tick(1);
        assert.equal(FakeWebSocket.constructed.length, afterFirst + 1, "reconnected at capped delay");
    } finally {
        clock.restore();
    }
});

QUnit.test("successful open resets the attempt counter", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 100, maxDelay: 60000, backoffFactor: 2 },
        });
        FakeWebSocket.last.__emitClose(1006);    // attempt 1 scheduled @100ms
        clock.tick(100);
        FakeWebSocket.last.__emitClose(1006);    // attempt 2 scheduled @200ms
        clock.tick(200);
        // Now succeed:
        FakeWebSocket.last.__emitOpen();
        var before = FakeWebSocket.constructed.length;
        FakeWebSocket.last.__emitClose(1006);    // fresh failure
        clock.tick(99);
        assert.equal(FakeWebSocket.constructed.length, before, "still waiting for initialDelay");
        clock.tick(1);
        assert.equal(
            FakeWebSocket.constructed.length, before + 1,
            "counter reset → first attempt uses initialDelay, not 400ms"
        );
    } finally {
        clock.restore();
    }
});

QUnit.test("maxAttempts cap emits failed state", function (assert) {
    const clock = sinon.useFakeTimers();
    var states = [];
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 1, maxDelay: 1, backoffFactor: 1, maxAttempts: 2 },
            onConnectionChange: function (s) { states.push(s); },
        });
        for (var i = 0; i < 5; i++) {
            FakeWebSocket.last.__emitClose(1006);
            clock.tick(10);
        }
        assert.ok(states.indexOf("failed") !== -1, "failed state emitted");
    } finally {
        clock.restore();
    }
});

QUnit.test("reconnect: false disables retry entirely", function (assert) {
    const clock = sinon.useFakeTimers();
    try {
        channelsBroadcast.init(null, { reconnect: false });
        var before = FakeWebSocket.constructed.length;
        FakeWebSocket.last.__emitClose(1006);
        clock.tick(60000);
        assert.equal(FakeWebSocket.constructed.length, before, "no reconnect attempts");
    } finally {
        clock.restore();
    }
});


QUnit.module("channelsBroadcast — onConnectionChange", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("emits connecting → open on first connect", function (assert) {
    var states = [];
    channelsBroadcast.init(null, {
        reconnect: false,
        onConnectionChange: function (s) { states.push(s); },
    });
    FakeWebSocket.last.__emitOpen();
    assert.deepEqual(states, ["connecting", "open"]);
});

QUnit.test("emits closed when socket closes", function (assert) {
    var states = [];
    channelsBroadcast.init(null, {
        reconnect: false,
        onConnectionChange: function (s) { states.push(s); },
    });
    FakeWebSocket.last.__emitOpen();
    FakeWebSocket.last.__emitClose(1006);
    assert.ok(states.indexOf("closed") !== -1);
});

QUnit.test("emits reconnecting with attempt + delay info", function (assert) {
    const clock = sinon.useFakeTimers();
    var events = [];
    try {
        channelsBroadcast.init(null, {
            reconnect: { initialDelay: 250, maxDelay: 1000, backoffFactor: 2 },
            onConnectionChange: function (s, info) { events.push({ s: s, info: info }); },
        });
        FakeWebSocket.last.__emitClose(1006);
        var reconnecting = events.filter(function (e) { return e.s === "reconnecting"; });
        assert.equal(reconnecting.length, 1, "one reconnecting event");
        assert.equal(reconnecting[0].info.attempt, 1);
        assert.equal(reconnecting[0].info.delayMs, 250);
        clock.tick(250);
    } finally {
        clock.restore();
    }
});

QUnit.test("intentional close() emits closed with intentional=true", function (assert) {
    var captured = null;
    channelsBroadcast.init(null, {
        reconnect: false,
        onConnectionChange: function (s, info) {
            if (s === "closed") captured = info;
        },
    });
    channelsBroadcast.close();
    assert.ok(captured, "got a closed event");
    assert.strictEqual(captured.intentional, true);
});


QUnit.module("channelsBroadcast.onmessage — defensive parsing", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("binary frame (non-string data) is ignored, no throw", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    var spy = sinon.spy(channelsBroadcast, "addMessage");
    FakeWebSocket.last.__emitMessage(new Uint8Array([1, 2, 3]).buffer);
    assert.notOk(spy.called, "addMessage NOT invoked for binary frame");
    spy.restore();
});

QUnit.test("message with id=0 still triggers ACK (was a real bug)", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    FakeWebSocket.last.__emitOpen();
    FakeWebSocket.last.__emitMessage(JSON.stringify({ id: 0, text: "hi" }));
    assert.equal(FakeWebSocket.last.sent.length, 1, "one ACK sent for id=0");
    var ack = JSON.parse(FakeWebSocket.last.sent[0]);
    assert.equal(ack.id, 0);
    assert.equal(ack.type, "ack_message");
});

QUnit.test("ACK no longer carries the dead channel_name field", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    FakeWebSocket.last.__emitOpen();
    FakeWebSocket.last.__emitMessage(JSON.stringify({ id: 42, text: "hi" }));
    var ack = JSON.parse(FakeWebSocket.last.sent[0]);
    assert.notOk("channel_name" in ack, "channel_name absent from ACK payload");
});

QUnit.test("ACK is skipped when socket isn't in OPEN state", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    // No __emitOpen — socket is still CONNECTING
    FakeWebSocket.last.__emitMessage(JSON.stringify({ id: 1, text: "hi" }));
    assert.equal(FakeWebSocket.last.sent.length, 0, "no ACK while CONNECTING");
});


QUnit.module("channelsBroadcast — pagehide handling", {
    beforeEach: tearDown,
    afterEach: tearDown,
});

QUnit.test("pagehide event closes the socket", function (assert) {
    channelsBroadcast.init(null, { reconnect: false });
    var sock = FakeWebSocket.last;
    sock.__emitOpen();
    assert.equal(sock.readyState, FakeWebSocket.OPEN);
    window.dispatchEvent(new window.Event("pagehide"));
    assert.equal(sock.readyState, FakeWebSocket.CLOSED, "socket closed on pagehide");
});

QUnit.test("repeated init() does not pile up pagehide listeners", function (assert) {
    // Init three times; close each. If listeners weren't removed, the
    // fourth init's pagehide would close-and-reopen via the leaked refs.
    for (var i = 0; i < 3; i++) {
        channelsBroadcast.init(null, { reconnect: false });
    }
    var beforeCount = FakeWebSocket.constructed.length;
    window.dispatchEvent(new window.Event("pagehide"));
    // The currently-live socket got closed, but no extras were touched.
    var openAfter = FakeWebSocket.constructed.filter(function (s) {
        return s.readyState !== FakeWebSocket.CLOSED;
    });
    assert.equal(openAfter.length, 0, "no leaked listeners reopened anything");
    assert.equal(FakeWebSocket.constructed.length, beforeCount, "no new sockets opened");
});
