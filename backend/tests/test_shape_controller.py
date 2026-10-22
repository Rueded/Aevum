import pytest
from app.character.conversational_models import StructuredTurnOutput, TurnMessageItem
from app.character.shape_controller import ShapeController


def test_clean_trailing_periods():
    assert ShapeController._clean_punctuation("好困。") == "好困"
    assert ShapeController._clean_punctuation("真的服了。。。") == "真的服了"
    assert ShapeController._clean_punctuation("ok.") == "ok"
    assert ShapeController._clean_punctuation("咋啦？") == "咋啦？"


def test_separate_inline_stickers():
    raw = "我先睡了[表情包: 趴地]明天再说"
    items = ShapeController._separate_inline_stickers(raw)
    assert len(items) == 3
    assert items[0].type == "text" and items[0].text == "我先睡了"
    assert items[1].type == "sticker" and items[1].sticker_id == "趴地"
    assert items[2].type == "text" and items[2].text == "明天再说"


def test_split_comma_into_bubbles():
    raw_output = StructuredTurnOutput(
        messages=[TurnMessageItem(type="text", text="没练，刚画完画。")]
    )
    processed = ShapeController.process(raw_output)
    # Comma should split into 2 bubbles and trailing period stripped
    assert len(processed.messages) == 2
    assert processed.messages[0].text == "没练"
    assert processed.messages[1].text == "刚画完画"


def test_trim_reflex_question_without_curiosity():
    raw_output = StructuredTurnOutput(
        messages=[TurnMessageItem(type="text", text="在发呆，你呢？")]
    )
    processed = ShapeController.process(raw_output, curiosity_active=False)
    assert len(processed.messages) == 1
    assert processed.messages[0].text == "在发呆"


def test_keep_reflex_question_with_curiosity():
    raw_output = StructuredTurnOutput(
        messages=[TurnMessageItem(type="text", text="在发呆，你呢？")]
    )
    processed = ShapeController.process(raw_output, curiosity_active=True)
    # With curiosity, "你呢？" is retained
    combined = " ".join(m.text for m in processed.messages if m.text)
    assert "你呢" in combined


def test_fatigued_caps_at_one_bubble():
    raw_output = StructuredTurnOutput(
        messages=[
            TurnMessageItem(type="text", text="困死了"),
            TurnMessageItem(type="text", text="眼睛睁不开"),
            TurnMessageItem(type="text", text="想睡"),
        ]
    )
    processed = ShapeController.process(raw_output, is_tired=True)
    assert len(processed.messages) == 1
    assert processed.messages[0].text == "困死了"
