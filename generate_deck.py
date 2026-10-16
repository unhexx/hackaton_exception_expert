#!/usr/bin/env python3
"""
Generate high-aesthetic FSP brandbook-compliant hackathon presentation for SpecTrack.
Target file: product/docs/prezentaciya.pptx
Total slides: 21
"""

import os
import sys
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# Color Palette (FSP Brandbook & SpecTrack dark theme)
C_DARK_BG       = RGBColor(0x1C, 0x1D, 0x22) # Primary dark canvas #1C1D22
C_CARD_BG       = RGBColor(0x25, 0x1C, 0x35) # Card background #251C35
C_CARD_BG2      = RGBColor(0x1F, 0x1B, 0x2B) # Secondary card bg #1F1B2B
C_CARD_BORDER   = RGBColor(0x3E, 0x2E, 0x54) # Subtle purple border #3E2E54
C_CARD_BORDER_HI= RGBColor(0x5A, 0x43, 0x78) # Highlighted card border
C_PINK          = RGBColor(0xFF, 0x00, 0x53) # Brand primary accent #FF0053
C_PINK_LIGHT    = RGBColor(0xFF, 0xD6, 0xE4) # Light soft pink #FFD6E4
C_LAVENDER      = RGBColor(0x8A, 0x83, 0xD1) # Lavender accent #8A83D1
C_GREEN         = RGBColor(0x52, 0xD9, 0x78) # Verified / success green #52D978
C_TEXT_WHITE    = RGBColor(0xFF, 0xFF, 0xFF) # Pure white text #FFFFFF
C_TEXT_MUTED    = RGBColor(0xAC, 0xA7, 0xBA) # Soft muted text #ACA7BA
C_TEXT_BODY     = RGBColor(0xE4, 0xE1, 0xED) # High contrast body text #E4E1ED

FONT_TITLE = "Montserrat"
FONT_BODY  = "Montserrat"
FONT_CODE  = "JetBrains Mono"

# Assets paths
ASSET_LOGO_WHITE = "brandbook-fsp/logo_white1.png"
ASSET_LOGO_FSP   = "product/docs/pitch/logo-fsp.png"
ASSET_LINE       = "brandbook-fsp/lineline1.png"
PITCH_DIR        = "product/docs/pitch"


def set_bg(slide, prs):
    """Fill slide with dark base color."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = C_DARK_BG


def add_header(slide, tag_text, title_text, subtitle_text=None):
    """Standardized branded header across all content slides."""
    # Tag / pill badge
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.40), Inches(7.0), Inches(0.32))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = tag_text.upper()
    p_tag.font.name = FONT_CODE
    p_tag.font.size = Pt(9.5)
    p_tag.font.bold = True
    p_tag.font.color.rgb = C_PINK

    # Slide Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.68), Inches(10.5), Inches(0.55))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.name = FONT_TITLE
    p_title.font.size = Pt(21)
    p_title.font.bold = True
    p_title.font.color.rgb = C_TEXT_WHITE

    # Slide Subtitle
    if subtitle_text:
        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.22), Inches(10.5), Inches(0.35))
        tf_sub = sub_box.text_frame
        tf_sub.word_wrap = True
        tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle_text
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(10.5)
        p_sub.font.color.rgb = C_TEXT_MUTED

    # Top right logo badge
    if os.path.exists(ASSET_LOGO_FSP):
        slide.shapes.add_picture(ASSET_LOGO_FSP, Inches(11.3), Inches(0.42), width=Inches(1.25))


def add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_CARD_BORDER):
    """Draw rounded rectangle card surface."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg_color
    if border_color:
        card.line.color.rgb = border_color
        card.line.width = Pt(1.2)
    else:
        card.line.fill.background()
    return card


def add_bullet_item(tf, bold_prefix, text_rest, bullet_color=C_PINK, font_size=10.5, space_after=5):
    """Add a bullet item to text frame with bold prefix."""
    p = tf.add_paragraph() if tf.paragraphs and tf.paragraphs[0].text else tf.paragraphs[0]
    p.space_after = Pt(space_after)
    
    r_b = p.add_run()
    r_b.text = "• "
    r_b.font.name = FONT_BODY
    r_b.font.size = Pt(font_size)
    r_b.font.bold = True
    r_b.font.color.rgb = bullet_color
    
    if bold_prefix:
        r_pre = p.add_run()
        r_pre.text = bold_prefix + " "
        r_pre.font.name = FONT_BODY
        r_pre.font.size = Pt(font_size)
        r_pre.font.bold = True
        r_pre.font.color.rgb = C_TEXT_WHITE
        
    r_rest = p.add_run()
    r_rest.text = text_rest
    r_rest.font.name = FONT_BODY
    r_rest.font.size = Pt(font_size)
    r_rest.font.color.rgb = C_TEXT_BODY


def add_stat_card(slide, left, top, width, height, stat_value, title, subtitle="", accent_color=C_PINK):
    """Big metric stat box."""
    add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_CARD_BORDER)
    
    # Accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left + Inches(0.2), top + Inches(0.18), Inches(0.4), Inches(0.04))
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent_color
    bar.line.fill.background()

    tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.25), width - Inches(0.4), height - Inches(0.35))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    
    p_val = tf.paragraphs[0]
    p_val.text = stat_value
    p_val.font.name = FONT_CODE
    p_val.font.size = Pt(24)
    p_val.font.bold = True
    p_val.font.color.rgb = accent_color
    p_val.space_after = Pt(4)
    
    p_title = tf.add_paragraph()
    p_title.text = title
    p_title.font.name = FONT_BODY
    p_title.font.size = Pt(11)
    p_title.font.bold = True
    p_title.font.color.rgb = C_TEXT_WHITE
    p_title.space_after = Pt(2)
    
    if subtitle:
        p_sub = tf.add_paragraph()
        p_sub.text = subtitle
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(9.5)
        p_sub.font.color.rgb = C_TEXT_MUTED


def add_framed_screenshot(slide, left, top, width, height, img_path, title, caption=None, badge_text="ЭКРАН"):
    """Screenshot placed inside clean card with title and caption."""
    add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_CARD_BORDER)
    
    # Header bar inside card
    header_box = slide.shapes.add_textbox(left + Inches(0.18), top + Inches(0.12), width - Inches(0.36), Inches(0.4))
    tf_h = header_box.text_frame
    tf_h.word_wrap = True
    tf_h.margin_left = tf_h.margin_top = tf_h.margin_right = tf_h.margin_bottom = 0
    p_h = tf_h.paragraphs[0]
    
    r_badge = p_h.add_run()
    r_badge.text = f"[{badge_text}] "
    r_badge.font.name = FONT_CODE
    r_badge.font.size = Pt(9.5)
    r_badge.font.bold = True
    r_badge.font.color.rgb = C_PINK
    
    r_title = p_h.add_run()
    r_title.text = title
    r_title.font.name = FONT_BODY
    r_title.font.size = Pt(11)
    r_title.font.bold = True
    r_title.font.color.rgb = C_TEXT_WHITE
    
    # Image frame
    img_top = top + Inches(0.55)
    img_height = height - Inches(1.05 if caption else 0.65)
    img_left = left + Inches(0.18)
    img_width = width - Inches(0.36)
    
    if os.path.exists(img_path):
        slide.shapes.add_picture(img_path, img_left, img_top, width=img_width, height=img_height)
        
    # Caption
    if caption:
        cap_box = slide.shapes.add_textbox(left + Inches(0.18), top + height - Inches(0.46), width - Inches(0.36), Inches(0.38))
        tf_c = cap_box.text_frame
        tf_c.word_wrap = True
        tf_c.margin_left = tf_c.margin_top = tf_c.margin_right = tf_c.margin_bottom = 0
        p_c = tf_c.paragraphs[0]
        p_c.text = caption
        p_c.font.name = FONT_BODY
        p_c.font.size = Pt(9.5)
        p_c.font.color.rgb = C_TEXT_MUTED


