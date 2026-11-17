export type OcrWordEvidence = {
  text: string;
  confidence: number | null;
  left: number;
  top: number;
  width: number;
  height: number;
};

export type OcrEvidence = {
  lines: Array<{ text: string; words: OcrWordEvidence[] }>;
};

export type ParsePayload = {
  rawText: string;
  source: "ocr" | "reviewed";
  ocrEvidence?: OcrEvidence;
};

export function buildParsePayload(
  reviewedText: string,
  originalText: string,
  evidence: OcrEvidence | undefined,
): ParsePayload {
  const payload: ParsePayload = {
    rawText: reviewedText,
    source: "reviewed",
  };
  if (evidence && reviewedText === originalText) {
    payload.ocrEvidence = evidence;
  }
  return payload;
}
