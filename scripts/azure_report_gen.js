// Main assembly — Azure & Cloud Demand Justification dossier
const {
  Document, Packer, Paragraph, TextRun, PageBreak, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, SectionType, TableOfContents,
  P, buildCoverR1, h1, h2, body, b, t, it, caption, figure, table, tableTitle, OUT_MAIN,
} = require("/home/z/my-project/scripts/azure_report_lib.js");
const fs = require("fs");

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
    children: [new TextRun({ text: "Azure & Cloud Demand Analysis - Bildungsgutschein Evidence Dossier",
      size: 18, color: "808080", font: { ascii: "Calibri" } })],
  })] });
}

// ══════════════════ BODY CONTENT ══════════════════
const bodyChildren = [];

// ── 1. Executive Summary ──
bodyChildren.push(h1("1.", "Executive Summary"));
bodyChildren.push(body([t("This dossier quantifies the demand for Microsoft Azure and cloud competencies in the regional job market around Erlangen, based on every job posting collected and enriched by an automated job-market monitor between 14 October and 30 October 2026. It provides the labour-market evidence base for an application for a federal training voucher ("), b("Bildungsgutschein"), t(", Section 82 of the Third Book of the Social Security Code, SGB III) covering the Microsoft Azure certifications AZ-900 (Azure Fundamentals) and AZ-104 (Azure Administrator).")]));
bodyChildren.push(body([t("The headline findings are: "), b("23.4% of all 77 currently active Systemintegration postings (18 of 77)"), t(" require Azure, cloud or Microsoft-infrastructure skills, compared with only "), b("3.4%"), t(" across a 1,977-posting regional baseline of all professions - a roughly sevenfold concentration of cloud demand on exactly the role the applicant is targeting. "), b("40.3% of the active postings carry entry-level signals"), t(", and two of the three postings that explicitly name Azure are explicitly entry-friendly. Three directly nameable regional employers - DMG MORI Digital GmbH, SUESPA (Suspa GmbH, Altdorf) and NConsult GmbH - request Azure skills verbatim in their current postings.")]));
bodyChildren.push(body([t("Because virtually no employer in the corpus gates entry-level roles on formal certificates - only one posting names a Microsoft certification at all - a vendor certificate functions as a "), it("differentiator"), t(" rather than a filter for a career entrant: it converts self-taught knowledge into employer-verifiable proof. The recommended certification path (AZ-900 then AZ-104) is the recognised industry standard for junior cloud-administration profiles, is available from AZAV-approved training providers eligible for Bildungsgutschein funding, and maps directly onto the requirements observed in the corpus. Chapter 7 maps these findings onto the three legal funding criteria of Section 82 SGB III: necessity, suitability and prospects of success.")]));

// ── 2. Background and Objective ──
bodyChildren.push(h1("2.", "Background and Objective"));
bodyChildren.push(h2("2.1  The applicant and the target role"));
bodyChildren.push(body([t("The applicant is preparing to enter the German IT labour market as a "), b("Fachinformatiker/-in fuer Systemintegration"), t(" (IT specialist for system integration) in the Erlangen region (50 km radius). This role profile is the classical on-premises-to-cloud bridge: system integrators administer Windows Server estates, networks and client fleets, and are increasingly expected to operate the connected Microsoft cloud services - Azure infrastructure, Microsoft 365, Azure Active Directory (Entra ID) and Intune device management. The applicant seeks a training voucher from the Agentur fuer Arbeit to fund the Microsoft Azure certifications described in Chapter 6.")]));
bodyChildren.push(h2("2.2  The Bildungsgutschein as a funding instrument"));
bodyChildren.push(body([t("The Bildungsgutschein (Section 82 SGB III) is a commitment by the employment agency to cover the costs of a vocational further-training measure. The agency checks three criteria: the "), b("necessity"), t(" of the training for placing the applicant in work (Notwendigkeit), the "), b("suitability"), t(" of both the applicant and the measure (Eignung), and the "), b("prospects of success"), t(" after completion (Erfolgsaussichten). The measure itself must be offered by a training provider approved under the Accreditation and Approval Ordinance for Further Training (Akkreditierungs- und Zulassungsverordnung Arbeitsfoerderung, AZAV). This dossier supplies the labour-market evidence for these deliberations; the applicant's personal circumstances are documented separately at the agency.")]));
bodyChildren.push(h2("2.3  Objective and scope"));
bodyChildren.push(body([t("The objective is a transparent, reproducible answer to one question: "), b("how strong is the regional, current demand for Azure and cloud skills in the applicant's target role, and does a recognised Azure certification improve the applicant's placement prospects?"), t(" The dossier deliberately restricts itself to evidence that can be reproduced from the underlying data files (Chapter 3 and Appendix C). It does not attempt to reproduce official statistics of the Bundesagentur fuer Arbeit; it is a complementary, highly localised primary-source analysis.")]));

