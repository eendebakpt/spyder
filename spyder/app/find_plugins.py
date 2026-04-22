# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)
"""
Plugin dependency solver.
"""

import importlib
import logging
import sys
import traceback

from spyder.api.exceptions import SpyderAPIError
from spyder.api.plugins import Plugins
from spyder.api.utils import get_class_values
from spyder.config.base import STDERR

# See compatibility note on `group` keyword:
# https://docs.python.org/3/library/importlib.metadata.html#entry-points
if sys.version_info < (3, 10):  # pragma: no cover
    from importlib_metadata import entry_points
else:  # pragma: no cover
    from importlib.metadata import entry_points


logger = logging.getLogger(__name__)

# Plugins whose module import is deferred until after the main window is
# visible.  They are not in any other plugin's REQUIRES list, so deferring
# them does not block the window from rendering.  Adding a plugin here is
# enough to opt it in; no changes to the plugin class are needed.
DEFERRED_PLUGINS = frozenset({
    # Heavy importers first (import cost in a real startup context)
    "debugger",          # ~2075 ms, pulls in 757 new modules
    "pylint",            # ~354 ms
    "appearance",        # ~448 ms (APP_STYLESHEET already applied by setup())
    # Medium importers
    "help",              # ~61 ms
    "project_explorer",  # ~34 ms
    "update_manager",    # ~11 ms
    "remoteclient",      # ~12 ms
    "find_in_files",     # ~10 ms
    # Fast but still deferrable tool/panel plugins
    "tours",
    "variable_explorer",
    "historylog",
    "explorer",
    "plots",
    "profiler",
    "external_terminal",
    "onlinehelp",
    "outline_explorer",
})


class _LazyPluginClass:
    """
    Proxy for a Spyder plugin class that defers the module import.

    Only :attr:`NAME` and :attr:`LAZY_LOAD` are accessible without triggering
    the actual ``importlib.import_module`` call.  Any other attribute access
    (or calling the proxy as a constructor) resolves the real class first.

    This lets :func:`find_internal_plugins` return all plugin entries without
    importing their modules, so the heavy imports are paid only when each
    plugin is actually instantiated.
    """

    def __init__(self, entry_point, deferred: bool = False):
        # Stored directly so __getattr__ is never invoked for these two.
        self.NAME = entry_point.name
        self.LAZY_LOAD = deferred
        self._ep = entry_point
        self._cls = None

    # ------------------------------------------------------------------
    def _resolve(self):
        """Import the plugin module and return the real class."""
        if self._cls is None:
            mod = importlib.import_module(self._ep.module)
            self._cls = getattr(mod, self._ep.attr)
        return self._cls

    # Proxy all other attribute lookups to the real class.
    def __getattr__(self, name):
        return getattr(self._resolve(), name)

    # Allow the proxy to be used as a constructor: PluginClass(parent, ...)
    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __repr__(self):
        resolved = " [resolved]" if self._cls is not None else ""
        lazy = " [deferred]" if self.LAZY_LOAD else ""
        return f"<_LazyPluginClass {self.NAME!r}{lazy}{resolved}>"


def find_internal_plugins():
    """
    Find internal plugins based on setuptools entry points.

    Returns a mapping of plugin name → :class:`_LazyPluginClass` proxy.
    Module imports are deferred until each proxy is first used, so that
    heavy plugin modules are not all imported at startup.
    """
    internal_plugins = {}

    internal_names = get_class_values(Plugins)

    for entry_point in entry_points(group="spyder.plugins"):
        name = entry_point.name
        if name not in internal_names:
            continue

        deferred = name in DEFERRED_PLUGINS
        internal_plugins[name] = _LazyPluginClass(entry_point, deferred)

    # FIXME: This shouldn't be necessary but it's just to be sure
    # plugins are sorted in alphabetical order. We need to remove it
    # in a later version.
    internal_plugins = {
        key: value for key, value in sorted(internal_plugins.items())
    }

    return internal_plugins


def find_external_plugins():
    """
    Find available external plugins based on setuptools entry points.
    """
    internal_names = get_class_values(Plugins)
    external_plugins = {}

    for entry_point in entry_points(group="spyder.plugins"):
        name = entry_point.name
        if name not in internal_names:
            try:
                class_name = entry_point.attr
                mod = importlib.import_module(entry_point.module)
                plugin_class = getattr(mod, class_name, None)

                # To display in dependencies dialog.
                plugin_class._spyder_module_name = entry_point.module
                plugin_class._spyder_package_name = entry_point.dist.name
                plugin_class._spyder_version = entry_point.dist.version

                external_plugins[name] = plugin_class
                if name != plugin_class.NAME:
                    raise SpyderAPIError(
                        "Entry point name '{0}' and plugin.NAME '{1}' "
                        "do not match!".format(name, plugin_class.NAME)
                    )
            except Exception as error:
                # We catch any error here to avoid Spyder to crash at startup
                # due to faulty or outdated plugins.
                print("%s: %s" % (name, str(error)), file=STDERR)
                traceback.print_exc(file=STDERR)

    return external_plugins
