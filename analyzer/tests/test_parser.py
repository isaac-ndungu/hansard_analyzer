import pytest
from analyzer.pipeline.parser import (
    parse_speakers,
    parse_sections,
    SPEAKER_PATTERN,
)


# Speaker Regex

class TestSpeakerPattern:

    def test_standard_speaker_match(self):
        text = "Hon. John Kamau (Kikuyu, UDA): We must invest in roads."
        matches = list(SPEAKER_PATTERN.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1).strip() == "John Kamau"
        assert matches[0].group(2).strip() == "Kikuyu"
        assert matches[0].group(3).strip() == "UDA"

    def test_speaker_with_dr_title(self):
        text = "Hon. Dr. Alice Omondi (Kisumu East, ODM): Healthcare is critical."
        matches = list(SPEAKER_PATTERN.finditer(text))
        assert len(matches) == 1
        assert "Omondi" in matches[0].group(1)

    def test_speaker_with_prof_title(self):
        text = "Hon. Prof. James Mwangi (Naivasha, Jubilee): Education must be funded."
        matches = list(SPEAKER_PATTERN.finditer(text))
        assert len(matches) == 1
        assert "Mwangi" in matches[0].group(1)

    def test_multiple_speakers(self):
        text = (
            "Hon. Jane Weru (Dagoretti, UDA): The budget is insufficient.\n"
            "Hon. Peter Otieno (Kisumu West, ODM): I agree with the member."
        )
        matches = list(SPEAKER_PATTERN.finditer(text))
        assert len(matches) == 2

    def test_no_match_on_plain_text(self):
        text = "The house was called to order at 9:00 AM."
        matches = list(SPEAKER_PATTERN.finditer(text))
        assert len(matches) == 0


# parse_speakers

class TestParseSpeakers:

    def test_returns_list_of_dicts(self):
        text = "Hon. Mary Njoki (Ruiru, UDA): Water access is a right."
        result = parse_speakers(text)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "Mary Njoki"
        assert result[0]["constituency"] == "Ruiru"
        assert result[0]["party"] == "UDA"
        assert "Water access" in result[0]["content"]

    def test_empty_text_returns_empty_list(self):
        result = parse_speakers("")
        assert result == []

    def test_skips_entries_with_no_content(self):
        text = "Hon. Ghost Speaker (Nowhere, None): "
        result = parse_speakers(text)
        assert result == []

    def test_preserves_swahili_content(self):
        text = "Hon. Ali Hassan (Mombasa, ODM): Serikali lazima itoe huduma za afya kwa wananchi."
        result = parse_speakers(text)
        assert len(result) == 1
        assert "Serikali" in result[0]["content"]


# parse_sections

class TestParseSections:

    def test_detects_known_section(self):
        text = "PETITIONS\n\nHon. Jane Doe (Nairobi, UDA): I wish to present a petition."
        result = parse_sections(text)
        assert any(s["title"] == "PETITIONS" for s in result)

    def test_detects_multiple_sections(self):
        text = (
            "PETITIONS\n\nSome petition content.\n\n"
            "BILLS\n\nSome bill content."
        )
        result = parse_sections(text)
        titles = [s["title"] for s in result]
        assert "PETITIONS" in titles
        assert "BILLS" in titles

    def test_empty_text_returns_empty_list(self):
        result = parse_sections("")
        assert result == []

    def test_section_content_is_captured(self):
        text = "MOTIONS\n\nThis motion concerns the budget allocation."
        result = parse_sections(text)
        assert len(result) == 1
        assert "budget allocation" in result[0]["content"]