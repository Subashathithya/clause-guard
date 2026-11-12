import type { jsPDF as JsPdf } from 'jspdf';
import type { AnalysisResult, ChecklistItem, Clause, ContractDate } from '../types';
import { attentionOf, categoryLabel } from './format';

/* Brand palette (RGB) — mirrors src/styles/tokens.css */
const BRAND: [number, number, number] = [79, 70, 229];
const BRAND_DARK: [number, number, number] = [67, 56, 202];
const INK: [number, number, number] = [17, 24, 39];
const MUTED: [number, number, number] = [107, 114, 128];
const LINE: [number, number, number] = [229, 231, 235];
const RED: [number, number, number] = [220, 38, 38];
const AMBER: [number, number, number] = [217, 119, 6];
const GREEN: [number, number, number] = [22, 163, 74];

const PAGE_W = 210;
const MARGIN = 14;
const CONTENT_W = PAGE_W - MARGIN * 2;

/** jsPDF core fonts do not include the ₹ glyph — use a plain-text prefix. */
function clean(text: unknown, max = 600): string {
  const s = String(text ?? '')
    .replace(/₹/g, 'Rs ')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\u2013/g, '-')
    .replace(/\u2014/g, '-')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/[^\x20-\xFF]/g, '')
    .trim();
  return s.length > max ? `${s.slice(0, max - 1)}…`.replace('…', '...') : s;
}

