/**
 * channels_broadcast — vanilla JS + jQuery client.
 *
 * Exposes `window.channelsBroadcast` with:
 *   .init(extraChannels, opts)   — opens the websocket; idempotent (calling
 *                                  again closes the previous socket cleanly).
 *   .addMessage(message)         — dispatch one incoming payload to the DOM.
 *   .onmessage(event)            — websocket "message" handler (ACKs + dispatch).
 *   .goTo(url)                   — internal: navigate the browser.
 *   .close()                     — close the socket and stop reconnecting.
 *
 * Recognised payload shapes (server-side functions that produce them):
 *   {text, cssClass, clickURL, ...}   send_to_*       — message
 *   {url}                             redirect_*      — navigation
 *   {progress: true, percent}         progress_*      — progress bar
 *
 * `init(extraChannels, opts)` options:
 *   subscriptionToken: string         — server-issued signed token
 *   reconnect: bool | object          — see DEFAULT_RECONNECT below; pass
 *                                       `false` to disable, an object to tune.
 *   onConnectionChange(state, info)   — "connecting" | "open" | "closed" |
 *                                       "reconnecting" | "failed"
 *
 * Optional hooks (assigned on the global):
 *   onChime(message)                  — called per arriving message (sound = !== false)
 *
 * Plugins can override `addMessage` entirely — see notifications-toastify.js.
 */
