"""
core/similarity_engine.py
-------------------------
Purpose: Compute semantic similarity between student answers and model answers
         using local dense vector embeddings (all-MiniLM-L6-v2) with automated
         fallback to Scikit-Learn TF-IDF cosine similarity.
Inputs:  Student answer text and model answer text (or batch DataFrames).
Outputs: Cosine similarity float (0.0 to 1.0), percentage match (0 to 100%), and qualitative band.
"""

import logging
from typing import List, Optional, Tuple, Union
import numpy as np
import pandas as pd

# Configure logging for informative diagnostics
logger = logging.getLogger(__name__)


class SemanticSimilarityEngine:
    """
    Evaluates semantic similarity between student responses and model answers.
    Prioritizes local neural sentence embeddings ('all-MiniLM-L6-v2') and seamlessly
    falls back to Scikit-Learn TF-IDF cosine similarity if sentence-transformers
    is not installed or weights cannot be downloaded.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", use_fallback: bool = False):
        """
        Initialize the similarity engine.

        Args:
            model_name: HuggingFace model tag for sentence-transformers.
            use_fallback: If True, forces TF-IDF fallback mode (useful for testing/low memory).
        """
        self.model_name = model_name
        self.model = None
        self.engine_type = "tfidf" if use_fallback else "pending"

        if not use_fallback:
            self._initialize_neural_model()

    def _initialize_neural_model(self):
        """Attempt to load SentenceTransformer model; fallback to TF-IDF on failure."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local sentence embedding model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            self.engine_type = "sentence-transformers"
            logger.info("SentenceTransformer model successfully loaded.")
        except Exception as e:
            logger.warning(
                f"SentenceTransformer unavailable ({e}). "
                "Engaging Scikit-Learn TF-IDF fallback engine."
            )
            self.model = None
            self.engine_type = "tfidf"

    def compute_similarity(self, student_answer: str, model_answer: str) -> float:
        """
        Calculate cosine similarity between a single student answer and the model answer.

        Args:
            student_answer: Raw text submitted by the student.
            model_answer: Benchmark text provided by the instructor.

        Returns:
            float: Normalized similarity score in the range [0.0, 1.0].
        """
        s_clean = student_answer.strip()
        m_clean = model_answer.strip()

        # Handle trivial cases
        if not s_clean or not m_clean:
            return 0.0

        if s_clean.lower() == m_clean.lower():
            return 1.0

        if self.engine_type == "sentence-transformers" and self.model is not None:
            return self._compute_neural_similarity(s_clean, m_clean)
        else:
            return self._compute_tfidf_similarity(s_clean, m_clean)

    def _compute_neural_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity using dense 384-dimensional embeddings."""
        embeddings = self.model.encode([text_a, text_b], convert_to_numpy=True)
        vec_a = embeddings[0]
        vec_b = embeddings[1]

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        cosine_sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        # Clamp to [0.0, 1.0] for educational scoring consistency
        return max(0.0, min(1.0, cosine_sim))

    def _compute_tfidf_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity using Scikit-Learn TF-IDF representation."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        try:
            tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
            sim = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
            return max(0.0, min(1.0, sim))
        except ValueError:
            # Fallback if both texts contain only stop words
            return 0.0

    def batch_compute_similarity(self, student_answers: List[str], model_answer: str) -> List[float]:
        """
        Compute similarity scores for a batch of student answers against one model answer.

        Args:
            student_answers: List of student answer strings.
            model_answer: Benchmark model answer string.

        Returns:
            List[float]: Similarity score for each student answer.
        """
        if not student_answers:
            return []

        if self.engine_type == "sentence-transformers" and self.model is not None:
            # High-throughput batched encoding
            all_texts = [model_answer] + student_answers
            all_embeddings = self.model.encode(all_texts, convert_to_numpy=True)
            model_vec = all_embeddings[0]
            student_vecs = all_embeddings[1:]

            norm_m = np.linalg.norm(model_vec)
            if norm_m == 0:
                return [0.0] * len(student_answers)

            scores = []
            for s_vec in student_vecs:
                norm_s = np.linalg.norm(s_vec)
                if norm_s == 0:
                    scores.append(0.0)
                else:
                    sim = float(np.dot(s_vec, model_vec) / (norm_s * norm_m))
                    scores.append(max(0.0, min(1.0, sim)))
            return scores
        else:
            return [self.compute_similarity(s, model_answer) for s in student_answers]

    def get_match_percentage(self, similarity_score: float) -> float:
        """Convert a 0.0-1.0 similarity score to a human-readable 0-100% value."""
        return round(similarity_score * 100.0, 1)

    def classify_match_band(self, similarity_score: float) -> str:
        """Categorize similarity score into an actionable tier for instructors."""
        if similarity_score >= 0.75:
            return "High Match"
        elif similarity_score >= 0.45:
            return "Moderate Match"
        else:
            return "Low Match"

    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich a batch DataFrame containing 'student_answer' and 'model_answer' columns
        with semantic similarity metrics.

        Returns:
            pd.DataFrame: Enriched copy with 'semantic_similarity', 'semantic_score_pct',
                          and 'semantic_band'.
        """
        enriched_df = df.copy()

        similarities = []
        for _, row in enriched_df.iterrows():
            sim = self.compute_similarity(str(row["student_answer"]), str(row["model_answer"]))
            similarities.append(sim)

        enriched_df["semantic_similarity"] = similarities
        enriched_df["semantic_score_pct"] = [self.get_match_percentage(s) for s in similarities]
        enriched_df["semantic_band"] = [self.classify_match_band(s) for s in similarities]

        return enriched_df
