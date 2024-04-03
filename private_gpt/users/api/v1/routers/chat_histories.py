import logging
import traceback

from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, HTTPException, status, Security

from private_gpt.users.api import deps
from private_gpt.users.constants.role import Role
from private_gpt.users import crud, models, schemas

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/c", tags=["Chat Histories"])


@router.get("", response_model=list[schemas.ChatBase])
def list_chat_histories(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Security(
        deps.get_current_user,
    ),
) -> list[schemas.ChatBase]:
    """
    Retrieve a list of chat histories with pagination support.
    """
    try:
        chat_histories = crud.chat.get_multi(
            db, skip=skip, limit=limit, user_id=current_user.id)
        return chat_histories
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error listing chat histories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@router.post("/create", response_model=schemas.ChatBase)
def create_chat_history(
    chat_history_in: schemas.ChatCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Security(
        deps.get_current_user,
    ),
) -> schemas.ChatBase:
    """
    Create a new chat history
    """
    try:
        chat_history = crud.chat.create(
            db=db, obj_in=chat_history_in, user_id=current_user.id)
        return chat_history
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error creating chat history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@router.get("/{chat_history_id}", response_model=schemas.ChatMessages)
def read_chat_history(
    chat_history_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Security(
        deps.get_current_user,
    ),
) -> schemas.ChatMessages:
    """
    Read a chat history by ID
    """
    try:
        chat_history = crud.chat.get_by_id(db, id=chat_history_id)
        if chat_history is None or chat_history.user_id != current_user.id:
            raise HTTPException(
                status_code=404, detail="Chat history not found")
        return chat_history
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error reading chat history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@router.post("/conversation", response_model=schemas.ChatHistory)
def conversation(
    chat_history_in: schemas.ChatUpdate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Security(
        deps.get_current_user,
    ),
) -> schemas.ChatHistory:
    """
    Update a chat history by ID
    """
    try:
        chat_history = crud.chat.get_by_id(
            db, id=chat_history_in.conversation_id)
        if chat_history is None or chat_history.user_id != current_user.id:
            raise HTTPException(
                status_code=404, detail="Chat history not found")

        updated_chat_history = crud.chat.update_messages(
            db=db, db_obj=chat_history, obj_in=chat_history_in)

        return updated_chat_history
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error updating chat history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@router.post("/delete")
def delete_chat_history(
    chat_history_in: schemas.ChatDelete,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Security(
        deps.get_current_user,
    ),
):
    """
    Delete a chat history by ID
    """
    try:
        chat_history_id = chat_history_in.id
        chat_history = crud.chat.get(db, id=chat_history_id)
        if chat_history is None or chat_history.user_id != current_user.id:
            raise HTTPException(
                status_code=404, detail="Chat history not found")

        crud.chat.remove(db=db, id=chat_history_id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Chat history deleted successfully",
            },
        )
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Error deleting chat history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )