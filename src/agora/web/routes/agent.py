"""AGENT tab: raw crawl table, math scores, heuristic tasks (no Qwen yet)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from agora.services.immo import bot_running, fetch_listings, heuristic_tasks, scored_listings
from agora.web.deps import get_db, require_project, shell_context
from agora.web.templating import render
from agora.web.urls import redirect

router = APIRouter(tags=["agent"])


def _paths(request: Request) -> tuple[Path, Path]:
    settings = request.app.state.settings
    return settings.crawl_db_path, settings.crawl_state_path


@router.get("/projects/{project_id}/agent")
def agent_index(project_id: int, request: Request, loaded=Depends(require_project)):
    project, _membership, _user = loaded
    return redirect(request, f"/projects/{project.id}/agent/brut")


@router.get("/projects/{project_id}/agent/brut")
def agent_raw(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    listing_type: str = Query(""),
    property_type: str = Query(""),
    city: str = Query(""),
    postal_code: str = Query(""),
    q: str = Query(""),
    sort: str = Query("last_seen"),
    direction: str = Query("desc"),
):
    project, membership, user = loaded
    crawl_db, state_path = _paths(request)
    rows, total = fetch_listings(
        crawl_db,
        listing_type=listing_type,
        property_type=property_type,
        city=city,
        postal_code=postal_code,
        q=q,
        sort=sort,
        direction=direction,
        limit=80,
    )
    return render(
        request,
        "projects/agent.html",
        project=project,
        membership=membership,
        active_tab="agent",
        agent_sub="brut",
        rows=rows,
        total=total,
        bot_status=bot_running(state_path),
        filters={
            "listing_type": listing_type,
            "property_type": property_type,
            "city": city,
            "postal_code": postal_code,
            "q": q,
            "sort": sort,
            "direction": direction,
        },
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/agent/analyse")
def agent_analyse(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
    listing_type: str = Query(""),
    city: str = Query(""),
):
    project, membership, user = loaded
    crawl_db, state_path = _paths(request)
    ranked, total, stats = scored_listings(crawl_db, listing_type=listing_type, city=city)
    return render(
        request,
        "projects/agent.html",
        project=project,
        membership=membership,
        active_tab="agent",
        agent_sub="analyse",
        ranked=ranked,
        total=total,
        stats=stats,
        bot_status=bot_running(state_path),
        filters={"listing_type": listing_type, "city": city},
        **shell_context(request, db, user),
    )


@router.get("/projects/{project_id}/agent/taches")
def agent_tasks(
    request: Request,
    db: Session = Depends(get_db),
    loaded=Depends(require_project),
):
    project, membership, user = loaded
    crawl_db, state_path = _paths(request)
    ranked, _total, _stats = scored_listings(crawl_db)
    return render(
        request,
        "projects/agent.html",
        project=project,
        membership=membership,
        active_tab="agent",
        agent_sub="taches",
        tasks=heuristic_tasks(ranked),
        bot_status=bot_running(state_path),
        qwen_ready=False,
        **shell_context(request, db, user),
    )
