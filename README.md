# libebml Android builder

Builds libebml 1.4.5 for Nova using `AVP/android-setup-light.sh`, CMake,
Ninja and the NDK. Requires Python 3.9+. Android API 23, C++14, PIC and the static
C++ runtime are used for all four ABIs. Source archives are SHA-256 verified;
versions and hashes are pinned in `build.py`. Upstream source trees are unmodified;
installed headers have trailing whitespace removed for the prebuilt Git checks.

This is the static dependency used by the libmatroska Android builder.

## Build

From the Nova workspace root:

```sh
make native_build_native/libebml-android-builder
```

From this directory:

```sh
bash build.sh              # NDK_APP_ABI, or all four Android ABIs
bash build.sh -a arm64     # arm, arm64, x86, x86_64; full ABI names also work
python3 build.py --host    # host-only validation, needs a JDK for the JNI inspector
```

Configure the Android SDK as for the existing fastText/dav1d builders. Output is
`../prebuilt/libebml/include/` and `../prebuilt/libebml/lib/<ABI>/`, with CMake
package exports per ABI. Android archives/shared objects have debug information
stripped. The inspector's ELF load segments use 16 KiB alignment. Host artifacts
stay in `build-host/prebuilt/` and never enter Android prebuilts or the APK.

`build-info/<ABI>.json` records source, toolchain, builder hashes and output
checksums. Matching prebuilts skip CMake and source downloading; changed inputs
or missing/corrupt outputs trigger incremental rebuilding. Downloads, extracted
sources and build trees are ignored. `make clean_native_build` removes these
caches; `make clean_prebuilt` removes generated prebuilt artifacts and stamps.

## Integration and licenses

MediaLib consumes the Matroska prebuilt shared library and `share/matroska/`
license assets directly. No C++ source, CMake project, dependency download or
native build cache belongs in MediaLib.

Nova-authored scripts, documentation and JNI adapter are Apache-2.0 (`LICENSE`).
Upstream libebml is LGPL-2.1-or-later (`LICENSE.libebml`); see `NOTICE` for
source URL and checksum. The Matroska bundle also carries libebml's license.
The prebuilt repositories preserve headers, archives, CMake exports and build
provenance for rebuilding/relinking the inspector from these sources.

This directory is a separate Git repository on `main`, paired with
`native/prebuilt/libebml` (`prebuilt-libebml`, also `main`). AVP's manifest
references those repositories; publish them before using that manifest in a
fresh remote checkout.
