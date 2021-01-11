#!/usr/bin/env python3

import sys
import appcli
from .table import tabulate

class StepwiseCommand:
    brief = appcli.config_attr()
    dirs = appcli.config_attr()
    usage_io = sys.stderr

    def __init__(self):
        self.quiet = False
        self.force_text = False

class StepwiseConfig(appcli.Config):

    def __init__(self, root_key=None):
        self.app_dirs = appcli.AppDirsConfig('conf.toml', slug='stepwise')
        self.root_key = root_key

    def load(self, obj):
        yield from self.load_app_dirs(obj)
        yield from self.load_plugins(obj)

    def load_app_dirs(self, obj):
        yield from (
                self.normalize_layer(x)
                for x in self.app_dirs.load(obj)
        )

    def load_plugins(self, obj):
        from entrypoints import get_group_all
        plugins = [
                *get_group_all('stepwise.protocols'),
                *get_group_all('stepwise.commands'),
        ]

        for plugin in plugins:
            try: path = plugin.load().config_defaults
            except AttributeError: continue

            config = appcli.TomlConfig(path)
            yield from (
                    self.normalize_layer(x, prefix=plugin.name)
                    for x in config.load(obj)
            )

    def normalize_layer(self, layer, prefix=None):
        if prefix:
            layer.values = {prefix: layer.values}
        if self.root_key:
            try:
                layer.values = appcli.lookup(layer.values, self.root_key)
            except KeyError:
                layer.values = {}

        return layer

    def get_dirs(self, obj):
        return self.app_dirs.get_dirs(obj)

class PresetConfig(appcli.Config):

    def __init__(self, presets_attr='presets', key_attr='preset'):
        self.presets_attr = presets_attr
        self.key_attr = key_attr
        self._presets = None

    def load(self, obj):
        # Note that the `obj.presets` attribute is evaluated when this config 
        # is loaded, so subsequent changes to this attribute will have no 
        # effect.  If this is a problem, you can either: (i) make sure this 
        # config is loaded after `obj.presets` has its final value, or (ii) 
        # implement `appcli.reload()` and use it every time `obj.presets` 
        # changes.
        #
        # In contrast, the `obj.preset` attribute is queried every time the 
        # parameter is accessed, so changes to that attribute will be 
        # automatically applied.
        
        presets = self.get_presets(obj)
        yield appcli.Layer(
                values=lambda k: presets[getattr(obj, self.key_attr)][k],
                location=lambda: f'{obj.__class__.__qualname__}.{self.presets_attr}[{getattr(obj, self.key_attr)!r}]'
        )

    def get_presets(self, obj):
        if self._presets:
            return self._presets
        else:
            raw_presets = getattr(obj, self.presets_attr)
            self._presets = Presets(raw_presets)
            return self._presets

    def get_preset_briefs(self, obj):
        presets = self.get_presets(obj)
        default = getattr(obj, 'preset_brief_template', '')
        max_width = getattr(obj, 'preset_brief_max_width', 71)

        rows = []
        for key in presets:
            preset = presets[key]
            rows.append([
                    f'{key}:',
                    preset.get('brief', default.format(**preset)),
            ])

        return tabulate(rows, truncate='-x', max_width=max_width)

class Presets:

    def __init__(self, presets):
        self.raw_presets = presets
        self.final_presets = {}

    def __iter__(self):
        yield from self.raw_presets

    def __getitem__(self, key):
        try:
            return self.final_presets[key]
        except KeyError:
            pass

        try:
            preset = self.raw_presets[key]
        except KeyError:
            if not self.raw_presets:
                raise KeyError(f"no preset {key!r}") from None
            else:
                from inform import did_you_mean
                raise KeyError(f"no preset {key!r}, did you mean {did_you_mean(str(key), self)!r}") from None

        if 'inherit' not in preset:
            self.final_presets[key] = preset
            return preset
        else:
            parent = self[preset['inherit']]
            merged = {**parent, **preset}; del merged['inherit']
            self.final_presets[key] = merged
            return merged

config_dirs = StepwiseConfig().get_dirs(None)
