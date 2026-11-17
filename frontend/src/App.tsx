import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import {
  ArrowRight, BarChart3, Camera, Check, CircleAlert,
  Leaf, LoaderCircle, Search, ShieldCheck, Sparkles, Upload, X,
} from "lucide-react";
import { buildParsePayload, type OcrEvidence } from "./parsePayload";

type OcrMetadata = {
  filename: string | null;
  width: number;
  height: number;
  bytes: number;
  preprocessing: string;
  averageConfidence: number | null;
  ocrEvidence?: OcrEvidence;
};

const OCR_ENDPOINT = `${import.meta.env.VITE_OCR_URL ?? "http://127.0.0.1:8000"}/ocr`;
const PARSE_ENDPOINT = `${import.meta.env.VITE_OCR_URL ?? "http://127.0.0.1:8000"}/parse`;
const PRODUCT_API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8080";

type ProductResult = {
  found: boolean;
  barcode: string;
  name: string | null;
  brand: string | null;
  category: string | null;
  imageUrl: string | null;
  ingredients: string | null;
  nutritionFacts: Array<{ field: string; value: number; unit: string; basis: string }>;
  missingFields: string[];
  source: string;
};

type ParsedResult = {
  rawText: string;
  source: "ocr" | "reviewed";
  nutritionFacts: Array<{ field: string; label: string; originalValue: string; normalizedValue: number; unit: string; basis: string | null; confidence: string; reviewRequired: boolean }>;
  ingredients: Array<{ originalText: string; normalizedName: string; order: number }>;
  additives: Array<{ originalText: string; code: string; name: string | null; category: string | null; matchStatus: string }>;
  declaredAllergens: Array<{ name: string; originalText: string }>;
  possibleIngredientAllergens: Array<{ name: string; originalText: string }>;
  precautionaryStatements: Array<{ name: string; originalText: string }>;
  missingFields: string[];
  reviewWarnings: string[];
  parsingStatus: string;
};

