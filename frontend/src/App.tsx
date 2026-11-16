import { useState } from "react";
import {
  ArrowRight, BarChart3, Camera, Check, ChevronDown, CircleAlert,
  FileImage, Leaf, LoaderCircle, Search, ShieldCheck, Sparkles, Upload, X,
} from "lucide-react";

type Nutrition = { label: string; value: string; unit: string; tone?: string };

const nutrition: Nutrition[] = [
  { label: "Energy", value: "472", unit: "kcal / 100 g", tone: "orange" },
  { label: "Protein", value: "7.4", unit: "g / 100 g", tone: "green" },
  { label: "Total sugars", value: "18.6", unit: "g / 100 g", tone: "yellow" },
  { label: "Total fat", value: "21.2", unit: "g / 100 g", tone: "red" },
];

const ingredients = [
  ["Wheat flour", "Base ingredient"],
  ["Sugar", "Sweetener"],
  ["Palm oil", "Fat source"],
  ["Raising agents (INS 500(ii), INS 503(ii))", "Additive"],
];

type OcrMetadata = {
  filename: string | null;
  width: number;
  height: number;
  bytes: number;
  preprocessing: string;
  averageConfidence: number | null;
};

const OCR_ENDPOINT = `${import.meta.env.VITE_OCR_URL ?? "http://127.0.0.1:8000"}/ocr`;

function App() {
  const [barcode, setBarcode] = useState("");
  const [searched, setSearched] = useState(false);
  const [image, setImage] = useState<string | null>(null);
  const [ocrText, setOcrText] = useState("");
  const [confirmedText, setConfirmedText] = useState<string | null>(null);
  const [ocrMetadata, setOcrMetadata] = useState<OcrMetadata | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ocrError, setOcrError] = useState<string | null>(null);

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
    setConfirmedText(null);
    setOcrMetadata(null);
    setOcrError(null);
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
              <button onClick={() => setSearched(true)} aria-label="Search"><ArrowRight size={19} /></button>
            </div>
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
            <button className="action-card" onClick={() => setSearched(true)}><span className="action-icon green-bg"><Search /></span><span><b>Look up a product</b><small>Search by barcode or product name</small></span><ArrowRight /></button>
          </div>
          <input id="upload" hidden type="file" accept="image/jpeg,image/png" onChange={(e) => onImage(e.target.files?.[0])} />
          {image && <div className="upload-preview"><img src={image} alt="Selected food label" /><div><b>{ocrLoading ? "Reading label…" : "Label uploaded"}</b><p>{ocrLoading ? `Uploading and extracting text (${uploadProgress}%)` : "Review the extracted text below."}</p></div><button onClick={() => { setImage(null); setOcrText(""); setConfirmedText(null); setOcrMetadata(null); setOcrError(null); }} aria-label="Remove image"><X size={18} /></button></div>}
          {ocrError && <div className="ocr-error"><CircleAlert size={17} />{ocrError}</div>}
        </section>

        {image && (ocrLoading || ocrText || ocrError) && <section className="review-section">
          <div className="analysis-heading"><div><p className="eyebrow">OCR review</p><h2>Check the extracted label text</h2><p className="muted">Correct anything the camera or label layout made unclear before continuing.</p></div>{ocrLoading && <span className="status-pill"><LoaderCircle className="spin" size={14} /> Reading label</span>}</div>
          {ocrLoading ? <div className="ocr-loading"><LoaderCircle className="spin" size={25} /><span>Preprocessing image and running Tesseract OCR…</span></div> : ocrText && <><label className="review-label" htmlFor="ocr-text">Extracted text</label><textarea id="ocr-text" value={ocrText} onChange={(event) => { setOcrText(event.target.value); setConfirmedText(null); }} rows={11} /><div className="review-actions"><button className="primary-button" onClick={() => setConfirmedText(ocrText)}><Check size={16} /> Confirm corrected text</button>{ocrMetadata && <small>{ocrMetadata.width} × {ocrMetadata.height}px · {Math.round(ocrMetadata.bytes / 1024)} KB · {ocrMetadata.averageConfidence === null ? "Confidence unavailable" : `${ocrMetadata.averageConfidence}% average confidence`}</small>}</div>{confirmedText !== null && <div className="confirmed"><Check size={16} /> Text confirmed. Nutrition parsing will use this reviewed text in the next milestone.</div>}</>}
        </section>}

        {searched && <section className="analysis-section">
          <div className="analysis-heading"><div><p className="eyebrow">Example analysis</p><h2>Good Day Whole Grain Crackers</h2><p className="muted">Sample data · Per 100 g serving</p></div><span className="status-pill"><span /> Partial data</span></div>
          <div className="notice"><CircleAlert size={18} /><span><b>Read this first:</b> This is an informational interpretation, not medical advice. Some label fields were not available.</span></div>
          <div className="analysis-grid"><div className="panel nutrition-panel"><div className="panel-title"><span><BarChart3 size={18} /> Nutrition snapshot</span><ChevronDown size={18} /></div><div className="nutrition-grid">{nutrition.map((item) => <div className="nutrition-item" key={item.label}><span className={`nutrition-value ${item.tone}`}>{item.value}</span><b>{item.unit}</b><small>{item.label}</small></div>)}</div><div className="missing"><CircleAlert size={15} /> Added sugars and trans fat were not declared</div></div>
            <div className="panel"><div className="panel-title"><span><Leaf size={18} /> Ingredient highlights</span><ChevronDown size={18} /></div><div className="ingredient-list">{ingredients.map(([name, type]) => <div className="ingredient" key={name}><span className="ingredient-dot" /><span><b>{name}</b><small>{type}</small></span></div>)}</div><button className="text-button">See all ingredients <ArrowRight size={15} /></button></div></div>
        </section>}

        <section className="trust-section" id="how-it-works"><div className="section-intro"><p className="eyebrow">Built for clarity</p><h2>Answers, not alarm.</h2><p className="muted wide">AharaIQ helps you understand labels without turning food into a pass-or-fail test.</p></div><div className="trust-grid"><div><Sparkles className="trust-icon" /><h3>Explainable by design</h3><p>Every insight links back to a label value or ingredient. No mystery scores.</p></div><div><ShieldCheck className="trust-icon" /><h3>Honest about gaps</h3><p>Missing information stays missing. We show what we know and what we don’t.</p></div><div><Leaf className="trust-icon" /><h3>Made for Indian labels</h3><p>Understand INS codes, serving sizes and the details that matter locally.</p></div></div></section>
      </main>
      <footer id="about"><div className="brand">ahara<span>iq</span></div><p>Understand your food. Make your choice.</p><small>Prototype · Not medical advice · Data sources will be documented as integrations are added</small></footer>
    </div>
  );
}

export default App;
