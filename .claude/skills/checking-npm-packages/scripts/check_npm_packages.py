#!/usr/bin/env python3
"""Check npm dependencies against OSV for malware and known vulnerabilities.

Reads package-lock.json, npm-shrinkwrap.json, yarn.lock, or pnpm-lock.yaml
(every exact version, including transitive ones), or exact name@version specs
given with --package. Queries https://api.osv.dev, which carries the OpenSSF
malicious-packages feed (MAL-* ids) and the GitHub advisory database.
Packages resolved from private registries, git, or local paths are skipped,
so their names never leave the machine.

Exit status: 0 clean; 1 malware found (or a vulnerability with
--fail-on-vulnerability, or a too-new version with --min-age-days);
2 usage, parse, or network error.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator, Sequence
import concurrent.futures
import dataclasses
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_OSV_VULN_URL = "https://api.osv.dev/v1/vulns/"
_NPM_REGISTRY_URL = "https://registry.npmjs.org/"
_BATCH_SIZE = 1000
_TIMEOUT_SECONDS = 30
_MALWARE_CWE = "CWE-506"  # Embedded Malicious Code
_PUBLIC_REGISTRY_HOSTS = frozenset({
    "registry.npmjs.org",
    "registry.yarnpkg.com",
})
_LOCKFILE_NAMES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
)
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+[0-9A-Za-z.+-]*$")


class CheckError(Exception):
    """A lockfile could not be read or a registry could not be queried."""


@dataclasses.dataclass(frozen=True, order=True)
class Package:
    name: str
    version: str


@dataclasses.dataclass(frozen=True)
class Finding:
    package: Package
    vuln_id: str
    summary: str
    severity: str
    is_malware: bool


def _split_spec(spec: str) -> Package:
    """Parse 'name@version' or '@scope/name@version'."""
    at_index = spec.rfind("@")
    if at_index <= 0:
        raise CheckError(f"expected name@version, got {spec!r}")
    return Package(spec[:at_index], spec[at_index + 1:])


def _is_public_registry(resolved: str | None) -> bool:
    """True when a resolved URL is absent or points at the public registry."""
    if not resolved:
        return True
    return urllib.parse.urlparse(resolved).hostname in _PUBLIC_REGISTRY_HOSTS


def _parse_package_lock(text: str) -> Iterator[Package]:
    data = json.loads(text)
    if "packages" in data:  # lockfileVersion 2 and 3
        for path, entry in data["packages"].items():
            if not path or entry.get("link") or "version" not in entry:
                continue
            if not _is_public_registry(entry.get("resolved")):
                continue
            name = entry.get("name") or path.rsplit("node_modules/", 1)[-1]
            yield Package(name, entry["version"])
        return

    def walk(dependencies: dict[str, dict]) -> Iterator[Package]:
        for name, entry in dependencies.items():
            if _is_public_registry(entry.get("resolved")):
                yield Package(name, entry["version"])
            yield from walk(entry.get("dependencies", {}))

    yield from walk(data.get("dependencies", {}))


def _yarn_entry(name: str | None, fields: dict[str, str]) -> Package | None:
    """The package of one finished yarn.lock entry, if it is a public one."""
    version = fields.get("version", "")
    resolution = fields.get("resolution")
    if (name is None or not _VERSION_PATTERN.match(version)
            or not _is_public_registry(fields.get("resolved"))
            or (resolution is not None and "@npm:" not in resolution)):
        return None  # workspace:, patch:, link:, git, private registries
    return Package(name, version)


def _parse_yarn_lock(text: str) -> Iterator[Package]:
    """Yarn classic (v1) and Berry lockfiles."""
    name: str | None = None
    fields: dict[str, str] = {}
    for line in [*text.splitlines(), "end:"]:
        if line and not line.startswith((" ", "#")) and line.endswith(":"):
            package = _yarn_entry(name, fields)
            if package:
                yield package
            first_spec = line[:-1].split(",")[0].strip().strip('"')
            name = None if first_spec in {"__metadata", "end"} else (
                _split_spec(first_spec).name)
            fields = {}
        elif line.startswith("  ") and not line.startswith("   "):
            key, _, value = line.strip().partition(" ")
            fields[key.rstrip(":")] = value.strip('"')


def _parse_pnpm_lock(text: str) -> Iterator[Package]:
    """pnpm lockfiles v5 to v9: the keys of the top-level packages map."""
    in_packages = False
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_packages = line.rstrip() == "packages:"
            continue
        if not in_packages or line.startswith("   ") or not line.endswith(":"):
            continue
        key = line.strip()[:-1].strip("'\"").lstrip("/").split("(", 1)[0]
        if "@" in key[1:]:
            package = _split_spec(key)
        else:  # v5 keys look like name/1.2.3
            name, _, version = key.rpartition("/")
            package = Package(name, version)
        if package.name and _VERSION_PATTERN.match(package.version):
            yield package


_PARSERS = {
    "package-lock.json": _parse_package_lock,
    "npm-shrinkwrap.json": _parse_package_lock,
    "yarn.lock": _parse_yarn_lock,
    "pnpm-lock.yaml": _parse_pnpm_lock,
}


def read_lockfile(path: pathlib.Path) -> set[Package]:
    """Every exact npm package version a lockfile pins."""
    parser = _PARSERS.get(path.name)
    if parser is None:
        raise CheckError(f"{path}: unsupported lockfile, expected one of "
                         f"{', '.join(_LOCKFILE_NAMES)}")
    try:
        return set(parser(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError) as error:
        raise CheckError(f"{path}: {error}") from error


def find_lockfiles(root: pathlib.Path) -> list[pathlib.Path]:
    """Lockfiles below root, skipping node_modules and hidden folders."""
    found = []
    for name in _LOCKFILE_NAMES:
        for path in root.rglob(name):
            folders = path.relative_to(root).parts[:-1]
            if any(f == "node_modules" or f.startswith(".") for f in folders):
                continue
            found.append(path)
    return sorted(found)


def _request_json(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as reply:
            return json.load(reply)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise CheckError(f"request to {url} failed: {error}") from error


def _chunks(items: Sequence[Package],
            size: int) -> Iterable[Sequence[Package]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _fetch_vuln(vuln_id: str) -> dict:
    return _request_json(_OSV_VULN_URL + urllib.parse.quote(vuln_id))


def query_osv(packages: Sequence[Package]) -> list[Finding]:
    """All OSV advisories affecting the packages, with malware flagged."""
    ids_by_package: dict[Package, list[str]] = {}
    for chunk in _chunks(packages, _BATCH_SIZE):
        queries = [{"package": {"ecosystem": "npm", "name": p.name},
                    "version": p.version} for p in chunk]
        results = _request_json(_OSV_BATCH_URL, {"queries": queries})
        for package, result in zip(chunk, results.get("results", [])):
            ids = [vuln["id"] for vuln in result.get("vulns", [])]
            if ids:
                ids_by_package[package] = ids

    all_ids = sorted({i for ids in ids_by_package.values() for i in ids})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        details = dict(zip(all_ids, pool.map(_fetch_vuln, all_ids)))

    findings = []
    for package, ids in sorted(ids_by_package.items()):
        for vuln_id in ids:
            detail = details[vuln_id]
            specific = detail.get("database_specific") or {}
            related_ids = [vuln_id, *detail.get("aliases", [])]
            is_malware = (any(i.startswith("MAL-") for i in related_ids)
                          or _MALWARE_CWE in specific.get("cwe_ids", []))
            findings.append(Finding(
                package=package,
                vuln_id=vuln_id,
                summary=detail.get("summary") or "(no summary)",
                severity=str(specific.get("severity", "UNKNOWN")),
                is_malware=is_malware,
            ))
    return findings


def find_too_new(packages: Iterable[Package],
                 min_age_days: int) -> list[tuple[Package, int]]:
    """Packages published fewer than min_age_days ago, with their age."""
    now = datetime.datetime.now(datetime.timezone.utc)
    too_new = []
    for package in packages:
        metadata = _request_json(
            _NPM_REGISTRY_URL + urllib.parse.quote(package.name, safe="@"))
        published = metadata.get("time", {}).get(package.version)
        if published is None:
            raise CheckError(f"{package.name}@{package.version}: version not "
                             "found on the npm registry")
        age = now - datetime.datetime.fromisoformat(
            published.replace("Z", "+00:00"))
        if age.days < min_age_days:
            too_new.append((package, age.days))
    return too_new


def _collect_packages(paths: Sequence[pathlib.Path],
                      specs: Sequence[str]) -> set[Package]:
    packages = {_split_spec(spec) for spec in specs}
    roots = list(paths) or ([] if specs else [pathlib.Path(".")])
    lockfiles: list[pathlib.Path] = []
    for root in roots:
        if root.is_dir():
            lockfiles.extend(find_lockfiles(root))
        elif root.is_file():
            lockfiles.append(root)
        else:
            raise CheckError(f"{root}: not found")
    if roots and not lockfiles:
        raise CheckError(
            "no lockfile found; create one without running install scripts: "
            "npm install --package-lock-only --ignore-scripts")
    for lockfile in lockfiles:
        pinned = read_lockfile(lockfile)
        print(f"{lockfile}: {len(pinned)} packages")
        packages |= pinned
    return packages


def main(argv: Sequence[str] | None = None) -> int:
    """Check the requested lockfiles or package specs."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "paths", nargs="*", type=pathlib.Path,
        help="lockfiles or folders to search (default: current folder)")
    parser.add_argument(
        "--package", action="append", default=[], metavar="NAME@VERSION",
        help="check an exact version before installing it (repeatable)")
    parser.add_argument(
        "--fail-on-vulnerability", action="store_true",
        help="also exit 1 for known vulnerabilities that are not malware")
    parser.add_argument(
        "--min-age-days", type=int, default=0, metavar="DAYS",
        help="with --package: fail versions published fewer than DAYS ago")
    args = parser.parse_args(argv)

    try:
        packages = sorted(_collect_packages(args.paths, args.package))
        findings = query_osv(packages)
        too_new = (find_too_new(map(_split_spec, args.package),
                                args.min_age_days)
                   if args.min_age_days else [])
    except CheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for finding in sorted(findings, key=lambda f: not f.is_malware):
        label = "MALWARE" if finding.is_malware else "VULN   "
        print(f"{label}  {finding.package.name}@{finding.package.version}  "
              f"{finding.vuln_id}  [{finding.severity}]  {finding.summary}")
    for package, age_days in too_new:
        print(f"TOO NEW  {package.name}@{package.version}  published "
              f"{age_days} days ago (minimum {args.min_age_days})")

    malware_count = sum(f.is_malware for f in findings)
    vulnerability_count = len(findings) - malware_count
    print(f"checked {len(packages)} packages: {malware_count} malware, "
          f"{vulnerability_count} vulnerabilities")
    failed = (malware_count > 0 or bool(too_new)
              or (args.fail_on_vulnerability and vulnerability_count > 0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
