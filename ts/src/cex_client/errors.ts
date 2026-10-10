export class ClientError extends Error {}

export class NotLoggedIn extends ClientError {}

export class ServerUnreachable extends ClientError {}