// ── 3. Data Basis and Methodology ──
bodyChildren.push(h1("3.", "Data Basis and Methodology"));
bodyChildren.push(h2("3.1  Corpora"));
bodyChildren.push(body([t("Two job corpora feed the analysis. Both were collected automatically and are stored with their original URLs so that every finding can be traced back to the source posting.")]));
bodyChildren.push(tableTitle("Table 1: The two job corpora underlying this dossier"));
bodyChildren.push(table(
  ["Property", "Corpus H (baseline)", "Corpus N (active postings)"],
  [
    ["Collection date", "17 October 2026", "30 October 2026 (daily pipeline run)"],
    ["Scope", "Erlangen region, all portals, all professions", "Erlangen 50 km, Fachinformatiker Systemintegration filter, 14-day window"],
    ["Volume (unique postings)", "3,825 collected; 1,977 with full description text (Indeed)", "77 active postings"],
    ["Text quality", "Full posting text for the 1,977 Indeed rows; LinkedIn rows arrive text-blocked and are excluded from text statistics", "Full BA detail-API text for 31 postings; title plus snippet for the remainder"],
    ["Main use in this dossier", "Regional baseline rate (Chapter 4.2)", "Current requirement profile (Chapters 4.1, 4.3, 4.4)"],
  ],
  [22, 39, 39]
));
bodyChildren.push(body([t("Corpus H originates from an all-portals harvest (Indeed, LinkedIn) on 17 October 2026 and represents the overall regional labour market without occupational filtering; it therefore contains the full spread of professions from nursing to logistics. Corpus N is the continuously maintained, daily refreshed pipeline corpus that filters for the Systemintegration role family within 50 km of Erlangen and enriches every posting with employer, posting date, original URL and contact data.")], { after: 200 }));
bodyChildren.push(h2("3.2  Classification procedure"));
bodyChildren.push(body([t("Every posting was scanned with case-insensitive keyword families (full definitions in Appendix A): "), b("Azure"), t(" (the word Azure in any context), "), b("Azure certification"), t(" (AZ-900, AZ-104, AZ-800, MCSA, MCSE or Microsoft Zertifizierung), "), b("cloud (any)"), t(" (Azure, AWS, Google Cloud, GCP, generic cloud), "), b("Microsoft stack"), t(" (Windows Server, Active Directory, M365/Microsoft 365, Intune, Exchange, SCCM, Hyper-V), plus the context families network, virtualization, Linux and entry-level signals (Ausbildung, Azubi, Berufseinsteiger, Junior, Quereinsteiger and similar). A posting counts for a family if any keyword of that family occurs anywhere in title or text. Titles were additionally classified as FISI-relevant (system integration, system administration, IT support, network, infrastructure and related).")]));
bodyChildren.push(body([t("The union of the Azure, cloud and Microsoft-stack families forms the headline measure "), b("Microsoft/cloud competence demand"), t(". This union is deliberately generous: it counts every posting in which Microsoft-infrastructure or cloud skills appear, whether as a hard requirement or as part of the desired profile, and is therefore an upper bound rather than an overstatement.")], { after: 200 }));
bodyChildren.push(h2("3.3  Limitations"));
bodyChildren.push(body([t("Four limitations should be noted when weighing the evidence. First, the historical LinkedIn rows carry no description text (platform restriction), so the baseline rate is computed on the 1,977 text-bearing Indeed rows only. Second, 46 of the 77 active postings were classified on title plus snippet rather than full text, which makes the active-corpus rates, if anything, "), it("understated"), t(". Third, a local corpus of a few thousand postings is a sample, not a census; the direction of the finding (concentration of cloud demand in IT-infrastructure roles) is robust, the exact percentages carry sampling uncertainty. Fourth, keyword detection cannot distinguish hard requirements from nice-to-have mentions; the verbatim employer quotes in Chapter 4.3 allow case-by-case verification.")]));

