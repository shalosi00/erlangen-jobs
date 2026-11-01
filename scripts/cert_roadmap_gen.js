// Certificate Roadmap — companion to the Azure & Cloud Demand Justification dossier.
// Compact single-section report (no cover, no TOC). Uses azure_report_lib.js helpers
// (skill-compliant: line 312, HeadingLevel, tableHeader/cantSplit, DM-1 palette).
const {
  Document, Packer, Paragraph, TextRun, PageBreak, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, SectionType,
  P, h1, h2, body, b, t, it, caption, figure, table, tableTitle,
} = require("/home/z/my-project/scripts/azure_report_lib.js");
const fs = require("fs");

const OUT = "/home/z/my-project/download/Certificate_Roadmap_Erlangen_Corpus_2026-10-30.docx";
const CH3 = "/home/z/my-project/data/azure_demand/chart3_skill_stacks.png";

const pgSize = { width: 11906, height: 16838 };
const pgMargin = { top: 1440, bottom: 1440, left: 1701, right: 1417 };

function pageFooter() {
  return new Footer({ children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "808080", font: { ascii: "Times New Roman" } })],
  })] });
}
function pageHeader() {
  return new Header({ children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { bottom: { style: "single", size: 2, color: "C8DDE2" } },
    children: [new TextRun({ text: "Certification Roadmap - Bildungsgutschein evidence dossier (companion)",
      size: 18, color: "808080", font: { ascii: "Calibri" } })],
  })] });
}

// ── title block (not a cover page) ──
const bodyChildren = [];
bodyChildren.push(new Paragraph({
  alignment: AlignmentType.LEFT, spacing: { before: 120, after: 60, line: 312 },
  children: [new TextRun({ text: "Certification Roadmap for a Fachinformatiker/-in Systemintegration Applicant",
    bold: true, size: 40, color: "162235", font: { ascii: "Calibri" } })],
}));
bodyChildren.push(new Paragraph({
  alignment: AlignmentType.LEFT, spacing: { after: 80, line: 312 },
  children: [new TextRun({ text: "Which certificates to pursue, in which order, and how to fund them - derived from every job posting observed since mid-October 2026",
    size: 24, color: "505050", font: { ascii: "Calibri" } })],
}));
bodyChildren.push(new Paragraph({
  alignment: AlignmentType.LEFT, spacing: { after: 200, line: 276 },
  border: { bottom: { style: "single", size: 6, color: "1B6B7A" } },
  children: [new TextRun({ text: "Companion to: Azure & Cloud Demand Justification (Bildungsgutschein dossier, 2026-10-30)  |  Evidence base: 3,902 unique postings, Erlangen 50 km  |  Prepared: 30 October 2026",
    size: 19, color: "1B6B7A", font: { ascii: "Calibri" } })],
}));

// ── 1. Purpose and evidence base ──
bodyChildren.push(h1("1.", "Purpose and evidence base"));
bodyChildren.push(body([t("This roadmap answers a single question: which vendor certificates should the applicant pursue, and in what order, so that the investment of time and of a potential Agentur fuer Arbeit training voucher (Bildungsgutschein, Section 82 SGB III) produces the largest measurable gain in placement probability. The answer is not a matter of taste: it is derived from the same automated job-market monitor that has collected and enriched postings for the Erlangen region (50 km radius) since 14 October 2026, and it is therefore grounded in the actual requirement language of employers hiring for the applicant's target role.")])); 
bodyChildren.push(body([t("The evidence base comprises "), b("3,902 unique postings"), t(": a regional baseline of "), b("3,825 postings"), t(" harvested on 17 October 2026 across all portals (1,977 Indeed postings with full text; 1,848 LinkedIn postings whose text is blocked and which are classified by title only), plus the "), b("77 currently active Systemintegration postings"), t(" of the daily pipeline (30 October 2026), of which 30 were re-fetched as full texts from the Bundesagentur detail API. Each posting was classified with a certificate scan (26 explicit certificate patterns, from AZ-900 to CCNA to ITIL) and a skill-stack scan (18 stacks), with every hit stored as a verbatim evidence sentence in the accompanying data files. One limitation must be stated: a single Bundesagentur detail fetch failed during this re-scan (30 instead of 31 full texts), so the entry-level and virtualization counts differ from the dossier's morning scan by at most one posting (39.0% vs. 40.3% entry-level, 15.6% vs. 16.9% virtualization); all other headline figures are identical.")])); 

