"""Grok teammate: classify, ask for documents, propose work, help plan."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agora.constants import TaskStatus
from agora.models import ChatMessage, Project, User
from agora.services import xai
from agora.services.snapshot import capture_state, write_state_file
from agora.services.tasks import create_task
from agora.settings import Settings

BOT_EMAIL = "grok@office.agora"
BOT_NAME = "Grok"

SYSTEM_PROMPT = """Tu es Grok, membre de l'équipe Office Agora (famille Leyssens + collègues).
Tu parles français, tu es concis, concret, jamais corporate.
À partir de l'état JSON du projet tu dois :
1. Classer la situation (1-2 phrases).
2. Lister les documents ou infos manquantes (bullet points).
3. Proposer 2 à 4 activités concrètes pour aujourd'hui / cette semaine.
4. Aider à planifier le kick-off (idées, finance, SWOT, sélection de projets).
N'invente pas de fichiers qui n'existent pas. Signe simplement — Grok."""


def get_bot(session: Session) -> User | None:
    return session.scalar(select(User).where(User.email == BOT_EMAIL, User.is_bot.is_(True)))


def heuristic_reply(state: dict, question: str) -> str:
    projects = state.get("projects") or []
    if not projects:
        return "Je ne vois encore aucun projet. Créez-en un, je m’y mets."
    project = projects[0]
    gaps = project.get("gaps") or []
    suggestions = project.get("suggestions") or []
    tasks = project.get("tasks") or []
    open_tasks = [t for t in tasks if t["status"] != TaskStatus.DONE.value]
    lines = [
        f"État de **{project['name']}** : {len(open_tasks)} tâche(s) ouverte(s), "
        f"{len(project.get('files') or [])} fichier(s), "
        f"{len(project.get('recent_chat') or [])} message(s).",
        "",
    ]
    if question.strip():
        lines.append(f"Tu as demandé : « {question.strip()[:240]} »")
        lines.append("")
    lines.append("**À classer / à clarifier**")
    if gaps:
        lines.extend(f"- {gap}" for gap in gaps)
    else:
        lines.append("- Rien de bloquant, on peut avancer.")
    lines.append("")
    lines.append("**Documents / infos utiles**")
    lines.append("- Notes du kick-off (ordre du jour, décisions)")
    lines.append("- Brouillon SWOT")
    lines.append("- Chiffres ou questions finance")
    lines.append("- Liste des projets à garder, fusionner ou écarter")
    lines.append("")
    lines.append("**Activités proposées**")
    if suggestions:
        for item in suggestions:
            lines.append(f"- {item['title']} — {item['description']}")
    else:
        lines.append("- Continuer les tâches déjà ouvertes.")
    lines.append("")
    lines.append("Écris @Grok avec une question, ou clique **Grok** pour un nouveau briefing.")
    return "\n".join(lines)


def _should_create_tasks(question: str) -> bool:
    text = question.lower()
    return "crée" in text and "tâche" in text


def apply_suggestions(session: Session, *, project: Project, actor: User, state: dict) -> list[str]:
    created: list[str] = []
    block = next((p for p in state["projects"] if p["id"] == project.id), None)
    if block is None:
        return created
    existing = {t.title.lower() for t in project.tasks}
    for item in block.get("suggestions") or []:
        if item["title"].lower() in existing:
            continue
        create_task(
            session,
            project_id=project.id,
            actor=actor,
            title=item["title"],
            description=item["description"],
            status=TaskStatus.TODO.value,
        )
        created.append(item["title"])
        existing.add(item["title"].lower())
    return created


def respond(
    session: Session,
    *,
    settings: Settings,
    project: Project,
    question: str = "",
    create_tasks: bool = False,
) -> ChatMessage:
    bot = get_bot(session)
    if bot is None:
        raise RuntimeError("Utilisateur Grok absent — relancez le seed.")
    state = capture_state(session)
    write_state_file(session, settings)
    body = heuristic_reply(state, question)
    if settings.xai_api_key:
        try:
            body = xai.complete(
                settings,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": "État JSON :\n"
                        + str(state)[:12000]
                        + "\n\nQuestion de l'équipe :\n"
                        + (question.strip() or "(briefing, pas de question)"),
                    },
                ],
            )
        except RuntimeError:
            body = heuristic_reply(state, question)
            body += "\n\n_(réponse locale : clé xAI absente ou API injoignable)_"
    if create_tasks or _should_create_tasks(question):
        made = apply_suggestions(session, project=project, actor=bot, state=state)
        if made:
            body += "\n\nJ’ai créé : " + ", ".join(made) + "."
    message = ChatMessage(project_id=project.id, author_id=bot.id, body=body[:4000])
    session.add(message)
    session.flush()
    return message
