#!/bin/bash
# Copyright 2026 Courville Software
# SPDX-License-Identifier: Apache-2.0

set -e -o pipefail

usage() {
  echo "Usage: bash build.sh [-a arm|arm64|x86|x86_64]"
  echo "Without -a, builds NDK_APP_ABI or all four Nova ABIs."
}

ARCH=
while getopts ":a:h" opt; do
  case "$opt" in
    a) ARCH=$OPTARG ;;
    h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
if [ "$#" -ne 0 ]; then
  usage >&2
  exit 2
fi

ABIS=()
if [ -n "$ARCH" ]; then
  ABIS=("$ARCH")
else
  read -r -a ABIS <<< "${NDK_APP_ABI:-armeabi-v7a arm64-v8a x86 x86_64}"
fi
for i in "${!ABIS[@]}"; do
  case "${ABIS[$i]}" in
    arm|armeabi-v7a) ABIS[$i]=armeabi-v7a ;;
    arm64|arm64-v8a) ABIS[$i]=arm64-v8a ;;
    x86|x86_64) ;;
    *) echo "Unsupported architecture: ${ABIS[$i]}" >&2; exit 2 ;;
  esac
done
if [ "${#ABIS[@]}" -eq 0 ]; then
  echo "No Android ABIs selected." >&2
  exit 2
fi

LOCAL_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$LOCAL_PATH"
# Shared setup expects optional SDK environment variables to be unset safely.
source ../../AVP/android-setup-light.sh
set -u

if [ ! -f "${NDK_PATH:-}/build/cmake/android.toolchain.cmake" ]; then
  echo "Android NDK not found; configure ANDROID_SDK_ROOT as for the other Nova builders." >&2
  exit 1
fi
CMAKE=${CMAKE_PATH:+${CMAKE_PATH}/bin/}cmake

exec python3 "$LOCAL_PATH/build.py" --ndk "$NDK_PATH" --cmake "$CMAKE" --jobs "$CORES" --abis "${ABIS[@]}"
