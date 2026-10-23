"""
validate_dataset.py
-------------------
Sanity checks for the synthetic dataset. Run from the project root:
    python scripts/validate_dataset.py
Exits with code 1 if a hard check fails.
"""

"""
The `validate_dataset.py` script is a data quality validation utility for the University Grievance Triage System. 
It uses Pandas to load the synthetic grievance dataset and its train, validation, and test splits, along with the incident records and category hierarchy.

1. Checks missing information: Makes sure important details, such as complaint descriptions and IDs, are not empty.
2. Checks duplicate IDs: Ensures two complaints don't accidentally have the same ID.
3. Checks the data splits: Verifies that the training, validation, and testing datasets have the expected total number
 of records and checks for certain types of overlap.
4.Checks complaint categories: Ensures every complaint's category exists in the predefined category list.
5.Checks sensitive complaints: Makes sure complaints marked as sensitive have P1 priority and require human review.
6.Checks duplicate complaints: Finds identical complaint descriptions outside groups where repetition is expected.
7.Checks incident records: Ensures that complaint groups match the incident records.
8.Prints statistics: Shows information such as the number of complaints in each category, the languages used, and how many contact numbers are missing.

What happens at the end?
- PASS: The check is successful.
- FAIL: The script finds a problem and records it.
- If any hard check fails, the script exits with error code 1.

For example, a fictional harmless complaint might say:
"The hostel security guard threatened to charge a fine if I did not return the library book."

Depending on the wording, a poorly designed detector might incorrectly identify the message as a serious threat.

The dataset uses the record type "edge_harmless_trigger" to identify specially designed examples that test this behavior. 
The check verifies that all those records have sensitive_label = 0.

This helps test whether the system can distinguish genuinely sensitive complaints from harmless text containing misleading trigger words.

validate_dataset.py checks whether the data used in your University Grievance Triage System is correct and ready for the AI model.

"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
full = pd.read_csv(ROOT / "data/synthetic/grievances_full.csv")
train = pd.read_csv(ROOT / "data/processed/train.csv")
val = pd.read_csv(ROOT / "data/processed/val.csv")
test = pd.read_csv(ROOT / "data/test_set/test.csv")
inc = pd.read_csv(ROOT / "data/synthetic/incidents.csv")
tree = json.loads((ROOT / "config/category_tree.json").read_text(encoding="utf-8"))["tree"]

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        failures.append(name)


# --- hard checks -----------------------------------------------------------------
req = ["request_id", "description", "message_type", "true_master", "true_subcategory",
       "sensitive_label", "priority_label", "expected_route", "split"]
check("no nulls in required columns", full[req].notna().all().all())
check("request_id unique", full.request_id.is_unique)
check("splits partition the data", len(train) + len(val) + len(test) == len(full))
check("no request in two splits", not (set(train.request_id) & set(test.request_id))
      and not (set(val.request_id) & set(test.request_id)))

valid_subs = {s for cats in tree.values() for subs in cats.values() for s in subs} | {"UNCLEAR"}
check("all true labels exist in category tree", set(full.true_subcategory) <= valid_subs)
check("sensitive records are all P1", (full[full.sensitive_label == 1].priority_label == "P1").all())
check("sensitive records require human review", (full[full.sensitive_label == 1].needs_human_review == 1).all())
check("harmless trigger records are NOT sensitive",
      (full[full.record_type == "edge_harmless_trigger"].sensitive_label == 0).all())
import re


def components(tid):
    return tid.split("+")


def is_heldout_component(c):
    m = re.match(r"HARMLESS-(\d+)$", c)
    if m:
        return int(m.group(1)) % 3 == 2
    m = re.match(r"T\d+-v(\d)$", c)
    return bool(m) and int(m.group(1)) % 4 == 3


train_components = {c for t in train.template_id for c in components(t)}
held = {c for t in test.template_id for c in components(t) if is_heldout_component(c)}
check("held-out templates never appear in train", not (held & train_components), f"({len(held)} held-out templates)")
check("every cluster has an incident", set(full[full.cluster_id != "NONE"].cluster_id) == set(inc.cluster_id))

# non-cluster exact duplicate descriptions (clusters may legitimately repeat)
nc = full[full.cluster_id == "NONE"]
dups = nc.description.duplicated().sum()
check("no exact-duplicate descriptions outside clusters", dups == 0, f"({dups} found)")

# --- soft reports ----------------------------------------------------------------
print("\n--- class balance (true_subcategory), smallest 8 ---")
print(full.true_subcategory.value_counts().tail(8).to_string())
print("\n--- sensitive vs normal per split ---")
print(pd.crosstab(full.split, full.sensitive_label).to_string())
print("\n--- language mix ---")
print(full.language.value_counts().to_string())
print("\n--- priority mix ---")
print(full.priority_label.value_counts().to_string())
print("\n--- expected_action mix ---")
print(full.expected_action.value_counts().to_string())
print("\n--- clusters in test split ---")
print(test[test.cluster_id != "NONE"].cluster_id.value_counts().to_string())
print(f"\nMissing contact numbers: {full.contact_no.isna().mean():.1%}")
print(f"Wrong dropdown selection: {1 - full[full.true_master != 'UNCLEAR'].selected_is_correct.mean():.1%}")

if failures:
    print("\nFAILED:", failures)
    sys.exit(1)
print("\nAll hard checks passed.")