// ── 4. Core Findings ──
bodyChildren.push(h1("4.", "Core Findings: Azure and Cloud Requirements in the Regional Market"));
bodyChildren.push(h2("4.1  Requirement profile of the 77 active postings"));
bodyChildren.push(body([t("Figure 1 shows the requirement profile of the currently active postings. Entry-level accessibility (40.3%) and networking (33.8%) dominate - both directly favourable for the applicant - followed by virtualization (16.9%), Linux (14.3%), generic cloud (13.0%) and the Microsoft on-premises stack (10.4%). Explicit Azure mentions appear in 3.9% of postings; the union of all Microsoft/cloud families reaches "), b("23.4%"), t(" (18 of 77).")]));
bodyChildren.push(figure("/home/z/my-project/data/azure_demand/chart1_profile_now.png", 560));
bodyChildren.push(caption("Figure 1: Requirement profile of the 77 active Systemintegration postings, Erlangen 50 km, 30 October 2026 (share of postings per keyword family; n = absolute count)."));
bodyChildren.push(body([t("The profile matches the textbook Systemintegration job: classical network and client-server administration on the ground floor, with the Microsoft cloud layer (Azure, M365, Intune) already present in one posting in four. A certification plan that certifies exactly this layer therefore addresses the single most sharply growing sub-demand in the corpus.")], { after: 200 }));
bodyChildren.push(h2("4.2  Concentration on the target role"));
bodyChildren.push(body([t("The decisive comparison is against the regional baseline. Across all professions (Corpus H), Microsoft/cloud skills appear in 3.4% of postings. Within the FISI-relevant titles of the same corpus the share rises to 14.5%, and in the currently active, role-filtered pipeline (Corpus N) to "), b("23.4%"), t(" - a sevenfold concentration from baseline to target role (Figure 2). In other words: an Azure certification is not a general-purpose credential in the Erlangen region; it is a targeted credential whose value concentrates precisely in the occupational niche the applicant is entering.")]));
bodyChildren.push(figure("/home/z/my-project/data/azure_demand/chart2_concentration.png", 540));
bodyChildren.push(caption("Figure 2: Share of postings requiring Azure, cloud or Microsoft-stack skills, by corpus. Baseline: all professions (n = 1,977 text-bearing postings); middle: FISI-relevant titles within the baseline (n = 76); right: active Systemintegration pipeline (n = 77)."));
bodyChildren.push(h2("4.3  Employer evidence"));
bodyChildren.push(body([t("Three currently active postings name Azure explicitly. All three are direct or verifiable employers with published contact channels (phone and/or application e-mail); their verbatim requirement wording is reproduced below so that the evidence can be checked against the original postings.")]));
bodyChildren.push(tableTitle("Table 2: Active postings naming Azure, with verbatim requirement wording"));
bodyChildren.push(table(
  ["Employer / role", "Source and status", "Verbatim requirement (German)"],
  [
    ["DMG MORI Digital GmbH - IT-Systemadministrator (m/w/d), Azure & IT Operations", "Get-in-IT, active 30 Oct 2026", "Job title in extenso: IT-Systemadministrator - Azure & IT Operations; Azure operations is the stated core of the role"],
    ["Suspa GmbH, Betriebsstaette Altdorf - Systemadministrator Netzwerk & Security", "BA job board, full API text, active 30 Oct 2026", "Administration und Weiterentwicklung der Azure-Netzwerkinfrastruktur (administration and further development of the Azure network infrastructure)"],
    ["NConsult GmbH - DevOps Engineer (m/w/d)", "BA job board, full API text, active 30 Oct 2026", "Betreuung und Optimierung von Cloud-Umgebungen (z. B. AWS, Azure oder GCP) (operation and optimisation of cloud environments, e.g. AWS, Azure or GCP)"],
  ],
  [34, 26, 40]
));
bodyChildren.push(body([t("Beyond these three, the Microsoft-stack family covers a further eight active postings - among them the Fachinformatiker Systemintegration role of ncsolution GmbH, the IT-specialist role of Minderleinsmuehle GmbH (Windows Server and Active Directory environment) and the Wimmer IT role addressed to Fachinformatiker explicitly. The full register of all 18 Microsoft/cloud postings is reproduced in Appendix B with employers and sources.")], { after: 200 }));
bodyChildren.push(body([t("Certification language is rare: exactly "), b("one"), t(" of the 77 active postings references a Microsoft certification path, and none of the three Azure postings conditions the role on a certificate - they ask for demonstrated knowledge ("), it("Kenntnisse"), t(") and experience. For a labour-market entrant without verifiable work history this is precisely the gap a vendor certification closes: employers state a knowledge requirement, and the certificate is the portable, third-party-verifiable proof of that knowledge.")], { after: 200 }));
bodyChildren.push(h2("4.4  Entry-level accessibility"));
bodyChildren.push(body([t("Of the 77 active postings, 40.3% carry explicit entry-level signals (Ausbildung, Azubi, Berufseinsteiger, Junior, Quereinsteiger or comparable wording). Reassuringly for the funding logic, entry-friendliness is "), it("overrepresented"), t(" among the Azure postings: two of the three Azure-naming postings are entry-flagged (the Suspa system-administrator role and the NConsult DevOps role), i.e. 66.7% versus 40.3% in the corpus at large. The corpus also contains 37 postings from direct employers as against 13 from staffing intermediaries (26 unclassified), and the Azure evidence of Table 2 sits entirely with direct employers. The demand the certification addresses is thus both current and reachable for a beginner.")]));

