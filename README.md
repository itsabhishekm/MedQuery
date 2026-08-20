# MedQuery a RAG based Medical Assistant

## Overview

A Medical Assistant built on Retrieval-Augmented Generation (RAG) that answers clinical questions by retrieving knowledge directly from medical PDFs. At ingest time, PDF content is extracted and split into 500-character chunks, then encoded into dense vector representations using all-MiniLM-L6-v2, a lightweight sentence transformer that maps text into a 384-dimensional embedding space optimized for semantic similarity. Those embeddings are indexed in FAISS (Facebook AI Similarity Search), an in-memory vector store that performs approximate nearest-neighbor search at query time to surface the chunk most semantically relevant to the user's question. The retrieved passage is injected into a scoped system prompt and passed to Mistral 7B, which generates a concise, grounded answer constrained strictly to the provided context.

Deployment is handled through a Jenkins CI/CD pipeline running inside a custom Docker image that bundles Jenkins LTS, the Docker daemon, Aqua Trivy, and the AWS CLI — so the agent needs no pre-installed tooling on the host. On every push to main, Jenkins builds the application image, runs Aqua Trivy to scan for HIGH and CRITICAL CVEs and archives the JSON report, then authenticates with AWS and pushes the verified image to a private ECR repository, and is ready for deployment.

---

## Architecture

### RAG Pipeline

```
Medical PDF(s)
      │
      ▼
 PyPDF Loader          — extracts raw text page by page
      │
      ▼
 Text Chunker          — RecursiveCharacterTextSplitter (chunk=500, overlap=50)
      │
      ▼
 Embedding Model       — sentence-transformers/all-MiniLM-L6-v2 (HuggingFace)
      │
      ▼
 FAISS Vector Store    — persisted to vectorstore/db_faiss
      │
      ▼
 Semantic Retriever    — top-1 most relevant chunk (k=1)
      │
      ▼
 Mistral 7B (API)      — open-mistral-7b, temp=0.3, max_tokens=256
      │
      ▼
 Flask Chat UI         — session-aware, multi-turn web interface
```

### CI/CD Pipeline

```
GitHub (main branch)
      │
      ▼
 Jenkins (custom image — Jenkins LTS + Docker + Trivy + AWS CLI)
      │
      ├── Stage 1: Clone repo
      ├── Stage 2: Build Docker image
      ├── Stage 3: Aqua Trivy scan (HIGH + CRITICAL CVEs → trivy-report.json)
      └── Stage 4: Push image to AWS ECR (us-east-2)
```

---

## Project Structure

```
RAG-CHATBOT/
├── app/
│   ├── application.py              # Flask app — routes, session handling
│   ├── common/
│   │   ├── logger.py               # Structured logging utility
│   │   └── custom_exception.py     # Unified exception wrapper
│   ├── components/
│   │   ├── pdf_loader.py           # PDF ingestion + recursive text chunking
│   │   ├── embeddings.py           # HuggingFace embedding model loader
│   │   ├── llm.py                  # Mistral API LLM loader
│   │   ├── retriever.py            # LangChain QA chain (retriever + LLM)
│   │   └── vector_store.py         # FAISS index creation and loading
│   ├── config/
│   │   └── config.py               # Paths, chunk size, overlap params
│   └── templates/
│       ├── welcome.html            # Name entry / landing page
│       └── index.html              # Chat interface
│
├── custom_jenkins/
│   └── Dockerfile                  # Custom Jenkins image (Docker + Trivy + AWS CLI)
│
├── data/                           # Drop medical PDFs here before first run
├── vectorstore/                    # FAISS index (auto-generated on first run)
├── logs/                           # Application logs
│
├── Dockerfile                      # App container (python:3.10-slim, port 5000)
├── Jenkinsfile                     # CI/CD pipeline definition
├── requirements.txt                # Python dependencies
├── setup.py                        # Package install config
└── .env                            # API keys (not committed — see setup below)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Mistral AI : `open-mistral-7b` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) |
| Vector store | FAISS (CPU) |
| PDF extraction | PyPDF via LangChain `DirectoryLoader` |
| Orchestration | LangChain (`create_retrieval_chain`, `create_stuff_documents_chain`) |
| Web framework | Flask |
| Containerization | Docker (python:3.10-slim) |
| CI/CD | Jenkins |
| Security scanning | Aqua Trivy (HIGH + CRITICAL CVE detection) |
| Container registry | AWS ECR (us-east-2) |
| Knowledge base | Gale Encyclopedia of Medicine, 2nd Edition |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/itsabhishekm/MedQuery.git
cd MedQuery
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
MISTRAL_API_KEY=your_mistral_api_key_here
HF_TOKEN=your_huggingface_token_here
```

