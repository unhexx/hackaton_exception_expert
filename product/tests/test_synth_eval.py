"""Контракт SYNTH-EVAL: имена, слоты и сборщик шарда без тел шардов в git."""

from __future__ import annotations

import json
from pathlib import Path

import product
from product.matching.grade import load_template, score_attempt, select_template
from product.matching.simulate import _answers_adjacent
from product.matching.stems import catalog
from product.matching.synth_eval import (
    FIRST_FEMALE,
    FIRST_MALE,
    N,
    SEED,
    SHARD_SIZE,
    SURNAMES,
    answers_for,
    assign_slot,
    build_shard,
    extras_for_shard,
    forbidden_name,
    generate_chosen,
    load_shards,
    profile_id_for,
)

_NAMES = Path(product.__file__).resolve().parent / "matching" / "golden" / "synth_eval" / "names.json"

_GOLDEN_SLOTS = {
    0: {
        "shard": 1,
        "offset": 0,
        "t": 0,
        "k": 0,
        "template_id": "backend-junior-a",
        "claim_kind": "aligned",
        "persona": "competent",
        "true_grade": "junior",
    },
    216: {
        "shard": 1,
        "offset": 216,
        "t": 0,
        "k": 3,
        "template_id": "backend-junior-a",
        "claim_kind": "aligned",
        "persona": "competent",
        "true_grade": "junior",
    },
    249: {
        "shard": 1,
        "offset": 249,
        "t": 68,
        "k": 3,
        "template_id": "security-middle-c",
        "claim_kind": "stretch",
        "persona": "adjacent",
        "true_grade": "junior",
    },
    250: {
        "shard": 2,
        "offset": 0,
        "t": 0,
        "k": 0,
        "template_id": "backend-junior-a",
        "claim_kind": "aligned",
        "persona": "competent",
        "true_grade": "junior",
    },
    999: {
        "shard": 4,
        "offset": 249,
        "t": 71,
        "k": 3,
        "template_id": "security-senior-c",
        "claim_kind": "stretch",
        "persona": "adjacent",
        "true_grade": "middle",
    },
}


def _names() -> dict:
    return json.loads(_NAMES.read_text(encoding="utf-8"))


def test_names_json_has_unique_living_chosen():
    data = _names()
    assert data["seed"] == SEED
    assert data["first_male"] == FIRST_MALE
    assert data["first_female"] == FIRST_FEMALE
    assert data["surnames"] == SURNAMES
    assert len(data["first_male"]) == 40
    assert len(data["first_female"]) == 40
    assert len(data["surnames"]["m"]) == 40
    assert len(data["surnames"]["f"]) == 40
    chosen = data["chosen"]
    assert len(chosen) == 1000
    assert len(set(chosen)) == 1000
    assert all(isinstance(name, str) and " " in name for name in chosen)
    mocks = {
        "Иван Синтетиков",
        "Анна Синтетикова",
        "Мария Черновикова",
        "Пётр Черновой",
    }
    for name in chosen:
        assert not forbidden_name(name)
        assert name not in mocks


def test_generate_chosen_is_deterministic():
    data = _names()
    again = generate_chosen(data["first_male"], data["first_female"], data["surnames"], seed=data["seed"])
    assert again == data["chosen"]
    from_module = generate_chosen(FIRST_MALE, FIRST_FEMALE, SURNAMES, seed=SEED)
    assert from_module == data["chosen"]


def test_assign_slot_golden_tuples():
    for index, expected in _GOLDEN_SLOTS.items():
        slot = assign_slot(index)
        assert slot["index"] == index
        for key, value in expected.items():
            assert slot[key] == value, (index, key, slot[key], value)
    assert assign_slot(0)["t"] == 0
    assert assign_slot(999)["t"] == 71


def test_extras_for_shard_closed_form():
    assert extras_for_shard(1)[-1] == (68, 3)
    assert extras_for_shard(4)[-1] == (71, 3)
    for shard in range(1, 5):
        extras = extras_for_shard(shard)
        assert len(extras) == 34
        assert extras == sorted(extras)


