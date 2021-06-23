#!/usr/bin/env python3

def load_plugins(group, default_priority=None):
    from entrypoints import get_group_all

    for entry_point in get_group_all(group):
        plugin = entry_point.load()
        plugin.entry_point = entry_point

        if not hasattr(plugin, 'priority') and default_priority is not None:
            setattr(plugin, 'priority', default_priority)

        yield plugin

def sort_plugins(plugins):
    return sorted(
            plugins,
            key=lambda x: getattr(x, 'priority'),
            reverse=True,
    )

def load_and_sort_plugins(group, default_priority=None):
    return sort_plugins(load_plugins(group, default_priority))

