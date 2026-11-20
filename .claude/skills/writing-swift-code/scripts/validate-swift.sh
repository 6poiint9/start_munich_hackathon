#!/bin/bash
#
# Validate Swift syntax with swiftc, then lint with swift-format (bundled with
# Swift 6 toolchains as `swift format`). swift-format's defaults match the
# Google Swift Style Guide's 2-space indent and 100-column limit; a project
# .swift-format file takes precedence.

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

main() {
  if (( $# == 0 )); then
    usage
    return 2
  fi

  local -a formatter=()
  if swift format --version >/dev/null 2>&1; then
    formatter=(swift format)
  elif command -v swift-format >/dev/null 2>&1; then
    formatter=(swift-format)
  else
    warn 'swift-format is unavailable; only syntax will be validated'
  fi
  local swiftc_available='true'
  if ! command -v swiftc >/dev/null 2>&1; then
    swiftc_available='false'
    warn 'swiftc is unavailable; syntax will not be validated'
  fi

  local validation_failed='false'
  local source_file
  for source_file in "$@"; do
    if [[ ! -f "${source_file}" ]]; then
      error "File not found: ${source_file}"
      validation_failed='true'
      continue
    fi
    if [[ "${source_file}" != *.swift ]]; then
      error "Expected a .swift file: ${source_file}"
      validation_failed='true'
      continue
    fi
    if [[ "${swiftc_available}" == 'true' ]] \
      && ! swiftc -parse "${source_file}"; then
      validation_failed='true'
    fi
  done

  if (( ${#formatter[@]} > 0 )) \
    && ! "${formatter[@]}" lint --strict -- "$@"; then
    validation_failed='true'
  fi

  if [[ "${validation_failed}" == 'true' ]]; then
    return 1
  fi
}

main "$@"
