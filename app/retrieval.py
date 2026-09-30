import json
import re
import os
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple
from app.adapters.hf_adapter import HuggingFaceAdapter

class HuggingFaceAPIEmbeddings:
    """Wrapper using the central HuggingFaceAdapter for Embeddings"""
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.adapter = HuggingFaceAdapter(model_name=model_name)

    def encode(self, texts: List[str], convert_to_numpy: bool = True) -> np.ndarray:
        if isinstance(texts, str): texts = [texts]
        
        results = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            res = self.adapter.feature_extraction(batch)
            if hasattr(res, "tolist"): res = res.tolist()
            if len(batch) == 1 and isinstance(res, list) and len(res) > 0 and isinstance(res[0], float):
                res = [res]
            results.extend(res)
        return np.array(results, dtype=np.float32)

class HFAPI_CrossEncoder:
    """Wrapper using the central HuggingFaceAdapter for Cross Encoders"""
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.adapter = HuggingFaceAdapter(model_name=model_name)
    
    def predict(self, pairs: List[Tuple[str, str]]) -> np.ndarray:
        scores = self.adapter.text_classification(pairs)
        return np.array(scores, dtype=np.float32)

def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for BM25."""
    text = re.sub(r'[^\w\s]', '', text.lower())
    return text.split()

class StructuralHybridRetriever:
    """
    Hybrid retriever that uses Dense Embeddings (FAISS), Sparse (BM25), 
    and a Hierarchical TOC Tree for exact node resolution.
    """
    def __init__(self, embed_model_name: str = "all-MiniLM-L6-v2", rerank_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        provider = os.getenv("LR_EMBEDDING_PROVIDER", "local")
        if provider == "huggingface_api":
            hf_embed = embed_model_name
            if "/" not in hf_embed:
                hf_embed = "sentence-transformers/" + hf_embed
            self.embedder = HuggingFaceAPIEmbeddings(hf_embed)
            self.reranker = HFAPI_CrossEncoder(rerank_model_name)
        else:
            from sentence_transformers import SentenceTransformer, CrossEncoder
            self.embedder = SentenceTransformer(embed_model_name, model_kwargs={"use_safetensors": False})
            self.reranker = CrossEncoder(rerank_model_name, model_kwargs={"use_safetensors": False})
            
        self.chunks = []
        self.toc_tree = {}
        self.bm25 = None
        self.index = None

    def load_and_index(self, chunks_path: str, toc_path: str = None):
        """Loads chunks and toc_tree and uses cached FAISS/BM25 indexes if available to save startup time."""
        import pickle
        import logging
        logger = logging.getLogger(__name__)
        
        with open(chunks_path, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
            
        if toc_path:
            with open(toc_path, 'r', encoding='utf-8') as f:
                self.toc_tree = json.load(f)
                
        # Define cache paths alongside the data json files
        data_dir = os.path.dirname(chunks_path)
        faiss_path = os.path.join(data_dir, "faiss_index.bin")
        bm25_path = os.path.join(data_dir, "bm25_index.pkl")
        
        # 1. Try loading from cache
        if os.path.exists(faiss_path) and os.path.exists(bm25_path):
            logger.info("Loading pre-computed FAISS and BM25 indexes from disk cache...")
            self.index = faiss.read_index(faiss_path)
            with open(bm25_path, 'rb') as f:
                self.bm25 = pickle.load(f)
            return
            
        # 2. Otherwise compute from scratch
        logger.info("Computing embeddings and building indexes from scratch...")
        bm25_corpus = []
        texts_for_dense = []
        
        for c in self.chunks:
            base_text = c.get("text", "")
            node_path = c.get("metadata", {}).get("node_path", [])
            heading = " > ".join(node_path) if node_path else c.get("metadata", {}).get("parent_heading", "")
            
            texts_for_dense.append(f"Heading: {heading}. Content: {base_text}")
            bm25_text = f"{base_text} {heading} {heading} {heading}"
            bm25_corpus.append(_tokenize(bm25_text))
            
        self.bm25 = BM25Okapi(bm25_corpus)
        embeddings = self.embedder.encode(texts_for_dense, convert_to_numpy=True)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        # 3. Save to disk for future use
        faiss.write_index(self.index, faiss_path)
        with open(bm25_path, 'wb') as f:
            pickle.dump(self.bm25, f)
        logger.info("Successfully saved indexes to disk cache.")

    def _normalize_node_name(self, text: str) -> str:
        """Normalizes document nodes like 'Title I' to 'title i' for easier search."""
        text = re.sub(r'\s+', ' ', text.lower().strip())
        roman_map = {'1': 'i', '2': 'ii', '3': 'iii', '4': 'iv', '5': 'v', '6': 'vi', '7': 'vii', '8': 'viii', '9': 'ix', '10': 'x', '11': 'xi', '12': 'xii', '13': 'xiii'}
        def repl(m):
            prefix = m.group(1)
            num = m.group(2)
            return f"{prefix} {roman_map.get(num, num)}"
        return re.sub(r'(chapter|title|annex)\s+(\d+)', repl, text)

    def _find_node_in_tree(self, tree: Dict, target: str, current_path: str = "") -> Dict:
        """Recursively search TOC tree for a node matching the target using full node paths."""
        if not target: return None
            
        target_clean = self._normalize_node_name(target)
        target_tokens = set(target_clean.split())
        
        for k, v in tree.items():
            k_clean = self._normalize_node_name(k)
            path_so_far = current_path + " " + k_clean if current_path else k_clean
            path_tokens = set(path_so_far.split())
            
            if target_tokens.issubset(path_tokens):
                return v
            if "children" in v and v["children"]:
                res = self._find_node_in_tree(v["children"], target, path_so_far)
                if res: return res
        return None
        
    def _get_outline_context(self, node: Dict) -> List[Dict[str, Any]]:
        """Extracts context blocks from a tree node."""
        results = []
        if node.get("_type") == "leaf":
            return node.get("chunks", [])[:10]
            
        def recurse_gather(n):
            if n.get("children"):
                for child in n["children"].values():
                    recurse_gather(child)
            else:
                chunks = n.get("chunks", [])
                if chunks:
                    first_chunk = chunks[0]
                    preview = {
                        "id": first_chunk["id"],
                        "text": f"Preview of {n.get('_name')}: " + first_chunk["text"][:600] + "...",
                        "metadata": first_chunk.get("metadata", {}),
                        "is_outline": True
                    }
                    results.append(preview)
                    
        recurse_gather(node)
        return results

    def _search_single(self, query: str, intent: Dict, retrieve_k: int = 50, precomputed_emb=None) -> Tuple[List[Dict], List[Dict]]:
        """Executes a single search branch based on intent scores."""
        toc_results = []
        vector_candidates = set()
        
        # 1. TOC Branch
        if intent.get("article_confidence", 0) > 0.5:
            targets = intent.get("target_articles", [])
            for t in targets:
                node = self._find_node_in_tree(self.toc_tree, t)
                if node:
                    toc_results.extend(self._get_outline_context(node))
                    
        # 2. Sparse Branch (BM25)
        if intent.get("keyword_confidence", 0) > 0.5:
            toks = _tokenize(query)
            scores = self.bm25.get_scores(toks)
            top_sparse = np.argsort(scores)[::-1][:retrieve_k]
            vector_candidates.update(top_sparse.tolist())
            
        # 3. Dense Branch (FAISS)
        if intent.get("semantic_confidence", 0) > 0.5:
            emb = precomputed_emb if precomputed_emb is not None else self.embedder.encode([query], convert_to_numpy=True)
            dist, dense_idx = self.index.search(emb, retrieve_k)
            vector_candidates.update(dense_idx[0].tolist())
            
        valid_vector_cands = [idx for idx in vector_candidates if 0 <= idx < len(self.chunks)]
        return toc_results, valid_vector_cands

    def search_batch_parallel(self, queries: List[str], intents: List[Dict], query_embeddings: List[List[float]] = None, top_k: int = 5, retrieve_k: int = 50, score_threshold: float = -5.0) -> List[List[Dict]]:
        """Parallel batched hybrid retrieval."""
        if not self.chunks:
            return [[] for _ in queries]
            
        batch_toc_results = []
        batch_vector_candidates = []
        
        for i, (q, intent) in enumerate(zip(queries, intents)):
            q_emb = np.array([query_embeddings[i]], dtype=np.float32) if query_embeddings and query_embeddings[i] else None
            toc_res, vec_cands = self._search_single(q, intent, retrieve_k, q_emb)
            batch_toc_results.append(toc_res)
            batch_vector_candidates.append(vec_cands)
            
        # CrossEncoder Reranking
        cross_inp = []
        cross_inp_lens = []
        
        for i, q in enumerate(queries):
            cands = batch_vector_candidates[i]
            for idx in cands:
                c = self.chunks[idx]
                node_path = c.get("metadata", {}).get("node_path", [])
                heading = " > ".join(node_path) if node_path else c.get("metadata", {}).get("parent_heading", "")
                cross_inp.append([q, f"Heading: {heading}. {c.get('text', '')}"])
            cross_inp_lens.append(len(cands))
            
        if not cross_inp:
            return batch_toc_results
            
        all_scores = self.reranker.predict(cross_inp)
        
        final_results = []
        if len(queries) > 5:
            # Exception case: each query gives 1 top_k
            ptr = 0
            for i, q in enumerate(queries):
                c_len = cross_inp_lens[i]
                scores = all_scores[ptr:ptr+c_len]
                cands = batch_vector_candidates[i]
                
                ranked = sorted(zip(cands, scores), key=lambda x: x[1], reverse=True)
                filtered = [((idx, self.chunks[idx]), s) for idx, s in ranked if s >= score_threshold]
                if not filtered and ranked:
                    filtered = [((idx, self.chunks[idx]), s) for idx, s in ranked[:1]]
                    
                top_vector = [c for (idx, c), s in filtered[:1]] # strictly 1
                
                seen_ids = set()
                merged = []
                for c in batch_toc_results[i]:
                    if c["id"] not in seen_ids:
                        merged.append(c)
                        seen_ids.add(c["id"])
                for c in top_vector:
                    if c["id"] not in seen_ids and len(merged) < 1 + len(batch_toc_results[i]):
                        merged.append(c)
                        seen_ids.add(c["id"])
                final_results.append(merged)
                ptr += c_len
            return final_results
        else:
            # Normal case: global top 5 across ALL queries in the batch
            global_candidates = []
            ptr = 0
            for i, q in enumerate(queries):
                c_len = cross_inp_lens[i]
                scores = all_scores[ptr:ptr+c_len]
                cands = batch_vector_candidates[i]
                for idx, s in zip(cands, scores):
                    global_candidates.append((idx, s))
                ptr += c_len
                
            ranked = sorted(global_candidates, key=lambda x: x[1], reverse=True)
            
            seen_ids = set()
            top_vector = []
            for idx, s in ranked:
                c = self.chunks[idx]
                if c["id"] not in seen_ids and (s >= score_threshold or len(top_vector) < 3):
                    top_vector.append(c)
                    seen_ids.add(c["id"])
                if len(top_vector) >= 5:
                    break
                    
            merged = []
            toc_seen = set()
            for toc_list in batch_toc_results:
                for c in toc_list:
                    if c["id"] not in toc_seen:
                        merged.append(c)
                        toc_seen.add(c["id"])
            
            for c in top_vector:
                if c["id"] not in toc_seen and len(merged) < 5 + len(toc_seen):
                    merged.append(c)
                    toc_seen.add(c["id"])
                    
            # Return as a list of lists so flattening in core.py works perfectly
            if not queries:
                return []
            final = [merged] + [[] for _ in range(len(queries)-1)]
            return final
