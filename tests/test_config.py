#!/usr/bin/env python3

import pytest
from stepwise import Presets, StepwiseConfig, PresetConfig
from byoc.errors import Log
from more_itertools import one, flatten
from operator import attrgetter
from param_helpers import *

class MockObj:
    pass

# test rootkey?

@parametrize_from_file(
        schema=[
            cast(
                plugins=Schema({str: [with_py.exec(get='MockPlugin')]}),
                config_factory=with_sw.exec(get='MockConfig'),
                obj=with_sw.fork(MockObj=MockObj).exec(get='obj'),
                expected=with_py.eval,
            ),
            defaults(
                plugins={},
                config_factory=StepwiseConfig,
                obj=MockObj(),
            ),
        ],
)
def test_stepwise_config(files, appdirs, plugins, config_factory, obj, expected, config_paths, tmp_path, monkeypatch):
    import appdirs as appdirs_module
    import entrypoints

    # Create the indicated files:

    for name, contents in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    # Monkeypatch `appdirs`:

    class AppDirs:

        def __init__(self, slug, author, version):
            self.slug = slug
            self.author = author
            self.version = version

            self.user_config_dir = appdirs['user_dir']
            self.site_config_dir = appdirs['site_dir']

    monkeypatch.setattr(appdirs_module, 'AppDirs', AppDirs)

    # Monkeypatch `entrypoints`:

    class MockEntryPoint:

        def __init__(self, plugin):
            self.name = plugin.config_path.split('/')[0]
            self.plugin = plugin

        def load(self):
            return self.plugin

    def get_group_all(group, path=None):
        return map(MockEntryPoint, plugins.get(group, []))

    monkeypatch.setattr(entrypoints, 'get_group_all', get_group_all)

    # Monkeypatch `os.cwd`:

    monkeypatch.chdir(tmp_path)

    # Run the test:

    config = config_factory(obj)

    for key, values in expected.items():
        actual = flatten(
                layer.iter_values(key, Log())
                for layer in config.load()
        )
        assert list(actual) == values

    assert list(config.config_paths) == [Path(x) for x in config_paths]
    
@parametrize_from_file(
        schema=[
            cast(
                config_factory=with_sw.fork(attrgetter=attrgetter).exec(
                    get='MockConfig',
                ),
                obj=with_sw.fork(MockObj=MockObj).exec(get='obj'),
                key=with_py.eval,
                expected=with_py.eval,
            ),
            defaults(
                config_factory=PresetConfig,
                briefs='',
            ),
        ],
)
def test_preset_config(config_factory, obj, key, expected, briefs):
    config = config_factory(obj)
    layer = one(config.load())
    values = layer.iter_values(key, Log())

    assert list(values) == expected

    if briefs:
        assert config.preset_briefs == briefs

@parametrize_from_file
def test_presets(presets, expected):
    p = Presets(presets)

    assert set(p) == set(expected)

    for k, v in expected.items():
        assert p[k] == v

@parametrize_from_file(
        schema=cast(key=with_py.eval, error=with_sw.error),
)
def test_presets_err(presets, key, error):
    p = Presets(presets)
    with error:
        p[key]
       




