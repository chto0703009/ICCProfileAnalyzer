"""Combine two architecture-specific Analyzer builds into one macOS app."""
import argparse
import plistlib
import shutil
import subprocess
from pathlib import Path

NAME = 'ICC Profile Analyzer'


def run(*args):
    subprocess.run(args, check=True)


def architectures(executable):
    return set(subprocess.check_output(['lipo', '-archs', executable], text=True).split())


def build(arm, intel, destination, version):
    destination = destination.resolve()
    contents = destination / 'Contents'
    macos = contents / 'MacOS'
    helpers = contents / 'Helpers'
    macos.mkdir(parents=True, exist_ok=False)
    helpers.mkdir()
    plist = Path('Contents/Info.plist')
    info = plistlib.loads((arm / plist).read_bytes())
    info.update(CFBundleName=NAME, CFBundleDisplayName=NAME,
                CFBundleVersion=version, CFBundleShortVersionString=version,
                LSMinimumSystemVersion='14.0')
    (destination / plist).write_bytes(plistlib.dumps(info))
    resources = contents / 'Resources'
    resources.mkdir()
    icon = info['CFBundleIconFile']
    shutil.copyfile(arm / 'Contents/Resources' / icon, resources / icon)
    for label, cpu, source in (('Apple Silicon', 'arm64', arm), ('Intel', 'x86_64', intel)):
        payload = helpers / f'{NAME} - {label}.app'
        run('ditto', source, payload)
        if architectures(payload / 'Contents/MacOS' / NAME) != {cpu}:
            raise ValueError(f'{source} must be a {cpu} build')
        payload_info = plistlib.loads((payload / plist).read_bytes())
        payload_info.update(CFBundleVersion=version, CFBundleShortVersionString=version,
                            LSMinimumSystemVersion='14.0')
        payload_info['CFBundleIdentifier'] = info['CFBundleIdentifier'] + '.' + cpu
        (payload / plist).write_bytes(plistlib.dumps(payload_info))
        run('codesign', '--force', '--sign', '-', payload)
    launcher = macos / NAME
    run('clang', '-arch', 'arm64', '-arch', 'x86_64', '-mmacosx-version-min=14.0',
        Path(__file__).with_name('universal_launcher.c'), '-o', launcher)
    if architectures(launcher) != {'arm64', 'x86_64'}:
        raise ValueError('Expected a Universal launcher')
    run('codesign', '--force', '--sign', '-', destination)
    run('codesign', '--verify', '--deep', '--strict', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arm', type=Path)
    parser.add_argument('intel', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    build(args.arm, args.intel, args.destination, args.version)
