# Architecture notes

The frontend is intentionally usable without a server for the first
demonstration. In the integrated flow, the React client will call the Java
backend for product lookup and analysis. The Java service will coordinate
Open Food Facts and the OCR service; the Python service will only accept,
validate, preprocess, and extract text from images.

The Python service also exposes `POST /parse`. This endpoint uses deterministic
rules to parse user-reviewed OCR text into nutrition facts, ingredients,
additives, and allergen findings. It preserves raw text and original values
alongside normalized values. OCR and parsing remain separate so users can
correct OCR output before structured extraction.

Canonical products and OCR scan data must remain separate. A missing field is
represented by absence/null, never by a numeric zero. Analysis responses should
include both the source and completeness of each fact so the UI can explain
uncertainty.
