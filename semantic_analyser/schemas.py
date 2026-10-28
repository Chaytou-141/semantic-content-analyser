import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Method = Literal["embeddings", "tfidf", "compare"]


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    topic: str = Field(default="", max_length=100)
    url: str = Field(default="", max_length=2048)
    eligible: bool = True
    existing_links: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value and (urlparse(value).scheme not in {"http", "https"} or not urlparse(value).netloc):
            raise ValueError("URLs must begin with http:// or https:// and include a hostname.")
        return value

    @field_validator("existing_links")
    @classmethod
    def valid_links(cls, value):
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item) for item in value):
            raise ValueError("Existing links must be article IDs separated by semicolons in CSV files.")
        return list(dict.fromkeys(value))


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    method: Method = "embeddings"
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0, ge=0, le=1)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Enter at least two non-space characters.")
        return value.strip()


class LinkRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=64)
    method: Method = "embeddings"
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0, ge=0, le=1)


class OverlapRequest(BaseModel):
    method: Literal["embeddings", "tfidf"] = "embeddings"
    threshold: float = Field(default=0.65, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class ImportRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=1500000)


class ReviewRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=64)
    decision: Literal["useful", "not_useful", "pending"]
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def different_articles(self):
        if self.source_id == self.target_id:
            raise ValueError("A source and destination must be different articles.")
        return self


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class FetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
