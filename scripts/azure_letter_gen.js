// Begruendungsschreiben (German) — Bildungsgutschein Azure-Zertifizierungen
// Letter format: no cover, no TOC, single section, closing right-aligned (common-rules).
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, WidthType, BorderStyle, ShadingType,
} = require("docx");
const fs = require("fs");

const OUT = "/home/z/my-project/download/Begruendung_Bildungsgutschein_Azure_2026-10-30.docx";

const TNR = { ascii: "Times New Roman", eastAsia: "Times New Roman" };
function p(runsOrText, opts = {}) {
  const runs = typeof runsOrText === "string"
    ? [new TextRun({ text: runsOrText, size: 24, font: TNR, bold: !!opts.bold })]
    : runsOrText;
  return new Paragraph({
    alignment: opts.right ? AlignmentType.RIGHT : AlignmentType.LEFT,
    spacing: { line: 312, after: opts.after !== undefined ? opts.after : 160, before: opts.before || 0 },
    children: runs,
  });
}
const r = (text, o = {}) => new TextRun({ text, size: 24, font: TNR, bold: !!o.bold, italics: !!o.i });
const ph = (text) => new TextRun({ text, size: 24, font: TNR, bold: true, color: "8A5A00" }); // placeholders amber

function statCell(text, w, header) {
  return new TableCell({
    width: { size: w, type: WidthType.PERCENTAGE },
    shading: header ? { type: ShadingType.CLEAR, fill: "1B6B7A" } : undefined,
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: AlignmentType.LEFT, spacing: { line: 276 },
      children: [new TextRun({ text: String(text), size: 21, bold: header,
        color: header ? "FFFFFF" : "000000", font: TNR })],
    })],
  });
}
function statTable(rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "1B6B7A" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "1B6B7A" },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "C8DDE2" },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    },
    rows: rows.map((row, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: row.map((c, j) => statCell(c, [34, 22, 44][j], i === 0)),
    })),
  });
}

