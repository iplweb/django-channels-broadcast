# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  `CHANNELS_NOTIFICATIONS_SUBSCRIPTION_AUTHORIZER` runs once per
  channel in `?extraChannels=`. Default: deny everything (secure by default).
- Signed subscription tokens: `issue_subscription_token(user, channels, ttl)`
  binds a user to a channel list for N seconds, no Redis required —
  uses Django's `TimestampSigner`. Browser sends as
  `?subscription_token=`; consumer verifies signature + user match + TTL.
- Settings contract for individual audience gates:
  `CHANNELS_NOTIFICATIONS_ENABLE_{ALL,AUTHENTICATED,ANONYMOUS,PAGE_CHANNELS}`.
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

### Removed

- `NotificationsMiddleware` (BPP-specific `messages_extends` coupling).
- `send_message` management command (BPP-specific `messages_extends` coupling).
- Legacy migrations 0002/0003 squashed into a single `0001_initial`.
