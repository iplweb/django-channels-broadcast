/**
 * QUnit tests for notifications.js — the default jQuery+Mustache renderer.
 *
 * Mirrors the original BPP tests/qunit suite and extends it with cases
 * for the new payload types (redirects, progress).
 */

const QUnit = require("qunit");
const sinon = require("sinon");

QUnit.module("channelsBroadcast.addMessage", {
    beforeEach: function () {
        $("#messagesPlaceholder").empty();
        document.getElementById("notifications-progress").style.width = "";
    },
});

// ---- messages ---------------------------------------------------------

QUnit.test("text payload appends one element", function (assert) {
    assert.equal($("#messagesPlaceholder").children().length, 0, "placeholder empty");
    channelsBroadcast.addMessage({ text: "hello" });
    assert.equal($("#messagesPlaceholder").children().length, 1, "one child appended");
});

QUnit.test("text payload renders cssClass on inner div", function (assert) {
    channelsBroadcast.addMessage({ text: "hi", cssClass: "success" });
    assert.ok(
        $("#messagesPlaceholder").html().indexOf("success") !== -1,
        "rendered HTML mentions cssClass"
    );
});

QUnit.test("clickURL becomes an <a href>", function (assert) {
    channelsBroadcast.addMessage({ text: "hi", clickURL: "https://example.com/" });
    const href = $("#messagesPlaceholder").find("a").first().attr("href");
    assert.equal(href, "https://example.com/", "first anchor points at clickURL");
});

QUnit.test("closeURL becomes the closing link", function (assert) {
    channelsBroadcast.addMessage({ text: "hi", closeURL: "https://example.com/close" });
    const lastHref = $("#messagesPlaceholder").find("a").last().attr("href");
    assert.equal(lastHref, "https://example.com/close", "last anchor points at closeURL");
});

QUnit.test("hideCloseOption=true omits the close link", function (assert) {
    channelsBroadcast.addMessage({ text: "hi", hideCloseOption: true });
    assert.equal($("#messagesPlaceholder").find("a").length, 0, "no anchors at all");
});

QUnit.test("hideCloseOption unspecified renders close link", function (assert) {
    channelsBroadcast.addMessage({ text: "hi" });
    assert.equal($("#messagesPlaceholder").find("a").length, 1, "one close anchor present");
});

// ---- redirects --------------------------------------------------------

QUnit.test("url payload triggers goTo", function (assert) {
    const stub = sinon.stub(channelsBroadcast, "goTo");
    channelsBroadcast.addMessage({ url: "https://example.com/results/" });
    assert.ok(stub.calledOnce, "goTo called");
    assert.equal(stub.firstCall.args[0], "https://example.com/results/", "with the url");
    stub.restore();
});

QUnit.test("url payload does not append a message DOM element", function (assert) {
    const stub = sinon.stub(channelsBroadcast, "goTo");
    channelsBroadcast.addMessage({ url: "/x/" });
    assert.equal($("#messagesPlaceholder").children().length, 0, "no DOM children added");
    stub.restore();
});

// ---- progress ---------------------------------------------------------

QUnit.test("progress payload updates #notifications-progress width", function (assert) {
    channelsBroadcast.addMessage({ progress: true, percent: "75%" });
    assert.equal(
        document.getElementById("notifications-progress").style.width,
        "75%",
        "progress bar width set"
    );
});

QUnit.test("progress payload does not append a message", function (assert) {
    channelsBroadcast.addMessage({ progress: true, percent: "50%" });
    assert.equal($("#messagesPlaceholder").children().length, 0, "no DOM children added");
});

// ---- chime hook -------------------------------------------------------

QUnit.test("onChime is called for text payloads", function (assert) {
    const spy = sinon.spy();
    channelsBroadcast.onChime = spy;
    channelsBroadcast.addMessage({ text: "hi" });
    assert.ok(spy.calledOnce, "chime hook fired");
    delete channelsBroadcast.onChime;
});

QUnit.test("onChime is not called when message.sound === false", function (assert) {
    const spy = sinon.spy();
    channelsBroadcast.onChime = spy;
    channelsBroadcast.addMessage({ text: "hi", sound: false });
    assert.notOk(spy.called, "chime hook suppressed");
    delete channelsBroadcast.onChime;
});

QUnit.test("onChime is not called for redirect / progress payloads", function (assert) {
    const spy = sinon.spy();
    channelsBroadcast.onChime = spy;
    const stub = sinon.stub(channelsBroadcast, "goTo");
    channelsBroadcast.addMessage({ url: "/x/" });
    channelsBroadcast.addMessage({ progress: true, percent: "10%" });
    assert.notOk(spy.called, "chime only fires on messages, not redirects/progress");
    stub.restore();
    delete channelsBroadcast.onChime;
});

// ---- onmessage --------------------------------------------------------

QUnit.test("onmessage dispatches to addMessage", function (assert) {
    const spy = sinon.spy(channelsBroadcast, "addMessage");
    channelsBroadcast.onmessage({ data: JSON.stringify({ text: "wire" }) });
    assert.ok(spy.calledOnce, "addMessage called once");
    assert.equal(spy.firstCall.args[0].text, "wire", "with parsed payload");
    spy.restore();
});

QUnit.test("onmessage with id ACKs over the socket", function (assert) {
    const fakeSocket = { readyState: 1, sent: [], send(s) { this.sent.push(JSON.parse(s)); } };
    channelsBroadcast.chatSocket = fakeSocket;
    channelsBroadcast.onmessage({
        data: JSON.stringify({ id: 42, text: "stored" }),
        channel_name: "ch-x",
    });
    assert.equal(fakeSocket.sent.length, 1, "one ACK sent");
    assert.equal(fakeSocket.sent[0].type, "ack_message");
    assert.equal(fakeSocket.sent[0].id, 42);
    delete channelsBroadcast.chatSocket;
});

QUnit.test("onmessage without id does not ACK", function (assert) {
    const fakeSocket = { readyState: 1, sent: [], send(s) { this.sent.push(s); } };
    channelsBroadcast.chatSocket = fakeSocket;
    channelsBroadcast.onmessage({ data: JSON.stringify({ text: "no-id" }) });
    assert.equal(fakeSocket.sent.length, 0, "no ACK without id");
    delete channelsBroadcast.chatSocket;
});

QUnit.test("onmessage with malformed JSON does not throw", function (assert) {
    assert.expect(0);
    channelsBroadcast.onmessage({ data: "{ not json" });
});
