#!/usr/bin/env python3
"""Finance transport/response adapter for the existing host rubric bridge.

The shared module owns its CLI, env-file loading, Docker image allowlist,
sealed-request validation, listener, logs and response injection. This module
only replaces that process's grade function. Importing it performs no I/O to
credentials, Docker or a grading API. PDF page selection is a transport
projection, never a replacement for the full sealed request saved in logs.
"""
import copy
import hashlib
import importlib.util
import json
import math
import re
import threading
from pathlib import Path


SHARED_PATH = Path(__file__).resolve().with_name("host_rubric_bridge.py")
ADAPTER_VERSION = "finance-pdf-projection-v2-explicit-evidence-anchors"
TASKS = {f"finance-pilot-{number:02d}-v2" for number in range(1, 6)}
# Physical page numbers, established against these task packages' originals.
FIXED_PACKS = {
    "finance-pilot-01-v2": {
        "F003": {1, 7, 23, 24, 31, *range(77, 86), *range(128, 131),
                 140, 163, 164, 165, 181, 189, 190}},
    "finance-pilot-02-v2": {
        "F011": {*range(1, 23), 149}, "F013": None,
        "F014": set(range(1, 23))},
    "finance-pilot-03-v2": {
        "F025": {1, 6, 7, 9, 10, 11, 18, 19, 28, 61}},
    "finance-pilot-04-v2": {},
    "finance-pilot-05-v2": {
        "F048": None, "F049": None, "F050": {1, 14, 15, 16}},
}
# Sources lacking a printed_page field in their native sealed extraction.
# F003's physical and printed numbers coincide; F025 has an unnumbered cover.
PRINTED_OFFSETS = {"F003": 0, "F025": 1}
KNOWN_PAGE_COUNTS = {
    "F003": 224, "F011": 216, "F013": 32, "F014": 218, "F025": 99,
    "F048": 22, "F049": 16, "F050": 82,
}
SOURCE_ID = re.compile(r"(?<![A-Za-z0-9])F\d{3}(?!\d)")
RANGE_SEPARATOR = r"(?:[-–—~～至]|(?i:to|through))"
NUMBER_LIST = r"\d+(?:\s*(?:" + RANGE_SEPARATOR + r"\s*\d+|[,，、/&]\s*\d+))*"
PAGE_REF = re.compile(
    r"(?P<kind>physical(?:[ _-]*pages?)?|物理(?:页码|页面|页)?|"
    r"printed(?:[ _-]*pages?)?|印刷(?:页码|页面|页)?|"
    r"(?<![A-Za-z0-9])p(?:p)?\.?|页码)\s*[:：_-]?\s*"
    r"(?P<numbers>" + NUMBER_LIST + r")", re.IGNORECASE)
CHINESE_PAGE = re.compile(r"第\s*(" + NUMBER_LIST + r")\s*页")
LOCATOR_FIELD = re.compile(r"locator|source_ref|citation|引用|页码", re.I)
PAGE_MARKER = re.compile(r"(?:physical|printed|物理|印刷|页码)[^。；;\n]*\d|第[^。；;\n]*页", re.I)
REFERENCE_CUE = re.compile(r"序号|章节|(?:section|clause|chapter)\s*\d", re.I)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def verify_seal(req):
    if req.get("task_id") not in TASKS or req.get("schema_version") != 1:
        raise ValueError("Unsupported finance task/schema")
    original = {key: value for key, value in req.items() if key != "request_sha256"}
    if req.get("request_sha256") != digest(original):
        raise ValueError("Sealed finance request digest changed")
    if not isinstance(req.get("inputs"), dict) or not isinstance(req.get("outputs"), dict):
        raise ValueError("Finance input/output mappings absent")
    criteria = req.get("rubric", {}).get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Finance rubric criteria absent")
    ids = [criterion.get("id") for criterion in criteria]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Rubric IDs are not unique nonempty strings")
    for criterion in criteria:
        points = criterion.get("points")
        if (isinstance(points, bool) or not isinstance(points, (int, float))
                or not math.isfinite(points) or points < 0):
            raise ValueError("Rubric maximum is not finite and nonnegative")


