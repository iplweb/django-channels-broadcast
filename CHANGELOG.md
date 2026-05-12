# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial extraction from BPP (Bibliografia Publikacji Pracowników) monolith
  at commit `75f3c70f7`.
- Public audience-routing API: `send_to_all`, `send_to_authenticated`,
  `send_to_anonymous`, `send_to_user`, `send_to_object`.
- Settings contract for individual audience gates:
  `CHANNELS_NOTIFICATIONS_ENABLE_{ALL,AUTHENTICATED,ANONYMOUS,PAGE_CHANNELS}`.
- Anonymous visitors get no websocket connection at all when
  `ENABLE_ANONYMOUS=False` (default).
- `send_notification` management command with `--audience` flag.
- 42 unit + ASGI integration tests covering audience routing and
  flag enforcement.

### Removed

- `NotificationsMiddleware` (BPP-specific `messages_extends` coupling).
- `send_message` management command (BPP-specific `messages_extends` coupling).
- Legacy migrations 0002/0003 squashed into a single `0001_initial`.
