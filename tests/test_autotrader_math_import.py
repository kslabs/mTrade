def test_autotrader_module_has_math():
    import autotrader
    assert hasattr(autotrader, 'math'), "autotrader.py should import math at module level"
