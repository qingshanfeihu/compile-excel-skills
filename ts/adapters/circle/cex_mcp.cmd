@echo off
if "%CEX_NODE%"=="" set CEX_NODE=node
"%CEX_NODE%" "%~dp0..\..\dist\bin\cex_mcp_proxy.js" %*
