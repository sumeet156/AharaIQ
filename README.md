# AharaIQ

AharaIQ is an explainable Indian packaged-food label analyzer. The current
vertical slice includes a React dashboard and a real FastAPI/Tesseract OCR
workflow. Missing nutrition values are shown as unavailable; they are never
converted to zero.

## Project structure

```text
frontend/    React + Vite + TypeScript dashboard
backend/     Java 21 + Spring Boot product lookup API
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

## Run the Java product API

Install Java 21 and Maven, then:

```powershell
cd "C:\MCA_2026-28\01_Semester_1\Mini_Project_1A\AharaIQ\backend"
mvn spring-boot:run
```

The health endpoint is `GET http://localhost:8080/api/health`.
Barcode lookup is:

```text
GET http://localhost:8080/api/products/{barcode}
```

The backend validates 8–14 digit barcodes and calls Open Food Facts with a
descriptive `User-Agent`. It returns `found: false` for an unavailable product,
keeps unavailable fields as `null`, and reports absent nutrition fields in
`missingFields`. External service failures return `502`; invalid barcodes
return `400`.

The frontend defaults to `http://127.0.0.1:8080`. To use another backend port:

```powershell
$env:VITE_API_URL = "http://127.0.0.1:8081"
npx vite --host 127.0.0.1
```

The product search camera button uses `html5-qrcode`. Camera permission is
required, and manual barcode entry remains available when camera scanning is
not supported.

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
    "originalSha256": "…",
    "preprocessing": "resize, grayscale, denoise, deskew, adaptive threshold",
    "scale": 1.33,
    "deskewAngle": -2.5,
    "candidateCount": 2,
    "averageConfidence": 87.42
  }
}
```

The endpoint returns `400` for invalid image bytes, `413` for files over 5 MB,
`415` for non-JPG/PNG uploads, and `503` when Tesseract is unavailable.

### OCR accuracy improvements

The original upload bytes are never overwritten or persisted; the browser
continues to preview the original image, and the API returns its SHA-256 hash
and original dimensions for provenance. OCR preprocessing creates in-memory
candidates using:

- Cubic upscaling for small images, capped at three times the source size.
- Grayscale conversion and non-local-means denoising.
- Bounded projection-profile deskew for small rotations.
- Adaptive Gaussian thresholding and Otsu thresholding.
- Tesseract OCR on both candidates, selecting the non-empty result with the
  strongest confidence/text signal.

The selected strategy is reported in `metadata.preprocessing`. OCR text is
returned with line breaks where Tesseract detects separate text lines instead
of being silently flattened. The result remains reviewable because preprocessing
does not infer or correct nutrition values.

The OCR response also includes optional evidence metadata for the selected
candidate: median confidence, the proportion of low-confidence words, word and
line counts, and conservatively detected nutrition rows with text confidence
and image bounds. These fields help later review and table handling; they are
heuristics and are not guarantees that a value is correct.

Perspective correction is also an optional candidate. It is added only when a
validated rectangular contour is detected; the original adaptive and Otsu
candidates are always retained. `perspectiveConfidence` describes geometric
detection confidence, not OCR accuracy. Nutrition-row bounds use
`coordinateSpace: "selected_candidate_pixels"`, while returned perspective
corners use `perspectiveCornerCoordinateSpace: "resized_source_pixels"`.
Failed or ambiguous contour detection falls back to the original candidates.

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

### Table-aware OCR evidence

The `/ocr` response includes `metadata.ocrEvidence` for the selected OCR
candidate. It contains line and word text, confidence and pixel coordinates.
Clients that retain this metadata may send it back to `/parse` as optional
`ocrEvidence`:

```json
{
  "rawText": "Protein 10 g",
  "source": "ocr",
  "ocrEvidence": {
    "lines": [
      {
        "text": "Protein 10 g",
        "words": [
          {
            "text": "Protein",
            "confidence": 91.0,
            "left": 10,
            "top": 20,
            "width": 70,
            "height": 18
          }
        ]
      }
    ]
  }
}
```

When at least two nutrient rows and reliable numeric alignment are detected,
table-derived values retain their column type, serving basis, source text,
coordinates and review warnings. Missing or ambiguous serving headers never
become an inferred `per_100_g` or `per_serving` value. Without `ocrEvidence`,
the existing flattened-text parser remains the fallback.

The React review flow preserves the original OCR text separately from the
editable reviewed text. It forwards `ocrEvidence` only when the reviewed text
is unchanged. If the user edits the OCR text, the frontend intentionally omits
coordinate evidence and marks returned numeric results for manual review,
because original word coordinates may no longer correspond to the edited text.

The UI labels OCR text as **Unreviewed OCR**. Parsing starts only after the user
confirms or edits the text, and the resulting cards are labelled as based on
reviewed text.

Run OCR tests with:

```powershell
python -m pytest
```

The preprocessing tests cover small-image upscaling, candidate generation,
rotated-image deskewing, and invalid image bytes. The OCR and parser regression
tests remain part of the same suite.

Run Java API tests with:

```powershell
cd "C:\MCA_2026-28\01_Semester_1\Mini_Project_1A\AharaIQ\backend"
mvn test
```

The current product lookup test uses mocked Open Food Facts responses for
success, not-found, invalid barcode, and external failure cases. A live
verification can use a known barcode:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/products/3017620422003 |
  ConvertTo-Json -Depth 8
```

## Design principles

- Declared allergens, precautionary statements, and inferred matches are
  separate concepts.
- No score or medical claim is made from incomplete data.
- External integrations will be added behind backend services, not directly
  embedded in UI components.
- Uploaded images are previewed in the browser and are not persisted by the
  prototype.