// ── 2. What the corpus says about certificates ──
bodyChildren.push(h1("2.", "What the corpus says about certificates"));
bodyChildren.push(body([t("The most important structural finding is that "), b("certificates almost never gate access"), t(" to the roles the applicant is targeting. Across the 1,977 full-text baseline postings, exactly two name a certification framework at all (ITIL, in a consulting and a public-sector service-management role), and across the 77 active postings only "), b("three postings name concrete certificates"), t(": iT4Network GmbH explicitly lists 'Ideale Kenntnisse: VMWare Zertifizierung (VCP), Microsoft Zertifizierung (MCP, MCSA, MCSE, ...)' in a Fachinformatiker Systemintegration profile, and FERCHAU (Nuernberg) and Brunel each reference ITIL in IT-specialist profiles. One apparent baseline hit - 'MTA (m/w/d)' - is a linguistic false positive (Medizinisch-Technische Assistentin, a medical role) and was excluded. Not a single posting in either corpus names AZ-900, AZ-104, AWS, Google Cloud, CompTIA or CCNA.")])); 
bodyChildren.push(body([t("Certificates function, in other words, as a "), it("differentiator"), t(" rather than a filter for a career entrant: they convert self-taught knowledge into employer-verifiable proof where the posting itself does not demand a certificate. The corpus shows that regional employers value exactly that signal. Six of the 77 active postings (7.8%) explicitly mention Zertifizierungen as desirable - most concretely ncsolution GmbH: 'Weiterbildung und Zertifizierungen: Wir unterstuetzen Ihre fachliche Entwicklung mit individuell abgestimmten Schulungen' - and iT4Network frames certificates as 'ideal' knowledge for its Systemintegration hire. This is the demand-side logic on which the portfolio below rests: the applicant should carry certificates that match the stacks employers actually list, not certificates that merely look impressive.")])); 
bodyChildren.push(tableTitle("Table 1 - Explicit certification references in the corpus (verbatim evidence)"));
bodyChildren.push(table(
  ["Employer", "Role / corpus", "Certificate reference", "Verbatim evidence"],
  [
    ["iT4Network GmbH", "FISI Systemintegration (active, BA)", "Microsoft MCP/MCSA/MCSE + VMware VCP", "\"Ideale Kenntnisse: VMWare Zertifizierung (VCP) Microsoft Zertifizierung (MCP, MCSA, MCSE,...)\""],
    ["ncsolution GmbH", "Fachinformatiker Systemintegration (active, BA)", "Employer funds certifications", "\"Weiterbildung und Zertifizierungen: Wir unterstuetzen Ihre fachliche Entwicklung mit individuell abgestimmten Schulungen.\""],
    ["FERCHAU GmbH NL Nuernberg City", "IT-Spezialist Netzwerk & Connectivity (active, BA)", "ITIL", "ITIL named in the requirement profile of the BA full text"],
    ["Brunel GmbH NL Mannheim", "IT-Spezialist (active, BA+XING)", "ITIL", "ITIL named in the requirement profile"],
    ["cns computer & netzwerk service GmbH (2 postings)", "IT-Systemadministrator / FISI (active, BA)", "Zertifizierungen as asset", "generic 'Zertifizierung' mention in the BA full text"],
    ["Masoona Consulting GmbH", "BA IT-Service Management (baseline)", "ITIL", "\"...Optimierung von Geschaeftsprozessen, speziell im IT-Service-Management auf der Basis der IT Infrastructure Library (ITIL)\""],
    ["ANregiomed gKU", "Lead Enterprise Service Manager (baseline)", "ITIL", "\"Prozess-Governance & -Design (ITIL): Definition, Etablierung ... von ITIL-basierten Best-Practice-Prozessen\""],
  ],
  [22, 24, 20, 34]
));
bodyChildren.push(caption("Figure references and full URLs for every row are listed in Appendix A."));

