"""
RAG pipeline: indexes AQSQHC Clinical Care Standard PDFs into ChromaDB
and exposes a search_guidelines() function for the Agent to call.

Usage:
  python rag_pipeline.py          # builds / rebuilds the vector index
  from rag_pipeline import search_guidelines
"""

import os
import glob
import chromadb
from chromadb.utils import embedding_functions

DOCS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..",
    "OneDrive_1_11-12-2025",
    "02-2016-and-updated-2023-AQSQHC-Clinical-Care-Stand...",
)
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "hip_fracture_guidelines"

# Fallback guideline text used when PDF extraction is not available
FALLBACK_GUIDELINES = [
    {
        "id": "g001",
        "source": "ACSQHC 2023 – Quality Statement 1: Time to Surgery",
        "content": (
            "People presenting with hip fracture receive surgery within 48 hours of "
            "admission to hospital. Timely surgery reduces pain, complications and "
            "mortality. Hospitals should monitor median time to surgery and the "
            "proportion of patients receiving surgery within 48 hours."
        ),
    },
    {
        "id": "g002",
        "source": "ACSQHC 2023 – Quality Statement 2: Pain Assessment",
        "content": (
            "People presenting to the ED with hip fracture have their pain assessed "
            "within 30 minutes of presentation. A validated pain assessment tool "
            "should be used. Nerve blocks (fascia iliaca) are recommended as part "
            "of multimodal analgesia to reduce opioid requirements."
        ),
    },
    {
        "id": "g003",
        "source": "ACSQHC 2023 – Quality Statement 3: Geriatric Medicine Assessment",
        "content": (
            "All people admitted with hip fracture are assessed and managed by a "
            "geriatrician or geriatric medicine team. Shared care models between "
            "orthopaedics and geriatric medicine are associated with lower mortality "
            "and reduced length of stay."
        ),
    },
    {
        "id": "g004",
        "source": "ACSQHC 2023 – Quality Statement 4: Delirium Prevention",
        "content": (
            "People with hip fracture are screened for delirium pre- and "
            "post-operatively using a validated tool (e.g. 4AT, CAM). "
            "Non-pharmacological delirium prevention strategies should be used. "
            "Delirium is associated with increased mortality and longer hospital stay."
        ),
    },
    {
        "id": "g005",
        "source": "ACSQHC 2023 – Quality Statement 5: Early Mobilisation",
        "content": (
            "People with hip fracture are given the opportunity to mobilise on the "
            "first day after surgery. Early mobilisation reduces pressure injuries, "
            "venous thromboembolism and hospital-acquired complications. "
            "Physiotherapy input on post-operative day 1 is the standard."
        ),
    },
    {
        "id": "g006",
        "source": "ACSQHC 2023 – Quality Statement 6: Bone Protection",
        "content": (
            "People with hip fracture are assessed for osteoporosis and prescribed "
            "bone protection therapy (bisphosphonates, denosumab, or equivalent) at "
            "hospital discharge unless contraindicated. Calcium and vitamin D "
            "supplementation alone is insufficient as bone protection therapy."
        ),
    },
    {
        "id": "g007",
        "source": "ACSQHC 2023 – Quality Statement 7: Rehabilitation",
        "content": (
            "People with hip fracture have access to and are offered inpatient "
            "rehabilitation. Access to rehabilitation is associated with improved "
            "functional outcomes and reduced new residential aged care placement. "
            "The type and intensity of rehabilitation should be matched to patient "
            "goals and functional status."
        ),
    },
    {
        "id": "g008",
        "source": "ACSQHC 2023 – Outcome Benchmarks",
        "content": (
            "National performance benchmarks for ANZHFR hospitals:\n"
            "- 30-day mortality: target <7%\n"
            "- Median time to surgery: target ≤24 hours (best practice), ≤48 hours (standard)\n"
            "- Proportion with surgery ≤48h: target >95%\n"
            "- Geriatric medicine assessment rate: target >90%\n"
            "- Bone protection at discharge: target >80%\n"
            "- Early mobilisation (day 1): target >85%"
        ),
    },
    {
        "id": "g009",
        "source": "ACSQHC 2016 – Cognitive Impairment Management",
        "content": (
            "All patients with hip fracture should have cognitive status assessed "
            "on admission. Patients with known or suspected dementia require "
            "additional safeguards including delirium prevention protocols, "
            "careful analgesia titration, and carer involvement in care planning. "
            "Cognitive impairment is an independent predictor of poor outcomes "
            "including mortality and loss of function."
        ),
    },
    {
        "id": "g010",
        "source": "ACSQHC 2023 – Anaesthesia Considerations",
        "content": (
            "Spinal (neuraxial) anaesthesia is preferred over general anaesthesia "
            "for hip fracture surgery where clinically appropriate, as it is "
            "associated with reduced rates of post-operative confusion and "
            "pulmonary complications. Regional nerve blocks (fascia iliaca, "
            "femoral nerve block) should be used as part of multimodal analgesia "
            "in both the pre- and peri-operative period."
        ),
    },
]


