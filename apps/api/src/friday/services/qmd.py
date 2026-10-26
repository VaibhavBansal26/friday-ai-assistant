import json
import subprocess
from typing import Protocol

from friday.domain.models import KnowledgeSearchResult, SearchCitation


class QmdRunner(Protocol):
    def run(self, args: list[str]) -> str: ...


class SubprocessQmdRunner:
    def run(self, args: list[str]) -> str:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError("QMD search failed")
        return completed.stdout


class QmdSearchService:
    def __init__(self, runner: QmdRunner | None = None) -> None:
        self.runner = runner or SubprocessQmdRunner()

    def search(self, query: str, collection: str, limit: int = 5) -> KnowledgeSearchResult:
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        safe_limit = min(max(limit, 1), 20)
        raw = self.runner.run(
            ["qmd", "query", "--json", "-n", str(safe_limit), "-c", collection, query]
        )
        parsed = json.loads(raw or "[]")
        items = parsed if isinstance(parsed, list) else parsed.get("results", [])
        citations: list[SearchCitation] = []
        for item in items:
            path = item.get("path") or item.get("file") or item.get("displayPath")
            snippet = item.get("snippet") or item.get("text") or item.get("content")
            if not path or not snippet:
                continue
            citations.append(
                SearchCitation(
                    collection=collection,
                    path=path,
                    doc_id=item.get("docid") or item.get("id"),
                    title=item.get("title"),
                    snippet=snippet,
                    score=item.get("score"),
                )
            )
        return KnowledgeSearchResult(
            query=query,
            citations=citations,
            answerable=bool(citations),
        )

