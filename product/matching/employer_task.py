"""Короткое задание работодателя. Не испытание грейда и не пишет балл.

ТЗ §2.1 «Регулярные задания: короткая задача от работодателя» (желательно для MVP).
"""

from __future__ import annotations

MAX_ANSWER = 2000


def answer_accepted(prompt: str, answer: str) -> bool:
    task = str(prompt or "").strip()
    text = str(answer or "").strip()
    if not task or not text or len(text) > MAX_ANSWER:
        return False
    return True
