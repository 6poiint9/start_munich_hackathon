#!/bin/bash
#
# Check Dart formatting with `dart format` and run `dart analyze`, which uses
# the project's analysis_options.yaml (for example package:flutter_lints or
# package:lints). Run from the package root (the folder with pubspec.yaml).

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

  local validation_failed='false'
  local source_file
  for source_file in "$@"; do
    if [[ ! -f "${source_file}" ]]; then
      error "File not found: ${source_file}"
      validation_failed='true'
    elif [[ "${source_file}" != *.dart ]]; then
      error "Expected a .dart file: ${source_file}"
      validation_failed='true'
    fi
  done

  if ! command -v dart >/dev/null 2>&1; then
    warn 'the Dart SDK is unavailable; nothing was validated'
    [[ "${validation_failed}" == 'true' ]] && return 1
    return 0
  fi

  dart format --output=none --set-exit-if-changed -- "$@" \
    || validation_failed='true'
  dart analyze --fatal-infos -- "$@" || validation_failed='true'

  if [[ "${validation_failed}" == 'true' ]]; then
    return 1
  fi
}

main "$@"
