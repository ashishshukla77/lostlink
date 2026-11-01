import re
from datetime import datetime
from difflib import SequenceMatcher

CONCEPT_GROUPS = {
    "audio": {"earbud", "earbuds", "earphone", "earphones", "headphone", "headphones"},
    "student_id": {"id", "badge", "identity", "card", "access"},
    "charger": {"charger", "adapter", "power", "supply"},
    "bottle": {"bottle", "flask", "thermos"},
    "wallet": {"wallet", "purse"},
    "keys": {"key", "keys", "keyring"},
    "notebook": {"notebook", "journal", "notepad"},
}
FAMILY_GROUPS = {
    "audio": CONCEPT_GROUPS["audio"],
    "student ID": CONCEPT_GROUPS["student_id"],
    "charger": CONCEPT_GROUPS["charger"],
    "bottle": CONCEPT_GROUPS["bottle"],
    "wallet": CONCEPT_GROUPS["wallet"],
    "keys": CONCEPT_GROUPS["keys"],
    "notebook": CONCEPT_GROUPS["notebook"],
    "umbrella": {"umbrella"},
    "calculator": {"calculator"},
}


def _item_family(report):
    words = set(re.findall(r"[a-z0-9]+", " ".join([report.get("name", ""), report.get("description", "")]).lower()))
    for family, aliases in FAMILY_GROUPS.items():
        if words & aliases:
            return family
    return None


def _tokens(value):
    words = set(re.findall(r"[a-z0-9]+", str(value or "").lower()))
    for concept, aliases in CONCEPT_GROUPS.items():
        if words & aliases:
            words.add("concept_" + concept)
    return words


def _text_similarity(left, right):
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.45
    jaccard = len(a & b) / len(a | b)
    sequence = SequenceMatcher(None, str(left or "").lower(), str(right or "").lower()).ratio()
    return min(1.0, 0.75 * jaccard + 0.25 * sequence)


def _category_score(left, right):
    a, b = str(left or "").strip().lower(), str(right or "").strip().lower()
    if not a or not b:
        return 0.5
    return 1.0 if a == b else (0.35 if _tokens(a) & _tokens(b) else 0.0)


def _color_score(left, right):
    a, b = str(left or "").strip().lower(), str(right or "").strip().lower()
    if not a or not b:
        return 0.5, False
    if a == b or a in b or b in a:
        return 1.0, False
    return 0.0, True


def _time_score(left, right):
    try:
        a, b = datetime.fromisoformat(left), datetime.fromisoformat(right)
        hours = abs((a - b).total_seconds()) / 3600
    except (TypeError, ValueError):
        return 0.5
    if hours <= 24:
        return 1.0
    if hours <= 72:
        return 0.8
    if hours <= 168:
        return 0.6
    return 0.2


def score_pair(lost, found):
    text = _text_similarity(
        " ".join([lost.get("name", ""), lost.get("description", "")]),
        " ".join([found.get("name", ""), found.get("description", "")]),
    )
    category = _category_score(lost.get("category"), found.get("category"))
    color, color_conflict = _color_score(lost.get("color"), found.get("color"))
    location = _text_similarity(lost.get("location", ""), found.get("location", ""))
    time = _time_score(lost.get("reported_at"), found.get("reported_at"))
    category_conflict = bool(lost.get("category") and found.get("category") and category == 0.0)
    left_family, right_family = _item_family(lost), _item_family(found)
    item_type_conflict = bool(left_family and right_family and left_family != right_family)
    raw = 0.30 * text + 0.20 * category + 0.18 * color + 0.17 * location + 0.15 * time
    if color_conflict or category_conflict or item_type_conflict:
        raw *= 0.35
    score = round(raw * 100)
    signals = {
        "description": round(text * 100),
        "category": round(category * 100),
        "colour": round(color * 100),
        "location": round(location * 100),
        "time": round(time * 100),
    }
    conflicts = []
    if color_conflict:
        conflicts.append("The reported colours differ.")
    if category_conflict:
        conflicts.append("The reported categories differ.")
    if item_type_conflict:
        conflicts.append("The reported item types differ.")
    return {"score": score, "signals": signals, "conflicts": conflicts}


def find_matches(reports, minimum_score=22):
    lost_reports = [r for r in reports if r.get("kind") == "Lost"]
    found_reports = [r for r in reports if r.get("kind") == "Found"]
    matches = []
    for lost in lost_reports:
        for found in found_reports:
            scored = score_pair(lost, found)
            if scored["score"] < minimum_score:
                continue
            matches.append({
                "pair_id": lost["id"] + "|" + found["id"],
                "lost": lost,
                "found": found,
                **scored,
            })
    return sorted(matches, key=lambda item: item["score"], reverse=True)



