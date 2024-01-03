# tests/test_imports.py
import sys
import os

# Append the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#def test_import_prosumer_model():
#    import ProsumerModel as pyp
#    assert True  # Example assertion
#
#def test_import_consumer_model(): 
#    import ConsumerModel as pyc
#    assert True


def test_other_impports():
    import numpy as np
    import pandas as pd
    from pathlib import Path
    import Pyomo
    import os
    import pprint
    import functions
    import parametri
    import warnings
    import json
    assert True
