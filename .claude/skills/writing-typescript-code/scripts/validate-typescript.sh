#!/bin/bash
#
# Type-check TypeScript with the project's compiler, then run the project's
# ESLint and Prettier when they are installed. Never downloads tools
# (npx --no-install). Run from the project root (the folder with tsconfig.json).

set -o errexit
set -o nounset
set -o pipefail

readonly SCRIPT_NAME="${0##*/}"

error() {
  printf '%s: %s\n' "${SCRIPT_NAME}" "$*" >&2
}

warn() {
  printf '%s: warning: %s\n' "${SCRIPT_NAME}" "$*" >&2
}

usage() {
  printf 'Usage: %s FILE [FILE ...]\n' "${SCRIPT_NAME}" >&2
}

has_project_tool() {
  npx --no-install "$1" --version >/dev/null 2>&1
}

main() {
  if (( $# == 0 )); then
    usage
    return 2
  fi

  local validation_failed='false'
  local source_file
  for source_file in "$@"; do
    if [[ ! -f "${source_file}" ]]; then
      error "File not found: ${source_file}"
      validation_failed='true'
    elif [[ ! "${source_file}" =~ \.(ts|tsx|mts|cts)$ ]]; then
      error "Expected a .ts, .tsx, .mts, or .cts file: ${source_file}"
      validation_failed='true'
    fi
  done

  if ! has_project_tool tsc; then
    warn 'TypeScript is not installed in this project; types were not checked'
  elif [[ -f tsconfig.json ]]; then
    npx --no-install tsc --noEmit --project tsconfig.json \
      || validation_failed='true'
  else
    npx --no-install tsc --noEmit --strict "$@" || validation_failed='true'
  fi

  if has_project_tool eslint; then
    npx --no-install eslint "$@" || validation_failed='true'
  else
    warn 'ESLint is not installed in this project; lint was skipped'
  fi
  if has_project_tool prettier; then
    npx --no-install prettier --check "$@" || validation_failed='true'
  fi

  if [[ "${validation_failed}" == 'true' ]]; then
    return 1
  fi
}

main "$@"