function App() {
  const [barcode, setBarcode] = useState("");
  const [searched, setSearched] = useState(false);
  const [image, setImage] = useState<string | null>(null);
  const [ocrText, setOcrText] = useState("");
  const [originalOcrText, setOriginalOcrText] = useState("");
  const [confirmedText, setConfirmedText] = useState<string | null>(null);
  const [ocrMetadata, setOcrMetadata] = useState<OcrMetadata | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [parsedResult, setParsedResult] = useState<ParsedResult | null>(null);
  const [parseLoading, setParseLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [productResult, setProductResult] = useState<ProductResult | null>(null);
  const [productLoading, setProductLoading] = useState(false);
  const [productError, setProductError] = useState<string | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const scannerRef = useRef<Html5Qrcode | null>(null);

  const lookupProduct = async (value = barcode) => {
    const trimmed = value.trim();
    setSearched(true);
    setProductResult(null);
    setProductError(null);
    if (!/^\d{8,14}$/.test(trimmed)) {
      setProductError("Enter a barcode containing 8 to 14 digits.");
      return;
    }
    setProductLoading(true);
    try {
      const response = await fetch(`${PRODUCT_API}/api/products/${encodeURIComponent(trimmed)}`);
      const body = await response.json() as ProductResult | { message?: string };
      if (!response.ok) {
        throw new Error(("message" in body && body.message) || "Product lookup failed.");
      }
      const product = body as ProductResult;
      if (!product.found) {
        setProductError("No product was found for this barcode in Open Food Facts.");
      } else {
        setProductResult(product);
      }
    } catch (error) {
      setProductError(error instanceof Error ? error.message : "Could not reach the product lookup service.");
    } finally {
      setProductLoading(false);
    }
  };

  useEffect(() => {
    if (!scannerOpen) return;
    const scanner = new Html5Qrcode("barcode-reader");
    scannerRef.current = scanner;
    scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 280, height: 120 } },
      (decodedText) => {
        setBarcode(decodedText);
        setScannerOpen(false);
        void lookupProduct(decodedText);
      },
      () => undefined,
    ).catch(() => {
      setProductError("Camera access was unavailable. Enter the barcode manually instead.");
      setScannerOpen(false);
    });
    return () => {
      if (scannerRef.current) {
        void scannerRef.current.stop().then(() => scannerRef.current?.clear());
        scannerRef.current = null;
      }
    };
  }, [scannerOpen]);

  const onImage = (file?: File) => {
    if (!file) return;
    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setOcrError("Please choose a JPG, JPEG or PNG label image.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setOcrError("Images must be smaller than 5 MB.");
      return;
    }
    setImage(URL.createObjectURL(file));
    setOcrText("");
    setOriginalOcrText("");
    setConfirmedText(null);
    setOcrMetadata(null);
    setOcrError(null);
    setParsedResult(null);
    setParseError(null);
    setOcrLoading(true);
    setUploadProgress(0);

    const request = new XMLHttpRequest();
    request.open("POST", OCR_ENDPOINT);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) setUploadProgress(Math.round((event.loaded / event.total) * 100));
    });
    request.addEventListener("load", () => {
      setOcrLoading(false);
      if (request.status >= 200 && request.status < 300) {
        const result = JSON.parse(request.responseText) as { text: string; metadata: OcrMetadata };
        setOcrText(result.text);
        setOriginalOcrText(result.text);
        setOcrMetadata(result.metadata);
        setUploadProgress(100);
      } else {
        try {
          setOcrError((JSON.parse(request.responseText) as { detail?: string }).detail ?? "OCR could not process this image.");
        } catch {
          setOcrError("OCR service returned an unexpected response.");
        }
      }
    });
    request.addEventListener("error", () => {
      setOcrLoading(false);
      setOcrError("Could not reach the OCR service. Start FastAPI on port 8000 and try again.");
    });
    const formData = new FormData();
    formData.append("file", file);
    request.send(formData);
  };

  const confirmText = async () => {
    setConfirmedText(ocrText);
    setParseLoading(true);
    setParseError(null);
    const textWasEdited = ocrText !== originalOcrText;
    try {
      const response = await fetch(PARSE_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          buildParsePayload(ocrText, originalOcrText, ocrMetadata?.ocrEvidence),
        ),
      });
      if (!response.ok) {
        const error = await response.json() as { detail?: string };
        throw new Error(error.detail ?? "The label parser returned an error.");
      }
      const parsed = await response.json() as ParsedResult;
      if (textWasEdited) {
        parsed.reviewWarnings = [
          ...parsed.reviewWarnings,
          "Reviewed OCR text differs from the original; coordinate table evidence was not applied. Numeric results require manual review.",
        ];
        parsed.nutritionFacts = parsed.nutritionFacts.map((fact) => ({
          ...fact,
          confidence: "review",
          reviewRequired: true,
        }));
        if (parsed.nutritionFacts.length > 0) {
          parsed.parsingStatus = "needs_review";
        }
      }
      setParsedResult(parsed);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Could not parse the reviewed text.");
    } finally {
      setParseLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top"><span className="brand-mark"><Leaf size={19} /></span> ahara<span>iq</span></a>
        <nav><a className="active" href="#analyze">Analyze</a><a href="#how-it-works">How it works</a><a href="#about">About</a></nav>
        <button className="outline-button" onClick={() => document.getElementById("upload")?.click()}><Upload size={16} /> Upload label</button>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-dot" /> Food label intelligence</p>
            <h1>Know what’s<br /><em>inside.</em></h1>
            <p className="hero-text">Make better food choices with clear, explainable insights from the labels you already have.</p>
            <div className="search-box">
              <Search size={20} />
              <input value={barcode} onChange={(e) => setBarcode(e.target.value)} placeholder="Search product or enter barcode" aria-label="Product or barcode" />
              <button className="scan-button" onClick={() => setScannerOpen(true)} aria-label="Scan barcode with camera"><Camera size={17} /></button>
              <button onClick={() => void lookupProduct()} aria-label="Search"><ArrowRight size={19} /></button>
            </div>
            {scannerOpen && <div className="scanner-panel"><div id="barcode-reader" /><button className="text-button" onClick={() => setScannerOpen(false)}>Close scanner</button></div>}
            <p className="hint"><ShieldCheck size={14} /> No account needed · Your scans stay private</p>
          </div>
          <div className="hero-art" aria-label="Illustration of a packaged snack">
            <div className="blob" /><div className="package"><div className="package-top">WHOLE<br /><strong>GRAIN</strong></div><div className="package-leaf"><Leaf size={46} /></div><div className="package-bottom">CRACKERS</div></div>
            <div className="floating-card card-one"><span className="mini-icon green-bg"><Check size={14} /></span><div><b>Simple insights</b><small>Made for you</small></div></div>
            <div className="floating-card card-two"><span className="mini-icon orange-bg"><BarChart3 size={15} /></span><div><b>8 / 12 fields</b><small>Data completeness</small></div></div>
          </div>
        </section>

        <section className="quick-actions" id="analyze">
          <div className="section-intro"><p className="eyebrow">Start an analysis</p><h2>Choose your way in</h2></div>
          <div className="action-grid">
            <button className="action-card" onClick={() => document.getElementById("upload")?.click()}><span className="action-icon orange-bg"><Camera /></span><span><b>Scan a label</b><small>Upload a photo of the nutrition label</small></span><ArrowRight /></button>
            <button className="action-card" onClick={() => document.querySelector<HTMLInputElement>(".search-box input")?.focus()}><span className="action-icon green-bg"><Search /></span><span><b>Look up a product</b><small>Search by barcode</small></span><ArrowRight /></button>
          </div>
          <input id="upload" hidden type="file" accept="image/jpeg,image/png" onChange={(e) => onImage(e.target.files?.[0])} />
          {image && <div className="upload-preview"><img src={image} alt="Selected food label" /><div><b>{ocrLoading ? "Reading label…" : "Label uploaded"}</b><p>{ocrLoading ? `Uploading and extracting text (${uploadProgress}%)` : "Review the extracted text below."}</p></div><button onClick={() => { setImage(null); setOcrText(""); setOriginalOcrText(""); setConfirmedText(null); setOcrMetadata(null); setOcrError(null); setParsedResult(null); setParseError(null); }} aria-label="Remove image"><X size={18} /></button></div>}
          {ocrError && <div className="ocr-error"><CircleAlert size={17} />{ocrError}</div>}
        </section>

        {image && (ocrLoading || ocrText || ocrError) && <section className="review-section">
          <div className="analysis-heading"><div><p className="eyebrow">OCR review</p><h2>Check the extracted label text</h2><p className="muted">Correct anything the camera or label layout made unclear before continuing.</p></div>{ocrLoading && <span className="status-pill"><LoaderCircle className="spin" size={14} /> Reading label</span>}</div>
          {ocrLoading ? <div className="ocr-loading"><LoaderCircle className="spin" size={25} /><span>Preprocessing image and running Tesseract OCR…</span></div> : ocrText && <><label className="review-label" htmlFor="ocr-text">Extracted text <span className="unreviewed-tag">Unreviewed OCR</span></label><textarea id="ocr-text" value={ocrText} onChange={(event) => { setOcrText(event.target.value); setConfirmedText(null); setParsedResult(null); }} rows={11} /><div className="review-actions"><button className="primary-button" onClick={confirmText} disabled={parseLoading}><Check size={16} /> {parseLoading ? "Parsing label…" : "Confirm and parse text"}</button>{ocrMetadata && <small>{ocrMetadata.width} × {ocrMetadata.height}px · {Math.round(ocrMetadata.bytes / 1024)} KB · {ocrMetadata.averageConfidence === null ? "Confidence unavailable" : `${ocrMetadata.averageConfidence}% average confidence`}</small>}</div>{confirmedText !== null && !parseLoading && !parseError && <div className="confirmed"><Check size={16} /> Text confirmed and parsed. Results below are based on your reviewed text.</div>}{parseError && <div className="ocr-error"><CircleAlert size={17} />{parseError}</div>}</>}
        </section>}

        {parsedResult && <section className="parsed-section">
          <div className="analysis-heading"><div><p className="eyebrow">Structured label</p><h2>What we found</h2><p className="muted">Parsed from user-reviewed text · No health score applied</p></div><span className="status-pill"><span /> {parsedResult.parsingStatus.replace("_", " ")}</span></div>
          {parsedResult.reviewWarnings.length > 0 && <div className="notice"><CircleAlert size={18} /><span>{parsedResult.reviewWarnings.join(" ")}</span></div>}
          <div className="parsed-grid">
            <div className="panel"><div className="panel-title"><span><BarChart3 size={18} /> Nutrition information</span></div>{parsedResult.nutritionFacts.length ? <div className="parsed-list">{parsedResult.nutritionFacts.map((fact) => <div className="parsed-row" key={fact.field}><span><b>{fact.label}</b><small>{fact.originalValue}{fact.basis ? ` · ${fact.basis.replace(/_/g, " ")}` : ""}</small></span><strong>{fact.normalizedValue} {fact.unit}{fact.reviewRequired ? " · review" : ""}</strong></div>)}</div> : <p className="muted">No nutrition values identified.</p>}<div className="missing">Missing: {parsedResult.missingFields.join(", ") || "none identified"}</div></div>
            <div className="panel"><div className="panel-title"><span><Leaf size={18} /> Ingredients</span></div>{parsedResult.ingredients.length ? <div className="ingredient-list">{parsedResult.ingredients.map((ingredient) => <div className="ingredient" key={`${ingredient.order}-${ingredient.originalText}`}><span className="ingredient-dot" /><span><b>{ingredient.originalText}</b><small>Normalized: {ingredient.normalizedName}</small></span></div>)}</div> : <p className="muted">No ingredients section identified.</p>}</div>
            <div className="panel"><div className="panel-title"><span><Sparkles size={18} /> Additives</span></div>{parsedResult.additives.length ? <div className="ingredient-list">{parsedResult.additives.map((additive) => <div className="ingredient" key={additive.code}><span className="ingredient-dot" /><span><b>{additive.originalText} · {additive.name ?? "Unknown additive"}</b><small>{additive.category ?? "No local category"} · {additive.matchStatus}</small></span></div>)}</div> : <p className="muted">No INS/additive codes identified.</p>}</div>
            <div className="panel"><div className="panel-title"><span><ShieldCheck size={18} /> Allergens</span></div><div className="allergen-group"><b>Declared</b><span>{parsedResult.declaredAllergens.map((item) => item.name).join(", ") || "None identified"}</span><b>Possible ingredient matches</b><span>{parsedResult.possibleIngredientAllergens.map((item) => item.name).join(", ") || "None identified"}</span><b>Precautionary</b><span>{parsedResult.precautionaryStatements.map((item) => `May contain ${item.name}`).join(", ") || "None identified"}</span></div><div className="missing">Absence of a finding does not prove allergen-free.</div></div>
          </div>
        </section>}

        {searched && <section className="analysis-section">
          <div className="analysis-heading"><div><p className="eyebrow">Product lookup</p><h2>{productLoading ? "Looking up product…" : productResult?.name ?? "Barcode result"}</h2><p className="muted">{productResult ? `${productResult.brand ?? "Brand unavailable"} · ${productResult.barcode}` : "Open Food Facts data will appear here"}</p></div>{productResult && <span className="status-pill"><span /> Partial data is possible</span>}</div>
          {productError && <div className="ocr-error"><CircleAlert size={17} />{productError}</div>}
          {productLoading && <div className="ocr-loading"><LoaderCircle className="spin" size={25} /> Querying Open Food Facts through the Java backend…</div>}
          {productResult && <div className="product-layout"><div className="panel product-summary">{productResult.imageUrl ? <img src={productResult.imageUrl} alt={`${productResult.name ?? "Product"} package`} /> : <div className="product-image-placeholder"><Leaf size={30} /></div>}<div><b>{productResult.name ?? "Name unavailable"}</b><small>{productResult.category ?? "Category unavailable"}</small><small>Source: {productResult.source}</small></div></div><div className="panel"><div className="panel-title"><span><BarChart3 size={18} /> Available nutrition</span></div>{productResult.nutritionFacts.length ? <div className="parsed-list">{productResult.nutritionFacts.map((fact) => <div className="parsed-row" key={fact.field}><span><b>{fact.field.replace(/_/g, " ")}</b><small>{fact.basis.replace(/_/g, " ")}</small></span><strong>{fact.value} {fact.unit}</strong></div>)}</div> : <p className="muted">No nutrition values available.</p>}<div className="missing">Missing: {productResult.missingFields.join(", ") || "none identified"}</div></div><div className="panel"><div className="panel-title"><span><Leaf size={18} /> Ingredients</span></div><p className="product-ingredients">{productResult.ingredients ?? "Ingredients unavailable."}</p></div></div>}
        </section>}

        <section className="trust-section" id="how-it-works"><div className="section-intro"><p className="eyebrow">Built for clarity</p><h2>Answers, not alarm.</h2><p className="muted wide">AharaIQ helps you understand labels without turning food into a pass-or-fail test.</p></div><div className="trust-grid"><div><Sparkles className="trust-icon" /><h3>Explainable by design</h3><p>Every insight links back to a label value or ingredient. No mystery scores.</p></div><div><ShieldCheck className="trust-icon" /><h3>Honest about gaps</h3><p>Missing information stays missing. We show what we know and what we don’t.</p></div><div><Leaf className="trust-icon" /><h3>Made for Indian labels</h3><p>Understand INS codes, serving sizes and the details that matter locally.</p></div></div></section>
      </main>
      <footer id="about"><div className="brand">ahara<span>iq</span></div><p>Understand your food. Make your choice.</p><small>Prototype · Not medical advice · Data sources will be documented as integrations are added</small></footer>
    </div>
  );
}

export default App;