def test_claim_kind_counts_on_thousand():
    kinds: dict[str, int] = {}
    personas: dict[str, int] = {}
    for index in range(N):
        slot = assign_slot(index)
        assert slot["k"] in {0, 1, 2, 3, 4}
        kinds[slot["claim_kind"]] = kinds.get(slot["claim_kind"], 0) + 1
        personas[slot["persona"]] = personas.get(slot["persona"], 0) + 1
    assert kinds == {"aligned": 898, "stretch": 54, "underclaim": 48}
    assert personas == {"competent": 642, "confirm": 304, "adjacent": 54}


def test_twenty_four_pairs_cover_letters():
    letters: dict[tuple[str, str], set[str]] = {}
    for index in range(N):
        slot = assign_slot(index)
        key = (slot["specialization"], slot["declared_grade"])
        letters.setdefault(key, set()).add(slot["letter"])
    assert len(letters) == 24
    for pair, seen in letters.items():
        assert seen == {"a", "b", "c"}, pair


def test_profile_id_ray_congruence():
    used_one: set[int] = set()
    pid_one = profile_id_for("backend", "junior", "a", used_one, 1)
    assert pid_one >= 10001
    assert pid_one % 4 == 1
    used_four: set[int] = set()
    pid_four = profile_id_for("backend", "junior", "a", used_four, 4)
    assert pid_four >= 10001
    assert pid_four % 4 == 0


def test_answers_for_not_constant_bca():
    triples = []
    for letter in "abc":
        template = load_template(f"backend-middle-{letter}")
        answers = answers_for(template, "competent", slot=0)
        assert answers == [question["correct"] for question in template["questions"]]
        triples.append(tuple(answers))
    assert set(triples) != {("b", "c", "a")}
    assert len(set(triples)) == 3


def test_adjacent_matches_simulate_on_catalog_template():
    template = catalog()[0]
    assert answers_for(template, "adjacent") == _answers_adjacent(template)


def test_load_shards_missing_is_ok():
    bundle = load_shards()
    assert bundle["n"] == len(bundle["profiles"])
    assert bundle["n"] in {0, 250, 500, 750, 1000}


def test_build_shard_one_in_tmp(tmp_path):
    chosen = _names()["chosen"]
    shard = build_shard(1, names=chosen[:SHARD_SIZE])
    (tmp_path / "shard-1.json").write_text(
        json.dumps(shard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert shard["n"] == 250
    assert len(shard["profiles"]) == 250
    assert len(shard["needs"]) == 3
    assert all(need["relevant_profile_ids"] == [] for need in shard["needs"])
    assert [need["id"] for need in shard["needs"]] == [
        "backend-middle",
        "frontend-middle",
        "mobile-middle",
    ]
    assert len(shard["template_pairs"]) == 6
    assert [pair["template_id"] for pair in shard["template_pairs"]] == [
        "backend-middle-a",
        "data-middle-a",
        "devops-middle-a",
        "frontend-middle-a",
        "mobile-middle-a",
        "security-middle-a",
    ]
    for pair in shard["template_pairs"]:
        assert pair["answers_repeat"] == pair["answers"]
    living = [row["display_name"] for row in shard["profiles"]]
    assert living == chosen[:SHARD_SIZE]
    for row in shard["profiles"]:
        assert select_template(row["profile_id"], row["specialization"], row["grade"], "v1") == row["template_id"]
        scored = score_attempt(load_template(row["template_id"]), row["answers"])
        assert scored["score"] == row["test_score"]
        assert scored["outcome"] == row["test_outcome"]
        assert scored["outcome"] == row["expected_outcome"]
        assert row["expected_category_id"] == f"{row['specialization']}:{row['declared_grade']}"
        assert row["profile_id"] >= 10001
        assert row["profile_id"] % 4 == 1
