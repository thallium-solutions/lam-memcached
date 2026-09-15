# @lam/memcached Changelog

All notable changes to `@lam/memcached` are documented here.

## 1.0.0 - 2026-09-13

### Added

- Initial standalone `@lam/memcached` package migrated from Lammergeier's
  `lamemcached` standard-library module.
- Binary-protocol `Memcached` client backed by `github.com/memcachier/mc/v3`
  v3.0.3.
- String operations, TTL updates, conditional writes, deletion, append/prepend,
  atomic increment/decrement, flush, liveness, version, and stats APIs.
- Optional SASL PLAIN username/password connection path with an eager `NOOP`
  handshake.
- Scoped package-root exports through `__init__.lam` and package version tag.
- Consumer-style integration runner with Lam compiler version enforcement,
  case filters, compile-only mode, service diagnostics, and honest skips.
- Package-local Docker service helper for unauthenticated and auth-path fixtures,
  with safe reuse and cleanup behavior.
- Migrated standard-library Memcached integration and auth-path tests using
  `from @lam/memcached import Memcached`.
- Installation, configuration, usage, authentication, and service-testing
  documentation.