def _document_id(filename):
    match = SOURCE_ID.search(filename)
    return match.group() if match else filename


def _expand_numbers(text, maximum):
    """Expand every page in a range; no range-width or page-count clipping."""
    numbers = set()
    for token in re.split(r"\s*[,，、/&]\s*", text):
        bounds = re.split(r"\s*" + RANGE_SEPARATOR + r"\s*", token)
        if not all(part.isdigit() for part in bounds) or len(bounds) not in (1, 2):
            raise ValueError("Unresolved page range")
        first, last = int(bounds[0]), int(bounds[-1])
        if not 1 <= first <= last <= maximum:
            raise ValueError("Page range lies outside supplied source")
        numbers.update(range(first, last + 1))
    return numbers


def _page_mentions(text):
    found = []
    for match in PAGE_REF.finditer(text):
        kind = match["kind"].lower()
        # Uppercase P3 in an XLSX formula/coordinate is not a PDF citation.
        if kind in ("p", "pp", "p.", "pp.") and match["kind"].isupper():
            continue
        basis = "physical" if kind.startswith("physical") or kind.startswith("物理") else (
            "printed" if kind.startswith("printed") or kind.startswith("印刷") else "unspecified")
        number_text = match["numbers"]
        if re.match(r"\s*" + RANGE_SEPARATOR + r"(?:\s*$|\s*[^\d\s])", text[match.end():]):
            number_text += "-unresolved"
        found.append((basis, number_text))
    found.extend(("unspecified", match[1]) for match in CHINESE_PAGE.finditer(text))
    return found


