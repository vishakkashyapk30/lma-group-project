"""Real generated PDFs through PyMuPDF: text-layer coverage, bundle splitting on Hindi and High Court pages, vision fallback."""

from __future__ import annotations

from tests.fixtures import pdfgen
from vakeel_sahayak.ingestion.classify import page_type_hint
from vakeel_sahayak.ingestion.pipeline import read_file, split_and_label
from vakeel_sahayak.ingestion.signals import compute_signals, passes_text_layer_check
from vakeel_sahayak.ingestion.thresholds import load_thresholds
from vakeel_sahayak.schemas.enums import DocumentType, ParseRoute

TH = load_thresholds()

HINDI_REMAND = (
    "न्यायिक मजिस्ट्रेट के न्यायालय में\nरिमांड आदेश दिनांक 16.05.2024\nप्रथम सूचना रिपोर्ट सं. 609/2024, थाना PS-59, धाराएं IPC 409।\n"
    "आरोपी को न्यायिक अभिरक्षा में रिमांड पर भेजा जाता है।"
)
HINDI_BAIL = "माननीय न्यायालय - Karnataka High Court\nजमानत आवेदन पर आदेश\nप्रथम सूचना रिपोर्ट सं. 609/2024, थाना PS-59।\nआवेदक ने नियमित जमानत की प्रार्थना की है।"
HINDI_CUSTODY = "अभिरक्षा प्रमाण पत्र\nजिला कारागार के अधीक्षक द्वारा दिनांक 03.02.2025 को जारी।\nप्रथम सूचना रिपोर्ट सं. 609/2024 में अभिरक्षा की अवधि 264 दिन है।"
HC_CALCUTTA = (
    "04.08.2025\n\nItem No.47Court No. 25Sudipta Allowed\n\nCRM (A) 2154 of 2025\n\nIn Re: An application for Anticipatory Bail under "
    "Section 482 of the Bharatiya Nagarik Suraksha Sanhita,\n2023 in connection with Gopalnagar Police Station Case No. 162/2025.\n\n"
    "For the Petitioner : Mr. Santanu Talundar\n\nFor the State : Mr. Arindam Sen"
)
FIR = "FIRST INFORMATION REPORT (under Section 173 BNSS)\nIntegrated Investigation Form-1 (IIF-1)\n1. District: Patna P.S.: PS-3 FIR No. 881/2025 Date: 04.05.2025"
CUSTODY = "CUSTODY CERTIFICATE\nIssued by the Superintendent, District Jail, on 04.08.2025.\nThe period of custody is 56 days."


def test_short_born_digital_page_has_full_text_coverage(require_pymupdf, pdfs):
    """A one-paragraph order is a complete text layer even though its blocks fill a few percent of the page."""
    pdf = pdfs.text("short.pdf", [pdfgen.REMAND_PAGE])
    s = compute_signals(str(pdf), 1)
    assert s.text_coverage == 1.0
    assert passes_text_layer_check(s, TH)


