"""
This is the main module for Selene.
"""
__all__ = ["sequences", "targets", "samplers", "utils",
           "predict", "interpret", "__version__"]
from .version import __version__
from .train_model import TrainModel
