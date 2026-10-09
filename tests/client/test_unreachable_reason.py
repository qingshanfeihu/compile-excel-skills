"""连不上服务端时报出原因与处理办法（中文）：证书不受信任要指到连接串（和 SSL_CERT_FILE），
证书里没有这个地址要让管理员重新签发，拒绝连接、超时、域名解析失败各有一句；地址里没写端口时
提示默认端口 8900。别的网络故障带上系统给的原因，不再只有一个异常类名。"""

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
    failure.verify_code = 20
    monkeypatch.setattr(auth._OPENER, "open", _raising(urllib.error.URLError(failure)))
    with pytest.raises(ServerUnreachable) as caught:
        auth.http("GET", "https://ces.example.test/v1/client_config")
    text = str(caught.value)
    assert "证书不受信任" in text and "unable to get local issuer certificate" in text
    assert "连接串" in text and "SSL_CERT_FILE" in text


def test_a_certificate_without_this_address_asks_for_a_reissue(monkeypatch):
    failure = ssl.SSLCertVerificationError(1, "certificate verify failed")
    failure.verify_message = "IP address mismatch, certificate is not valid for '10.9.8.7'."
    failure.verify_code = 64
    monkeypatch.setattr(auth._OPENER, "open", _raising(urllib.error.URLError(failure)))
    with pytest.raises(ServerUnreachable) as caught:
        auth.http("GET", "https://10.9.8.7:8900/healthz")
    text = str(caught.value)
    assert "证书里没有这个地址（10.9.8.7）" in text and "重新签发" in text


def test_refused_timeout_and_dns_failures_say_what_to_check(monkeypatch):
    refused = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
    monkeypatch.setattr(auth._OPENER, "open", _raising(refused))
    with pytest.raises(ServerUnreachable) as caught:
        auth.http("GET", "https://ces.example.test:8900/healthz")
    assert "拒绝连接" in str(caught.value) and "没写端口" not in str(caught.value)
    with pytest.raises(ServerUnreachable) as caught:
        auth.http("GET", "http://172.16.2.90/healthz")
    text = str(caught.value)
    assert "拒绝连接" in text and "地址里没写端口" in text and "https://172.16.2.90:8900" in text

    monkeypatch.setattr(auth._OPENER, "open", _raising(TimeoutError("timed out")))
    with pytest.raises(ServerUnreachable, match="连接超时"):
        auth.http("GET", "https://ces.example.test:8900/healthz")
    unknown = urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided"))
    monkeypatch.setattr(auth._OPENER, "open", _raising(unknown))
    with pytest.raises(ServerUnreachable, match="找不到主机 ces.example.test"):
        auth.http("GET", "https://ces.example.test:8900/healthz")


def test_other_failures_carry_the_system_reason(monkeypatch):
    odd = urllib.error.URLError(OSError(5, "Input/output error"))
    monkeypatch.setattr(auth._OPENER, "open", _raising(odd))
    with pytest.raises(ServerUnreachable, match=r"OSError: .*Input/output error"):
        auth.http("GET", "https://ces.example.test/healthz")
