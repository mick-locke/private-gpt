"""FastAPI app creation, logger configuration and main API routes."""
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from llama_index.llms import LlamaCPP
from llama_index.llms.llama_utils import completion_to_prompt, messages_to_prompt
from loguru import logger
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from src.api.models import OpenAICompletion
from src.api.types import HealthRouteOutput, HelloWorldRouteInput, HelloWorldRouteOutput
from src.constants import PROJECT_ROOT_PATH

# Remove pre-configured logging handler
logger.remove(0)
# Create a new logging handler same as the pre-configured one but with the extra
# attribute `request_id`
logger.add(
    sys.stdout,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "ID: {extra[request_id]} - <level>{message}</level>"
    ),
)

app = FastAPI()


@app.get("/health")
def health_check_route() -> HealthRouteOutput:
    """Health check route to check that the API is up.

    Returns:
        a dict with a "status" key
    """
    return HealthRouteOutput(status="ok")


@app.post("/hello-world")
def hello_world(
        hello_world_input: HelloWorldRouteInput,
) -> HelloWorldRouteOutput:
    """Says hello to the name provided in the input.

    Args:
        hello_world_input: a dict with a "name" key

    Returns:
        a dict with a "message" key
    """
    with logger.contextualize(request_id=uuid.uuid4().hex):
        response_message = f"Hello, {hello_world_input.name}!"
        logger.info(f"Responding '{response_message}'")
        return HelloWorldRouteOutput(message=response_message)


llms = {}


@asynccontextmanager
async def _lifespan():
    models_folder = PROJECT_ROOT_PATH.joinpath("models")
    llms["llama"] = LlamaCPP(
        # model_url="https://huggingface.co/TheBloke/Llama-2-7B-chat-GGUF/resolve/main/llama-2-7b-chat.Q4_0.gguf",
        model_path=f"{models_folder.absolute()}/llama-2-7b-chat.Q4_0.gguf",
        temperature=0.1,
        max_new_tokens=256,
        # llama2 has a context window of 4096 tokens,
        # but we set it lower to allow for some wiggle room
        context_window=3900,
        # kwargs to pass to __call__()
        generate_kwargs={},
        # kwargs to pass to __init__()
        # set to at least 1 to use GPU
        model_kwargs={"n_gpu_layers": 1},
        # transform inputs into Llama2 format
        messages_to_prompt=messages_to_prompt,
        completion_to_prompt=completion_to_prompt,
        verbose=True,
    )
    yield


app = FastAPI(lifespan=_lifespan)


def _run_llm(prompt: str) -> AsyncGenerator:
    llm: LlamaCPP = llms["llama"]
    truncated_prompt = prompt[:llm.context_window]
    response_iter = llm.stream_complete(truncated_prompt)
    for response in response_iter:
        yield f"data: {OpenAICompletion.simple_json_delta(text=response.delta)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/health")
def root() -> str:
    return "ok"


class InferenceBody(BaseModel):
    prompt: str


@app.post("/")
async def inference(body: InferenceBody) -> StreamingResponse:
    return StreamingResponse(_run_llm(body.prompt), media_type="text/event-stream")
