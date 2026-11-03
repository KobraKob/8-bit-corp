from typing import Optional
from sqlalchemy import select, or_
from app.core.ids import generate_id
from app.db.models import WikiNote
from app.db.session import async_session_factory


async def save_memory(*, title: str, body: str, tags: str = "", project_id: Optional[str] = None,
                      created_by_agent_id: Optional[str] = None) -> WikiNote:
    """Upsert a reusable company/project knowledge note by normalized title and scope."""
    normalized = " ".join(title.lower().split())
    async with async_session_factory() as session:
        stmt = select(WikiNote).where(
            WikiNote.project_id == project_id,
            WikiNote.title.ilike(title.strip()),
        )
        note = (await session.execute(stmt)).scalar_one_or_none()
        if note:
            note.body = body.strip()
            note.tags = tags.strip()
            if created_by_agent_id:
                note.created_by_agent_id = created_by_agent_id
        else:
            note = WikiNote(
                id=generate_id("mem"),
                project_id=project_id,
                title=title.strip(),
                body=body.strip(),
                tags=tags.strip(),
                created_by_agent_id=created_by_agent_id,
            )
            session.add(note)
        await session.commit()
        await session.refresh(note)
        return note


async def search_memory(query: str = "", project_id: Optional[str] = None, limit: int = 30):
    """Return company-wide notes plus notes scoped to the selected project."""
    terms = [term for term in query.lower().split() if term]
    async with async_session_factory() as session:
        stmt = select(WikiNote).where(
            or_(WikiNote.project_id.is_(None), WikiNote.project_id == project_id)
        ).order_by(WikiNote.updated_at.desc()).limit(500)
        notes = (await session.execute(stmt)).scalars().all()
        if terms:
            notes = [
                note for note in notes
                if all(term in (note.title + " " + note.body + " " + note.tags).lower() for term in terms)
            ]
        return notes[:max(1, min(limit, 100))]
