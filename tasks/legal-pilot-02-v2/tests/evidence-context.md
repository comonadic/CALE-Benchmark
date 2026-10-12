Judge-only evidence index; original input remains authoritative.
{
  "version": 2,
  "source_document_id": "L007",
  "original_sha256": "4a8fe6fa519e3d8663aa72d70ce5ccd15f85368fcf181f823326a1fa57739507",
  "locator_convention": "PDF physical pages 1-based; printed p=physical-7 in main rules; verify headings where page spans",
  "fact_role_policy": "procedural chronology and conditional schedule are provided; client assertions are not findings",
  "facts_visible_in": [
    "scenario.md",
    "notice.md",
    "delivery-log.csv",
    "client-email.md",
    "future-events.md",
    "events.json"
  ],
  "evidence": [
    {
      "id": "R01",
      "rule": "8(1)-(5)",
      "pages": [
        16,
        17
      ],
      "role": "institution rule",
      "finding": "designated electronic address permissible; next day start",
      "facts": [
        "N02",
        "D01",
        "E01"
      ],
      "derivation": "notice effective receipt 2025-03-28; internal reading and paper copy do not reset clock under explicit receipt fact"
    },
    {
      "id": "R02",
      "rule": "68,71,75; contrast 15-16",
      "pages": [
        20,
        21,
        22,
        48,
        49,
        50
      ],
      "role": "institution rule",
      "finding": "domestic ordinary response and counterclaim20 days; claimant reply20days",
      "derivation": "E01+20=2025-04-17; F08+20=2025-05-11; extension authority changes on tribunal constitution"
    },
    {
      "id": "R03",
      "rule": "25-28,70",
      "pages": [
        27,
        28,
        29,
        48
      ],
      "role": "institution rule",
      "finding": "three-member default,15days both own member and common presiding member",
      "derivation": "E01+15=2025-04-12; conservative consecutive-day control dates; confirm actual filing arrangements with institution"
    },
    {
      "id": "R04",
      "rule": "6(4)-(5),10",
      "pages": [
        15,
        16,
        18
      ],
      "role": "institution rule",
      "finding": "written jurisdiction objection before first hearing or first substantive response if written-only; continues proceedings",
      "derivation": "A05 event boundary2025-05-22 09:00; A06 mutual-exclusive boundary2025-04-10 10:00; internal submission target earlier is recommendation"
    },
    {
      "id": "R05",
      "rule": "32(1)-(3)",
      "pages": [
        31
      ],
      "role": "institution rule",
      "finding": "disclosed matter10days vs general known grounds15days; applicable limitation must not be replaced",
      "derivation": "F02+10=2025-05-05; F01+15=2025-05-10; A08 general date does not extend A07 disclosed-matter limit"
    },
    {
      "id": "R06",
      "rule": "72(1)-(3); compare37,64",
      "pages": [
        34,
        47,
        49
      ],
      "role": "institution rule",
      "finding": "domestic firsthearing15days advance; postpone requestwithin3daysreceipt; later hearings excluded",
      "derivation": "F04-15=2025-05-07; May09->May22=13days, short2days; F03+3=2025-05-12; no automatic postponement"
    },
    {
      "id": "R07",
      "rule": "74(1)-(3),65(1)-(3)",
      "pages": [
        47,
        49,
        50
      ],
      "role": "institution rule",
      "finding": "domestic ordinary4months; summary3months, extension and suspension qualifications",
      "derivation": "EDATE(2025-04-25,4)=2025-08-25; EDATE(...,3)=2025-07-25, date convention is explicit scenario assumption"
    },
    {
      "id": "R08",
      "rule": "59,61-62,66-68",
      "pages": [
        45,
        46,
        47,
        48
      ],
      "role": "institution rule",
      "finding": "6.4m >5m can summary with request+otherparty written consent or agreed summary; requestalone not enough; summaryamountincrease not automatic conversion",
      "derivation": "base domestic ordinary remains; if summary consent coordinate schedule/sole arbitrator/no invented reset; summary->ordinary special continuity rule is not reciprocal automatic rule"
    },
    {
      "id": "R09",
      "rule": "56-57",
      "pages": [
        44,
        45
      ],
      "role": "institution rule",
      "finding": "correction limited clerical/calculation/analogous errors; supplement omitted claim/counterclaim; party30days, tribunal30daysifgroundexists",
      "derivation": "F06+30=2025-10-09; F07+30=2025-10-31; no guaranteed error/omission or merits appeal"
    },
    {
      "id": "R10",
      "rule": "16(2)-(3),20-21,41; domestic71",
      "pages": [
        21,
        22,
        25,
        36,
        48,
        49
      ],
      "role": "institution rule",
      "finding": "counterclaim specifics facts reasons evidence, fee at notified time; no payment treat notsubmitted",
      "derivation": "F09 deadlineunknown staysblank; gather project records, authorization, filing copies/electronic compliance; see clientC02"
    },
    {
      "id": "R11",
      "rule": "88",
      "pages": [
        54
      ],
      "role": "institution rule",
      "finding": "2024-01-01 effective; earlieracceptedcase uses priorrules unlessjointagreement",
      "derivation": "caseaccepted2025-03-26; tasklocked2024version"
    }
  ],
  "calculations_are_author_reference": "not solver rollout"
}