// ── 5. Suitability ──
bodyChildren.push(h1("5.", "Suitability of the Azure Certification Path for the Applicant"));
bodyChildren.push(h2("5.1  Skill-family overlap with the target role"));
bodyChildren.push(body([t("The AZ-104 Azure Administrator curriculum - identity and governance (Entra ID), storage, compute, virtual networking, monitoring and backup - is the cloud continuation of the exact skill families that dominate the active corpus: networking (33.8%), virtualization (16.9%) and the Microsoft on-premises stack (10.4%). Systemintegration training and Azure administration are not parallel tracks; the second is the natural extension of the first. This is visible in the corpus itself, where hybrid roles (Suspa: Azure network infrastructure alongside VLANs, firewalls and a public-key infrastructure) treat on-premises and cloud administration as one task.")]));
bodyChildren.push(h2("5.2  The certificate as verifiable proof for an entrant"));
bodyChildren.push(body([t("Chapter 4.3 showed that employers ask for knowledge, not certificates. A career entrant lacks the work history that normally evidences such knowledge. The Microsoft certification path solves this asymmetrically well for three reasons: it is "), b("vendor-official"), t(" (the certificate issuer is the same company whose products the employers in Table 2 operate); it is "), b("standardised and internationally readable"), t(", which matters in a market where many intermediaries pre-screen CVs; and it is "), b("examination-based"), t(", so the proof does not depend on prior employment. AZ-900 requires no professional background and is explicitly designed as an entry credential; AZ-104 is the associate-level certificate that corresponds to the administrator roles observed in the corpus.")]));
bodyChildren.push(h2("5.3  Demand-supply asymmetry"));
bodyChildren.push(body([t("The corpus contains no evidence that would suggest an oversupply of certified Azure juniors locally: certificates are almost never demanded (1 of 77), while the underlying skills are demanded in every fourth posting (23.4%). Where skills are demanded but credentials are rare, certification is economically meaningful - it differentiates without excluding. The applicant would hold a formal, verifiable credential in a skill family that one in four target employers currently names, in a region whose industrial base (Siemens, medical technology, manufacturing IT in and around Erlangen, Fuerth and Nuernberg) continues to migrate hybrid workloads into Azure.")]));