class PageSelection:
    def __init__(self, req):
        self.req = req
        self.documents = {}
        self.selected = {}
        self.reasons = {}
        self.fallbacks = []
        self.fact_sources = {}
        for fact in req.get("evidence_context", {}).get("verified_facts", []):
            sources = {group.get("document_id") for group in fact.get("source_groups", [])}
            for field in ("check_id", "draft_id"):
                if fact.get(field):
                    self.fact_sources.setdefault(fact[field], set()).update(sources)
        for name, source in req["inputs"].items():
            if not name.lower().endswith(".pdf"):
                continue
            pages = source.get("pages")
            if not isinstance(pages, list) or not pages:
                raise ValueError("Supplied PDF has no complete page extraction: " + name)
            mapping = {}
            for page in pages:
                number = page.get("physical_page")
                if isinstance(number, bool) or not isinstance(number, int) or number in mapping:
                    raise ValueError("PDF physical page mapping is unreliable: " + name)
                if not isinstance(page.get("text"), str):
                    raise ValueError("PDF page text is unavailable: " + name)
                mapping[number] = page
            if set(mapping) != set(range(1, len(pages) + 1)):
                raise ValueError("PDF extraction has missing/non-contiguous physical pages: " + name)
            if source.get("page_count", len(pages)) != len(pages):
                raise ValueError("PDF page count disagrees with supplied extraction: " + name)
            source_id = _document_id(name)
            if source_id in self.documents:
                raise ValueError("Ambiguous PDF source identity: " + source_id)
            expected_count = KNOWN_PAGE_COUNTS.get(source_id, source.get("page_count"))
            if expected_count is None or expected_count != len(pages):
                raise ValueError("PDF extraction does not cover its verified original page count: " + name)
            self.documents[source_id] = (name, source, mapping)
            self.selected[source_id] = set()
            self.reasons[source_id] = {}
            raw_hash = source.get("sha256")
            if not isinstance(raw_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", raw_hash):
                raise ValueError("PDF raw-source SHA256 is unavailable: " + name)
        packs = FIXED_PACKS[req["task_id"]]
        if not set(packs).issubset(self.documents):
            raise ValueError("Required broad-pack PDF source is absent")
        for source_id in self.documents:
            if source_id not in packs or packs[source_id] is None:
                self.retain_all([source_id], "full-source policy")
            else:
                self.add(source_id, packs[source_id], "physical", "fixed broad source pack")

    def retain_all(self, source_ids, reason):
        for source_id in source_ids:
            self.add(source_id, set(self.documents[source_id][2]), "physical", reason)
        self.fallbacks.append({"sources": sorted(source_ids), "reason": reason})

    def add(self, source_id, numbers, basis, reason):
        if source_id not in self.documents:
            return
        mapping = self.documents[source_id][2]
        physical = set()
        if basis in ("physical", "unspecified"):
            if not numbers.issubset(mapping):
                self.retain_all([source_id], reason + ": invalid physical locator; retain full source")
                return
            physical.update(numbers)
        if basis in ("printed", "unspecified"):
            if any("printed_page" in page for page in mapping.values()):
                printed = {}
                for page_number, page in mapping.items():
                    if page.get("printed_page") is not None:
                        printed.setdefault(page["printed_page"], set()).add(page_number)
                if not numbers.issubset(printed):
                    self.retain_all([source_id], reason + ": unresolved printed locator; retain full source")
                    return
                for number in numbers:
                    physical.update(printed[number])
            elif source_id in PRINTED_OFFSETS:
                converted = {number + PRINTED_OFFSETS[source_id] for number in numbers}
                if not converted.issubset(mapping):
                    self.retain_all([source_id], reason + ": invalid printed locator; retain full source")
                    return
                physical.update(converted)
            else:
                self.retain_all([source_id], reason + ": printed mapping unavailable; retain full source")
                return
        for number in physical:
            self.selected[source_id].add(number)
            self.reasons[source_id].setdefault(number, set()).add(reason)

    def text(self, text, source_ids, origin, field):
        if not text.strip():
            return
        # This is a coordinate convention, not an unresolved page citation.
        if (not _page_mentions(text)
                and re.search(r"物理页\s*=\s*PDF页", text, re.I)
                and re.search(r"印刷页\s*=\s*物理页\s*[−–—-]\s*1", text)):
            return
        # CCA is the task's unambiguous visible name for F013; typed check/draft
        # IDs likewise bind to actual trusted source_groups, never a grade.
        if "F013" in self.documents and re.search(r"(?<![A-Za-z])CCA(?![A-Za-z])", text):
            source_ids = {"F013"}
        tagged = set()
        for identifier in re.findall(r"(?<![A-Za-z0-9])(?:D\d{2}|[A-Z]\d{2})(?!\d)", text):
            tagged.update(self.fact_sources.get(identifier, set()) & self.documents.keys())
        if tagged:
            source_ids = tagged
        aliases = list(SOURCE_ID.finditer(text))
        segments = []
        if aliases:
            prefix = text[:aliases[0].start()]
            if _page_mentions(prefix):
                segments.append((prefix, source_ids))
            for index, match in enumerate(aliases):
                stop = aliases[index + 1].start() if index + 1 < len(aliases) else len(text)
                segments.append((text[match.end():stop], {match.group()} & self.documents.keys()))
        else:
            segments.append((text, source_ids))
        for segment, associated in segments:
            mentions = _page_mentions(segment)
            if not mentions:
                if associated and (LOCATOR_FIELD.search(field) or PAGE_MARKER.search(segment)
                                   or (aliases and REFERENCE_CUE.search(segment))):
                    self.retain_all(associated, origin + ": locator has no reliably resolved page")
                continue
            if not associated:
                associated = set(self.documents) if len(self.documents) == 1 else set()
            if not associated:
                self.retain_all(set(self.documents), origin + ": page citation has ambiguous source")
                continue
            for source_id in associated:
                for basis, number_text in mentions:
                    try:
                        numbers = _expand_numbers(number_text, len(self.documents[source_id][2]))
                    except ValueError:
                        self.retain_all([source_id], origin + ": invalid/unresolved page range")
                    else:
                        self.add(source_id, numbers, basis, origin)

    def walk(self, value, source_ids=None, origin="candidate", field="", path=""):
        associated = set(source_ids or [])
        if isinstance(value, dict):
            # A row's source_locator and related_locator may refer to different
            # PDFs; each is parsed separately, never inherited from its sibling.
            for key in ("document_id", "source_id", "source_file", "filename", "file", "name"):
                identifier = value.get(key)
                if isinstance(identifier, str):
                    ids = set(SOURCE_ID.findall(identifier)) & self.documents.keys()
                    if ids:
                        associated = ids
                        break
            if not associated:
                for key in ("check_id", "draft_id"):
                    associated.update(self.fact_sources.get(value.get(key), set()) & self.documents.keys())
                for group in value.get("source_groups", []):
                    if isinstance(group, dict) and group.get("document_id") in self.documents:
                        associated.add(group["document_id"])
                for key, item in value.items():
                    if LOCATOR_FIELD.search(str(key)) and isinstance(item, str):
                        associated.update(set(SOURCE_ID.findall(item)) & self.documents.keys())
            for key, item in value.items():
                here = path + "/" + str(key)
                if associated and key in ("physical_page", "printed_page", "pages", "physical_pages", "printed_pages"):
                    if key == "pages" and not (isinstance(item, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in item)):
                        self.walk(item, associated, origin, str(key), here)
                        continue
                    numbers = item if isinstance(item, list) else [item]
                    if not numbers or any(isinstance(x, bool) or not isinstance(x, int) for x in numbers):
                        self.retain_all(associated, origin + here + ": unreliable structured locator")
                    else:
                        basis = "printed" if key.startswith("printed") else "physical"
                        for source_id in associated:
                            self.add(source_id, set(numbers), basis, origin + here)
                else:
                    self.walk(item, associated, origin, str(key), here)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self.walk(item, associated, origin, field, path + "/" + str(index))
        elif isinstance(value, str):
            self.text(value, associated, origin + path, field)


def project_request(req):
    verify_seal(req)
    selection = PageSelection(req)
    selection.walk(req.get("evidence_context", {}), origin="trusted evidence_context")
    selection.walk(req["rubric"], origin="trusted rubric")
    selection.walk(req["outputs"], origin="actual candidate")
    # Business source maps/README can supply further locators. They are always
    # transported whole; PDF page text itself must not recursively select pages.
    for name, source in req["inputs"].items():
        if not name.lower().endswith(".pdf"):
            # This task's supplied readable PDF derivative stays complete in the
            # transport. Its own page headers are not fresh candidate citations;
            # rescanning them would unnecessarily duplicate every PDF page.
            if (_document_id(name) in selection.documents and name.lower().endswith(".txt")
                    and re.match(r"\s*---\s*PAGE\s+1\s*---", source.get("text", ""), re.I)):
                continue
            selection.walk(source, origin="visible non-PDF input " + name)
    projected = copy.deepcopy(req)
    manifest = {
        "adapter_version": ADAPTER_VERSION,
        "projection_role": "Selected PDF pages for transport; not the full canonical sealed request",
        "original_sealed_request_sha256": req["request_sha256"],
        "preserved_complete_fields": [key for key in req if key not in ("inputs", "source_images")],
        "complete_non_pdf_inputs": [name for name in req["inputs"] if not name.lower().endswith(".pdf")],
        "pdf_sources": [], "conservative_full_source_fallbacks": selection.fallbacks,
        "source_images_metadata": [],
    }
    for source_id, (name, source, pages) in selection.documents.items():
        selected = selection.selected[source_id]
        projected["inputs"][name]["pages"] = [page for number, page in pages.items() if number in selected]
        # Retain all other source metadata, including its original page_count.
        projected["inputs"][name]["transport_selection"] = {
            "full_original_page_count": len(pages), "selected_physical_pages": sorted(selected),
            "text_is_selected_original_page_text": True}
        manifest["pdf_sources"].append({
            "filename": name, "document_id": source_id,
            "raw_source_sha256": source.get("sha256"), "full_original_page_count": len(pages),
            "selected_physical_pages": sorted(selected),
            "printed_mapping_fallback_offset": PRINTED_OFFSETS.get(source_id),
            "original_page_hashes": [{
                "physical_page": number, "printed_page": page.get("printed_page"),
                "text_sha256": hashlib.sha256(page["text"].encode("utf-8")).hexdigest(),
                "page_object_sha256": digest(page), "selected": number in selected,
                "selection_reasons": sorted(selection.reasons[source_id].get(number, []))}
                for number, page in pages.items()]})
    images = req.get("source_images", [])
    if not isinstance(images, list):
        raise ValueError("Supplied image sequence is not a list")
    for index, supplied in enumerate(images, 1):
        if not isinstance(supplied, dict) or not isinstance(supplied.get("data"), str):
            raise ValueError("Supplied request image lacks actual base64 data")
        metadata = {key: value for key, value in supplied.items() if key != "data"}
        manifest["source_images_metadata"].append({
            "request_sequence": index, "metadata": metadata,
            "base64_data_sha256": hashlib.sha256(supplied["data"].encode("ascii")).hexdigest()})
    # The delegate moves these exact images into actual Anthropic image blocks.
    # Keep data and every supplied metadata field; never relabel candidate pages.
    manifest["criterion_source_coverage"] = [{
        "criterion_id": criterion["id"],
        "source_pack": {source_id: sorted(selection.selected[source_id]) for source_id in selection.documents},
        "complete_non_pdf_inputs": manifest["complete_non_pdf_inputs"],
        "complete_actual_outputs": list(req["outputs"]),
        "coverage_method": "Broad original-source pack plus every resolved trusted/candidate page locator; complete business inputs, objective and actual outputs"}
        for criterion in req["rubric"]["criteria"]]
    projected["transport_projection"] = {
        "adapter_version": ADAPTER_VERSION,
        "original_sealed_request_sha256": req["request_sha256"],
        "note": "request_sha256 binds the full original request saved by the host; this transport projection has not been sealed under that digest",
        "pdf_sources": [{key: value for key, value in source.items() if key != "original_page_hashes"}
                        for source in manifest["pdf_sources"]],
        "source_images_metadata": manifest["source_images_metadata"],
    }
    projected["finance_response_requirements"] = response_contract(req)
    manifest["transport_projection_sha256"] = digest(projected)
    return projected, manifest


def response_contract(req):
    return {
        "actual_candidate_anchor_options": sorted(req["outputs"]),
        "actual_input_anchor_options": sorted(set(req["inputs"]) | {_document_id(name) for name in req["inputs"]}),
        "mandatory_positive_evidence": "Every positive criterion, including native usability, formatting and handoff criteria, must include an exact actual_candidate_anchor_options filename and an exact actual_input_anchor_options filename/source ID in its evidence strings, with concrete supported locations. For handoff/format requirements cite the supplied business dictionary, schema or basis document that establishes that requirement; output-only evidence is incomplete. Never invent an input anchor.",
        "criteria": [{"id": criterion["id"],
                      "score": "finite JSON number from 0 through " + str(criterion["points"]),
                      "reason": "nonempty specific substantive assessment string",
                      "evidence": ["actual candidate filename + concrete location/short quote; actual input filename/source ID + concrete location/short quote"]}
                     for criterion in req["rubric"]["criteria"]],
        "critical_error": "JSON boolean: independently judge whether this actual candidate contains any rubric-defined critical/serious error; never infer false from objective passing or default it",
        "critical_error_reason": "nonempty evidence-grounded explanation of the boolean judgment under the supplied rubric and actual candidate; name the triggering error or explain why none was found",
    }


FINANCE_SYSTEM_MARKER = "FINANCE_ADAPTER_RESPONSE_CONTRACT_V1"
FINANCE_SYSTEM_APPEND = """
FINANCE_ADAPTER_RESPONSE_CONTRACT_V1
Finance response requirements supplement the user schema: return one JSON
object with criteria, critical_error and critical_error_reason. critical_error
MUST be a JSON boolean explicitly assessed against the supplied rubric and the
actual candidate, never a default false and never inferred from objective
passing. critical_error_reason MUST be a nonempty, evidence-grounded string
explaining the boolean. In task 02 apply every rubric critical condition,
including false principal guarantees, mandatory redemption, write-down
restoration and reversed capital absorption/ranking. For tasks without a
critical-error cap, still explicitly state whether any supplied rubric-defined
critical/serious condition was found. Every rubric ID exactly once; scores must
be finite numbers within that criterion's points; nonempty substantive reason
strings and evidence string lists. Every positive score needs the actual
candidate filename and concrete location/short quote, plus the supplied input
filename/source ID and concrete location/short quote. Apply the rubric's actual
scoring scope and objective upper bounds. Do not add objective points or infer
professional correctness from them. Read all candidate cells, formulas,
caches, current/deleted/hidden text and contradictions.
The request is an explicit transport projection. Its request_sha256 binds the
full ORIGINAL sealed request saved by the host, not the projected PDF subset.
Selected pages contain their full original page text. Non-PDF inputs, business
workpapers, actual candidate extraction, objective and rubric remain complete.
Images can be actual candidate renders or input source pages. Use their
preserved metadata and evidence_context image sequence to determine roles.
Any generic image caption, including an upstream 'Original source figure'
caption, does not establish an image's role as an original input. Judge only
the supplied facts and actual candidate, accepting supported alternatives.
"""


def validate_assessment(req, assessment):
    if not isinstance(assessment, dict):
        raise ValueError("Model assessment is not a JSON object")
    if not isinstance(assessment.get("critical_error"), bool):
        raise ValueError("Model must independently return explicit critical_error boolean")
    if not isinstance(assessment.get("critical_error_reason"), str) or not assessment["critical_error_reason"].strip():
        raise ValueError("Model critical_error judgment has no substantive explanation")
    maxima = {criterion["id"]: criterion["points"] for criterion in req["rubric"]["criteria"]}
    items = assessment.get("criteria")
    if not isinstance(items, list) or len(items) != len(maxima) or not all(isinstance(item, dict) for item in items):
        raise ValueError("Incomplete model rubric")
    ids = [item.get("id") for item in items]
    if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids) or set(ids) != set(maxima):
        raise ValueError("Model criteria must contain every exact rubric ID once")
    candidate_names = list(req["outputs"])
    source_anchors = list(req["inputs"]) + [_document_id(name) for name in req["inputs"]]
    for item in items:
        score = item.get("score")
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(score) or not 0 <= score <= maxima[item["id"]]):
            raise ValueError("Model rubric score outside finite range")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError("Substantive model assessment reason absent")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not all(isinstance(value, str) and value.strip() for value in evidence):
            raise ValueError("Model criterion evidence must be a string list")
        if score > 0:
            text = "\n".join(evidence)
            if not any(name in text for name in candidate_names):
                raise ValueError("Positive score lacks actual candidate filename anchor")
            if not any(re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text)
                       for name in source_anchors):
                raise ValueError("Positive score lacks actual input/source anchor")
    return assessment


