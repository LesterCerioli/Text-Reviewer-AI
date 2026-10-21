import asyncio
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime


try:
    from sentence_transformers import SentenceTransformer, util
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    MODEL = None


class PlagiarismDetector:
        
    def __init__(self, similarity_threshold: float = 0.75):
        self.similarity_threshold = similarity_threshold
        self.model = MODEL
        self.corpus_embeddings = None
        self.source_sentences = []
        self.document_map = {}  # maps sentence index to document info
    
    async def detect_all(
        self,
        all_sentences: List[Any],
        compare_against: str = "public"
    ) -> List[Dict[str, Any]]:
        
        if not self.model:
            raise RuntimeError("Sentence transformer model not available")
        
        
        sentences_text = [s.text for s in all_sentences]
        embeddings = self.model.encode(sentences_text, convert_to_tensor=False)
        
        
        self.corpus_embeddings = embeddings
        self.source_sentences = sentences_text
        self.document_map = self._build_document_map(all_sentences)
        
        
        results = []
        
        for i, sentence_obj in enumerate(all_sentences):
            result = await self._detect_single(
                i, sentence_obj, embeddings, compare_against
            )
            results.append(result)
        
        return results
    
    def _build_document_map(self, sentences: List[Any]) -> Dict[int, Tuple[int, int]]:
        
        mapping = {}
        current_doc = -1
        doc_count = 0
        
        for i, sent in enumerate(sentences):
            if sent.doc_index != current_doc:
                current_doc = sent.doc_index
                doc_count = 1
            else:
                doc_count += 1
            mapping[i] = (sent.doc_index, sent.sentence_index)
        
        return mapping
    
    async def _detect_single(
        self,
        sentence_idx: int,
        sentence_obj: Any,
        query_embedding: np.ndarray,
        compare_against: str
    ) -> Dict[str, Any]:
        
        sentence_text = sentence_obj.text
        
        
        if self.corpus_embeddings is None:
            query_emb = self.model.encode(sentence_text)
        else:
            query_emb = query_embedding[sentence_idx]
        
        
        similarities = []
        
        if self.corpus_embeddings is not None and len(self.corpus_embeddings) > 1:
            
            from sentence_transformers import util
            cos_sims = util.cos_sim(query_emb, self.corpus_embeddings)[0]
            
            
            indexed_sims = list(enumerate(cos_sims.numpy()))
            indexed_sims.sort(key=lambda x: x[1], reverse=True)
                        
            top_similarities = []
            for j, sim in indexed_sims:
                if j == sentence_idx:
                    continue  # Skip self-comparison
                if sim > self.similarity_threshold:
                    top_similarities.append({
                        "similarity": float(sim),
                        "target_idx": j,
                        "target_text": self.source_sentences[j],
                        "target_doc": self.document_map[j][0]
                    })
                
                if len(top_similarities) >= 5:  # Limit to top 5 matches
                    break
        
        
        is_plagiarized = len(top_similarities) > 0
                
        best_match = top_similarities[0] if top_similarities else None
        
        return {
            "sentence_id": sentence_idx,
            "original_text": sentence_text,
            "is_plagiarized": is_plagiarized,
            "similarity_score": best_match["similarity"] if best_match else 0.0,
            "source_urls": self._get_source_urls(best_match) if best_match else [],
            "rephrased_text": None,  
            "acceptance_status": False,
            "best_match_text": best_match["target_text"] if best_match else None,
            "best_match_doc": best_match["target_doc"] if best_match else None
        }
    
    def _get_source_urls(self, match: Optional[Dict]) -> List[str]:
        
        if not match:
            return []
        
        return [f"https://example-source.com/paper/{match.get('target_idx', 0)}"]