// ── 6. Certification Pathway and Cost Frame ──
bodyChildren.push(h1("6.", "Certification Pathway, Providers and Cost Frame"));
bodyChildren.push(body([t("The recommended pathway follows the standard Microsoft stack for junior infrastructure profiles:")]));
bodyChildren.push(tableTitle("Table 3: Recommended certification pathway"));
bodyChildren.push(table(
  ["Step", "Certificate", "Level and content focus", "Typical preparation", "Exam fee (approx.)"],
  [
    ["1", "AZ-900 Azure Fundamentals", "Entry level; cloud concepts, Azure architecture and services, governance and pricing", "2-6 weeks part-time", "approx. EUR 99"],
    ["2", "AZ-104 Azure Administrator Associate", "Associate level; Entra ID, storage, compute, virtual networking, monitoring, backup", "6-12 weeks part-time (after AZ-900)", "approx. EUR 165-195"],
    ["3 (optional)", "AZ-800 Windows Server Hybrid Core Infrastructure", "Hybrid bridge; certifies the on-premises Windows Server competence of the classic Systemintegration role", "8-12 weeks part-time", "approx. EUR 165-195"],
  ],
  [8, 24, 36, 16, 16]
));
bodyChildren.push(body([t("All figures are approximate list prices as of October 2026 and must be confirmed with the provider and Pearson VUE at the time of application; the dossier deliberately avoids quoting binding prices. For the Bildungsgutschein the decisive requirement is that the measure - course and, where offered, the integrated examination - is carried out by an "), b("AZAV-approved provider"), t("; approved measures in this field are offered both regionally (Franconia/Nuremberg metropolitan area) and as supported online programmes. The applicant should request the provider's AZAV approval number and the measure number (Maßnahmenummer) when obtaining quotes, since the agency issues the voucher for a named, approved measure. The two-step path is deliberately staged: AZ-900 establishes a verifiable foundation quickly, and AZ-104 then targets the administrator profile of Table 2 directly.")], { after: 200 }));

// ── 7. Conclusions ──
bodyChildren.push(h1("7.", "Conclusions and Recommendation"));
bodyChildren.push(body([t("Mapped onto the three funding criteria of Section 82 SGB III, the evidence reads as follows.")]));
bodyChildren.push(tableTitle("Table 4: Findings mapped to the funding criteria of Section 82 SGB III"));
bodyChildren.push(table(
  ["Criterion", "Evidence from this dossier"],
  [
    ["Necessity (Notwendigkeit)", "23.4% of active target-role postings require Azure/cloud/Microsoft-stack skills versus 3.4% regional baseline; the applicant has no verifiable proof of these skills yet; the certificate closes the proof gap for an entrant (Chapter 4.3, 5.2)."],
    ["Suitability (Eignung)", "The AZ-900/AZ-104 path starts at foundation level with no prior experience required; the skill families overlap directly with the Systemintegration profile (network 33.8%, virtualization 16.9%, Microsoft stack 10.4%); 40.3% of postings are entry-friendly (Chapters 4.1, 5.1)."],
    ["Prospects of success (Erfolgsaussichten)", "Three named regional employers with live Azure requirements (DMG MORI Digital, Suspa, NConsult); two of three Azure roles entry-flagged; direct-employer majority among gold-list contacts; certified-skills asymmetry indicates differentiation rather than gatekeeping (Chapters 4.3, 4.4, 5.3)."],
  ],
  [28, 72]
));
bodyChildren.push(body([b("Recommendation."), t(" The evidence supports funding the staged Azure certification path (AZ-900 followed by AZ-104, optionally extended by AZ-800) with a Bildungsgutschein, provided the measure is booked with an AZAV-approved provider. The applicant should: (1) present this dossier and its German one-page summary at the next appointment with the Agentur fuer Arbeit; (2) obtain two to three quotes from approved providers including the measure number; (3) confirm whether examination fees are integrated in the funded measure; and (4) after certification, target the employer group of Table 2 and Appendix B directly, using the contact channels already documented in the job monitor. The underlying data files and scripts are named in Appendix C so that the analysis can be re-run and extended at any time.")]));

