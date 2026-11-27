"""Gaussian naive Bayes over physically measured slope, moisture and rut depth."""

from math import exp, log, pi
from statistics import fmean, pvariance

from .states import TrialResult

FEATURES = ('slope_pct', 'moisture_pct', 'rut_mm')
MIN_CLASS_ROWS = 4
MIN_CLEAR = 0.8
# Floors use each instrument's approximate measurement variance.
VARIANCE_FLOORS = (0.04, 1.0, 0.25)


class InsufficientLabels(ValueError):
    pass


def predict(training, probe):
    counts, log_scores = {}, {}
    for label in TrialResult:
        group = [row for row in training if row['observed_result'] == label]
        if len(group) < MIN_CLASS_ROWS:
            raise InsufficientLabels('通行和受阻各需要至少 4 条已判读测验。')
        counts[label] = len(group)
        score = log(len(group) / len(training))
        for name, floor in zip(FEATURES, VARIANCE_FLOORS, strict=True):
            values = [float(row[name]) for row in group]
            variance = max(pvariance(values), floor)
            difference = float(probe[name]) - fmean(values)
            score -= 0.5 * (log(2 * pi * variance) + difference ** 2 / variance)
        log_scores[label] = score
    normalizer = max(log_scores.values())
    weights = {label: exp(score - normalizer) for label, score in log_scores.items()}
    probability = weights[TrialResult.CLEAR] / sum(weights.values())
    return {
        'predicted_result': TrialResult.CLEAR if probability >= MIN_CLEAR else TrialResult.STUCK,
        'clear_probability': round(probability, 6),
        'sample_count': sum(counts.values()),
    }
