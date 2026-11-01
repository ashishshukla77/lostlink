import copy
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
LOCAL_PACKAGES = PROJECT_DIR / ".packages"
if LOCAL_PACKAGES.is_dir():
    sys.path.insert(0, str(LOCAL_PACKAGES))

from matching import find_matches
from sample_data import SAMPLE_REPORTS
from sarvam_client import analyze_candidates, load_api_key

st.set_page_config(page_title="LOSTLINK | Campus Lost & Found", page_icon="🔎", layout="wide")
st.markdown("""
<style>
:root { --ink:#12233f; --blue:#2563eb; --pale:#eff6ff; }
.block-container { padding-top: 1.6rem; max-width: 1180px; }
[data-testid="stMetric"] { background:#f4f8ff; border:1px solid #dbeafe; padding:16px 18px; border-radius:16px; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
section[data-testid="stSidebar"] { background:#f7faff; }
.lostlink-subtitle { color:#5b6b82; margin-top:-.5rem; }
.small-note { color:#66758b; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

CATEGORIES = ["Electronics", "ID & cards", "Bags", "Wallets", "Keys", "Bottles", "Books & stationery", "Clothing & accessories", "Other"]
PAGES = ["Dashboard", "Report an item", "Smart matching", "My reports"]


def _go_to(page):
    st.session_state["page"] = page


def _go_to_report(kind):
    st.session_state["report_kind"] = kind
    st.session_state["page"] = "Report an item"


def _submit_report():
    state = st.session_state
    name = str(state.get("report_name", "")).strip()
    description = str(state.get("report_description", "")).strip()
    location = str(state.get("report_location", "")).strip()
    if not name or not description or not location:
        state["report_error"] = "Please fill in the item name, public description, and campus location."
        return

    report_id = "user-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    uploaded = state.get("report_image")
    report = {
        "id": report_id,
        "kind": state.get("form_report_kind", "Lost"),
        "name": name,
        "description": description,
        "category": state.get("report_category", "Other"),
        "color": str(state.get("report_color", "")).strip(),
        "location": location,
        "reported_at": datetime.combine(state["report_date"], state["report_time"]).isoformat(timespec="minutes"),
        "private_detail": str(state.get("report_private_detail", "")).strip(),
        "created_by": "user",
        "image": uploaded.getvalue() if uploaded else None,
    }
    state["reports"].append(report)
    state["my_report_ids"].append(report_id)
    state["latest_submitted_report_id"] = report_id
    state["ai_analyses"] = {}
    state["report_error"] = ""

    state["pending_match_report_id"] = report_id
    state["latest_report_status"] = "Report saved. Checking for possible matches…"
    state["page"] = "Smart matching"


def _init_state():
    if "reports" not in st.session_state:
        st.session_state["reports"] = copy.deepcopy(SAMPLE_REPORTS)
    st.session_state.setdefault("my_report_ids", [])
    st.session_state.setdefault("report_kind", "Lost")
    st.session_state.setdefault("contact_requests", [])
    st.session_state.setdefault("ai_analyses", {})
    st.session_state.setdefault("latest_submitted_report_id", None)
    st.session_state.setdefault("latest_report_status", "")
    st.session_state.setdefault("report_error", "")
    st.session_state.setdefault("pending_match_report_id", None)


def _public_report(report):
    fields = ["kind", "name", "description", "category", "color", "location", "reported_at"]
    return {key: report.get(key, "") for key in fields}


def _when(value):
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %I:%M %p")
    except (TypeError, ValueError):
        return "Time not provided"


def _report_card(report, show_status=False):
    badge = "🟥 LOST" if report.get("kind") == "Lost" else "🟩 FOUND"
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"**{badge} · {report.get('name', 'Untitled item')}**")
            st.write(report.get("description", ""))
            details = " · ".join(part for part in [report.get("category", ""), report.get("color", ""), report.get("location", "")] if part)
            st.caption(f"{details} · {_when(report.get('reported_at'))}")
            if show_status:
                st.caption("Open report" if report.get("created_by") == "user" else "Demo report")
        with right:
            if report.get("image"):
                st.image(report["image"], use_container_width=True)


def _candidate_matches():
    return find_matches(st.session_state["reports"])


_init_state()
with st.sidebar:
    st.markdown("# 🔎 LOSTLINK")
    st.caption("Lost something? Let AI find it.")
    st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    st.caption("Private identifying details stay out of public match analysis.")

page = st.session_state["page"]
reports = st.session_state["reports"]
lost_count = sum(1 for report in reports if report.get("kind") == "Lost")
found_count = sum(1 for report in reports if report.get("kind") == "Found")
all_matches = _candidate_matches()
potential_count = sum(1 for match in all_matches if match["score"] >= 45)

st.title("LOSTLINK")
st.markdown('<p class="lostlink-subtitle">Lost something? Let AI find it.</p>', unsafe_allow_html=True)

if page == "Smart matching" and st.session_state["pending_match_report_id"]:
    report_id = st.session_state["pending_match_report_id"]
    st.session_state["pending_match_report_id"] = None
    candidates = find_matches(reports, minimum_score=0)
    related = [pair for pair in candidates if report_id in pair["pair_id"].split("|")]
    if not related:
        st.session_state["latest_report_status"] = "Report saved. There is no Lost/Found report of the opposite type to compare yet."
    elif load_api_key():
        with st.spinner("Checking this report against existing reports…"):
            analyses, error = analyze_candidates(candidates)
        if error:
            st.session_state["latest_report_status"] = f"Report saved. {error} Showing deterministic matches."
        else:
            st.session_state["ai_analyses"] = analyses
            st.session_state["latest_report_status"] = f"Report saved. Sarvam checked {len(related)} related Lost/Found pair(s); review the suggestions below."
    else:
        st.session_state["latest_report_status"] = "Report saved. Sarvam is not configured, so deterministic matching is shown below."

if page == "Dashboard":
    m1, m2, m3 = st.columns(3)
    m1.metric("Lost reports", lost_count)
    m2.metric("Found reports", found_count)
    m3.metric("Potential matches", potential_count)
    st.subheader("Start here")
    a, b = st.columns(2)
    a.button("＋ Report a lost item", use_container_width=True, on_click=_go_to_report, args=("Lost",))
    b.button("＋ Report a found item", use_container_width=True, on_click=_go_to_report, args=("Found",))
    if all_matches:
        best = all_matches[0]
        st.subheader("Top possible match")
        st.info(f"{best['lost']['name']} ↔ {best['found']['name']} · {best['score']}% signal score. This is only a lead; ownership must be verified.")
    st.subheader("Recently submitted")
    recent = sorted(reports, key=lambda item: item.get("reported_at", ""), reverse=True)[:5]
    for report in recent:
        _report_card(report)
    with st.expander("How LOSTLINK protects claimants"):
        st.write("Public match analysis uses report descriptions and basic attributes. Private identifying details are kept out of public cards and are not sent to Sarvam. A suggested match is never proof of ownership.")

elif page == "Report an item":
    st.subheader("Report an item")
    st.write("Share enough public detail to help find a match. Keep serial numbers and unique identifying details in the private field.")
    with st.form("report_form", clear_on_submit=True):
        st.radio("Report type", ["Lost", "Found"], horizontal=True, key="form_report_kind")
        st.text_input("Item name *", placeholder="e.g. wireless earbuds", key="report_name")
        st.text_area("Public description *", placeholder="Describe the item without sharing secret identifiers", key="report_description")
        c1, c2 = st.columns(2)
        c1.selectbox("Category *", CATEGORIES, key="report_category")
        c2.text_input("Colour", placeholder="e.g. black", key="report_color")
        c3, c4 = st.columns(2)
        c3.text_input("Campus location *", placeholder="e.g. central library", key="report_location")
        c4.date_input("Approximate date", key="report_date")
        st.time_input("Approximate time", key="report_time")
        st.text_area("Private identifying detail (never shown publicly)", placeholder="A mark or detail only the owner/finder should know", key="report_private_detail")
        st.file_uploader("Optional photo", type=["png", "jpg", "jpeg", "webp"], key="report_image")
        st.form_submit_button("Submit report", type="primary", use_container_width=True, on_click=_submit_report)
    if st.session_state["report_error"]:
        st.error(st.session_state["report_error"])

elif page == "Smart matching":
    st.subheader("Smart matching")
    st.write("Sarvam compares every Lost report with every Found report to find semantic matches. Deterministic attribute scoring remains available as a fallback.")
    st.caption("Scores are leads, not confirmation. No private verification detail is sent to the AI or shown on public cards.")
    if st.session_state["latest_report_status"]:
        st.info(st.session_state["latest_report_status"])
    if st.button("Find matches with Sarvam", type="primary", disabled=not any(r.get("kind") == "Lost" for r in reports) or not any(r.get("kind") == "Found" for r in reports)):
        if not load_api_key():
            st.info("Sarvam key is not configured. Add SARVAM_API_KEY=your_new_key to the project .env file, then click again. Deterministic matches are still shown below.")
        else:
            # Include low-scoring pairs too: Sarvam may recognize equivalent
            # descriptions even when the deterministic lexical score is low.
            candidates = find_matches(reports, minimum_score=0)
            analyses, error = analyze_candidates(candidates)
            if error:
                st.warning(f"{error} Showing deterministic fallback matches.")
            else:
                st.session_state["ai_analyses"] = analyses
                st.success(f"Sarvam checked {len(candidates)} Lost/Found pairs and updated the match suggestions.")
    if not all_matches:
        if not st.session_state["ai_analyses"]:
            st.info("There are no lost/found pairs to compare yet.")
    # Add AI-discovered pairs that fell below the deterministic matcher cutoff.
    known_pair_ids = {match["pair_id"] for match in all_matches}
    ai_only_matches = []
    ai_only_pair_ids = set()
    if st.session_state["ai_analyses"]:
        from matching import score_pair
        reports_by_id = {report["id"]: report for report in reports}
        for pair_id, analysis in st.session_state["ai_analyses"].items():
            if pair_id in known_pair_ids or analysis.get("match_likelihood", 0) < 45:
                continue
            lost_id, found_id = pair_id.split("|", 1)
            lost, found = reports_by_id.get(lost_id), reports_by_id.get(found_id)
            if lost and found:
                ai_only_matches.append({"pair_id": pair_id, "lost": lost, "found": found, **score_pair(lost, found)})
                ai_only_pair_ids.add(pair_id)
    display_matches = all_matches + ai_only_matches
    display_matches.sort(key=lambda match: max(match["score"], st.session_state["ai_analyses"].get(match["pair_id"], {}).get("match_likelihood", 0)), reverse=True)
    latest_report_id = st.session_state["latest_submitted_report_id"]
    if latest_report_id and st.session_state["latest_report_status"]:
        related_display = [match for match in display_matches if latest_report_id in match["pair_id"].split("|")]
        if related_display:
            st.success(f"Found {len(related_display)} possible match(es) for your latest report. Review them below; none is verified.")
        elif any(latest_report_id in pair["pair_id"].split("|") for pair in find_matches(reports, minimum_score=0)):
            st.info("No likely match found for this report yet. It is saved for this session; another report may match it later.")
    if st.session_state["ai_analyses"] and not ai_only_matches and not all_matches:
        st.info("Sarvam did not find any likely pairs. Submit more details or reports to compare.")
    for index, match in enumerate(display_matches[:12]):
        lost, found = match["lost"], match["found"]
        analysis = st.session_state["ai_analyses"].get(match["pair_id"])
        score = match["score"]
        if analysis:
            if match["pair_id"] in ai_only_pair_ids:
                score = analysis["match_likelihood"]
            else:
                score = round(0.7 * score + 0.3 * analysis["match_likelihood"])
        if match["conflicts"]:
            score = min(score, 39)
        label = "Possible match" if score >= 55 else "Needs review"
        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                st.markdown(f"### {lost['name']} ↔ {found['name']}")
                source = "Sarvam match" if match["pair_id"] in ai_only_pair_ids else ("Sarvam + attribute score" if analysis else "Attribute score")
                st.caption(f"{label} · {score}% · {source} · Not verified")
                st.write(f"**Lost:** {lost['description']}")
                st.write(f"**Found:** {found['description']}")
                sig = match["signals"]
                st.caption(f"Signals — description {sig['description']} · category {sig['category']} · colour {sig['colour']} · location {sig['location']} · time {sig['time']}")
                if match["conflicts"]:
                    st.warning(" ".join(match["conflicts"]))
                if analysis:
                    st.write(analysis["explanation"])
                    if analysis["supporting_details"]:
                        st.caption("Supports: " + "; ".join(analysis["supporting_details"]))
                    if analysis["uncertain_details"]:
                        st.caption("Uncertain: " + "; ".join(analysis["uncertain_details"]))
                else:
                    st.write("This pair shares some attributes. Compare the reported item, colour, location, and time before taking action.")
                prompts = analysis["verification_prompts"] if analysis else ["Ask the claimant to describe a distinctive detail not shown in the public report.", "Verify the detail privately with the finder; do not post it in chat."]
                st.markdown("**Safe verification checklist**")
                for prompt in prompts[:3]:
                    st.markdown(f"- {prompt}")
                request_key = "request-" + match["pair_id"]
                if st.button("Simulate contact request", key=request_key):
                    st.session_state["contact_requests"].append({"pair_id": match["pair_id"], "created_at": datetime.now().isoformat(timespec="minutes")})
                    st.success("Demo request recorded in this session. No message was sent.")
            with right:
                st.metric("Signal score", f"{score}%")
                st.progress(min(score, 100) / 100)

elif page == "My reports":
    st.subheader("My reports")
    mine = [report for report in reports if report.get("id") in st.session_state["my_report_ids"]]
    if not mine:
        st.info("You have no reports in this session yet. Sample reports are shown on the dashboard and in Smart matching.")
    if mine:
        summary = pd.DataFrame([{
            "Type": report["kind"], "Item": report["name"], "Category": report["category"],
            "Location": report["location"], "Reported": _when(report["reported_at"]),
        } for report in mine])
        st.dataframe(summary, hide_index=True, use_container_width=True)
    for report in mine:
        _report_card(report, show_status=True)
        associated = [m for m in all_matches if report["id"] in (m["lost"]["id"], m["found"]["id"])]
        if associated:
            st.caption(f"{len(associated)} possible match lead(s) to review.")
        if st.button("Remove my report", key="remove-" + report["id"]):
            st.session_state["reports"] = [item for item in reports if item["id"] != report["id"]]
            st.session_state["my_report_ids"].remove(report["id"])
            st.session_state["ai_analyses"] = {}
            st.rerun()
    if st.session_state["contact_requests"]:
        st.markdown("**Simulated contact requests**")
        st.caption(f"{len(st.session_state['contact_requests'])} request(s) recorded in this session. No notification was sent.")

st.divider()
st.caption("LOSTLINK demo · Session-only storage · Potential matches require human verification")