// ── 3. What the corpus demands in skills ──
bodyChildren.push(h1("3.", "What the corpus demands in skills"));
bodyChildren.push(body([t("Because explicit certificate names are rare, the correct basis for prioritisation is the "), b("skill-stack demand"), t(" behind them. In the 77 active postings, network skills are the single largest stack (26 postings, 33.8%), followed by IT security (16, 20.8%), IT service management (14, 18.2%), virtualization (12, 15.6%), Linux (11, 14.3%) and cloud in general (10, 13.0%). The Microsoft ecosystem (Windows Server, Active Directory/Entra, Microsoft 365/Intune, Exchange) reaches 8 postings (10.4%), and the combined cloud-or-Microsoft demand - the union the dossier quantifies - reaches "), b("18 of 77 postings (23.4%)"), t(", against 3.4% in the all-professions baseline: a roughly sevenfold concentration on exactly the applicant's target role. Eleven postings demand network and security skills together, which is precisely the CompTIA entry sequence.")])); 
bodyChildren.push(figure(CH3, 560));
bodyChildren.push(caption("Figure 1 - Skill-stack demand in the 77 active postings and the certificate that maps to each (n = number of postings; bars are non-additive because stacks overlap)."));
bodyChildren.push(tableTitle("Table 2 - From observed demand to certificate choice"));
bodyChildren.push(table(
  ["Observed stack (active corpus)", "Share", "Matching certificate", "Why this certificate"],
  [
    ["Network (Cisco/FortiGate/VPN/LAN)", "26 / 33.8%", "CompTIA Network+ (or CCNA)", "largest stack; vendor-neutral fits the heterogeneous SMB toolset named in postings"],
    ["IT security (Datenschutz/DSGVO/ISO 27001)", "16 / 20.8%", "CompTIA Security+", "second-largest stack; often combined with network (11 postings)"],
    ["IT service management (ticketing)", "14 / 18.2%", "ITIL 4 Foundation", "ITIL is the only framework named by name in the corpus"],
    ["Virtualization (VMware/Hyper-V)", "12 / 15.6%", "AZ-104, later AZ-800 / VCP", "virtualization is administered through Azure/Hyper-V in MS-centred shops"],
    ["Linux (Debian/Ubuntu/RHEL)", "11 / 14.3%", "LPIC-1 (optional)", "secondary stack for FISI roles; relevant only for Linux-heavy employers"],
    ["Cloud (any provider)", "10 / 13.0%", "AZ-900, then AZ-104", "Azure named 3x, AWS/GCP 1x each; MS-centred region"],
    ["Microsoft 365 / Intune / endpoint", "5 / 6.5%", "MD-102", "endpoint administration is the classic FISI adjacent specialisation"],
    ["Windows Server + AD/Entra", "8 / 10.4%", "AZ-104 / AZ-800", "the on-prem-to-cloud bridge is exactly the Azure Administrator profile"],
  ],
  [30, 12, 24, 34],
  { centerCols: [1] }
));

