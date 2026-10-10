"""Симуляция: попытки, цепочка пересдач и показатели валидации.

Показатели соответствуют критерию оценки 2 ТЗ и требованиям Q&A:

| Эксперимент         | Что доказывает                         | Формулировка ТЗ / Q&A                       |
|---------------------|----------------------------------------|---------------------------------------------|
| accuracy            | итоговый грейд = истинный              | «соответствие эталонной разметке»           |
| retest              | грейд стабилен на другом варианте      | «стабильный грейд при повторном прохождении»|
| separation          | балл растёт с истинным уровнем         | «дискриминативность», «разделяющая сила»    |
| tricks              | уловки не проходят тест                | «устойчивость к распространению заданий»    |
| leakage             | утечка части банка почти не помогает   | то же                                       |
| items / exposure    | качество вопросов, расход банка        | «качество процедуры валидации»              |

Каждый эксперимент запускается на СВОЕЙ копии системы (свои счётчики показов
и история кандидатов), чтобы эксперименты не влияли друг на друга.
"""

from __future__ import annotations

import random
import statistics

from product.validation_sim import responders
from product.validation_sim.bank import BankIndex
from product.validation_sim.form import Exposure, History, assemble_form
from product.validation_sim.scale import GRADES, LOWER, grade_index, next_grade, prev_grade
from product.validation_sim.scoring import score_form

STRATEGIES = ("random", "always_b", "pattern_bca", "longest")
LEAK_SHARES = (0.0, 0.1, 0.3, 0.5)
PASS = ("confirm", "suggest_higher")


class NewSystem:
    """Новая механика: вариант по плану + оценка уровня θ."""

    name = "Новый тест (банк семейств, 12 вопросов, IRT)"

    def __init__(self, index: BankIndex, seed: int) -> None:
        self.index = index
        self.rng = random.Random(seed)
        self.exposure = Exposure()
        self.history: dict[str, History] = {}

    def _responder(self, strategy: str, theta: float, leaked: set[str] | None):
        if strategy == "honest":
            return responders.honest(theta)
        if strategy == "leaked":
            return responders.leaked(theta, leaked or set())
        return {
            "random": responders.random_guess,
            "always_b": responders.always_b,
            "pattern_bca": responders.pattern_bca,
            "longest": responders.longest,
        }[strategy]()

    def take(self, candidate: dict, grade: str, strategy: str = "honest",
             theta: float | None = None, leaked: set[str] | None = None) -> dict:
        history = self.history.setdefault(candidate["candidate_id"], History())
        form = assemble_form(self.index, candidate["specialization"], grade, self.rng, history, self.exposure)
        answer = self._responder(strategy, candidate["theta"] if theta is None else theta, leaked)
        answers = {item["item_id"]: answer(item, form["key"][item["item_id"]], self.rng)
                   for item in form["items"]}
        result = score_form(form, answers)
        # Для анализа качества вопросов берём семейство: варианты-изоморфы одной
        # темы показываются редко по отдельности, а семейство набирает статистику.
        result["items"] = [(item["family_id"], ok) for item, ok in zip(form["items"], result["correct"])]
        return result


def run_chain(system, candidate: dict, strategy: str = "honest") -> tuple[str | None, int]:
    """Путь кандидата по правилам ТЗ: тест на заявленный грейд, затем
    (при «suggest_higher») тест выше или (при провале) тест ниже — без
    принудительного понижения. Возвращает (итоговый грейд, число попыток).
    В продукте шаг вверх ограничен интервалом; в симуляции время не моделируется.
    """
    grade = candidate["declared_grade"]
    result = system.take(candidate, grade, strategy)
    attempts = 1
    if result["outcome"] in PASS:
        final = grade
        while result["outcome"] == "suggest_higher" and next_grade(grade):
            grade = next_grade(grade)
            result = system.take(candidate, grade, strategy)
            attempts += 1
            if result["outcome"] in PASS:
                final = grade
            else:
                break  # не сдал ступень выше — остаётся подтверждённый грейд
        return final, attempts
    while prev_grade(grade):
        grade = prev_grade(grade)
        result = system.take(candidate, grade, strategy)
        attempts += 1
        if result["outcome"] in PASS:
            return grade, attempts
    return None, attempts


