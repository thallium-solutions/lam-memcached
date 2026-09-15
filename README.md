# @lam/memcached

`@lam/memcached` is a binary-protocol Memcached client for the
[Lammergeier programming language](https://github.com/thallium-solutions/lammergeier-lang).
It provides a small Lam API for strings, expiration, atomic counters, server
metadata, and optional SASL PLAIN credentials.

The package is backed by
[`github.com/memcachier/mc/v3`](https://github.com/memcachier/mc), pinned to
`v3.0.3`. That client uses Memcached's binary protocol, which is required for
SASL authentication. Direct Go code is kept at this Memcached client boundary;
applications use the Lam `Memcached` class.

## Requirements

- `lamc` 1.16.0 or newer within the compatible `^1.16` range.
- A reachable Memcached server for runtime operations.
- Go module downloads during the first build unless they are already cached.

## Installation

From the package registry:

```bash
lamc install @lam/memcached@1.0.0
```

Directly from Git:

```bash
lamc install https://github.com/thallium-solutions/lam-memcached.git
```

From a local checkout:

```bash
lamc install /path/to/lam-memcached
```

Every installation form uses the canonical scoped import:

```lammergeier
from @lam/memcached import Memcached
```

## Configuration

Create a client with a `host:port` address. The constructor performs an eager
`NOOP` round trip, so an unreachable server or rejected credentials fail during
`connect` rather than on the first data operation.

```lammergeier
from @lam/memcached import Memcached

func main() {
    cache: Memcached = Memcached.connect("cache.internal:11211")
    cache.noop()
    cache.close()
}
```

`Memcached.connect` accepts these values:

| Parameter | Default | Purpose |
|---|---|---|
| `addr` | required | Memcached endpoint in `host:port` form. |
| `username` | `""` | SASL PLAIN username; leave empty for an unauthenticated server. |
| `password` | `""` | SASL PLAIN password; keep empty when `username` is empty. |

The package deliberately does not choose an environment-variable convention.
Applications can pass values from their existing configuration or secret
manager. Do not commit production credentials.

## Usage

### Strings and key lifecycle

```lammergeier
from @lam/memcached import Memcached

func main() {
    cache: Memcached = Memcached.connect("localhost:11211")

    cache.set("greeting", "hello")
    print(cache.get("greeting"))
    print(cache.exists("greeting"))

    # Store only when absent, then update only when present.
    print(cache.add("job:lock", "worker-1", ttlSec=30))
    print(cache.replace("greeting", "hello again", ttlSec=300))

    cache.append("greeting", "!")
    cache.prepend("greeting", "Lam says: ")
    cache.touch("greeting", 600)

    print(cache.delete("greeting"))
    cache.close()
}
```

`get` returns `""` for a missing key. Use `exists` when an absent key must be
distinguished from a stored empty string. `add`, `replace`, `delete`, `touch`,
`append`, and `prepend` return `false` for their normal not-stored/not-found
conditions; other client or server errors fail the operation.

`ttlSec=0` means no expiration. Positive expiration values are passed to
Memcached as seconds. Memcached interprets values above 30 days as absolute
Unix timestamps, following the server protocol.

### Atomic counters

```lammergeier
cache: Memcached = Memcached.connect("localhost:11211")

# A missing counter is created with `initial`; the first call returns 0.
print(cache.incr("requests", by=1, initial=0, ttlSec=3600))
print(cache.incr("requests"))
print(cache.decr("requests", by=1))

cache.close()
```

Counters are unsigned at the Memcached protocol boundary. `decr` saturates at
zero. When a counter is missing, the first `incr` or `decr` returns `initial`;
the delta is applied by subsequent calls.

### Server information and maintenance

```lammergeier
cache: Memcached = Memcached.connect("localhost:11211")

versions: dict[str, str] = cache.version()
serverStats: dict[str, dict[str, str]] = cache.stats()
cache.noop()

# Deletes all keys on the configured server. Use with care.
cache.flush()
cache.close()
```

`flush(when=0)` can schedule a flush by passing a positive delay in seconds.
`close` releases pooled connections and is safe to call more than once.

## Authentication

Pass a username and password to use the `mc/v3` SASL PLAIN path:

```lammergeier
from @lam/memcached import Memcached

func main() {
    cache: Memcached = Memcached.connect(
        "cache.internal:11211",
        username="application-user",
        password="secret-from-your-config",
    )
    cache.set("private:key", "value")
    cache.close()
}
```

Production authentication requires a Memcached server built and started with
SASL support. Use encrypted, private networking as appropriate: SASL PLAIN
credentials are authentication data, not transport encryption.

The local test fixture on port `11212` uses the same `memuser` /
`mempass123` values as the Lammergeier language test services. The stock
`memcached:1.6` image is not started with `-S`; it responds to the authentication
command with `UnknownCommand`, and `mc/v3` continues. Consequently that fixture
verifies the client-side credential path and subsequent commands, but it does
**not** prove server-side credential rejection. Test real authentication against
a SASL-enabled deployment.

## API

| Method | Description |
|---|---|
| `Memcached.connect(addr, username="", password="")` | Creates a client and performs an eager `NOOP`. |
| `get(key)` | Returns a value or `""` when the key is missing. |
| `set(key, value, ttlSec=0)` | Stores a value unconditionally. |
| `add(key, value, ttlSec=0)` | Stores only if absent and reports success. |
| `replace(key, value, ttlSec=0)` | Stores only if present and reports success. |
| `delete(key)` | Deletes a key and reports whether it existed. |
| `exists(key)` | Distinguishes a missing key from an empty value. |
| `touch(key, ttlSec)` | Updates expiration and reports whether the key existed. |
| `incr(key, by=1, initial=0, ttlSec=0)` | Atomically increments an unsigned counter. |
| `decr(key, by=1, initial=0, ttlSec=0)` | Atomically decrements, saturating at zero. |
| `append(key, value)` | Appends to an existing value and reports success. |
| `prepend(key, value)` | Prepends to an existing value and reports success. |
| `flush(when=0)` | Flushes now or after a delay. |
| `noop()` | Performs a liveness round trip. |
| `version()` | Returns server-address-to-version values. |
| `stats()` | Returns stats grouped by server address. |
| `close()` | Releases the client's pooled connections. |

## Service-backed testing

The package contains the two Memcached integration tests migrated from the
Lammergeier standard library. They import `@lam/memcached` from a temporary
consumer project, so the runner checks path installation, package-root
re-exports, manifest Go pins, compilation, execution, and expected output.

Start both fixtures in one terminal:

```bash
sh test-services.sh
# or: lamc lib run service
```

The script uses the same test endpoints and credentials as
`lammergeier-lang/scripts/test-services.sh`:

| Fixture | Endpoint | Credentials |
|---|---|---|
| Standard | `localhost:11211` | none |
| Auth-path | `localhost:11212` | `memuser` / `mempass123` |

It reuses services that already accept connections and stops only containers it
started itself.

Run the package tests in another terminal:

```bash
python3 tests/run_memcached_tests.py --verbose --require-services
# or: lamc lib run test
```

Useful runner options:

```bash
# Compile from a temporary installed-package consumer without services.
python3 tests/run_memcached_tests.py --compile-only

# Select the auth test by substring or glob; -f can be repeated.
python3 tests/run_memcached_tests.py --filter auth --verbose
python3 tests/run_memcached_tests.py --filter '*auth*' --require-services

# Inspect selected cases.
python3 tests/run_memcached_tests.py --list
```

The runner requires `lamc >=1.16.0`. By default it reports a successfully
compiled test as `SKIP` when its service is unavailable and prints a startup
command. `--require-services` makes those skips produce a nonzero exit status,
which is recommended for service-enabled CI.

Format Lam sources with:

```bash
lamc lib run format
# equivalent to: lamc fmt .
```

## License and releases

`@lam/memcached` is distributed under the Apache License, Version 2.0. See
[`LICENSE`](LICENSE). Release notes are in [`CHANGELOG.md`](CHANGELOG.md).
