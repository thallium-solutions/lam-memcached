# @lam/memcached

`@lam/memcached` is a Result-first, binary-protocol Memcached client for the
[Lammergeier programming language](https://github.com/thallium-solutions/lammergeier-lang).
It supports strings, expiration, atomic counters, server metadata, and optional
SASL PLAIN credentials through `github.com/memcachier/mc/v3` v3.0.3.

Version 2 is a breaking release: operations no longer panic on expected
service/transport failures, and missing `get` values are no longer hidden as
empty strings. Fallible public methods use unsuffixed `Result[T]` APIs.

## Requirements and installation

- `lamc` 1.18.0 or newer including 2.x (`>=1.18, <4`).
- A reachable Memcached server for runtime operations.
- Go module downloads on the first build unless dependencies are cached.

```bash
lamc install @lam/memcached@2.0.0
# or
lamc install https://github.com/thallium-solutions/lam-memcached.git
```

```lammergeier
from @lam/memcached import Memcached
from lamerrors import Result
```

## Quick start

```lammergeier
from @lam/memcached import Memcached
from lamerrors import Result

func writeAndRead() -> Result[str] {
    cache: Memcached = Memcached.connect("localhost:11211")?
    _ = cache.set("greeting", "hello", ttlSec=60)?
    value: str = cache.get("greeting")?
    _ = cache.close()?
    return Result.Ok(value)
}
```

`connect` eagerly performs `NOOP`. An unreachable endpoint or rejected
credentials therefore returns `Result.Err` before a client is exposed. Pass
`username` and `password` for the `mc/v3` SASL PLAIN path:

```lammergeier
cache: Memcached = Memcached.connect(
    "cache.internal:11211",
    username="application-user",
    password="secret-from-your-config",
)?
```

SASL PLAIN authenticates but does not encrypt traffic; use suitable private or
encrypted networking.

## Result and absence semantics

All service-facing operations return `Result[T]`:

- Transport, authentication, protocol, closed-client, and server failures use
  `Error.kind == "MemcachedError"`.
- `get` on an absent key returns `MemcachedNotFound`. A stored empty string is
  still `Result.Ok("")`, so absence is no longer ambiguous.
- Conditional mutation outcomes are values, not failures: `add` returns
  `Ok(false)` when the key exists, while `replace`, `delete`, `touch`, `append`,
  and `prepend` return `Ok(false)` when the key is absent.
- Invalid negative TTL, counter, or flush-delay values return
  `MemcachedArgumentError` before reaching the client.
- `close` returns `Result[any]` and is idempotent.

Handle expected absence without unwrapping:

```lammergeier
value: Result[str] = cache.get("optional")
if value.ok() {
    text: str = value.unwrap()
    print(text)
} else {
    print("missing or unavailable: " + str(value.error))
}
```

## API map

| API | Return | Semantics |
|---|---|---|
| `Memcached.connect(addr, username="", password="")` | `Result[Memcached]` | Constructs the pool and eagerly performs `NOOP`. |
| `get(key)` | `Result[str]` | `MemcachedNotFound` when absent. |
| `set(key, value, ttlSec=0)` | `Result[bool]` | `Ok(true)` after storage. |
| `add(key, value, ttlSec=0)` | `Result[bool]` | `Ok(false)` when already present. |
| `replace(key, value, ttlSec=0)` | `Result[bool]` | `Ok(false)` when absent. |
| `delete(key)` | `Result[bool]` | `Ok(false)` when absent. |
| `exists(key)` | `Result[bool]` | Distinguishes absence from empty values. |
| `touch(key, ttlSec)` | `Result[bool]` | `Ok(false)` when absent. |
| `incr(key, by=1, initial=0, ttlSec=0)` | `Result[int]` | Unsigned atomic increment. |
| `decr(key, by=1, initial=0, ttlSec=0)` | `Result[int]` | Unsigned decrement with zero saturation. |
| `append(key, value)` / `prepend(key, value)` | `Result[bool]` | `Ok(false)` when absent. |
| `flush(when=0)` | `Result[bool]` | Flushes now or after a delay. |
| `noop()` | `Result[bool]` | Explicit liveness round trip. |
| `version()` | `Result[dict[str, str]]` | Versions by server address. |
| `stats()` | `Result[dict[str, dict[str, str]]]` | Statistics by server address. |
| `close()` | `Result[any]` | Idempotently releases the pool. |

`ttlSec=0` means no expiration. Memcached interprets values above 30 days as
absolute Unix timestamps. A missing counter is created with `initial`; the
first increment/decrement returns that initial value and later calls apply the
delta.

## Testing

The consumer runner installs the local package into a temporary project and
compiles against its public scoped import.

```bash
# Offline/compiler gate; never contacts Memcached.
python3 tests/run_memcached_tests.py --compile-only --verbose

# Run only when fixtures already exist.
python3 tests/run_memcached_tests.py --verbose --require-services
```

Fixture endpoints are `localhost:11211` (no credentials) and
`localhost:11212` (`memuser` / `mempass123`). `test-services.sh` can create
those fixtures manually, but test automation should not start external or
destructive services implicitly. The integration tests call `flush`, so never
point them at shared or production Memcached instances.

Format Lam sources with `lamc fmt .`.

## License

Apache License 2.0. See [LICENSE](LICENSE). Release notes are in
[CHANGELOG.md](CHANGELOG.md).