# ==============================================================================
# SLIDE BUILDERS (21 SLIDES)
# ==============================================================================

def build_slide_1(prs):
    """Slide 1: Hero / Title Slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)

    # Decorative wave line from FSP brandbook
    if os.path.exists(ASSET_LINE):
        slide.shapes.add_picture(ASSET_LINE, Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))

    # Top Brand Logo
    if os.path.exists(ASSET_LOGO_WHITE):
        slide.shapes.add_picture(ASSET_LOGO_WHITE, Inches(0.8), Inches(0.65), width=Inches(2.8))

    # Top Pill
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(4.5), Inches(0.35))
    pill.fill.solid()
    pill.fill.fore_color.rgb = C_CARD_BG
    pill.line.color.rgb = C_PINK
    pill.line.width = Pt(1)
    tf_p = pill.text_frame
    p_p = tf_p.paragraphs[0]
    p_p.text = "ФЕДЕРАЦИЯ СПОРТИВНОГО ПРОГРАММИРОВАНИЯ • СПЕЦТРЭК 2026"
    p_p.font.name = FONT_CODE
    p_p.font.size = Pt(8.5)
    p_p.font.bold = True
    p_p.font.color.rgb = C_PINK

    # Main Hero Title
    tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(11.5), Inches(1.6))
    tf_t = tb_title.text_frame
    tf_t.word_wrap = True
    p_t = tf_t.paragraphs[0]
    p_t.text = "SPECTRACK"
    p_t.font.name = FONT_TITLE
    p_t.font.size = Pt(46)
    p_t.font.bold = True
    p_t.font.color.rgb = C_TEXT_WHITE
    p_t.space_after = Pt(6)

    p_sub = tf_t.add_paragraph()
    p_sub.text = "Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений ФСП и адаптивным подтверждением квалификации"
    p_sub.font.name = FONT_BODY
    p_sub.font.size = Pt(14)
    p_sub.font.color.rgb = C_TEXT_MUTED

    # 4 Key Stats Cards
    stats_data = [
        ("92.7%", "Точность грейда", "со статусом «уверенно», 0% ошибок > 1 ступени", C_PINK),
        ("38 / 38", "Золотой набор", "100% совпадение целевых категорий в golden run", C_LAVENDER),
        ("100% Offline", "Zero-Cloud архитектура", "FastAPI + SQLite WAL, локальный htmx, без CDN", C_GREEN),
        ("31 API / 125 тестов", "Качество и готовность", "OpenAPI спецификация, прогон тестов прямо на стенде", C_PINK)
    ]
    card_w = Inches(2.78)
    card_h = Inches(1.85)
    card_y = Inches(3.85)
    for i, (val, title, desc, acc) in enumerate(stats_data):
        cx = Inches(0.8) + i * Inches(2.98)
        add_stat_card(slide, cx, card_y, card_w, card_h, val, title, desc, acc)

    # Bottom Team Credits Card
    bot_card = add_card(slide, Inches(0.8), Inches(5.95), Inches(11.733), Inches(0.9), bg_color=C_CARD_BG2, border_color=C_CARD_BORDER)
    tb_b = slide.shapes.add_textbox(Inches(1.0), Inches(6.05), Inches(11.3), Inches(0.7))
    tf_b = tb_b.text_frame
    tf_b.word_wrap = True
    p_b1 = tf_b.paragraphs[0]
    p_b1.text = "КОМАНДА РАЗРАБОТКИ:"
    p_b1.font.name = FONT_CODE
    p_b1.font.size = Pt(9.5)
    p_b1.font.bold = True
    p_b1.font.color.rgb = C_LAVENDER
    p_b1.space_after = Pt(2)

    p_b2 = tf_b.add_paragraph()
    p_b2.text = "Чистяков Евгений (капитан) • Иван Курлыков • Леонид Пластуненко • Николай Кузнецов • Игорь Софронов | Контакт: echistyakov@aq.ru"
    p_b2.font.name = FONT_BODY
    p_b2.font.size = Pt(10.5)
    p_b2.font.bold = True
    p_b2.font.color.rgb = C_TEXT_WHITE


def build_slide_2(prs):
    """Slide 2: Problem & Market Gap."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Проблема и Концепция", "Разрыв рынка найма: хаос откликов против верификации", "Почему классические джоб-борды не работают для соискателей и работодателей")

    card_w = Inches(3.75)
    card_h = Inches(5.35)
    top_y = Inches(1.65)

    # Card 1: Боль кандидата
    c1 = add_card(slide, Inches(0.8), top_y, card_w, card_h)
    tb1 = slide.shapes.add_textbox(Inches(1.0), top_y + Inches(0.25), card_w - Inches(0.4), card_h - Inches(0.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "БОЛЬ КАНДИДАТА"
    p1.font.name = FONT_CODE
    p1.font.size = Pt(13)
    p1.font.bold = True
    p1.font.color.rgb = C_PINK
    p1.space_after = Pt(12)

    add_bullet_item(tf1, "Слепые отклики:", "Сотни резюме отправляются в пустоту без понятной обратной связи и критериев отбора.")
    add_bullet_item(tf1, "Скрытые зарплаты:", "Работодатели прячут вилки («по результатам собеседования»), отнимая время кандидатов.")
    add_bullet_item(tf1, "Субъективный скрининг:", "Оценка навыков часто зависит от настроения рекрутера, а не реальной инженерной квалификации.")
    add_bullet_item(tf1, "Игнорирование ФСП:", "Спортивные достижения и разряды не учитываются традиционными HR-системами.")

    # Card 2: Боль работодателя
    c2 = add_card(slide, Inches(4.8), top_y, card_w, card_h)
    tb2 = slide.shapes.add_textbox(Inches(5.0), top_y + Inches(0.25), card_w - Inches(0.4), card_h - Inches(0.5))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "БОЛЬ РАБОТОДАТЕЛЯ"
    p2.font.name = FONT_CODE
    p2.font.size = Pt(13)
    p2.font.bold = True
    p2.font.color.rgb = C_LAVENDER
    p2.space_after = Pt(12)

    add_bullet_item(tf2, "Лавина нерелевантного спама:", "Сотни неподходящих откликов на каждую открытую вакансию блокируют работу HR.")
    add_bullet_item(tf2, "Недостоверные резюме:", "Завышенные грейды в резюме вскрываются только на дорогостоящих технических интервью.")
    add_bullet_item(tf2, "Колоссальные затраты:", "Десятки часов Senior-инженеров тратятся на отсев кандидатов со слабым базовым уровнем.")
    add_bullet_item(tf2, "Отсутствие единой метрики:", "Нет стандартизированного инструмента быстрой независимой валидации грейда.")

    # Card 3: Решение SpecTrack
    c3 = add_card(slide, Inches(8.8), top_y, card_w, card_h, bg_color=C_CARD_BG2, border_color=C_PINK)
    tb3 = slide.shapes.add_textbox(Inches(9.0), top_y + Inches(0.25), card_w - Inches(0.4), card_h - Inches(0.5))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    p3 = tf3.paragraphs[0]
    p3.text = "РЕШЕНИЕ SPECTRACK"
    p3.font.name = FONT_CODE
    p3.font.size = Pt(13)
    p3.font.bold = True
    p3.font.color.rgb = C_GREEN
    p3.space_after = Pt(12)

    add_bullet_item(tf3, "Обратная механика:", "Кандидат не спамит откликами. Работодатель сам находит профиль по верифицированной категории.", C_GREEN)
    add_bullet_item(tf3, "Прозрачные вилки:", "Работодатель обязан указать обе границы вилки в рублях в первом же сообщении.", C_GREEN)
    add_bullet_item(tf3, "Адаптивный IRT-тест:", "12 вопросов единого плана валидируют реальный грейд с надежностью 92.7% без зубрежки.", C_GREEN)
    add_bullet_item(tf3, "Реестр достижений ФСП:", "Прямой учет спортивных разрядов и турнирных баллов Федерации спортивного программирования.", C_GREEN)


def build_slide_3(prs):
    """Slide 3: Team & Roles."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Команда Проекта", "Состав команды и зоны инженерной ответственности", "Слаженная работа 5 специалистов: от математического моделирования до продакшн-стенда")

    top1 = Inches(1.65)
    h1 = Inches(2.55)
    w3 = Inches(3.75)

    team_members = [
        ("Евгений Чистяков", "Капитан команды • Архитектура • Продукт", "echistyakov@aq.ru",
         ["Общая архитектура монолита и проектирование сервисов", "Разработка ядра подбора и правил категоризации", "Взаимодействие с оргкомитетом и защита проекта"], C_PINK),
        ("Иван Курлыков", "Алгоритмы ранжирования • Математика", "Разработка",
         ["Многофакторный алгоритм скоринга потребности evaluate_need", "Интеграция стемминга русской и английской морфологии", "Нормализация стеков технологий и синонимов"], C_LAVENDER),
        ("Леонид Пластуненко", "Движок тестирования • Адаптивный IRT", "Разработка",
         ["Реализация механики 12 вопросов единого плана 3/6/3", "Алгоритм адаптивного добора блоков на границе грейда", "Генерация одноразовых ID вариантов и защита от утечек"], C_LAVENDER),
    ]

    for i, (name, role, email_or_tag, tasks, acc) in enumerate(team_members):
        cx = Inches(0.8) + i * Inches(4.0)
        c = add_card(slide, cx, top1, w3, h1)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), top1 + Inches(0.18), w3 - Inches(0.4), h1 - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        p_n = tf.paragraphs[0]
        p_n.text = name
        p_n.font.name = FONT_TITLE
        p_n.font.size = Pt(13)
        p_n.font.bold = True
        p_n.font.color.rgb = C_TEXT_WHITE
        p_n.space_after = Pt(2)

        p_r = tf.add_paragraph()
        p_r.text = role
        p_r.font.name = FONT_CODE
        p_r.font.size = Pt(9.0)
        p_r.font.bold = True
        p_r.font.color.rgb = acc
        p_r.space_after = Pt(6)

        for task in tasks:
            add_bullet_item(tf, "", task, bullet_color=acc, font_size=9.5, space_after=3)

    top2 = Inches(4.45)
    h2 = Inches(2.55)
    w2 = Inches(5.75)

    team_row2 = [
        ("Николай Кузнецов", "Fullstack разработка • Web UI & Security", "Разработка",
         ["Разработка серверных шаблонов Jinja2 и реактивного htmx без CDN", "Безопасность: сессии, хэширование Argon2, шторка контактов 152-ФЗ", "Отображение воронки статусов sent -> seen -> accepted"], C_LAVENDER),
        ("Игорь Софронов", "Валидация • Golden Run • Стенд и DevOps", "Тестирование & DevOps",
         ["Подготовка стенда Docker Compose (uvicorn в одном процессе)", "Разработка Golden Run набора из 38 профилей и симуляции 500 кандидатов", "Обеспечение 100% offline-режима без обращения к внешней сети"], C_GREEN)
    ]

    for i, (name, role, email_or_tag, tasks, acc) in enumerate(team_row2):
        cx = Inches(0.8) + i * Inches(6.0)
        c = add_card(slide, cx, top2, w2, h2)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), top2 + Inches(0.18), w2 - Inches(0.4), h2 - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        p_n = tf.paragraphs[0]
        p_n.text = name
        p_n.font.name = FONT_TITLE
        p_n.font.size = Pt(13)
        p_n.font.bold = True
        p_n.font.color.rgb = C_TEXT_WHITE
        p_n.space_after = Pt(2)

        p_r = tf.add_paragraph()
        p_r.text = role
        p_r.font.name = FONT_CODE
        p_r.font.size = Pt(9.0)
        p_r.font.bold = True
        p_r.font.color.rgb = acc
        p_r.space_after = Pt(6)

        for task in tasks:
            add_bullet_item(tf, "", task, bullet_color=acc, font_size=9.5, space_after=3)


def build_slide_4(prs):
    """Slide 4: Key Engineering Challenges."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Инженерные Вызовы", "С какими основными сложностями столкнулись и как преодолели", "Строгое следование ТЗ: решение краевых случаев и архитектурных ограничений")

    grid_w = Inches(5.75)
    grid_h = Inches(2.55)
    top1 = Inches(1.65)
    top2 = Inches(4.45)

    challenges = [
        ("ВЫЗОВ 01: СИНТЕЗ КАТЕГОРИИ",
         "Категория складывается из специализации и подтвержденного грейда (напр. backend:middle). Отрасль MVP зафиксирована в IT и в ID не входит.",
         "Резюме PDF парсится pypdf и нормализуется словарем синонимов, но после прохождения теста PDF не может затереть подтвержденный грейд.",
         C_PINK),
        ("ВЫЗОВ 02: ОБЯЗАТЕЛЬНЫЕ РУБЛЕВЫЕ ВИЛКИ",
         "Работодатели часто избегают указания четких финансовых условий на ранних этапах, что порождает неэффективные отклики.",
         "Форма приглашения валидирует обе границы: нижняя и верхняя строго в RUB (верхняя > нижней). Без вилки оффер сохранить невозможно.",
         C_LAVENDER),
        ("ВЫЗОВ 03: КОРРЕКТНАЯ ПУСТАЯ ИСТОРИЯ ФСП",
         "У большинства ИТ-специалистов на начальном этапе отсутствуют официальные спортивные разряды и история соревнований ФСП.",
         "Стенд обрабатывает отсутствие истории ФСП как нормальное штатное состояние. Интерфейс не падает, а чисто отображает пустой реестр.",
         C_GREEN),
        ("ВЫЗОВ 04: ЗАЩИТА ПЕРСОНАЛЬНЫХ ДАННЫХ (152-ФЗ)",
         "Необходимость дать работодателю полную информацию для отбора без риска утечки прямых контактов соискателя.",
         "Шторка контактов: почта соискателя скрыта и отдается только после взаимного accept. 3 гибких чекбокса приватности (ФИО, стаж, ФСП).",
         C_PINK)
    ]

    for i, (title, problem, solution, acc) in enumerate(challenges):
        col = i % 2
        row = i // 2
        cx = Inches(0.8) + col * Inches(6.0)
        cy = top1 if row == 0 else top2

        add_card(slide, cx, cy, grid_w, grid_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.22), cy + Inches(0.18), grid_w - Inches(0.44), grid_h - Inches(0.36))
        tf = tb.text_frame
        tf.word_wrap = True

        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.name = FONT_CODE
        p_t.font.size = Pt(11)
        p_t.font.bold = True
        p_t.font.color.rgb = acc
        p_t.space_after = Pt(6)

        add_bullet_item(tf, "Проблема:", problem, bullet_color=acc, font_size=10, space_after=4)
        add_bullet_item(tf, "Решение:", solution, bullet_color=C_TEXT_WHITE, font_size=10, space_after=2)


