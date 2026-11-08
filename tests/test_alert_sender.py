"""Offline sender checks. Every request is intercepted before network access."""
import contextlib
import hashlib
import hmac
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

SPEC = importlib.util.spec_from_file_location('alert_sender', Path(__file__).resolve().parents[1] / 'tools/alerts/send.py')
sender = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sender)
SECRET = 'synthetic-sender-secret-DO-NOT-LOG'


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.body = b'{ "summary": "Synthetic test" }\n'
        self.event = Path(self.tmp.name) / 'event.json'
        self.event.write_bytes(self.body)
        self.key = Path(self.tmp.name) / 'secret'
        self.key.write_text(SECRET + '\n')

    def run_sender(self, extra=(), env=None, status=204, error=None):
        output, errors = io.StringIO(), io.StringIO()
        response = mock.MagicMock()
        response.__enter__.return_value.status = status
        opener = mock.Mock()
        opener.open.return_value = response
        opener.open.side_effect = error
        with mock.patch.dict(os.environ, env or {}, clear=True), \
                mock.patch.object(sender.urllib.request, 'build_opener', return_value=opener) as build, \
                mock.patch.object(sender.time, 'time', return_value=1800000000), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = sender.main(['--event', str(self.event), *extra])
        text = output.getvalue() + errors.getvalue()
        self.assertNotIn(SECRET, text)
        self.assertNotIn('sha256=', text)
        return code, text, opener, build

    def test_file_and_env_secret_sign_exact_bytes(self):
        for extra, env in [(['--secret-file', str(self.key)], {}), ([], {'OPENHRA_ALERT_SECRET': SECRET})]:
            code, text, opener, build = self.run_sender(extra, env)
            self.assertEqual(code, 0)
            self.assertEqual(text, 'alert sender: accepted\n')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.data, self.body)
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.full_url, 'https://plans.openhra.com/api/alerts')
            self.assertEqual(request.get_header('X-openhra-timestamp'), '1800000000')
            expected = 'sha256=' + hmac.new(SECRET.encode(), b'1800000000.' + self.body, hashlib.sha256).hexdigest()
            self.assertEqual(request.get_header('X-openhra-signature'), expected)
            self.assertEqual(opener.open.call_args.kwargs, {'timeout': 10})
            self.assertIsInstance(build.call_args.args[0], sender.NoRedirect)

    def test_file_takes_precedence_over_environment(self):
        code, _, opener, _ = self.run_sender(['--secret-file', str(self.key)], {'OPENHRA_ALERT_SECRET': 'synthetic-other'})
        self.assertEqual(code, 0)
        self.assertEqual(opener.open.call_args.args[0].get_header('X-openhra-signature'), sender.sign(self.body, 1800000000, SECRET.encode()))

    def test_invalid_inputs_do_not_attempt_network(self):
        for extra in [[], ['--secret-file', str(self.key) + '-missing'],
                      ['--secret-file', str(self.key), '--url', 'http://localhost/api/alerts'],
                      ['--secret-file', str(self.key), '--url', 'https://user:password@localhost/api/alerts'],
                      ['--secret-file', str(self.key), '--url', 'https://localhost/api/alerts#fragment']]:
            code, _, opener, build = self.run_sender(extra)
            self.assertEqual(code, 1)
            build.assert_not_called()
            opener.open.assert_not_called()
        for body in [b'{', b'[]', b'null', b' ' * 8193, b'\xff']:
            self.event.write_bytes(body)
            code, _, opener, _ = self.run_sender(['--secret-file', str(self.key)])
            self.assertEqual(code, 1)
            opener.open.assert_not_called()

    def test_stdin_and_size_boundary(self):
        self.event.write_bytes(b'{}' + b' ' * 8190)
        self.assertEqual(self.run_sender(['--secret-file', str(self.key)])[0], 0)
        with mock.patch.object(sender.sys, 'stdin', mock.Mock(buffer=io.BytesIO(self.body))):
            self.assertEqual(self.run_sender(['--event', '-', '--secret-file', str(self.key)])[0], 0)

    def test_failures_are_sanitized_and_redirects_refused(self):
        for status in [200, 301, 409, 500]:
            self.assertEqual(self.run_sender(['--secret-file', str(self.key)], status=status)[0], 1)
        for error in [urllib.error.HTTPError('https://localhost', 401, SECRET, {}, None),
                      urllib.error.URLError(SECRET), TimeoutError(SECRET)]:
            code, text, _, _ = self.run_sender(['--secret-file', str(self.key)], error=error)
            self.assertEqual(code, 1)
            self.assertNotIn(SECRET, text)
        self.assertIsNone(sender.NoRedirect().redirect_request(None, None, 307, None, {}, 'https://localhost'))


if __name__ == '__main__':
    unittest.main()