def test_scan_with_a_sparse_text_layer_is_thin(require_pymupdf, tmp_path):
    """A full-page scan image with only a stamp's worth of text on top has a thin layer (K2)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 600, 800), False)
    pix.set_rect(pix.irect, (235, 235, 235))
    page.insert_image(page.rect, pixmap=pix)
    page.insert_text((72, 60), "Scanned copy attested by the registry of the court", fontsize=8)
    path = tmp_path / "scan_sparse.pdf"
    doc.save(str(path))
    doc.close()
    s = compute_signals(str(path), 1)
    assert s.text_coverage is not None and s.text_coverage < 0.2
    assert not passes_text_layer_check(s, TH)


def test_small_logo_does_not_make_a_text_page_a_scan(require_pymupdf, tmp_path):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60), False)
    pix.set_rect(pix.irect, (10, 10, 10))
    page.insert_image(fitz.Rect(450, 30, 520, 100), pixmap=pix)
    page.insert_text((72, 120), pdfgen.REMAND_PAGE.split("\n")[0], fontsize=11)
    page.insert_text((72, 140), "The accused was produced before this Court and remanded to judicial custody.", fontsize=11)
    path = tmp_path / "logo.pdf"
    doc.save(str(path))
    doc.close()
    assert compute_signals(str(path), 1).text_coverage == 1.0


def test_hindi_title_after_a_court_line_is_the_pages_type():
    assert page_type_hint(HINDI_REMAND)[:2] == (DocumentType.REMAND_ORDER, 0.8)
    assert page_type_hint(HINDI_BAIL)[0] == DocumentType.BAIL_ORDER
    assert page_type_hint(HINDI_CUSTODY)[0] == DocumentType.CUSTODY_CERTIFICATE


def test_high_court_caption_below_the_list_header_is_a_bail_order():
    assert page_type_hint(HC_CALCUTTA)[0] == DocumentType.BAIL_ORDER
    assert page_type_hint("Some narrative page about the facts of the matter.\nIt has no title at all.")[0] is None


def test_hindi_bundle_splits_into_its_four_documents():
    """The base-14 fonts of tests/fixtures/pdfgen.py cannot carry Devanagari, so the Hindi pages go in as text layers."""
    from vakeel_sahayak.ingestion.bundles import split_into_documents
    from vakeel_sahayak.ingestion.signals import signals_from_text

    texts = [HINDI_REMAND, HINDI_BAIL, HINDI_CUSTODY, "प्रथम सूचना रिपोर्ट (धारा 173)\n1. जिला: नागपुर"]
    signals = [signals_from_text(t, 595.0 * 842.0, 1.0) for t in texts]
    assert split_into_documents(texts, signals, TH) == [(1, 1), (2, 2), (3, 3), (4, 4)]


def test_english_bundle_with_a_high_court_order_splits(require_pymupdf, pdfs):
    pdf = pdfs.text("en_bundle.pdf", [CUSTODY, pdfgen.REMAND_PAGE, HC_CALCUTTA, FIR])
    docs = split_and_label(read_file(str(pdf), TH), TH)
    assert [(d.first, d.last) for d in docs] == [(1, 1), (2, 2), (3, 3), (4, 4)]
    assert docs[2].doc_type == DocumentType.BAIL_ORDER


def test_image_only_pdf_asks_counsel_when_the_vision_model_cannot_load(require_pymupdf, pdfs, monkeypatch):
    """Torchvision or weights missing is 'no vision model', not a crash: the page falls through to ask-counsel."""
    import transformers

    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.vlm import LocalVisionClient

    def boom(*a, **k):
        raise ImportError("Qwen3VLVideoProcessor requires the Torchvision library")

    monkeypatch.setattr(transformers.AutoProcessor, "from_pretrained", boom)
    LocalVisionClient._load_failures.clear()
    monkeypatch.setattr(factory, "get_vision", lambda: LocalVisionClient("test/none", quant_4bit=False))
    monkeypatch.setattr("vakeel_sahayak.ingestion.routes.vision.get_vision", lambda: LocalVisionClient("test/none", quant_4bit=False))
    pdf = pdfs.scanned("scan.pdf", 2)
    f = read_file(str(pdf), TH)
    assert [p.outcome.route for p in f.pages] == [ParseRoute.ASK_COUNSEL] * 2
    LocalVisionClient._load_failures.clear()


def test_untitled_high_court_orders_split_from_their_neighbours():
    """Real High Court orders carry the court's name and a case number, not a title: they start a document of their own."""
    from vakeel_sahayak.ingestion.bundles import split_into_documents
    from vakeel_sahayak.ingestion.signals import signals_from_text

    delhi = "$~3\\n*INTHEHIGHCOURTOFDELHIATNEWDELHI+BAIL APPLN. 2667/2025 & CRL.M.A.\\n20731/2025KUSH VERMA.....Petitioner\\nversus\\nTHE STATE NCT OF DELHI"
    tripura = "HIGH COURT OF TRIPURA AGARTALA\\nA.B. 24/2025\\nSri Jagu Debnath ----Applicant(s) Versus The State of Tripura\\nOrder 19/03/2025"
    cases = {
        "order first, then a certificate": ([tripura, CUSTODY, FIR], [(1, 1), (2, 2), (3, 3)]),
        "order after an FIR": ([FIR, delhi, CUSTODY], [(1, 1), (2, 2), (3, 3)]),
        "order between a remand order and an FIR": ([pdfgen.REMAND_PAGE, delhi, FIR], [(1, 1), (2, 2), (3, 3)]),
    }
    for name, (texts, want) in cases.items():
        signals = [signals_from_text(t, 595.0 * 842.0, 1.0) for t in texts]
        assert split_into_documents(texts, signals, TH) == want, name


def test_a_continuation_page_without_a_title_stays_with_its_order():
    from vakeel_sahayak.ingestion.bundles import split_into_documents
    from vakeel_sahayak.ingestion.signals import signals_from_text

    texts = [HC_CALCUTTA, "The learned counsel for the petitioner submitted that the petitioner is innocent and has been in custody.", FIR]
    signals = [signals_from_text(t, 595.0 * 842.0, 1.0) for t in texts]
    assert split_into_documents(texts, signals, TH) == [(1, 2), (3, 3)]
