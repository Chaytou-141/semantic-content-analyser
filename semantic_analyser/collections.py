"""Format-independent collection admission before transactional storage writes.

CSV and future website selections use this service. Store remains the low-level
persistence layer; analysis-dependent validation belongs at this boundary.
"""

import threading

from .schemas import Article
from .storage import MAX_ARTICLES, validate_collection


class PreflightUnavailable(Exception):
    """The analysis dependency failed; existing collection must remain intact."""


class CollectionService:
    def __init__(self, store, engine, lock=None):
        self.store = store
        self.engine = engine
        self.lock = lock if lock is not None else threading.RLock()

    def preflight(self, articles):
        if not 1 <= len(articles) <= MAX_ARTICLES:
            raise ValueError(f"A collection must contain between 1 and {MAX_ARTICLES} articles.")
        # Revalidate even constructed/mutated Article instances, and accept mappings
        # so future extracted website selections need not round-trip through CSV.
        candidates = [Article.model_validate(a.model_dump() if isinstance(a, Article) else a)
                      for a in articles]
        validate_collection(candidates)
        try:
            summary = self.engine.preflight(candidates)
        except (OSError, RuntimeError) as error:
            raise PreflightUnavailable("Collection validation is temporarily unavailable. No changes were saved; try again later.") from error
        return candidates, summary

    def replace(self, articles, before_commit=None):
        with self.lock:
            candidates, _ = self.preflight(articles)
            if before_commit:
                before_commit()
            return self.store.replace(candidates, before_commit)

    def save_article(self, article, before_commit=None):
        with self.lock:
            collection = self.store.articles()
            if article.id not in {a.id for a in collection}:
                raise KeyError(article.id)
            candidates, _ = self.preflight([article if a.id == article.id else a for a in collection])
            if before_commit:
                before_commit()
            self.store.save_article(next(a for a in candidates if a.id == article.id), before_commit)