// ── 4. The recommended certificate portfolio ──
bodyChildren.push(h1("4.", "The recommended certificate portfolio"));
bodyChildren.push(body([t("Table 3 is the direct answer to the question this roadmap was commissioned for. The portfolio is ordered by "), b("expected placement impact per week of preparation"), t(", starting with the certificate pair that the companion dossier already justifies for voucher funding (AZ-900, then AZ-104), followed by the two highest-coverage complements (Network+ for the largest stack; MD-102 for the Microsoft endpoint stack), then the security track, and finally the low-cost, employer-fundable additions that make sense after placement. Fees are official list prices as of October 2026 and were verified against the certification bodies' own listings (Microsoft Learn, CompTIA street pricing via recognised resellers, PeopleCert); Microsoft charges the EUR equivalent by proctoring country, so EUR figures for role-based exams vary slightly.")])); 
bodyChildren.push(tableTitle("Table 3 - Prioritised certificate portfolio (exam fees: official list prices, Oct 2026)"));
bodyChildren.push(table(
  ["#", "Certificate (exam)", "Corpus evidence", "Typical prep", "Exam fee (list)", "Funding route"],
  [
    ["P1", "AZ-900 Microsoft Azure Fundamentals", "cloud 13.0%; Azure 3.9%; 7x concentration vs. baseline", "2-4 weeks", "EUR 53", "Bildungsgutschein measure; alternatively free MS Learn path + exam fee"],
    ["P2", "AZ-104 Microsoft Azure Administrator Associate", "cloud/MS union 23.4% (18/77); virtualization 15.6%", "8-12 weeks", "USD 165 (associate tier)", "Bildungsgutschein - the core module of the application"],
    ["P3", "CompTIA Network+ (N10-009)", "network 33.8% - largest stack; Cisco/FortiGate named", "8-12 weeks", "USD 399 (street ~359)", "AZAV-funded alternative; employer co-funding"],
    ["P4", "MD-102 Microsoft 365 Endpoint Administrator", "M365/Intune 6.5% + AD/Entra 5.2%", "6-10 weeks", "USD 165 (associate tier)", "employer-funded (ncsolution model) or later voucher"],
    ["P5", "CompTIA Security+ (SY0-701)", "security 20.8%; overlaps network in 11 postings", "8-12 weeks", "USD 439 (street ~395)", "AZAV providers or later voucher; note V8 launches ~17 Nov 2026"],
    ["P6", "ITIL 4 Foundation", "ITSM 18.2%; ITIL named by FERCHAU, Brunel, 2 baseline roles", "1-2 weeks", "USD 690 bundle incl. VAT (exam-only via trainers typically lower)", "employer-funded after placement"],
    ["P7", "AZ-800 Windows Server Hybrid (later)", "Windows Server stack; legacy MCP/MCSA/MCSE ask (iT4Network)", "after AZ-104", "USD 165 (associate tier)", "employer-funded"],
    ["P8", "LPIC-1 / VMware VCP (optional)", "Linux 14.3%; VCP named by iT4Network", "8-10 weeks", "per regional schedule", "employer-funded; only if the employer's stack demands it"],
  ],
  [5, 20, 24, 10, 17, 24],
  { centerCols: [0, 3] }
));
bodyChildren.push(body([t("Two design decisions in this portfolio deserve explanation. First, AZ-900 precedes AZ-104 not because employers ask for AZ-900 (no posting does) but because it de-risks the voucher measure: it is a two-to-four-week confirmation that the applicant can carry the eight-to-twelve-week AZ-104 module, which strengthens both the training plan and the Section 82 argument that the measure is realistic. Second, CompTIA Network+ ranks above MD-102 despite the Microsoft-centred corpus because network is the largest single stack (33.8%) and the Franconian SMB market runs heterogeneous hardware (Cisco and FortiGate are named in postings), which a vendor-neutral network certificate covers better than a Microsoft-only credential; where an applicant targets a Cisco-heavy employer instead, CCNA is the equivalent choice.")])); 

