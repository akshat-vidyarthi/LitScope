import re
from typing import List, Tuple, Dict


# AI Cliché & Tell-tale LLM phrase patterns mapped to clean, natural academic alternatives
CLICHE_PHRASE_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    # Metaphorical & overused LLM phrases
    (re.compile(r'\bserves as a testament to\b', re.IGNORECASE), 'demonstrates'),
    (re.compile(r'\bis a testament to\b', re.IGNORECASE), 'demonstrates'),
    (re.compile(r'\btestament to\b', re.IGNORECASE), 'evidence of'),
    (re.compile(r'\bdelves into\b', re.IGNORECASE), 'examines'),
    (re.compile(r'\bdelved into\b', re.IGNORECASE), 'examined'),
    (re.compile(r'\bdelve into\b', re.IGNORECASE), 'examine'),
    (re.compile(r'\bsheds light on\b', re.IGNORECASE), 'clarifies'),
    (re.compile(r'\bshed light on\b', re.IGNORECASE), 'clarified'),
    (re.compile(r'\bplays a pivotal role in\b', re.IGNORECASE), 'is central to'),
    (re.compile(r'\bpivotal role\b', re.IGNORECASE), 'central role'),
    (re.compile(r'\bpivotal\b', re.IGNORECASE), 'key'),
    (re.compile(r'\bparamount importance\b', re.IGNORECASE), 'primary importance'),
    (re.compile(r'\bparamount\b', re.IGNORECASE), 'fundamental'),
    (re.compile(r'\bmultifaceted\b', re.IGNORECASE), 'varied'),
    (re.compile(r'\btapestry\b', re.IGNORECASE), 'spectrum'),
    (re.compile(r'\beacon of\b', re.IGNORECASE), 'foundation for'),
    (re.compile(r'\ba plethora of\b', re.IGNORECASE), 'numerous'),
    (re.compile(r'\bit is worth noting that\b', re.IGNORECASE), 'notably,'),
    (re.compile(r'\bit is important to note that\b', re.IGNORECASE), 'notably,'),
    (re.compile(r'\bneedless to say\b', re.IGNORECASE), 'evidently,'),
    (re.compile(r'\bplays an indispensable role\b', re.IGNORECASE), 'remains essential'),
    (re.compile(r'\bindispensable\b', re.IGNORECASE), 'essential'),
    (re.compile(r'\bever-evolving\b', re.IGNORECASE), 'evolving'),
    (re.compile(r'\bholistic\b', re.IGNORECASE), 'comprehensive'),

    # Formulaic LLM transition phrases
    (re.compile(r'\btogether, these studies underscore\b', re.IGNORECASE), 'collectively, these investigations show'),
    (re.compile(r'\btogether, these findings underscore\b', re.IGNORECASE), 'collectively, these results show'),
    (re.compile(r'\btogether, these studies illustrate\b', re.IGNORECASE), 'in summary, these investigations demonstrate'),
    (re.compile(r'\btogether, these studies demonstrate\b', re.IGNORECASE), 'collectively, these studies show'),
    (re.compile(r'\btogether, these findings indicate\b', re.IGNORECASE), 'collectively, these findings indicate'),
    (re.compile(r'\bunderscores the shift\b', re.IGNORECASE), 'reflects the transition'),
    (re.compile(r'\bunderscores the necessity\b', re.IGNORECASE), 'emphasizes the need'),
    (re.compile(r'\bunderscores\b', re.IGNORECASE), 'highlights'),
    (re.compile(r'\bunderscore\b', re.IGNORECASE), 'highlight'),
    (re.compile(r'\bunderscored\b', re.IGNORECASE), 'highlighted'),
    (re.compile(r'\bin parallel with\b', re.IGNORECASE), 'alongside'),
    (re.compile(r'\bin parallel,\s*', re.IGNORECASE), 'Alongside this, '),
    (re.compile(r'\badvancing beyond\b', re.IGNORECASE), 'moving beyond'),
    (re.compile(r'\bexpanding on\b', re.IGNORECASE), 'extending'),
]