def exp_accuracy_retest(make_system, candidates: list[dict]) -> dict:
    """Две независимые цепочки на одной системе: вторая — как пересдача
    (у нового теста история кандидата исключает уже виденные семейства)."""
    system = make_system()
    first, second, attempts = [], [], []
    item_log: list[tuple[str, bool, float]] = []
    for cand in candidates:
        final, n = run_chain(_LoggingSystem(system, item_log), cand)
        first.append(final)
        attempts.append(n)
    for cand in candidates:
        second.append(run_chain(system, cand)[0])
    confusion = {g: {h: 0 for h in (*GRADES, "none")} for g in GRADES}
    for cand, final in zip(candidates, first):
        confusion[cand["true_grade"]][final or "none"] += 1
    n = len(candidates)
    exact = sum(c["true_grade"] == f for c, f in zip(candidates, first))
    near = sum(abs(grade_index(c["true_grade"]) - grade_index(f)) <= 1 for c, f in zip(candidates, first))
    over = sum(grade_index(f) > grade_index(c["true_grade"]) for c, f in zip(candidates, first))
    same = sum(a == b for a, b in zip(first, second))
    by_grade = {}
    for grade in GRADES:
        group = [(c, f) for c, f in zip(candidates, first) if c["true_grade"] == grade]
        by_grade[grade] = round(100 * sum(c["true_grade"] == f for c, f in group) / max(1, len(group)), 1)
    return {
        "exact_pct": round(100 * exact / n, 1),
        "within1_pct": round(100 * near / n, 1),
        "overrated_pct": round(100 * over / n, 1),
        "retest_same_pct": round(100 * same / n, 1),
        "mean_attempts": round(statistics.mean(attempts), 2),
        "exact_by_true_grade": by_grade,
        "confusion": confusion,
        "_system": system,
        "_item_log": item_log,
    }


class _LoggingSystem:
    """Обёртка: записывает (вопрос, верно, процент остальных) для анализа вопросов."""

    def __init__(self, system, log: list) -> None:
        self.system, self.log = system, log

    def take(self, candidate, grade, strategy="honest", theta=None, leaked=None):
        result = self.system.take(candidate, grade, strategy, theta, leaked)
        flags = [ok for _id, ok in result["items"]]
        for item_id, ok in result["items"]:
            rest = (sum(flags) - ok) / (len(flags) - 1)
            self.log.append((item_id, ok, rest))
        return result


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    rx, ry = _ranks(x), _ranks(y)
    return round(statistics.correlation(rx, ry), 3)


def exp_separation(make_system, candidates: list[dict], level: str = "middle") -> dict:
    """Все кандидаты проходят тест одного уровня (middle): насколько балл
    различает истинные грейды. Cohen's d — разрыв средних соседних грейдов в
    единицах разброса; > 0.8 считается большим эффектом."""
    system = make_system()
    scores = {g: [] for g in GRADES}
    thetas, percents = [], []
    for cand in candidates:
        result = system.take(cand, level)
        scores[cand["true_grade"]].append(result["percent"])
        thetas.append(cand["theta"])
        percents.append(result["percent"])
    summary = {}
    for grade in GRADES:
        values = scores[grade]
        summary[grade] = {
            "mean": round(statistics.mean(values), 1),
            "sd": round(statistics.pstdev(values), 1),
            "n": len(values),
        }
    cohen = {}
    for low, high in zip(GRADES, GRADES[1:]):
        a, b = scores[low], scores[high]
        pooled = ((statistics.pvariance(a) + statistics.pvariance(b)) / 2) ** 0.5 or 1.0
        cohen[f"{low}->{high}"] = round((statistics.mean(b) - statistics.mean(a)) / pooled, 2)
    distinct = len(set(percents))
    return {
        "level": level,
        "by_true_grade": summary,
        "cohen_d": cohen,
        "spearman_theta_percent": spearman(thetas, percents),
        "distinct_scores": distinct,
    }


