# Compliance Document Review App — Backend

FastAPI backend for the Compliance Document Review Platform.

The backend provides authentication, document upload/storage, document status management, and a secure internal endpoint that allows the Data Engineering pipeline to retrieve uploaded documents.

## Tech Stack

* Python 3.14
* FastAPI
* SQLAlchemy
* PostgreSQL
* JWT authentication
* Uvicorn
* Docker

## Project Structure

```text
Backend/
├── app/
│   ├── auth/
│   │   ├── router.py
│   │   ├── schema.py
│   │   ├── security.py
│   │   └── service_auth.py
│   │
│   ├── document/
│   │   ├── router.py
│   │   ├── model.py
│   │   └── schema.py
│   │
│   ├── model/
│   ├── schema/
│   ├── database.py
        revision.py
│   └── main.py
        
│
├── uploads/
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env
└── README.md
```

## Running Locally

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the `.env` file:

```env
DATABASE_URL=postgresql://postgres:<password>@localhost:5432/compliance_db
INTERNAL_SERVICE_TOKEN=<internal-service-token>
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## Running with Docker

Build the image:

```bash
docker build -t compliance-backend .
```

Run the container:

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  compliance-backend
```

### Important Docker Database Note

When the backend runs inside Docker, `localhost` refers to the Docker container itself, not the host machine.

For the final platform setup, the backend should use the PostgreSQL service provided by the platform's Docker Compose network.

The platform repository is responsible for connecting the backend to the shared PostgreSQL/pgvector database.

## API Endpoints

### Authentication

#### Register

```http
POST /api/v1/auth/register
```

Example request:

```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "role": "advisor"
}
```

#### Login

```http
POST api/v1/auth/login
```

Example request:

```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

Returns a JWT access token:

```json
{
  "access_token": "<token>",
  "token_type": "bearer"
}
```

#### Current User

```http
GET /api/v1/auth/me
```

Requires:

```http
Authorization: Bearer <jwt-token>
```

## Documents

### Upload Document

```http
POST api/v1/documents/upload
```

Requires a user JWT.

The endpoint accepts uploaded PDF/DOCX/XLSX files and stores the document in the backend.

Example response:

```json
{
  "id": 7,
  "filename": "DGA.pdf",
  "content_type": "application/pdf",
  "file_size": 3422452,
  "status": "pending_review",
  "advisor_id": 11,
  "created_at": "2026-09-08T13:49:19.509513+03:00"
}
```

### Internal Document File Access

```http
GET api/v1/documents/{document_id}/file
```

This endpoint is intended for **Data Engineering**, not normal user access.

It is protected using the shared:

```env
INTERNAL_SERVICE_TOKEN
```

Data Engineering sends the token in the request:

```http
Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
```

A successful request returns the original document file.

Example:

```bash
curl -i \
  http://127.0.0.1:8000/api/v1/documents/7/file \
  -H "Authorization: Bearer $INTERNAL_SERVICE_TOKEN"
```

The endpoint returns the original file with its appropriate content type.

## Data Engineering Integration

The agreed document-processing flow is:

```text
Frontend
   |
   | upload
   v
Backend
   |
   | stores original file
   v
Data Engineering
   |
   | GET /documents/{document_id}/file
   | authenticated with INTERNAL_SERVICE_TOKEN
   v
PDF/DOCX/XLSX extraction
   |
   v
Chunking
   |
   v
Embeddings
   |
   v
PostgreSQL + pgvector
```

The backend **does not extract the document text**.

Data Engineering owns:

* PDF extraction
* DOCX extraction
* XLSX extraction
* Chunking
* Embedding generation
* Vector storage
* Retrieval

The backend owns:

* File upload
* File storage
* Document metadata
* Document status
* Secure file access for internal services

## Authentication Model

There are two different authentication mechanisms.

### User Authentication

Users authenticate using JWT:

```text
Authorization: Bearer <JWT>
```

Used for normal application endpoints such as:

```text
/appi/v1/auth/me
/api/v1/documents/upload
```

### Internal Service Authentication

Trusted internal services use:

```text
Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
```

The internal token is used by Data Engineering to access:

```text
GET /api/v1/documents/{document_id}/file
```

The internal token must never be committed to Git.

## Environment Variables

| Variable                 | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `DATABASE_URL`           | PostgreSQL database connection               |
| `INTERNAL_SERVICE_TOKEN` | Authentication for trusted internal services |

Do not commit `.env` or real secrets to Git.

## Health Check

The backend exposes:

```http
GET /api/v1/health
```

This can be used by Docker Compose or other services to check whether the backend is running.

## Current Status

Implemented:

* [x] FastAPI application
* [x] PostgreSQL integration
* [x] User registration
* [x] User login
* [x] JWT authentication
* [x] Current-user endpoint
* [x] Document upload
* [x] Document metadata storage
* [x] Document file storage
* [x] Internal service authentication
* [x] Data Engineering file-access endpoint
* [x] Dockerfile
* [x] Docker image builds successfully
* [x] Health check endpoint

## Integration Responsibilities

### Backend

Provides:

```text
Authentication
Document upload
Document storage
Document metadata
Document file-access endpoint
```

### Data Engineering

Consumes the internal file-access endpoint and performs:

```text
Extraction
Chunking
Embeddings
Vector storage
Retrieval
```

### AI

Consumes retrieval results and provides AI-assisted compliance analysis.

### DevOps / Platform

Integrates the backend, frontend, AI service, and shared PostgreSQL/pgvector database through Docker Compose.

## Development

Start the development server:

```bash
uvicorn app.main:app --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

Before pushing changes:

```bash
git status
git diff
```

Then commit:

```bash
git add .
git commit -m "docs: add backend README"
git push origin main
```
