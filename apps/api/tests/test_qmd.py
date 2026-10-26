import json

from friday.services.qmd import QmdSearchService


class FakeRunner:
    def __init__(self, payload):
        self.payload = payload
        self.args = None

    def run(self, args: list[str]) -> str:
        self.args = args
        return json.dumps(self.payload)


def test_qmd_results_require_path_and_snippet_citations():
    runner = FakeRunner(
        [
            {"path": "notes/interview.md", "snippet": "Use active recall", "score": 0.8},
            {"path": "notes/empty.md"},
        ]
    )
    result = QmdSearchService(runner).search("interview prep", "notes")
    assert result.answerable
    assert len(result.citations) == 1
    assert result.citations[0].path == "notes/interview.md"
    assert runner.args == [
        "qmd", "query", "--json", "-n", "5", "-c", "notes", "interview prep"
    ]


def test_empty_qmd_results_are_not_answerable():
    assert not QmdSearchService(FakeRunner([])).search("unknown", "notes").answerable

