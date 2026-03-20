#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");

const sourceHtmlPath = path.join(
  repoRoot,
  "data/published/sites/kaisei-2026-math/index.html",
);
const outputDir = path.join(
  repoRoot,
  "data/derived/problem-labels/kaisei-2026-math",
);
const manualLabelsPath = path.join(outputDir, "manual-labels.json");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function extractInlineScripts(html) {
  return [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
}

function extractExamData(filePath) {
  const html = fs.readFileSync(filePath, "utf8");
  const inlineScripts = extractInlineScripts(html);
  const lastScript = inlineScripts.at(-1);

  if (!lastScript) {
    throw new Error(`No inline script found in ${filePath}`);
  }

  const sandbox = {
    renderExamPage(data) {
      sandbox.examData = data;
    },
  };

  vm.createContext(sandbox);
  vm.runInContext(lastScript, sandbox, { filename: filePath });

  if (!sandbox.examData) {
    throw new Error(`Exam data was not captured from ${filePath}`);
  }

  return sandbox.examData;
}

function pathFromSiteHref(href) {
  const withoutDotDots = href.replace(/^(\.\.\/)+/, "");

  if (withoutDotDots.startsWith("pdfs/")) {
    return `data/raw/${withoutDotDots}`;
  }

  if (withoutDotDots.startsWith("page_images/")) {
    return `data/derived/${withoutDotDots.replace("page_images/", "page-images/")}`;
  }

  return withoutDotDots;
}

function toProblemCode(displayId) {
  return displayId
    .replace(/^問/, "q")
    .replace(/\(/g, "_")
    .replace(/\)/g, "")
    .replace(/[^\w]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/_$/, "")
    .toLowerCase();
}

function flattenQuestions(examData) {
  const questionPdf = pathFromSiteHref(examData.sources.localPaths[0]);
  const answerPdf = pathFromSiteHref(examData.sources.localPaths[1]);
  const answerImage = pathFromSiteHref(examData.sources.referenceLinks[0].href);

  let sortOrder = 1;

  return examData.sections.flatMap((section) =>
    section.questions.map((question) => {
      const pitfallNotes = [question.pitfall, question.source].filter(Boolean);

      return {
        exam_key: "kaisei-2026-math",
        subject: "算数",
        section_id: section.id,
        section_title: section.title,
        problem_code: toProblemCode(question.id),
        display_id: question.id,
        sort_order: sortOrder++,
        source: {
          question_pdf: questionPdf,
          answer_pdf: answerPdf,
          page_images: section.pages.map((page) => ({
            label: page.label,
            path: pathFromSiteHref(page.src),
          })),
          answer_images: [
            {
              label: examData.sources.referenceLinks[0].label,
              path: answerImage,
            },
          ],
          verification: question.verdict,
        },
        source_pack: {
          prompt_summary: question.prompt,
          official_answer: question.official,
          verified_answer: question.verified,
          explanation_summary: question.explanation,
          knowledge_points: question.knowledge ?? [],
          method_outline: question.how ?? [],
          reasoning_why: question.why ?? "",
          lesson_points: question.lesson ?? [],
          ocr_notes: pitfallNotes,
          problem_core: question.problemCore ?? "",
          learning_map_hint: {
            main_unit: question.mainUnit ?? "",
            supporting_units: question.supportingUnits ?? [],
            cross_skills: question.crossSkills ?? [],
            advanced_labels: question.advancedLabels ?? [],
          },
        },
      };
    }),
  );
}

function normalizeSecondaryLabels(labels) {
  return (labels ?? []).map((label) => ({
    code: label.code,
    name: label.name,
  }));
}

function mergeRecords(roster, manual) {
  const manualById = new Map(manual.records.map((record) => [record.display_id, record]));

  if (manualById.size !== roster.length) {
    throw new Error(
      `manual-labels count mismatch: expected ${roster.length}, got ${manualById.size}`,
    );
  }

  return roster.map((record) => {
    const manualRecord = manualById.get(record.display_id);

    if (!manualRecord) {
      throw new Error(`Missing manual labels for ${record.display_id}`);
    }

    if (!manualRecord.search_labels?.primary_label?.code) {
      throw new Error(`Missing primary label code for ${record.display_id}`);
    }

    if (!manualRecord.search_labels?.difficulty?.level) {
      throw new Error(`Missing difficulty for ${record.display_id}`);
    }

    return {
      exam_key: record.exam_key,
      subject: record.subject,
      problem_code: record.problem_code,
      display_id: record.display_id,
      sort_order: record.sort_order,
      section_id: record.section_id,
      section_title: record.section_title,
      status: manualRecord.status ?? manual.status ?? "draft",
      source: record.source,
      search_labels: {
        primary_label: {
          code: manualRecord.search_labels.primary_label.code,
          name: manualRecord.search_labels.primary_label.name,
        },
        secondary_labels: normalizeSecondaryLabels(
          manualRecord.search_labels.secondary_labels,
        ),
        difficulty: {
          level: manualRecord.search_labels.difficulty.level,
          scale: manualRecord.search_labels.difficulty.scale ?? "exam_math_5_v1",
        },
        confidence: manualRecord.search_labels.confidence,
        rationale: manualRecord.search_labels.rationale,
        uncertainty: manualRecord.search_labels.uncertainty ?? "",
      },
      learning_map: manualRecord.learning_map ?? record.source_pack.learning_map_hint,
      evidence: {
        problem_core: record.source_pack.problem_core,
        official_answer: record.source_pack.official_answer,
        notes: [
          `verified: ${record.source_pack.verified_answer}`,
          record.source_pack.explanation_summary,
          ...record.source_pack.ocr_notes,
        ]
          .filter(Boolean)
          .join(" | "),
      },
      review: manualRecord.review ?? {
        verdict: "agree",
        notes: "",
        residual_uncertainty: "",
      },
    };
  });
}

function buildIssues(records, manual) {
  const issues = [];

  for (const record of records) {
    const residual = record.review.residual_uncertainty?.trim();

    if (record.review.verdict === "adjust") {
      issues.push({
        display_id: record.display_id,
        kind: "review_adjustment",
        note: record.review.notes || "Reviewer requested an adjustment.",
      });
    }

    if (residual) {
      issues.push({
        display_id: record.display_id,
        kind: "review_residual_uncertainty",
        note: residual,
      });
    }
  }

  for (const issue of manual.global_issues ?? []) {
    issues.push(issue);
  }

  return issues;
}

function buildReviewDocument(examData, records, issues, manual) {
  const lines = [
    "# 開成中学校 2026 算数 ラベルレビュー",
    "",
    `- exam_key: \`kaisei-2026-math\``,
    `- status: \`${manual.status ?? "draft"}\``,
    `- taxonomy_namespace: \`${manual.taxonomy_namespace}\``,
    `- total_problems: \`${records.length}\``,
    `- source_page: \`data/published/sites/kaisei-2026-math/index.html\``,
    "",
    examData.description ?? "",
    "",
    "## Review Table",
    "",
    "| display_id | primary | secondary | difficulty | confidence | main_unit | advanced_labels | uncertainty |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
  ];

  for (const record of records) {
    const secondary = record.search_labels.secondary_labels
      .map((label) => label.name)
      .join(", ");
    const advanced = (record.learning_map.advanced_labels ?? []).join(", ");

    lines.push(
      `| ${record.display_id} | ${record.search_labels.primary_label.name} | ${secondary} | ${record.search_labels.difficulty.level} | ${record.search_labels.confidence} | ${record.learning_map.main_unit} | ${advanced} | ${record.search_labels.uncertainty || ""} |`,
    );
  }

  lines.push("", "## Issues", "");

  if (issues.length === 0) {
    lines.push("- なし");
  } else {
    for (const issue of issues) {
      lines.push(`- ${issue.display_id}: ${issue.kind} - ${issue.note}`);
    }
  }

  lines.push("", "## Spot Check Candidates", "");

  for (const candidate of manual.spot_check_candidates ?? []) {
    lines.push(`- ${candidate}`);
  }

  lines.push("");

  return `${lines.join("\n")}\n`;
}

function main() {
  if (!fs.existsSync(manualLabelsPath)) {
    throw new Error(`Missing manual labels file: ${manualLabelsPath}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const examData = extractExamData(sourceHtmlPath);
  const roster = flattenQuestions(examData);
  const manual = readJson(manualLabelsPath);
  const reviewRecords = mergeRecords(roster, manual);
  const issues = buildIssues(reviewRecords, manual);

  if (reviewRecords.length !== 15) {
    throw new Error(`Expected 15 review records, got ${reviewRecords.length}`);
  }

  writeJson(path.join(outputDir, "roster.json"), roster);
  writeJson(path.join(outputDir, "source-packs.json"), roster.map((record) => ({
    display_id: record.display_id,
    problem_code: record.problem_code,
    sort_order: record.sort_order,
    section_id: record.section_id,
    section_title: record.section_title,
    source: record.source,
    source_pack: record.source_pack,
  })));
  writeJson(path.join(outputDir, "review.json"), {
    metadata: {
      exam_key: "kaisei-2026-math",
      subject: "算数",
      status: manual.status ?? "draft",
      taxonomy_namespace: manual.taxonomy_namespace,
      generated_from: "data/published/sites/kaisei-2026-math/index.html",
      total_problems: reviewRecords.length,
    },
    records: reviewRecords,
    issues,
  });
  fs.writeFileSync(
    path.join(outputDir, "review.md"),
    buildReviewDocument(examData, reviewRecords, issues, manual),
    "utf8",
  );
}

main();
