"""Base event schemas for Trinity Intelligence Platform"""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Base event class - all events inherit from this"""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str  # Service that emitted event
    correlation_id: UUID = Field(default_factory=uuid4)


class CommitReceived(Event):
    """Git commit received from GitHub webhook"""
    event_type: Literal["git.commit.received"] = "git.commit.received"
    commit_hash: str
    author: str
    author_email: str
    message: str
    files_changed: list[str]
    repository: str


class IssueCreated(Event):
    """GitHub issue created"""
    event_type: Literal["github.issue.created"] = "github.issue.created"
    issue_number: int
    title: str
    body: str
    labels: list[str]
    repository: str


class ServiceModified(Event):
    """Code service modified"""
    event_type: Literal["code.service.modified"] = "code.service.modified"
    service_name: str
    file_path: str
    commit_hash: str
    dependencies_changed: bool
