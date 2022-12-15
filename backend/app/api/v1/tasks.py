# -*- coding: utf-8 -*-
import random
from typing import Any
from uuid import UUID

from app.api import deps
from app.schemas import protocol as protocol_schema
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security.api_key import APIKey
from loguru import logger
from sqlmodel import Session
from starlette.status import HTTP_400_BAD_REQUEST

router = APIRouter()


def generate_task(request: protocol_schema.TaskRequest) -> protocol_schema.Task:
    match (request.type):
        case protocol_schema.TaskRequestType.generic:
            logger.info("Frontend requested a generic task.")
            while request.type == protocol_schema.TaskRequestType.generic:
                request.type = random.choice(list(protocol_schema.TaskRequestType)).value
            return generate_task(request)
        case protocol_schema.TaskRequestType.summarize_story:
            logger.info("Generating a SummarizeStoryTask.")
            task = protocol_schema.SummarizeStoryTask(
                story="This is a story. A very long story. So long, it needs to be summarized.",
            )
        case protocol_schema.TaskRequestType.rate_summary:
            logger.info("Generating a RateSummaryTask.")
            task = protocol_schema.RateSummaryTask(
                full_text="This is a story. A very long story. So long, it needs to be summarized.",
                summary="This is a summary.",
                scale=protocol_schema.RatingScale(min=1, max=5),
            )
        case _:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Invalid request type.",
            )
    logger.info(f"Generated {task=}.")
    if request.user_id is not None:
        task.addressed_users = [request.user_id]

    return task


@router.post("/", response_model=protocol_schema.AnyTask)  # work with Union once more types are added
def request_task(
    *,
    db: Session = Depends(deps.get_db),
    api_key: APIKey = Depends(deps.get_api_key),
    request: protocol_schema.TaskRequest,
) -> Any:
    """
    Create new task.
    """
    deps.api_auth(api_key, db, create=True)

    try:
        task = generate_task(request)
        # TODO: store task in database
    except Exception:
        logger.exception("Failed to generate task.")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
        )
    return task


@router.post("/{task_id}/ack")
def acknowledge_task(
    *,
    db: Session = Depends(deps.get_db),
    api_key: APIKey = Depends(deps.get_api_key),
    task_id: UUID,
    response: protocol_schema.AnyTaskResponse,
) -> Any:
    """
    The frontend acknowledges a task.
    """
    deps.api_auth(api_key, db, create=True)

    match (type(response)):
        case protocol_schema.PostCreatedTaskResponse:
            logger.info(f"Frontend acknowledged {task_id=} and created {response.post_id=}.")
            # here we would store the post id in the database for the task
        case protocol_schema.RatingCreatedTaskResponse:
            logger.info(f"Frontend acknowledged {task_id=} for {response.post_id=}.")
            # here we would store the rating id in the database for the task
        case _:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Invalid response type.",
            )

    return {}


@router.post("/interaction")
def post_interaction(
    *,
    db: Session = Depends(deps.get_db),
    api_key: APIKey = Depends(deps.get_api_key),
    interaction: protocol_schema.AnyInteraction,
) -> Any:
    """
    The frontend reports an interaction.
    """
    deps.api_auth(api_key, db, create=True)

    match (type(interaction)):
        case protocol_schema.TextReplyToPost:
            logger.info(
                f"Frontend reports text reply to {interaction.post_id=} with {interaction.text=} by {interaction.user_id=}."
            )
            # here we would store the text reply in the database
            return protocol_schema.TaskDone(
                reply_to_post_id=interaction.user_post_id,
                addressed_users=[interaction.user_id],
            )
        case protocol_schema.PostRating:
            logger.info(
                f"Frontend reports rating of {interaction.post_id=} with {interaction.rating=} by {interaction.user_id=}."
            )
            # here we would store the rating in the database
            return protocol_schema.TaskDone(
                reply_to_post_id=interaction.post_id,
                addressed_users=[interaction.user_id],
            )
        case _:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Invalid response type.",
            )
