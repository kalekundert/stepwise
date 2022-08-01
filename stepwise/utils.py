#!/usr/bin/env python3

NO_DEFAULT = object()

def unanimous(
        items,
        default=NO_DEFAULT,
        err_empty=ValueError("empty iterable"),
        err_multiple=lambda v1, v2: ValueError(f"found multiple values: {v1!r}, {v2!r}"),
    ):
    it = iter(items)

    try:
        value = next(it)
    except StopIteration:
        if default is not NO_DEFAULT:
            return default
        else:
            raise err_empty

    for next_value in it:
        if next_value != value:
            raise err_multiple(value, next_value)

    return value

def repr_join(xs):
    return ', '.join(map(repr, xs))

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

class EmptyMemo:

    def __setitem__(self, key, value):
        pass

    def __contains__(self, key):
        return False

EMPTY_MEMO = EmptyMemo()

def get_memo(memo, func):
    if memo is None: return EMPTY_MEMO
    if memo is EMPTY_MEMO: return EMPTY_MEMO
    return memo.setdefault(func, {})

