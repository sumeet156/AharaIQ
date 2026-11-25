import assert from "node:assert/strict";
import { buildParsePayload } from "../src/parsePayload.ts";

const evidence = {
  lines: [
    {
      text: "Protein 10 g",
      words: [
        { text: "Protein", confidence: 90, left: 10, top: 20, width: 60, height: 18 },
      ],
    },
  ],
};

const unchanged = buildParsePayload("Protein 10 g", "Protein 10 g", evidence);
assert.deepEqual(unchanged.ocrEvidence, evidence);
assert.equal(unchanged.source, "reviewed");

const edited = buildParsePayload("Protein 11 g", "Protein 10 g", evidence);
assert.equal("ocrEvidence" in edited, false);

console.log("parse payload tests passed");
