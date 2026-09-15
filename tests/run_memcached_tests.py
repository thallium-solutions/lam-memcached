#!/usr/bin/env python3
# Copyright 2026 Thallium Solutions di Busconi Alessandro.
# SPDX-License-Identifier: Apache-2.0
"""Consumer-style integration test runner for @lam/memcached."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


LIB_ROOT = Path(__file__).resolve().parents[1]
COMPILER = os.environ.get("LAMC", "lamc")
MIN_COMPILER_VERSION = (1, 16, 0)
VERSION_RE = re.compile(
    r"(?<![0-9])v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?(?![0-9])"
)


@dataclass(frozen=True)
class Service:
    label: str
    host: str
    port: int
    credentials: str = ""

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True)
class TestCase:
    source: Path
    service: Service


@dataclass(frozen=True)
class TestResult:
    status: str
    message: str


PLAIN_SERVICE = Service("unauthenticated memcached", "localhost", 11211)
AUTH_SERVICE = Service(
    "memcached auth fixture",
    "localhost",
    11212,
    "username=memuser, password=mempass123",
)


def _compiler_version() -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            [COMPILER, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        print(
            f"Error: {COMPILER!r} is not installed or is not available on PATH. "
            "Install Lammergeier before running these tests.",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        print(f"Error: {COMPILER!r} version check timed out after 10 seconds.", file=sys.stderr)
        return None

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        suffix = f"\n{detail}" if detail else ""
        print(f"Error: unable to check {COMPILER!r} version.{suffix}", file=sys.stderr)
        return None

    output = proc.stdout.strip()
    matches = list(VERSION_RE.finditer(output))
    if len(matches) != 1:
        print(
            f"Error: expected one semantic version from `{COMPILER} version`, got {output!r}.",
            file=sys.stderr,
        )
        return None

    match = matches[0]
    version = tuple(int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4)
    too_old = version < MIN_COMPILER_VERSION
    minimum_prerelease = version == MIN_COMPILER_VERSION and prerelease is not None
    if too_old or minimum_prerelease:
        required = ".".join(str(part) for part in MIN_COMPILER_VERSION)
        print(
            f"Error: {COMPILER} {match.group(0)} is incompatible; lamc >= {required} is required.",
            file=sys.stderr,
        )
        return None
    return version


def _expectations(source: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in source.splitlines()
        if (match := re.match(r"^\s*#\s*expect:\s*(.*)$", line))
    ]


def _service_for(path: Path) -> Service:
    return AUTH_SERVICE if path.stem.endswith("_auth") else PLAIN_SERVICE


def _matches(path: Path, patterns: list[str]) -> bool:
    haystacks = (path.name.lower(), str(path.relative_to(LIB_ROOT)).lower())
    for raw_pattern in patterns:
        pattern = raw_pattern.lower()
        if not any(
            fnmatch.fnmatch(haystack, pattern) if any(ch in pattern for ch in "*?[")
            else pattern in haystack
            for haystack in haystacks
        ):
            return False
    return True


def _discover(patterns: list[str]) -> list[TestCase]:
    sources = sorted((LIB_ROOT / "tests").glob("test_*.lam"))
    if patterns:
        sources = [path for path in sources if _matches(path, patterns)]
    return [TestCase(path, _service_for(path)) for path in sources]


def _process_detail(proc: subprocess.CompletedProcess[str]) -> str:
    parts: list[str] = []
    if proc.stdout.strip():
        parts.append("stdout:\n" + proc.stdout.rstrip())
    if proc.stderr.strip():
        parts.append("stderr:\n" + proc.stderr.rstrip())
    return "\n".join(parts) if parts else "(no process output)"


def _prepare_consumer(root: Path) -> tuple[bool, str]:
    manifest = root / "lamlib.toml"
    manifest.write_text(
        "[library]\n"
        "name = \"lam_memcached_consumer_tests\"\n"
        "version = \"0.0.0\"\n"
        "license = \"Apache-2.0\"\n\n"
        "[compatibility]\n"
        "lamc = \"^1.16\"\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [COMPILER, "install", str(LIB_ROOT)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "CONSUMER SETUP FAIL: local package installation timed out after 120 seconds"

    if proc.returncode != 0:
        return False, "CONSUMER SETUP FAIL: `lamc install` failed\n" + _process_detail(proc)

    package_root = root / "extlibs" / "@lam" / "memcached"
    required = (package_root / "lamlib.toml", package_root / "__init__.lam")
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        return False, "CONSUMER SETUP FAIL: installed package is missing " + ", ".join(missing)
    return True, "ok"


def _probe_service(service: Service, timeout: float = 0.75) -> tuple[bool, str]:
    try:
        with socket.create_connection((service.host, service.port), timeout=timeout):
            return True, ""
    except OSError as exc:
        return False, str(exc)


def _service_unavailable(service: Service, detail: str) -> str:
    credentials = f" ({service.credentials})" if service.credentials else ""
    return (
        f"SERVICE UNAVAILABLE: {service.label} did not accept TCP connections at "
        f"{service.endpoint}{credentials}: {detail}\n"
        f"The Lam test compiled successfully, but its service-dependent runtime was skipped.\n"
        f"Start the package fixtures in another terminal with:\n"
        f"  cd {LIB_ROOT}\n"
        f"  sh test-services.sh\n"
        f"Then rerun this test. Use --require-services in CI to make skips fail the command."
    )


def _run_case(case: TestCase, consumer_root: Path, compile_only: bool) -> TestResult:
    source_text = case.source.read_text(encoding="utf-8")
    expected = _expectations(source_text)
    consumer_tests = consumer_root / "tests"
    consumer_tests.mkdir(exist_ok=True)
    consumer_source = consumer_tests / case.source.name
    shutil.copy2(case.source, consumer_source)
    binary = consumer_root / "build" / case.source.stem
    binary.parent.mkdir(exist_ok=True)

    command = [
        COMPILER,
        str(consumer_source),
        "--extlibs",
        str(consumer_root / "extlibs"),
        "--no-cache",
        "-o",
        str(binary),
    ]
    try:
        compile_proc = subprocess.run(
            command,
            cwd=consumer_root,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        return TestResult("FAIL", "COMPILE FAIL: lamc timed out after 240 seconds")

    if compile_proc.returncode != 0:
        return TestResult("FAIL", "COMPILE FAIL:\n" + _process_detail(compile_proc))
    if not binary.is_file():
        return TestResult("FAIL", f"COMPILE FAIL: lamc reported success but did not create {binary}")
    if compile_only:
        return TestResult("PASS", "compiled as an installed-package consumer")

    available, service_detail = _probe_service(case.service)
    if not available:
        return TestResult("SKIP", _service_unavailable(case.service, service_detail))

    try:
        run_proc = subprocess.run(
            [str(binary)],
            cwd=consumer_root,
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        available_after, after_detail = _probe_service(case.service)
        suffix = ""
        if not available_after:
            suffix = "\n" + _service_unavailable(case.service, after_detail)
        return TestResult("FAIL", "RUN FAIL: test binary timed out after 60 seconds" + suffix)

    if run_proc.returncode != 0:
        message = f"RUN FAIL (exit {run_proc.returncode}):\n{_process_detail(run_proc)}"
        available_after, after_detail = _probe_service(case.service)
        if not available_after:
            message += "\nService became unavailable during the test:\n" + _service_unavailable(
                case.service, after_detail
            )
        return TestResult("FAIL", message)

    actual = run_proc.stdout.rstrip("\n")
    expected_text = "\n".join(expected).strip()
    if expected and actual != expected_text:
        return TestResult(
            "FAIL",
            f"OUTPUT MISMATCH:\n  expected: {expected_text!r}\n  actual:   {actual!r}",
        )
    return TestResult("PASS", "output matches")


def _print_message(message: str, indent: str = "        ") -> None:
    for line in message.splitlines():
        print(indent + line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile and run @lam/memcached tests from a temporary consumer project"
    )
    parser.add_argument(
        "--filter",
        "-f",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "case-insensitive substring or glob matched against test paths; repeat to narrow "
            "the selection"
        ),
    )
    parser.add_argument("--list", action="store_true", help="list selected tests without running them")
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="install the package and compile tests without requiring Memcached services",
    )
    parser.add_argument(
        "--require-services",
        action="store_true",
        help="exit nonzero when a required Memcached service is unavailable",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="show details for every result")
    args = parser.parse_args()

    if _compiler_version() is None:
        return 1

    cases = _discover(args.filter)
    if not cases:
        available = ", ".join(path.name for path in sorted((LIB_ROOT / "tests").glob("test_*.lam")))
        print(
            "Error: no tests matched the requested filters."
            + (f" Available tests: {available}." if available else " No test_*.lam files were found."),
            file=sys.stderr,
        )
        return 2

    if args.list:
        for case in cases:
            print(f"{case.source.relative_to(LIB_ROOT)}\t{case.service.endpoint}")
        return 0

    with tempfile.TemporaryDirectory(prefix="lam_memcached_consumer_") as tmp:
        consumer_root = Path(tmp)
        prepared, setup_message = _prepare_consumer(consumer_root)
        if not prepared:
            print(setup_message, file=sys.stderr)
            return 1

        results: list[tuple[TestCase, TestResult]] = []
        mode = "compile" if args.compile_only else "integration"
        print(f"Running {len(cases)} @lam/memcached {mode} test(s) as a package consumer...\n")
        for case in cases:
            result = _run_case(case, consumer_root, args.compile_only)
            results.append((case, result))
            relative = case.source.relative_to(LIB_ROOT)
            print(f"  {result.status:<4}  {relative}")
            if args.verbose or result.status == "SKIP":
                _print_message(result.message)

    passed = sum(result.status == "PASS" for _, result in results)
    failed = sum(result.status == "FAIL" for _, result in results)
    skipped = sum(result.status == "SKIP" for _, result in results)
    print(
        f"\n@lam/memcached results: {passed} passed, {failed} failed, "
        f"{skipped} skipped, {len(results)} total",
        flush=True,
    )

    if failed and not args.verbose:
        print("\nFailure details:")
        for case, result in results:
            if result.status == "FAIL":
                print(f"  {case.source.relative_to(LIB_ROOT)}")
                _print_message(result.message, indent="    ")

    if skipped and args.require_services:
        print(
            f"Error: {skipped} test(s) were skipped because required services were unavailable.",
            file=sys.stderr,
        )
    return 1 if failed or (skipped and args.require_services) else 0


if __name__ == "__main__":
    raise SystemExit(main())
