"""MCP Package initialization.

Ensures official third-party `mcp` library from site-packages is included in `__path__`
and re-exports all public definitions so that third-party tools (like FastMCP)
can resolve `mcp` symbols without collision.
"""

import os
import sys

_site_init = None
for _p in sys.path:
    if "site-packages" in _p:
        _site_mcp = os.path.join(_p, "mcp")
        if os.path.isdir(_site_mcp):
            if _site_mcp not in __path__:
                __path__.insert(0, _site_mcp)
            _init_file = os.path.join(_site_mcp, "__init__.py")
            if os.path.isfile(_init_file):
                _site_init = _init_file
            break

if _site_init:
    with open(_site_init, encoding="utf-8") as _f:
        _code = _f.read()
    exec(_code, globals())
