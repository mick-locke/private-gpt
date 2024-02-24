import os
import logging
import traceback

from pathlib import Path
from typing import Literal, Optional, List

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status, Security, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from private_gpt.users import crud, models, schemas
from private_gpt.users.api import deps
from private_gpt.users.constants.role import Role

from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.server.ingest.model import IngestedDoc
from private_gpt.server.utils.auth import authenticated
from private_gpt.constants import UPLOAD_DIR

ingest_router = APIRouter(prefix="/v1", dependencies=[Depends(authenticated)])

logger = logging.getLogger(__name__)
class IngestTextBody(BaseModel):
    file_name: str = Field(examples=["Avatar: The Last Airbender"])
    text: str = Field(
        examples=[
            "Avatar is set in an Asian and Arctic-inspired world in which some "
            "people can telekinetically manipulate one of the four elements—water, "
            "earth, fire or air—through practices known as 'bending', inspired by "
            "Chinese martial arts."
        ]
    )


class IngestResponse(BaseModel):
    object: Literal["list"]
    model: Literal["private-gpt"]
    data: list[IngestedDoc]

class DeleteFilename(BaseModel):
    filename: str

@ingest_router.post("/ingest", tags=["Ingestion"], deprecated=True)
def ingest(request: Request, file: UploadFile) -> IngestResponse:
    """Ingests and processes a file.

    Deprecated. Use ingest/file instead.
    """
    return ingest_file(request, file)


@ingest_router.post("/ingest/file1", tags=["Ingestion"])
def ingest_file(request: Request, file: UploadFile = File(...)) -> IngestResponse:
    """Ingests and processes a file, storing its chunks to be used as context.

    The context obtained from files is later used in
    `/chat/completions`, `/completions`, and `/chunks` APIs.

    Most common document
    formats are supported, but you may be prompted to install an extra dependency to
    manage a specific file type.

    A file can generate different Documents (for example a PDF generates one Document
    per page). All Documents IDs are returned in the response, together with the
    extracted Metadata (which is later used to improve context retrieval). Those IDs
    can be used to filter the context used to create responses in
    `/chat/completions`, `/completions`, and `/chunks` APIs.
    """
    service = request.state.injector.get(IngestService)
    if file.filename is None:
        raise HTTPException(400, "No file name provided")
    upload_path = Path(f"{UPLOAD_DIR}/{file.filename}")
    try:
        with open(upload_path, "wb") as f:
            f.write(file.file.read())
        with open(upload_path, "rb") as f:
            ingested_documents = service.ingest_bin_data(file.filename, f)
    except Exception as e:
        return {"message": f"There was an error uploading the file(s)\n {e}"}
    finally:
        file.file.close()
    return IngestResponse(object="list", model="private-gpt", data=ingested_documents)
    

@ingest_router.post("/ingest/text", tags=["Ingestion"])
def ingest_text(request: Request, body: IngestTextBody) -> IngestResponse:
    """Ingests and processes a text, storing its chunks to be used as context.

    The context obtained from files is later used in
    `/chat/completions`, `/completions`, and `/chunks` APIs.

    A Document will be generated with the given text. The Document
    ID is returned in the response, together with the
    extracted Metadata (which is later used to improve context retrieval). That ID
    can be used to filter the context used to create responses in
    `/chat/completions`, `/completions`, and `/chunks` APIs.
    """
    service = request.state.injector.get(IngestService)
    if len(body.file_name) == 0:
        raise HTTPException(400, "No file name provided")
    ingested_documents = service.ingest_text(body.file_name, body.text)
    return IngestResponse(object="list", model="private-gpt", data=ingested_documents)


@ingest_router.get("/ingest/list", tags=["Ingestion"])
def list_ingested(request: Request) -> IngestResponse:
    """Lists already ingested Documents including their Document ID and metadata.

    Those IDs can be used to filter the context used to create responses
    in `/chat/completions`, `/completions`, and `/chunks` APIs.
    """
    service = request.state.injector.get(IngestService)
    ingested_documents = service.list_ingested()
    return IngestResponse(object="list", model="private-gpt", data=ingested_documents)


@ingest_router.delete("/ingest/{doc_id}", tags=["Ingestion"])
def delete_ingested(request: Request, doc_id: str) -> None:
    """Delete the specified ingested Document.

    The `doc_id` can be obtained from the `GET /ingest/list` endpoint.
    The document will be effectively deleted from your storage context.
    """
    service = request.state.injector.get(IngestService)
    service.delete(doc_id)


