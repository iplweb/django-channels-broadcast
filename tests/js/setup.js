/**
 * Node-side test harness for the package's frontend JS.
 *
 * Shims a browser environment with jsdom, exposes jQuery + Mustache as
 * globals (the way the templates would in real use), then loads the
 * production notifications.js so QUnit assertions exercise the
 * shipped code, not a copy.
 *
 * IMPORTANT: require("jquery")(window) must run BEFORE we assign
 * global.window. If global.window is already set, jQuery's bootstrap
 * detects it and returns a jQuery collection object instead of the
 * usual constructor function — every $("...") call then breaks.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { JSDOM } = require("jsdom");

const dom = new JSDOM(
    `<!DOCTYPE html><html><body>
        <div id="messagesPlaceholder"></div>
        <div id="messageTemplate">
          <div data-alert class="alert-box radius {{ cssClass }}">
            {{#clickURL}}<a rel="nofollow" href="{{ clickURL }}">{{/clickURL}}
            {{ text }}
            {{#clickURL}}</a>{{/clickURL}}
            {{^hideCloseOption}}
              {{#closeURL}}
                <a rel="nofollow" href="{{ closeURL }}" class="close">{{{ closeText }}}{{ ^closeText }}&times;{{ /closeText }}</a>
              {{/closeURL}}
              {{^closeURL}}
                <a rel="nofollow" href="#" class="close">{{{ closeText }}}{{ ^closeText }}&times;{{ /closeText }}</a>
              {{/closeURL}}
            {{/hideCloseOption}}
          </div>
        </div>
        <div id="notifications-progress"></div>
    </body></html>`,
    { url: "http://localhost/", runScripts: "outside-only" }
);

// MUST come before global.window assignment — see module docstring.
const $ = require("jquery")(dom.window);
const Mustache = require("mustache");

global.window = dom.window;
global.document = dom.window.document;
global.$ = global.jQuery = $;
global.Mustache = Mustache;
global.WebSocket = class FakeWebSocket {
    constructor(url) { this.url = url; this.readyState = 1; }
    send() {}
    close() { this.readyState = 3; }
};
global.WebSocket.OPEN = 1;

// Make our shims visible inside the jsdom realm so production scripts
// using `window.X` find them where they expect.
dom.window.$ = $;
dom.window.jQuery = $;
dom.window.Mustache = Mustache;
dom.window.WebSocket = global.WebSocket;
dom.window.console = console;

// Load each script into the jsdom realm via vm.runInContext (the same
// API jsdom is built on). The script's bare `window`/`document`/`$`
// lookups resolve to dom.window via the context's global scope.
const jsRoot = path.join(
    __dirname, "..", "..", "src", "channels_notifications", "static",
    "channels_notifications", "js"
);

function loadScript(name) {
    const code = fs.readFileSync(path.join(jsRoot, name), "utf8");
    const ctx = dom.getInternalVMContext();
    vm.runInContext(code, ctx, { filename: name });
}

loadScript("notifications.js");
loadScript("notifications-toastify.js");

// Re-expose on the test harness's global so tests don't have to write window.X.
global.channelsBroadcast = dom.window.channelsBroadcast;
