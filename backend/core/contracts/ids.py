from typing import NewType

UserId = NewType("UserId", int)
MentorId = NewType("MentorId", int)
SessionId = NewType("SessionId", int)
ConceptId = NewType("ConceptId", int)
ArticleId = NewType("ArticleId", int)
NewsId = NewType("NewsId", int)
ReportId = NewType("ReportId", int)
DebateSessionId = NewType("DebateSessionId", int)

__all__ = [
    "ArticleId",
    "ConceptId",
    "DebateSessionId",
    "MentorId",
    "NewsId",
    "ReportId",
    "SessionId",
    "UserId",
]
