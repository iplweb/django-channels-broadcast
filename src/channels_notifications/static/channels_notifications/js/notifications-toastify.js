/**
 * channels_notifications — opt-in toastify-js renderer.
 *
 * Replaces the default jQuery+Mustache rendering with right-side toast
 * popups via Toastify (https://github.com/apvarun/toastify-js — MIT,
 * ~3KB). Toastify must be on the page already.
 *
 * Usage:
 *   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js/src/toastify.css">
 *   <script src="https://cdn.jsdelivr.net/npm/toastify-js"></script>
 *   <script src="{% static 'channels_notifications/js/notifications.js' %}"></script>
 *   <script src="{% static 'channels_notifications/js/notifications-toastify.js' %}"></script>
 *   <script>
 *     channelsBroadcast.useToastify({duration: 4000, gravity: "top", position: "right"});
 *     channelsBroadcast.init();
 *   </script>
 *
 * After useToastify() is called, every {text, cssClass} message renders
 * as a Toastify popup instead of being appended to #messagesPlaceholder.
 * Redirect ({url}) and progress ({progress, percent}) payloads still go
 * through the default handler — those don't make sense as toasts.
 */
(function () {
    if (!window.channelsBroadcast) {
        console.warn("notifications-toastify.js loaded before notifications.js");
        return;
    }

    // Sensible per-level colours; users override via opts.classMap.
    var DEFAULT_BG = {
        info:    "linear-gradient(to right, #4a90e2, #357abd)",
        success: "linear-gradient(to right, #00b09b, #96c93d)",
        warning: "linear-gradient(to right, #f7971e, #ffd200)",
        error:   "linear-gradient(to right, #e74c3c, #c0392b)",
    };

    window.channelsBroadcast.useToastify = function (opts) {
        if (typeof Toastify === "undefined") {
            console.warn(
                "channels_notifications: Toastify is not loaded — call useToastify() " +
                "AFTER including <script src='.../toastify-js'></script>."
            );
            return;
        }

        opts = opts || {};
        var bgMap = Object.assign({}, DEFAULT_BG, opts.classMap || {});

        // Preserve the original so URL + progress payloads still work.
        var defaultAddMessage = this.addMessage.bind(this);

        this.addMessage = function (message) {
            if (!message.text) {
                // Non-text payloads (redirects, progress) — delegate to default.
                return defaultAddMessage(message);
            }

            var t = Toastify({
                text: message.text,
                duration: opts.duration != null ? opts.duration : 4000,
                gravity: opts.gravity || "top",
                position: opts.position || "right",
                close: !message.hideCloseOption,
                stopOnFocus: true,
                style: { background: bgMap[message.cssClass] || bgMap.info },
                onClick: function () {
                    if (message.clickURL) {
                        window.location.href = message.clickURL;
                    }
                },
            });
            t.showToast();

            // Chime hook still applies, if installed.
            if (typeof this.onChime === "function" && message.sound !== false) {
                try { this.onChime(message); }
                catch (e) { console.debug("channels_notifications: onChime threw", e); }
            }
        };
    };
})();
