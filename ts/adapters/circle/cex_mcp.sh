#!/bin/sh
CDPATH= cd -- "$(dirname -- "$0")"
exec "${CEX_NODE:-node}" "$(dirname -- "$0")/../../dist/bin/cex_mcp_proxy.js" "$@"
