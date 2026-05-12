/**
 * channels_notifications — vanilla JS + jQuery client.
 *
 * Exposes `window.channelsBroadcast` with:
 *   .init(extraChannels, opts)   — opens the websocket; subscribes
 *   .addMessage(message)         — dispatch one incoming payload
 *   .onmessage(event)            — websocket onmessage handler (ACKs + addMessage)
 *   .goTo(url)                   — internal: navigate the browser
 *
 * Recognised payload shapes (server-side functions that produce them):
 *   {text, cssClass, ...}        send_to_*       — rendered as a message
 *   {url}                        redirect_*      — navigates the page
 *   {progress: true, percent}    progress_*      — updates #notifications-progress
 *
 * Optional hooks (assign before .init()):
 *   onChime(message)             — called when a message arrives (e.g. Tone.js)
 *   render(message)              — replace the default Mustache append
 *
 * Plugins can override `addMessage` entirely — see notifications-toastify.js
 * for an opt-in right-side toast renderer.
 */
window.channelsBroadcast = window.channelsBroadcast || {};

window.channelsBroadcast.init = function (extraChannels, opts) {
    opts = opts || {};
    var self = this;

    var proto = (window.location.protocol === "https:" ? "wss:" : "ws:");
    var url = proto + "//" + window.location.host + "/asgi/notifications/";
    var params = [];
    if (extraChannels) {
        params.push("extraChannels=" + encodeURIComponent(extraChannels));
    }
    if (opts.subscriptionToken) {
        params.push("subscription_token=" + encodeURIComponent(opts.subscriptionToken));
    }
    if (params.length) {
        url += "?" + params.join("&");
    }

    this.chatSocket = new WebSocket(url);
    this.chatSocket.onmessage = function (e) { self.onmessage(e); };
    this.chatSocket.onopen    = function () { console.info("channels_notifications: connected"); };
    this.chatSocket.onclose   = function () { console.info("channels_notifications: closed"); };
    this.chatSocket.onerror   = function () { console.warn("channels_notifications: error"); };

    window.addEventListener("unload", function () {
        if (self.chatSocket && self.chatSocket.readyState === WebSocket.OPEN) {
            self.chatSocket.close();
        }
    });
};

window.channelsBroadcast.goTo = function (url) {
    window.location.href = url;
};

window.channelsBroadcast.onmessage = function (event) {
    var message;
    try {
        message = JSON.parse(event.data);
    } catch (e) {
        console.warn("channels_notifications: bad payload", event.data);
        return;
    }

    // ACK persistent Notification rows so the server doesn't replay them on reconnect.
    if (message.id && this.chatSocket && this.chatSocket.readyState === WebSocket.OPEN) {
        this.chatSocket.send(JSON.stringify({
            type: "ack_message",
            id: message.id,
            channel_name: event.channel_name,
        }));
    }

    this.addMessage(message);
};

window.channelsBroadcast.addMessage = function (message) {
    // Three known payload families:
    if (message.text) {
        // Message: append via Mustache template (#messageTemplate -> #messagesPlaceholder)
        var $ph = (typeof $ !== "undefined") ? $("#messagesPlaceholder") : null;
        if ($ph && $ph.length) {
            $ph.append(Mustache.render($("#messageTemplate").html(), message));
        } else if (typeof document !== "undefined") {
            // Minimal vanilla-JS fallback if jQuery/Mustache aren't present.
            var ph = document.getElementById("messagesPlaceholder");
            if (ph) {
                var div = document.createElement("div");
                div.className = "msg " + (message.cssClass || "info");
                div.textContent = message.text;
                ph.appendChild(div);
            }
        }

        if (typeof this.onChime === "function" && message.sound !== false) {
            try { this.onChime(message); }
            catch (e) { console.debug("channels_notifications: onChime threw", e); }
        }
        return;
    }

    if (message.url) {
        this.goTo(message.url);
        return;
    }

    if (message.progress) {
        var bar = (typeof $ !== "undefined") ? $("#notifications-progress") : null;
        if (bar && bar.length) {
            bar.css("width", message.percent);
        } else if (typeof document !== "undefined") {
            var el = document.getElementById("notifications-progress");
            if (el) { el.style.width = message.percent; }
        }
        return;
    }
};
