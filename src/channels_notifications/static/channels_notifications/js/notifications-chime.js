/**
 * channels_notifications — optional audio-chime plugin.
 *
 * Plays a four-note arpeggio (C5 E5 G5 C6, sine PolySynth) whenever a
 * message arrives. Off by default — load this script AFTER notifications.js
 * AND include Tone.js (https://tonejs.github.io/) to enable.
 *
 * Browsers don't allow audio without a user gesture; this plugin defers
 * Tone.start() until the first click or keydown anywhere on the page.
 *
 * Usage:
 *   <script src="https://unpkg.com/tone@15/build/Tone.js"></script>
 *   <script src="{% static 'channels_notifications/js/notifications.js' %}"></script>
 *   <script src="{% static 'channels_notifications/js/notifications-chime.js' %}"></script>
 *   <script>
 *     channelsBroadcast.init();
 *     channelsBroadcast.enableChime();   // installs the onChime hook
 *   </script>
 */
(function () {
    if (!window.channelsBroadcast) {
        console.warn("notifications-chime.js loaded before notifications.js");
        return;
    }

    var state = { synth: null, ready: false };

    function setupSynth() {
        if (state.ready || typeof Tone === "undefined") return;
        Tone.start().then(function () {
            state.synth = new Tone.PolySynth(Tone.Synth, {
                oscillator: { type: "sine" },
                envelope: { attack: 0.01, decay: 0.3, sustain: 0.1, release: 0.8 },
            }).toDestination();
            state.synth.volume.value = -14;
            state.ready = true;
        }).catch(function (err) {
            console.debug("channels_notifications: audio context unavailable", err);
        });
    }

    function playArpeggio() {
        if (!state.ready || typeof Tone === "undefined") return;
        try {
            var now = Tone.now();
            state.synth.triggerAttackRelease("C5", 0.1, now);
            state.synth.triggerAttackRelease("E5", 0.1, now + 0.05);
            state.synth.triggerAttackRelease("G5", 0.1, now + 0.10);
            state.synth.triggerAttackRelease("C6", 0.15, now + 0.15);
        } catch (err) {
            console.debug("channels_notifications: chime failed", err);
        }
    }

    window.channelsBroadcast.enableChime = function () {
        function gestureOnce() {
            setupSynth();
            document.removeEventListener("click", gestureOnce);
            document.removeEventListener("keydown", gestureOnce);
        }
        document.addEventListener("click", gestureOnce);
        document.addEventListener("keydown", gestureOnce);

        // If the user already clicked before this ran (unlikely), prime now.
        if (typeof Tone !== "undefined" && Tone.context && Tone.context.state === "running") {
            setupSynth();
        }

        // Wire chime into the message dispatcher.
        var prev = window.channelsBroadcast.onChime;
        window.channelsBroadcast.onChime = function (message) {
            if (typeof prev === "function") prev.call(this, message);
            playArpeggio();
        };
    };
})();
