import json
import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

from app.config.settings import settings

logger = logging.getLogger("newsletter.clustering.embedder")

class SemanticEmbedder:
    """Computes semantic embeddings and performs clustering & semantic deduplication."""

    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL_NAME
        logger.info(f"Loading embedding model '{self.model_name}'...")
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformer model: {e}")
            self.model = None

    def embed_text(self, text: str) -> List[float]:
        """Generates embedding vector for a given string."""
        if not self.model or not text:
            return []
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to compute embedding: {e}")
            return []

    def cluster_articles(self, articles: List[Dict[str, Any]], distance_threshold: float = 0.5) -> List[List[Dict[str, Any]]]:
        """Clusters a list of articles using AgglomerativeClustering based on cosine similarity."""
        if not articles:
            return []

        # If only 1 article, return single cluster
        if len(articles) == 1:
            return [articles]

        embeddings = []
        valid_articles = []
        
        for art in articles:
            vector = art.get("embedding")
            if vector:
                embeddings.append(vector)
                valid_articles.append(art)

        # If we don't have enough embeddings, return articles as individual single clusters
        if len(embeddings) < 2:
            return [[art] for art in articles]

        X = np.array(embeddings)
        
        try:
            # We cluster using cosine distance (1 - cosine_similarity)
            # average linkage is extremely robust for text clusters
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=distance_threshold,
                metric="cosine",
                linkage="average"
            )
            labels = clustering.fit_predict(X)
            
            # Group articles by cluster label
            clusters_dict = {}
            for idx, label in enumerate(labels):
                clusters_dict.setdefault(int(label), []).append(valid_articles[idx])
                
            # Add any articles that lacked embeddings as separate single clusters
            result_clusters = list(clusters_dict.values())
            for art in articles:
                if art not in valid_articles:
                    result_clusters.append([art])
                    
            logger.info(f"Grouped {len(articles)} articles into {len(result_clusters)} semantic clusters.")
            return result_clusters
            
        except Exception as e:
            logger.error(f"Clustering algorithm execution failed: {e}")
            # Fallback to returning all articles as one big group or separate
            return [articles]

    def remove_semantic_duplicates(self, new_articles: List[Dict[str, Any]], existing_articles: List[Dict[str, Any]], similarity_threshold: float = 0.85) -> List[Dict[str, Any]]:
        """Filters out new articles that are semantically identical to existing articles or duplicates within the new batch."""
        if not new_articles:
            return []

        filtered_articles = []
        
        # 1. Compute embeddings for new articles if missing
        for art in new_articles:
            if not art.get("embedding"):
                art["embedding"] = self.embed_text(art.get("summary") or art.get("title") or "")

        # 2. Extract embeddings of existing articles
        existing_embeddings = []
        for art in existing_articles:
            vector = art.get("embedding")
            if vector:
                existing_embeddings.append(vector)

        for new_art in new_articles:
            new_vector = new_art.get("embedding")
            if not new_vector:
                # No embedding available, keep it by default (safer)
                filtered_articles.append(new_art)
                continue

            # Compare against existing database articles
            is_duplicate = False
            if existing_embeddings:
                sims = cosine_similarity([new_vector], existing_embeddings)[0]
                if np.max(sims) > similarity_threshold:
                    logger.info(f"Semantically duplicate article detected and dropped: '{new_art.get('title')}' (matches DB article)")
                    is_duplicate = True

            # Compare against articles already accepted in this batch
            if not is_duplicate and filtered_articles:
                accepted_embeddings = [art["embedding"] for art in filtered_articles if art.get("embedding")]
                if accepted_embeddings:
                    sims_batch = cosine_similarity([new_vector], accepted_embeddings)[0]
                    if np.max(sims_batch) > similarity_threshold:
                        logger.info(f"Semantically duplicate article detected and dropped: '{new_art.get('title')}' (matches batch article)")
                        is_duplicate = True

            if not is_duplicate:
                filtered_articles.append(new_art)

        return filtered_articles

    def search_similar_articles(self, query: str, articles: List[Dict[str, Any]], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Vector search engine: Queries articles semantically and returns list of (article, score) tuples."""
        query_vector = self.embed_text(query)
        if not query_vector or not articles:
            return []

        embeddings = []
        valid_articles = []
        for art in articles:
            vector = art.get("embedding")
            if vector:
                embeddings.append(vector)
                valid_articles.append(art)

        if not embeddings:
            return []

        sims = cosine_similarity([query_vector], embeddings)[0]
        results = []
        for idx, score in enumerate(sims):
            results.append((valid_articles[idx], float(score)))

        # Sort descending by score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
