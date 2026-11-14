"""
Configuration & Knowledge Dictionaries for SVB Collapse NLP & Vector Embedding Pipeline
"""

# Reputable International Sources on Silicon Valley Bank (SVB) Collapse
SVB_SOURCES = [
    {
        "publisher": "Wikipedia Encyclopedia",
        "url": "https://en.wikipedia.org/wiki/Collapse_of_Silicon_Valley_Bank",
        "title": "Collapse of Silicon Valley Bank (Comprehensive Financial & Regulatory History)",
        "category": "Historical & Financial Overview"
    },
    {
        "publisher": "Federal Reserve & Regulatory Reports",
        "url": "https://en.wikipedia.org/wiki/2023_United_States_banking_crisis",
        "title": "2023 United States Banking Crisis & Regulatory Interventions",
        "category": "Banking Crisis & Systemic Risk"
    },
    {
        "publisher": "Reuters International",
        "url": "https://www.reuters.com/business/finance/what-caused-silicon-valley-banks-collapse-2023-03-10/",
        "title": "What Caused Silicon Valley Bank's Historic Collapse",
        "category": "Journalistic News Analysis"
    },
    {
        "publisher": "BBC News International",
        "url": "https://www.bbc.com/news/business-64915128",
        "title": "Silicon Valley Bank Collapse: What Happened and Why?",
        "category": "Global Financial Impact"
    }
]

# Domain-specific financial & technology abbreviations expansion dictionary
FINANCIAL_ACRONYMS = {
    "SVB": "Silicon Valley Bank",
    "FDIC": "Federal Deposit Insurance Corporation",
    "FED": "Federal Reserve",
    "FRB": "Federal Reserve Board",
    "VC": "Venture Capital",
    "VCS": "Venture Capitalists",
    "HTM": "Held To Maturity",
    "AFS": "Available For Sale",
    "MBS": "Mortgage Backed Securities",
    "CEO": "Chief Executive Officer",
    "CFO": "Chief Financial Officer",
    "CRO": "Chief Risk Officer",
    "YOY": "Year Over Year",
    "QOQ": "Quarter Over Quarter",
    "Q1": "First Quarter",
    "Q2": "Second Quarter",
    "Q3": "Third Quarter",
    "Q4": "Fourth Quarter",
    "ROI": "Return On Investment",
    "IPO": "Initial Public Offering",
    "NAV": "Net Asset Value",
    "AUM": "Assets Under Management",
    "LCR": "Liquidity Coverage Ratio",
    "HQLA": "High Quality Liquid Assets",
    "DIF": "Deposit Insurance Fund",
    "BTFP": "Bank Term Funding Program",
    "SBNY": "Signature Bank New York",
    "SI": "Silvergate Bank",
    "CS": "Credit Suisse",
    "US": "United States",
    "USA": "United States of America",
    "UK": "United Kingdom",
    "SEC": "Securities and Exchange Commission",
    "OCC": "Office of the Comptroller of the Currency",
    "ALM": "Asset Liability Management",
    "IRR": "Interest Rate Risk"
}

# General chat words & informal acronyms
CHAT_WORDS = {
    "AFAIK": "As Far As I Know",
    "AFK": "Away From Keyboard",
    "ASAP": "As Soon As Possible",
    "ATK": "At The Keyboard",
    "ATM": "At The Moment",
    "BBL": "Be Back Later",
    "BBS": "Be Back Soon",
    "BFN": "Bye For Now",
    "BRB": "Be Right Back",
    "BTW": "By The Way",
    "CU": "See You",
    "FAQ": "Frequently Asked Questions",
    "FWIW": "For What It Is Worth",
    "FYI": "For Your Information",
    "GG": "Good Game",
    "GMTA": "Great Minds Think Alike",
    "GR8": "Great",
    "IC": "I See",
    "IDK": "I Do Not Know",
    "ILU": "I Love You",
    "IMHO": "In My Humble Opinion",
    "IMO": "In My Opinion",
    "IRL": "In Real Life",
    "JK": "Just Kidding",
    "LOL": "Laughing Out Loud",
    "LMAO": "Laughing My Ass Off",
    "TBH": "To Be Honest",
    "TBD": "To Be Determined",
    "THX": "Thank You",
    "TIA": "Thanks In Advance",
    "TLDR": "Too Long Did Not Read",
    "TTYL": "Talk To You Later",
    "U": "You",
    "UR": "Your",
    "W/": "With",
    "W/O": "Without",
    "WTF": "What The Heck",
    "WYSIWYG": "What You See Is What You Get"
}

# Preprocessing & Vector Embedding Pipeline Default Parameters
DEFAULT_PIPELINE_CONFIG = {
    "min_paragraph_length": 40,
    "max_paragraphs_per_source": 40,
    "chunk_word_size": 180,
    "chunk_overlap": 30,
    "min_chunk_tokens": 25,
    "top_k_similarity": 4,
    "export_raw_json": "svb_collapse_raw_scraped.json",
    "export_preprocessed_json": "svb_collapse_preprocessed.json",
    "export_vector_json": "svb_collapse_vector_embeddings.json",
    "export_csv": "svb_chunks_dataset.csv",
    "export_notebook": "svb_collapse_nlp_embeddings.ipynb"
}