# Vocabulary swaps that vary logit probability tokens without changing semantic meaning
LOGIT_VARIATION_MAP: Dict[str, str] = {
    "utilized": "used",
    "utilizing": "using",
    "utilize": "use",
    "leverage": "apply",
    "leveraging": "applying",
    "leveraged": "applied",
    "demonstrating": "showing",
    "demonstrated": "showed",
    "demonstrates": "shows",
    "investigated": "studied",
    "investigating": "studying",
    "investigate": "study",
    "attaining": "achieving",
    "attained": "achieved",
    "exhibits": "displays",
    "exhibited": "displayed",
    "exhibit": "display",
    "complemented by": "supported by",
    "subsequently": "later",
    "consequently": "therefore",
    "notwithstanding": "despite",
    "furthermore": "in addition",
    "moreover": "additionally",
}


def sanitize_unicode_watermarks(text: str) -> str:
    """
    Strips zero-width characters, non-breaking spaces, and invisible formatting tokens
    that can act as covert digital watermarks.
    """
    # Remove Zero-Width Spaces, Non-Joiners, and BOMs
    cleaned = re.sub(r'[\u200B\u200C\u200D\uFEFF\u2060\u200E\u200F]', '', text)
    # Replace non-breaking spaces with standard ASCII space
    cleaned = cleaned.replace('\u00A0', ' ')
    # Normalize curly smart quotes to clean ASCII quotes
    cleaned = cleaned.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    # Normalize em-dashes and en-dashes
    cleaned = cleaned.replace('—', ' - ').replace('–', '-')
    return cleaned


def dewatermark_academic_prose(raw_text: str) -> str:
    """
    De-watermarks and humanizes academic text by:
    1. Scrubbing invisible unicode and zero-width artifacts.
    2. Protecting citations [X], author names, acronyms, and metrics.
    3. Neutralizing tell-tale AI buzzwords and clichés (e.g. Turnitin/GPTZero triggers).
    4. Modulating logit-level consecutive token probabilities (SynthID disruption).
    5. Restoring protected citations and metrics exactly.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    # 1. Unicode cleanse
    text = sanitize_unicode_watermarks(raw_text)

    # 2. Protect citations, author tags, and exact metrics
    protected_tokens: List[str] = []

    def save_token(match: re.Match) -> str:
        idx = len(protected_tokens)
        protected_tokens.append(match.group(0))
        return f"__LIT_PROTECTED_{idx}__"

    # Pattern A: Numbered citations e.g. [1], [2], [14]
    text = re.sub(r'\[\d+(?:,\s*p\.\s*\d+)?\]', save_token, text)

    # Pattern B: Percentages and numbers e.g. 94.48%, 7,000, 700, 1,372
    text = re.sub(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?', save_token, text)

    # Pattern C: Critical technical acronyms
    text = re.sub(r'\b(LBP|SSIM|SIFT|MSE|ROC|Youden\'s J|SVM|KNN|CNN|ORB|RGB|MATLAB|OpenCV|UCI|RBI)\b', save_token, text)

    # 3. Replace AI cliché phrases with natural academic expressions
    for pattern, replacement in CLICHE_PHRASE_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    # 4. Modulate logit tokens: swap select AI favorite words with natural synonyms
    # to disrupt consecutive token sampling correlations (SynthID-Text)
    for word, swap in LOGIT_VARIATION_MAP.items():
        # Match standalone word with word boundary, case-insensitively
        def swap_func(m: re.Match, target=swap) -> str:
            original = m.group(0)
            if original.isupper():
                return target.upper()
            elif original[0].isupper():
                return target.capitalize()
            return target

        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        text = pattern.sub(swap_func, text)

    # 5. Fix any double spaces or punctuation glitches
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+([,.;?!])', r'\1', text)

    # 6. Restore protected tokens
    for idx, original in enumerate(protected_tokens):
        text = text.replace(f"__LIT_PROTECTED_{idx}__", original)

    return text.strip()
