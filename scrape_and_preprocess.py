"""
Web Scraper and Text Preprocessing Script for Silicon Valley Collapse (NLP & Vector Embedding Ready)
--------------------------------------------------------------------------------------------------
Maintains full backward-compatibility and delegates to the modular pipeline in pipeline.py.
"""

import sys
import argparse
from pipeline import run_full_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape SVB collapse data, preprocess with NLP steps, and arrange for vector embeddings.")
    parser.add_argument("--force-live", action="store_true", help="Force live web scraping")
    parser.add_argument("--chunk-size", type=int, default=180, help="Chunk size for vector embeddings")
    parser.add_argument("--overlap", type=int, default=30, help="Overlap for sliding window")
    parser.add_argument("--query", type=str, default="What caused the digital bank run and Federal Reserve interest rate losses at Silicon Valley Bank?", help="Test query for vector search")

    args = parser.parse_args()
    run_full_pipeline(
        force_live=args.force_live,
        chunk_word_size=args.chunk_size,
        chunk_overlap=args.overlap,
        test_query=args.query
    )
