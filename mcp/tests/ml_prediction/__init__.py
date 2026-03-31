"""
Tests for ML prediction tools.

Note that the PES models require PYG backend, while the property prediction 
models require DGL backend. However, MatGL can only use one backend per python 
process, so the tests will fail if running all tests together via: 
`pytest tests/ml_prediction/ -v`.

The solution is to run each test file separately, e.g.:
`pytest tests/ml_prediction/test_ml_relax_structure.py -v`
"""
