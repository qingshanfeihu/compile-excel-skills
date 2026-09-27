"""连不上服务端时报出原因：证书不受信任（宿主进程没带组织 CA）要直说，并指到 SSL_CERT_FILE；
别的网络故障带上系统给的原因，不再只有一个异常类名。"""

from __future__ import annotations

import socket
import ssl
import urllib.error

import pytest

from cex_client import auth
from cex_client.errors import ServerUnreachable


def _raising(exc: BaseException):
    def open_(*_args, **_kwargs):
        raise exc
    return open_


def test_an_untrusted_certificate_is_named_with_the_fix(monkeypatch):
    failure = ssl.SSLCertVerificationError(1, "certificate verify failed")
    failure.verify_message = "unable to get local issuer certificate"
    monkeypatch.setattr(auth._OPENER, "open", _raising(urllib.error.URLError(failure)))
    with pytest.raises(ServerUnreachable) as caught:
        auth.http("GET", "https://ces.example.test/v1/client_config")
    text = str(caught.value)
    assert "TLS certificate not trusted" in text
    assert "unable to get local issuer certificate" in text
    assert "SSL_CERT_FILE" in text


def test_other_failures_carry_the_system_reason(monkeypatch):
    refused = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
    monkeypatch.setattr(auth._OPENER, "open", _raising(refused))
    with pytest.raises(ServerUnreachable, match="URLError: .*Connection refused"):
        auth.http("GET", "https://ces.example.test/healthz")
    monkeypatch.setattr(auth._OPENER, "open", _raising(socket.timeout("timed out")))
    with pytest.raises(ServerUnreachable, match=r"\(TimeoutError: timed out\)|\(timeout: timed out\)"):
        auth.http("GET", "https://ces.example.test/healthz")
