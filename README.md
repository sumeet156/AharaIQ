# AharaIQ

AharaIQ is an explainable Indian packaged-food label analyzer. The current
vertical slice includes a React dashboard and a real FastAPI/Tesseract OCR
workflow. Missing nutrition values are shown as unavailable; they are never
converted to zero.

## Project structure

```text
frontend/    React + Vite + TypeScript dashboard
backend/     Java 21 + Spring Boot API boundary
ocr-service/ Python FastAPI + Tesseract OCR service
database/    Versioned MySQL schema
docs/        Architecture and API notes
sample-data/ Demo label data
```

## Run the dashboard

```powershell
cd "C:\MCA_2026-28\01_Semester_1\Mini_Project_1A\AharaIQ\frontend"
npm install
npx vite --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The upload control sends images directly to the
OCR service, displays an editable review text area, and sends confirmed text
to the deterministic label parser.

## Run the Java API

Install Java 21 and Maven, then:

```powershell
cd "C:\MCA_2026-28\01_Semester_1\Mini_Project_1A\AharaIQ\backend"
mvn spring-boot:run
```

The health endpoint is `GET http://localhost:8080/api/health`.

## Install and run the OCR service

Install [Tesseract OCR for Windows](https://github.com/tesseract-ocr/tesseract)
if it is not already installed. This project was verified with Tesseract 5.5.3
at `C:\Program Files\Tesseract-OCR\tesseract.exe`. The service checks
`TESSERACT_CMD` first, then the standard Windows installation locations:

```powershell
cd "C:\MCA_2026-28\01_Semester_1\Mini_Project_1A\AharaIQ\ocr-service"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TESSERACT_CMD = "C:\path\to\tesseract.exe" # only needed for a custom path
uvicorn app.main:app --reload --port 8000
```

Check `http://127.0.0.1:8000/health` before uploading. A configured service
returns `"status": "ok"` and `"tesseractConfigured": true`.

### OCR API

Request:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ocr `
  -F "file=@C:\path\to\label.png"
```

Successful response:

```json
{
  "text": "Nutrition Information ...",
  "metadata": {
    "filename": "label.png",
    "contentType": "image/png",
    "width": 1200,
    "height": 900,
    "bytes": 245678,
    "preprocessing": "grayscale, denoise, Otsu threshold",
    "averageConfidence": 87.42
  }
}
```

The endpoint returns `400` for invalid image bytes, `413` for files over 5 MB,
`415` for non-JPG/PNG uploads, and `503` when Tesseract is unavailable.

### Label parser API

The parser is intentionally separate from OCR so reviewed text can be parsed
again without uploading the image:

```powershell
curl.exe -X POST http://127.0.0.1:8000/parse `
  -H "Content-Type: application/json" `
  -d '{\"rawText\":\"Nutrition Information per 100 g Protein 10.59 g Ingredients: wheat flour, sugar. Contains wheat.\",\"source\":\"reviewed\"}'
```

The response contains the original text, nutrition facts with original and
normalized values, ingredient order, additive matches, allergen categories,
missing fields, review warnings, and parsing status. Known additive metadata is
maintained in `ocr-service/app/data/additives.json`; unknown INS codes remain
unknown and are not labelled harmful.

The UI labels OCR text as **Unreviewed OCR**. Parsing starts only after the user
confirms or edits the text, and the resulting cards are labelled as based on
reviewed text.

Run OCR tests with:

```powershell
python -m pytest
```

## Design principles

- Declared allergens, precautionary statements, and inferred matches are
  separate concepts.
- No score or medical claim is made from incomplete data.
- External integrations will be added behind backend services, not directly
  embedded in UI components.
- Uploaded images are previewed in the browser and are not persisted by the
  prototype.
