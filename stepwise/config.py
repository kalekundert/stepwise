#!/usr/bin/env python3

import sys
import appcli

class StepwiseCommand:
    brief = appcli.config_attr()
    dirs = appcli.config_attr()
    usage_io = sys.stderr

    def __init__(self):
        self.quiet = False
        self.force_text = False

class StepwiseConfig(appcli.AppDirsConfig):

    def __init__(self):
        super().__init__('conf.toml', slug='stepwise')

class PresetConfig(appcli.CallbackConfig):

    def __init__(self, presets='presets', name='preset', **kwargs):

        def getter(obj):
            values = getattr(obj, presets) 
            key = getattr(obj, name)
            return values[key]

        def location(obj):
            loc = f'{obj.__class__.__qualname__}.{presets}'

            try:
                key = getattr(obj, name)
                loc += f'[{key!r}]'
            except AttributeError:
                pass

            return loc

        super().__init__(getter, AttributeError, location=location)

config_dirs = StepwiseConfig().get_dirs(None)

