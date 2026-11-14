"""
NLP Preprocessing Pipeline Module
---------------------------------
Implements 10 foundational NLP text preprocessing steps:
1. Lowercasing
2. Removing HTML tags & entities
3. Removing URLs
4. Removing Punctuations
5. Financial & Chat Acronyms Expansion (SVB, FDIC, Fed, VC, etc.)
6. Spelling Correction / Character Normalization
7. Removing Stop Words (NLTK + domain stop words)
8. Handling Emojis & Unicode symbols
9. Stemming (Porter Stemmer)
10. Lemmatization (WordNet Lemmatizer with POS mapping)
"""

import re
import string
import html
from typing import List, Dict, Any, Optional

import nltk
from nltk.corpus import stopwords, wordnet
from nltk.stem import PorterStemmer, WordNetLemmatizer
from nltk.tokenize import word_tokenize

from config import FINANCIAL_ACRONYMS, CHAT_WORDS

# Ensure NLTK datasets are loaded
try:
    NLTK_STOPWORDS = set(stopwords.words("english"))
except Exception:
    nltk.download("stopwords", quiet=True)
    NLTK_STOPWORDS = set(stopwords.words("english"))

try:
    _ = wordnet.synsets("bank")
except Exception:
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)

# Merge Financial & Chat Acronym dictionaries for fast O(1) lookup
EXPANSION_DICT = {**CHAT_WORDS, **FINANCIAL_ACRONYMS}

# Emoji unicode range regex
EMOJI_PATTERN = re.compile(
    "["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)


