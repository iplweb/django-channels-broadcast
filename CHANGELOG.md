# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Support for Django 6.1 (tested in CI on Python 3.12 and 3.13; Django 6.1
  requires Python ≥ 3.12).

## [0.2.1] - 2026-06-18

### Fixed

- `notifications.js` no longer emits a useless `?extraChannels=` query
  param when there are no channels to subscribe to. `normalizeExtraChannels`
  now returns `null` (→ param omitted) for an empty array, the already-JSON
  strings `"[]"`, `'""'` and `"null"`, and whitespace-only input. The `'""'`
  case is the common Django footgun where `{{ extraChannels|json_script }}`
  on an undefined context variable renders `json.dumps('') === '""'`, which
  used to leak as `?extraChannels=%22%22`. Non-empty arrays and non-JSON
  strings are unchanged (the latter still pass through verbatim).

## [0.2.0] - 2026-05-13

### Changed (breaking)

- Renamed Python package `channels_notifications` → `channels_broadcast`.
  All imports, the Django app label, and the settings prefix
  `CHANNELS_NOTIFICATIONS_*` → `CHANNELS_BROADCAST_*` change in lockstep.
  The `AppConfig` class is now `ChannelsBroadcastConfig`. Update
  `INSTALLED_APPS`, every `from channels_notifications import …`, and
  any `CHANNELS_NOTIFICATIONS_*` settings keys in your project.

## [0.1.0]

### Added

- Initial extraction from BPP (Bibliografia Publikacji Pracowników) monolith
  at commit `75f3c70f7`.
- Public audience-routing API: `send_to_all`, `send_to_authenticated`,
  `send_to_anonymous`, `send_to_user`, `send_to_object`,
  plus `send_to_channel` for raw channel names.
- Redirect API: `redirect_user`, `redirect_object`, `redirect_channel` —
  tell the receiving page to navigate to a URL.
- Progress API: `progress_user`, `progress_object`, `progress_channel` —
  push a percent to a progress bar.
- Subscription authorization: settings-pluggable callable
  `CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER` runs once per
  channel in `?extraChannels=`. Default: deny everything (secure by default).
- Signed subscription tokens: `issue_subscription_token(user, channels, ttl)`
  binds a user to a channel list for N seconds, no Redis required —
  uses Django's `TimestampSigner`. Browser sends as
  `?subscription_token=`; consumer verifies signature + user match + TTL.
- Settings contract for individual audience gates:
  `CHANNELS_BROADCAST_ENABLE_{ALL,AUTHENTICATED,ANONYMOUS,PAGE_CHANNELS}`.
- Anonymous visitors get no websocket connection at all when
  `ENABLE_ANONYMOUS=False` (default).
- `send_notification` management command with `--audience` flag.
- 80 unit + ASGI integration tests covering audience routing, flag
  enforcement, redirect/progress payloads, authorizer hook, and
  signed-token subscription including tampered/expired/cross-user cases.
- 22 QUnit + sinon frontend tests run via Node (`npm test`) using
  jsdom — covering the default Mustache renderer, redirect / progress
  payload handling, ACK behaviour, the chime hook, and the Toastify
  integration with stubbed Toastify.
- Optional opt-in JS plugins: `notifications-toastify.js` (right-side
  toast popups via Toastify, ~3KB) and `notifications-chime.js`
  (four-note arpeggio via Tone.js, user-gesture deferred).
- Example project demonstrates all five audience modes plus the
  authorizer (owner-only) and signed-token UID flows.

### Changed

- JS global renamed from `bppNotifications` to `channelsBroadcast` for
  the public package. Existing payload shapes (`{text, cssClass, ...}`,
  `{url}`, `{progress, percent}`) and Mustache template contract
  unchanged.
- Tone.js audio code extracted out of `notifications.js` into an
  optional sibling `notifications-chime.js`. Core `notifications.js`
  no longer depends on Tone.js being loaded.
- `send_notification` management command rewritten:
  - Now reaches every function in `channels_broadcast.api` —
    messages, redirects, progress, across all six audience targets
    (`all`, `authenticated`, `anonymous`, `user`, `object`, `channel`).
  - New `--kind=`, `--object=app.Model:pk`, `--channel=` flags.
  - **Interactive wizard mode**: run with no arguments (or just
    some flags) from a TTY and the command prompts for kind →
    audience → target → level → payload. Non-TTY (cron, systemd)
    keeps the fail-fast "X is required" behaviour.
  - `--kind={redirect,progress}` is rejected for broadcast audiences
    (`all`/`authenticated`/`anonymous`) — those require a specific
    recipient.
  - When the relevant `ENABLE_*` flag is False, exits 0 with a
    `No-op: ...` stdout warning rather than silently swallowing.

### Removed

- `NotificationsMiddleware` (BPP-specific `messages_extends` coupling).
- `send_message` management command (BPP-specific `messages_extends` coupling).
- Legacy migrations 0002/0003 squashed into a single `0001_initial`.
