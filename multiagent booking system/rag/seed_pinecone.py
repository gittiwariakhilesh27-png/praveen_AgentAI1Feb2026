import time
from typing import List, Optional

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


class TravelKnowledgeStore:
    """Wraps a Pinecone index with travel-domain knowledge for RAG retrieval."""

    def __init__(
        self,
        openai_api_key: str,
        pinecone_api_key: str,
        index_name: str = "travel-knowledge",
    ):
        self.openai_api_key = openai_api_key
        self.pinecone_api_key = pinecone_api_key
        self.index_name = index_name
        self._vector_store = None

        self.embeddings = OpenAIEmbeddings(
            api_key=openai_api_key,
            model="text-embedding-3-small",  # 1536-dim, fast and cost-effective
        )

    # ------------------------------------------------------------------
    # Connection / index management
    # ------------------------------------------------------------------

    def connect(self) -> "TravelKnowledgeStore":
        """Initialise the Pinecone client and ensure the index exists."""
        from pinecone import Pinecone, ServerlessSpec
        from langchain_pinecone import PineconeVectorStore

        pc = Pinecone(api_key=self.pinecone_api_key)

        existing = [idx.name for idx in pc.list_indexes()]
        if self.index_name not in existing:
            print(f"[Pinecone] Creating index '{self.index_name}' …")
            pc.create_index(
                name=self.index_name,
                dimension=1536,          # matches text-embedding-3-small
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            # Wait until the index is ready
            while not pc.describe_index(self.index_name).status["ready"]:
                time.sleep(1)
            print(f"[Pinecone] Index '{self.index_name}' is ready.")

        self._vector_store = PineconeVectorStore(
            index=pc.Index(self.index_name),
            embedding=self.embeddings,
        )
        return self

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_documents(self, documents: List[Document]) -> None:
        """Embed and upsert a list of LangChain Documents into Pinecone."""
        if self._vector_store is None:
            self.connect()
        self._vector_store.add_documents(documents)
        print(f"[Pinecone] Upserted {len(documents)} documents.")

    # ------------------------------------------------------------------
    # Read / Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 4) -> List[Document]:
        """Return the top-k most relevant documents for *query*."""
        if self._vector_store is None:
            self.connect()
        return self._vector_store.similarity_search(query, k=top_k)

    def retrieve_with_score(self, query: str, top_k: int = 4):
        """Return (Document, score) tuples for *query*."""
        if self._vector_store is None:
            self.connect()
        return self._vector_store.similarity_search_with_score(query, k=top_k)

    def is_ready(self) -> bool:
        return self._vector_store is not None


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rag.travel_knowledge import TRAVEL_DOCUMENTS

    openai_key = os.environ["OPENAI_API_KEY"]
    pinecone_key = os.environ["PINECONE_API_KEY"]
    index_name = os.environ.get("PINECONE_INDEX_NAME", "travel-knowledge")

    print(f"[Seed] Connecting to Pinecone index '{index_name}' …")
    store = TravelKnowledgeStore(openai_key, pinecone_key, index_name)
    store.connect()

    print(f"[Seed] Upserting {len(TRAVEL_DOCUMENTS)} documents …")
    store.upsert_documents(TRAVEL_DOCUMENTS)
    print("[Seed] Done.")
