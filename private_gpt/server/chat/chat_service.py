from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from injector import inject, singleton
from llama_index import ServiceContext, StorageContext, VectorStoreIndex
from llama_index.chat_engine import ContextChatEngine
from llama_index.indices.vector_store import VectorIndexRetriever
from llama_index.llm_predictor.utils import stream_chat_response_to_tokens
from llama_index.llms import ChatMessage
from llama_index.types import TokenGen

from private_gpt.llm.llm_service import LLMService
from private_gpt.node_store.node_store_service import NodeStoreService
from private_gpt.node_store.node_utils import get_context_nodes
from private_gpt.open_ai.extensions.context_files import ContextFiles
from private_gpt.vector_store.vector_store_service import VectorStoreService

if TYPE_CHECKING:
    from llama_index.chat_engine.types import (
        AgentChatResponse,
        StreamingAgentChatResponse,
    )


@singleton
class ChatService:
    @inject
    def __init__(
        self,
        llm_service: LLMService,
        vector_store_service: VectorStoreService,
        node_store_service: NodeStoreService,
    ) -> None:
        self.llm_service = llm_service
        self.vector_store_service = vector_store_service
        self.node_store_service = node_store_service
        self.storage_context = StorageContext.from_defaults(
            vector_store=vector_store_service.vector_store,
            docstore=node_store_service.doc_store,
            index_store=node_store_service.index_store,
        )
        self.service_context = ServiceContext.from_defaults(
            llm=llm_service.llm, embed_model="local"
        )
        self.index = VectorStoreIndex.from_vector_store(
            self.vector_store_service.vector_store,
            storage_context=self.storage_context,
            service_context=self.service_context,
            show_progress=True,
        )

    def _chat_with_contex(
        self,
        message: str,
        context_files: ContextFiles,
        chat_history: Sequence[ChatMessage] | None = None,
        streaming: bool = False,
    ) -> Any:
        node_ids = get_context_nodes(context_files, self.storage_context.docstore)
        vector_index_retriever = VectorIndexRetriever(
            index=self.index, node_ids=node_ids
        )
        chat_engine = ContextChatEngine.from_defaults(
            retriever=vector_index_retriever,
            service_context=self.service_context,
        )
        if streaming:
            result = chat_engine.stream_chat(message, chat_history)
        else:
            result = chat_engine.chat(message, chat_history)
        return result

    def stream_chat(
        self,
        messages: list[ChatMessage],
        context_files: ContextFiles | None = None,
    ) -> TokenGen:
        if context_files:
            last_message = messages[-1].content
            response: StreamingAgentChatResponse = self._chat_with_contex(
                message=last_message if last_message is not None else "",
                chat_history=messages[:-1],
                context_files=context_files,
                streaming=True,
            )
            response_gen = response.response_gen
        else:
            stream = self.llm_service.llm.stream_chat(messages)
            response_gen = stream_chat_response_to_tokens(stream)
        return response_gen

    def chat(
        self,
        messages: list[ChatMessage],
        context_files: ContextFiles | None = None,
    ) -> str:
        if context_files:
            last_message = messages[-1].content
            wrapped_response: AgentChatResponse = self._chat_with_contex(
                message=last_message if last_message is not None else "",
                chat_history=messages[:-1],
                context_files=context_files,
                streaming=False,
            )
            response = wrapped_response.response
        else:
            chat_response = self.llm_service.llm.chat(messages)
            response_content = chat_response.message.content
            response = response_content if response_content is not None else ""
        return response