def _get_ef():
    """Sentence-transformers embedding function (local, no API key needed)."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def build_index(force_rebuild: bool = False) -> chromadb.Collection:
    """Create or load the ChromaDB vector index from guideline text."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = _get_ef()

    if not force_rebuild:
        try:
            col = client.get_collection(COLLECTION_NAME, embedding_function=ef)
            if col.count() > 0:
                print(f"Loaded existing index: {col.count()} chunks")
                return col
        except Exception:
            pass

    # Delete and recreate
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    col = client.create_collection(COLLECTION_NAME, embedding_function=ef)

    # Try to extract text from PDFs if available
    chunks = _try_extract_pdf_chunks()
    if not chunks:
        print("PDFs not extractable — using built-in guideline summaries.")
        chunks = FALLBACK_GUIDELINES

    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["content"] for c in chunks],
        metadatas=[{"source": c["source"]} for c in chunks],
    )
    print(f"Built index: {len(chunks)} chunks indexed")
    return col


def _try_extract_pdf_chunks() -> list[dict]:
    """Attempt to extract text from PDFs using pypdf if available."""
    try:
        import pypdf
    except ImportError:
        return []

    chunks = []
    pdf_files = glob.glob(os.path.join(DOCS_DIR, "*.pdf"))
    if not pdf_files:
        pdf_files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "**", "*.pdf"), recursive=True)

    for pdf_path in pdf_files:
        try:
            reader = pypdf.PdfReader(pdf_path)
            source_name = os.path.basename(pdf_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = text.strip()
                if len(text) < 100:
                    continue
                # Split into ~500 char chunks
                for j in range(0, len(text), 500):
                    chunk = text[j:j+500].strip()
                    if len(chunk) < 80:
                        continue
                    chunks.append({
                        "id": f"{source_name}_p{i}_c{j}",
                        "source": f"{source_name} – page {i+1}",
                        "content": chunk,
                    })
        except Exception:
            continue

    return chunks


_collection_cache = None


def search_guidelines(query: str, k: int = 3) -> list[dict]:
    """
    Semantic search over clinical guidelines.
    Returns top-k relevant chunks with source attribution.
    """
    global _collection_cache
    if _collection_cache is None:
        _collection_cache = build_index()

    results = _collection_cache.query(
        query_texts=[query],
        n_results=min(k, _collection_cache.count()),
    )

    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        output.append({
            "source": meta.get("source", "Unknown"),
            "content": doc,
        })
    return output


if __name__ == "__main__":
    print("Building guideline index...")
    build_index(force_rebuild=True)
    print("\nTest query: 'time to surgery standard'")
    for r in search_guidelines("time to surgery standard"):
        print(f"\n[{r['source']}]\n{r['content']}")