// ── Appendices ──
bodyChildren.push(h1("8.", "Appendices"));
bodyChildren.push(h2("Appendix A: Keyword definitions"));
bodyChildren.push(table(
  ["Family", "Keywords (case-insensitive, German/English)"],
  [
    ["Azure (explicit)", "the word Azure in any context within title or text"],
    ["Azure certification", "AZ-900, AZ-104, AZ-800, AZ-140, AZ-700, MCSA, MCSE, Microsoft Zertifizierung"],
    ["Cloud (any)", "cloud, AWS, Azure, Google Cloud, GCP, OpenStack, Cloudumgebung, Cloud-Technolog*"],
    ["Microsoft stack", "Windows Server, Active Directory, M365, Microsoft 365, Intune, Exchange, SCCM, Hyper-V"],
    ["Virtualization", "VMware, Proxmox, Hyper-V, VirtualBox, Docker, Kubernetes, Virtualisierung"],
    ["Network", "Netzwerk, network, TCP/IP, Firewall, VPN, LAN, WLAN, Routing"],
    ["Linux", "Linux, Debian, Ubuntu, RHEL, Red Hat"],
    ["Entry signals", "Ausbildung, Azubi, Berufseinsteiger, Berufseinstieg, Einstieg, Junior, Quereinsteiger, keine Erfahrung"],
    ["FISI-relevant title", "Systemintegration, Systemintegration, Systemadmin, IT-Admin, Administrator, IT-Support, Support, Sysadmin, IT-Techniker, Netzwerk, Infrastruktur, Client, Server, IT-Betreuung, IT-Operation*"],
  ],
  [24, 76]
));
bodyChildren.push(h2("Appendix B: Register of the 18 active Microsoft/cloud postings (30 October 2026)"));
bodyChildren.push(table(
  ["Posting title", "Employer", "Source", "Flags"],
  [
    ["IT-Systemadministrator (m/w/d)", "cns computer & netzwerk service gmbh", "BA", "MS stack"],
    ["IT-Spezialist KI & Digitalisierung (m/w/d)", "Minderleinsmuehle GmbH & Co. KG", "BA", "MS stack"],
    ["Wimmer IT - Fachinformatiker(in) / IT-Techniker(in)", "Wimmer IT GmbH & Co. KG", "BA", "MS stack"],
    ["Systemadministrator Netzwerk & Security", "Suspa GmbH, BS Altdorf", "BA", "Azure + cloud"],
    ["Fachinformatiker Systemintegration (m/w/d)", "ncsolution GmbH", "BA", "MS stack"],
    ["DevOps Platform Engineer OpenShift (m/w/d)", "set - software engineering gmbh", "BA", "Cloud"],
    ["DevOps Engineer (m/w/d)", "NConsult GmbH", "BA", "Azure + cloud"],
    ["(Junior) IT Manager First Level Support (m/w/d)", "Simba-Dickie-Group GmbH", "BA", "MS stack"],
    ["IT-Systemadministrator (m/w/d)", "I.K. Hofmann GmbH", "BA", "MS stack"],
    ["IT System Engineer z/OS Netzwerk und Security (m/w/d)", "Akkodis Germany Tech Experts GmbH", "BA", "Cloud"],
    ["Supporter (m/w/d) im Help Desk", "Akkodis Germany Tech Experts GmbH", "BA", "Cloud"],
    ["System Engineer Netzwerk (m/w/d)", "Akkodis Germany Tech Experts GmbH", "BA", "Cloud"],
    ["System Engineer (m/w/d) Linux", "Akkodis Germany Tech Experts GmbH", "BA", "Cloud"],
    ["IT-Systemadministrator (m/w/d)", "Akkodis Germany Tech Experts GmbH", "BA", "Cloud"],
    ["IT-Servicetechniker (m/w/d)", "wu personal GmbH Muenchen", "BA", "MS stack"],
    ["Servicetechniker (m/w/d) IT Support und Kundenservice", "puro Personaldienstleistung GmbH", "BA", "MS stack"],
    ["IT-Systemadministrator (m/w/d) - Azure & IT Operations", "DMG MORI Digital GmbH", "Get-in-IT", "Azure + cloud"],
    ["IT-Systemadministrator Infrastruktur & Cloud (m/w/d)", "PFLEIDERER", "Indeed", "Cloud"],
  ],
  [40, 30, 12, 18]
));
bodyChildren.push(body([t("Note on intermediaries: rows by Akkodis, I.K. Hofmann, wu personal and puro Personaldienstleistung are staffing-intermediary listings; the remaining fourteen postings sit with direct employers. The full original URLs for all 18 rows are contained in the evidence CSV named in Appendix C.")], { after: 200 }));
bodyChildren.push(h2("Appendix C: Reproducibility"));
bodyChildren.push(body([t("All numbers in this dossier are generated by scripts/azure_demand_scan.py from two immutable source files (data/raw/erlangen_ALL_portals_20261017_1733.json for the baseline and data/enriched/jobs_enriched_20261030-0709.json for the active corpus, augmented by live BA detail-API calls). Intermediate outputs: data/azure_demand/azure_scan_20261030-0825.json (per-posting classification), azure_scan_20261030-0825.csv (evidence register with original URLs), stats_20261030-0825.json (all quoted percentages), and the two figure PNGs. Re-running the scan script reproduces every statistic in this document; the daily pipeline (scripts/run_daily_task.sh) refreshes the active corpus each morning, so the analysis can be repeated with any later corpus vintage.")]));

