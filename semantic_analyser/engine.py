import hashlib
import json
import threading
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import MODEL_REVISION


class AnalysisEngine:
    def __init__(self, revision=MODEL_REVISION, model_factory=None):
        self.revision = revision
        self.model_factory = model_factory
        self.model = None
        self.lock = threading.RLock()
        self.cache_key = None

    def load(self):
        with self.lock:
            if self.model is None:
                if self.model_factory:
                    self.model = self.model_factory()
                else:
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2",
                                                     revision=self.revision, device="cpu")
                    self.model.eval()
        return self.model

    def passages(self, article):
        model = self.load()
        offsets = model.tokenizer(article.body, add_special_tokens=False,
                                  return_offsets_mapping=True, verbose=False)["offset_mapping"]
        title_ids = model.tokenizer.encode(article.title, add_special_tokens=False)[:40]
        short_title = model.tokenizer.decode(title_ids, skip_special_tokens=True)
        passages = []
        # 192 body tokens + 40 title tokens + separators stay below the 256-token model limit.
        for start in range(0, len(offsets), 160):
            window = offsets[start:start + 192]
            if not window:
                continue
            left, right = window[0][0], window[-1][1]
            text = article.body[left:right]
            passages.append({"article_id": article.id, "text": text, "start": left, "end": right,
                             "model_text": short_title + ". " + text})
            if start + 192 >= len(offsets):
                break
        return passages

    def prepare(self, articles):
        fingerprint = hashlib.sha256(json.dumps([a.model_dump() for a in articles], sort_keys=True).encode()).hexdigest()
        if self.cache_key == fingerprint:
            return
        chunks = [passage for article in articles for passage in self.passages(article)]
        if not chunks:
            raise ValueError("The collection does not contain any tokenisable text.")
        if len(chunks) > 800:
            raise ValueError("The collection exceeds 800 passages. Import fewer or shorter articles.")
        vectorizer = TfidfVectorizer()
        try:
            word_vectors = vectorizer.fit_transform([p["model_text"] for p in chunks])
        except ValueError as error:
            raise ValueError("Add text containing words of at least two characters before analysing.") from error
        self.chunks = chunks
        self.vectorizer = vectorizer
        self.word_vectors = word_vectors
        self.embeddings = None
        self.cache_key = fingerprint

    def semantic_vectors(self):
        if self.embeddings is None:
            self.embeddings = np.asarray(self.load().encode([p["model_text"] for p in self.chunks],
                                                         normalize_embeddings=True, show_progress_bar=False))
        return self.embeddings

    def scores(self, query, method):
        if method == "tfidf":
            return cosine_similarity(self.vectorizer.transform([query]), self.word_vectors)[0]
        # Bound queries at tokenizer level too; reject silent truncation.
        if len(self.load().tokenizer.encode(query, add_special_tokens=True)) > 256:
            raise ValueError("Shorten the search query to at most 256 model tokens.")
        vector = np.asarray(self.load().encode([query], normalize_embeddings=True, show_progress_bar=False))
        return (vector @ self.semantic_vectors().T)[0]

    @staticmethod
    def item(article, score, passage):
        return {"id": article.id, "title": article.title, "topic": article.topic,
                "url": article.url, "score": round(float(score), 5),
                "passage": passage["text"], "passage_start": passage["start"],
                "passage_end": passage["end"]}

    def search(self, articles, query, method, top_k, minimum):
        with self.lock:
            self.prepare(articles)
            scores = self.scores(query, method)
            by_id = {a.id: a for a in articles}
            best = {}
            for chunk, score in zip(self.chunks, scores):
                aid = chunk["article_id"]
                if score > 0 and score >= minimum and (aid not in best or score > best[aid][0]):
                    best[aid] = (float(score), chunk)
            ordered = sorted(best.items(), key=lambda row: (-row[1][0], row[0]))[:top_k]
            return [self.item(by_id[aid], score, passage) for aid, (score, passage) in ordered]

    def links(self, articles, source_id, method, top_k, minimum):
        with self.lock:
            self.prepare(articles)
            by_id = {a.id: a for a in articles}
            if source_id not in by_id:
                raise KeyError(source_id)
            source = by_id[source_id]
            excluded = {source_id} | set(source.existing_links) | {a.id for a in articles if not a.eligible}
            if method == "tfidf":
                matrix = cosine_similarity(self.word_vectors, self.word_vectors)
            else:
                vectors = self.semantic_vectors()
                matrix = vectors @ vectors.T
            source_positions = [i for i, p in enumerate(self.chunks) if p["article_id"] == source_id]
            best = {}
            for source_position in source_positions:
                for target_position, target in enumerate(self.chunks):
                    aid = target["article_id"]
                    score = float(matrix[source_position, target_position])
                    if aid in excluded or score <= 0 or score < minimum:
                        continue
                    if aid not in best or score > best[aid][0]:
                        best[aid] = (score, self.chunks[source_position], target)
            results = []
            for aid, (score, source_passage, target_passage) in sorted(best.items(), key=lambda row: (-row[1][0], row[0]))[:top_k]:
                result = self.item(by_id[aid], score, target_passage)
                result.update({"source_passage": source_passage["text"], "source_start": source_passage["start"],
                               "source_end": source_passage["end"], "review_required": True})
                results.append(result)
            return {"results": results, "excluded": {"self": source_id, "existing": source.existing_links,
                    "disallowed": [a.id for a in articles if not a.eligible]}}

    def overlaps(self, articles, method, threshold, limit):
        with self.lock:
            self.prepare(articles)
            if method == "tfidf":
                matrix = cosine_similarity(self.word_vectors, self.word_vectors)
            else:
                vectors = self.semantic_vectors()
                matrix = vectors @ vectors.T
            best = {}
            by_id = {a.id: a for a in articles}
            for i, left in enumerate(self.chunks):
                for j in range(i + 1, len(self.chunks)):
                    right = self.chunks[j]
                    if left["article_id"] == right["article_id"]:
                        continue
                    score = float(matrix[i, j])
                    pair = tuple(sorted((left["article_id"], right["article_id"])))
                    if score >= threshold and (pair not in best or score > best[pair][0]):
                        best[pair] = (score, left, right)
            results = []
            for pair, (score, left, right) in sorted(best.items(), key=lambda row: (-row[1][0], row[0]))[:limit]:
                results.append({"left": self.item(by_id[left["article_id"]], score, left),
                                "right": self.item(by_id[right["article_id"]], score, right),
                                "score": round(score, 5), "recommendation": "Review intent and unique information",
                                "review_required": True})
            return results