def build_slide_5(prs):
    """Slide 5: Reverse Mechanics & 3 Visibility Rules."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Обратная Механика", "Смена парадигмы: инициатива у работодателя, а не соискателя", "ТЗ §2: Соискатель не тратит недели на спам откликов — работодатель отбирает подтвержденные анкеты")

    # Top Flow banner
    top_banner = add_card(slide, Inches(0.8), Inches(1.65), Inches(11.733), Inches(1.3), bg_color=C_CARD_BG2, border_color=C_LAVENDER)
    tb_flow = slide.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(11.333), Inches(1.1))
    tf_f = tb_flow.text_frame
    tf_f.word_wrap = True
    p_f0 = tf_f.paragraphs[0]
    p_f0.text = "СКВОЗНОЙ ПРОЦЕСС ОБРАТНОЙ МЕХАНИКИ:"
    p_f0.font.name = FONT_CODE
    p_f0.font.size = Pt(10)
    p_f0.font.bold = True
    p_f0.font.color.rgb = C_PINK
    p_f0.space_after = Pt(4)

    p_f1 = tf_f.add_paragraph()
    p_f1.text = "1. Соискатель подтверждает грейд тестом  ➔  2. Система синтезирует категорию и ранг  ➔  3. Работодатель формирует потребность  ➔  4. Оффер с обязательной RUB вилкой  ➔  5. Контакты открываются после согласия"
    p_f1.font.name = FONT_BODY
    p_f1.font.size = Pt(10.5)
    p_f1.font.bold = True
    p_f1.font.color.rgb = C_TEXT_WHITE

    # 3 Visibility rules cards
    card_w = Inches(3.75)
    card_h = Inches(3.85)
    card_y = Inches(3.15)

    rules = [
        ("ПРАВИЛО 1: УПРАВЛЕНИЕ ПРИВАТНОСТЬЮ",
         "Согласие на публикацию",
         [
             "Кандидат управляет видимостью профиля одной главной кнопкой публикации.",
             "3 независимые настройки: скрыть ФИО, скрыть стаж, скрыть достижения ФСП.",
             "Если галка снята — в карточке подборки отдается пустая строка, но ранжирование сохраняется.",
             "Снятие публикации полностью исключает соискателя из поисковой выдачи работодателей."
         ], C_PINK),
        ("ПРАВИЛО 2: СТАТУСЫ И ПРОЗРАЧНОСТЬ",
         "Воронка обратной связи",
         [
             "Каждое отправленное приглашение получает строгий жизненный цикл: sent ➔ seen ➔ accepted / rejected.",
             "Статус 'seen' выставляется автоматически в момент первого открытия карточки кандидатом.",
             "Работодатель видит факт прочтения своего оффера в реальном времени.",
             "Кандидат видит компанию, текст оффера и рублевую зарплатную вилку сразу."
         ], C_LAVENDER),
        ("ПРАВИЛО 3: ШТОРКА ПРЯМЫХ КОНТАКТОВ",
         "Защита персональных данных",
         [
             "До принятия приглашения соискателем работодатель видит только обезличенный верифицированный профиль.",
             "Email и прямые контакты передаются в кабинет компании только после нажатия кнопки 'Принять' кандидатом.",
             "Исключает возможность спама, прямых холодных звонков и несанкционированного сбора баз данных кандидатов."
         ], C_GREEN)
    ]

    for i, (tag, title, items, acc) in enumerate(rules):
        cx = Inches(0.8) + i * Inches(4.0)
        c = add_card(slide, cx, card_y, card_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), card_y + Inches(0.18), card_w - Inches(0.4), card_h - Inches(0.35))
        tf = tb.text_frame
        tf.word_wrap = True

        p_t = tf.paragraphs[0]
        p_t.text = tag
        p_t.font.name = FONT_CODE
        p_t.font.size = Pt(9.5)
        p_t.font.bold = True
        p_t.font.color.rgb = acc
        p_t.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = title
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(12)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(8)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.5, space_after=4)


def build_slide_6(prs):
    """Slide 6: Platform Functional Pillars."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Функциональные Столпы", "Архитектурное разделение кабинетов и контуров интеграции", "ТЗ §2.1: Единое пространство взаимодействия кандидатов, работодателей и спортивного реестра")

    card_w = Inches(3.75)
    card_h = Inches(5.35)
    card_y = Inches(1.65)

    pillars = [
        ("СТОЛП 1", "КАБИНЕТ СОИСКАТЕЛЯ",
         "Автономия и контроль квалификации",
         [
             "Авторизация по коду без парольной уязвимости и интеграция Keycloak SSO.",
             "Заполнение профиля вручную или авторазбор PDF резюме с нормализацией стека.",
             "Прохождение адаптивного IRT тестирования (12 вопросов) для подтверждения грейда.",
             "Отображение официального спортивного разряда и турнирных баллов из реестра ФСП.",
             "Центр входящих офферов: просмотр условий, зарплатных вилок, подтверждение или отказ."
         ], C_PINK),
        ("СТОЛП 2", "КАБИНЕТ РАБОТОДАТЕЛЯ",
         "Умный скоринг и адресный наем",
         [
             "Создание потребности: указание роли, стека, формата работы и спортивного фильтра.",
             "Умный ранжирующий движок evaluate_need с объяснением «почему подходит этот человек».",
             "Поиск по банку кандидатов с фильтрами без жесткой привязки к категории.",
             "Формирование оффера со строгой валидацией диапазона в рублях (RUB до вычета НДФЛ).",
             "Трекинг воронки: sent (отправлено) ➔ seen (просмотрено) ➔ accepted (контакт открыт)."
         ], C_LAVENDER),
        ("СТОЛП 3", "РЕЕСТР ФСП И БЕЗОПАСНОСТЬ",
         "Верификация и защита данных",
         [
             "Мок-интеграция реестра Федерации спортивного программирования из версионируемого git.",
             "Связка профиля кандидата с external_id в едином контуре авторизации.",
             "Полная устойчивость к отсутствию спортивной истории (пустая история без падений).",
             "Строгая изоляция ПДн: SQLite WAL на локальном стенде, хранение паролей Argon2.",
             "Нулевая зависимость от внешних серверов и облачных провайдеров (100% offline)."
         ], C_GREEN)
    ]

    for i, (tag, title, subtitle, items, acc) in enumerate(pillars):
        cx = Inches(0.8) + i * Inches(4.0)
        c = add_card(slide, cx, card_y, card_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True

        p_tag = tf.paragraphs[0]
        p_tag.text = tag
        p_tag.font.name = FONT_CODE
        p_tag.font.size = Pt(9.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = acc
        p_tag.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = title
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(13)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(2)

        p_sub = tf.add_paragraph()
        p_sub.text = subtitle
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(9.5)
        p_sub.font.color.rgb = C_TEXT_MUTED
        p_sub.space_after = Pt(10)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.5, space_after=5)


def build_slide_7(prs):
    """Slide 7: Adaptive IRT Testing Engine."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Механика Тестирования", "Адаптивный движок IRT с защитой от угадывания и утечек", "ТЗ §2: Тест устойчив к заучиванию ключей и дает сопоставимую сложность каждому соискателю")

    col_w = Inches(5.75)
    card_h = Inches(2.55)
    top1 = Inches(1.65)
    top2 = Inches(4.45)

    blocks = [
        ("АРХИТЕКТУРА БАНКА И ВЫРАВНИВАНИЕ",
         "216 вопросов, 288 семейств заданий",
         [
             "Каталог stems.py разбит по 9 вопросов на пару «специализация × грейд».",
             "Длины вариантов ответов выровнены: верный ответ длиннее остальных лишь в 30% случаев.",
             "Читерская стратегия «выбирай самый длинный ответ» дает не более 1% успеха.",
             "Темы: refusal_contract, close_cause, offline_check и профильные алгоритмы."
         ], C_PINK),
        ("ЕДИНЫЙ ПЛАН: 12 ВОПРОСОВ (3 / 6 / 3)",
         "Сбалансированная матрица сложности",
         [
             "Каждый тест на грейд g содержит: 3 вопроса уровня ниже, 6 уровня g, 3 уровня выше.",
             "У junior и lead недостающие слоты добираются своим уровнем без потери качества.",
             "Темы и интегральная сложность одинаковы для всех, но порядок и вопросы уникальны.",
             "Повторная сдача берет другие темы; частота показа вопросов выравнивается."
         ], C_LAVENDER),
        ("ФОРМАТ «ОЦЕНИТЕ КАЖДЫЙ ВАРИАНТ»",
         "Вероятность угадать снижена с 1/3 до 1/8",
         [
             "Кандидат оценивает каждое из 3 утверждений: «верно» или «неверно».",
             "Балл начисляется только если верны все 3 оценки: шанс угадать — 12.5% (1 из 8).",
             "Варианты перемешиваются и получают одноразовые ID; буквы правильного ответа нет.",
             "Ключ лежит строго на сервере в записи сессии test_attempts.form_json."
         ], C_GREEN),
        ("АДАПТИВНАЯ ОЦЕНКА IRT И ПОРОГИ",
         "Осторожная стратегия подтверждения",
         [
             "Уровень θ рассчитывается по модели IRT с учетом индивидуальной сложности вопросов.",
             "На границе грейдов (вероятность 15–85%) движок динамически добавляет до 3 блоков.",
             "Грейд подтверждается при уверенности ≥ 60% (завысить грейд хуже, чем занизить).",
             "При смене грейда учитываются накопленные ответы двух предыдущих попыток."
         ], C_PINK)
    ]

    for i, (tag, subtitle, items, acc) in enumerate(blocks):
        col = i % 2
        row = i // 2
        cx = Inches(0.8) + col * Inches(6.0)
        cy = top1 if row == 0 else top2

        c = add_card(slide, cx, cy, col_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.18), col_w - Inches(0.4), card_h - Inches(0.35))
        tf = tb.text_frame
        tf.word_wrap = True

        p_tag = tf.paragraphs[0]
        p_tag.text = tag
        p_tag.font.name = FONT_CODE
        p_tag.font.size = Pt(9.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = acc
        p_tag.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = subtitle
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(11)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(6)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.5, space_after=3)


def build_slide_8(prs):
    """Slide 8: Mathematical Validation Matrix."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Математическая Валидация", "Матрица смежности и симуляция на 500 синтетических кандидатах", "Строгое математическое подтверждение точности IRT-теста по сравнению с классическим опросником")

    # Table on Left Side
    table_left = Inches(0.8)
    table_top = Inches(1.65)
    table_width = Inches(7.5)
    table_height = Inches(4.0)

    # Confusion matrix data: Grade | Совпало | Завышен | Занижен | Стабильность пересдачи
    headers = ["Грейд", "Совпало с истинным", "Завышен", "Занижен", "Стабильность"]
    rows = [
        ["Junior", "79%", "12%", "0%", "69%"],
        ["Middle", "81%", "10%", "9%", "75%"],
        ["Senior", "84%", "7%", "9%", "78%"],
        ["Lead", "68%", "0%", "32%", "71%"],
        ["Среднее", "82% (79–84)", "8%", "10%", "75%"]
    ]

    shape_t = slide.shapes.add_table(6, 5, table_left, table_top, table_width, table_height)
    table = shape_t.table
    table.columns[0].width = Inches(1.5)
    table.columns[1].width = Inches(1.8)
    table.columns[2].width = Inches(1.3)
    table.columns[3].width = Inches(1.3)
    table.columns[4].width = Inches(1.6)

    for c_idx, h_text in enumerate(headers):
        cell = table.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_CARD_BG2
        p = cell.text_frame.paragraphs[0]
        p.text = h_text
        p.font.name = FONT_BODY
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = C_PINK if c_idx == 1 else C_TEXT_WHITE
        p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT

    for r_idx, row_vals in enumerate(rows):
        is_avg = (r_idx == len(rows) - 1)
        for c_idx, val in enumerate(row_vals):
            cell = table.cell(r_idx + 1, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0x28, 0x1E, 0x38) if is_avg else C_CARD_BG
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_CODE if c_idx > 0 else FONT_BODY
            p.font.size = Pt(10)
            p.font.bold = is_avg or (c_idx == 1)
            p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
            if c_idx == 1:
                p.font.color.rgb = C_GREEN if not is_avg else C_PINK
            elif is_avg:
                p.font.color.rgb = C_TEXT_WHITE
            else:
                p.font.color.rgb = C_TEXT_BODY

    # Under-table note card
    un_card = add_card(slide, Inches(0.8), Inches(5.8), table_width, Inches(1.2), bg_color=C_CARD_BG2, border_color=C_CARD_BORDER)
    tb_un = slide.shapes.add_textbox(Inches(0.95), Inches(5.85), table_width - Inches(0.3), Inches(1.0))
    tf_un = tb_un.text_frame
    tf_un.word_wrap = True
    p_un1 = tf_un.paragraphs[0]
    p_un1.text = "АНАЛИТИЧЕСКИЙ ВЫВОД ИЗ СИМУЛЯЦИИ:"
    p_un1.font.name = FONT_CODE
    p_un1.font.size = Pt(9.5)
    p_un1.font.bold = True
    p_un1.font.color.rgb = C_LAVENDER
    p_un1.space_after = Pt(2)

    p_un2 = tf_un.add_paragraph()
    p_un2.text = "• Lead осторожен: Lead чаще получает Senior, чем наоборот — завысить хуже, чем занизить.\n• Ошибка на одну ступень: ни один кандидат не ошибся более чем на 1 уровень (0% cross-grade выбросов)."
    p_un2.font.name = FONT_BODY
    p_un2.font.size = Pt(9.5)
    p_un2.font.color.rgb = C_TEXT_BODY

    # Right side 3 stat callouts
    right_x = Inches(8.55)
    right_w = Inches(3.98)
    
    add_stat_card(slide, right_x, Inches(1.65), right_w, Inches(1.65), "92.7%", "Точность среди «уверенно»", "Целевой показатель платформы достигнут без зубрежки (мин. 91% — макс. 96%)", C_PINK)
    add_stat_card(slide, right_x, Inches(3.45), right_w, Inches(1.65), "0%", "Ошибок больше ступени", "В эталоне ТЗ ошибка составляла 2.4%, в SpecTrack — строгий ноль", C_GREEN)
    add_stat_card(slide, right_x, Inches(5.25), right_w, Inches(1.75), "5% vs 100%", "Устойчивость к утечке ключа", "Знание ключа b-c-a в эталоне давало 100% сдачи, в SpecTrack — лишь 5%", C_LAVENDER)