def _shared_module():
    spec = importlib.util.spec_from_file_location("finance_shared_host_rubric_bridge", SHARED_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Shared host rubric bridge unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ORIGINAL_GRADE = None
_SHARED = None
_GRADE_LOCK = threading.RLock()


def configure_shared(shared=None):
    """Capture the final upstream grade once; never patch its file or HTTP stack."""
    global _ORIGINAL_GRADE, _SHARED
    if _SHARED is not None:
        return _SHARED
    shared = shared or _shared_module()
    _ORIGINAL_GRADE = shared.grade
    if FINANCE_SYSTEM_MARKER not in shared.SYSTEM:
        shared.SYSTEM += "\n" + FINANCE_SYSTEM_APPEND
    shared.grade = grade
    _SHARED = shared
    return shared


def _dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n")


def _record_actual_transport(raw_path, projected, manifest):
    """Audit Request.data captured at the shared opener, never a guessed body."""
    actual_path = Path(raw_path).parent / "actual-http-body.json"
    manifest["actual_transport_file"] = actual_path.name
    manifest["actual_transport_recorded"] = False
    if not manifest.get("http_request_attempts"):
        manifest["transport_audit_error"] = "This grading invocation did not reach the shared HTTP client"
        return False
    if not actual_path.is_file():
        manifest["transport_audit_error"] = "Shared grade did not hand a Request.data body to its HTTP client"
        return False
    body_bytes = actual_path.read_bytes()
    body = json.loads(body_bytes)
    user_request = {key: value for key, value in projected.items() if key != "source_images"}
    actual_contents = [message.get("content", []) for message in body.get("messages", [])
                       if isinstance(message, dict) and message.get("role") == "user"]
    # JSON whitespace/key order belong to transport formatting. Parse the
    # delegate's actual candidate payload and compare its full canonical content.
    expected_user_digest = digest(user_request)
    matched_request = False
    matched_layout = None
    for content in actual_contents:
        contexts = []
        candidates = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text")
            if not isinstance(text, str):
                continue
            for marker, values in [("Task context:", contexts), ("Review this candidate:", candidates)]:
                if marker not in text:
                    continue
                try:
                    value = json.loads(text.partition(marker)[2])
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict):
                    values.append(value)
        if len(candidates) != 1 or len(contexts) > 1:
            continue
        if contexts:
            if contexts[0].keys() & candidates[0].keys():
                raise ValueError("Delegate split transport repeats static/dynamic keys")
            actual_user_request = {**contexts[0], **candidates[0]}
            layout = "stable-task-context-plus-dynamic-candidate"
        else:
            actual_user_request = candidates[0]
            layout = "legacy-full-candidate-request"
        if digest(actual_user_request) == expected_user_digest:
            matched_request = True
            matched_layout = layout
        if matched_request:
            break
    if not matched_request:
        raise ValueError("Delegate's actual transport does not contain the projected request")
    actual_images = [block.get("source") for content in actual_contents for block in content
                     if isinstance(block, dict) and block.get("type") == "image"]
    expected_images = [{"type": "base64", "media_type": image.get("media_type", "image/png"),
                        "data": image["data"]} for image in projected.get("source_images", [])]
    if actual_images != expected_images:
        raise ValueError("Delegate's actual transport changed supplied images")
    if body.get("stream") is not True or FINANCE_SYSTEM_MARKER not in body.get("system", ""):
        raise ValueError("Delegate transport lacks actual SSE/finance response requirements")
    manifest.update(actual_transport_recorded=True,
                    actual_api_body_sha256=hashlib.sha256(body_bytes).hexdigest(),
                    actual_requested_model=body.get("model"), actual_stream=body["stream"],
                    actual_max_tokens=body.get("max_tokens"),
                    actual_image_count=len(actual_images),
                    actual_request_transport_layout=matched_layout,
                    actual_cache_control_blocks=[{"user_content_sequence":i+1,
                                                  "cache_control":block["cache_control"]}
                                                 for content in actual_contents for i,block in enumerate(content)
                                                 if isinstance(block,dict) and "cache_control" in block])
    upstream_path = Path(raw_path).with_suffix(".transport.json")
    if upstream_path.is_file():
        upstream_sha = hashlib.sha256(upstream_path.read_bytes()).hexdigest()
        manifest.update(upstream_transport_file=upstream_path.name,
                        upstream_transport_sha256=upstream_sha)
        if upstream_sha != manifest["actual_api_body_sha256"]:
            raise ValueError("Upstream transport file differs from actual HTTP-client body")
    return True


