import numpy as np

from vision.synthimg import CLASSES, classify_features, render


def test_render_shape_and_dtype():
    img = render("OK", (96, 96), np.random.default_rng(0))
    assert img.shape == (96, 96, 3)
    assert img.dtype == np.uint8


def test_taxonomy_is_servo():
    assert CLASSES == ["OK", "horn_missing", "case_defect", "foreign_object"]


def test_ok_is_confident():
    rng = np.random.default_rng(1)
    poks = []
    for _ in range(20):
        _, probs = classify_features(render("OK", (96, 96), rng))
        poks.append(probs["OK"])
    assert np.mean(poks) > 0.6


def test_baseline_accuracy_per_class():
    rng = np.random.default_rng(2)
    for cls in CLASSES:
        correct = 0
        for _ in range(25):
            pred, _ = classify_features(render(cls, (96, 96), rng))
            correct += int(pred == cls)
        assert correct / 25 >= 0.7, f"{cls} accuracy too low: {correct}/25"