def build_slide_9(prs):
    """Slide 9: System Architecture & Standards."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Архитектура Системы", "Монолитная реализация и Zero-Cloud стандарты", "ТЗ §3: Автономный рабочий процесс без тяжелых внешних сервисов, GPU и сторонних CDN")

    col_w = Inches(5.75)
    card_h = Inches(2.55)
    top1 = Inches(1.65)
    top2 = Inches(4.45)

    arch_blocks = [
        ("ZERO-CLOUD МОНОЛИТ", "Python 3.12 • Jinja2 • htmx",
         [
             "Один контейнер, один процесс uvicorn с одним worker — максимальная стабильность стенда.",
             "Реактивный интерфейс на локальном htmx: библиотека вшита в репозиторий, 0 CDN ссылок.",
             "Кабинеты кандидата, работодателя и API живут в одном адресном пространстве.",
             "Отсутствие Node.js, Webpack и React ускоряет сборку контейнера до нескольких секунд."
         ], C_PINK),
        ("ХРАНИЛИЩЕ И ДАННЫЕ", "SQLite WAL • Том стенда fsp-sqlite",
         [
             "Один файл базы данных в режиме Write-Ahead Logging (WAL) с единственным писателем.",
             "Мок достижений ФСП читает JSON из репозитория и наполняет базу при старте.",
             "Кабинеты, подбор и тесты обращаются к согласованным нормализованным таблицам.",
             "Отсутствие внешней СУБД (Postgres/Redis) гарантирует нулевую вероятность сетевых сбоев."
         ], C_LAVENDER),
        ("БЕЗОПАСНОСТЬ И 152-ФЗ", "Argon2 • Подписанные cookie-сессии",
         [
             "Хэширование паролей промышленным алгоритмом Argon2; защита от перебора.",
             "Авторизационная сессия через защищенную cookie product_session.",
             "Персональные данные (ФИО, почта, анкета) не покидают контур стенда (нет облачных AI).",
             "Готовность интеграции с локальным Keycloak через external_id без смешивания контекстов."
         ], C_GREEN),
        ("API И ТЕСТОВОЕ ПОКРЫТИЕ", "31 OpenAPI эндпоинт • 125 тестов",
         [
             "Интерактивная документация /docs и схема в /api/openapi.json прямо на стенде.",
             "125 автоматических тестов покрывают валидацию, скоринг, безопасность и кабинеты.",
             "Разбор PDF через pypdf 6.19.0 и словарь синонимов без падений процесса.",
             "Прогон валидации доступен жюри в один клик через GET /validation (ответ text/plain)."
         ], C_PINK)
    ]

    for i, (tag, subtitle, items, acc) in enumerate(arch_blocks):
        col = i % 2
        row = i // 2
        cx = Inches(0.8) + col * Inches(6.0)
        cy = top1 if row == 0 else top2

        c = add_card(slide, cx, cy, col_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.18), col_w - Inches(0.4), card_h - Inches(0.35))
        tf = tb.text_frame
        tf.word_wrap = True

        p_tag = tf.paragraphs[0]
        p_tag.text = tag
        p_tag.font.name = FONT_CODE
        p_tag.font.size = Pt(9.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = acc
        p_tag.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = subtitle
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(11)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(6)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.5, space_after=3)


# ==============================================================================
# UI WALKTHROUGH SLIDES (SLIDES 10 - 17)
# ==============================================================================

def build_slide_10(prs):
    """Slide 10: Step 1 Registration & Confirm Code."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 1", "Регистрация и подтверждение входа соискателя", "Быстрый вход без пароля: согласие на обработку данных и одноразовый проверочный код")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "01-register.png"),
                          "Форма регистрации и согласия 152-ФЗ",
                          "Соискатель указывает email, роль и подтверждает согласие на обработку персональных данных",
                          badge_text="ЭКРАН 01")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "02-confirm-code.png"),
                          "Ввод одноразового кода подтверждения",
                          "Для автономного стенда проверочный код отображается прямо в интерфейсе для удобства жюри",
                          badge_text="ЭКРАН 02")