@ingest_router.post("/ingest/file/delete", tags=["Ingestion"])
def delete_file(
        request: Request,
        delete_input: DeleteFilename,
        log_audit: models.Audit = Depends(deps.get_audit_logger),
        db: Session = Depends(deps.get_db),
        current_user: models.User = Security(
            deps.get_current_user,
            scopes=[Role.ADMIN["name"], Role.SUPER_ADMIN["name"]],

        )) -> dict:
    """Delete the specified filename.

    The `filename` can be obtained from the `GET /ingest/list` endpoint.
    The document will be effectively deleted from your storage context.
    """
    filename = delete_input.filename    
    service = request.state.injector.get(IngestService)
    try:
        doc_ids = service.get_doc_ids_by_filename(filename)
        if not doc_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"No documents found with filename '{filename}'")

        for doc_id in doc_ids:
            service.delete(doc_id)
        try:
            upload_path = Path(f"{UPLOAD_DIR}/{filename}")
            os.remove(upload_path)
        except:
            print("Unable to delete file from the static directory")
        document = crud.documents.get_by_filename(db,file_name=filename)
        if document:
            log_audit(model='Document', action='delete',
                      details={"status": "SUCCESS", "message": f"{filename}' successfully deleted."}, user_id=current_user.id)
            crud.documents.remove(db=db, id=document.id)
        return {"status": "SUCCESS", "message": f"{filename}' successfully deleted."}
    except Exception as e:
        print(traceback.print_exc())
        logger.error(
            f"Unexpected error deleting documents with filename '{filename}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@ingest_router.post("/ingest/file", response_model=IngestResponse, tags=["Ingestion"])
def ingest_file(
        request: Request,
        log_audit: models.Audit = Depends(deps.get_audit_logger),

        db: Session = Depends(deps.get_db),
        file: UploadFile = File(...),
        current_user: models.User = Security(
            deps.get_current_user,
            scopes=[Role.ADMIN["name"], Role.SUPER_ADMIN["name"]],
        )) -> IngestResponse:
    """Ingests and processes a file, storing its chunks to be used as context."""
    service = request.state.injector.get(IngestService)
    print("-------------------------------------->",file)
    try:
        file_ingested = crud.documents.get_by_filename(db, file_name=file.filename)
        if file_ingested:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File already exists. Choose a different file.",
            )
        
        if file.filename is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file name provided",
            )

        try:
            docs_in = schemas.DocumentCreate(filename=file.filename, uploaded_by=current_user.id, department_id=current_user.department_id)
            crud.documents.create(db=db, obj_in=docs_in)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to upload file.",
            )
        upload_path = Path(f"{UPLOAD_DIR}/{file.filename}")

        with open(upload_path, "wb") as f:
            f.write(file.file.read())

        with open(upload_path, "rb") as f:
            ingested_documents = service.ingest_bin_data(file.filename, f)
        logger.info(f"{file.filename} is uploaded by the {current_user.fullname}.")
        response = IngestResponse(
            object="list", model="private-gpt", data=ingested_documents)
        log_audit(model='Document', action='create',
                  details={
                      'status': '200',
                      'filename': file.filename,
                      'user': current_user.fullname,
                  }, user_id=current_user.id)
        return response
    except HTTPException:
        print(traceback.print_exc())
        raise

    except Exception as e:
        print(traceback.print_exc())
        log_audit(model='Document', action='create',
                  details={"status": 500, "detail": "Internal Server Error: Unable to ingest file.", }, user_id=current_user.id)
        logger.error(f"There was an error uploading the file(s): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error: Unable to ingest file.",
        )


async def common_ingest_logic(
    request: Request,
    
    db: Session,
    ocr_file,
    current_user,
):
    service = request.state.injector.get(IngestService)
    log_audit: models.Audit = Depends(deps.get_audit_logger)
    try:
        with open(ocr_file, 'rb') as file:
            file_name = Path(ocr_file).name
            upload_path = Path(f"{UPLOAD_DIR}/{file_name}")

            file_ingested = crud.documents.get_by_filename(
                db, file_name=file_name)
            if file_ingested:
                raise HTTPException(
                    status_code=409,
                    detail="File already exists. Choose a different file.",
                )

            if file_name is None:
                raise HTTPException(
                    status_code=400,
                    detail="No file name provided",
                )

            docs_in = schemas.DocumentCreate(
                filename=file_name, uploaded_by=current_user.id, department_id=current_user.department_id)
            crud.documents.create(db=db, obj_in=docs_in)

            with open(upload_path, "wb") as f:
                f.write(file.read())
            file.seek(0)  # Move the file pointer back to the beginning
            ingested_documents = service.ingest_bin_data(file_name, file)
            log_audit(model='Document', action='create',
                      details={'status': 200, 'message': "file uploaded successfully."}, user_id=current_user.id)

        logger.info(
            f"{file_name} is uploaded by the {current_user.fullname}.")

        return ingested_documents

    except HTTPException:
        print(traceback.print_exc())
        raise

    except Exception as e:
        print(traceback.print_exc())
        log_audit(model='Document', action='create',
                  details={"status": 500, "detail": "Internal Server Error: Unable to ingest file.", }, user_id=current_user.id)
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error: Unable to ingest file.",
        )
