import base64
import importlib
import io
import json
import socket
import threading
import time
from unittest.mock import Mock, patch

from .test_core_store import CoreCase
from living_spaces_core import bridge, db, grants, limits, sessions


PUBLIC = '93.184.216.34'


class Response:
    def __init__(self, body=b'hello', status=200, headers=None):
        self.status = status
        self.length = None
        self.headers = headers or {'Content-Type': 'text/plain; charset=utf-8'}
        self.stream = io.BytesIO(body)

    def getheaders(self):
        return list(self.headers.items())

    def getheader(self, name, default=None):
        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), default)

    def read1(self, amount):
        return self.stream.read(amount)

    def close(self):
        self.stream.close()


class NetGrantTests(CoreCase):
    def test_new_space_has_internet_access(self):
        grant = next((g for g in grants.list_grants(self.sid) if g['capability'] == 'net'), None)
        self.assertIsNotNone(grant)
        self.assertEqual(grant['status'], 'granted')
        self.assertTrue(grants.CAPABILITIES['net']['data_leaves_device'])

    def test_revoke_and_rerequest_require_host_approval(self):
        session = sessions.open_session(self.sid)['session']
        grants.decide(self.sid, 'net', 'revoke')
        reply = bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com'})
        self.assertEqual(reply['error']['code'], 'not_granted')
        grants.request(self.sid, 'net', scope={}, purpose='Public demo', actor='agent:demo')
        self.assertEqual(bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com'})['error']['code'], 'not_granted')
        grants.decide(self.sid, 'net', 'grant')
        grants.check(self.sid, 'net')

    def test_existing_database_migrates_once_and_preserves_decisions(self):
        other = self.create('Other Demo')['id']
        with db.write() as conn:
            conn.execute("DELETE FROM grants WHERE space=? AND capability='net'", (self.sid,))
            conn.execute("UPDATE grants SET status='revoked' WHERE space=? AND capability='net'", (other,))
            conn.execute('PRAGMA user_version=1')
        db._initialized.discard(str(db.db_path()))
        self.assertEqual(next(g for g in grants.list_grants(self.sid) if g['capability'] == 'net')['status'], 'granted')
        self.assertEqual(next(g for g in grants.list_grants(other) if g['capability'] == 'net')['status'], 'revoked')
        grants.decide(self.sid, 'net', 'revoke')
        before = grants.audit_log(self.sid)
        db._initialized.discard(str(db.db_path()))
        self.assertEqual(next(g for g in grants.list_grants(self.sid) if g['capability'] == 'net')['status'], 'revoked')
        self.assertEqual(grants.audit_log(self.sid), before)


class NetTests(CoreCase):
    """Synthetic DNS and HTTP transport; header values are public test data."""

    def setUp(self):
        super().setUp()
        self.net = importlib.import_module('living_spaces_core.net')
        self.resolver = Mock(return_value=[PUBLIC])
        self.responses = [Response()]
        self.connections = []
        self.requests = []
        self.on_response = None

        def connect(host, port, ip, timeout):
            conn = Mock()
            conn.request.side_effect = lambda *args, **kwargs: self.requests.append((args, kwargs))
            def response():
                if self.on_response:
                    self.on_response()
                return self.responses.pop(0)
            conn.getresponse.side_effect = response
            self.connections.append((host, port, ip, timeout, conn))
            return conn

        for name, value in (('_resolve', self.resolver), ('_connection', connect)):
            seam = patch.object(self.net, name, value)
            seam.start()
            self.addCleanup(seam.stop)

    def fetch(self, url='https://example.com/path?q=public-demo', **kwargs):
        return self.net.fetch(self.sid, url, **kwargs)

    def blocked(self, url, reason):
        before = len(self.connections)
        error = self.error('blocked', self.fetch, url)
        self.assertEqual(error['reason'], reason)
        self.assertEqual(len(self.connections), before)

    def test_refused_address_classes(self):
        addresses = [
            '127.0.0.1', '::1', '10.1.2.3', '192.168.1.2', '172.16.1.2',
            '169.254.169.254', '169.254.1.1', 'fe80::1', 'fc00::1', 'fd00:ec2::254',
            '100.64.0.1', '100.127.255.254', '224.0.0.1', 'ff02::1', '0.0.0.0', '::',
            '240.0.0.1', '192.0.2.1', 'fec0::1', '2001:db8::1', '::ffff:127.0.0.1',
            '::ffff:10.0.0.1', '2002:7f00:1::1', '2002:a00:1::1',
            '64:ff9b::7f00:1', '64:ff9b::a00:1', '64:ff9b:1::a00:1', '::127.0.0.1',
            '2001:0:4136:e378:8000:63bf:80ff:fffe',
        ]
        for ip in addresses:
            with self.subTest(ip=ip):
                self.resolver.return_value = [ip]
                self.blocked('https://example.com', 'private_address')

    def test_legacy_ipv4_literals_cannot_bypass_policy(self):
        for host in ('2130706433', '0x7f.1', '0177.0.0.1', '127.1', '0x7f000001'):
            with self.subTest(host=host):
                self.blocked('https://' + host, 'private_address')
        self.resolver.assert_not_called()

    def test_literals_and_mixed_dns_are_checked_before_connect(self):
        self.blocked('https://127.0.0.1', 'private_address')
        self.blocked('https://[::1]', 'private_address')
        self.resolver.return_value = [PUBLIC, '10.0.0.1']
        self.blocked('https://example.com', 'private_address')

    def test_rebinding_pins_first_vetted_answer_without_second_resolution(self):
        self.resolver.side_effect = [[PUBLIC], ['127.0.0.1']]
        self.assertEqual(self.fetch()['text'], 'hello')
        self.assertEqual(self.resolver.call_count, 1)
        self.assertEqual(self.connections[0][:3], ('example.com', 443, PUBLIC))

    def test_public_ipv6_and_8443(self):
        self.resolver.return_value = ['2606:4700:4700::1111']
        self.fetch('https://example.com:8443/a')
        self.assertEqual(self.connections[0][:3], ('example.com', 8443, '2606:4700:4700::1111'))
        self.assertEqual(self.requests[0][1]['headers']['Host'], 'example.com:8443')

    def test_scheme_and_port_policy(self):
        for url, reason in [('http://example.com', 'scheme'), ('file:///tmp/x', 'scheme'),
                            ('https://example.com:8080', 'port'), ('https://example.com:0', 'port')]:
            with self.subTest(url=url):
                self.blocked(url, reason)

    def test_invalid_inputs_never_send(self):
        for url in (None, '', 'https://', 'https://user:pass@example.com',
                    'https://example.com:bad', 'https://example.com/\r\nX:bad', 'https://[fe80::1%25en0]'):
            with self.subTest(url=url):
                self.error('invalid', self.fetch, url)
        for kwargs in ({'method': 'CONNECT'}, {'method': []}, {'as_': 'xml'}, {'as_': []},
                       {'headers': []}, {'headers': {'X-Test': '\r\nBad: yes'}},
                       {'headers': {'Bad Header': 'x'}}, {'headers': {'x': 4}}, {'body': {}},
                       {'method': 'GET', 'body': 'data'}):
            with self.subTest(kwargs=kwargs):
                self.error('invalid', self.fetch, **kwargs)
        self.assertFalse(self.connections)

    def test_redirect_to_private_is_refused(self):
        self.responses = [Response(status=302, headers={'Location': 'https://127.0.0.1/a'})]
        self.assertEqual(self.error('blocked', self.fetch)['reason'], 'private_address')
        self.assertEqual(len(self.connections), 1)

    def test_redirect_downgrade_is_refused(self):
        self.responses = [Response(status=302, headers={'Location': 'http://example.com/a'})]
        self.assertEqual(self.error('blocked', self.fetch)['reason'], 'scheme')
        self.assertEqual(len(self.connections), 1)

    def test_five_redirects_allowed_and_sixth_refused(self):
        self.responses = [Response(status=302, headers={'Location': '/next'}) for _ in range(5)] + [Response()]
        self.assertEqual(self.fetch()['url'], 'https://example.com/next')
        self.responses = [Response(status=302, headers={'Location': '/again'}) for _ in range(6)]
        self.assertEqual(self.error('blocked', self.fetch)['reason'], 'redirect')
        self.assertEqual(len(self.connections), 12)

    def test_redirect_method_rules(self):
        for status, expected_method, expected_body in ((301, 'GET', None), (302, 'GET', None),
                                                       (303, 'GET', None), (307, 'POST', b'demo'), (308, 'POST', b'demo')):
            with self.subTest(status=status):
                self.responses = [Response(status=status, headers={'Location': '/next'}), Response()]
                self.fetch(method='POST', body='demo')
                args, kwargs = self.requests[-1]
                self.assertEqual(args[0], expected_method)
                self.assertEqual(kwargs['body'], expected_body)

    def test_space_credentials_forwarded_and_reserved_framing_headers_stripped(self):
        self.fetch(method='POST', body='demo', headers={'Cookie': 'secret', 'AUTHORIZATION': 'secret',
                   'Proxy-Authorization': 'secret', 'Proxy-Thing': 'secret', 'Host': 'localhost',
                   'X-Hermes-Token': 'secret', 'x-hermesanything': 'secret', 'X-Public': 'demo',
                   'Content-Length': '999', 'Transfer-Encoding': 'chunked', 'Connection': 'upgrade'})
        headers = self.requests[0][1]['headers']
        self.assertEqual(headers, {'Cookie': 'secret', 'AUTHORIZATION': 'secret', 'X-Public': 'demo',
                                   'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT})

    def test_request_body_cap_has_numbers(self):
        error = self.error('limit', self.fetch, method='POST', body='x' * (limits.BRIDGE_BYTES + 1))
        self.assertEqual((error['limit'], error['actual']), (limits.BRIDGE_BYTES, limits.BRIDGE_BYTES + 1))
        self.assertFalse(self.connections)

    def test_response_cap_has_numbers_with_and_without_content_length(self):
        cap = 5 * 1024 * 1024
        for headers in ({'Content-Length': str(cap + 1)}, {}):
            self.responses = [Response(b'x' * (cap + 1), headers=headers)]
            error = self.error('limit', self.fetch)
            self.assertEqual((error['limit'], error['actual']), (cap, cap + 1))

    def test_text_json_and_bytes(self):
        self.responses = [Response('café'.encode('utf8')), Response(b'{"a":1}'), Response(b'\x00\xff', headers={'Content-Type': 'image/png'})]
        self.assertEqual(self.fetch()['text'], 'café')
        self.assertEqual(self.fetch(as_='json')['json'], {'a': 1})
        result = self.fetch(as_='bytes')
        self.assertEqual((base64.b64decode(result['b64']), result['mime']), (b'\x00\xff', 'image/png'))

    def test_invalid_json_and_nonfinite_json_fail(self):
        for body in (b'{', b'{"number":NaN}', b'{"number":1e999}'):
            self.responses = [Response(body)]
            self.error('invalid', self.fetch, as_='json')

    def test_methods_and_http_errors_are_results(self):
        for method in ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'):
            self.responses = [Response(status=404)]
            result = self.fetch(method=method)
            self.assertEqual(result['status'], 404)
            self.assertEqual(result['text'], '' if method == 'HEAD' else 'hello')

    def test_network_errors_do_not_expose_url_or_credentials(self):
        self.resolver.side_effect = OSError('secret-url?token=secret')
        error = self.error('blocked', self.fetch)
        self.assertEqual(error['reason'], 'network_error')
        self.assertNotIn('secret', json.dumps(error))

    def test_audit_is_bounded_and_contains_no_query_or_body(self):
        self.fetch(method='POST', body='private-demo-body')
        row = next(r for r in grants.audit_log(self.sid) if r['action'] == 'net.fetch')
        self.assertEqual(row['detail'], {'host': 'example.com', 'status': 200, 'bytes': 5})
        self.assertNotIn('private-demo-body', json.dumps(row))
        self.blocked('https://127.0.0.1/?secret=demo', 'private_address')
        rows = [r for r in grants.audit_log(self.sid) if r['action'] == 'net.fetch']
        self.assertEqual(len(rows), 2)
        self.assertNotIn('secret', json.dumps(rows))

    def test_no_sqlite_lock_and_no_delivery_after_revoke(self):
        def revoke():
            grants.decide(self.sid, 'net', 'revoke')
        self.on_response = revoke
        session = sessions.open_session(self.sid)['session']
        reply = bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com', 'as': 'text'})
        self.assertEqual(reply['error']['code'], 'not_granted')
        self.assertEqual(len(self.connections), 1)

    def test_revoke_stops_redirects(self):
        self.responses = [Response(status=302, headers={'Location': '/next'})]
        self.on_response = lambda: grants.decide(self.sid, 'net', 'revoke')
        self.error('not_granted', self.fetch)
        self.assertEqual(len(self.connections), 1)

    def test_bridge_dispatches_as_and_validates_arguments(self):
        session = sessions.open_session(self.sid)['session']
        self.responses = [Response(b'{"public":true}')]
        reply = bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com', 'as': 'json'})
        self.assertEqual(reply['result']['json'], {'public': True})
        self.assertEqual(bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com', 'unknown': 1})['error']['code'], 'invalid')

    def test_pinned_transport_uses_numeric_socket_and_hostname_tls(self):
        raw, tls, context = Mock(), Mock(), Mock()
        context.wrap_socket.return_value = tls
        with patch.object(self.net.socket, 'socket', return_value=raw) as make, patch.object(self.net.ssl, 'create_default_context', return_value=context):
            conn = self.net._PinnedHTTPS('example.com', 443, PUBLIC, 2)
            conn.connect()
            make.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
            raw.connect.assert_called_once_with((PUBLIC, 443))
            context.wrap_socket.assert_called_once_with(raw, server_hostname='example.com', do_handshake_on_connect=False)
            tls.do_handshake.assert_called_once()
            conn.close()

    def test_total_deadline_interrupts_slow_response(self):
        released = threading.Event()
        conn = Mock()
        conn.abort.side_effect = released.set
        def stalled():
            released.wait(1)
            raise TimeoutError()
        conn.getresponse.side_effect = stalled
        with patch.object(self.net, 'TIMEOUT', .03), patch.object(self.net, '_connection', return_value=conn):
            start = time.monotonic()
            self.assertEqual(self.error('blocked', self.fetch)['reason'], 'network_error')
            self.assertLess(time.monotonic() - start, .5)

    def test_dns_timeout_and_all_record_families(self):
        done = threading.Event()
        def stalled(*args, **kwargs):
            done.wait(1)
            return []
        with patch.object(self.net.socket, 'getaddrinfo', side_effect=stalled):
            try:
                with self.assertRaises(TimeoutError):
                    self.net._resolve_host('example.com', 443, .02)
            finally:
                done.set()
        answers = [(socket.AF_INET, 1, 6, '', (PUBLIC, 443)),
                   (socket.AF_INET6, 1, 6, '', ('::1', 443, 0, 0))]
        with patch.object(self.net.socket, 'getaddrinfo', return_value=answers) as resolver:
            self.assertEqual(self.net._resolve_host('example.com', 443, 1), [PUBLIC, '::1'])
            self.assertEqual(resolver.call_args.args, ('example.com', 443, socket.AF_UNSPEC, socket.SOCK_STREAM))

    def test_deadline_is_shared_across_redirects(self):
        elapsed = [0]
        def advance():
            elapsed[0] += 11
        self.on_response = advance
        self.responses = [Response(status=302, headers={'Location': '/next'}) for _ in range(3)]
        with patch.object(self.net.time, 'monotonic', side_effect=lambda: elapsed[0]):
            self.assertEqual(self.error('blocked', self.fetch)['reason'], 'network_error')
        self.assertEqual(len(self.connections), 2)
        self.assertEqual([c[3] for c in self.connections], [20, 9])

    def test_session_closed_during_fetch_suppresses_result(self):
        session = sessions.open_session(self.sid)['session']
        self.on_response = lambda: sessions.close_session(session)
        reply = bridge.dispatch(self.sid, session, 'net.fetch', {'url': 'https://example.com'})
        self.assertEqual(reply['error']['code'], 'session_invalid')

    def test_exact_response_limit_is_allowed(self):
        self.responses = [Response(b'x' * (5 * 1024 * 1024))]
        self.assertEqual(len(self.fetch()['text']), 5 * 1024 * 1024)

    def test_truncated_http_response_is_a_network_error(self):
        import http.client
        raw = Mock()
        raw.makefile.return_value = io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nshort')
        response = http.client.HTTPResponse(raw)
        response.begin()
        self.responses = [response]
        self.assertEqual(self.error('blocked', self.fetch)['reason'], 'network_error')

    def test_bridge_forwards_only_space_supplied_credentials(self):
        session = sessions.open_session(self.sid)['session']
        cases = ({}, {'Authorization': 'Bearer public-space-demo'},
                 {'Cookie': 'space=public-demo'},
                 {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo'})
        for credentials in cases:
            with self.subTest(credentials=list(credentials)):
                self.responses = [Response()]
                reply = bridge.dispatch(self.sid, session, 'net.fetch', {
                    'url': 'https://example.com/data',
                    'headers': {**credentials, 'X-Public': 'demo'},
                })
                self.assertTrue(reply['ok'], reply)
                self.assertEqual(reply['result']['text'], 'hello')
                self.assertEqual(self.requests[-1][1]['headers'], {
                    **credentials, 'X-Public': 'demo',
                    'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT,
                })

    def test_reserved_header_stripping_is_case_insensitive_with_own_credentials(self):
        for spelling in (str.lower, str.upper, str.swapcase):
            with self.subTest(spelling=spelling.__name__):
                self.responses = [Response()]
                supplied = {spelling(name): 'public-reserved-demo' for name in (
                    'Host', 'Content-Length', 'Transfer-Encoding', 'Connection',
                    'Keep-Alive', 'Upgrade', 'Te', 'Trailer', 'Accept-Encoding', 'User-Agent',
                    'Proxy-Authorization', 'Proxy-Thing', 'X-Hermes-Token', 'X-HermesAnything',
                )}
                supplied.update({spelling('Authorization'): 'Bearer public-space-demo',
                                 spelling('Cookie'): 'space=public-demo', 'X-Public': 'demo'})
                self.assertEqual(self.fetch(method='POST', body='demo', headers=supplied)['text'], 'hello')
                self.assertEqual({k.lower(): v for k, v in self.requests[-1][1]['headers'].items()}, {
                    'authorization': 'Bearer public-space-demo', 'cookie': 'space=public-demo',
                    'x-public': 'demo', 'host': 'example.com', 'accept-encoding': 'identity',
                    'user-agent': self.net.USER_AGENT,
                })

    def test_same_origin_redirects_preserve_space_credentials(self):
        supplied = {'aUtHoRiZaTiOn': 'Bearer public-space-demo', 'cOoKiE': 'space=public-demo',
                    'X-Public': 'demo'}
        for status in (301, 302, 303, 307, 308):
            for location in ('/next', 'https://example.com/next', 'https://EXAMPLE.COM:443/next'):
                with self.subTest(status=status, location=location):
                    self.responses = [Response(status=status, headers={'Location': location}), Response()]
                    result = self.fetch(headers=supplied)
                    self.assertEqual((result['status'], result['text']), (200, 'hello'))
                    self.assertEqual([c[:3] for c in self.connections[-2:]],
                                     [('example.com', 443, PUBLIC)] * 2)
                    self.assertEqual([request[1]['headers'] for request in self.requests[-2:]],
                                     [{**supplied, 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT}] * 2)

    def test_cross_host_redirects_strip_space_credentials_case_insensitively(self):
        for authorization, cookie in (('Authorization', 'Cookie'), ('authorization', 'cookie'),
                                      ('AUTHORIZATION', 'COOKIE'), ('aUtHoRiZaTiOn', 'cOoKiE')):
            for status in (301, 302, 303, 307, 308):
                with self.subTest(authorization=authorization, status=status):
                    supplied = {authorization: 'Bearer public-space-demo', cookie: 'space=public-demo',
                                'X-Public': 'demo'}
                    self.responses = [Response(status=status, headers={'Location': 'https://other.example/next'}),
                                      Response()]
                    result = self.fetch(headers=supplied)
                    self.assertEqual((result['url'], result['text']), ('https://other.example/next', 'hello'))
                    self.assertEqual([c[:3] for c in self.connections[-2:]],
                                     [('example.com', 443, PUBLIC), ('other.example', 443, PUBLIC)])
                    self.assertEqual([request[1]['headers'] for request in self.requests[-2:]], [
                        {**supplied, 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                        {'X-Public': 'demo', 'Host': 'other.example', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    ])

    def test_changed_port_redirects_strip_space_credentials(self):
        supplied = {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo',
                    'X-Public': 'demo'}
        for origin, destination in (('example.com', 'example.com:8443'),
                                    ('example.com:8443', 'example.com')):
            with self.subTest(origin=origin, destination=destination):
                self.responses = [Response(status=307, headers={'Location': f'https://{destination}/next'}),
                                  Response()]
                result = self.fetch(f'https://{origin}/start', headers=supplied)
                self.assertEqual((result['url'], result['text']), (f'https://{destination}/next', 'hello'))
                self.assertEqual([request[1]['headers'] for request in self.requests[-2:]], [
                    {**supplied, 'Host': origin, 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    {'X-Public': 'demo', 'Host': destination, 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                ])

    def test_redirect_return_to_origin_never_resurrects_space_credentials(self):
        supplied = {'aUtHoRiZaTiOn': 'Bearer public-space-demo', 'cOoKiE': 'space=public-demo',
                    'X-Public': 'demo'}
        for away in ('other.example', 'example.com:8443'):
            with self.subTest(away=away):
                self.responses = [
                    Response(status=302, headers={'Location': '/same-origin'}),
                    Response(status=307, headers={'Location': f'https://{away}/away'}),
                    Response(status=308, headers={'Location': 'https://example.com/returned'}),
                    Response(status=302, headers={'Location': '/final'}),
                    Response(),
                ]
                result = self.fetch(headers=supplied)
                self.assertEqual((result['url'], result['text']), ('https://example.com/final', 'hello'))
                self.assertEqual([request[1]['headers'] for request in self.requests[-5:]], [
                    {**supplied, 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    {**supplied, 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    {'X-Public': 'demo', 'Host': away, 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    {'X-Public': 'demo', 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                    {'X-Public': 'demo', 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT},
                ])

    def test_credentialed_fetch_still_refuses_private_addresses_before_connect(self):
        supplied = {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo'}
        self.assertEqual(self.fetch(headers=supplied)['text'], 'hello')
        self.assertEqual(len(self.requests), 1)
        for url, addresses in (('https://127.0.0.1/data', [PUBLIC]),
                               ('https://[::1]/data', [PUBLIC]),
                               ('https://example.com/data', ['10.0.0.1']),
                               ('https://example.com/data', [PUBLIC, '192.168.1.1'])):
            with self.subTest(url=url, addresses=addresses):
                self.resolver.return_value = addresses
                error = self.error('blocked', self.fetch, url, headers=supplied)
                self.assertEqual(error['reason'], 'private_address')
                self.assertEqual(len(self.connections), 1)
                self.assertEqual(len(self.requests), 1)

    def test_credentialed_redirect_rechecks_private_addresses(self):
        supplied = {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo'}
        for location, answers, allowed in (
                ('/next', [[PUBLIC], [PUBLIC]], True),
                ('https://127.0.0.1/next', [[PUBLIC]], False),
                ('/next', [[PUBLIC], ['10.0.0.1']], False),
                ('https://other.example/next', [[PUBLIC], [PUBLIC, '192.168.1.1']], False)):
            with self.subTest(location=location, answers=answers):
                self.resolver.side_effect = answers
                self.responses = [Response(status=302, headers={'Location': location}), Response()]
                before_connections, before_requests = len(self.connections), len(self.requests)
                if allowed:
                    self.assertEqual(self.fetch(headers=supplied)['text'], 'hello')
                else:
                    self.assertEqual(self.error('blocked', self.fetch, headers=supplied)['reason'], 'private_address')
                self.assertEqual(len(self.connections) - before_connections, 2 if allowed else 1)
                self.assertEqual(len(self.requests) - before_requests, 2 if allowed else 1)
                self.assertEqual(self.requests[before_requests][1]['headers'], {
                    **supplied, 'Host': 'example.com', 'Accept-Encoding': 'identity', 'User-Agent': self.net.USER_AGENT,
                })

    def test_credentialed_redirect_rechecks_grant_before_next_request(self):
        supplied = {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo'}
        for revoke in (False, True):
            with self.subTest(revoke=revoke):
                self.responses = [Response(status=302, headers={'Location': 'https://other.example/next'}),
                                  Response()]
                self.on_response = (lambda: grants.decide(self.sid, 'net', 'revoke')) if revoke else None
                before_connections, before_requests = len(self.connections), len(self.requests)
                if revoke:
                    self.error('not_granted', self.fetch, headers=supplied)
                else:
                    self.assertEqual(self.fetch(headers=supplied)['text'], 'hello')
                self.assertEqual(len(self.connections) - before_connections, 1 if revoke else 2)
                self.assertEqual(len(self.requests) - before_requests, 1 if revoke else 2)

    def test_credentialed_redirect_rechecks_session_before_next_request(self):
        supplied = {'Authorization': 'Bearer public-space-demo', 'Cookie': 'space=public-demo'}
        for close in (False, True):
            with self.subTest(close=close):
                session = sessions.open_session(self.sid)['session']
                self.responses = [Response(status=302, headers={'Location': 'https://other.example/next'}),
                                  Response()]
                self.on_response = (lambda: sessions.close_session(session)) if close else None
                before_connections, before_requests = len(self.connections), len(self.requests)
                reply = bridge.dispatch(self.sid, session, 'net.fetch', {
                    'url': 'https://example.com/start', 'headers': supplied,
                })
                if close:
                    self.assertEqual(reply['error']['code'], 'session_invalid')
                    self.assertNotIn('result', reply)
                else:
                    self.assertTrue(reply['ok'], reply)
                    self.assertEqual(reply['result']['text'], 'hello')
                self.assertEqual(len(self.connections) - before_connections, 1 if close else 2)
                self.assertEqual(len(self.requests) - before_requests, 1 if close else 2)