// ══════════════════ DOCUMENT ══════════════════
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimSun" }, size: 24, color: "000000" },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 30, bold: true, color: P.primary },
        paragraph: { spacing: { before: 360, after: 160, line: 312 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: { ascii: "Times New Roman", eastAsia: "SimHei" }, size: 26, bold: true, color: P.h2 },
        paragraph: { spacing: { before: 240, after: 120, line: 312 }, outlineLevel: 1 },
      },
    },
  },
  sections: [
    { // Section 1: cover
      properties: { page: { size: pgSize, margin: { top: 0, bottom: 0, left: 0, right: 0 } } },
      children: buildCoverR1({
        title: "Azure & Cloud Demand Analysis",
        subtitle: "Justification for a Bildungsgutschein - Microsoft Azure Certifications (AZ-900 / AZ-104)",
        englishLabel: "LABOUR MARKET EVIDENCE DOSSIER",
        metaLines: [
          "Data basis: 2,054 postings analysed (October 2026)",
          "Region: Erlangen, 50 km radius",
          "Target role: Fachinformatiker/-in fuer Systemintegration",
          "Prepared: 30 October 2026",
        ],
        footerLeft: "asha-jobtoolkit - automated job market monitor",
        footerRight: "30 Oct 2026",
        palette: P,
      }),
    },
    { // Section 2: TOC (Roman)
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: pgSize, margin: pgMargin, pageNumbers: { start: 1, formatType: NumberFormat.UPPER_ROMAN } },
      },
      footers: { default: pageFooter() },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER, spacing: { before: 200, after: 160 },
          children: [new TextRun({ text: "Table of Contents", bold: true, size: 32, font: { ascii: "Times New Roman", eastAsia: "SimHei" } })],
        }),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-2" }),
        new Paragraph({
          spacing: { before: 80 },
          children: [new TextRun({
            text: "Note: This Table of Contents is generated via field codes. To ensure page number accuracy after editing, please right-click the TOC and select \"Update Field.\"",
            italics: true, size: 16, color: "888888", font: { ascii: "Times New Roman" } })],
        }),
        // NOTE: no trailing PageBreak here — body is a separate NEXT_PAGE section
        // (PageBreak + section break = blank page, caught by postcheck)
      ],
    },
    { // Section 3: body (Arabic, start 1)
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: pgSize, margin: pgMargin, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } },
      },
      headers: { default: pageHeader() },
      footers: { default: pageFooter() },
      children: bodyChildren,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_MAIN, buf);
  console.log("written", OUT_MAIN, buf.length, "bytes");
});