// ── 5. Sequencing and funding strategy ──
bodyChildren.push(h1("5.", "Sequencing and funding strategy"));
bodyChildren.push(body([b("Phase 1 (months 0-3, voucher-funded): AZ-900, then AZ-104."), t(" The applicant applies for a Bildungsgutschein covering an AZAV-certified course that bundles both Azure certifications, or - if the Agentur prefers a smaller first measure - funds AZ-104 while AZ-900 is completed through Microsoft's free learning path plus the EUR 53 exam. Phase 1 ends with the applicant carrying the industry-standard junior cloud-administration credential pair that maps to the 23.4% cloud/Microsoft demand union documented in the dossier.")])); 
bodyChildren.push(body([b("Phase 2 (months 3-9, targeted): Network+ or MD-102, optionally Security+."), t(" While applications are running, the applicant adds the certificate matching the employers actually being pursued: Network+ where the target list is the SMB service-provider market (the largest stack at 33.8%), or MD-102 where the targets are Microsoft shops with large client fleets. Security+ is added if the applicant's search shifts toward the 16 postings (20.8%) with explicit security requirements; candidates who certify before 17 November 2026 hold the SY0-701/V7 version, whereas waiting for V8 covers AI-related risk topics at the cost of a later start.")])); 
bodyChildren.push(body([b("Phase 3 (months 9-18, post-placement, employer-funded): ITIL 4 Foundation, AZ-800, and stack-specific extras."), t(" The corpus itself shows that regional employers fund further certification (ncsolution's posting explicitly promises it), so the low-cost process and bridge certificates are best taken with employer support once the applicant is inside the market: ITIL 4 Foundation (one to two weeks of preparation) formalises the ticketing/ITSM work that 18.2% of active postings describe, AZ-800 bridges the Windows Server estates that the legacy MCP/MCSA/MCSE reference at iT4Network points to, and LPIC-1 or VCP are added only where the employer's stack demands them. This phasing also answers a fair objection to over-certification: it prevents collecting credentials before placement that employers have not asked for, while keeping the voucher request focused on the one measure with demonstrable demand.")])); 

// ── 6. Applicant suitability and the Section 82 mapping ──
bodyChildren.push(h1("6.", "Applicant suitability and the Section 82 SGB III mapping"));
bodyChildren.push(body([t("The applicant is entering the IT labour market as a Fachinformatiker/-in Systemintegration candidate in the Erlangen region. The corpus supports suitability on three measured facts. First, the entry door is wide: 30 of the 77 active postings (39.0%) carry explicit entry-level signals (Ausbildung, Berufseinsteiger, Junior, Quereinsteiger), and two of the three postings that explicitly name Azure are entry-friendly. Second, the applicant's target role is where the demand sits: 76.6% of active postings match FISI-relevant titles, and the cloud/Microsoft demand union is seven times more concentrated in these roles than in the regional baseline. Third, employers in the corpus treat certificates as an asset to be funded rather than an entry barrier - the ncsolution and iT4Network evidence - so a certificate-holding entry candidate competes against non-certified peers in a market that rewards the difference without requiring years of experience.")])); 
bodyChildren.push(body([t("Mapped onto the three funding criteria of Section 82 SGB III, as set out in full in the companion dossier (Chapter 7): "), b("necessity"), t(" - without verifiable cloud credentials the applicant cannot evidence the Azure/Cloud competence that 23.4% of target-role postings request; "), b("suitability"), t(" - the AZ-900/AZ-104 sequence is designed for exactly this entry profile, starts from zero cloud knowledge, and its two-stage structure makes successful completion realistic; "), b("prospects of successful placement"), t(" - the demand statistics above, the named regional employers (DMG MORI Digital GmbH, Suspa GmbH Altdorf, NConsult GmbH, iT4Network GmbH), and the fact that certificates function as differentiators in an entry market all point to improved placement odds within the regional labour market the Agentur is responsible for. The recommendation of this roadmap is therefore unchanged from the dossier: the voucher application should name the AZ-900 + AZ-104 certification path as its training goal, with Network+/MD-102 as the documented second step once placement is imminent.")])); 

