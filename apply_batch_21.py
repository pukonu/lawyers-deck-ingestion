#!/usr/bin/env python3
"""Apply manual batch 21 enrichment + storyline to EWCA Civ 2025 judgments."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "judgments" / "ewca" / "civ" / "2025"
BATCH_PATH = ROOT / "storyline_batches" / "ewca_civ_2025_batch_21.json"
BATCH_DATE = "2026-07-06"
BATCH_NUMBER = 21
BATCH_NOTES = (
    "EWCA Civ 2025 batch 21 — manual enrichment and storyline for judgments "
    "749, 755, 760, 763, 775, 776, 782, 783, 784, 788."
)

ENRICHMENT_FIELDS = [
    "area_of_law",
    "statutes_considered",
    "key_facts",
    "short_title",
    "procedural_posture",
    "outcome",
    "ratio",
    "legal_issues",
    "catchwords",
    "index_terms",
    "linked_authorities",
    "confidence",
    "storyline",
]

ENRICHMENTS = {
    "749.json": {
        "judges": ["Lord Justice Arnold", "Lord Justice Males"],
        "area_of_law": ["Intellectual property", "Trade marks", "Civil procedure"],
        "statutes_considered": [
            {"title": "Trade Marks Act 1994", "provisions": ["section 10(3)"]},
            {"title": "Civil Procedure Rules", "provisions": ["Part 18"]},
        ],
        "key_facts": [
            "Getty sued Stability AI alleging tarnishment where Stable Diffusion outputs carried Getty-branded signs on objectionable synthetic images.",
            "Paragraph 57.9 of Getty's pleading referred generally to pornography, violent imagery and propaganda, but after a case management conference Getty amended to identify specific adult NSFW image examples.",
            "On the eve of trial Getty's skeleton argument introduced a contention that the LAION datasets and Stable Diffusion outputs also involved child sexual abuse material.",
            "Joanna Smith J ruled on the first day of trial that the CSAM allegations were not pleaded and Getty appealed urgently.",
        ],
        "short_title": "Getty could not widen pleaded tarnishment case to CSAM",
        "procedural_posture": "Urgent appeal during trial from an extempore ruling that Getty's CSAM allegations in its skeleton fell outside the pleaded trade mark tarnishment case.",
        "outcome": "Appeal dismissed; although 'pornography' is linguistically broad enough to include illegal material, Getty's amended and particularised pleading had objectively narrowed the case to non-CSAM examples.",
        "ratio": "Where a broad pleading is later particularised by identified examples after case management intervention, the objective meaning of the amended case may be narrowed by those particulars, so a party cannot expand the case at trial through skeleton argument alone.",
        "legal_issues": [
            "Whether a pleading referring to pornography and violent imagery naturally includes CSAM",
            "Effect of case management directions requiring identified examples",
            "Whether serious or criminally tainted allegations needed further express pleading",
            "How to read pleadings objectively after amendment and reply",
        ],
        "catchwords": ["trade mark tarnishment", "pleadings", "particularisation", "case management", "CSAM", "skeleton argument"],
        "index_terms": ["Getty Images", "Stability AI", "Stable Diffusion", "Joanna Smith J", "paragraph 57.9"],
        "linked_authorities": ["L'Oréal SA v Bellure NV"],
        "confidence": {
            "score": 0.94,
            "level": "high",
            "notes": ["Reasoning and disposition are explicit in both Arnold LJ and Males LJ judgments."],
        },
        "storyline": {
            "title": "Getty's attempt to expand its tarnishment pleading failed",
            "summary": "Getty's trade mark claim against Stability AI was particularised before trial by adult NSFW examples. When Getty then tried to rely on CSAM allegations in its trial skeleton, the Court of Appeal held that the pleaded case had already been narrowed and dismissed the urgent appeal.",
            "span": {"start": "2022-08", "end": "2025-06", "label": "August 2022 – June 2025"},
            "parties": [
                {"role": "appellant", "name": "Getty Images (US) Inc and others", "short_name": "Getty"},
                {"role": "respondent", "name": "Stability AI Ltd", "short_name": "Stability"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "model-launch", "order": 1, "date": "2022-08", "date_label": "Around August 2022", "date_precision": "approximate", "title": "Stable Diffusion launched", "category": "background", "actor": "Stability", "what_happened": "Stability launched its text-to-image model trained on internet-scraped images, including images Getty says were taken from its sites.", "why_it_matters": "This created the factual basis for Getty's claims.", "legal_hook": None},
                {"id": "tarnishment-pleaded", "order": 2, "date": "2024-07-12", "date_label": "2024-07-12", "date_precision": "exact", "title": "Getty pleads general tarnishment case", "category": "pleading", "actor": "Getty", "what_happened": "Getty pleaded that Stable Diffusion could create pornography, violent imagery and propaganda that would tarnish Getty's marks.", "why_it_matters": "This was the originating pleading language later argued to be broad enough to include CSAM.", "legal_hook": "Trade Marks Act 1994 section 10(3)"},
                {"id": "cmc-warning", "order": 3, "date": "2025-04-30", "date_label": "2025-04-30", "date_precision": "exact", "title": "CMC requires concrete examples", "category": "case_management", "actor": "Joanna Smith J", "what_happened": "At a case management conference, the judge indicated Getty should identify the specific examples on which it relied.", "why_it_matters": "This step set up the later conclusion that the amended pleading narrowed the case.", "legal_hook": None},
                {"id": "amendment-made", "order": 4, "date": "2025-05-06", "date_label": "2025-05-06", "date_precision": "exact", "title": "Getty amends to identified examples", "category": "pleading", "actor": "Getty", "what_happened": "Getty amended paragraph 57.9 to refer to specific images in Annex 8H and exhibit DAS-15 rather than adding any CSAM example.", "why_it_matters": "Those examples were adult NSFW celebrity images, not illegal material.", "legal_hook": None},
                {"id": "reply-clarification", "order": 5, "date": "2025-05-23", "date_label": "2025-05-23", "date_precision": "exact", "title": "Reply describes NSFW images", "category": "pleading", "actor": "Getty", "what_happened": "Getty's reply clarified that the identified images were not safe for work because of nudity and poses.", "why_it_matters": "The reply reinforced the narrower reading of the pleaded case.", "legal_hook": None},
                {"id": "skeleton-escalation", "order": 6, "date": "2025-05-30", "date_label": "2025-05-30 to 2025-06-06", "date_precision": "approximate", "title": "Trial skeleton raises CSAM", "category": "hearing", "actor": "Getty", "what_happened": "Getty's skeleton argument asserted that LAION datasets and Stable Diffusion outputs included CSAM content and that this aggravated tarnishment concerns.", "why_it_matters": "This introduced a materially more serious allegation immediately before trial.", "legal_hook": None},
                {"id": "trial-ruling", "order": 7, "date": "2025-06-09", "date_label": "2025-06-09", "date_precision": "exact", "title": "Trial judge excludes CSAM case", "category": "decision", "actor": "Joanna Smith J", "what_happened": "On the first day of trial the judge ruled that the CSAM allegations were not part of the pleaded case and could not be deployed.", "why_it_matters": "That ruling generated an urgent interlocutory appeal during trial.", "legal_hook": "Pleading scope"},
                {"id": "appeal-dismissed", "order": 8, "date": "2025-06", "date_label": "June 2025", "date_precision": "approximate", "title": "Court of Appeal dismisses appeal", "category": "outcome", "actor": "Court of Appeal", "what_happened": "Arnold LJ and Males LJ held that the particularised pleading no longer extended to CSAM and dismissed Getty's appeal.", "why_it_matters": "The trial proceeded without the expanded allegation.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "cmc-warning", "label": "Examples were demanded", "impact": "The case moved from a general plea to a pleaded set of specific illustrations."},
                {"stage_id": "amendment-made", "label": "Adult examples became defining particulars", "impact": "The objective scope of the claim narrowed away from illegal-content allegations."},
                {"stage_id": "trial-ruling", "label": "Skeleton argument could not expand case", "impact": "Getty lost the ability to rely on CSAM at trial."},
            ],
            "confidence": {"score": 0.93, "level": "high", "notes": ["Chronology is explicit in the judgment."]},
        },
    },
    "755.json": {
        "judges": ["Lady Justice Asplin", "Lady Justice Falk", "Lord Justice Underhill"],
        "area_of_law": ["Insurance", "Commercial procedure", "Disclosure"],
        "statutes_considered": [
            {"title": "Third Parties (Rights against Insurers) Act 2010", "provisions": []},
            {"title": "Insurance Act 2015", "provisions": ["section 9"]},
            {"title": "CPR Practice Direction 57AD", "provisions": ["paragraphs 6.3, 6.4 and 7.6"]},
        ],
        "key_facts": [
            "AmTrust sought to pass to Sompo liabilities arising out of a failed litigation funding scheme run through solicitor firms Pure and HSS.",
            "For the preliminary issues trial, AmTrust sought disclosure of pre-inception communications between Sompo and the insured firms about the scheme and related agreements.",
            "The deputy High Court judge refused disclosure issues 1A and 1B because he considered the documents unlikely to affect construction of the policies.",
            "The Court of Appeal held that the judge effectively pre-judged trial construction issues instead of applying the multi-factorial PD57AD test.",
        ],
        "short_title": "Construction dispute required underwriting disclosure",
        "procedural_posture": "Appeal from a case management decision refusing targeted extended disclosure in advance of a preliminary issues trial on policy coverage and exclusions.",
        "outcome": "Appeal allowed; the disputed pre-contract communications must be disclosed because they may be probative on policy construction and fairness required AmTrust, as statutory assignee, to see them.",
        "ratio": "Under PD57AD there is no standalone threshold test of relevance permitting a CMC judge to decide definitively that documents cannot affect trial construction; if contemporaneous contractual or incorporated documents may be probative, and disclosure is proportionate, the issue should be left open for the trial judge with disclosure ordered.",
        "legal_issues": [
            "Correct test for identifying issues for disclosure under PD57AD",
            "Whether incorporated underwriting materials might affect construction of standard-form professional indemnity policies",
            "How fairness operates where the claimant is a statutory assignee lacking access to the insured's documents",
            "Whether a disclosure judge may effectively resolve construction issues at case management stage",
        ],
        "catchwords": ["extended disclosure", "PD57AD", "insurance policy construction", "professional indemnity", "incorporation clause", "statutory assignee"],
        "index_terms": ["AmTrust", "Sompo", "Novitas", "Pure Legal", "HSS"],
        "linked_authorities": ["McParland & Partners Ltd v Whitehead", "Impact Funding Solutions Ltd v Barrington Support Services Ltd", "Financial Conduct Authority v Arch Insurance (UK) Ltd"],
        "confidence": {"score": 0.93, "level": "high", "notes": ["The judgment gives a clear procedural and doctrinal explanation of the PD57AD error."]},
        "storyline": {
            "title": "AmTrust won access to underwriting communications",
            "summary": "In insurance coverage litigation arising from a collapsed litigation funding scheme, the Court of Appeal held that a disclosure judge had gone too far by deciding the relevance point himself. Because the materials may bear on construction and AmTrust stood in the shoes of the insured firms, disclosure had to be ordered.",
            "span": {"start": "2025-01", "end": "2025-06", "label": "2025 preliminary issues phase"},
            "parties": [
                {"role": "appellant", "name": "AmTrust Specialty Limited", "short_name": "AmTrust"},
                {"role": "respondent", "name": "Endurance Worldwide Insurance Limited trading as Sompo International", "short_name": "Sompo"},
                {"role": "related_party", "name": "Novitas Loans Limited", "short_name": "Novitas"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "scheme-built", "order": 1, "date": None, "date_label": "Funding scheme period", "date_precision": "unknown", "title": "Litigation funding scheme and policies", "category": "background", "actor": "Scheme parties", "what_happened": "Novitas loans, ATE policies and solicitors' TOBAs operated alongside Sompo's professional indemnity policies for Pure and HSS.", "why_it_matters": "Those arrangements created the later coverage disputes.", "legal_hook": None},
                {"id": "scheme-collapse", "order": 2, "date": None, "date_label": "After scheme failure", "date_precision": "unknown", "title": "Scheme fails and claims follow", "category": "background", "actor": "Novitas and AmTrust", "what_happened": "Novitas sued AmTrust and AmTrust brought Part 20 claims against Sompo as statutory assignee of the insured firms' rights.", "why_it_matters": "The central dispute became whether the solicitors' liabilities fell within or outside Sompo's policy cover.", "legal_hook": "Third Parties (Rights against Insurers) Act 2010"},
                {"id": "preliminary-issues", "order": 3, "date": "2025-11", "date_label": "Trial fixed for November 2025", "date_precision": "approximate", "title": "Coverage issues split out", "category": "case_management", "actor": "Commercial Court", "what_happened": "A five-week preliminary issues trial was fixed to determine scope of cover and exclusions.", "why_it_matters": "The construction issues made contemporaneous underwriting communications potentially material.", "legal_hook": None},
                {"id": "disclosure-request", "order": 4, "date": None, "date_label": "Third CMC", "date_precision": "unknown", "title": "AmTrust seeks Issues 1A and 1B disclosure", "category": "application", "actor": "AmTrust", "what_happened": "AmTrust requested pre-inception communications between Sompo and each insured firm about the scheme and related agreements.", "why_it_matters": "The documents might show what business activities were disclosed and incorporated into the policies.", "legal_hook": "PD57AD"},
                {"id": "judge-refusal", "order": 5, "date": None, "date_label": "CMC decision", "date_precision": "unknown", "title": "Disclosure refused at first instance", "category": "decision", "actor": "Deputy High Court Judge", "what_happened": "The judge treated the construction issues as unlikely to be influenced by the communications and declined to order disclosure.", "why_it_matters": "That ruling limited the arguments and materials available for the preliminary issues trial.", "legal_hook": None},
                {"id": "appeal-brought", "order": 6, "date": None, "date_label": "Appeal to Court of Appeal", "date_precision": "unknown", "title": "AmTrust challenges the disclosure approach", "category": "appeal", "actor": "AmTrust", "what_happened": "AmTrust argued the judge had applied the wrong test and prematurely resolved the relevance of incorporated materials.", "why_it_matters": "The appeal focused on how PD57AD should operate in practice.", "legal_hook": None},
                {"id": "ca-principle", "order": 7, "date": None, "date_label": "Court of Appeal decision", "date_precision": "unknown", "title": "Court rejects threshold relevance approach", "category": "decision", "actor": "Court of Appeal", "what_happened": "Asplin LJ held there is no standalone threshold of relevance permitting the disclosure judge to determine definitively that the documents cannot matter.", "why_it_matters": "It restored the PD57AD multi-factorial approach and protected the trial judge's role.", "legal_hook": "PD57AD paragraphs 6.4 and 7.6"},
                {"id": "disclosure-ordered", "order": 8, "date": None, "date_label": "Appeal allowed", "date_precision": "unknown", "title": "Documents ordered to be disclosed", "category": "outcome", "actor": "Court of Appeal", "what_happened": "The court directed disclosure, noting the documents existed, were proportionate to produce and fairness required AmTrust to inspect them.", "why_it_matters": "AmTrust recovered access to the materials before trial.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "disclosure-request", "label": "Issues 1A and 1B framed", "impact": "Focused the dispute on a narrow but important body of underwriting communications."},
                {"stage_id": "judge-refusal", "label": "Construction issue pre-judged", "impact": "Triggered appellate intervention because the trial judge's role was curtailed."},
                {"stage_id": "disclosure-ordered", "label": "Assignee gets the documents", "impact": "Restored a fair footing for the preliminary issues trial."},
            ],
            "confidence": {"score": 0.92, "level": "high", "notes": ["The factual chronology before and after the CMC is clear, though not every underlying transaction date is given in the judgment."]},
        },
    },
    "760.json": {
        "judges": ["Lord Justice Zacaroli", "Lord Justice Popplewell", "Lord Justice Baker"],
        "area_of_law": ["Contract", "Sale of goods", "Commercial law"],
        "statutes_considered": [{"title": "Sale of Goods Act 1979", "provisions": ["section 8(2)"]}],
        "key_facts": [
            "KSY and Citrosuco entered a three-year Wesos supply contract under a free-trucks pricing mechanism, with 400MT per year priced at EUR1,350 and 800MT per year left at an 'open price to be fixed' by December of the prior year.",
            "Citrosuco contended that the 800MT component was unenforceable because price was left for later agreement.",
            "The trial judge held the 2018 contract was enforceable only as to the 400MT tranche and dismissed the bulk of KSY's claim.",
            "The Court of Appeal held that a term should be implied that, failing agreement, the price for the 800MT tranche would be a reasonable or market price.",
        ],
        "short_title": "Reasonable price implied into long-term Wesos contract",
        "procedural_posture": "Appeal from a High Court trial judgment holding that a long-term supply contract was unenforceable in part as an agreement to agree on price.",
        "outcome": "Appeal allowed; the 2018 contract should be preserved by implying a reasonable or market price for the open-price tranche.",
        "ratio": "Where experienced commercial parties intended to conclude a binding long-term supply bargain and the price can be objectively anchored to an accepted market benchmark, the court may imply a reasonable or market price notwithstanding wording that initially envisages later agreement, because section 8(2) does not preclude a common-law implication that preserves the bargain.",
        "legal_issues": [
            "Whether 'open price to be fixed' left the parties free to agree or disagree without constraint",
            "Relationship between section 8(2) of the Sale of Goods Act 1979 and common-law implication of a reasonable price",
            "Whether the FCOJ market supplied an objective benchmark for Wesos pricing",
            "How far courts should strive to preserve partially open-textured commercial contracts",
        ],
        "catchwords": ["agreement to agree", "reasonable price", "market price", "implied term", "sale of goods", "commercial certainty"],
        "index_terms": ["KSY Juice Blends", "Citrosuco", "Wesos", "free trucks", "FCOJ"],
        "linked_authorities": ["May & Butcher Ltd v The King", "Hillas & Co v Arcos Ltd", "Foley v Classique Coaches Ltd", "Mamidoil-Jetoil Greek Petroleum Co SA v OKTA Crude Oil Refinery AD", "BJ Aviation Ltd v Pool Aviation Ltd"],
        "confidence": {"score": 0.95, "level": "high", "notes": ["The judgment gives a detailed doctrinal survey and a clear reason for implying the term."]},
        "storyline": {
            "title": "A long-term juice supply deal was saved from partial failure",
            "summary": "KSY persuaded the Court of Appeal that a three-year Wesos contract should not fail merely because part of the price was to be fixed later. Because the parties plainly intended a binding bargain and the market supplied an objective yardstick, a reasonable or market price was implied.",
            "span": {"start": "2018-05", "end": "2025-06", "label": "May 2018 – June 2025"},
            "parties": [
                {"role": "appellant", "name": "KSY Juice Blends UK Limited", "short_name": "KSY"},
                {"role": "respondent", "name": "Citrosuco GMBH", "short_name": "Citrosuco"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "prior-dealings", "order": 1, "date": "2017", "date_label": "2017 contracts", "date_precision": "approximate", "title": "Parties build trading relationship", "category": "background", "actor": "KSY and Citrosuco", "what_happened": "Earlier 2017 Wesos contracts included tranches whose prices were fixed later and performed successfully.", "why_it_matters": "That course of dealing supported the view that the parties were willing to leave details to be worked out within a binding relationship.", "legal_hook": None},
                {"id": "2018-contract", "order": 2, "date": "2018-05-18", "date_label": "2018-05-18", "date_precision": "exact", "title": "Three-year 2018 contract agreed", "category": "contract", "actor": "KSY and Citrosuco", "what_happened": "The parties agreed a three-year 3600MT framework with invoicing at EUR1,600/MT and a free-trucks mechanism.", "why_it_matters": "The deal fixed much of the bargain but left pricing of the 800MT annual tranche open.", "legal_hook": None},
                {"id": "market-turns", "order": 3, "date": "2018-12", "date_label": "By late 2018", "date_precision": "approximate", "title": "Citrosuco's commercial appetite falls", "category": "background", "actor": "Citrosuco", "what_happened": "Citrosuco's need for Wesos reduced and the contract became commercially unattractive from its perspective.", "why_it_matters": "No agreement was ever reached on the yearly open price for the 800MT tranche.", "legal_hook": None},
                {"id": "performance-breakdown", "order": 4, "date": "2019-2020", "date_label": "2019–2020", "date_precision": "approximate", "title": "Deliveries and payment dispute emerges", "category": "default", "actor": "Citrosuco", "what_happened": "Citrosuco took only limited deliveries and failed to pay for all product supplied, prompting KSY to allege repudiatory breach.", "why_it_matters": "The dispute crystallised into a claim for price or damages.", "legal_hook": None},
                {"id": "trial-loss", "order": 5, "date": "2024-08-09", "date_label": "2024-08-09", "date_precision": "exact", "title": "Trial judge treats contract as partly unenforceable", "category": "decision", "actor": "High Court", "what_happened": "HHJ Pearce held the bargain worked for 400MT per year but that the 800MT open-price tranche was an unenforceable agreement to agree.", "why_it_matters": "That destroyed most of KSY's damages claim.", "legal_hook": "Sale of Goods Act 1979 section 8(2)"},
                {"id": "appeal-argument", "order": 6, "date": "2025", "date_label": "Appeal hearing", "date_precision": "unknown", "title": "KSY argues for implied objective price", "category": "appeal", "actor": "KSY", "what_happened": "KSY contended that the bargain should be saved by implying a reasonable or market price, anchored to the accepted FCOJ benchmark.", "why_it_matters": "The appeal turned on preserving rather than destroying a long-term commercial contract.", "legal_hook": None},
                {"id": "ca-principle", "order": 7, "date": None, "date_label": "Court of Appeal reasoning", "date_precision": "unknown", "title": "Court says section 8(2) does not block implication", "category": "decision", "actor": "Court of Appeal", "what_happened": "Zacaroli LJ held that section 8(2) does not prevent a common-law implication of reasonable price where the contract is otherwise intended to bind.", "why_it_matters": "This removed the doctrinal obstacle relied on by Citrosuco.", "legal_hook": "Contractual implication"},
                {"id": "appeal-allowed", "order": 8, "date": None, "date_label": "Appeal allowed", "date_precision": "unknown", "title": "Open-price tranche reinstated", "category": "outcome", "actor": "Court of Appeal", "what_happened": "The court implied a reasonable or market price term and allowed KSY's appeal.", "why_it_matters": "The contract was preserved for the disputed tranche and KSY recovered its claim position.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "2018-contract", "label": "The parties fixed most of the bargain", "impact": "Made it plausible that the court should preserve the remaining open-textured part."},
                {"stage_id": "trial-loss", "label": "Agreement-to-agree finding", "impact": "Forced KSY to test how far the law would imply objective price machinery."},
                {"stage_id": "appeal-allowed", "label": "Reasonable price implied", "impact": "Restored enforceability of the bulk tranche."},
            ],
            "confidence": {"score": 0.94, "level": "high", "notes": ["The contract structure and doctrinal holding are explicit."]},
        },
    },
    "763.json": {
        "judges": ["Lord Justice Holgate", "Lady Justice Andrews", "Lord Justice Coulson"],
        "area_of_law": ["Public law", "Transport law", "Judicial review"],
        "statutes_considered": [
            {"title": "Traffic Management Act 2004", "provisions": ["sections 16, 17 and 18"]},
            {"title": "Infrastructure Act 2015", "provisions": ["section 21"]},
        ],
        "key_facts": [
            "The challenge concerned the Secretary of State's 2 October 2023 decision to withdraw 2022 section 18 guidance on network management to support active travel.",
            "The claimant argued that the withdrawal thwarted a statutory objective of increasing active travel, failed to consider climate and air quality impacts, and was irrational or disproportionate.",
            "Heather Williams J refused permission to apply for judicial review after an oral renewal hearing.",
            "The Court of Appeal held that the statutory premise of the challenge was misconceived because the 2004 Act imposed no duty to issue, or retain, section 18 guidance favouring active travel.",
        ],
        "short_title": "Withdrawal of active-travel guidance not arguably unlawful",
        "procedural_posture": "Appeal against refusal of permission to seek judicial review of the withdrawal of guidance issued under section 18 of the Traffic Management Act 2004.",
        "outcome": "Permission to appeal and permission to apply for judicial review both refused; all remaining grounds were unarguable.",
        "ratio": "Sections 16 to 18 of the Traffic Management Act 2004 create network management duties focused on expeditious movement of traffic but do not impose any statutory objective requiring the Secretary of State to issue or maintain active-travel guidance, so withdrawal of such discretionary guidance does not of itself create a legal lacuna or improper purpose challenge.",
        "legal_issues": [
            "Whether the 2004 Act embeds a statutory objective of increasing active travel",
            "Whether the withdrawal of discretionary section 18 guidance can be attacked as creating a policy lacuna",
            "Proper characterization of the ministerial reasons for withdrawing the 2022 guidance",
            "Limits of proportionality and irrationality review in macro-political transport policy",
        ],
        "catchwords": ["judicial review", "active travel", "guidance withdrawal", "transport policy", "irrationality", "statutory purpose"],
        "index_terms": ["Dale Vince", "Secretary of State for Transport", "Traffic Management Act 2004", "Gear Change", "Plan for Drivers"],
        "linked_authorities": ["R (Palestine Solidarity Campaign Ltd) v Secretary of State for Communities and Local Government", "For Women Scotland Ltd v Scottish Ministers", "R (Packham) v Secretary of State for Transport"],
        "confidence": {"score": 0.93, "level": "high", "notes": ["The judgment clearly distinguishes the statutory argument from the policy disagreement."]},
        "storyline": {
            "title": "Challenge to withdrawal of active-travel guidance failed at the permission stage",
            "summary": "The claimant tried to convert an active-travel policy disagreement into a public law challenge to the Secretary of State's withdrawal of section 18 guidance. The Court of Appeal held that the statute did not require such guidance in the first place, and that the factual and irrationality complaints were likewise unarguable.",
            "span": {"start": "2020-05", "end": "2025", "label": "May 2020 – 2025"},
            "parties": [
                {"role": "claimant", "name": "Dale Vince", "short_name": "Vince"},
                {"role": "defendant", "name": "Secretary of State for Transport", "short_name": "Secretary of State"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "covid-guidance", "order": 1, "date": "2020-05-09", "date_label": "2020-05-09", "date_precision": "exact", "title": "Supplementary guidance first issued", "category": "policy", "actor": "Department for Transport", "what_happened": "COVID-era section 18 guidance was published to support reallocating road space toward walking and cycling.", "why_it_matters": "This later evolved into the 2022 active-travel guidance under challenge.", "legal_hook": "Traffic Management Act 2004 section 18"},
                {"id": "2022-guidance", "order": 2, "date": "2022-04-01", "date_label": "2022-04-01", "date_precision": "exact", "title": "Final 2022 guidance adopts nine measures", "category": "policy", "actor": "Secretary of State", "what_happened": "The revised guidance promoted a step-change in active-travel schemes, including modal filters, school streets and cycling infrastructure.", "why_it_matters": "It became the focal point of later complaints about withdrawal.", "legal_hook": None},
                {"id": "policy-review", "order": 3, "date": "2023-03", "date_label": "March to September 2023", "date_precision": "approximate", "title": "Ministers review LTNs and wider traffic measures", "category": "policy_review", "actor": "Department for Transport", "what_happened": "Officials advised ministers on concerns about low-traffic neighbourhoods and broader road-space reallocation measures.", "why_it_matters": "The materials showed the decision was not confined to a single modal-filter issue.", "legal_hook": None},
                {"id": "withdrawal", "order": 4, "date": "2023-10-02", "date_label": "2023-10-02", "date_precision": "exact", "title": "2022 guidance withdrawn", "category": "decision", "actor": "Secretary of State", "what_happened": "The active-travel guidance was withdrawn as part of a broader shift in policy direction announced the same day as the Plan for Drivers.", "why_it_matters": "That decision triggered the judicial review challenge.", "legal_hook": None},
                {"id": "paper-refusal", "order": 5, "date": "2024-05-29", "date_label": "2024-05-29", "date_precision": "exact", "title": "Permission refused on the papers", "category": "procedural", "actor": "Lang J", "what_happened": "The judicial review claim was first refused on paper.", "why_it_matters": "The claimant had to pursue an oral renewal.", "legal_hook": None},
                {"id": "oral-renewal", "order": 6, "date": "2024-11-07", "date_label": "2024-11-07", "date_precision": "exact", "title": "Oral renewal also refused", "category": "decision", "actor": "Heather Williams J", "what_happened": "The judge rejected the remaining grounds and refused permission to apply for judicial review.", "why_it_matters": "This became the subject of the appeal to the Court of Appeal.", "legal_hook": None},
                {"id": "statutory-point-rejected", "order": 7, "date": None, "date_label": "Court of Appeal judgment", "date_precision": "unknown", "title": "Court rejects statutory-purpose theory", "category": "decision", "actor": "Court of Appeal", "what_happened": "Holgate LJ held that the 2004 Act does not require the Secretary of State to create or preserve active-travel guidance at all.", "why_it_matters": "That conclusion undermined the claimant's central improper-purpose and lacuna arguments.", "legal_hook": "Traffic Management Act 2004 sections 16 to 18"},
                {"id": "appeal-refused", "order": 8, "date": None, "date_label": "Appeal refused", "date_precision": "unknown", "title": "Judicial review remains refused", "category": "outcome", "actor": "Court of Appeal", "what_happened": "The court held the wider irrationality and factual grounds were also unarguable and refused permission.", "why_it_matters": "The challenge ended without a substantive judicial review hearing.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "withdrawal", "label": "Guidance removed", "impact": "Converted a policy shift into potential public law litigation."},
                {"stage_id": "oral-renewal", "label": "Permission refused twice", "impact": "Forced the claimant to frame the case as an appeal on arguability."},
                {"stage_id": "statutory-point-rejected", "label": "No statutory active-travel objective found", "impact": "Collapsed the legal foundation of the claim."},
            ],
            "confidence": {"score": 0.92, "level": "high", "notes": ["The internal policy chronology is clearly summarized by the judgment."]},
        },
    },
    "775.json": {
        "judges": ["Lord Justice Coulson", "Lady Justice Andrews", "Lord Justice Holgate"],
        "area_of_law": ["Civil procedure", "Personal injury procedure", "Protocol practice"],
        "statutes_considered": [
            {"title": "Civil Procedure Rules", "provisions": ["rule 3.1(2)(g)", "rule 3.1(2)(p)", "rule 3.1(4)"]},
            {"title": "Practice Direction 49F", "provisions": ["paragraph 16"]},
            {"title": "Pre-Action Protocol for Low Value Personal Injury Claims in Road Traffic Accidents", "provisions": ["paragraph 5.7", "section 7"]},
        ],
        "key_facts": [
            "A low-value RTA claim entered the PAP in July 2020 and liability was admitted, but the claimant never produced a Stage 2 Settlement Pack.",
            "Days before limitation expired the claimant issued a Part 8 protective claim and obtained a stay under PD49F paragraph 16.",
            "When delay continued, the defendants asked the court to lift the stay and make an unless order requiring the Stage 2 pack to be served.",
            "Both DJ Baldwin and HHJ Wood KC held that the court had no jurisdiction to direct compliance with the PAP process, but the Court of Appeal disagreed.",
        ],
        "short_title": "Part 8 court can direct progress within the PAP",
        "procedural_posture": "Second appeal on whether a court seized of a protective Part 8 claim under PD49F may make directions compelling steps within the RTA low-value pre-action protocol.",
        "outcome": "Appeal allowed; once Part 8 proceedings exist, the court has jurisdiction to make case management orders, including conditional stays, to secure compliance with the PAP.",
        "ratio": "Although the PAP is ordinarily self-contained, a claimant who invokes the court's jurisdiction through a limitation-protective Part 8 claim cannot insist that the court stay passive: the stay mechanism itself regulates PAP compliance, and CPR 3.1 together with the practice direction on pre-action conduct permit directions requiring outstanding protocol steps.",
        "legal_issues": [
            "Whether the court can order compliance with Stage 2 of the PAP once a Part 8 protective claim has been issued",
            "Relationship between PD49F paragraph 16 stays and the court's general case management powers",
            "Whether the appeal was academic after the claim exited the portal",
            "Limits on unless orders and the proper exercise of discretion in low-value PAP cases",
        ],
        "catchwords": ["RTA Protocol", "Part 8", "limitation", "stay", "case management", "Settlement Pack"],
        "index_terms": ["MH Site Maintenance Services", "James Watson", "PD49F", "Stage 2 Settlement Pack", "protective claim"],
        "linked_authorities": ["Jet2 Holidays Ltd v Hughes", "Cable v Liverpool Victoria Insurance Co Ltd", "Hutcheson v Popdog Ltd"],
        "confidence": {"score": 0.95, "level": "high", "notes": ["The judgment gives a full procedural history and clear ratio."]},
        "storyline": {
            "title": "The court said a stayed Part 8 claim can police PAP delay",
            "summary": "A claimant let an admitted low-value RTA claim drift in Stage 2, then used a Part 8 protective claim to avoid a limitation defence. The Court of Appeal held that once the court is seized of the matter, it can direct concrete steps within the PAP rather than merely wait for the stay to expire.",
            "span": {"start": "2020-07", "end": "2025", "label": "July 2020 – 2025"},
            "parties": [
                {"role": "appellants", "name": "MH Site Maintenance Services Limited and insurer", "short_name": "Defendants"},
                {"role": "respondent", "name": "James Watson", "short_name": "Claimant"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "pap-starts", "order": 1, "date": "2020-07-17", "date_label": "2020-07-17", "date_precision": "exact", "title": "RTA claim enters PAP", "category": "protocol", "actor": "Claimant", "what_happened": "The claimant began the portal process by claim notification form.", "why_it_matters": "This set the claim on the route intended to avoid ordinary court proceedings.", "legal_hook": None},
                {"id": "liability-admitted", "order": 2, "date": "2020-07-30", "date_label": "2020-07-30", "date_precision": "exact", "title": "Liability admitted", "category": "protocol", "actor": "Defendants", "what_happened": "Liability admission completed Stage 1 and moved the claim into Stage 2.", "why_it_matters": "The claimant then had to prepare a Settlement Pack and advance the quantum case.", "legal_hook": None},
                {"id": "limitation-pressure", "order": 3, "date": "2022-09-06", "date_label": "2022-09-06", "date_precision": "exact", "title": "Protective Part 8 claim issued", "category": "procedure", "actor": "Claimant", "what_happened": "With no Stage 2 pack ready and limitation about to expire, the claimant issued a Part 8 claim seeking a stay under PD49F.", "why_it_matters": "This brought the court formally into the picture.", "legal_hook": "PD49F paragraph 16"},
                {"id": "stay-granted", "order": 4, "date": "2022-09-13", "date_label": "2022-09-13", "date_precision": "exact", "title": "One-year stay granted", "category": "order", "actor": "Deputy District Judge Openshaw", "what_happened": "The Part 8 proceedings were stayed for a year with an unless provision tied to lifting the stay and moving on procedurally.", "why_it_matters": "The stay protected limitation but also left the PAP still unfinished.", "legal_hook": None},
                {"id": "defendants-apply", "order": 5, "date": "2023-06-13", "date_label": "2023-06-13", "date_precision": "exact", "title": "Defendants seek coercive directions", "category": "application", "actor": "Defendants", "what_happened": "After further silence, the defendants asked for the stay to be lifted and for an unless order requiring a Stage 2 Settlement Pack.", "why_it_matters": "This squarely raised whether the court could compel protocol progress.", "legal_hook": "CPR 3.1(2)(p)"},
                {"id": "jurisdiction-refused", "order": 6, "date": "2023-07-05", "date_label": "2023-07-05 and 2024-01-16", "date_precision": "approximate", "title": "Two judges say the court has no power", "category": "decision", "actor": "District Judge Baldwin and HHJ Wood KC", "what_happened": "Both first-instance judges held that the PAP remained outside the court's reach even though a stayed Part 8 claim existed.", "why_it_matters": "The defendants were left without a remedy against procedural drift.", "legal_hook": None},
                {"id": "portal-exit", "order": 7, "date": "2023-10-17", "date_label": "2023-10-17 onward", "date_precision": "approximate", "title": "Claim exits the portal unreasonably", "category": "development", "actor": "Claimant", "what_happened": "The claim was taken out of the portal on an incorrect basis, later described as unreasonable by a district judge.", "why_it_matters": "That development prompted an argument that the appeal had become academic.", "legal_hook": None},
                {"id": "appeal-allowed", "order": 8, "date": None, "date_label": "Court of Appeal decision", "date_precision": "unknown", "title": "Court of Appeal confirms jurisdiction", "category": "outcome", "actor": "Court of Appeal", "what_happened": "Coulson LJ held that the court could make direct or conditional stay orders to secure PAP compliance once Part 8 proceedings existed.", "why_it_matters": "The judgment clarifies national practice for limitation-protective PAP cases.", "legal_hook": "CPR 3.1 and Pre-Action Conduct PD"},
            ],
            "turning_points": [
                {"stage_id": "limitation-pressure", "label": "Part 8 claim invoked the court", "impact": "Shifted the dispute from a purely pre-action setting into one with judicial case-management powers."},
                {"stage_id": "jurisdiction-refused", "label": "Court declared powerless", "impact": "Created the procedural issue of general importance for the second appeal."},
                {"stage_id": "appeal-allowed", "label": "PAP delay became justiciable", "impact": "Established that stayed Part 8 claims may be managed actively, not passively."},
            ],
            "confidence": {"score": 0.94, "level": "high", "notes": ["Dates and procedural sequence are explicit in the judgment."]},
        },
    },
    "776.json": {
        "judges": ["Lady Justice Nicola Davies", "Lord Justice Edis", "Lord Justice Bean"],
        "area_of_law": ["Tort", "Sports law", "Negligence"],
        "statutes_considered": [],
        "key_facts": [
            "During an amateur rugby match in October 2017, the defendant sprinted from kickoff and collided from behind with the claimant, who was watching the ball and not carrying it.",
            "The collision caused catastrophic spinal injury at C5/C6, and liability at trial turned on breach of duty in the sporting context.",
            "Sweeting J found the defendant liable, describing the conduct as reckless and contrary to the laws of rugby.",
            "On appeal the defendant challenged the legal test and the characterization of the incident, but the Court of Appeal upheld liability through the claimant's Respondent's Notice.",
        ],
        "short_title": "Rugby collision was negligent, not mere error of judgment",
        "procedural_posture": "Appeal from a liability judgment in a personal injury action arising from an amateur rugby collision, with the claimant relying on a Respondent's Notice to uphold the result on orthodox negligence grounds.",
        "outcome": "Appeal dismissed; the trial judge's findings established negligence in the sporting context even if he used the higher language of recklessness.",
        "ratio": "In sporting negligence claims there is no separate legal requirement to prove recklessness, but where the findings show a player had time to avoid or soften a dangerous collision with a non-ball-carrying opponent and instead ran full speed into him, that conduct exceeds momentary carelessness and satisfies the negligence standard appropriate to the game.",
        "legal_issues": [
            "Proper negligence standard in competitive sport",
            "Difference between recklessness as a factual descriptor and negligence as the cause of action",
            "Whether the collision involved foreseeable risk of serious injury rather than mere knockdown risk",
            "Whether the incident was just a fast-moving error of judgment",
        ],
        "catchwords": ["sporting negligence", "rugby", "recklessness", "breach of duty", "spinal injury", "respondent's notice"],
        "index_terms": ["Tom Clark", "Omar Elbanna", "Sweeting J", "Cheltenham Tigers", "Midsomer Norton"],
        "linked_authorities": ["Condon v Basi", "Smoldon v Whitworth", "Caldwell v Maguire", "Czernuszka v King"],
        "confidence": {"score": 0.93, "level": "high", "notes": ["Video-based factual findings are central and are clearly summarised in the appellate judgment."]},
        "storyline": {
            "title": "A dangerous rugby collision remained actionable in negligence",
            "summary": "The Court of Appeal treated the trial judge's findings about a full-speed collision into a non-ball-carrying player as more than momentary carelessness. Even without embarking on a separate analysis of recklessness, the findings comfortably supported negligence and the defendant's appeal was dismissed.",
            "span": {"start": "2017-10-07", "end": "2025", "label": "October 2017 – 2025"},
            "parties": [
                {"role": "claimant", "name": "Tom Clark", "short_name": "Claimant"},
                {"role": "defendant", "name": "Omar Elbanna", "short_name": "Defendant"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "match-collision", "order": 1, "date": "2017-10-07", "date_label": "2017-10-07", "date_precision": "exact", "title": "Collision at amateur rugby match", "category": "incident", "actor": "Defendant", "what_happened": "From the restart, the defendant sprinted directly toward the claimant and struck him from behind while he watched the ball.", "why_it_matters": "The claimant suffered serious spinal injury and later sued in negligence.", "legal_hook": "Laws of rugby, especially law 10.4(f)"},
                {"id": "foul-play-process", "order": 2, "date": "2017-11", "date_label": "November 2017", "date_precision": "approximate", "title": "Disciplinary proceedings do not uphold foul play complaint", "category": "background", "actor": "Rugby disciplinary bodies", "what_happened": "A disciplinary panel and review did not find incontrovertible evidence of dangerous charging or shouldering.", "why_it_matters": "The civil negligence issue still had to be assessed independently.", "legal_hook": None},
                {"id": "civil-claim", "order": 3, "date": "2021-01-27", "date_label": "2021-01-27", "date_precision": "exact", "title": "Negligence claim pleaded", "category": "pleading", "actor": "Claimant", "what_happened": "The claimant alleged the collision was unnecessary, dangerous and negligent, with reckless disregard for safety.", "why_it_matters": "The pleaded cause of action was negligence, not a standalone tort of recklessness.", "legal_hook": None},
                {"id": "video-evidence", "order": 4, "date": None, "date_label": "Trial", "date_precision": "unknown", "title": "Video and expert evidence analysed", "category": "evidence", "actor": "High Court", "what_happened": "The judge relied heavily on match footage and preferred the claimant's rugby expert's reading of the collision.", "why_it_matters": "Those findings supported the view that the defendant had time to slow, deviate or soften the impact.", "legal_hook": None},
                {"id": "liability-found", "order": 5, "date": "2024-03-20", "date_label": "2024-03-20", "date_precision": "exact", "title": "Trial judge finds liability", "category": "decision", "actor": "Sweeting J", "what_happened": "The judge found the defendant's conduct reckless and held liability was made out.", "why_it_matters": "The appeal focused on whether the reasoning and legal standard were sound.", "legal_hook": None},
                {"id": "permission-limited", "order": 6, "date": "2024-12-19", "date_label": "2024-12-19", "date_precision": "exact", "title": "Permission to appeal limited", "category": "appeal", "actor": "Whipple LJ", "what_happened": "Permission was granted on limited points about recklessness, reasons and breach of duty in sport, but not on fact findings.", "why_it_matters": "The defendant could not reopen the trial judge's detailed factual conclusions.", "legal_hook": None},
                {"id": "rn-upheld", "order": 7, "date": None, "date_label": "At the appeal hearing", "date_precision": "unknown", "title": "Respondent's Notice drives outcome", "category": "appeal", "actor": "Court of Appeal", "what_happened": "The court indicated early in the hearing that the findings sustained a negligence conclusion even without resolving the law of recklessness.", "why_it_matters": "This made an extended analysis of recklessness unnecessary.", "legal_hook": None},
                {"id": "appeal-dismissed", "order": 8, "date": None, "date_label": "Appeal dismissed", "date_precision": "unknown", "title": "Liability stands", "category": "outcome", "actor": "Court of Appeal", "what_happened": "Nicola Davies LJ held the trial findings showed negligence in the sporting sense and dismissed the appeal.", "why_it_matters": "The claimant retained the liability judgment and moved on to quantum.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "video-evidence", "label": "Footage fixed the facts", "impact": "The appeal could not realistically recast the collision as a mere split-second mishap."},
                {"stage_id": "liability-found", "label": "Recklessness language used", "impact": "Created the doctrinal argument later neutralised by the Respondent's Notice."},
                {"stage_id": "rn-upheld", "label": "Negligence basis confirmed", "impact": "Let the Court of Appeal uphold the judgment without resolving broader debates about recklessness."},
            ],
            "confidence": {"score": 0.92, "level": "high", "notes": ["The key event and appellate reasoning are explicit; exact trial-hearing dates beyond judgment are less important."]},
        },
    },
    "782.json": {
        "judges": ["Lord Justice Birss", "Lord Justice Zacaroli"],
        "area_of_law": ["Civil procedure", "Contempt of court", "Remedies"],
        "statutes_considered": [
            {"title": "Protection from Harassment Act 1997", "provisions": []},
            {"title": "Senior Courts Act 1981", "provisions": ["section 16"]},
            {"title": "Human Rights Act 1998", "provisions": ["section 7"]},
        ],
        "key_facts": [
            "Following a neighbour dispute trial, HHJ Venn had made injunctions against Mr Coates and later found him in contempt once already.",
            "After his release from the first committal sentence, Mr Coates faced a second contempt application involving 20 allegations, including threats, property damage and roof-tile throwing.",
            "Parallel criminal proceedings were on foot over some of the same events, but the civil contempt proceedings were not stayed.",
            "The Court of Appeal rejected arguments that the civil proceedings should have been adjourned pending the criminal case and that the sentence should have been concurrent rather than consecutive.",
        ],
        "short_title": "Second neighbour-dispute contempt appeal failed",
        "procedural_posture": "Appeal against findings and sentence in second civil contempt proceedings for repeated breaches of injunctions arising from a neighbour and harassment dispute.",
        "outcome": "Appeal dismissed on both grounds; the judge was entitled to proceed despite parallel criminal proceedings and to structure sentence by distinct incidents subject to totality reduction.",
        "ratio": "Civil committal proceedings for breach of injunctions serve a separate function from criminal proceedings and should ordinarily be dealt with swiftly; absent real prejudice amounting to injustice there is no requirement to stay them, and sentencing may properly treat multiple proven contempts as separate incidents while applying totality.",
        "legal_issues": [
            "Whether pending criminal proceedings on overlapping facts require a stay of civil contempt proceedings",
            "How sentencing objectives for civil contempt differ from criminal punishment",
            "Whether multiple contempts should run concurrently or consecutively",
            "Limits on appealing adverse reasoning that does not affect the operative order",
        ],
        "catchwords": ["civil contempt", "parallel criminal proceedings", "injunction breach", "sentence", "totality", "jurisdiction"],
        "index_terms": ["Mark Coates", "HHJ Venn", "neighbour dispute", "committal", "harassment injunction"],
        "linked_authorities": ["Barnet LBC v Hurst", "Lomas v Parle", "Lovett v Wigan County Council", "Cie Noga d’Importation et d’Exportation SA v ANZ Banking Group Ltd", "In Re W (A Child) (Care Proceedings: Non-Party Appeal)"],
        "confidence": {"score": 0.92, "level": "high", "notes": ["The judgment is detailed on both the procedural overlap issue and sentencing approach."]},
        "storyline": {
            "title": "Mr Coates could not undo the second committal judgment",
            "summary": "After repeated breaches of neighbour-dispute injunctions, Mr Coates argued that civil contempt proceedings should have paused for a criminal trial and that the sentence was too heavily stacked. The Court of Appeal rejected both points, stressing the separate purpose of civil committal and the legitimacy of treating the incidents distinctly.",
            "span": {"start": "2022-09-22", "end": "2025-05", "label": "September 2022 – May 2025"},
            "parties": [
                {"role": "appellant", "name": "Mark Gary Coates", "short_name": "Mr Coates"},
                {"role": "respondents", "name": "Janice Elizabeth Turner and Brian David Abernethy Greenwood", "short_name": "Neighbours"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "original-trial", "order": 1, "date": "2022-09-22", "date_label": "2022-09-22", "date_precision": "exact", "title": "Boundary and harassment trial ends in injunctions", "category": "decision", "actor": "HHJ Venn", "what_happened": "The neighbours succeeded at trial, obtaining damages, costs and injunctions regulating behaviour and property use.", "why_it_matters": "Those injunctions became the foundation for later contempt proceedings.", "legal_hook": "Protection from Harassment Act 1997"},
                {"id": "first-committal", "order": 2, "date": "2023-10-26", "date_label": "2023-10-26", "date_precision": "exact", "title": "First committal sentence imposed", "category": "contempt", "actor": "HHJ Venn", "what_happened": "Many initial breaches were found proved and Mr Coates was sentenced to 252 days' imprisonment.", "why_it_matters": "It put him on explicit notice that further breaches would attract substantial punishment.", "legal_hook": None},
                {"id": "first-appeal-warning", "order": 3, "date": "2023-12-12", "date_label": "2023-12-12", "date_precision": "exact", "title": "Court of Appeal cuts first sentence but warns of future consequences", "category": "appeal", "actor": "Court of Appeal", "what_happened": "The court reduced the first sentence and ordered release, but expressly warned that future breaches would likely lead to a substantial committal term.", "why_it_matters": "The warning later informed the seriousness of the second sentence.", "legal_hook": None},
                {"id": "sale-order", "order": 4, "date": "2024-03-14", "date_label": "2024-03-14", "date_precision": "exact", "title": "Order for sale of home made", "category": "enforcement", "actor": "Court", "what_happened": "A sale order was made over the Coates property to enforce the original financial liabilities.", "why_it_matters": "Three months later, tensions escalated dramatically around the property.", "legal_hook": None},
                {"id": "second-application", "order": 5, "date": "2024-04-17", "date_label": "2024-04-17", "date_precision": "exact", "title": "Second contempt application issued", "category": "contempt", "actor": "Neighbours", "what_happened": "A new application alleged 20 further injunction breaches, including threats, violence and property damage.", "why_it_matters": "This began the second round of contempt litigation.", "legal_hook": None},
                {"id": "roof-tiles", "order": 6, "date": "2024-06-10", "date_label": "2024-06-10", "date_precision": "exact", "title": "Roof-tile incident intensifies the case", "category": "incident", "actor": "Mr Coates", "what_happened": "Mr Coates damaged his own and the neighbours' property and threw roof tiles, adding some of the most serious allegations.", "why_it_matters": "These incidents strongly drove the ultimate sentence.", "legal_hook": None},
                {"id": "stay-refused-and-heard", "order": 7, "date": "2024-08-12 to 2024-09-17", "date_label": "August–September 2024", "date_precision": "approximate", "title": "Stay refused and second committal proved", "category": "decision", "actor": "HHJ Venn", "what_happened": "The judge refused to stay the contempt case for the criminal process, found 19 of 20 allegations proved and sentenced Mr Coates to 448 days after totality.", "why_it_matters": "This produced the judgment challenged on appeal.", "legal_hook": None},
                {"id": "appeal-dismissed", "order": 8, "date": "2025-05-14", "date_label": "2025-05-14", "date_precision": "exact", "title": "Second appeal dismissed", "category": "outcome", "actor": "Court of Appeal", "what_happened": "Birss LJ held that the parallel criminal case created no injustice requiring a stay and that the sentence structure was within range.", "why_it_matters": "The second committal outcome stood in full.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "first-appeal-warning", "label": "Warning after first appeal", "impact": "Put future breaches in a more serious sentencing frame."},
                {"stage_id": "roof-tiles", "label": "Violence and property damage escalated", "impact": "Made the second contempt application much graver than a repetition of minor breaches."},
                {"stage_id": "appeal-dismissed", "label": "No stay principle reaffirmed", "impact": "Confirmed the separate and urgent function of civil committal proceedings."},
            ],
            "confidence": {"score": 0.91, "level": "high", "notes": ["Dates and sequence are clear; some criminal-case details are included only as context."]},
        },
    },
    "783.json": {
        "judges": ["Lady Justice Asplin", "Lord Justice Popplewell", "Lord Justice Zacaroli"],
        "area_of_law": ["Aviation finance", "Commercial contracts", "Appellate procedure"],
        "statutes_considered": [
            {"title": "Law of Property Act 1925", "provisions": ["section 103"]},
            {"title": "Senior Courts Act 1981", "provisions": ["section 16"]},
            {"title": "Vienna Convention on the Law of Treaties 1969", "provisions": ["articles 31 and 32"]},
        ],
        "key_facts": [
            "VietJet acquired four Airbus A321 aircraft under JOLCO financing structures involving leases, subleases, loan agreements and security assignments.",
            "After COVID-era disruption, rent arrears accrued and in October 2021 the security trustees served termination notices and FitzWalter entities took assignments of the debt positions and security roles.",
            "Picken J held for FWA on liability, including validity of the termination notices, FitzWalter's status as a permitted assignee and security trustee, and double-tax-treaty issues affecting the NEO loan agreements.",
            "The Court of Appeal rejected all five appeal grounds, including a jurisdictional attempt to challenge only one adverse aspect of the judge's reasoning on relief from forfeiture.",
        ],
        "short_title": "VietJet failed to upset aircraft-finance enforcement judgment",
        "procedural_posture": "Appeal from a Commercial Court liability judgment in aircraft finance enforcement litigation concerning four Airbus acquisitions, lease termination, assignments and treaty-related qualifying lender points.",
        "outcome": "Appeal dismissed on all grounds; the termination notices were valid, FitzWalter entities qualified as permitted assignee/security trustee, the tax-treaty grounds failed, and ground 5 could not be entertained because it attacked reasons not the order.",
        "ratio": "The security assignment and co-extensive rights provisions allowed the security trustee to issue termination notices without waiting for a separate enforcement event; 'financial institution' in the relevant finance documents bore the established broad Argo v Essar meaning; and an appellant cannot use section 16 of the Senior Courts Act to challenge only an unattractive piece of reasoning when the operative decision on relief is not appealed.",
        "legal_issues": [
            "Whether the security trustee could validly terminate the leases under the assignment documents before an enforcement event",
            "Meaning of 'financial institution' in permitted assignee and successor security trustee provisions",
            "Double-tax-treaty qualification points under the NEO loan agreements",
            "Whether the Court of Appeal has jurisdiction to hear a ground attacking reasoning alone, without challenging the operative order",
        ],
        "catchwords": ["aviation finance", "JOLCO", "termination notice", "security trustee", "financial institution", "jurisdiction"],
        "index_terms": ["VietJet", "FW Aviation", "FitzWalter", "Picken J", "Airbus A321"],
        "linked_authorities": ["The Argo Fund Ltd v Essar Steel Ltd", "Sunport Shipping Ltd v Tryg Baltica International (UK) Ltd", "Royal Bank of Canada v HMRC", "GE Financial Investments v HMRC", "Cie Noga d’Importation et d’Exportation SA v ANZ Banking Group Ltd"],
        "confidence": {"score": 0.9, "level": "high", "notes": ["The file is heavily compressed in source form, but the appellate issues and holdings are clear from the judgment text."]},
        "storyline": {
            "title": "VietJet could not undo the finance-side enforcement architecture",
            "summary": "VietJet challenged a wide range of holdings from an aircraft-finance enforcement trial, from termination rights to qualifying assignee status and treaty points. The Court of Appeal rejected each challenge and also shut down an attempt to appeal a finding embedded only in the reasoning on relief from forfeiture.",
            "span": {"start": "2018", "end": "2025", "label": "2018 – 2025"},
            "parties": [
                {"role": "appellant", "name": "VietJet Aviation Joint Stock Company", "short_name": "VietJet"},
                {"role": "respondent", "name": "FW Aviation (Holdings) 1 Limited", "short_name": "FWA"},
                {"role": "related_party", "name": "FitzWalter Capital Partners (Financial Trading) Limited", "short_name": "FWC"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "aircraft-acquisitions", "order": 1, "date": "2018-2019", "date_label": "2018–2019", "date_precision": "approximate", "title": "Four Airbus aircraft financed through JOLCO structures", "category": "transaction", "actor": "VietJet and financing parties", "what_happened": "Separate SPVs bought two NEO and two CEO aircraft under lease, sublease, loan and security assignment structures.", "why_it_matters": "Those interlocking documents generated every issue in the litigation.", "legal_hook": None},
                {"id": "covid-arrears", "order": 2, "date": "2020-2021", "date_label": "2020–2021", "date_precision": "approximate", "title": "COVID disruption creates rent arrears", "category": "default", "actor": "VietJet", "what_happened": "Operational restrictions in Vietnam caused payment pressure and negotiations over rent deferrals with the lenders.", "why_it_matters": "The defaults set the enforcement sequence in motion.", "legal_hook": None},
                {"id": "termination-notices", "order": 3, "date": "2021-10", "date_label": "October 2021", "date_precision": "approximate", "title": "Security trustees terminate for non-payment", "category": "enforcement", "actor": "BNP and Natixis as security trustees", "what_happened": "Termination notices were served for arrears ranging from 48 to 118 days across the aircraft.", "why_it_matters": "Ground 1 on appeal attacked the trustees' right to do this under the assignment structure.", "legal_hook": None},
                {"id": "fitzwalter-assignment", "order": 4, "date": "2021-10 to 2021-11", "date_label": "Late October to early November 2021", "date_precision": "approximate", "title": "FitzWalter entities take assignments and security roles", "category": "assignment", "actor": "FWC and FWA", "what_happened": "FWC acquired the loan positions and became successor security trustee, with FWA later enforcing as assignee.", "why_it_matters": "This drove the 'financial institution' and tax-treaty grounds.", "legal_hook": None},
                {"id": "vietnam-shareholder-case", "order": 5, "date": "2023-02 to 2023-04", "date_label": "February–April 2023", "date_precision": "approximate", "title": "Vietnam shareholder proceedings complicate enforcement", "category": "satellite_litigation", "actor": "Silva Star and other shareholders", "what_happened": "Proceedings in Vietnam sought to undo deregistration steps and led to later contempt allegations and relief-from-forfeiture arguments.", "why_it_matters": "These facts fed the reasoning challenged unsuccessfully under ground 5.", "legal_hook": None},
                {"id": "commercial-trial", "order": 6, "date": "2024-06-04 to 2024-06-14", "date_label": "4–14 June 2024", "date_precision": "approximate", "title": "Picken J tries liability issues", "category": "trial", "actor": "Commercial Court", "what_happened": "The court heard liability issues on termination, assignments, treaty status and relief-related conduct.", "why_it_matters": "The trial produced the detailed judgment under appeal.", "legal_hook": None},
                {"id": "trial-judgment", "order": 7, "date": "2024-07-31", "date_label": "2024-07-31", "date_precision": "exact", "title": "FWA wins on liability", "category": "decision", "actor": "Picken J", "what_happened": "The judge held the termination notices valid and resolved all material liability questions in FWA's favour.", "why_it_matters": "This set up a five-ground appeal and later quantum judgment.", "legal_hook": None},
                {"id": "appeal-dismissed", "order": 8, "date": "2025", "date_label": "2025 appeal judgment", "date_precision": "unknown", "title": "Court of Appeal dismisses every ground", "category": "outcome", "actor": "Court of Appeal", "what_happened": "Popplewell LJ rejected grounds 1 to 4 on the merits and held ground 5 was not a justiciable appeal from the order at all.", "why_it_matters": "The enforcement judgment survived intact.", "legal_hook": "Senior Courts Act 1981 section 16"},
            ],
            "turning_points": [
                {"stage_id": "termination-notices", "label": "Trustees pulled the trigger", "impact": "Made the meaning of the assignment documents decisive."},
                {"stage_id": "fitzwalter-assignment", "label": "FitzWalter stepped into the debt stack", "impact": "Generated the financial-institution and tax-treaty disputes."},
                {"stage_id": "appeal-dismissed", "label": "Reasoning-only challenge rebuffed", "impact": "Confirmed the limits of appellate jurisdiction over non-operative findings."},
            ],
            "confidence": {"score": 0.89, "level": "high", "notes": ["Exact date of the appeal judgment is not stated in the source file, but the sequence of events is clear."]},
        },
    },
    "784.json": {
        "judges": ["Lady Justice Elisabeth Laing", "Lord Justice Snowden", "Lord Justice Baker"],
        "area_of_law": ["Immigration", "EU law", "Public law"],
        "statutes_considered": [
            {"title": "Directive 2004/38/EC", "provisions": ["articles 16 and 28"]},
            {"title": "Immigration (European Economic Area) Regulations 2016", "provisions": ["regulations 3, 15, 23 and 27"]},
            {"title": "Citizens’ Rights (Application of Deadline and Temporary Protection) (EU Exit) Regulations 2020", "provisions": ["regulations 5 to 10"]},
        ],
        "key_facts": [
            "Mr Borges entered the UK in 2002 as the family member of his Portuguese father, later renounced Indian citizenship and acquired Portuguese citizenship in 2014.",
            "Following serious criminal offending and a 2022 deportation decision, the First-tier Tribunal allowed his appeal and the Upper Tribunal dismissed the Secretary of State's appeal.",
            "The tribunals treated residence accumulated before he became an EU citizen as counting toward the ten years needed for the highest level of EU-law protection from expulsion.",
            "The Court of Appeal held that the highest level of protection under article 28(3) required ten years' residence as a Union citizen, not merely as a third-country family member who later became one, and remitted the case.",
        ],
        "short_title": "Enhanced article 28 protection required ten years as an EU citizen",
        "procedural_posture": "Secretary of State's appeal from an Upper Tribunal decision upholding the FTT's allowance of an appeal against deportation under preserved EEA law.",
        "outcome": "Appeal allowed and remitted; the tribunals misdirected themselves by counting pre-citizenship residence toward article 28(3) enhanced protection, and the serious-grounds issue must now be determined on the correct footing.",
        "ratio": "The graduated protection against expulsion under the Directive depends on the distinct status and Treaty-derived rights of Union citizens; a person cannot qualify for article 28(3) enhanced protection by counting years spent only as a third-country family member before obtaining EU citizenship.",
        "legal_issues": [
            "Whether residence before becoming an EU citizen counts toward the ten-year article 28(3) threshold",
            "Relationship between permanent residence and enhanced protection under preserved EEA law",
            "Effect of imprisonment on continuity and integration in the expulsion context",
            "Whether the Upper Tribunal could re-make imperative-grounds analysis without first identifying and setting aside an error of law",
        ],
        "catchwords": ["deportation", "EU free movement", "enhanced protection", "article 28(3)", "continuous residence", "EEA Regulations"],
        "index_terms": ["Borges", "Directive 2004/38", "regulation 27", "permanent residence", "imperative grounds"],
        "linked_authorities": ["FV (Italy) v Secretary of State for the Home Department", "B v Land Baden-Württemberg", "Vomero v Secretary of State for the Home Department", "Onuekwere v Secretary of State for the Home Department", "Hafeez v Secretary of State for the Home Department"],
        "confidence": {"score": 0.95, "level": "high", "notes": ["The judgment is detailed and expressly addresses both the construction issue and the UT's error-of-law methodology."]},
        "storyline": {
            "title": "The Secretary of State regained the argument on enhanced deportation protection",
            "summary": "Two tribunals had treated Mr Borges's long residence in the UK as enough to trigger the highest EU-law protection against expulsion even though he only became an EU citizen in 2014. The Court of Appeal disagreed, held that the legal premise was wrong, and sent the case back to be decided on the lower but still significant protection level.",
            "span": {"start": "2002", "end": "2025", "label": "2002 – 2025"},
            "parties": [
                {"role": "appellant", "name": "Secretary of State for the Home Department", "short_name": "Secretary of State"},
                {"role": "respondent", "name": "Myron Francisco Joseph Borges", "short_name": "Mr Borges"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "arrival-as-family-member", "order": 1, "date": "2002", "date_label": "2002", "date_precision": "approximate", "title": "Mr Borges arrives as family member", "category": "background", "actor": "Mr Borges", "what_happened": "He came to the UK as the family member of his Portuguese father rather than as an EU citizen in his own right.", "why_it_matters": "That initial status became critical to the article 28(3) issue.", "legal_hook": None},
                {"id": "portuguese-citizenship", "order": 2, "date": "2014", "date_label": "2014", "date_precision": "approximate", "title": "He becomes a Portuguese citizen", "category": "status_change", "actor": "Mr Borges", "what_happened": "After renouncing Indian nationality, he acquired Portuguese citizenship and became an EU citizen.", "why_it_matters": "Only from this point did he enjoy Treaty rights in his own status.", "legal_hook": None},
                {"id": "serious-offending", "order": 3, "date": "2019-06-03", "date_label": "2019-06-03", "date_precision": "exact", "title": "Serious index offences lead to six-year sentence", "category": "criminal", "actor": "Criminal court", "what_happened": "Mr Borges was convicted of aggravated burglary, burglary and drug possession and sentenced to six years' imprisonment.", "why_it_matters": "The offences prompted renewed deportation action and continuity arguments.", "legal_hook": None},
                {"id": "deportation-decision", "order": 4, "date": "2022-11-22", "date_label": "2022-11-22", "date_precision": "exact", "title": "Secretary of State decides to deport", "category": "decision", "actor": "Secretary of State", "what_happened": "The Home Office decided that serious grounds of public policy justified deportation and denied enhanced ten-year protection.", "why_it_matters": "This was the operative EEA decision under appeal.", "legal_hook": "Regulation 27"},
                {"id": "ftt-win", "order": 5, "date": "2023-08", "date_label": "FTT determination", "date_precision": "unknown", "title": "First-tier Tribunal allows appeal", "category": "tribunal", "actor": "First-tier Tribunal", "what_happened": "The FTT accepted that Mr Borges had continuous residence attracting the highest level of protection.", "why_it_matters": "That conclusion set the framework for the UT and then the Court of Appeal.", "legal_hook": None},
                {"id": "ut-dismisses", "order": 6, "date": "2024-02-15", "date_label": "2024-02-15", "date_precision": "exact", "title": "Upper Tribunal upholds the FTT", "category": "tribunal", "actor": "Upper Tribunal", "what_happened": "The UT held that pre-citizenship residence as a family member could count toward the ten-year article 28(3) period and found no imperative grounds anyway.", "why_it_matters": "This created both the construction issue and a procedural error-of-law issue on further appeal.", "legal_hook": None},
                {"id": "ca-construction-ruling", "order": 7, "date": None, "date_label": "Court of Appeal judgment", "date_precision": "unknown", "title": "Court rejects counting pre-citizenship residence", "category": "decision", "actor": "Court of Appeal", "what_happened": "Elisabeth Laing LJ held that article 28(3) protection depends on residence as a Union citizen, not years spent only with derivative status.", "why_it_matters": "The entire legal basis of the tribunal outcome fell away.", "legal_hook": "Directive 2004/38 article 28(3)"},
                {"id": "remittal", "order": 8, "date": None, "date_label": "Appeal allowed and remitted", "date_precision": "unknown", "title": "Case sent back on correct legal footing", "category": "outcome", "actor": "Court of Appeal", "what_happened": "The appeal was allowed and remitted for consideration of deportation on the serious-grounds level of protection.", "why_it_matters": "Mr Borges lost the decisive shield that had previously defeated the deportation decision.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "portuguese-citizenship", "label": "Status changed only in 2014", "impact": "Made it impossible, on the Court of Appeal's reading, to build ten years of Union-citizen residence by 2022."},
                {"stage_id": "ut-dismisses", "label": "UT accepted the broader counting theory", "impact": "Set up the key construction issue for the Court of Appeal."},
                {"stage_id": "ca-construction-ruling", "label": "Derivative years ruled out", "impact": "Removed enhanced protection and forced remittal."},
            ],
            "confidence": {"score": 0.94, "level": "high", "notes": ["The legal reasoning and remittal outcome are explicit; some tribunal-hearing dates are not central and are therefore generalised."]},
        },
    },
    "788.json": {
        "judges": ["Lord Justice Bean", "Lord Justice Coulson", "Lady Justice Andrews"],
        "area_of_law": ["Personal injury", "Highways liability", "Negligence"],
        "statutes_considered": [
            {"title": "Highways Act 1980", "provisions": ["sections 41, 58, 328 and 329"]},
            {"title": "Highways Act 1835", "provisions": ["section 72"]},
        ],
        "key_facts": [
            "The claimant was injured in April 2020 when his bicycle struck a concealed hole in a grass verge beside the A10 after he moved off a narrow path to overtake a jogger.",
            "The trial judge found the verge hole was a dangerous defect and caused the accident, but held the highway authority succeeded on the section 58 defence and dismissed the alternative common-law negligence claim.",
            "A central part of the authority's defence depended on a witness statement from inspector Jeff Cooke asserting a prior walked inspection, despite GPS data strongly suggesting no such inspection occurred.",
            "The Court of Appeal held the judge had mishandled the evidential significance of Cooke's statement and the contemporaneous GPS data, so the section 58 defence failed and the appeal was allowed subject to one-third contributory negligence.",
        ],
        "short_title": "Section 58 defence failed after flawed treatment of inspection evidence",
        "procedural_posture": "Appeal from dismissal of a highways defect claim after a split trial on liability and contributory negligence.",
        "outcome": "Appeal allowed; judgment entered for the claimant on section 41 subject to damages assessment and a 33% deduction for contributory negligence.",
        "ratio": "When a highway authority relies on inspection evidence to establish the section 58 defence, the court must assess contemporaneous documents first; it was wrong to treat the claimant as bound to accept an inspector's witness statement at face value where disclosed GPS data and surrounding circumstances made the alleged inspection manifestly incredible, so the statutory defence was not proved.",
        "legal_issues": [
            "Whether a grass verge beside a footway can form part of the highway in dangerous disrepair for section 41 purposes",
            "How the section 58 defence operates where inspection evidence is undermined by contemporaneous records",
            "Use of a withdrawn witness statement in cross-examination and the limits of Property Alliance principles",
            "Appropriate apportionment of contributory negligence for overtaking on the verge",
        ],
        "catchwords": ["highways liability", "section 41", "section 58 defence", "grass verge", "inspection evidence", "contributory negligence"],
        "index_terms": ["Demetrios Karpasitis", "Hertfordshire County Council", "Jeff Cooke", "A10 verge defect", "GPS tracking data"],
        "linked_authorities": ["Burnside v Emerson", "Rider v Rider", "Goodes v East Sussex County Council", "Property Alliance Group Ltd v Royal Bank of Scotland plc", "Anonima Petroli Italiana SPA v Marlucidez Armadora SA (The Filiatra Legacy)", "Jackson v Murray"],
        "confidence": {"score": 0.95, "level": "high", "notes": ["The evidential error on the section 58 defence is the clear center of gravity of the appellate judgment."]},
        "storyline": {
            "title": "The claimant overturned a highways-inspection defence",
            "summary": "Although the trial judge accepted that a large verge hole was dangerous, the claim originally failed because the council said a prior inspection had missed nothing actionable. The Court of Appeal held that the inspection evidence could not survive the contemporaneous GPS record and restored the claimant's section 41 claim, subject to contributory negligence.",
            "span": {"start": "2020-04-22", "end": "2025", "label": "April 2020 – 2025"},
            "parties": [
                {"role": "appellant", "name": "Demetrios Karpasitis", "short_name": "Mr Karpasitis"},
                {"role": "respondent", "name": "Hertfordshire County Council", "short_name": "Council"},
                {"role": "court", "name": "Court of Appeal (Civil Division)", "short_name": "Court of Appeal"},
            ],
            "stages": [
                {"id": "accident", "order": 1, "date": "2020-04-22", "date_label": "2020-04-22", "date_precision": "exact", "title": "Cyclist crashes into concealed verge hole", "category": "incident", "actor": "Mr Karpasitis", "what_happened": "While overtaking a jogger on the grass verge beside the A10 path, the claimant hit a hole and suffered a major spinal fracture.", "why_it_matters": "This was the factual basis for the section 41 and negligence claims.", "legal_hook": None},
                {"id": "site-photos", "order": 2, "date": "2020-05 to 2020-06", "date_label": "May–June 2020", "date_precision": "approximate", "title": "Hole documented and later filled in", "category": "evidence", "actor": "Claimant's side", "what_happened": "The claimant's father and highway expert photographed and measured a substantial hole; by June it had been filled.", "why_it_matters": "The defect's size and condition became central to dangerousness and timing issues.", "legal_hook": None},
                {"id": "inspection-defence", "order": 3, "date": "2022-05 to 2022-06", "date_label": "2022 disclosure and witness evidence", "date_precision": "approximate", "title": "Council relies on inspector's account", "category": "defence", "actor": "Council", "what_happened": "The council produced inspector Jeff Cooke's statement saying he had walked the route in February 2020 and would have treated a large hole urgently if present.", "why_it_matters": "This was the backbone of the section 58 defence.", "legal_hook": "Highways Act 1980 section 58"},
                {"id": "gps-disclosure", "order": 4, "date": "2022-05-18", "date_label": "2022-05-18", "date_precision": "exact", "title": "GPS vehicle data disclosed", "category": "evidence", "actor": "Council's solicitors", "what_happened": "Continuing disclosure revealed tracking data indicating Cooke's vehicle only stopped briefly on the day of the alleged walk-through.", "why_it_matters": "The data strongly suggested no meaningful walked inspection happened.", "legal_hook": None},
                {"id": "trial-twist", "order": 5, "date": "2023-03", "date_label": "March 2023 trial", "date_precision": "approximate", "title": "Cooke not called and statement handling becomes contentious", "category": "trial", "actor": "Both parties", "what_happened": "The council withdrew reliance on Cooke's statement after another witness had already said Cooke would only have categorised the defect as non-urgent, leading to argument over how the statement could be used.", "why_it_matters": "The trial judge's evidential approach later became the decisive appellate error.", "legal_hook": None},
                {"id": "trial-loss", "order": 6, "date": "2023-10-20", "date_label": "2023-10-20", "date_precision": "exact", "title": "Claim dismissed despite dangerous defect finding", "category": "decision", "actor": "Deputy High Court Judge", "what_happened": "The judge held the hole was dangerous and causative but accepted the section 58 defence and rejected the common-law claim.", "why_it_matters": "The result turned almost entirely on the supposed prior inspection.", "legal_hook": None},
                {"id": "evidential-correction", "order": 7, "date": None, "date_label": "Court of Appeal reasoning", "date_precision": "unknown", "title": "Court of Appeal restores primacy of contemporaneous documents", "category": "decision", "actor": "Court of Appeal", "what_happened": "Bean LJ held that the GPS document, solicitor email and surrounding evidence made the alleged walked inspection manifestly incredible and that the judge had approached the evidence in the wrong order.", "why_it_matters": "Without a real inspection the statutory defence collapsed.", "legal_hook": None},
                {"id": "appeal-allowed", "order": 8, "date": None, "date_label": "Appeal allowed", "date_precision": "unknown", "title": "Section 41 claim succeeds with one-third deduction", "category": "outcome", "actor": "Court of Appeal", "what_happened": "The appeal was allowed, judgment entered for the claimant and damages left to be assessed with 33% contributory negligence.", "why_it_matters": "The claimant regained a valuable liability judgment after losing at trial.", "legal_hook": None},
            ],
            "turning_points": [
                {"stage_id": "gps-disclosure", "label": "Contemporaneous tracking contradicted the inspection story", "impact": "Changed the section 58 issue from one of weight to one of credibility."},
                {"stage_id": "trial-loss", "label": "Danger conceded but defence accepted", "impact": "Made the appeal focus tightly on the inspection evidence and procedural fairness."},
                {"stage_id": "appeal-allowed", "label": "Defence fell apart", "impact": "Converted a total defence win into liability for damages subject to contributory negligence."},
            ],
            "confidence": {"score": 0.94, "level": "high", "notes": ["The appellate reasoning on evidence is unusually explicit and well-supported by the record."]},
        },
    },
}


def apply_one(filename: str, enrichment: dict) -> dict:
    path = DATA / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    if "judges" in enrichment:
        data["judges"] = enrichment["judges"]
    base = {k: v for k, v in data.items() if k not in ENRICHMENT_FIELDS}
    new_data: dict = {}
    inserted = False
    for key, value in base.items():
        if not inserted and key == "full_text":
            for field in ENRICHMENT_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True
        new_data[key] = value
        if not inserted and key == "summary":
            for field in ENRICHMENT_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True
    if not inserted:
        for field in ENRICHMENT_FIELDS:
            new_data[field] = enrichment[field]
    path.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))
    return data


def enrichment_record(filename: str, enrichment: dict, original: dict, notes: str) -> dict:
    return {
        "source_path": f"data/judgments/ewca/civ/2025/{filename}",
        "tna_uri": original.get("tna_uri"),
        "neutral_citation": original.get("neutral_citation"),
        "status": "done",
        "enriched_fields": ENRICHMENT_FIELDS,
        "enriched_at": BATCH_DATE,
        "notes": notes,
        "enrichment": {f: enrichment[f] for f in ENRICHMENT_FIELDS},
    }


def storyline_record(filename: str, enrichment: dict, original: dict, notes: str) -> dict:
    return {
        "source_path": f"data/judgments/ewca/civ/2025/{filename}",
        "tna_uri": original.get("tna_uri"),
        "neutral_citation": original.get("neutral_citation"),
        "status": "done",
        "stage_count": len(enrichment["storyline"]["stages"]),
        "storylined_at": BATCH_DATE,
        "notes": notes,
        "storyline": enrichment["storyline"],
    }


def update_manifest(manifest_path: Path, record: dict) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.setdefault("records", [])
    records[:] = [r for r in records if r.get("source_path") != record["source_path"]]
    records.append(record)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    enrichment_records = []
    storyline_records = []
    for filename, enrichment in ENRICHMENTS.items():
        original = apply_one(filename, enrichment)
        notes = f"Batch {BATCH_NUMBER} manual enrichment — {original.get('case_name', filename)}"
        enrichment_records.append(enrichment_record(filename, enrichment, original, notes))
        storyline_records.append(storyline_record(filename, enrichment, original, notes))
        update_manifest(
            ROOT / "enrichment_manifest.json",
            {
                "source_path": f"data/judgments/ewca/civ/2025/{filename}",
                "tna_uri": original.get("tna_uri"),
                "neutral_citation": original.get("neutral_citation"),
                "status": "done",
                "enriched_fields": ENRICHMENT_FIELDS,
                "enriched_at": BATCH_DATE,
                "notes": notes,
            },
        )
        update_manifest(
            ROOT / "storyline_manifest.json",
            {
                "source_path": f"data/judgments/ewca/civ/2025/{filename}",
                "tna_uri": original.get("tna_uri"),
                "neutral_citation": original.get("neutral_citation"),
                "status": "done",
                "stage_count": len(enrichment["storyline"]["stages"]),
                "storylined_at": BATCH_DATE,
                "notes": notes,
            },
        )
        print(f"Applied: {filename}")
    batch_doc = {
        "batch_number": BATCH_NUMBER,
        "batch_date": BATCH_DATE,
        "notes": BATCH_NOTES,
        "enrichment_records": enrichment_records,
        "storyline_records": storyline_records,
    }
    BATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_PATH.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for filename in ENRICHMENTS:
        subprocess.run([sys.executable, "-m", "json.tool", str(DATA / filename)], check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "json.tool", str(BATCH_PATH)], check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "json.tool", str(ROOT / "enrichment_manifest.json")], check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "json.tool", str(ROOT / "storyline_manifest.json")], check=True, capture_output=True)
    print(f"Wrote batch file: {BATCH_PATH}")
    print(f"Validated {len(ENRICHMENTS)} judgments plus batch and manifests")


if __name__ == "__main__":
    main()