def exp_tricks(make_system, candidates: list[dict], strategies=STRATEGIES) -> dict:
    """Каждая уловка — 500 попыток на заявленный грейд. Доля «сдал» (confirm
    или выше). Для сравнения — честные кандидаты."""
    # Эталон: какая доля ДОЛЖНА сдать — истинный уровень не ниже заявленного грейда.
    ideal = sum(c["theta"] >= LOWER[c["declared_grade"]] for c in candidates)
    out = {"ideal_pass_pct": round(100 * ideal / len(candidates), 1)}
    for strategy in ("honest", *strategies):
        system = make_system()
        passed, percents = 0, []
        for cand in candidates:
            result = system.take(cand, cand["declared_grade"], strategy)
            passed += result["outcome"] in PASS
            percents.append(result["percent"])
        out[strategy] = {
            "pass_pct": round(100 * passed / len(candidates), 1),
            "mean_percent": round(statistics.mean(percents), 1),
        }
    return out


def exp_leakage(make_system, candidates: list[dict], universe: list[str], seed: int,
                shares=LEAK_SHARES) -> dict:
    """Кандидат идёт на ступень ВЫШЕ своего истинного грейда (где должен
    провалиться), но знает ответы на долю ``share`` банка. Насколько растёт
    доля «сдал»? ``universe`` — что может утечь: варианты (новый тест) или
    шаблоны (текущий тест)."""
    rng = random.Random(seed)
    targets = [c for c in candidates if next_grade(c["true_grade"])]
    out = {}
    for share in shares:
        leaked = set(rng.sample(universe, int(round(share * len(universe)))))
        system = make_system()
        passed = 0
        for cand in targets:
            result = system.take(cand, next_grade(cand["true_grade"]), "leaked", leaked=leaked)
            passed += result["outcome"] in PASS
        out[f"{share:.1f}"] = round(100 * passed / len(targets), 1)
    return {"pass_pct_by_share": out, "n": len(targets)}


def exp_key_known(make_system, candidates: list[dict]) -> float:
    """Текущий тест: кандидат знает ключ b-c-a и идёт на ступень выше истинной."""
    system = make_system()
    targets = [c for c in candidates if next_grade(c["true_grade"])]
    passed = sum(
        system.take(c, next_grade(c["true_grade"]), "pattern_bca")["outcome"] in PASS for c in targets
    )
    return round(100 * passed / len(targets), 1)


def item_analysis(item_log: list[tuple[str, bool, float]], min_n: int = 15) -> dict:
    """Скорректированная корреляция «вопрос — остальной тест» (point-biserial).
    Ниже 0.15 — вопрос плохо различает кандидатов, его надо пересмотреть."""
    by_item: dict[str, list[tuple[bool, float]]] = {}
    for item_id, ok, rest in item_log:
        by_item.setdefault(item_id, []).append((ok, rest))
    values = []
    weak = []
    for item_id, rows in by_item.items():
        if len(rows) < min_n:
            continue
        xs = [float(ok) for ok, _ in rows]
        ys = [rest for _, rest in rows]
        if len(set(xs)) < 2 or len(set(ys)) < 2:
            continue
        r = statistics.correlation(xs, ys)
        values.append(r)
        if r < 0.15:
            weak.append(item_id)
    return {
        "items_analysed": len(values),
        "mean_rpb": round(statistics.mean(values), 3) if values else None,
        "weak_items_pct": round(100 * len(weak) / max(1, len(values)), 1),
        "_weak": sorted(weak),
    }


def exposure_stats(system: NewSystem, total_variants: int) -> dict:
    counts = list(system.exposure.variants.values())
    return {
        "variants_used_pct": round(100 * len(counts) / total_variants, 1),
        "max_shows": max(counts),
        "mean_shows": round(statistics.mean(counts), 1),
    }


def longest_is_correct_share(index: BankIndex) -> dict:
    """Проверка текстов: как часто верный ответ — самый длинный.
    Для выбора из трёх «нейтральная» доля — 33%. Выше — тексты подсказывают ответ."""
    from product.validation_sim.baseline import _grade_module

    def share(questions: list[tuple[list[str], int]]) -> float:
        hits = sum(max(range(len(opts)), key=lambda i: len(opts[i])) == ci for opts, ci in questions)
        return round(100 * hits / max(1, len(questions)), 1)

    new = [
        (f["sample"]["options"], f["sample"]["correct_index"])
        for f in index.bank["families"]
        if f["type"] == "single" and f.get("sample")
    ]
    old = []
    for template in _grade_module()._catalog():
        for q in template["questions"]:
            ids = [c["id"] for c in q["choices"]]
            old.append(([c["text"] for c in q["choices"]], ids.index(q["correct"])))
    return {"old_pct": share(old), "new_single_samples_pct": share(new)}
