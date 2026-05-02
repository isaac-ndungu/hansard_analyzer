import pytest
from pathlib import Path


@pytest.fixture
def sample_text():
    return """
PRAYERS

IMPLEMENTATION OF NAIROBI RIVERS COMMISSION PROJECT

Hon. Speaker: We have a petition regarding the Nairobi Rivers Commission Project.

THE QUALITY HEALTHCARE AND PATIENT SAFETY BILL
(National Assembly Bill No. 41 of 2025)
(Moved by Hon. Owen Baya on 14.4.2026)

Hon. Owen Baya (Kilifi North, UDA): I beg to move that the Quality Healthcare
and Patient Safety Bill be now read a Second Time.

(Question put and agreed to)

THE TECHNOPOLIS (AMENDMENT) BILL
(National Assembly Bill No. 6 of 2024)

Hon. Kimani Ichung'wah (Kikuyu, UDA): I beg to move that this Bill be rejected.

(Question put and negatived)
"""


class TestExtractAgendaItems:

    def test_returns_list(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        assert isinstance(result, list)

    def test_includes_prayers_heading_in_combined_text(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        titles = [r["title"].lower() for r in result]
        assert any("prayer" in t for t in titles)

    def test_does_not_classify_implementation_heading_as_petition(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        types = [r["type"] for r in result]
        assert "PETITION" not in types

    def test_finds_bill(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        types = [r["type"] for r in result]
        assert "BILL" in types

    def test_all_items_have_position(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        assert all("position" in item for item in result)
        assert all(isinstance(item["position"], int) for item in result)

    def test_positions_are_increasing(self, sample_text):
        from analyzer.pipeline.parser import extract_agenda_items
        result = extract_agenda_items(sample_text)
        positions = [item["position"] for item in result]
        assert positions == sorted(positions)


class TestClassifyAgendaType:

    def test_bill_classification(self):
        from analyzer.pipeline.parser import classify_agenda_type
        assert classify_agenda_type("THE QUALITY HEALTHCARE BILL") == "BILL"

    def test_motion_classification(self):
        from analyzer.pipeline.parser import classify_agenda_type
        assert classify_agenda_type("ADOPTION OF REPORT ON CONSOLIDATED FUND") == "MOTION"

    def test_unknown_defaults_to_other(self):
        from analyzer.pipeline.parser import classify_agenda_type
        assert classify_agenda_type("SOME RANDOM HEADING") == "OTHER"


class TestExtractBills:

    def test_returns_list(self, sample_text):
        from analyzer.pipeline.bill_parser import extract_bills
        assert isinstance(extract_bills(sample_text), list)

    def test_finds_healthcare_bill(self, sample_text):
        from analyzer.pipeline.bill_parser import extract_bills
        result = extract_bills(sample_text)
        titles = [r["title"].lower() for r in result]
        assert any("healthcare" in t for t in titles)

    def test_extracts_bill_number(self, sample_text):
        from analyzer.pipeline.bill_parser import extract_bills
        result = extract_bills(sample_text)
        numbers = [r.get("bill_number") for r in result]
        assert any(n is not None for n in numbers)

    def test_detects_passed_outcome(self, sample_text):
        from analyzer.pipeline.bill_parser import extract_bills
        result = extract_bills(sample_text)
        outcomes = [r.get("outcome") for r in result]
        assert "Passed" in outcomes

    def test_detects_rejected_outcome(self):
        from analyzer.pipeline.bill_parser import extract_bills
        text = """
THE TECHNOPOLIS (AMENDMENT) BILL
(National Assembly Bill No. 6 of 2024)

Hon. Kimani Ichung'wah (Kikuyu, UDA): I beg to move that this Bill be rejected.

(Question put and negatived)
"""
        result = extract_bills(text)
        assert result[0].get("outcome") == "Rejected"

    def test_handles_empty_text(self):
        from analyzer.pipeline.bill_parser import extract_bills
        assert extract_bills("") == []

    def test_all_results_have_title(self, sample_text):
        from analyzer.pipeline.bill_parser import extract_bills
        result = extract_bills(sample_text)
        assert all("title" in r for r in result)


class TestPositionalMatching:

    def test_assigns_correct_agenda_item(self):
        from analyzer.pipeline.pipeline import _find_agenda_item_for_speech
        agenda_items = [
            {"id": 1, "position": 100},
            {"id": 2, "position": 500},
            {"id": 3, "position": 900},
        ]
        assert _find_agenda_item_for_speech(700, agenda_items) == 2

    def test_speech_before_any_heading_returns_none(self):
        from analyzer.pipeline.pipeline import _find_agenda_item_for_speech
        agenda_items = [{"id": 1, "position": 500}]
        assert _find_agenda_item_for_speech(100, agenda_items) is None

    def test_empty_agenda_items_returns_none(self):
        from analyzer.pipeline.pipeline import _find_agenda_item_for_speech
        assert _find_agenda_item_for_speech(500, []) is None

    def test_speech_exactly_at_heading_position(self):
        from analyzer.pipeline.pipeline import _find_agenda_item_for_speech
        agenda_items = [{"id": 1, "position": 500}]
        assert _find_agenda_item_for_speech(500, agenda_items) == 1

    def test_returns_last_preceding_heading_not_first(self):
        from analyzer.pipeline.pipeline import _find_agenda_item_for_speech
        agenda_items = [
            {"id": 1, "position": 100},
            {"id": 2, "position": 300},
            {"id": 3, "position": 700},
        ]
        assert _find_agenda_item_for_speech(400, agenda_items) == 2
