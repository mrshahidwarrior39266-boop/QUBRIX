"""
core/synonym_engine.py
----------------------
Purpose: Detect, resolve, and audit semantic synonyms, domain acronyms, and
         morphological paraphrases between student answers and rubric criteria.
         Integrates with dense embeddings (all-MiniLM-L6-v2) for sub-5ms local matching.
"""

import re
from typing import Any, Dict, List, Optional
import numpy as np

# Canonical academic acronyms by discipline
DOMAIN_ACRONYMS: Dict[str, Dict[str, str]] = {
    "biology": {
        "atp": "adenosine triphosphate",
        "adp": "adenosine diphosphate",
        "etc": "electron transport chain",
        "tca": "krebs cycle",
        "dna": "deoxyribonucleic acid",
        "rna": "ribonucleic acid",
        "co2": "carbon dioxide",
        "h2o": "water",
        "nad+": "nicotinamide adenine dinucleotide"
    },
    "computer science": {
        "dfs": "depth first search",
        "bfs": "breadth first search",
        "ram": "memory overhead",
        "cpu": "processing unit",
        "o(1)": "constant space",
        "o(n)": "linear space",
        "o(n log n)": "linearithmic complexity",
        "fifo": "first in first out",
        "lifo": "last in first out"
    },
    "economics": {
        "gdp": "gross domestic product",
        "cpi": "consumer price index",
        "fed": "federal reserve"
    }
}

# Domain semantic equivalences for STEM
DOMAIN_CONCEPT_EQUIVALENCES: Dict[str, List[tuple]] = {
    "biology": [
        ("catabolize", "break down"),
        ("oxidize", "break down"),
        ("sugar", "glucose"),
        ("cellular energy", "atp energy"),
        ("powerhouse", "mitochondria"),
        ("aerobic", "presence of oxygen"),
        ("anaerobic", "absence of oxygen")
    ],
    "computer science": [
        ("self calling", "recursion"),
        ("call stack", "memory frames"),
        ("loop", "iteration"),
        ("repeat", "iteration"),
        ("while loop", "iteration"),
        ("for loop", "iteration"),
        ("stack overflow", "memory exhaustion")
    ]
}


class SynonymEngine:
    """
    Detects and validates synonyms and conceptual paraphrases.
    Provides auditable transparent pairing between student phrases and rubric concepts.
    """

    def __init__(self, sim_engine=None, similarity_threshold: float = 0.78):
        self.sim_engine = sim_engine
        self.similarity_threshold = similarity_threshold

    def normalize_acronyms(self, text: str, subject: str = "Biology") -> str:
        """Expand domain acronyms to canonical full text."""
        sub_key = subject.lower().strip()
        acronyms = DOMAIN_ACRONYMS.get(sub_key, {})
        clean = text.lower()
        for acr, expansion in acronyms.items():
            pattern = r"\b" + re.escape(acr) + r"\b"
            clean = re.sub(pattern, expansion, clean)
        return clean

    def extract_phrases(self, text: str, max_n: int = 3) -> List[str]:
        """Extract word unigrams, bigrams, and trigrams from raw text."""
        tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\(\)]+\b", text)]
        phrases = []
        for n in range(1, max_n + 1):
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i:i + n])
                if len(phrase) >= 3:
                    phrases.append(phrase)
        return list(dict.fromkeys(phrases))

    def detect_synonyms(
        self,
        student_answer: str,
        criterion_description: str,
        subject: str = "Biology"
    ) -> List[Dict[str, Any]]:
        """
        Identify if any concepts in student_answer match criterion_description via
        acronyms, domain equivalence tables, or dense vector cosine similarity.
        """
        matches = []
        if not student_answer.strip() or not criterion_description.strip():
            return matches

        sub_key = subject.lower().strip()
        student_lower = student_answer.lower()
        desc_lower = criterion_description.lower()

        # 1. Check Domain Concept Equivalences
        equiv_pairs = DOMAIN_CONCEPT_EQUIVALENCES.get(sub_key, [])
        for term_a, term_b in equiv_pairs:
            # Case 1: Criterion mentions term_b, student wrote term_a
            if term_b in desc_lower and term_a in student_lower:
                matches.append({
                    "rubric_term": term_b,
                    "student_term": term_a,
                    "similarity": 0.92,
                    "match_type": "domain_thesaurus"
                })
            # Case 2: Criterion mentions term_a, student wrote term_b
            elif term_a in desc_lower and term_b in student_lower:
                matches.append({
                    "rubric_term": term_a,
                    "student_term": term_b,
                    "similarity": 0.92,
                    "match_type": "domain_thesaurus"
                })

        # 2. Check Acronym Expansions
        acronyms = DOMAIN_ACRONYMS.get(sub_key, {})
        for acr, full in acronyms.items():
            acr_pat = r"\b" + re.escape(acr) + r"\b"
            full_pat = r"\b" + re.escape(full) + r"\b"
            if re.search(full_pat, desc_lower) and re.search(acr_pat, student_lower):
                matches.append({
                    "rubric_term": full,
                    "student_term": acr.upper(),
                    "similarity": 0.98,
                    "match_type": "acronym_expansion"
                })
            elif re.search(acr_pat, desc_lower) and re.search(full_pat, student_lower):
                matches.append({
                    "rubric_term": acr.upper(),
                    "student_term": full,
                    "similarity": 0.98,
                    "match_type": "acronym_expansion"
                })

        # 3. Dense Embedding Latent Synonym Search (if sentence-transformers is active)
        if self.sim_engine and getattr(self.sim_engine, "model", None) and len(matches) == 0:
            stop_words = {"this", "that", "with", "from", "into", "identifies", "explains", "states", "mentions", "criterion"}
            desc_words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", desc_lower) if w not in stop_words]
            student_phrases = self.extract_phrases(student_answer, max_n=2)

            if desc_words and student_phrases:
                try:
                    desc_vecs = self.sim_engine.model.encode(desc_words, convert_to_numpy=True)
                    phrase_vecs = self.sim_engine.model.encode(student_phrases, convert_to_numpy=True)

                    desc_norms = np.linalg.norm(desc_vecs, axis=1, keepdims=True)
                    phrase_norms = np.linalg.norm(phrase_vecs, axis=1, keepdims=True)

                    desc_norms[desc_norms == 0] = 1e-9
                    phrase_norms[phrase_norms == 0] = 1e-9

                    d_unit = desc_vecs / desc_norms
                    p_unit = phrase_vecs / phrase_norms

                    # Cosine matrix: (len(desc_words), len(student_phrases))
                    cos_matrix = np.dot(d_unit, p_unit.T)

                    for i, r_word in enumerate(desc_words):
                        best_p_idx = int(np.argmax(cos_matrix[i]))
                        best_sim = float(cos_matrix[i, best_p_idx])
                        best_phrase = student_phrases[best_p_idx]

                        # Only count as synonym if not literal identical substring
                        if best_sim >= self.similarity_threshold and r_word not in best_phrase and best_phrase not in r_word:
                            matches.append({
                                "rubric_term": r_word,
                                "student_term": best_phrase,
                                "similarity": round(best_sim, 3),
                                "match_type": "dense_vector_synonym"
                            })
                            break
                except Exception:
                    pass

        # Deduplicate matches
        unique_matches = []
        seen = set()
        for m in matches:
            key = (m["rubric_term"], m["student_term"])
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)

        return unique_matches
