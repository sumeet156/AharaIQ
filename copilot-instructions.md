
# AharaIQ Development Instructions

- Follow the architecture and scope defined in README.
- Use Java 21 and Spring Boot for the central backend.
- Use Python FastAPI only for OCR operations.
- Use React + Vite for the frontend.
- Use MySQL for persistent structured data.
- Keep business logic out of controllers.
- Use DTOs for API requests and responses.
- Never commit secrets, credentials or .env files.
- Validate all external API and OCR data.
- Missing values must remain missing, not become zero.
- Never claim medical accuracy or official certification.
- Write tests for important functionality.
- Update documentation when APIs or architecture change.
- Explain implementation decisions to the student.
- Work in small, verifiable milestones.