def build_slide_11(prs):
    """Slide 11: Step 2 Candidate Profile & Grade Test."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 2", "Профиль кандидата и подготовка к тестированию", "Анкета, загрузка PDF резюме и карточка адаптивного теста на грейд")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "03-profile-card.png"),
                          "Карточка профиля соискателя",
                          "Отображение базовой информации, заявленного стека технологий и статуса готовности к подтверждению",
                          badge_text="ЭКРАН 03")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "05-test-card.png"),
                          "Карточка запуска адаптивного тестирования",
                          "Выбор специализации и грейда, инструкция по механике «оцените каждый вариант» и правила попыток",
                          badge_text="ЭКРАН 04")


def build_slide_12(prs):
    """Slide 12: Step 3 Test Completion & Category Determination."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 3", "Прохождение теста и фиксация верифицированной категории", "Синтез категории backend:middle, оценка уверенности и позиция в грейде")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "06-cabinet-category.png"),
                          "Кабинет с подтвержденной категорией",
                          "Уверенность 93%, подтвержденный статус middle, объяснение синтеза и управление 3 чекбоксами приватности",
                          badge_text="ЭКРАН 05")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "03-profile-form.png"),
                          "Редактирование профиля и разбор PDF",
                          "Возможность загрузить резюме без риска затирания подтвержденного тестом грейда квалификации",
                          badge_text="ЭКРАН 06")


