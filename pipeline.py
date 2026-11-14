"""
Master Pipeline Orchestrator: SVB Collapse NLP & Vector Embedding Pipeline
-------------------------------------------------------------------------
Executes the full end-to-end lifecycle:
1. Web Scraping from Internationally Reputed Sites (Reuters, BBC, Federal Reserve, Wikipedia)
2. 10 Comprehensive NLP Preprocessing Transformations
3. Vocabulary Construction & Tokenization
4. Semantic / Sliding Window Chunking for Vector Databases & RAG
5. Dense Vector Embeddings Generation & Similarity Retrieval Demonstration
6. Multi-format Dataset Export (JSON + CSV)
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime

# Set console encoding for Windows
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import DEFAULT_PIPELINE_CONFIG, SVB_SOURCES
from scraper import SVBScraper, export_scraped_data
from preprocessor import SVBTextPreprocessor, preprocess_articles_dataset
from vector_embedding_prep import SVBVectorEmbeddingPreparer, export_vector_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


def run_full_pipeline(
    force_live: bool = False,
    chunk_word_size: int = DEFAULT_PIPELINE_CONFIG["chunk_word_size"],
    chunk_overlap: int = DEFAULT_PIPELINE_CONFIG["chunk_overlap"],
    test_query: str = "What caused the digital bank run and Federal Reserve interest rate losses at Silicon Valley Bank?"
) -> None:
    """Executes all stages of the NLP & Vector Embedding Pipeline."""
    print("\n" + "=" * 80)
    print("🚀 SILICON VALLEY BANK (SVB) COLLAPSE - NLP & VECTOR EMBEDDING PIPELINE")
    print("=" * 80)

    # -------------------------------------------------------------
    # STAGE 1: Web Scraping from Reputed International Sources
    # -------------------------------------------------------------
    print("\n[STAGE 1/5] Scraping Reputed International Sources...")
    articles = SVBScraper.scrape_all_sources(force_live=force_live)
    export_scraped_data(articles, DEFAULT_PIPELINE_CONFIG["export_raw_json"])
    total_paragraphs = sum(len(a["paragraphs"]) for a in articles)
    print(f"  ✓ Total Source Articles: {len(articles)}")
    print(f"  ✓ Total Text Paragraphs Extracted: {total_paragraphs}")

    # -------------------------------------------------------------
    # STAGE 2: 10 NLP Preprocessing Steps
    # -------------------------------------------------------------
    print("\n[STAGE 2/5] Applying 10 Comprehensive NLP Preprocessing Steps...")
    processed_records = preprocess_articles_dataset(articles)

    # Save preprocessed JSON
    preprocessed_payload = {
        "metadata": {
            "topic": "Silicon Valley Bank (SVB) Collapse NLP Preprocessing",
            "pipeline_steps": [
                "1. Lowercasing",
                "2. Removing HTML tags & unescaping entities",
                "3. Removing URLs",
                "4. Removing Punctuations & normalizing hyphens",
                "5. Financial & Chat Acronyms Expansion (SVB, FDIC, Fed, VC, etc.)",
                "6. Spelling Correction & Character Normalization",
                "7. Removing Stop Words (with context preservation)",
                "8. Handling Emojis",
                "9. Stemming (Porter Stemmer)",
                "10. Lemmatization (WordNet Lemmatizer with POS mapping)"
            ],
            "total_records": len(processed_records),
            "generated_at": datetime.now().isoformat()
        },
        "records": processed_records
    }
    with open(DEFAULT_PIPELINE_CONFIG["export_preprocessed_json"], "w", encoding="utf-8") as f:
        json.dump(preprocessed_payload, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Successfully preprocessed {len(processed_records)} records.")
    print(f"  ✓ Exported to: {DEFAULT_PIPELINE_CONFIG['export_preprocessed_json']}")

    # -------------------------------------------------------------
    # STAGE 3: Tokenization & Semantic Chunking
    # -------------------------------------------------------------
    print(f"\n[STAGE 3/5] Tokenizing & Creating Semantic Chunks (Size: {chunk_word_size} words, Overlap: {chunk_overlap} words)...")
    preparer = SVBVectorEmbeddingPreparer(
        chunk_word_size=chunk_word_size,
        chunk_overlap=chunk_overlap
    )
    chunks = preparer.create_semantic_chunks(processed_records)
    print(f"  ✓ Built vocabulary of {len(preparer.vocab_to_id)} distinct tokens.")
    print(f"  ✓ Generated {len(chunks)} semantic chunks structured for Vector Stores / RAG.")

    # -------------------------------------------------------------
    # STAGE 4: Dense Vector Embeddings Generation
    # -------------------------------------------------------------
    print("\n[STAGE 4/5] Computing Dense Vector Embeddings...")
    embeddings = preparer.fit_and_compute_embeddings(chunks)
    print(f"  ✓ Embedding Matrix Dimensions: {embeddings.shape[0]} chunks x {embeddings.shape[1]} features.")

    # Export vector dataset to JSON and CSV
    export_vector_dataset(
        chunks=chunks,
        vocab_to_id=preparer.vocab_to_id,
        json_path=DEFAULT_PIPELINE_CONFIG["export_vector_json"],
        csv_path=DEFAULT_PIPELINE_CONFIG["export_csv"]
    )
    print(f"  ✓ Exported Vector Store JSON: {DEFAULT_PIPELINE_CONFIG['export_vector_json']}")
    print(f"  ✓ Exported Tabular Dataset CSV: {DEFAULT_PIPELINE_CONFIG['export_csv']}")

    # -------------------------------------------------------------
    # STAGE 5: Vector Semantic Similarity Retrieval Demonstration
    # -------------------------------------------------------------
    print("\n[STAGE 5/5] Testing Vector Semantic Retrieval...")
    print(f"  🔍 Query: '{test_query}'")
    search_results = preparer.search_similar_chunks(test_query, top_k=3)

    print("\n" + "-" * 80)
    print("TOP RETRIEVED VECTOR MATCHES:")
    print("-" * 80)
    for res in search_results:
        print(f"Rank #{res['rank']} | Score: {res['similarity_score']:.4f} | Chunk ID: {res['chunk_id']}")
        print(f"Source: [{res['publisher']}] - {res['source_title']}")
        print(f"Content: {res['cleaned_text'][:200]}...\n")
    print("-" * 80)

    # Sample before and after inspection
    sample_rec = processed_records[0]
    print("\n" + "=" * 80)
    print("SAMPLE PREPROCESSING TRANSFORMATION (RECORD #1):")
    print("=" * 80)
    print(f"RAW TEXT:\n{sample_rec['raw_text']}\n")
    print(f"EXPANDED & CLEANED:\n{sample_rec['cleaned_text']}\n")
    print(f"TOKENS (First 15): {sample_rec['tokens'][:15]}")
    print(f"LEMMATIZED: {sample_rec['lemmas'][:15]}")
    print(f"TOKEN IDs (First 15): {chunks[0]['token_ids'][:15]}")
    print("=" * 80)
    print("\n✨ PIPELINE COMPLETED SUCCESSFULLY!\n")


def main():
    parser = argparse.ArgumentParser(description="Silicon Valley Bank (SVB) Collapse NLP & Vector Embedding Pipeline")
    parser.add_argument("--force-live", action="store_true", help="Force live web scraping across all target URLs")
    parser.add_argument("--chunk-size", type=int, default=180, help="Word chunk size for vector embeddings (default: 180)")
    parser.add_argument("--overlap", type=int, default=30, help="Sliding window overlap size (default: 30)")
    parser.add_argument("--query", type=str, default="What caused the digital bank run and interest rate losses at Silicon Valley Bank?", help="Test search query for vector retrieval")

    args = parser.parse_args()
    run_full_pipeline(
        force_live=args.force_live,
        chunk_word_size=args.chunk_size,
        chunk_overlap=args.overlap,
        test_query=args.query
    )


if __name__ == "__main__":
    main()
