#
# Copyright (c) nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/nexB/scancode-toolkit/
# The ScanCode software is licensed under the Apache License version 2.0.
# Data generated with ScanCode require an acknowledgment.
# ScanCode is a trademark of nexB Inc.
#
# You may not use this software except in compliance with the License.
# You may obtain a copy of the License at: http://apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
# When you publish or redistribute any data created with ScanCode or any ScanCode
# derivative work, you must accompany this data with the following acknowledgment:
#
#  Generated with ScanCode and provided on an "AS IS" BASIS, WITHOUT WARRANTIES
#  OR CONDITIONS OF ANY KIND, either express or implied. No content created from
#  ScanCode should be considered or used as legal advice. Consult an Attorney
#  for any legal advice.
#  ScanCode is a free software code scanning tool from nexB Inc. and others.
#  Visit https://github.com/nexB/scancode-toolkit/ for support and download.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from collections import OrderedDict
import io
import json
import os

from commoncode.system import on_linux
from commoncode.system import on_windows
from scancode_config import scancode_root_dir


def run_scan_plain(options, cwd=None, test_mode=True, expected_rc=0, env=None):
    """
    Run a scan as a plain subprocess. Return rc, stdout, stderr.
    """
    from commoncode.command import execute2

    options = add_windows_extra_timeout(options)

    if test_mode and '--test-mode' not in options:
        options.append('--test-mode')

    scmd = b'deltacode' if on_linux else 'deltacode'
    scan_cmd = os.path.join(scancode_root_dir, scmd)
    rc, stdout, stderr = execute2(cmd_loc=scan_cmd, args=options, cwd=cwd, env=env)

    if rc != expected_rc:
        opts = get_opts(options)
        error = '''
Failure to run: deltacode %(opts)s
stdout:
%(stdout)s

stderr:
%(stderr)s
''' % locals()
        assert rc == expected_rc, error

    return rc, stdout, stderr


def run_scan_click(options, monkeypatch=None, test_mode=True, expected_rc=0, env=None):
    """
    Run a scan as a Click-controlled subprocess
    If monkeypatch is provided, a tty with a size (80, 43) is mocked.
    Return a click.testing.Result object.
    """
    import click
    from click.testing import CliRunner
    from deltacode import cli

    options = add_windows_extra_timeout(options)

    if monkeypatch:
        monkeypatch.setattr(click._termui_impl, 'isatty', lambda _: True)
        monkeypatch.setattr(click , 'get_terminal_size', lambda : (80, 43,))
    runner = CliRunner()

    result = runner.invoke(cli.cli, options, catch_exceptions=False, env=env)

    output = result.output
    if result.exit_code != expected_rc:
        opts = get_opts(options)
        error = '''
Failure to run: deltacode %(opts)s
output:
%(output)s
''' % locals()
        assert result.exit_code == expected_rc, error
    return result


def get_opts(options):
    try:
        return ' '.join(options)
    except:
        try:
            return b' '.join(options)
        except:
            return b' '.join(map(repr, options))


WINDOWS_CI_TIMEOUT = '222.2'


def add_windows_extra_timeout(options, timeout=WINDOWS_CI_TIMEOUT):
    """
    Add a timeout to an options list if on Windows.
    """
    if on_windows and '--timeout' not in options:
        # somehow the Appevyor windows CI is now much slower and timeouts at 120 secs
        options += ['--timeout', timeout]
    return options


def remove_windows_extra_timeout(scancode_options, timeout=WINDOWS_CI_TIMEOUT):
    """
    Strip a test timeout from a pretty deltacode_options mapping if on Windows.
    """
    if on_windows:
        if scancode_options and scancode_options.get('--timeout') == timeout:
            del scancode_options['--timeout']


def check_json_scan(expected_file, result_file, regen=False, remove_file_date=False, ignore_headers=False):
    """
    Check the scan `result_file` JSON results against the `expected_file`
    expected JSON results.

    If `regen` is True the expected_file WILL BE overwritten with the new scan
    results from `results_file`. This is convenient for updating tests
    expectations. But use with caution.

    if `remove_file_date` is True, the file.date attribute is removed.
    """
    results = load_json_result(result_file, remove_file_date)
    if regen:
        with open(expected_file, 'wb') as reg:
            json.dump(results, reg, indent=2, separators=(',', ': '))

    expected = load_json_result(expected_file, remove_file_date)

    if ignore_headers:
        results.pop('headers', None)
        expected.pop('headers', None)

    # NOTE we redump the JSON as a string for a more efficient display of the
    # failures comparison/diff
    # TODO: remove sort, this should no longer be needed
    expected = json.dumps(expected, indent=2, sort_keys=True, separators=(',', ': '))
    results = json.dumps(results, indent=2, sort_keys=True, separators=(',', ': '))
    assert expected == results


def load_json_result(location, remove_file_date=False):
    """
    Load the JSON scan results file at `location` location as UTF-8 JSON.

    To help with test resilience against small changes some attributes are
    removed or streamlined such as the  "tool_version" and scan "errors".

    To optionally also remove date attributes from "files" and "headers"
    entries, set the `remove_file_date` argument to True.
    """
    with io.open(location, encoding='utf-8') as res:
        scan_results = res.read()
    return load_json_result_from_string(scan_results, remove_file_date)


def load_json_result_from_string(string, remove_file_date=False):
    """
    Load the JSON scan results `string` as UTF-8 JSON.
    """
    scan_results = json.loads(string, object_pairs_hook=OrderedDict)
    # clean new headers attributes
    streamline_headers(scan_results)

    scan_results['deltas'].sort(key=lambda  x: x['factors'], reverse=False)
    scan_results['deltas'].sort(key=lambda x: x['score'], reverse=True)
    return scan_results


def streamline_errors(errors):
    """
    Modify the `errors` list in place to make it easier to test
    """
    for i, error in enumerate(errors[:]):
        error_lines = error.splitlines(True)
        if len(error_lines) <= 1:
            continue
        # keep only first and last line
        cleaned_error = ''.join([error_lines[0] + error_lines[-1]])
        errors[i] = cleaned_error


def streamline_headers(headers):
    """
    Modify the `headers` list of mappings in place to make it easier to test.
    """
    headers.pop('deltacode_version', None)
    headers.pop('deltacode_options', None)
    streamline_errors(headers['deltacode_errors'])