class SVBTextPreprocessor:
    """
    Comprehensive NLP Preprocessing Engine for Financial & News Text.
    Executes sequential transformations and provides step-by-step intermediate inspection.
    """

    def __init__(self, emoji_mode: str = "remove", preserve_negations: bool = True):
        self.emoji_mode = emoji_mode
        self.stemmer = PorterStemmer()
        self.lemmatizer = WordNetLemmatizer()
        self.stopwords_set = set(NLTK_STOPWORDS)

        # In financial and sentiment NLP, keeping negations improves vector semantics
        if preserve_negations:
            self.stopwords_set -= {"not", "no", "nor", "neither", "never", "without", "against"}

    # Step 1: Lowercase text
    @staticmethod
    def step1_lower(text: str) -> str:
        return text.lower()

    # Step 2: Remove HTML tags & unescape entities & citation brackets
    @staticmethod
    def step2_remove_html(text: str) -> str:
        text = html.unescape(text)
        # Remove html tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Remove Wikipedia/news citation references like [1], [23], [citation needed], [edit]
        text = re.sub(r"\[\s*(\d+|edit|citation needed)\s*\]", " ", text, flags=re.IGNORECASE)
        return text

    # Step 3: Remove URLs
    @staticmethod
    def step3_remove_urls(text: str) -> str:
        return re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Step 4: Remove Punctuations & Normalize Hyphens
    @staticmethod
    def step4_remove_punctuation(text: str) -> str:
        # Separate joined parentheses and punctuation with space first so tokens don't fuse
        text = re.sub(r"([()\[\]{}–—\-/])", r" \1 ", text)
        # Remove all punctuation
        text = text.translate(str.maketrans("", "", string.punctuation))
        return " ".join(text.split())

    # Step 5: Expand Financial Acronyms & Chat Slangs
    @staticmethod
    def step5_expand_acronyms(text: str) -> str:
        # Pad punctuation boundaries
        padded_text = re.sub(r"([()\[\]{}–—\-/])", r" \1 ", text)
        words = padded_text.split()
        expanded = []
        for word in words:
            # Strip outer punctuation for clean matching
            clean_word = word.strip(".,()[]{}!?\":;'").upper()
            if clean_word in EXPANSION_DICT:
                expanded.append(EXPANSION_DICT[clean_word])
            else:
                expanded.append(word)
        return " ".join(expanded)

    # Step 6: Character Normalization & Spelling Normalization
    @staticmethod
    def step6_normalize_characters(text: str) -> str:
        # Normalize repeated characters (e.g., 'craaaash' -> 'crash')
        text = re.sub(r"(.)\1{2,}", r"\1\1", text)
        # Normalize excessive whitespace
        return " ".join(text.split())

    # Step 7: Remove Stop Words
    def step7_remove_stopwords(self, text: str) -> str:
        words = text.split()
        filtered = [w for w in words if w.lower() not in self.stopwords_set and len(w) > 1]
        return " ".join(filtered)

    # Step 8: Handle Emojis
    def step8_handle_emojis(self, text: str) -> str:
        return EMOJI_PATTERN.sub("", text)

    # Step 9: Stemming (Porter Stemmer)
    def step9_stemming(self, text: str) -> List[str]:
        words = text.split()
        return [self.stemmer.stem(w) for w in words]

    # Step 10: Lemmatization (WordNet Lemmatizer with POS Tagging)
    def step10_lemmatization(self, text: str) -> List[str]:
        words = text.split()
        lemmas = []
        for word in words:
            # Lemmatize as noun first, then verb if unchanged
            lemma = self.lemmatizer.lemmatize(word, pos="n")
            if lemma == word:
                lemma = self.lemmatizer.lemmatize(word, pos="v")
            lemmas.append(lemma)
        return lemmas

    def preprocess_full_record(self, raw_text: str) -> Dict[str, Any]:
        """
        Executes all preprocessing steps in optimal sequence, capturing intermediate states.
        """
        # 1. Clean HTML and URLs first on raw string
        s2_no_html = self.step2_remove_html(raw_text)
        s3_no_url = self.step3_remove_urls(s2_no_html)
        s8_no_emoji = self.step8_handle_emojis(s3_no_url)

        # 2. Expand acronyms before stripping casing and punctuation
        s5_expanded = self.step5_expand_acronyms(s8_no_emoji)

        # 3. Standardize casing and remove punctuation
        s1_lower = self.step1_lower(s5_expanded)
        s4_no_punc = self.step4_remove_punctuation(s1_lower)
        s6_normalized = self.step6_normalize_characters(s4_no_punc)

        # 4. Filter stop words
        s7_no_stopwords = self.step7_remove_stopwords(s6_normalized)

        # 5. Tokenization & Morphological Analysis
        token_list = [w for w in s7_no_stopwords.split() if w]
        stemmed_tokens = self.step9_stemming(s7_no_stopwords)
        lemmatized_tokens = self.step10_lemmatization(s7_no_stopwords)

        return {
            "raw_text": raw_text,
            "step_1_lowercased": s1_lower,
            "step_2_remove_html": s2_no_html,
            "step_3_remove_urls": s3_no_url,
            "step_4_remove_punctuation": s4_no_punc,
            "step_5_expanded_acronyms": s5_expanded,
            "step_6_normalized_text": s6_normalized,
            "step_7_no_stopwords": s7_no_stopwords,
            "step_8_no_emojis": s8_no_emoji,
            "tokens": token_list,
            "stemmed_tokens": stemmed_tokens,
            "lemmatized_tokens": lemmatized_tokens,
            "final_cleaned_text": s7_no_stopwords,
            "final_lemmatized_text": " ".join(lemmatized_tokens)
        }


def preprocess_articles_dataset(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Applies preprocessing to all paragraphs across all scraped articles."""
    preprocessor = SVBTextPreprocessor()
    processed_records = []
    record_id = 1

    for article in articles:
        publisher = article.get("source_publisher", "Unknown")
        url = article.get("source_url", "")
        title = article.get("title", "")
        category = article.get("category", "")

        for p_idx, paragraph in enumerate(article.get("paragraphs", [])):
            res = preprocessor.preprocess_full_record(paragraph)
            processed_records.append({
                "record_id": record_id,
                "publisher": publisher,
                "source_url": url,
                "source_title": title,
                "category": category,
                "paragraph_index": p_idx + 1,
                "raw_text": res["raw_text"],
                "cleaned_text": res["final_cleaned_text"],
                "lemmatized_text": res["final_lemmatized_text"],
                "tokens": res["tokens"],
                "lemmas": res["lemmatized_tokens"],
                "token_count": len(res["tokens"]),
                "intermediate_steps": {
                    "s1_lower": res["step_1_lowercased"],
                    "s2_no_html": res["step_2_remove_html"],
                    "s3_no_url": res["step_3_remove_urls"],
                    "s4_no_punc": res["step_4_remove_punctuation"],
                    "s5_expanded": res["step_5_expanded_acronyms"],
                    "s6_normalized": res["step_6_normalized_text"],
                    "s7_no_stop": res["step_7_no_stopwords"]
                }
            })
            record_id += 1

    return processed_records