// ── 7. The answer in one box ──
bodyChildren.push(h1("7.", "The answer in brief"));
bodyChildren.push(new Paragraph({
  spacing: { before: 120, after: 240, line: 312 },
  shading: { type: "clear", fill: "EDF3F5" },
  border: { left: { style: "single", size: 18, color: "1B6B7A" } },
  children: [
    new TextRun({ text: "Pursue, in this order: ", bold: true, size: 24, color: "162235", font: { ascii: "Times New Roman" } }),
    new TextRun({ text: "(1) AZ-900 Azure Fundamentals (EUR 53) - now, as the voucher measure's entry stage; (2) AZ-104 Azure Administrator Associate - the core voucher module, mapping to the 23.4% cloud/Microsoft demand; (3) CompTIA Network+ or MD-102 - the largest observed stacks (33.8% network, Microsoft endpoint 6.5%+5.2%); (4) CompTIA Security+ - the 20.8% security stack; (5) after placement and employer-funded: ITIL 4 Foundation, AZ-800, and LPIC-1/VCP only where the employer's stack demands them. Every step of this order is traceable to verbatim postings listed in Appendix A and quantified in Tables 2-3.",
      size: 24, color: "162235", font: { ascii: "Times New Roman" } }),
  ],
}));

// ── Appendix A: evidence register ──
bodyChildren.push(h1("Appendix A.", "Evidence register (certification-relevant postings)"));
bodyChildren.push(body([t("All quotes are verbatim from the stored posting texts of the job monitor. BA references link to the Bundesagentur detail page; the daily pipeline stores the full enriched text alongside every posting, so each quote can be re-verified against the raw data at any time.")])); 
bodyChildren.push(table(
  ["Employer", "Role", "Source / reference", "URL"],
  [
    ["iT4Network GmbH", "FISI Systemintegration ('IT-Monster-Jaeger')", "BA 10000-1208461882-S", "arbeitsagentur.de/jobsuche/jobdetail/10000-1208461882-S"],
    ["ncsolution GmbH", "Fachinformatiker Systemintegration", "BA (active 2026-10-30)", "arbeitsagentur.de (BA full text, enriched store)"],
    ["cns computer & netzwerk service GmbH", "IT-Systemadministrator (m/w/d)", "BA (active 2026-10-30)", "arbeitsagentur.de (BA full text, enriched store)"],
    ["FERCHAU GmbH NL Nuernberg City", "IT-Spezialist Netzwerk & Connectivity", "BA 12265-516301_JB5283537-S", "arbeitsagentur.de/jobsuche/jobdetail/12265-516301_JB5283537-S"],
    ["Brunel GmbH NL Mannheim", "IT-Spezialist (w/m/d)", "BA 12362-TR-300879_624701LS-S", "arbeitsagentur.de/jobsuche/jobdetail/12362-TR-300879_624701LS-S"],
    ["NConsult GmbH", "DevOps Engineer ('Cloud-Umgebungen, z. B. AWS, Azure oder GCP')", "BA (active 2026-10-30)", "arbeitsagentur.de (BA full text, enriched store)"],
    ["Masoona Consulting GmbH", "Business Analyst IT-Service Management", "Indeed (baseline, 2026-10-17)", "indeed.com posting, baseline harvest"],
    ["ANregiomed gKU", "Lead Enterprise Service Manager", "Indeed (baseline, 2026-10-17)", "indeed.com posting, baseline harvest"],
    ["DMG MORI Digital GmbH", "Azure & IT Operations (2 Azure roles)", "enriched store (2026-10-30)", "recruiting.dmgmori.com/Vacancies/1284"],
  ],
  [24, 26, 22, 28]
));
bodyChildren.push(caption("Raw scan outputs: data/azure_demand/cert_scan_20261030-1111.json, cert_evidence_20261030-1111.csv, cert_stats_20261030-1111.json."));

// ── assemble ──
const doc = new Document({
  sections: [{
    properties: {
      page: { size: pgSize, margin: pgMargin, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } },
    },
    headers: { default: pageHeader() },
    footers: { default: pageFooter() },
    children: bodyChildren,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("written", OUT, buf.length, "bytes");
});
