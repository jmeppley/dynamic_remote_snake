from jme.dynamic_remote_snake.remote import *

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

