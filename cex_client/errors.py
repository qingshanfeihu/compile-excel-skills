"""客户端异常。消息会原样交给模型，不含任何令牌或口令。连接、初始化、登录这条路径上的消息用中文
并带处理办法（新手第一次用时直接看到，模型原样转述）；其余用英文。"""


class ClientError(Exception):
    """可以直接告诉调用方的失败原因。"""


class NotLoggedIn(ClientError):
    pass


class ServerUnreachable(ClientError):
    pass
