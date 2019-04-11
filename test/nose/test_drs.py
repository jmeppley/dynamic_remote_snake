from jme.drs import *

def test_path_up_to_wildcard():
    " should return last full dir name before first bracket "
    assert path_up_to_wildcard('/mnt/server/volume/project/file.{suffix}') \
            == '/mnt/server/volume/project'
    assert path_up_to_wildcard('/path/to/data/{sample}/file.{type}.ext') \
            == '/path/to/data'
    assert path_up_to_wildcard('/simple/path/file.ext') \
            == '/simple/path/file.ext'

def test_apply_defaults():
    " make sure this works as intended "
    config = {
        "param_1": True,
        "param_2": False,
        "subset": {
            "param_1": True,
            "param_2": False,
        }
    }

    defaults = {"param_2": True, "param_3": True}
    apply_defaults(config, defaults)
    assert (config ==
            {
                "param_1": True,
                "param_2": False,
                "param_3": True,
                "subset": {
                    "param_1": True,
                    "param_2": False,
                }
            })

    defaults = {"subset":{"param_2": True, "param_3": True}}
    apply_defaults(config, defaults)
    assert (config ==
            {
                "param_1": True,
                "param_2": False,
                "param_3": True,
                "subset": {
                    "param_1": True,
                    "param_2": False,
                    "param_3": True,
                }
            })

