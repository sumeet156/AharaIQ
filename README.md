# AharaIQ

AharaIQ is an explainable Indian packaged-food label analyzer. This repository
contains the first demonstrable vertical slice: a React dashboard with a
sample product analysis, barcode input, and label-image preview. Missing
nutrition values are shown as unavailable; they are never converted to zero.

## Project structure

```text
frontend/    React + Vite + TypeScript dashboard
backend/     Java 21 + Spring Boot API boundary
ocr-service/ Python FastAPI OCR boundary
database/    Versioned MySQL schema
docs/        Architecture and API notes
sample-data/ Demo label data
```

## Run the dashboard

```powershell
cd frontend
npm install
npm run dev
```

The current dashboard runs without a backend so it can be demonstrated
independently. The API and OCR services expose health endpoints for the next
integration milestone.

## Run the Java API

Install Java 21 and Maven, then:

```powershell
cd backend
mvn spring-boot:run
```

The health endpoint is `GET http://localhost:8080/api/health`.

## Run the OCR service

```powershell
cd ocr-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The OCR service currently validates image uploads and returns a clear
not-configured response until Tesseract is installed. This avoids pretending
OCR succeeded when the native dependency is absent.

## Design principles

- Declared allergens, precautionary statements, and inferred matches are
  separate concepts.
- No score or medical claim is made from incomplete data.
- External integrations will be added behind backend services, not directly
  embedded in UI components.
- Uploaded images are previewed in the browser and are not persisted by the
  prototype.