Get your Mistral API key at [console.mistral.ai](https://console.mistral.ai) and your HuggingFace token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

### 3. Add medical PDFs

Drop one or more PDF files into the `data/` directory. The system scans this directory on startup and indexes everything it finds.

### 4. Install dependencies and run locally

```bash
pip install -e .
python app/application.py
```

The app will load the PDFs, build the FAISS vector store (first run only — subsequent runs load from `vectorstore/db_faiss`), and start the Flask server at `http://localhost:5000`.

### 5. Run with Docker

```bash
docker build -t medquery .
docker run -p 5000:5000 --env-file .env medquery
```

---

## Configuration

All tunable parameters live in `app/config/config.py`:

| Parameter | Default | Description |
|---|---|---|
| `DATA_PATH` | `data/` | Directory scanned for PDF files |
| `DB_FAISS_PATH` | `vectorstore/db_faiss` | Where the FAISS index is saved/loaded |
| `CHUNK_SIZE` | `500` | Characters per text chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks |

LLM parameters are set in `app/components/llm.py` — temperature is `0.3` for factual, low-variance answers and `max_tokens` is capped at `256` to keep responses concise.

---

## CI/CD Pipeline

The Jenkins pipeline (`Jenkinsfile`) runs three stages on every push to `main`:

**Stage 1 — Clone:** Jenkins pulls the latest code from GitHub using stored credentials.

**Stage 2 — Build, Scan, and Push:** The Docker image is built, scanned with Aqua Trivy for HIGH and CRITICAL vulnerabilities (the report is archived as `trivy-report.json` in Jenkins), and then pushed to AWS ECR. The ECR URL is resolved dynamically from the AWS account ID at runtime — no hardcoded account numbers in the pipeline.

**Stage 3 — Deploy (optional):** An AWS App Runner deployment stage is included in the Jenkinsfile but currently commented out. Uncomment and configure the `SERVICE_NAME` environment variable to enable automatic deployment after each push.

### Custom Jenkins Image

`custom_jenkins/Dockerfile` builds a Jenkins image that bundles everything the pipeline needs: Docker-in-Docker support, Aqua Trivy, and the AWS CLI. This means the Jenkins agent itself requires no pre-installed tooling on the host machine.

```bash
# Build and run the custom Jenkins image
docker build -t custom-jenkins ./custom_jenkins
docker run -p 8080:8080 -p 50000:50000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  custom-jenkins
```

---

## How It Works

When a user submits a question through the chat interface, the Flask app passes it to the LangChain QA chain. The chain encodes the query using `all-MiniLM-L6-v2`, performs a cosine similarity search against the FAISS index to retrieve the single most relevant chunk (`k=1`), and injects that chunk into the system prompt alongside the user's question. Mistral 7B then generates a 2–3 line answer constrained strictly to the provided context, it cannot hallucinate outside the source material because the prompt explicitly instructs it to use only the retrieved passage.

The vector store is built once on first run and persisted to disk. Subsequent restarts load the existing index, so PDF re-processing is skipped unless the index is deleted.

---

## Security

- Aqua Trivy scans the built Docker image for HIGH and CRITICAL CVEs before it is pushed to ECR. The scan runs with `|| true` so a finding does not break the pipeline, but the full JSON report is archived in Jenkins for review.
- API keys are loaded from `.env` at runtime and are never committed to the repository (`.gitignore` excludes `.env`).
- The Flask session key is generated with `os.urandom(24)` at startup.

---

## Future Work

- Expand the knowledge base beyond a single encyclopedia — ingest specialty guidelines, clinical trial summaries, and drug reference PDFs.
- Increase retrieval breadth (`k > 1`) and evaluate answer quality with a RAGAS-style evaluation harness.
- Re-enable the AWS App Runner deployment stage for a fully automated push-to-deploy workflow.
- Add a document management UI so users can upload their own PDFs without touching the filesystem.
- Swap FAISS for a managed vector database (Pinecone, Weaviate, or pgvector) to support multi-user concurrent access at scale.
