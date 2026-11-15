import { useState } from "react";
import {
  ArrowRight, BarChart3, Camera, Check, ChevronDown, CircleAlert,
  FileImage, Leaf, Search, ShieldCheck, Sparkles, Upload, X,
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

function App() {
  const [barcode, setBarcode] = useState("");
  const [searched, setSearched] = useState(false);
  const [image, setImage] = useState<string | null>(null);

  const onImage = (file?: File) => {
    if (!file) return;
    if (!["image/jpeg", "image/png"].includes(file.type)) {
      window.alert("Please choose a JPG or PNG label image.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      window.alert("Images must be smaller than 5 MB.");
      return;
    }
    setImage(URL.createObjectURL(file));
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
          {image && <div className="upload-preview"><img src={image} alt="Selected food label" /><div><b>Label ready to review</b><p>This is a local preview. OCR connection comes next.</p></div><button onClick={() => setImage(null)} aria-label="Remove image"><X size={18} /></button></div>}
        </section>

        {(searched || image) && <section className="analysis-section">
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

