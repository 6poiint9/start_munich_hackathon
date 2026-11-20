#!/bin/bash
#
# Validate JavaScript syntax with Node.js, then run the project's ESLint and
# Prettier when they are installed. Never downloads tools (npx --no-install).
# Run from the project root so the project's configuration is used.

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
      continue
    fi
    case "${source_file}" in
      *.js | *.mjs | *.cjs)
        if command -v node >/dev/null 2>&1 \
          && ! node --check "${source_file}"; then
          validation_failed='true'
        fi
        ;;
      *.jsx) ;;  # JSX is checked by ESLint only
      *)
        error "Expected a .js, .mjs, .cjs, or .jsx file: ${source_file}"
        validation_failed='true'
        ;;
    esac
  done
  command -v node >/dev/null 2>&1 || warn 'Node.js is unavailable; syntax was not checked'

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
