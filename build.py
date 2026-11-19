#!/usr/bin/env python3
# Copyright 2026 Courville Software
# SPDX-License-Identifier: Apache-2.0
"""Build pinned Matroska libraries into Nova's ABI-specific prebuilt layout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
NAME = 'libebml'
VERSION = '1.4.5'
SHA256 = '4971640b0592da29c2d426f303e137a9b0b3d07e1b81d069c1e56a2f49ab221b'
ABIS = ['armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64']
URL = f'https://dl.matroska.org/downloads/{NAME}/{NAME}-{VERSION}.tar.xz'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def source():
    downloads = HERE / 'downloads'
    downloads.mkdir(exist_ok=True)
    archive = downloads / f'{NAME}-{VERSION}.tar.xz'
    if not archive.exists():
        temporary = archive.with_suffix('.tmp')
        urllib.request.urlretrieve(URL, temporary)
        if digest(temporary) != SHA256:
            raise RuntimeError('Downloaded source checksum mismatch')
        temporary.replace(archive)
    if digest(archive) != SHA256:
        raise RuntimeError('Cached source checksum mismatch')
    sources = HERE / 'sources'
    sources.mkdir(exist_ok=True)
    extracted = sources / f'{NAME}-{VERSION}'
    if not extracted.exists():
        with tarfile.open(archive) as tar:
            for entry in tar.getmembers():
                if not (sources / entry.name).resolve().is_relative_to(sources.resolve()) or not (entry.isfile() or entry.isdir()):
                    raise RuntimeError('Unsafe source archive entry')
            tar.extractall(sources)
    return extracted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', default=os.environ.get('ANDROID_NDK_HOME'))
    parser.add_argument('--abis', nargs='+', choices=ABIS, default=ABIS)
    parser.add_argument('--host', action='store_true')
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--jobs', default='4')
    args = parser.parse_args()
    ndk = Path(args.ndk).resolve() if args.ndk else None
    if not args.host and (not ndk or not (ndk / 'build/cmake/android.toolchain.cmake').is_file()):
        parser.error('A valid --ndk is required for Android builds')
    abis = ['host'] if args.host else args.abis
    output = HERE / 'build-host/prebuilt' if args.host else HERE.parent / 'prebuilt' / NAME
    output.mkdir(parents=True, exist_ok=True)
    ebml = HERE.parent / 'libebml-android-builder/build-host/prebuilt' if args.host else HERE.parent / 'prebuilt/libebml'
    if NAME == 'libmatroska':
        command = [sys.executable, HERE.parent / 'libebml-android-builder/build.py', '--cmake', args.cmake, '--jobs', args.jobs]
        command += ['--host'] if args.host else ['--ndk', ndk, '--abis', *abis]
        run(command)
    for filename in ['LICENSE', f'LICENSE.{NAME}', 'NOTICE']:
        shutil.copy2(HERE / filename, output / filename)
    if NAME == 'libmatroska':
        assets = output / 'share/matroska'
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / 'LICENSE.libmatroska', assets / 'libmatroska-LICENSE.LGPL')
        shutil.copy2(ebml / 'LICENSE.libebml', assets / 'libebml-LICENSE.LGPL')
        shutil.copy2(ebml / 'LICENSE.libebml', output / 'LICENSE.libebml')
    toolchain = subprocess.check_output([args.cmake, '--version'], text=True).splitlines()[0]
    for abi in abis:
        libdir = f'lib/{abi}'
        stamp = output / 'build-info' / f'{abi}.json'
        inputs = dict(source=URL, sha256=SHA256, abi=abi, api=None if args.host else 23,
                      runtime='host' if args.host else 'c++_static', cmake=toolchain,
                      ndk=None if args.host else str(ndk),
                      ndk_version=None if args.host else (ndk / 'source.properties').read_text(),
                      builder=digest(Path(__file__)))
        if NAME == 'libmatroska':
            inputs.update(adapter=digest(HERE / 'editor.cpp'), cmake_file=digest(HERE / 'CMakeLists.txt'),
                          ebml=digest(ebml / 'build-info' / f'{abi}.json'))
        if stamp.exists():
            previous = json.loads(stamp.read_text())
            if previous['inputs'] == inputs and all((output / p).is_file() and digest(output / p) == h
                                                    for p, h in previous['outputs'].items()):
                print(f'{NAME} {abi}: verified prebuilt is current', flush=True)
                continue
        tree = source()
        common = ['-DCMAKE_POLICY_VERSION_MINIMUM=3.5', '-DCMAKE_BUILD_TYPE=Release',
                  '-DCMAKE_POSITION_INDEPENDENT_CODE=ON', '-DBUILD_SHARED_LIBS=OFF', '-DBUILD_TESTING=OFF',
                  '-DDISABLE_PKGCONFIG=ON', '-DCMAKE_INSTALL_PREFIX=' + str(output),
                  '-DCMAKE_INSTALL_LIBDIR=' + libdir]
        if not args.host:
            common += ['-DCMAKE_TOOLCHAIN_FILE=' + str(ndk / 'build/cmake/android.toolchain.cmake'),
                       '-DANDROID_ABI=' + abi, '-DANDROID_PLATFORM=android-23', '-DANDROID_STL=c++_static']
        if NAME == 'libmatroska':
            common += ['-DEBML_DIR=' + str(ebml / libdir / 'cmake/EBML')]
        target = HERE / ('build-' + abi) / NAME
        run([args.cmake, '-S', tree, '-B', target, '-G', 'Ninja', *common])
        run([args.cmake, '--build', target, '--parallel', args.jobs])
        run([args.cmake, '--install', target])
        if NAME == 'libmatroska':
            target = HERE / ('build-' + abi) / 'editor'
            run([args.cmake, '-S', HERE, '-B', target, '-G', 'Ninja', *common,
                 '-DMatroska_DIR=' + str(output / libdir / 'cmake/Matroska')])
            run([args.cmake, '--build', target, '--parallel', args.jobs])
            run([args.cmake, '--install', target])
        if not args.host:
            strip = ndk / f'toolchains/llvm/prebuilt/{platform.system().lower()}-x86_64/bin/llvm-strip'
            for library in (output / libdir).glob('*'):
                if library.suffix in ('.a', '.so'):
                    run([strip, '--strip-debug', library])
        # Keep installed/generated headers clean for the prebuilt repository's
        # whitespace gate; upstream source trees remain untouched.
        for header in (output / 'include').rglob('*.h'):
            text = header.read_text()
            clean = '\n'.join(line.rstrip() for line in text.splitlines()) + '\n'
            if clean != text:
                header.write_text(clean)
        files = [p for base in [output / 'include', output / libdir] for p in base.rglob('*') if p.is_file()]
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(json.dumps(dict(inputs=inputs, outputs={str(p.relative_to(output)): digest(p) for p in sorted(files)}), indent=2) + '\n')


if __name__ == '__main__':
    main()