(function () {
    "use strict";

    var GLOBAL_KEY = "channelsBroadcast";
    var DEFAULT_PATH = "/asgi/notifications/";
    var DEFAULT_RECONNECT = {
        enabled: true,
        initialDelay: 1000,        // ms
        maxDelay: 30000,           // ms
        backoffFactor: 2,
        maxAttempts: Infinity,     // tighten if you want to give up
    };

    var W = window;
    W[GLOBAL_KEY] = W[GLOBAL_KEY] || {};
    var cn = W[GLOBAL_KEY];

    // ------------------------------------------------------------- helpers

    function emitState(state, info) {
        var fn = cn._opts && cn._opts.onConnectionChange;
        if (typeof fn === "function") {
            try { fn(state, info || {}); }
            catch (e) { console.debug("channels_broadcast: onConnectionChange threw", e); }
        }
    }

    function detectRenderer() {
        // Decide once how we render text payloads; avoids per-call typeof checks
        // and clears up the "Mustache without jQuery silently drops fields" trap.
        var hasJQuery = typeof W.$ === "function" || typeof W.jQuery === "function";
        var hasMustache = typeof W.Mustache !== "undefined";
        if (hasJQuery && hasMustache) {
            var $ = W.$ || W.jQuery;
            return function jqueryMustache(message) {
                var $ph = $("#messagesPlaceholder");
                if (!$ph.length) return false;
                var tmpl = $("#messageTemplate").html();
                if (!tmpl) return false;
                $ph.append(W.Mustache.render(tmpl, message));
                return true;
            };
        }
        return function vanilla(message) {
            var ph = document.getElementById("messagesPlaceholder");
            if (!ph) return false;
            var div = document.createElement("div");
            div.className = "msg " + (message.cssClass || "info");
            div.textContent = message.text;
            ph.appendChild(div);
            return true;
        };
    }

    function normalizeExtraChannels(x) {
        // The server expects ?extraChannels=<JSON-array>. Accept array (auto-stringify)
        // or string (assume already-JSON); reject anything else.
        //
        // Returning null tells buildUrl() to omit the param entirely. We do that
        // for every "no channels" shape so we never emit a useless query string
        // like ?extraChannels=%5B%5D ([]) or ?extraChannels=%22%22 (""). The
        // latter is the classic Django footgun: {{ undefined|json_script }}
        // renders json.dumps('') === '""', which is a truthy 2-char string.
        if (x == null) return null;
        if (Array.isArray(x)) return x.length ? JSON.stringify(x) : null;
        if (typeof x === "string") {
            var s = x.trim();
            if (s === "") return null;
            try {
                var parsed = JSON.parse(s);
                // Already-JSON that isn't a non-empty array carries no channels
                // ([], "", null, 42, {}): drop it instead of forwarding noise.
                if (!Array.isArray(parsed) || parsed.length === 0) return null;
            } catch (e) {
                // Not JSON — honour the legacy "caller did the work" contract
                // and pass the raw string through verbatim.
            }
            return s;  // verbatim — preserves the caller's exact JSON formatting
        }
        return null;
    }

    function buildUrl(opts) {
        var proto = (W.location.protocol === "https:" ? "wss:" : "ws:");
        var url = proto + "//" + W.location.host + (opts.path || DEFAULT_PATH);
        var params = [];
        var ec = normalizeExtraChannels(opts.extraChannels);
        if (ec) params.push("extraChannels=" + encodeURIComponent(ec));
        if (opts.subscriptionToken) {
            params.push("subscription_token=" + encodeURIComponent(opts.subscriptionToken));
        }
        return params.length ? url + "?" + params.join("&") : url;
    }

    // ----------------------------------------------------------- listener mgmt

    function addManagedListener(target, type, listener) {
        target.addEventListener(type, listener);
        cn._listeners.push({ target: target, type: type, listener: listener });
    }

    function removeAllManagedListeners() {
        if (!cn._listeners) return;
        for (var i = 0; i < cn._listeners.length; i++) {
            var L = cn._listeners[i];
            L.target.removeEventListener(L.type, L.listener);
        }
        cn._listeners = [];
    }

    // ------------------------------------------------------------- reconnect

    function scheduleReconnect() {
        var r = cn._reconnect;
        if (!r.enabled || cn._closed) return;
        if (r.attempts >= r.maxAttempts) {
            emitState("failed", { attempts: r.attempts });
            return;
        }
        var delay = Math.min(
            r.initialDelay * Math.pow(r.backoffFactor, r.attempts),
            r.maxDelay
        );
        r.attempts += 1;
        emitState("reconnecting", { attempt: r.attempts, delayMs: delay });
        r.timer = setTimeout(function () { openSocket(); }, delay);
    }

    function clearReconnectTimer() {
        if (cn._reconnect && cn._reconnect.timer) {
            clearTimeout(cn._reconnect.timer);
            cn._reconnect.timer = null;
        }
    }

    // --------------------------------------------------------------- socket

    function openSocket() {
        var url = buildUrl(cn._opts);
        var ws;
        try {
            ws = new WebSocket(url);
        } catch (e) {
            // Some browsers throw synchronously on bad URLs / mixed content.
            console.warn("channels_broadcast: WebSocket open failed", e);
            emitState("closed", { error: String(e) });
            scheduleReconnect();
            return;
        }
        cn.chatSocket = ws;
        emitState("connecting");

        ws.addEventListener("open", function () {
            cn._reconnect.attempts = 0;
            emitState("open");
        });
        ws.addEventListener("close", function (e) {
            emitState("closed", { code: e.code, reason: e.reason });
            if (!cn._closed) scheduleReconnect();
        });
        ws.addEventListener("error", function () {
            // The "close" handler also fires; reconnect logic lives there
            // so we don't schedule twice.
        });
        ws.addEventListener("message", function (e) { cn.onmessage(e); });
    }

    // ------------------------------------------------------------- public API

    cn.init = function (extraChannels, opts) {
        opts = opts || {};

        // Re-entrant: close any previous socket + drop its listeners.
        cn.close({ silent: true });

        cn._closed = false;
        cn._listeners = [];
        cn._opts = {
            extraChannels: extraChannels,
            subscriptionToken: opts.subscriptionToken,
            path: opts.path,
            onConnectionChange: opts.onConnectionChange,
        };
        cn._reconnect = (opts.reconnect === false)
            ? { enabled: false, attempts: 0 }
            : Object.assign(
                { attempts: 0, timer: null },
                DEFAULT_RECONNECT,
                (typeof opts.reconnect === "object" && opts.reconnect) || {}
            );

        cn._render = detectRenderer();

        // Tab going away: close gracefully so the server's disconnect runs.
        // `pagehide` works on mobile Safari where `unload` doesn't.
        addManagedListener(W, "pagehide", function () {
            cn.close({ silent: true });
        });

        openSocket();
    };

    cn.close = function (opts) {
        opts = opts || {};
        cn._closed = true;
        clearReconnectTimer();
        if (cn.chatSocket) {
            try { cn.chatSocket.close(); }
            catch (e) { /* already closed */ }
            cn.chatSocket = null;
        }
        removeAllManagedListeners();
        if (!opts.silent) emitState("closed", { intentional: true });
    };

    cn.goTo = function (url) { W.location.href = url; };

    cn.onmessage = function (event) {
        if (typeof event.data !== "string") {
            // Binary frame — we don't speak any binary protocol.
            console.debug("channels_broadcast: non-string frame ignored");
            return;
        }
        var message;
        try { message = JSON.parse(event.data); }
        catch (e) {
            console.warn("channels_broadcast: bad JSON payload", event.data);
            return;
        }

        // ACK persistent Notification rows. The server matches by `id` alone;
        // we don't send channel_name (it's not on the standard MessageEvent
        // and was a dead field in the BPP-era client).
        if (message.id != null && cn.chatSocket
                && cn.chatSocket.readyState === WebSocket.OPEN) {
            cn.chatSocket.send(JSON.stringify({
                type: "ack_message",
                id: message.id,
            }));
        }

        cn.addMessage(message);
    };

    cn.addMessage = function (message) {
        if (message.text) {
            if (!cn._render) cn._render = detectRenderer();
            cn._render(message);
            if (typeof cn.onChime === "function" && message.sound !== false) {
                try { cn.onChime(message); }
                catch (e) { console.debug("channels_broadcast: onChime threw", e); }
            }
            return;
        }

        if (message.url) {
            cn.goTo(message.url);
            return;
        }

        if (message.progress) {
            var width = message.percent;
            var el = document.getElementById("notifications-progress");
            if (el) el.style.width = width;
            return;
        }
    };
})();
