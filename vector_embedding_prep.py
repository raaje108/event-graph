"""
Tokenization & Vector Embedding Preparation Module
--------------------------------------------------
This module:
1. Tokenizes the cleaned preprocessed corpus and builds a vocabulary index.
2. Performs Semantic / Sliding Window Chunking optimized for Vector Stores (Chroma, FAISS, Pinecone) & RAG.
3. Computes Dense Vector Embeddings (TF-IDF / SVD / Dense representation) with Cosine Similarity Search.
4. Prepares an ingestion-ready payload with embeddings, metadata, and token IDs.
"""

import math
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import DEFAULT_PIPELINE_CONFIG


class SVBVectorEmbeddingPreparer:
    """
    Arranges tokenized and preprocessed SVB collapse datasets into
    vector embedding structures suitable for modern Vector Databases and RAG pipelines.
    """

    def __init__(
        self,
        chunk_word_size: int = DEFAULT_PIPELINE_CONFIG["chunk_word_size"],
        chunk_overlap: int = DEFAULT_PIPELINE_CONFIG["chunk_overlap"],
        min_chunk_tokens: int = DEFAULT_PIPELINE_CONFIG["min_chunk_tokens"]
    ):
        self.chunk_word_size = chunk_word_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_tokens = min_chunk_tokens
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=2500,
            sublinear_tf=True
        )
        self.is_fitted = False
        self.vocab_to_id: Dict[str, int] = {}
        self.id_to_vocab: Dict[int, str] = {}
        self.chunk_records: List[Dict[str, Any]] = []
        self.embedding_matrix: Optional[np.ndarray] = None

    def build_vocabulary(self, preprocessed_records: List[Dict[str, Any]]) -> None:
        """Constructs unique vocabulary mapping and token index lookup."""
        unique_tokens = set()
        for rec in preprocessed_records:
            for token in rec.get("tokens", []):
                unique_tokens.add(token.lower())

        sorted_tokens = sorted(list(unique_tokens))
        self.vocab_to_id = {token: idx + 1 for idx, token in enumerate(sorted_tokens)}
        # Add special padding and unknown tokens
        self.vocab_to_id["[PAD]"] = 0
        self.vocab_to_id["[UNK]"] = len(self.vocab_to_id)
        self.id_to_vocab = {idx: token for token, idx in self.vocab_to_id.items()}
        logging.info(f"Built token vocabulary containing {len(self.vocab_to_id)} distinct tokens.")

    def tokens_to_ids(self, tokens: List[str]) -> List[int]:
        """Encodes token strings into numerical token IDs."""
        unk_id = self.vocab_to_id.get("[UNK]", 999999)
        return [self.vocab_to_id.get(t.lower(), unk_id) for t in tokens]

    def create_semantic_chunks(self, preprocessed_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Groups paragraphs per source and creates overlapping sliding-window chunks
        for optimal vector embedding retrieval (RAG).
        """
        if not self.vocab_to_id:
            self.build_vocabulary(preprocessed_records)

        # Group records by source document
        grouped_by_source: Dict[str, List[Dict[str, Any]]] = {}
        for rec in preprocessed_records:
            src = rec.get("source_url", "default")
            grouped_by_source.setdefault(src, []).append(rec)

        chunk_id = 1
        all_chunks = []

        for src_url, recs in grouped_by_source.items():
            first_rec = recs[0]
            publisher = first_rec.get("publisher", "Unknown")
            title = first_rec.get("source_title", "SVB Article")
            category = first_rec.get("category", "General")

            # Combine tokens across paragraphs of the same document
            doc_tokens = []
            doc_raw_sentences = []
            for r in recs:
                doc_tokens.extend(r.get("tokens", []))
                doc_raw_sentences.append(r.get("raw_text", ""))

            # Sliding window chunking
            step = max(1, self.chunk_word_size - self.chunk_overlap)
            total_tokens = len(doc_tokens)

            if total_tokens <= self.chunk_word_size:
                # Document fits within one chunk
                chunk_token_list = doc_tokens
                cleaned_chunk_text = " ".join(chunk_token_list)
                raw_chunk_text = " ".join(doc_raw_sentences)
                token_ids = self.tokens_to_ids(chunk_token_list)

                chunk_payload = {
                    "chunk_id": f"svb_chunk_{chunk_id:04d}",
                    "chunk_index": 1,
                    "publisher": publisher,
                    "source_title": title,
                    "source_url": src_url,
                    "category": category,
                    "raw_text": raw_chunk_text,
                    "cleaned_text": cleaned_chunk_text,
                    "token_count": len(chunk_token_list),
                    "char_count": len(cleaned_chunk_text),
                    "tokens": chunk_token_list,
                    "token_ids": token_ids,
                    "metadata": {
                        "source": publisher,
                        "title": title,
                        "url": src_url,
                        "category": category,
                        "token_count": len(chunk_token_list)
                    }
                }
                all_chunks.append(chunk_payload)
                chunk_id += 1
            else:
                chunk_idx_in_doc = 1
                for start_idx in range(0, total_tokens, step):
                    end_idx = min(start_idx + self.chunk_word_size, total_tokens)
                    chunk_token_list = doc_tokens[start_idx:end_idx]

                    if len(chunk_token_list) < self.min_chunk_tokens and all_chunks:
                        # Skip tiny trailing chunks
                        continue

                    cleaned_chunk_text = " ".join(chunk_token_list)
                    token_ids = self.tokens_to_ids(chunk_token_list)

                    chunk_payload = {
                        "chunk_id": f"svb_chunk_{chunk_id:04d}",
                        "chunk_index": chunk_idx_in_doc,
                        "publisher": publisher,
                        "source_title": title,
                        "source_url": src_url,
                        "category": category,
                        "raw_text": cleaned_chunk_text,  # Cleaned representation with provenance
                        "cleaned_text": cleaned_chunk_text,
                        "token_count": len(chunk_token_list),
                        "char_count": len(cleaned_chunk_text),
                        "tokens": chunk_token_list,
                        "token_ids": token_ids,
                        "metadata": {
                            "source": publisher,
                            "title": title,
                            "url": src_url,
                            "category": category,
                            "chunk_index": chunk_idx_in_doc,
                            "token_count": len(chunk_token_list)
                        }
                    }
                    all_chunks.append(chunk_payload)
                    chunk_id += 1
                    chunk_idx_in_doc += 1

        self.chunk_records = all_chunks
        logging.info(f"Generated {len(all_chunks)} semantic chunks ready for vector embedding.")
        return all_chunks

    def fit_and_compute_embeddings(self, chunks: Optional[List[Dict[str, Any]]] = None) -> np.ndarray:
        """
        Computes dense vector representations for all chunks using TF-IDF / LSA features,
        and attaches normalized embedding vectors to each chunk payload.
        """
        if chunks is None:
            chunks = self.chunk_records

        corpus_texts = [c["cleaned_text"] for c in chunks]
        tfidf_sparse = self.vectorizer.fit_transform(corpus_texts)
        dense_embeddings = tfidf_sparse.toarray()
        self.embedding_matrix = dense_embeddings
        self.is_fitted = True

        # Attach embedding list to each chunk record
        for idx, chunk in enumerate(chunks):
            vector_list = dense_embeddings[idx].tolist()
            # Non-zero dimensions for compact representation
            non_zero_dim = int(np.count_nonzero(dense_embeddings[idx]))
            chunk["embedding_vector"] = [round(float(v), 6) for v in vector_list]
            chunk["embedding_dimensions"] = len(vector_list)
            chunk["non_zero_features"] = non_zero_dim

        logging.info(f"Computed vector embeddings with shape {dense_embeddings.shape} (Dimensions: {dense_embeddings.shape[1]}).")
        return dense_embeddings

    def search_similar_chunks(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Performs vector cosine similarity search for a given natural language query
        against the tokenized and embedded SVB collapse corpus.
        """
        if not self.is_fitted or self.embedding_matrix is None:
            raise ValueError("Embedding model has not been fitted yet.")

        # Transform query into embedding space
        query_vec = self.vectorizer.transform([query]).toarray()
        similarities = cosine_similarity(query_vec, self.embedding_matrix)[0]

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []

        for rank, idx in enumerate(top_indices, start=1):
            score = float(similarities[idx])
            chunk = self.chunk_records[idx]
            results.append({
                "rank": rank,
                "similarity_score": round(score, 4),
                "chunk_id": chunk["chunk_id"],
                "publisher": chunk["publisher"],
                "source_title": chunk["source_title"],
                "cleaned_text": chunk["cleaned_text"],
                "token_count": chunk["token_count"]
            })

        return results


def export_vector_dataset(
    chunks: List[Dict[str, Any]],
    vocab_to_id: Dict[str, int],
    json_path: str,
    csv_path: str
) -> None:
    """Exports structured vector embedding dataset in JSON (for Vector DBs) and CSV (for Pandas/Analysis)."""
    # 1. JSON Export for Vector Stores (Chroma, Pinecone, Weaviate, FAISS)
    vector_payload = {
        "metadata": {
            "dataset_name": "Silicon Valley Bank (SVB) Collapse Vector Embeddings",
            "total_chunks": len(chunks),
            "vocabulary_size": len(vocab_to_id),
            "embedding_type": "TF-IDF / N-gram Dense Vector Space (Cosine Normalized)",
            "vector_database_compatibility": ["ChromaDB", "FAISS", "Pinecone", "Qdrant", "Weaviate"],
            "embedding_dimensions": chunks[0]["embedding_dimensions"] if chunks else 0
        },
        "vocabulary_index": {k: v for k, v in list(vocab_to_id.items())[:100]},  # Sample vocab
        "vector_chunks": chunks
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(vector_payload, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved Vector Embedding JSON dataset to: {json_path}")

    # 2. Tabular CSV Export
    csv_rows = []
    for c in chunks:
        csv_rows.append({
            "chunk_id": c["chunk_id"],
            "publisher": c["publisher"],
            "source_title": c["source_title"],
            "source_url": c["source_url"],
            "category": c["category"],
            "token_count": c["token_count"],
            "cleaned_text": c["cleaned_text"],
            "tokens_sample": " ".join(c["tokens"][:15]),
            "token_ids_sample": str(c["token_ids"][:15]),
            "embedding_dim": c["embedding_dimensions"],
            "non_zero_features": c.get("non_zero_features", 0)
        })
    df = pd.DataFrame(csv_rows)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logging.info(f"Saved Tabular Chunks CSV to: {csv_path}")
