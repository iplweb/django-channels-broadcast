/**
 * QUnit tests for notifications-toastify.js — opt-in toast renderer.
 *
 * We don't load the real Toastify library (it's a CDN/runtime concern);
 * instead we install a stub and assert useToastify() routes text
 * payloads through it while still delegating url/progress to the
 * default handler.
 *
 * Each test re-wraps useToastify on a fresh-ish addMessage by stashing
 * the un-wrapped function on first load and restoring it before each test.
 */

const QUnit = require("qunit");
const sinon = require("sinon");

// First-load snapshot of the un-wrapped addMessage, captured before any test runs.
const ORIGINAL_ADD_MESSAGE = channelsBroadcast.addMessage;

QUnit.module("channelsBroadcast.useToastify", {
    beforeEach: function () {
        $("#messagesPlaceholder").empty();
        document.getElementById("notifications-progress").style.width = "";
        // Reset to the un-wrapped version so each test sees a clean
        // addMessage to wrap (otherwise useToastify wraps a wrapper).
        channelsBroadcast.addMessage = ORIGINAL_ADD_MESSAGE;
    },
});

function withStubbedToastify(fn) {
    const showToastSpy = sinon.spy();
    const factory = sinon.stub().returns({ showToast: showToastSpy });
    // toastify-js shim must live in the same realm as the script under test.
    window.Toastify = factory;
    try {
        fn(factory, showToastSpy);
    } finally {
        delete window.Toastify;
    }
}

QUnit.test("useToastify with Toastify missing warns and is a no-op", function (assert) {
    const stub = sinon.stub(console, "warn");
    const original = channelsBroadcast.addMessage;
    channelsBroadcast.useToastify();
    assert.ok(stub.called, "warned about missing Toastify");
    assert.strictEqual(channelsBroadcast.addMessage, original, "addMessage untouched");
    stub.restore();
});

QUnit.test("after useToastify, text payloads invoke Toastify", function (assert) {
    withStubbedToastify(function (factory, showToastSpy) {
        channelsBroadcast.useToastify({ duration: 2000 });
        channelsBroadcast.addMessage({ text: "hello", cssClass: "success" });
        assert.ok(factory.calledOnce, "Toastify factory called once");
        assert.ok(showToastSpy.calledOnce, ".showToast() called once");
        const opts = factory.firstCall.args[0];
        assert.equal(opts.text, "hello", "text passed through");
        assert.equal(opts.duration, 2000, "duration override honoured");
        assert.equal(opts.position, "right", "default position is right");
    });
});

QUnit.test("after useToastify, url payloads still trigger goTo (delegated)", function (assert) {
    withStubbedToastify(function (factory, showToastSpy) {
        channelsBroadcast.useToastify();
        const stub = sinon.stub(channelsBroadcast, "goTo");
        channelsBroadcast.addMessage({ url: "/results/" });
        assert.notOk(showToastSpy.called, "Toastify NOT invoked for redirect");
        assert.ok(stub.calledOnce, "goTo called");
        assert.equal(stub.firstCall.args[0], "/results/");
        stub.restore();
    });
});

QUnit.test("after useToastify, progress payloads still update the bar (delegated)", function (assert) {
    withStubbedToastify(function (factory, showToastSpy) {
        channelsBroadcast.useToastify();
        channelsBroadcast.addMessage({ progress: true, percent: "33%" });
        assert.notOk(showToastSpy.called, "Toastify NOT invoked for progress");
        assert.equal(
            document.getElementById("notifications-progress").style.width,
            "33%",
            "progress bar updated"
        );
    });
});

QUnit.test("classMap option lets users override per-level colours", function (assert) {
    withStubbedToastify(function (factory) {
        channelsBroadcast.useToastify({
            classMap: { success: "linear-gradient(red, blue)" },
        });
        channelsBroadcast.addMessage({ text: "ok", cssClass: "success" });
        const opts = factory.firstCall.args[0];
        assert.equal(opts.style.background, "linear-gradient(red, blue)");
    });
});