function money(n?: number | null): string {
  if (!n || n <= 0) return 'Rs 0';
  if (n >= 1_00_00_000) return `Rs ${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `Rs ${(n / 1_00_000).toFixed(1)} L`;
  if (n >= 1_000) return `Rs ${(n / 1_000).toFixed(1)}k`;
  return `Rs ${n.toLocaleString('en-IN')}`;
}

function riskColor(level: string): [number, number, number] {
  if (level === 'red') return RED;
  if (level === 'yellow') return AMBER;
  if (level === 'green') return GREEN;
  return MUTED;
}

function riskWord(level: string): string {
  if (level === 'red') return 'High';
  if (level === 'yellow') return 'Moderate';
  if (level === 'green') return 'Low';
  return 'Unknown';
}

/** Rounded chip, drawn with a filled rect + border. */
function chip(doc: JsPdf, x: number, y: number, w: number, h: number, color: [number, number, number], label: string) {
  doc.setFillColor(...color);
  doc.setDrawColor(...color);
  doc.roundedRect(x, y, w, h, 2.2, 2.2, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.text(label, x + w / 2, y + h / 2 + 0.9, { align: 'center' });
}

function sectionTitle(doc: JsPdf, y: number, text: string): number {
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11.5);
  doc.setTextColor(...INK);
  doc.text(text, MARGIN, y);
  doc.setDrawColor(...LINE);
  doc.setLineWidth(0.3);
  doc.line(MARGIN, y + 2, PAGE_W - MARGIN, y + 2);
  return y + 8;
}

/**
 * Build and download a branded PDF report for one analysed contract.
 * The PDF libraries are loaded on demand so they stay out of the initial bundle.
 */
export interface ReportExtras {
  dates?: ContractDate[];
  checklist?: ChecklistItem[];
}

const DATE_KIND_LABELS: Record<string, string> = {
  payment: 'Payment',
  renewal: 'Renewal',
  notice: 'Notice',
  termination: 'Termination',
  other: 'Other',
};

function prettyDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return clean(iso, 30);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export async function downloadAnalysisReport(
  analysis: AnalysisResult,
  extras: ReportExtras = {}
): Promise<void> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ]);
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const generated = new Date().toLocaleString();

  /* ---------------------------------------------------------- header band */
  doc.setFillColor(...BRAND);
  doc.rect(0, 0, PAGE_W, 30, 'F');
  doc.setFillColor(...BRAND_DARK);
  doc.circle(19, 15, 6, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.text('CG', 19, 16.2, { align: 'center' });

  doc.setFontSize(16);
  doc.text('ClauseGuard', 29, 13.5);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(224, 231, 255);
  doc.text('Contract Risk & Clause Report', 29, 18.6);

  doc.setFontSize(8);
  doc.setTextColor(224, 231, 255);
  doc.text(`Generated ${clean(generated, 60)}`, PAGE_W - MARGIN, 12, { align: 'right' });
  doc.text(`ID ${clean(analysis.document_id || '-', 40)}`, PAGE_W - MARGIN, 17, { align: 'right' });

  /* ------------------------------------------------------------ title block */
  let y = 42;
  doc.setTextColor(...INK);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.text(clean(analysis.document_name || 'Untitled contract', 90), MARGIN, y);

  const summary = analysis.risk_summary;
  const overall = clean(summary?.overall_risk || 'unknown');
  const avg = Number(summary?.average_risk_score ?? 0);
  y += 7;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...MUTED);
  doc.text(
    `${analysis.total_clauses} sections analyzed  ·  average risk score ${avg.toFixed(1)}/100  ·  exposure ${money(summary?.total_financial_exposure_inr)}`,
    MARGIN,
    y
  );

  y += 8;
  const chipColor = riskColor(
    /red|high/i.test(overall) ? 'red' : /yellow|moderate|medium/i.test(overall) ? 'yellow' : 'green'
  );
  chip(doc, MARGIN, y, 42, 8, chipColor, `OVERALL: ${riskWord(
    /red|high/i.test(overall) ? 'red' : /yellow|moderate|medium/i.test(overall) ? 'yellow' : 'green'
  ).toUpperCase()}`);

  chip(doc, MARGIN + 46, y, 30, 8, RED, `${summary?.red_count ?? 0} high`);
  chip(doc, MARGIN + 79, y, 30, 8, AMBER, `${summary?.yellow_count ?? 0} mod`);
  chip(doc, MARGIN + 112, y, 30, 8, GREEN, `${summary?.green_count ?? 0} low`);
  y += 8;

  /* --------------------------------------------------------------- summary */
  y = sectionTitle(doc, y + 4, 'Summary');
  const s = analysis.summary;
  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    theme: 'plain',
    styles: { font: 'helvetica', fontSize: 9, cellPadding: 1.6, textColor: INK },
    body: [
      ['Sections analyzed', String(s?.total_analyzed ?? analysis.total_clauses)],
      ['Review carefully', String(s?.red_flags ?? 0)],
      ['Worth a look', String(s?.warnings ?? 0)],
      ['Looks fine', String(s?.safe ?? 0)],
      ['Priority actions', clean((s?.top_priorities || []).join('  •  '), 400) || '-'],
      ['Recommendation', clean(s?.recommendation, 600) || '-'],
    ],
    columnStyles: {
      0: { fontStyle: 'bold', cellWidth: 40, textColor: MUTED },
      1: { cellWidth: CONTENT_W - 40 },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && data.column.index === 0) data.cell.styles.fontStyle = 'bold';
    },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;

  /* --------------------------------------------------------- clause table */
  y = sectionTitle(doc, y, 'Clause-by-clause breakdown');
  const rows = (analysis.clauses || []).map((c: Clause, i) => [
    String(i + 1),
    clean(c.category ? categoryLabel(c.category) : 'Other', 40),
    clean(c.text, 220),
    riskWord(c.risk_level),
    `${Math.round(Number(c.risk_score ?? 0))}`,
  ]);

  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    head: [['#', 'Section', 'Clause text', 'Risk', 'Score']],
    body: rows,
    theme: 'grid',
    styles: { font: 'helvetica', fontSize: 7.6, cellPadding: 1.6, textColor: INK, lineColor: LINE, lineWidth: 0.15, valign: 'top' },
    headStyles: { fillColor: BRAND, textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 8 },
    alternateRowStyles: { fillColor: [249, 250, 251] },
    columnStyles: {
      0: { cellWidth: 7, halign: 'center' },
      1: { cellWidth: 34 },
      2: { cellWidth: CONTENT_W - 7 - 34 - 18 - 14 },
      3: { cellWidth: 18, halign: 'center' },
      4: { cellWidth: 14, halign: 'center' },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && data.column.index === 3) {
        const level = (analysis.clauses || [])[data.row.index]?.risk_level;
        data.cell.styles.textColor = riskColor(level);
        data.cell.styles.fontStyle = 'bold';
      }
    },
  });
  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;

  /* ---------------------------------------------------------- key findings */
  const keyIssues = (analysis.clauses || []).filter((c) => c.risk_level !== 'green').slice(0, 8);
  if (keyIssues.length > 0) {
    if (y > 232) {
      doc.addPage();
      y = 22;
    }
    y = sectionTitle(doc, y, 'What needs your attention');
    for (const c of keyIssues) {
      if (y > 262) {
        doc.addPage();
        y = 22;
      }
      const color = riskColor(c.risk_level);
      doc.setFillColor(...color);
      doc.rect(MARGIN, y - 3.4, 1.6, 4, 'F');
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(...INK);
      doc.text(`${categoryLabel(c.category || 'Other')} - ${riskWord(c.risk_level)} risk`, MARGIN + 4, y);
      y += 5;
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      const explanation = doc.splitTextToSize(clean(c.explanation || c.text, 320), CONTENT_W - 6);
      doc.text(explanation.slice(0, 4), MARGIN + 4, y);
      y += explanation.slice(0, 4).length * 3.6 + 4;
    }
  }

  /* ------------------------------------------------------------- key dates */
  const dates = extras.dates || [];
  if (dates.length > 0) {
    if (y > 230) {
      doc.addPage();
      y = 22;
    }
    y = sectionTitle(doc, y, 'Key dates and reminders');
    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [['Date', 'What it is', 'Type', 'Reminder', 'Status']],
      body: dates.map((d) => [
        prettyDay(d.due_date),
        clean(d.label, 80),
        DATE_KIND_LABELS[d.kind] || 'Other',
        d.remind_days_before === 0
          ? `On ${prettyDay(d.due_date)}`
          : `${prettyDay(d.remind_on)} (${d.remind_days_before}d before)`,
        d.is_overdue ? 'Overdue' : d.days_until === 0 ? 'Today' : `In ${d.days_until}d`,
      ]),
      theme: 'grid',
      styles: { font: 'helvetica', fontSize: 8, cellPadding: 1.6, textColor: INK, lineColor: LINE, lineWidth: 0.15, valign: 'top' },
      headStyles: { fillColor: BRAND, textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 8 },
      alternateRowStyles: { fillColor: [249, 250, 251] },
      columnStyles: {
        0: { cellWidth: 32 },
        1: { cellWidth: 62 },
        2: { cellWidth: 22 },
        3: { cellWidth: 42 },
        4: { cellWidth: CONTENT_W - 32 - 62 - 22 - 42, halign: 'center' },
      },
      didParseCell: (data) => {
        if (data.section === 'body' && data.column.index === 4) {
          const row = dates[data.row.index];
          data.cell.styles.fontStyle = 'bold';
          data.cell.styles.textColor = row?.is_overdue ? RED : row?.days_until === 0 ? AMBER : GREEN;
        }
      },
    });
    y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
  }

  /* ------------------------------------------------------------- checklist */
  const checklist = extras.checklist || [];
  if (checklist.length > 0) {
    if (y > 238) {
      doc.addPage();
      y = 22;
    }
    const done = checklist.filter((i) => i.done).length;
    y = sectionTitle(doc, y, `Before you sign (${done}/${checklist.length} done)`);
    for (const item of checklist) {
      const lines = doc.splitTextToSize(clean(item.text, 320), CONTENT_W - 8);
      const needed = lines.length * 3.8 + 2.4;
      if (y + needed > 280) {
        doc.addPage();
        y = 22;
      }
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(...(item.done ? GREEN : INK));
      doc.text(item.done ? '[x]' : '[ ]', MARGIN, y);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(...(item.done ? MUTED : INK));
      doc.text(lines, MARGIN + 8, y);
      y += needed;
    }
    y += 4;
  }

  /* ---------------------------------------------------------------- footer */
  const pages = doc.getNumberOfPages();
  for (let p = 1; p <= pages; p += 1) {
    doc.setPage(p);
    doc.setDrawColor(...LINE);
    doc.setLineWidth(0.3);
    doc.line(MARGIN, 285, PAGE_W - MARGIN, 285);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTED);
    doc.text(
      'Generated by ClauseGuard. This report is an automated assist, not legal advice.',
      MARGIN,
      289.5
    );
    doc.text(`Page ${p} of ${pages}`, PAGE_W - MARGIN, 289.5, { align: 'right' });
  }

  const safeName = (analysis.document_name || 'contract')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 40);
  doc.save(`clauseguard-report-${safeName || 'contract'}.pdf`);
}

/** Small helper so callers can show the attention label used inside the PDF. */
export function reportRiskLabel(level: string): string {
  return riskWord(level);
}

export { attentionOf };