const children = [
  // sender block (placeholders per convention)
  p([ph("【Vorname Nachname】")], { after: 0 }),
  p([ph("【Stra\u00dfe Hausnummer】")], { after: 0 }),
  p([ph("【PLZ Ort】")], { after: 0 }),
  p([ph("【Telefon】 \u00b7 【E-Mail】")], { after: 300 }),
  // recipient block
  p("Agentur f\u00fcr Arbeit", { after: 0 }),
  p([ph("【Name der Arbeitsagentur / Jobcenter-Ort】")], { after: 0 }),
  p([ph("【Adresse der Agentur】")], { after: 300 }),
  // customer no + date
  p([r("Kundennummer: "), ph("【Kundennummer】")], { after: 0 }),
  p([ph("【Ort, Datum】")], { after: 400 }),

  // subject
  p([r("Begr\u00fcndung zur Beantragung eines Bildungsgutscheins \u2013 Microsoft-Azure-Zertifizierungen (AZ-900 und AZ-104)", { bold: true })], { after: 300 }),

  p("Sehr geehrte Damen und Herren,"),

  p([r("ich beabsichtige den Berufseinstieg als Fachinformatiker/-in f\u00fcr Systemintegration im Raum Erlangen und beantrage einen Bildungsgutschein (\u00a7 82 SGB III) f\u00fcr die gestuften Microsoft-Zertifizierungen AZ-900 (Azure Fundamentals) und im zweiten Schritt AZ-104 (Azure Administrator Associate) bei einem AZAV-zugelassenen Bildungsanbieter. Diese Begr\u00fcndung st\u00fctzt sich auf eine eigene, reproduzierbare Auswertung des regionalen Stellenmarkts; das vollst\u00e4ndige Dossier mit allen Zahlen, Quellen und Original-URLs liegt diesem Schreiben als Anlage bei.")]),

  p([r("Arbeitsmarktnachweise (Stand 30.10.2026): ", { bold: true }), r("Von den aktuell 77 aktiven Systemintegration-Stellen im 50-km-Radius um Erlangen erfordern 18 Stellen \u2013 also "), r("23,4 Prozent", { bold: true }), r(" \u2013 Azure-, Cloud- oder Microsoft-Infrastrukturkenntnisse. Zum Vergleich: Im gesamten regionalen Basiskorpus von 1.977 Stellenberufen aller Branchen liegen diese Kenntnisse nur bei 3,4 Prozent vor. Die Nachfrage konzentriert sich also rund siebenfach genau auf meine Zielrolle. Zugleich sind 40,3 Prozent der aktiven Stellen mit Einstiegssignalen gekennzeichnet (Ausbildung, Azubi, Berufseinsteiger, Junior, Quereinsteiger); von den drei Stellen mit expliziter Azure-Anforderung sind zwei einsteigerfreundlich.")]),

  statTable([
    ["Nachweiskategorie", "Anteil", "Beleg aus dem Korpus"],
    ["Azure/Cloud/MS-Stack in aktiven FISI-Stellen", "18 von 77 (23,4 %)", "u. a. DMG MORI Digital GmbH, Suspa GmbH Altdorf, NConsult GmbH"],
    ["Dasselbe im Regionalbasiskorpus (alle Berufe)", "68 von 1.977 (3,4 %)", "Volltextauswertung Indeed-Korpus vom 17.10.2026"],
    ["Einstiegssignale in aktiven FISI-Stellen", "31 von 77 (40,3 %)", "Ausbildung/Azubi/Junior/Quereinsteiger-Wortlaut"],
  ]),
  p("", { after: 60 }),

  p([r("Konkrete Arbeitgeberbelege: ", { bold: true }), r("Die DMG MORI Digital GmbH sucht aktuell einen \u201eIT-Systemadministrator \u2013 Azure & IT Operations\u201c; die Suspa GmbH (Altdorf) verlangt die \u201eAdministration und Weiterentwicklung der Azure-Netzwerkinfrastruktur\u201c; die NConsult GmbH betreibt \u201eCloud-Umgebungen (z. B. AWS, Azure oder GCP)\u201c. Keine dieser Stellen setzt eine Zertifizierung voraus \u2013 gefordert werden Kenntnisse. F\u00fcr Berufseinsteiger ohne nachweisbare Berufserfahrung ist das herstellerseitige Zertifikat der tragf\u00e4hige, f\u00fcr Arbeitgeber \u00fcberpr\u00fcfbare Kompetenznachweis genau dieser Kenntnisse.")]),

  p([r("F\u00f6rderw\u00fcrdigkeit nach \u00a7 82 SGB III: ", { bold: true }), r("Die "), r("Notwendigkeit", { i: true }), r(" folgt aus der gezeigten, rollenspezifischen Nachfragekonzentration und dem fehlenden Kenntnisnachweis. Die "), r("Eignung", { i: true }), r(" ist gegeben: AZ-900 setzt keine Vorerfahrung voraus, und die Zertifikatsinhalte (Entra ID, virtuelle Netzwerke, Speicher, Monitoring) setzen die im Stellenkorpus dominierenden Familien Netzwerk (33,8 %), Virtualisierung (16,9 %) und Microsoft-Stack (10,4 %) unmittelbar fort. Die "), r("Erfolgsaussichten", { i: true }), r(" belegen drei aktuell aktive Azure-Stellen mit direkten Arbeitgeberkontakten sowie die Tatsache, dass Zertifikate in nur 1 von 77 Stellen gefordert, die dahinterstehenden Kenntnisse aber in jeder vierten Stelle verlangt werden \u2013 das Zertifikat unterscheidet also, ohne auszuschlie\u00dfen.")]),

  p([r("Die Ma\u00dfnahme soll bei einem AZAV-zugelassenen Tr\u00e4ger erfolgen; Anbieter, Ma\u00dfnahmenummer und Kostenangaben reiche ich nach Erhalt der Angebote nach. Vorgesehen ist der Ablauf: AZ-900 als Fundament (Pr\u00fcfungsgeb\u00fchr ca. 99 EUR), anschlie\u00dfend AZ-104 als associate-level Zieltitel (ca. 165\u2013195 EUR, Angaben unverbindlich, Stand Oktober 2026).")]),

  p([r("Ich bitte Sie, die F\u00f6rderung der genannten Zertifizierungen mit einem Bildungsgutschein zu pr\u00fcfen. Das beigef\u00fcgte Dossier enth\u00e4lt alle Methodik, alle Kennzahlen sowie ein Register der 18 betroffenen Stellen mit Original-URLs zur \u00dcberpr\u00fcfung.")]),

  p("Mit freundlichen Gr\u00fc\u00dfen", { right: true, before: 300, after: 40 }),
  p([ph("【Unterschrift / Vorname Nachname】")], { right: true }),

  p([r("Anlage: Dossier \u201eAzure & Cloud Demand Analysis\u201c (30.10.2026)", { i: true })], { before: 300, after: 0 }),
];

const doc = new Document({
  styles: { default: { document: {
    run: { font: TNR, size: 24, color: "000000" },
    paragraph: { spacing: { line: 312 } },
  } } },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("written", OUT, buf.length, "bytes");
});
