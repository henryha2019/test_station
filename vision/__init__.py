"""PogoTest vision: dataset generation, training, evaluation, quantization.

The production inspector is a small INT8 CNN (train.py + quantize.py). Until a
trained model is present, the station falls back to the feature baseline in
synthimg.py so the whole pipeline is runnable end-to-end without TensorFlow.
"""
