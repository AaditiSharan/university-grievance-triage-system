# Synthetic grievance dataset

All records are SYNTHETIC. No real student data. Contact numbers are random digits.
The category tree in `config/category_tree.json` is a PLACEHOLDER: replace it with the real RMS dropdown values.

## Files
| File | Contents |
|---|---|
| data/synthetic/grievances_full.csv | every record (all splits) |
| data/synthetic/incidents.csv | known-issue records for the 10 clusters |
| data/processed/train.csv, val.csv | training and validation splits |
| data/test_set/test.csv | held-out test split. Never train or tune on it |

## Key columns
| Column | Meaning |
|---|---|
| message_type | Grievance / Assistance / Enquiry / Feedback / Positive Feedback |
| selected_* | what the student chose in the dropdowns (wrong about 47% of the time) |
| true_master / true_category / true_subcategory | ground-truth label (UNCLEAR for incomplete messages) |
| secondary_subcategory | second issue in multi-issue messages |
| record_type | valid, sensitive, edge_harmless_trigger, incomplete, multi_issue, multi_issue_sensitive, cluster, hard_negative |
| sensitive_label, sensitivity_type | 1/0 and SAFETY / WELFARE / MEDICAL / NONE |
| trigger_keyword | risky word in a harmless record (for example "killing", "hospital") |
| urgent_deadline, priority_label | P1 sensitive, P2 deadline-urgent, P3 normal, P4 enquiry/feedback |
| expected_route | correct department |
| needs_human_review | 1 for sensitive, incomplete and multi-issue records |
| expected_action | ROUTE_NORMAL, ESCALATE_SENSITIVE, REQUEST_MORE_INFO, MANUAL_FIRST_RESPONSE, AUTO_REPLY_KNOWN_ISSUE, LOG_FEEDBACK |
| cluster_id, cluster_position | incident group and arrival order (positions 1-2 answered manually, then auto-reply) |
| hard_negative_of | same category but a different section/event/course, so it must NOT get that incident's reply |
| template_id, variant_heldout | which template produced the text; held-out templates appear only in test |

## Known limitations
* Text comes from templates (8 per subcategory), so scores will be higher than on real RMS data.
* Real messages are messier. Add your own hand-written or paraphrased records, especially to the test set.
* Sensitive keywords are kept non-graphic. Real welfare messages are more varied.
