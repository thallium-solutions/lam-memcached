# @lam/memcached Changelog

All notable changes to `@lam/memcached` are documented here.

## [2.0.4] - 2026-11-14

### Fixed

- `incr`/`decr` return a `MemcachedError` for a counter above the `int`
  range. Memcached counters are unsigned 64-bit and the value was converted
  with `int(value)`, so incrementing past 9223372036854775807 returned a
  negative number.
- `test-services.sh`: the `localhost:11212` fixture really requires SASL
  PLAIN credentials. The official `memcached` image ignores
  `MEMCACHED_USERNAME`/`MEMCACHED_PASSWORD`, so the "auth" fixture accepted
  every client and the `_auth` tests never exercised authentication; it now
  runs `memcached -S` with a SASL configuration and password file generated
  in a temporary directory.

### Tests

- `tests/test_memcached_edge_cases.lam`: key limits in bytes (empty, 250/251
  bytes, 125/126 `é`), spaces and non-ASCII keys; byte-exact values (every
  byte value), empty and non-ASCII values, 1 MB stored and 2 MB refused;
  counters on text, the zero floor and the int-range overflow; expiry,
  `touch` and `add` after expiry; a refused port and every operation on a
  closed client.
- `tests/test_memcached_sasl_auth.lam`: correct, wrong and missing
  credentials against the SASL fixture, shared data between authenticated
  clients, 8 concurrent authenticated connections.
- `tests/test_memcached_cache_composed.lam`: a cache-aside `ProductCache`
  class (JSON values with non-ASCII text, `add` so concurrent loaders store
  once, counters incremented from 60 async tasks, an append-only log,
  invalidation, `?` and `do/catch`).

## [2.0.3] - 2026-11-03

### Changed

- Compatible with `lamc` 4.x: `compatibility.lamc = ">=1.18, <5"` (test runner too).

## [2.0.2] - 2026-10-20

### Changed

- Compatible with `lamc` 3.x: `compatibility.lamc = ">=1.18, <4"` (test runner too).

## [2.0.1] - 2026-10-18

### Changed

- Compatible with `lamc` 2.x: `compatibility.lamc = ">=1.18, <3"` (the test
  runner accepts the same range). Tested with `lamc` 2.0.0; no API change.

## 2.0.0 - 2026-10-15

### Removed

- **Breaking:** removed the root `tag()` helper. The package name and version
  are declared in `lamlib.toml`, and the generic top-level function made this
  package impossible to link together with any other package (or application)
  that also declared `tag()`, because all Lam modules share one Go package.

### Changed

- Replaced expected service/transport panics with unsuffixed, typed `Result[T]`
  APIs across connection, storage, counters, maintenance, metadata, and close.
- Changed `Memcached.connect` to return `Result[Memcached]` while preserving its
  eager `NOOP` handshake and cleaning up the pool when that handshake fails.
- Changed missing `get` from the ambiguous empty-string sentinel to a
  `MemcachedNotFound` error; explicit conditional-mutation outcomes remain
  `Ok(false)` values.
- Fixed append/prepend misses by treating `mc/v3`'s `ErrValueNotStored` as
  `Ok(false)` instead of a transport error.
- Replaced the class constructor spelling `__init__` with `init`, added argument
  validation, and limited raw Go to the `mc/v3` boundary.
- Bumped the package major version to 2.0.0 and compiler compatibility to
  `lamc ^1.18`.
- Updated consumer tests and examples to handle or propagate `Result` values.

### Testing

- Added a service-backed installed-package matrix across plain/authenticated
  clients, storage and counters, typed misses, validation, cleanup, and close.

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
