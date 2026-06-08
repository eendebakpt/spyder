# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Lazy imports configuration for Spyder (PEP 810).

This module provides a filter function for use with Python 3.15+'s
`-X lazy_imports=all` mode. It excludes modules that have important
import-time side effects from being lazily imported.

Usage:
    # Early in startup (e.g. in start.py):
    from spyder.app.lazy_imports_filter import install_filter
    install_filter()
"""

import sys

# Modules that MUST be imported eagerly because they have important
# import-time side effects or initialization requirements.
EAGER_MODULES = frozenset({
    # ZMQ must be imported early to prevent race conditions
    # See spyder-ide/spyder#5324
    "zmq",

    # typing uses __getattr__ for deprecated aliases (Match, Pattern, etc.)
    # which breaks under deferred resolution
    "typing",

    # Qt framework modules need proper initialization order
    # - sip API version settings
    # - QApplication not existing when widgets are created
    # - DLL loading on Windows
    "sip",
    "sipbuild",
    "PyQt5",

    # qtpy sets the Qt binding at import time
    "qtpy",

    # Modules that register plugins/hooks at import time
    "pkg_resources",
    "setuptools",

    # Modules with __init__ side effects that Spyder depends on
    "spyder.requirements",  # check_qt() runs at import

    # watchdog accesses submodules as attributes (watchdog.utils.BaseThread)
    # which requires eager import of the package hierarchy
    "watchdog",

    # pygments has circular imports between submodules that break under
    # lazy resolution (e.g. pygments.lexers.Python3Lexer)
    "pygments",
})

# Module prefixes that should always be imported eagerly.
# These match any module whose fully-qualified name starts with the prefix.
EAGER_PREFIXES = (
    "PyQt5.",
    "sip",
    "qtpy.",
    "zmq.",
    "typing.",
    "watchdog.",
    "pygments.",
)


def _lazy_imports_filter(importer, name, fromlist):
    """
    Filter function for sys.set_lazy_imports_filter().

    Returns True if the import should remain lazy, False to force eager.
    Modules with critical side effects are forced eager.
    """
    if name in EAGER_MODULES:
        return False
    for prefix in EAGER_PREFIXES:
        if name.startswith(prefix):
            return False
    return True


def install_filter():
    """Install the lazy imports filter if lazy imports are active."""
    if hasattr(sys, 'get_lazy_imports') and sys.get_lazy_imports() == "all":
        sys.set_lazy_imports_filter(_lazy_imports_filter)


# Auto-install when this module is imported
install_filter()