def build_slide_13(prs):
    """Slide 13: Step 4 FSP Registry Integration."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 4", "Интеграция с реестром спортивного программирования", "Подтягивание официальных разрядов ФСП и корректная обработка пустой истории")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "07b-fsp-synth-1-top.png"),
                          "Профиль с подтвержденными разрядами ФСП",
                          "Несколько спортивных дисциплин, баллы турниров и разряды в топе профиля кандидата",
                          badge_text="ЭКРАН 07")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "08-fsp-synth-2.png"),
                          "Штатная пустая история достижений ФСП",
                          "Отсутствие спортивной истории не приводит к ошибке: чистый интерфейс без ложных данных",
                          badge_text="ЭКРАН 08")


def build_slide_14(prs):
    """Slide 14: Step 5 Employer Cabinet & Shortlist."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 5", "Кабинет работодателя и умная подборка кандидатов", "Ранжирование по 5 параметрам потребности с объяснением «почему подходит этот кандидат»")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "09-employer-cabinet.png"),
                          "Кабинет работодателя и форма потребности",
                          "Фильтры специализации, грейда, стека технологий и признака достижений в спортивном программировании",
                          badge_text="ЭКРАН 09")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "10-shortlist-card.png"),
                          "Карточка соискателя в выдаче подборки",
                          "Прозрачное обоснование релевантности, подтвержденный грейд и кнопка адресного приглашения",
                          badge_text="ЭКРАН 10")


def build_slide_15(prs):
    """Slide 15: Step 6 Offer Creation & Anti-Spam Salary Bounds."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 6", "Формирование оффера и обязательная вилка в рублях", "Защита соискателя от бессмысленных откликов: строгие границы зарплаты в первом же сообщении")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "11-offer-form.png"),
                          "Форма создания оффера с вилкой RUB",
                          "Обязательное указание нижней и верхней границы в рублях; контакты компании видны соискателю сразу",
                          badge_text="ЭКРАН 11")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "12-sent-card.png"),
                          "Карточка отправленного оффера (статус sent)",
                          "Оффер зафиксирован в системе; почта кандидата скрыта до подтверждения согласия",
                          badge_text="ЭКРАН 12")


def build_slide_16(prs):
    """Slide 16: Step 7 Transparency Funnel & Privacy Curtain."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 7", "Воронка статусов и открытие контактов кандидата", "Жизненный цикл: sent ➔ seen ➔ accepted. Почта передается работодателю только после согласия")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "13-offer-seen.png"),
                          "Фиксация прочтения соискателем (seen)",
                          "Работодатель видит, что кандидат ознакомился с условиями и зарплатной вилкой предложения",
                          badge_text="ЭКРАН 13")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "15-accepted-card.png"),
                          "Согласие соискателя и открытие контактов (accepted)",
                          "Шторка приватности снята: email кандидата отображается в карточке для прямого найма",
                          badge_text="ЭКРАН 14")


