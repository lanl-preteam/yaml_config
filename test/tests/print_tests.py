"""Check style and other formatting issues."""

import distutils.spawn
import glob
import re
import subprocess
import unittest

from testlib import YCTestCase

_PYLINT3_PATH = distutils.spawn.find_executable('pylint3')
if _PYLINT3_PATH is None:
    _PYLINT3_PATH = distutils.spawn.find_executable('pylint')


class StyleTests(YCTestCase):
    LIB_DIR = YCTestCase.ROOT_DIR / 'lib' / 'yaml_config'

    @unittest.skipIf(not _PYLINT3_PATH, "pylint3 not found.")
    def test_style(self):
        enabled = [
            'logging',
            'format',
            'imports',
            'exceptions',
            'classes',
            'basic',
        ]

        disabled = [
            'missing-docstring',
            'consider-using-enumerate',
            'bad-builtin',
        ]

        cmd = [
            _PYLINT3_PATH,
            '--disable=all',
            '--enable={}'.format(','.join(enabled)),
            '--disable={}'.format(','.join(disabled)),
            '--output-format=text',
            '--msg-template="{line},{column}:  {msg}  ({symbol} - {msg_id})"',
            '--reports=n',
            '--max-line-length=80',
            self.LIB_DIR.as_posix()
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            self.fail('\n' + stdout.decode('utf8'))

    def test_prints(self):
        """Make sure there aren't any debug print statements sitting around."""

        skip_re_str = 'ext_print: #'

        print_re = re.compile('print\(')
        skip_re = re.compile('ext_print: (\d*)')

        lib_dir = (self.ROOT_DIR/'lib').as_posix()

        files = glob.glob(lib_dir + '/*/*.py')
        msg = []

        for fn in files:
            with open(fn) as file:
                data = file.read()

            found = []
            line_num = 1
            skip = 0
            for line in data.split('\n'):
                skip_match = skip_re.search(line)
                if skip:
                    skip -= 1
                elif print_re.search(line) is not None:
                    found.append((line_num, line))
                elif skip_match:
                    skip = int(skip_match.groups()[0])

                line_num += 1

            if found:
                msg.append("Found extra prints in file: {}".format(fn))
                for line_num, line in found:
                    msg.append("{:5d} {}".format(line_num, line))

        if msg:
            msg.append(
                "You can have this test ignore print() calls by adding '{}' in"
                "a comment on or immediately before the offending line."
                .format(skip_re_str))

        if msg:
            self.fail('\n'.join(msg))