def grade(req, base, model, key, raw_path=None, **kwargs):
    """Delegate the authorized API call; credential is only forwarded as an argument."""
    if raw_path is None:
        raise ValueError("Audit log destination is required")
    shared = configure_shared()
    projected, manifest = project_request(req)
    dest = Path(raw_path).parent
    dest.mkdir(parents=True, exist_ok=True)
    # Shared main already saves request.json as the exact original container
    # bytes. This second record preserves the full parsed canonical request.
    (dest / "finance-sealed-request.json").write_bytes(canonical(req) + b"\n")
    (dest / "finance-projected-request.json").write_bytes(canonical(projected) + b"\n")
    manifest.update(requested_model=model,
                    adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    shared_bridge_sha256=hashlib.sha256(SHARED_PATH.read_bytes()).hexdigest(),
                    transport_owner="original shared host_rubric_bridge.grade")
    manifest_path = dest / "finance-page-selection-manifest.json"
    _dump(manifest_path, manifest)
    manifest["http_request_attempts"] = []
    # Only the original shared opener sends the request. This process-local hook
    # reads the body attribute only: no URL, headers, env or credential inspection.
    # The lock also prevents concurrent finance grades from replacing the opener.
    with _GRADE_LOCK:
        original_opener = shared.urllib.request.urlopen

        def audited_opener(request, *args, **opener_kwargs):
            body_bytes = request.data
            if not isinstance(body_bytes, bytes):
                raise ValueError("Shared HTTP client request lacks actual byte body")
            number = len(manifest["http_request_attempts"]) + 1
            body_name = "actual-http-body.json" if number == 1 else f"actual-http-body.attempt-{number}.json"
            (dest / body_name).write_bytes(body_bytes)
            attempt = {
                "attempt": number, "body_file": body_name,
                "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
                "capture_layer": "Request.data handed to the original shared urllib opener",
                "captured_before_http_client_call": True,
                "http_client_response_opened": False,
                "response_completion_claimed": False,
            }
            manifest["http_request_attempts"].append(attempt)
            _dump(manifest_path, manifest)
            try:
                response = original_opener(request, *args, **opener_kwargs)
            except Exception as error:
                attempt["http_client_error_type"] = type(error).__name__
                if isinstance(error, shared.urllib.error.HTTPError):
                    attempt["http_status"] = error.code
                    error_text = error.read().decode('utf-8', errors='replace')
                    error_text = re.sub(r'(?i)\bsk-[A-Za-z0-9_-]{8,}', '[redacted credential]', error_text)
                    error_text = re.sub(r'(?i)(api[_-]?key|x-api-key|authorization)(\s*[:=]\s*)[^\s<,}]+', r'\1\2[redacted credential]', error_text)
                    (dest/'http-error-response.txt').write_text(error_text)
                    attempt["sanitized_http_error_body_file"] = 'http-error-response.txt'
                    attempt["sanitized_http_error_body_sha256"] = hashlib.sha256(error_text.encode()).hexdigest()
                _dump(manifest_path, manifest)
                raise
            attempt["http_client_response_opened"] = True
            _dump(manifest_path, manifest)
            return response

        shared.urllib.request.urlopen = audited_opener
        try:
            assessment, raw = _ORIGINAL_GRADE(
                projected, base, model, key, raw_path=raw_path, **kwargs)
        finally:
            shared.urllib.request.urlopen = original_opener
            transport_recorded = _record_actual_transport(raw_path, projected, manifest)
            _dump(manifest_path, manifest)
    if not transport_recorded:
        raise RuntimeError("Actual shared transport body is absent; assessment cannot be injected")
    if manifest["actual_requested_model"] != model:
        raise ValueError("Actual shared transport model differs from configured model")
    if not isinstance(raw, dict) or raw.get("stop_reason") != "end_turn":
        raise ValueError("Actual delegated model response did not complete an assessment")
    if raw.get("stream_complete") is not True:
        raise ValueError("Actual delegated SSE response is incomplete")
    manifest["delegated_response_stream_complete"] = True
    manifest["http_request_attempts"][-1]["response_completion_claimed"] = True
    _dump(manifest_path, manifest)
    if not all(isinstance(raw.get(field), str) and raw[field].strip() for field in ("model", "id")):
        raise ValueError("Actual model response identity is unavailable")
    usage = raw.get("usage")
    _dump(dest / "finance-model-usage.json", usage)
    if not isinstance(usage, dict) or not usage:
        raise ValueError("Actual model usage is unavailable")
    for field in ("input_tokens", "output_tokens"):
        if isinstance(usage.get(field), bool) or not isinstance(usage.get(field), int) or usage[field] < 0:
            raise ValueError("Actual model token usage is incomplete")
    validate_assessment(req, assessment)
    if assessment.get("request_sha256") != req["request_sha256"]:
        raise ValueError("Delegated assessment lost original sealed request binding")
    # Identity and binding come only from the actual request and API response.
    assessment.update(judge_kind="independent-model-rubric",
                      judge_identity={**assessment.get("judge_identity", {}),
                                      "model": raw["model"], "requested_model": model,
                                      "protocol": "anthropic-messages", "response_id": raw["id"],
                                      "usage": usage})
    manifest.update(assessment_validated=True,
                    assessment_bound_to_original_request_sha256=req["request_sha256"])
    _dump(manifest_path, manifest)
    return assessment, raw


def main():
    shared = configure_shared()
    shared.main()


if __name__ == "__main__":
    main()
