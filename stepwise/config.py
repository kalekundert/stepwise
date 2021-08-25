#!/usr/bin/env python3

import sys
import appcli
import autoprop

from .format import tabulate
from .utils import load_plugins, sort_plugins
from appcli import TomlConfig, unbind_method
from more_itertools import only, flatten, unique_everseen

class StepwiseCommand:
    brief = appcli.config_attr()
    dirs = appcli.config_attr()
    usage_io = sys.stderr

    def __init__(self):
        self.quiet = False
        self.force_text = False

@autoprop
class StepwiseConfig(appcli.Config):
    schema = None
    root_key = None

    def __init__(self, obj, root_key=None, *, schema=None):
        super().__init__(obj)

        self.schema = schema or unbind_method(self.schema)
        self.root_key = root_key or self.root_key

        self.app_dirs = appcli.AppDirsConfig(obj)
        self.app_dirs.name = 'conf.toml'
        self.app_dirs.slug = 'stepwise'
        self.app_dirs.schema = self.schema
        self.app_dirs.root_key = self.root_key

    def load(self):
        yield from self.load_app_dirs()
        yield from self.load_plugins()

    def load_app_dirs(self):
        yield from self.app_dirs.load()

    def load_plugins(self):
        plugins = sort_plugins([
                *load_plugins('stepwise.protocols'),
                *load_plugins('stepwise.commands', default_priority=1),
        ])
        for plugin in plugins:
            try: path = plugin.config_path
            except AttributeError: continue


            yield from TomlConfig.load_from_path(
                    path,
                    schema=self.schema,
                    root_key=self.root_key,
            )

    def get_dirs(self):
        return self.app_dirs.dirs

    def get_config_paths(self):
        return self.app_dirs.config_paths

@autoprop
class PresetConfig(appcli.Config):
    """
    The presets should be a list of dicts.  If loading the presets using 
    appcli, you can do this by specifying `pick=list`.
    """
    presets_getter = lambda obj: obj.presets
    key_getter = lambda obj: obj.preset
    schema = None

    class Layer(appcli.Layer):

        def __init__(self, presets_getter, key_getter, schema=None):
            self.presets_getter = presets_getter
            self.key_getter = key_getter
            self.schema = schema

        def iter_values(self, key, log):
            layer_1 = appcli.DictLayer(self.presets_getter())
            preset = only(layer_1.iter_values(self.key_getter(), log))

            if preset is not None:
                layer_2 = appcli.DictLayer(preset, schema=self.schema)
                yield from layer_2.iter_values(key, log)

    def __init__(self, obj, presets_getter=None, key_getter=None, schema=None):
        super().__init__(obj)

        self.presets_getter = presets_getter or unbind_method(self.presets_getter)
        self.key_getter = key_getter or unbind_method(self.key_getter)
        self.schema = schema or self.schema
        self._presets = None

    def load(self):
        # `preset_getter`:
        #   Evaluated the first time a preset is accessed after a load/reload.  
        #
        # `key_getter`:
        #   Evaluated every time the parameter is accessed.

        self._presets = None
        yield self.Layer(
                presets_getter=self.get_presets,
                key_getter=lambda: self.key_getter(self.obj),
                schema=self.schema,
        )

    def get_presets(self):
        if self._presets is None:
            raw_presets = self.presets_getter(self.obj)
            self._presets = Presets(raw_presets)

        return self._presets

    def get_preset_briefs(self):
        presets = self.presets
        default = getattr(self.obj, 'preset_brief_template', '')
        max_width = getattr(self.obj, 'preset_brief_max_width', 71)

        rows = []
        for key in presets:
            preset = presets[key]
            rows.append([
                    f'{key}:',
                    preset.get('brief', default.format(**preset)),
            ])

        return tabulate(rows, truncate='-x', max_width=max_width)

class Presets:

    def __init__(self, layers):
        self.layers = list(layers)  # List[Dict]
        self.loaded_presets = {}

    def __iter__(self):
        yield from unique_everseen(flatten(self.layers))

    def __getitem__(self, key):
        try: return self.loaded_presets[key]
        except KeyError: pass

        try:
            preset = load_preset(key, self.layers)
        except KeyError as err:
            known_presets = list(self)
            if known_presets:
                from inform import did_you_mean
                raise KeyError(f"{err.args[0]}, did you mean {did_you_mean(str(key), self)!r}?") from None
            else:
                raise

        self.loaded_presets[key] = preset
        return preset

def load_preset(key, layers):
    for i, layer in enumerate(layers):
        if key not in layer:
            continue

        preset = layer[key]

        if 'inherit' not in preset:
            return preset

        parent_key = preset['inherit']

        if parent_key == key:
            layers = layers[:]
            layers[i] = layer.copy()
            del layers[i][key]

        parent_preset = load_preset(parent_key, layers)

        merged = {**parent_preset, **preset}
        del merged['inherit']
        return merged

    raise KeyError(f"no preset {key!r}")

config_dirs = StepwiseConfig(None).dirs
