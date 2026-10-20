"""Synthetic transport checks: never call Supabase or retry a state-changing request."""
import errno
import io
import json
import socket
import ssl
import unittest
from http.client import IncompleteRead
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError, URLError

from desktop.cloud import CloudAPIError, CloudNetworkError, request
from desktop.daily_official import failure_record


def response(body: bytes = b'{"ok": true}') -> MagicMock:
    value = MagicMock()
    value.__enter__.return_value.read.return_value = body
    return value


class CloudNetworkTests(unittest.TestCase):
    def test_transient_read_request_recovers_with_short_bounded_backoff(self) -> None:
        with patch('desktop.cloud.urlopen', side_effect=[URLError(TimeoutError('private-token')), response()]) as network, patch('desktop.cloud.time.sleep') as sleep:
            self.assertEqual(request('/rest/v1/discussions', token='private-token', method='get'), {'ok': True})
        self.assertEqual(network.call_count, 2)
        self.assertEqual(network.call_args.args[0].get_method(), 'GET')
        sleep.assert_called_once_with(0.5)

    def test_read_failures_stop_at_three_attempts_and_keep_safe_metadata(self) -> None:
        original = ConnectionResetError(errno.ECONNRESET, 'private-url-token-body')
        original.winerror = 10054
        with patch('desktop.cloud.urlopen', side_effect=URLError(original)) as network, patch('desktop.cloud.time.sleep') as sleep:
            with self.assertRaises(CloudNetworkError) as caught:
                request('/rest/v1/discussions?private-url', token='private-token', method='GET')
        error = caught.exception
        self.assertEqual(network.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(0.5), call(1.0)])
        self.assertEqual(vars(error), {'network_kind': 'connection_reset', 'attempts': 3, 'retry_allowed': True, 'errno': errno.ECONNRESET, 'winerror': 10054})
        self.assertIsNone(error.__cause__)
        self.assertNotIn('private', str(error))
        report = failure_record('account', error)
        self.assertEqual(report['causes'][0]['network_kind'], 'connection_reset')
        self.assertEqual(report['causes'][0]['attempts'], 3)
        self.assertEqual(report['causes'][0]['errno'], errno.ECONNRESET)
        self.assertEqual(report['causes'][0]['winerror'], 10054)
        self.assertNotIn('private', json.dumps(report))

    def test_all_posts_are_single_attempt_even_for_connect_failures(self) -> None:
        failures = [TimeoutError('private'), ConnectionResetError(errno.ECONNRESET, 'private'), ConnectionRefusedError(errno.ECONNREFUSED, 'private'), socket.gaierror(socket.EAI_AGAIN, 'private')]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch('desktop.cloud.urlopen', side_effect=URLError(failure)) as network, patch('desktop.cloud.time.sleep') as sleep:
                with self.assertRaises(CloudNetworkError) as caught:
                    request('/auth/v1/token?grant_type=refresh_token', {'refresh_token': 'private'})
                self.assertEqual(network.call_count, 1)
                self.assertEqual(caught.exception.attempts, 1)
                self.assertFalse(caught.exception.retry_allowed)
                sleep.assert_not_called()

    def test_interrupted_response_retries_only_for_reads(self) -> None:
        for method, attempts in [('GET', 2), ('POST', 1)]:
            broken = response()
            broken.__enter__.return_value.read.side_effect = IncompleteRead(b'private-body', 100)
            with self.subTest(method=method), patch('desktop.cloud.urlopen', side_effect=[broken, response()]) as network, patch('desktop.cloud.time.sleep'):
                if method == 'GET':
                    self.assertEqual(request('/rest/v1/discussions', method=method), {'ok': True})
                else:
                    with self.assertRaises(CloudNetworkError) as caught:
                        request('/rest/v1/discussions', {'payload': 'private'}, method=method)
                    self.assertEqual(caught.exception.network_kind, 'response_incomplete')
                    self.assertNotIn('private', str(caught.exception))
                self.assertEqual(network.call_count, attempts)

    def test_temporary_dns_failure_recovers_but_missing_host_does_not_loop(self) -> None:
        with patch('desktop.cloud.urlopen', side_effect=[URLError(socket.gaierror(socket.EAI_AGAIN, 'private-host')), response()]) as network, patch('desktop.cloud.time.sleep'):
            self.assertEqual(request('/rest/v1/discussions', method='GET'), {'ok': True})
        self.assertEqual(network.call_count, 2)
        with patch('desktop.cloud.urlopen', side_effect=URLError(socket.gaierror(socket.EAI_NONAME, 'private-host'))) as network, patch('desktop.cloud.time.sleep') as sleep:
            with self.assertRaises(CloudNetworkError) as caught:
                request('/rest/v1/discussions', method='GET')
        self.assertEqual(caught.exception.network_kind, 'dns')
        self.assertFalse(caught.exception.retry_allowed)
        network.assert_called_once()
        sleep.assert_not_called()

    def test_tls_and_unclassified_failures_do_not_repeat(self) -> None:
        for failure, expected in [(ssl.SSLCertVerificationError(1, 'private-host'), 'tls'), ('private-unknown-reason', 'network')]:
            with self.subTest(expected=expected), patch('desktop.cloud.urlopen', side_effect=URLError(failure)) as network, patch('desktop.cloud.time.sleep') as sleep:
                with self.assertRaises(CloudNetworkError) as caught:
                    request('/rest/v1/discussions', method='GET')
                self.assertEqual(caught.exception.network_kind, expected)
                self.assertFalse(caught.exception.retry_allowed)
                network.assert_called_once()
                sleep.assert_not_called()

    def test_http_errors_preserve_existing_status_contract_without_retries(self) -> None:
        for status in [400, 401, 404, 429, 503]:
            error = HTTPError('https://private.example/token', status, 'private', {}, io.BytesIO(b'private'))
            with self.subTest(status=status), patch('desktop.cloud.urlopen', side_effect=error) as network, patch('desktop.cloud.time.sleep') as sleep:
                with self.assertRaises(CloudAPIError) as caught:
                    request('/rest/v1/discussions', method='GET')
                self.assertEqual(vars(caught.exception), {'status_code': status})
                self.assertNotIn('private', str(caught.exception))
                network.assert_called_once()
                sleep.assert_not_called()

    def test_windows_transport_code_from_response_read_is_preserved(self) -> None:
        broken = response()
        original = OSError(errno.EIO, 'private-provider-text')
        original.winerror = 10060
        broken.__enter__.return_value.read.side_effect = original
        with patch('desktop.cloud.urlopen', return_value=broken) as network, patch('desktop.cloud.time.sleep') as sleep:
            with self.assertRaises(CloudNetworkError) as caught:
                request('/rest/v1/discussions', {'payload': 'private'}, method='POST')
        self.assertEqual(caught.exception.network_kind, 'timeout')
        self.assertEqual(caught.exception.winerror, 10060)
        self.assertFalse(caught.exception.retry_allowed)
        network.assert_called_once()
        sleep.assert_not_called()

    def test_invalid_json_is_not_retried_as_transport_failure(self) -> None:
        with patch('desktop.cloud.urlopen', return_value=response(b'private malformed json')) as network, patch('desktop.cloud.time.sleep') as sleep:
            with self.assertRaises(json.JSONDecodeError):
                request('/rest/v1/discussions', method='GET')
        network.assert_called_once()
        sleep.assert_not_called()

    def test_wrapped_network_metadata_survives_without_provider_details(self) -> None:
        inner = CloudNetworkError('timeout', 1, False)
        outer = RuntimeError('private token')
        outer.__cause__ = inner
        report = failure_record('account', outer)
        self.assertEqual(report['causes'][1]['network_kind'], 'timeout')
        self.assertFalse(report['causes'][1]['retry_allowed'])
        self.assertNotIn('private', json.dumps(report))
        self.assertNotIn('errno', report['causes'][1])


if __name__ == '__main__':
    unittest.main()
