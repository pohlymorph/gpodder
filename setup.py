#!/usr/bin/env python3

#
# gPodder - A media aggregator and podcast client
# Copyright (c) 2005-2018 The gPodder Team
#
# gPodder is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# gPodder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import glob
import os
import re
import sys

from distutils.core import setup

installing = ('install' in sys.argv and '--help' not in sys.argv)

# Read the metadata from gPodder's __init__ module (doesn't need importing)
main_module = open('src/gpodder/__init__.py', 'r', encoding='utf-8').read()
metadata = dict(re.findall("__([a-z_]+)__\s*=\s*'([^']+)'", main_module))

author, email = re.match(r'^(.*) <(.*)>$', metadata['author']).groups()


class MissingFile(BaseException): pass


def info(message, item=None):
    print('=>', message, item if item is not None else '')


def find_data_files(uis, scripts):
    # Support for installing only a subset of translations
    linguas = os.environ.get('LINGUAS', None)
    if linguas is not None:
        linguas = linguas.split()
        info('Selected languages (from $LINGUAS):', linguas)

    for dirpath, dirnames, filenames in os.walk('share'):
        if not filenames:
            continue

        # Skip data folders if we don't want the corresponding UI
        share_gpodder_ui = os.path.join('share', 'gpodder', 'ui')
        if uis is not None and dirpath.startswith(share_gpodder_ui):
            dirparts = dirpath.split(os.sep)
            if not any(part in uis for part in dirparts):
                info('Skipping folder:', dirpath)
                continue

        # Skip translations if $LINGUAS is set
        share_locale = os.path.join('share', 'locale')
        if linguas is not None and dirpath.startswith(share_locale):
            _, _, language, _ = dirpath.split(os.sep, 3)
            if language not in linguas:
                info('Skipping translation:', language)
                continue

        # Skip desktop stuff if we don't have any UIs requiring it
        skip_folder = False
        uis_requiring_freedesktop = ('gtk',)
        freedesktop_folders = ('icons', 'dbus-1', 'applications')
        for folder in freedesktop_folders:
            share_folder = os.path.join('share', folder)
            if dirpath.startswith(share_folder) and uis is not None:
                if not any(ui in uis_requiring_freedesktop for ui in uis):
                    info('Skipping freedesktop.org folder:', dirpath)
                    skip_folder = True
                    break

        if skip_folder:
            continue

        # Skip manpages if their scripts are not going to be installed
        share_man = os.path.join('share', 'man')
        if dirpath.startswith(share_man):
            def have_script(filename):
                if not filename.endswith('.1'):
                    return True

                basename, _ = os.path.splitext(filename)
                result = any(os.path.basename(s) == basename for s in scripts)
                if not result:
                    info('Skipping manpage without script:', filename)
                return result
            filenames = list(filter(have_script, filenames))

        def convert_filename(filename):
            filename = os.path.join(dirpath, filename)

            # Skip header files generated by "make messages"
            if filename.endswith('.h'):
                return None

            # Skip .in files, but check if their target exist
            if filename.endswith('.in'):
                filename = filename[:-3]
                if installing and not os.path.exists(filename):
                    raise MissingFile(filename)
                return None

            return filename

        filenames = [_f for _f in map(convert_filename, filenames) if _f]
        if filenames:
            # Some distros/ports install manpages into $PREFIX/man instead
            # of $PREFIX/share/man (e.g. FreeBSD). To allow this, we strip
            # the "share/" part if the variable GPODDER_MANPATH_NO_SHARE is
            # set to any value in the environment.
            if dirpath.startswith(share_man):
                if 'GPODDER_MANPATH_NO_SHARE' in os.environ:
                    dirpath = dirpath.replace(share_man, 'man')

            yield (dirpath, filenames)


def find_packages(uis):
    src_gpodder = os.path.join('src', 'gpodder')
    for dirpath, dirnames, filenames in os.walk(src_gpodder):
        if '__init__.py' not in filenames:
            continue

        skip = False
        dirparts = dirpath.split(os.sep)
        dirparts.pop(0)
        package = '.'.join(dirparts)

        # Extract all parts of the package name ending in "ui"
        ui_parts = [p for p in dirparts if p.endswith('ui')]
        if uis is not None and ui_parts:
            # Strip the trailing "ui", e.g. "gtkui" -> "gtk"
            folder_uis = [p[:-2] for p in ui_parts]
            for folder_ui in folder_uis:
                if folder_ui not in uis:
                    info('Skipping package:', package)
                    skip = True
                    break

        if not skip:
            yield package


def find_scripts(uis):
    # Functions for scripts to check if they should be installed
    file_checks = {
        'gpo': lambda uis: 'cli' in uis,
        'gpodder': lambda uis: any(ui in uis for ui in ('gtk',)),
    }

    for dirpath, dirnames, filenames in os.walk('bin'):
        for filename in filenames:
            # If we have a set of uis, check if we can skip this file
            if uis is not None and filename in file_checks:
                if not file_checks[filename](uis):
                    info('Skipping script:', filename)
                    continue

            yield os.path.join(dirpath, filename)


# Recognized UIs: cli, gtk (default: install all UIs)
uis = os.environ.get('GPODDER_INSTALL_UIS', None)
if uis is not None:
    uis = uis.split()

    info('Selected UIs (from $GPODDER_INSTALL_UIS):', uis)


try:
    packages = list(sorted(find_packages(uis)))
    scripts = list(sorted(find_scripts(uis)))
    data_files = list(sorted(find_data_files(uis, scripts)))
except MissingFile as mf:
    print("""
    Missing file: %s

    If you want to install, use "make install" instead of using
    setup.py directly. See the README file for more information.
    """ % mf.message, file=sys.stderr)
    sys.exit(1)


setup(
    name         = 'gpodder',
    version      = metadata['version'],
    description  = metadata['tagline'],
    license      = metadata['license'],
    url          = metadata['url'],

    author       = author,
    author_email = email,

    package_dir  = {'': 'src'},
    packages     = packages,
    scripts      = scripts,
    data_files   = data_files,
)
