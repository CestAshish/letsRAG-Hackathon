import fitz
import json
import uuid
import re
import os
from typing import List, Dict, Any

def extract_hierarchical_blocks(pdf_path: str) -> List[Dict[str, Any]]:
    """Extracts text blocks from a PDF while tracking hierarchical structure (Title, Chapter, Article)."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")
        
    doc = fitz.open(pdf_path)
    
    current_title = None
    current_chapter = None
    current_section = None
    current_article = None
    
    raw_blocks = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict").get("blocks", [])
        
        for b in blocks:
            if b.get('type') != 0:
                continue
                
            block_text = ""
            is_bold = False
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "") + " "
                    if "bold" in span.get("font", "").lower():
                        is_bold = True
                        
            block_text = block_text.strip().replace('\n', ' ')
            if len(block_text) < 5:
                continue
                
            title_match = re.match(r'^(TITLE\s+[IVX]+)\b(?!.*[;,]\s*$)(.*)', block_text, re.IGNORECASE)
            chapter_match = re.match(r'^(CHAPTER\s+[IVX\d]+)\b(?!.*[;,]\s*$)(.*)', block_text, re.IGNORECASE)
            section_match = re.match(r'^(SECTION\s+\d+)\b(?!.*[;,]\s*$)(.*)', block_text, re.IGNORECASE)
            article_match = re.match(r'^(Article\s+\d+\w*)\b(?!.*[;,]\s*$)(.*)', block_text, re.IGNORECASE)
            annex_match = re.match(r'^(ANNEX\s+[IVX]+)\b(?!.*[;,]\s*$)(.*)', block_text, re.IGNORECASE)
            
            if title_match and len(block_text) < 200:
                current_title = block_text
                current_chapter, current_section, current_article = None, None, None
            elif annex_match and len(block_text) < 200:
                current_title = block_text
                current_chapter, current_section, current_article = None, None, None
            elif chapter_match and len(block_text) < 200:
                current_chapter = block_text
                current_section, current_article = None, None
            elif section_match and len(block_text) < 200:
                current_section = block_text
                current_article = None
            elif article_match and len(block_text) < 200:
                current_article = block_text
            elif is_bold and current_article and block_text != current_article and len(block_text) < 200:
                if " - " not in current_article:
                    current_article = f"{current_article} - {block_text}"
            
            node_path = []
            if current_title: node_path.append(current_title)
            if current_chapter: node_path.append(current_chapter)
            if current_section: node_path.append(current_section)
            if current_article: node_path.append(current_article)
            
            raw_blocks.append({
                "text": block_text,
                "bbox": list(b.get("bbox", [])),
                "page": page_num + 1,
                "node_path": node_path,
                "is_bold": is_bold
            })
            
    return raw_blocks

def _estimate_tokens(text: str) -> int:
    """Rough estimation of tokens based on word count."""
    return int(len(text.split()) * 1.3)

def build_tree_and_chunks(raw_blocks: List[Dict[str, Any]], max_tokens=500, overlap_tokens=50):
    """Chunks text while building a hierarchical TOC tree."""
    toc_tree = {}
    chunks = []
    
    current_chunk_lines = []
    current_chunk_tokens = 0
    current_node_path = None
    line_counter = 1
    
    def _flush_chunk(is_boundary_change=False):
        nonlocal current_chunk_lines, current_chunk_tokens, line_counter
        if not current_chunk_lines: return
        
        merged_text = " \n".join(l["text"] for l in current_chunk_lines)
        first_line = current_chunk_lines[0]
        
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": merged_text.strip(),
            "metadata": {
                "page": first_line["page"],
                "bbox": first_line["bbox"],
                "node_path": current_node_path,
                "lines": current_chunk_lines
            }
        })
        
        if not is_boundary_change and len(current_chunk_lines) > 1:
            overlap = current_chunk_lines[-1]
            current_chunk_lines = [{"num": 1, "text": overlap["text"], "bbox": overlap["bbox"], "page": overlap["page"]}]
            current_chunk_tokens = _estimate_tokens(overlap["text"])
            line_counter = 2
        else:
            current_chunk_lines = []
            current_chunk_tokens = 0
            line_counter = 1

    for b in raw_blocks:
        path = b.get("node_path", [])
        
        if path != current_node_path:
            _flush_chunk(is_boundary_change=True)
            current_node_path = path
            
        block_tokens = _estimate_tokens(b["text"])
        if current_chunk_tokens > 0 and (current_chunk_tokens + block_tokens) > max_tokens:
            _flush_chunk(is_boundary_change=False)
            
        current_chunk_lines.append({
            "num": line_counter,
            "text": b["text"],
            "bbox": b["bbox"],
            "page": b["page"]
        })
        current_chunk_tokens += block_tokens
        line_counter += 1
        
    _flush_chunk(is_boundary_change=True)
    
    # Filter out empty or tiny chunks
    chunks = [c for c in chunks if len(c["text"].split()) > 5]
    
    for chunk in chunks:
        path = chunk["metadata"]["node_path"]
        if not path:
            continue
            
        current = toc_tree
        for i, node_name in enumerate(path):
            if node_name not in current:
                current[node_name] = {
                    "_type": "parent" if i < len(path)-1 else "leaf",
                    "_name": node_name,
                    "chunks": [] if i == len(path)-1 else None,
                    "children": {}
                }
            if i == len(path)-1:
                current[node_name]["chunks"].append(chunk)
            current = current[node_name]["children"]
            
    return toc_tree, chunks

if __name__ == "__main__":
    # Fix: Corrected the path to point to the PDF in the frontend's public folder
    base_dir = os.path.dirname(os.path.dirname(__file__))
    pdf_path = os.path.join(base_dir, "frontend", "public", "EU_AI_Act.pdf")
    
    print(f"Extracting blocks from {pdf_path}...")
    raw = extract_hierarchical_blocks(pdf_path)
    
    print("Building tree and chunks...")
    toc, chunks = build_tree_and_chunks(raw)
    
    print(f"Total chunks generated: {len(chunks)}")
    
    app_dir = os.path.dirname(__file__)
    data_dir = os.path.join(app_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    chunks_path = os.path.join(data_dir, "corpus_blocks_hierarchical.json")
    toc_path = os.path.join(data_dir, "toc_tree.json")
    
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)
        
    with open(toc_path, "w", encoding="utf-8") as f:
        json.dump(toc, f, indent=2)
        
    print(f"Done. Saved:\n- {chunks_path}\n- {toc_path}")
