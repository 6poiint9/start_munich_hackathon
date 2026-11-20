---
name: checking-npm-packages
description: Checks npm dependencies for malware (compromised or typosquatted packages) and known vulnerabilities before they are installed or shipped. Use whenever a task touches JavaScript or TypeScript dependencies, including adding, upgrading, or installing npm/yarn/pnpm packages, editing package.json or a lockfile, or reviewing a JS project's supply chain.
---

# Checking npm Packages

A compromised package runs its code on `npm install` (install scripts) or at
import time, often to steal npm, GitHub, and cloud tokens. Check versions
**before** they reach `node_modules`, and treat a hit as an incident, not a
warning.

The checker is `scripts/check_npm_packages.py` in this skill's folder (next to
this `SKILL.md`). It needs only Python 3 and network access to `api.osv.dev`
(OpenSSF malicious-packages feed and GitHub advisories). Packages from private
registries, git, or local paths are skipped and never sent.

## Workflow

1. **Before adding or upgrading a dependency**, resolve the exact version and
   check it before installing:

   ```bash
   python3 <skill-dir>/scripts/check_npm_packages.py \
     --package some-lib@1.4.2 --min-age-days 7
   ```

   `--min-age-days 7` rejects versions younger than a week; most hijacked
   releases are detected and unpublished within days. Choose an older version
   when it fails, unless the user needs the newest one (for example a security
   fix) and accepts the risk.
2. **Install without running scripts**, so the lockfile can be checked first:
   `npm install --package-lock-only --ignore-scripts` (yarn:
   `yarn install --mode=update-lockfile`; pnpm:
   `pnpm install --lockfile-only`).
3. **Check every lockfile** of the repository (transitive dependencies
   included):

   ```bash
   python3 <skill-dir>/scripts/check_npm_packages.py path/to/repo
   ```

   Exit `0` clean, `1` malware found, `2` the check could not run. A `2` is
   not a pass: fix the cause (network, missing lockfile) and rerun.
4. **Only after a clean check**, install for real: `npm ci` (or
   `yarn install --immutable`, `pnpm install --frozen-lockfile`). Then run
   `npm audit signatures` where npm is used to verify registry signatures and
   provenance.
5. **Report** the checked package count, every `MALWARE` line, and `VULN`
   lines rated HIGH or CRITICAL with the fixed version to upgrade to.

## When malware is found

1. Stop: no install, build, test, or `npx` run in that project.
2. Pin a clean version (the last release before the compromise, or the
   fixed release from the advisory) in `package.json`, also through
   `overrides` (npm), `resolutions` (yarn), or `pnpm.overrides` when it is a
   transitive dependency. Regenerate the lockfile with step 2 and recheck.
3. If the infected version was ever installed on a machine or in CI, tell the
   user to treat that environment as compromised: delete `node_modules`,
   rotate npm, GitHub, and cloud tokens and SSH keys reachable from it, and
   look for unknown GitHub Actions workflows or repositories created with
   those credentials.

## Dependency hygiene

- Commit the lockfile and install with `npm ci` in CI so versions cannot drift.
- Pin exact versions for new direct dependencies when the project already
  does; otherwise keep its range style.
- Prefer well-known, maintained packages. Compare the name character by
  character with the intended package to catch typosquats (`lodahs`,
  `cross-env.js`), and check its weekly downloads and repository link on
  npmjs.com.
- Add `ignore-scripts=true` to the project's `.npmrc` when no dependency needs
  install scripts; list the packages that do in the report.
- Run `npx` only with an exact version of a known package (`npx pkg@1.2.3`).
