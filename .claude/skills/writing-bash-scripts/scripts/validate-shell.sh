#!/bin/bash
#
# Validate Bash syntax and run ShellCheck when it is available.

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
  printf 'Usage: %s SCRIPT [SCRIPT ...]\n' "${SCRIPT_NAME}" >&2
}

main() {
  if (( $# == 0 )); then
    usage
    return 2
  fi

  local shellcheck_available='false'
  if command -v shellcheck >/dev/null 2>&1; then
    shellcheck_available='true'
  else
    warn 'ShellCheck is unavailable; only Bash syntax will be validated'
  fi

  local validation_failed='false'
  local script_file
  for script_file in "$@"; do
    if [[ ! -f "${script_file}" ]]; then
      error "File not found: ${script_file}"
      validation_failed='true'
      continue
    fi

    if ! bash -n "${script_file}"; then
      validation_failed='true'
    fi

    if [[ "${shellcheck_available}" == 'true' ]] \
      && ! shellcheck --shell=bash "${script_file}"; then
      validation_failed='true'
    fi
  done

  if [[ "${validation_failed}" == 'true' ]]; then
    return 1
  fi
}

main "$@"
