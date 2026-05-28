import re
from pathlib import Path

import fitz
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

CHROMA_DIR = "storage/chroma"
COLLECTION_NAME = "northwind_policies"


def extract_pdf_text(pdf_path: Path) -> str:
    text = ""
    doc = fitz.open(str(pdf_path))

    for page in doc:
        text += page.get_text() + "\n"

    return text


def split_policy_documents(text: str):
    pattern = r"(Document:\s+[A-Z]{2,5}-\d{3}[\s\S]*?)(?=Document:\s+[A-Z]{2,5}-\d{3}|$)"
    docs = re.findall(pattern, text)

    if docs:
        return docs

    return [text]


def get_policy_id(policy_text: str):
    match = re.search(r"Document:\s+([A-Z]{2,5}-\d{3})", policy_text)
    return match.group(1) if match else "UNKNOWN"


def strip_document_control(policy_text: str) -> str:
    patterns = [
        r"\n10\.\s*Document control[\s\S]*$",
        r"\nDocument control[\s\S]*$",
        r"\nVersion\s+Date\s+Author\s+Change[\s\S]*$",
        r"\nNext scheduled review:[\s\S]*$",
    ]

    cleaned = policy_text

    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def clean_text(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_sections(policy_id: str, policy_text: str):
    policy_text = clean_text(strip_document_control(policy_text))

    section_pattern = r"(?m)^(\d+(?:\.\d+)*)\.\s+([A-Z][^\n]{3,120})\n"
    matches = list(re.finditer(section_pattern, policy_text))

    chunks = []

    if not matches:
        return [{
            "policy_id": policy_id,
            "section": "full",
            "section_title": "Full document",
            "text": policy_text[:3000]
        }]

    for i, match in enumerate(matches):
        section_num = match.group(1)
        section_title = match.group(2).strip()

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(policy_text)

        section_text = policy_text[start:end].strip()

        if len(section_text) < 80:
            continue

        chunks.append({
            "policy_id": policy_id,
            "section": section_num,
            "section_title": section_title,
            "text": section_text
        })

    return chunks


def embed_text(text: str):
    """Embed a single text. Used by search_policies for query embedding."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding


def embed_texts_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call. Much faster than one-by-one."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )

    return [item.embedding for item in response.data]


def get_policy_folder():
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    return project_root / "data" / "policies"


def build_policy_index():
    policy_folder = get_policy_folder()

    if not policy_folder.exists():
        return {
            "status": "error",
            "message": f"Policy folder not found: {policy_folder}"
        }

    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = chroma_client.create_collection(name=COLLECTION_NAME)

    # Step 1: collect all chunks across all PDFs first
    all_chunks = []
    total_pdfs = 0

    for pdf_path in policy_folder.glob("*.pdf"):
        total_pdfs += 1
        pdf_text = extract_pdf_text(pdf_path)
        policy_docs = split_policy_documents(pdf_text)

        for policy_doc in policy_docs:
            policy_id = get_policy_id(policy_doc)
            chunks = split_sections(policy_id, policy_doc)

            for idx, chunk in enumerate(chunks):
                all_chunks.append({
                    "doc_id": f"{pdf_path.stem}-{policy_id}-{chunk['section']}-{idx}",
                    "text": chunk["text"],
                    "metadata": {
                        "source_file": pdf_path.name,
                        "policy_id": chunk["policy_id"],
                        "section": chunk["section"],
                        "section_title": chunk["section_title"],
                    }
                })

    if not all_chunks:
        return {
            "status": "error",
            "message": "No chunks were produced from the policy PDFs"
        }

    # Step 2: embed all chunks in one batch
    texts = [c["text"] for c in all_chunks]
    embeddings = embed_texts_batch(texts)

    # Step 3: add everything to Chroma in one call
    collection.add(
        ids=[c["doc_id"] for c in all_chunks],
        embeddings=embeddings,
        documents=[c["text"] for c in all_chunks],
        metadatas=[c["metadata"] for c in all_chunks],
    )

    return {
        "status": "ok",
        "message": "Policy index built successfully",
        "pdfs_indexed": total_pdfs,
        "chunks_indexed": len(all_chunks),
        "policy_folder": str(policy_folder)
    }


def search_policies(query: str, top_k: int = 5):
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    query_embedding = embed_text(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    matches = []

    for i in range(len(results["documents"][0])):
        matches.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })

    return matches