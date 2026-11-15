"""Original-PDF retrieval with page provenance and optional semantic/lexical fusion.

Default lexical retrieval is local and does not download models. Set HIP_RAG_MODE=hybrid
for Chroma + sentence-transformers reciprocal-rank fusion. No fabricated fallback text.
"""
import hashlib
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOPWORDS = set('the a an of to in on for and or is are be what how should does do with by from about standard guideline recommended'.split())


def _tokens(text):
    return [t for t in re.findall(r'[a-z0-9]+', text.lower()) if t not in STOPWORDS]


def _sources():
    directory = Path(os.environ.get('HIP_GUIDELINES_DIR', str(ROOT / 'guidelines'))).expanduser()
    paths = sorted(directory.glob('*.pdf')) if directory.is_dir() else []
    if not paths:
        raise FileNotFoundError('No original guideline PDFs in the configured directory')
    # Only this explicit directory; never recursively scan a user's parent folders.
    return tuple((str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)


@lru_cache(maxsize=4)
def _load_chunks(sources):
    from pypdf import PdfReader
    chunks = []
    for filename, _, _ in sources:
        path = Path(filename)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reader = PdfReader(path)
        for page_no, page in enumerate(reader.pages, 1):
            text = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
            # Sliding windows retain overlap and page boundaries for auditable citations.
            for offset in range(0, max(0, len(text)-40), 650):
                content = text[offset:offset+900]
                chunks.append(dict(id=f'{digest[:16]}-p{page_no}-c{offset}', document=path.name,
                                   page=page_no, sha256=digest, content=content,
                                   source=f'{path.name}, page {page_no}',
                                   superseded='superseded' in path.name.lower()))
    if not chunks:
        raise ValueError('PDFs contained no extractable text')
    return chunks


def _lexical_rank(chunks, query):
    terms = set(_tokens(query))
    if not terms:
        return []
    counts = [Counter(_tokens(c['content'])) for c in chunks]
    frequency = {t: sum(t in c for c in counts) for t in terms}
    scored = []
    for index, count in enumerate(counts):
        score = sum((1 + math.log(count[t])) * math.log(1 + len(chunks)/(1 + frequency[t]))
                    for t in terms if count[t])
        if score:
            scored.append((score, index))
    return [i for _, i in sorted(scored, key=lambda p: (-p[0], p[1]))]


def build_index(force_rebuild=False):
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    chunks = _load_chunks(_sources())
    fingerprint = hashlib.sha256('|'.join(c['id'] for c in chunks).encode()).hexdigest()[:20]
    client = chromadb.PersistentClient(path=os.environ.get('HIP_CHROMA_DIR', str(ROOT / 'chroma_db')))
    name = f'guideline_pdf_v2_{fingerprint}'
    embedding = SentenceTransformerEmbeddingFunction(model_name='all-MiniLM-L6-v2')
    if force_rebuild:
        try:
            client.delete_collection(name)
        except chromadb.errors.NotFoundError:
            pass
    collection = client.get_or_create_collection(name, embedding_function=embedding)
    # Content-addressed collection: never reuse the old summary-only vector index.
    if collection.count() != len(chunks):
        collection.upsert(ids=[c['id'] for c in chunks], documents=[c['content'] for c in chunks],
                          metadatas=[{k: c[k] for k in ('document', 'page', 'sha256', 'superseded')} for c in chunks])
    return collection


def _semantic_rank(chunks, query, k):
    col = build_index()
    result = col.query(query_texts=[query], n_results=min(max(k*4, 12), col.count()))
    positions = {c['id']: i for i, c in enumerate(chunks)}
    return [positions[i] for i in result['ids'][0] if i in positions]


def search_guidelines(query, k=3):
    if not isinstance(query, str) or not query.strip() or not 1 <= k <= 10:
        raise ValueError('Provide a query and k between 1 and 10')
    mode = os.environ.get('HIP_RAG_MODE', 'lexical')
    if mode not in ('lexical', 'hybrid'):
        raise ValueError('HIP_RAG_MODE must be lexical or hybrid')
    chunks = list(_load_chunks(_sources()))
    if '2016' not in query and 'superseded' not in query.lower():
        chunks = [c for c in chunks if not c['superseded']]
    lexical = _lexical_rank(chunks, query)
    ranking, actual_mode = lexical, 'lexical'
    if mode == 'hybrid':
        semantic = _semantic_rank(chunks, query, k)
        scores = {}
        for ranked in (lexical, semantic):
            for rank, i in enumerate(ranked, 1):
                scores[i] = scores.get(i, 0) + 1/(60 + rank)
        ranking = sorted(scores, key=lambda i: (-scores[i], i))
        actual_mode = 'hybrid_rrf'
    return [dict(citation=f'G{j}', retrieval_mode=actual_mode, **chunks[i])
            for j, i in enumerate(ranking[:k], 1)]


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', default='time to surgery')
    parser.add_argument('--build-semantic', action='store_true')
    args = parser.parse_args()
    if args.build_semantic:
        build_index(force_rebuild=True)
    print(json.dumps(search_guidelines(args.query), ensure_ascii=False, indent=2))
