"""Генерация данных: банк вопросов и синтетические кандидаты.

Запуск из корня репозитория:

    python -m product.validation_sim.generate            # 500 кандидатов, seed 2026
    python -m product.validation_sim.generate --n 1000 --seed 7

Пишет ``product/validation_sim/data/{bank.json, candidates.json, candidates.csv, pilot.json, pilot_live.json}``.
Тот же seed даёт те же файлы — результат воспроизводим.

ТЗ §2: «команда работает на собственных данных, синтетических…»; ТЗ §3.4 «процедура валидации».
"""

from __future__ import annotations

import argparse

from product.validation_sim import adaptive, bank, candidates


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Банк вопросов и синтетические кандидаты")
    parser.add_argument("--n", type=int, default=500, help="число кандидатов")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    built = bank.build_bank(seed=args.seed)
    path = bank.save_bank(built)
    variants = sum(len(f["variants"]) for f in built["families"])
    print(f"bank: {len(built['families'])} семейств, {variants} вариантов -> {path}")

    rows = candidates.generate(n=args.n, seed=args.seed)
    candidates.save(rows, seed=args.seed)
    print(f"candidates: {len(rows)} -> {candidates.CSV_PATH} и {candidates.JSON_PATH}")

    # Пилот на отдельной группе (seed 7): слабые семейства и порог «уверенно».
    # Два варианта банка: со всеми форматами (прогноз) и тот, что работает в кабинете.
    for view, target in ((built, adaptive.PILOT_PATH), (bank.live_view(built), adaptive.PILOT_LIVE_PATH)):
        pilot = adaptive.run_pilot(bank.BankIndex(view))
        path = adaptive.save_pilot(pilot, target)
        print(f"pilot: выведено {len(pilot['retired'])} семейств, порог «уверенно» "
              f"{pilot['confident_threshold']} -> {path}")


if __name__ == "__main__":
    main()