def build_slide_17(prs):
    """Slide 17: Step 8 Validation Engine on Live Stand."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Демонстрация • Шаг 8", "Движок валидации и метрики на живом стенде", "Доступность для жюри в один клик: прогон Golden Run и сбор системных метрик")

    w = Inches(5.75)
    h = Inches(5.35)
    y = Inches(1.65)

    add_framed_screenshot(slide, Inches(0.8), y, w, h,
                          os.path.join(PITCH_DIR, "16-validation-zoom.png"),
                          "Прогон валидации golden_run (/validation)",
                          "Category match: 38/38, Outcome match: 72/72, Resume OK: 4/4 без обращения во внешнюю сеть",
                          badge_text="ЭКРАН 15")

    add_framed_screenshot(slide, Inches(6.8), y, w, h,
                          os.path.join(PITCH_DIR, "16-metrics.png"),
                          "Сводные метрики стабильности стенда",
                          "Быстрый ответ сервера, отсутствие GPU-нагрузки и полная воспроизводимость прогона",
                          badge_text="ЭКРАН 16")


def build_slide_18(prs):
    """Slide 18: Deployment & Zero-Cloud."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Развертывание Стенда", "Запуск одной командой и автономность без облаков", "ТЗ §3: Полная воспроизводимость на стенде жюри без внешних зависимостей и ключей API")

    # Command Banner Box
    cmd_card = add_card(slide, Inches(0.8), Inches(1.65), Inches(11.733), Inches(1.4), bg_color=C_CARD_BG2, border_color=C_PINK)
    tb_cmd = slide.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(11.333), Inches(1.2))
    tf_c = tb_cmd.text_frame
    tf_c.word_wrap = True
    p_c0 = tf_c.paragraphs[0]
    p_c0.text = "КОМАНДА ЗАПУСКА НА СТЕНДЕ ЖЮРИ:"
    p_c0.font.name = FONT_CODE
    p_c0.font.size = Pt(10)
    p_c0.font.bold = True
    p_c0.font.color.rgb = C_PINK
    p_c0.space_after = Pt(4)

    p_c1 = tf_c.add_paragraph()
    p_c1.text = "docker compose -f deploy/fsp/compose.yaml up --build"
    p_c1.font.name = FONT_CODE
    p_c1.font.size = Pt(14)
    p_c1.font.bold = True
    p_c1.font.color.rgb = C_TEXT_WHITE
    p_c1.space_after = Pt(4)

    p_c2 = tf_c.add_paragraph()
    p_c2.text = "Кабинеты стенда: http://127.0.0.1:8000  •  OpenAPI спецификация: /docs  •  Схема: /api/openapi.json"
    p_c2.font.name = FONT_CODE
    p_c2.font.size = Pt(10)
    p_c2.font.color.rgb = C_GREEN

    # 3 Feature Cards
    card_w = Inches(3.75)
    card_h = Inches(3.75)
    card_y = Inches(3.25)

    features = [
        ("АВТОНОМНЫЙ ОБРАЗ", "Zero Network Dependencies",
         [
             "Стенд требует только Docker Engine и плагин Compose.",
             "Никаких обращений к внешним CDN: шрифты, htmx и стили вшиты в локальный репозиторий.",
             "Полная работоспособность в изолированном сетевом контуре без доступа в интернет."
         ], C_PINK),
        ("АВТОГЕНЕРАЦИЯ СЕКРЕТА", "PRODUCT_SECRET Guard",
         [
             "Стенд генерирует безопасный ключ PRODUCT_SECRET автоматически, если он не передан явно.",
             "Строго соблюдается требование безопасности: длина ключа не менее 32 символов.",
             "Подписанные cookie сессии гарантируют защиту от подделки идентификаторов пользователей."
         ], C_LAVENDER),
        ("ПРЕДУСТАНОВЛЕННЫЕ ДАННЫЕ", "Git Seed & SQLite WAL",
         [
             "Банк из 216 вопросов и 288 семейств инициализируется из локального репозитория.",
             "Мок достижений ФСП заполняется при первом старте контейнера без сторонних запросов.",
             "База SQLite WAL надежно сохраняет все действия жюри в выделенном томе fsp-sqlite."
         ], C_GREEN)
    ]

    for i, (tag, title, items, acc) in enumerate(features):
        cx = Inches(0.8) + i * Inches(4.0)
        c = add_card(slide, cx, card_y, card_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.2), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True

        p_t = tf.paragraphs[0]
        p_t.text = tag
        p_t.font.name = FONT_CODE
        p_t.font.size = Pt(9.5)
        p_t.font.bold = True
        p_t.font.color.rgb = acc
        p_t.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = title
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(12)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(8)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.5, space_after=4)


