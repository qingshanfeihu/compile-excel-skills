"""客户端异常。消息会原样交给模型，所以用英文、不含任何令牌或口令。"""


class ClientError(Exception):
    """可以直接告诉调用方的失败原因。"""


class NotLoggedIn(ClientError):
    pass


class ServerUnreachable(ClientError):
    pass
