"""Модель ответа на вопрос и оценка уровня кандидата (IRT, трёхпараметрическая).

Зачем IRT, а не «процент верных»: варианты теста у кандидатов разные
(защита от утечки, ТЗ §2), и процент на лёгком и на трудном варианте нельзя
сравнивать напрямую. IRT учитывает сложность каждого вопроса и даёт уровень θ
на общей шкале — сравнение кандидатов становится честным.

Параметры вопроса:
    a — различающая сила: насколько резко растёт вероятность успеха с уровнем;
    b — сложность: уровень θ, на котором кандидат решает вопрос «наполовину»;
    c — вероятность угадать (1/3 для выбора из трёх, ~0.03 для множественного выбора).

В реальном продукте a и b оцениваются по пилоту (калибровка), здесь они
заданы в банке, а «настоящие» значения отличаются от заявленных случайным
сдвигом — см. ``responders.true_params``. Так симуляция учитывает ошибку калибровки.
"""

from __future__ import annotations

import math

D = 1.7  # стандартный масштабный множитель логистической модели

# Сетка уровней для численной оценки θ. Шаг 0.05 даёт точность много выше
# ширины грейда (1.2), а считается быстро на CPU без numpy.
GRID: tuple[float, ...] = tuple(round(-4.0 + 0.05 * i, 2) for i in range(181))  # -4 .. 5


def p_correct(theta: float, a: float, b: float, c: float) -> float:
    """Вероятность верного ответа кандидата уровня theta на вопрос (a, b, c)."""
    return c + (1.0 - c) / (1.0 + math.exp(-D * a * (theta - b)))


def estimate_theta(
    responses: list[tuple[float, float, float, bool]],
    prior_mean: float = 0.6,
    prior_sd: float = 1.5,
) -> tuple[float, float]:
    """Оценка уровня по ответам: среднее апостериорного распределения (EAP).

    responses — список (a, b, c, верно_ли). Априорное распределение широкое
    (sd 1.5 при ширине грейда 1.2) и лишь стабилизирует оценку при 0 или 100%
    верных; на итог при 12 вопросах влияет слабо.

    Возвращает (θ, стандартная ошибка θ).
    """
    logs = []
    for theta in GRID:
        z = (theta - prior_mean) / prior_sd
        total = -0.5 * z * z
        for a, b, c, correct in responses:
            p = p_correct(theta, a, b, c)
            p = min(max(p, 1e-9), 1 - 1e-9)
            total += math.log(p if correct else 1.0 - p)
        logs.append(total)
    peak = max(logs)
    weights = [math.exp(value - peak) for value in logs]
    norm = sum(weights)
    mean = sum(t * w for t, w in zip(GRID, weights)) / norm
    var = sum((t - mean) ** 2 * w for t, w in zip(GRID, weights)) / norm
    return mean, math.sqrt(var)


# ---------------------------------------------------------------------------
# Апостериорное распределение уровня: нужно для «результата с уверенностью»
# и для накопления информации между попытками (план улучшений, п. 1 и 3).
# ---------------------------------------------------------------------------


def prior_weights(prior_mean: float = 0.6, prior_sd: float = 1.5) -> list[float]:
    """Стартовое (априорное) распределение уровня на сетке GRID."""
    weights = [math.exp(-0.5 * ((t - prior_mean) / prior_sd) ** 2) for t in GRID]
    norm = sum(weights)
    return [w / norm for w in weights]


def update(weights: list[float], responses: list[tuple[float, float, float, bool]]) -> list[float]:
    """Байесовское обновление: прошлое распределение × правдоподобие новых ответов.

    Если ``weights`` — итог прошлой попытки, новая попытка не начинает с нуля,
    а уточняет уже известное. Так две короткие сессии дают точность одной длинной.
    """
    logs = []
    for theta, w in zip(GRID, weights):
        total = math.log(max(w, 1e-300))
        for a, b, c, correct in responses:
            p = min(max(p_correct(theta, a, b, c), 1e-9), 1 - 1e-9)
            total += math.log(p if correct else 1.0 - p)
        logs.append(total)
    peak = max(logs)
    out = [math.exp(v - peak) for v in logs]
    norm = sum(out)
    return [v / norm for v in out]


def summary(weights: list[float]) -> tuple[float, float]:
    """Среднее и стандартное отклонение распределения: (θ, погрешность θ)."""
    mean = sum(t * w for t, w in zip(GRID, weights))
    var = sum((t - mean) ** 2 * w for t, w in zip(GRID, weights))
    return mean, math.sqrt(var)


def prob_at_least(weights: list[float], bound: float) -> float:
    """Вероятность того, что истинный уровень не ниже ``bound``."""
    return sum(w for t, w in zip(GRID, weights) if t >= bound)