def build_slide_19(prs):
    """Slide 19: 5-Step Live Demo Scenario for Jury."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Сценарий Для Жюри", "Пошаговый регламент проверки соответствия ТЗ за 5 шагов", "Прозрачный и повторяемый сценарий живой демонстрации функционала на стенде")

    step_w = Inches(11.733)
    step_h = Inches(0.95)
    start_y = Inches(1.65)
    spacing_y = Inches(1.05)

    steps = [
        ("ШАГ 01", "Регистрация и подтверждение",
         "Соискатель соглашается с 152-ФЗ, получает одноразовый код прямо на экране стенда и входит в систему без внешнего почтового сервиса.", C_PINK),
        ("ШАГ 02", "Анкета и адаптивный тест IRT",
         "Заполняются стек и роль; соискатель сдает 12 вопросов единого плана 3/6/3 формата «оцените варианты» и получает подтвержденную категорию.", C_LAVENDER),
        ("ШАГ 03", "Интеграция с реестром ФСП",
         "Демонстрация двух соискателей: с подтвержденными спортивными дисциплинами и разрядами, и с чистой пустой историей без сбоев интерфейса.", C_GREEN),
        ("ШАГ 04", "Подбор и оффер с RUB вилкой",
         "Работодатель создает потребность, видит соискателя в топе с обоснованием («почему подходит») и отправляет оффер с обязательной вилкой в рублях.", C_PINK),
        ("ШАГ 05", "Прозрачность и открытие контактов",
         "Соискатель видит оффер (статус sent ➔ seen). После нажатия кнопки «Принять» (accepted) работодатель получает прямой email кандидата.", C_LAVENDER)
    ]

    for i, (tag, title, desc, acc) in enumerate(steps):
        sy = start_y + i * spacing_y
        c = add_card(slide, Inches(0.8), sy, step_w, step_h)
        tb = slide.shapes.add_textbox(Inches(1.0), sy + Inches(0.12), step_w - Inches(0.4), step_h - Inches(0.24))
        tf = tb.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        r_tag = p.add_run()
        r_tag.text = f"[{tag}] "
        r_tag.font.name = FONT_CODE
        r_tag.font.size = Pt(11)
        r_tag.font.bold = True
        r_tag.font.color.rgb = acc

        r_title = p.add_run()
        r_title.text = title + "  —  "
        r_title.font.name = FONT_BODY
        r_title.font.size = Pt(11)
        r_title.font.bold = True
        r_title.font.color.rgb = C_TEXT_WHITE

        r_desc = p.add_run()
        r_desc.text = desc
        r_desc.font.name = FONT_BODY
        r_desc.font.size = Pt(10)
        r_desc.font.color.rgb = C_TEXT_MUTED


def build_slide_20(prs):
    """Slide 20: Summary & Production Roadmap."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    add_header(slide, "Итоги и Дорожная Карта", "Результаты хакатона и план развития платформы на 2026 год", "От проверенного прототипа к полноценному отраслевому сервису Федерации")

    card_w = Inches(2.78)
    card_h = Inches(5.35)
    card_y = Inches(1.65)

    roadmap = [
        ("ЭТАП 01 (ВЫПОЛНЕНО)", "MVP ХАКАТОНА", "Q1 2026",
         [
             "Монолитная архитектура Python 3.12 + FastAPI + Jinja2/htmx.",
             "Адаптивный IRT движок с банком на 216 вопросов и защитой от угадывания.",
             "Математическая валидация на 500 кандидатах: 92.7% точность.",
             "Полное покрытие ТЗ: обратная механика, RUB вилки, 152-ФЗ.",
             "125 тестов, Docker Compose стенд 100% offline."
         ], C_GREEN),
        ("ЭТАП 02", "ИНТЕГРАЦИЯ С ФСП", "Q2 2026",
         [
             "Переход с мока на боевой REST API Федерации спортивного программирования.",
             "Автоматическая синхронизация протоколов всероссийских соревнований.",
             "Расширение банка тестовых заданий до 1000+ вопросов.",
             "Добавление новых форматов заданий: multi-choice, order, numeric."
         ], C_PINK),
        ("ЭТАП 03", "КОРПОРАТИВНЫЙ КОНТУР", "Q3 2026",
         [
             "Подключение внешних корпоративных провайдеров авторизации (Keycloak / LDAP).",
             "Многопользовательские кабинеты для компаний: роли HR, TeamLead, CTO.",
             "Аналитический дашборд воронки найма и времени закрытия вакансий.",
             "Интеграция с внутренними ATS работодателей через вебхуки."
         ], C_LAVENDER),
        ("ЭТАП 04", "ИИ-АССИСТЕНТ", "Q4 2026",
         [
             "Внедрение российской языковой модели в изолированном контуре.",
             "Автоматическая помощь в формулировании требований к вакансии.",
             "Генерация персональных рекомендаций соискателям по закрытию пробелов.",
             "Предиктивная аналитика потребности в ИТ-кадрах для Федерации."
         ], C_PINK)
    ]

    for i, (tag, title, period, items, acc) in enumerate(roadmap):
        cx = Inches(0.8) + i * Inches(2.98)
        c = add_card(slide, cx, card_y, card_w, card_h)
        tb = slide.shapes.add_textbox(cx + Inches(0.18), card_y + Inches(0.2), card_w - Inches(0.36), card_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True

        p_tag = tf.paragraphs[0]
        p_tag.text = tag
        p_tag.font.name = FONT_CODE
        p_tag.font.size = Pt(8.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = acc
        p_tag.space_after = Pt(2)

        p_tit = tf.add_paragraph()
        p_tit.text = title
        p_tit.font.name = FONT_TITLE
        p_tit.font.size = Pt(11.5)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_WHITE
        p_tit.space_after = Pt(1)

        p_per = tf.add_paragraph()
        p_per.text = period
        p_per.font.name = FONT_CODE
        p_per.font.size = Pt(9.5)
        p_per.font.bold = True
        p_per.font.color.rgb = C_TEXT_MUTED
        p_per.space_after = Pt(8)

        for item in items:
            add_bullet_item(tf, "", item, bullet_color=acc, font_size=9.2, space_after=4)


def build_slide_21(prs):
    """Slide 21: Team Contacts & Repository."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)

    # Decorative wave line from FSP brandbook
    if os.path.exists(ASSET_LINE):
        slide.shapes.add_picture(ASSET_LINE, Inches(0.0), Inches(0.0), width=Inches(13.333), height=Inches(7.5))

    # Top Brand Logo
    if os.path.exists(ASSET_LOGO_WHITE):
        slide.shapes.add_picture(ASSET_LOGO_WHITE, Inches(0.8), Inches(0.65), width=Inches(2.8))

    # Center-left Content
    left_x = Inches(0.8)
    top_y = Inches(1.8)
    left_w = Inches(7.5)

    tb_t = slide.shapes.add_textbox(left_x, top_y, left_w, Inches(1.8))
    tf_t = tb_t.text_frame
    tf_t.word_wrap = True

    p0 = tf_t.paragraphs[0]
    p0.text = "СПАСИБО ЗА ВНИМАНИЕ!"
    p0.font.name = FONT_TITLE
    p0.font.size = Pt(36)
    p0.font.bold = True
    p0.font.color.rgb = C_TEXT_WHITE
    p0.space_after = Pt(6)

    p1 = tf_t.add_paragraph()
    p1.text = "Готовы ответить на любые технические и архитектурные вопросы жюри"
    p1.font.name = FONT_BODY
    p1.font.size = Pt(14)
    p1.font.color.rgb = C_TEXT_MUTED

    # Contact Info Card
    c_card = add_card(slide, left_x, Inches(3.6), left_w, Inches(2.6), bg_color=C_CARD_BG, border_color=C_CARD_BORDER)
    tb_c = slide.shapes.add_textbox(left_x + Inches(0.25), Inches(3.8), left_w - Inches(0.5), Inches(2.2))
    tf_c = tb_c.text_frame
    tf_c.word_wrap = True

    p_c0 = tf_c.paragraphs[0]
    p_c0.text = "КОНТАКТЫ И ИНФОРМАЦИЯ О ПРОЕКТЕ:"
    p_c0.font.name = FONT_CODE
    p_c0.font.size = Pt(11)
    p_c0.font.bold = True
    p_c0.font.color.rgb = C_PINK
    p_c0.space_after = Pt(8)

    add_bullet_item(tf_c, "Капитан команды:", "Чистяков Евгений • echistyakov@aq.ru", bullet_color=C_PINK, font_size=11, space_after=5)
    add_bullet_item(tf_c, "Состав команды:", "Иван Курлыков, Леонид Пластуненко, Николай Кузнецов, Игорь Софронов", bullet_color=C_LAVENDER, font_size=11, space_after=5)
    add_bullet_item(tf_c, "Лицензия:", "Открытый код (Open Source MIT / Apache-2.0)", bullet_color=C_GREEN, font_size=11, space_after=5)
    add_bullet_item(tf_c, "Стенд развернут:", "http://127.0.0.1:8000  •  Документация: /docs", bullet_color=C_PINK, font_size=11, space_after=2)

    # Right side stat cards
    right_x = Inches(8.8)
    right_w = Inches(3.733)
    
    add_stat_card(slide, right_x, Inches(1.8), right_w, Inches(1.5), "38 / 38", "Golden Run", "Полное совпадение категорий", C_PINK)
    add_stat_card(slide, right_x, Inches(3.45), right_w, Inches(1.5), "92.7%", "Точность IRT", "Математическая надежность", C_GREEN)
    add_stat_card(slide, right_x, Inches(5.1), right_w, Inches(1.5), "125 тестов", "Качество кода", "100% автотестов стенда", C_LAVENDER)


def main():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    builders = [
        build_slide_1,
        build_slide_2,
        build_slide_3,
        build_slide_4,
        build_slide_5,
        build_slide_6,
        build_slide_7,
        build_slide_8,
        build_slide_9,
        build_slide_10,
        build_slide_11,
        build_slide_12,
        build_slide_13,
        build_slide_14,
        build_slide_15,
        build_slide_16,
        build_slide_17,
        build_slide_18,
        build_slide_19,
        build_slide_20,
        build_slide_21,
    ]

    print(f"Building {len(builders)} slides...")
    for idx, builder in enumerate(builders, 1):
        print(f"Building slide {idx}...")
        builder(prs)

    out_path = "product/docs/prezentaciya.pptx"
    prs.save(out_path)
    print(f"Presentation saved successfully to: {out_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
