<?php

namespace App\Services\Import;

use App\Models\DocumentPage;
use App\Models\Exam;
use App\Models\ExamDocument;
use App\Models\School;
use Generator;
use Illuminate\Support\Carbon;
use InvalidArgumentException;
use RuntimeException;
use SplFileObject;

class PageTextIndexImportService
{
    /**
     * @var list<string>
     */
    private const KNOWN_SUBJECTS = ['算数', '国語', '理科', '社会', 'その他'];

    /**
     * @var array<string, int>
     */
    private array $schoolIdsByName = [];

    /**
     * @var array<string, int>
     */
    private array $examIdsByKey = [];

    /**
     * @var array<string, int>
     */
    private array $documentIdsByImageDir = [];

    /**
     * Import OCR index files into the relational ingest tables.
     *
     * @return array<string, int>
     */
    public function import(string $indexRoot): array
    {
        $pdfsPath = $this->resolveIndexFile($indexRoot, 'pdfs.jsonl');
        $pagesPath = $this->resolveIndexFile($indexRoot, 'pages.jsonl');

        $documentsProcessed = 0;
        foreach ($this->readJsonl($pdfsPath) as [$lineNumber, $entry]) {
            $this->upsertDocument($this->normalizeDocumentEntry($entry, $lineNumber));
            $documentsProcessed++;
        }

        $pageRows = [];
        $pagesProcessed = 0;
        foreach ($this->readJsonl($pagesPath) as [$lineNumber, $entry]) {
            $pageRows[] = $this->makePageRow($entry, $lineNumber);
            $pagesProcessed++;

            if (count($pageRows) >= 1000) {
                $this->flushPages($pageRows);
                $pageRows = [];
            }
        }

        $this->flushPages($pageRows);

        return [
            'schools' => School::query()->count(),
            'exams' => Exam::query()->count(),
            'documents' => ExamDocument::query()->count(),
            'pages' => DocumentPage::query()->count(),
            'documents_processed' => $documentsProcessed,
            'pages_processed' => $pagesProcessed,
        ];
    }

    /**
     * @return Generator<int, array{0:int, 1:array<string, mixed>}, mixed, void>
     */
    private function readJsonl(string $path): Generator
    {
        $file = new SplFileObject($path, 'r');

        while (! $file->eof()) {
            $line = trim((string) $file->fgets());
            if ($line === '') {
                continue;
            }

            $decoded = json_decode($line, true);
            if (! is_array($decoded)) {
                throw new RuntimeException("Invalid JSONL at {$path}:{$file->key()}");
            }

            yield [$file->key(), $decoded];
        }
    }

    private function resolveIndexFile(string $indexRoot, string $fileName): string
    {
        $path = rtrim($indexRoot, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.$fileName;

        if (! is_file($path)) {
            throw new InvalidArgumentException("Index file not found: {$path}");
        }

        return $path;
    }

    /**
     * @param  array<string, mixed>  $entry
     * @return array<string, int|float|string|null>
     */
    private function normalizeDocumentEntry(array $entry, int $lineNumber): array
    {
        $pdfName = $this->requiredString($entry, 'pdf_name', $lineNumber);

        return [
            'school_name' => $this->requiredString($entry, 'school', $lineNumber),
            'exam_year' => $this->requiredInt($entry, 'year', $lineNumber),
            'subject' => $this->inferSubject($pdfName),
            'exam_round' => '',
            'source_system' => 'yotsuya_otsuka',
            'document_kind' => $this->requiredString($entry, 'kind', $lineNumber),
            'pdf_name' => $pdfName,
            'source_pdf_path' => $this->nullableString($entry['source_pdf'] ?? null),
            'relative_source_pdf' => $this->nullableString($entry['relative_source_pdf'] ?? null),
            'relative_image_dir' => $this->requiredString($entry, 'relative_image_dir', $lineNumber),
            'full_text_path' => $this->nullableString($entry['full_text_path'] ?? null),
            'ocr_backend' => $this->nullableString($entry['backend'] ?? null),
            'page_count' => $this->nullableInt($entry['page_count'] ?? null) ?? 0,
        ];
    }

    /**
     * @param  array<string, mixed>  $entry
     * @return array<string, mixed>
     */
    private function normalizePageEntry(array $entry, int $lineNumber): array
    {
        return [
            'relative_image_dir' => $this->requiredString($entry, 'relative_image_dir', $lineNumber),
            'page_no' => $this->requiredInt($entry, 'page', $lineNumber),
            'image_path' => $this->nullableString($entry['image_path'] ?? null),
            'text_path' => $this->nullableString($entry['text_path'] ?? null),
            'ocr_json_path' => $this->nullableString($entry['ocr_json_path'] ?? null),
            'page_text' => (string) ($entry['text'] ?? ''),
            'char_count' => $this->nullableInt($entry['char_count'] ?? null) ?? 0,
            'line_count' => $this->nullableInt($entry['line_count'] ?? null) ?? 0,
            'avg_confidence' => $this->nullableFloat($entry['avg_confidence'] ?? null),
        ];
    }

    /**
     * @param  array<string, mixed>  $entry
     */
    private function upsertDocument(array $entry): void
    {
        $schoolId = $this->resolveSchoolId($entry['school_name']);
        $examId = $this->resolveExamId(
            $schoolId,
            $entry['exam_year'],
            $entry['subject'],
            $entry['exam_round'],
            $entry['source_system'],
        );

        $document = ExamDocument::query()->updateOrCreate(
            [
                'exam_id' => $examId,
                'document_kind' => $entry['document_kind'],
                'pdf_name' => $entry['pdf_name'],
            ],
            [
                'source_pdf_path' => $entry['source_pdf_path'],
                'relative_source_pdf' => $entry['relative_source_pdf'],
                'relative_image_dir' => $entry['relative_image_dir'],
                'full_text_path' => $entry['full_text_path'],
                'ocr_backend' => $entry['ocr_backend'],
                'page_count' => $entry['page_count'],
            ],
        );

        $this->documentIdsByImageDir[$entry['relative_image_dir']] = (int) $document->getKey();
    }

    /**
     * @param  array<string, mixed>  $entry
     * @return array<string, Carbon|float|int|string|null>
     */
    private function makePageRow(array $entry, int $lineNumber): array
    {
        $normalized = $this->normalizePageEntry($entry, $lineNumber);
        $documentId = $this->resolveDocumentId($normalized['relative_image_dir']);
        $timestamp = now();

        return [
            'document_id' => $documentId,
            'page_no' => $normalized['page_no'],
            'image_path' => $normalized['image_path'],
            'text_path' => $normalized['text_path'],
            'ocr_json_path' => $normalized['ocr_json_path'],
            'page_text' => $normalized['page_text'],
            'char_count' => $normalized['char_count'],
            'line_count' => $normalized['line_count'],
            'avg_confidence' => $normalized['avg_confidence'],
            'created_at' => $timestamp,
            'updated_at' => $timestamp,
        ];
    }

    /**
     * @param  list<array<string, Carbon|float|int|string|null>>  $rows
     */
    private function flushPages(array $rows): void
    {
        if ($rows === []) {
            return;
        }

        DocumentPage::query()->upsert(
            $rows,
            ['document_id', 'page_no'],
            ['image_path', 'text_path', 'ocr_json_path', 'page_text', 'char_count', 'line_count', 'avg_confidence', 'updated_at'],
        );
    }

    private function resolveSchoolId(string $schoolName): int
    {
        if (isset($this->schoolIdsByName[$schoolName])) {
            return $this->schoolIdsByName[$schoolName];
        }

        $school = School::query()->firstOrCreate(['school_name' => $schoolName]);

        return $this->schoolIdsByName[$schoolName] = (int) $school->getKey();
    }

    private function resolveExamId(int $schoolId, int $examYear, string $subject, string $examRound, string $sourceSystem): int
    {
        $cacheKey = implode('|', [$schoolId, $examYear, $subject, $examRound]);
        if (isset($this->examIdsByKey[$cacheKey])) {
            return $this->examIdsByKey[$cacheKey];
        }

        $exam = Exam::query()->firstOrCreate(
            [
                'school_id' => $schoolId,
                'exam_year' => $examYear,
                'subject' => $subject,
                'exam_round' => $examRound,
            ],
            [
                'source_system' => $sourceSystem,
            ],
        );

        return $this->examIdsByKey[$cacheKey] = (int) $exam->getKey();
    }

    private function resolveDocumentId(string $relativeImageDir): int
    {
        if (isset($this->documentIdsByImageDir[$relativeImageDir])) {
            return $this->documentIdsByImageDir[$relativeImageDir];
        }

        $documentId = ExamDocument::query()
            ->where('relative_image_dir', $relativeImageDir)
            ->value('id');

        if (! is_numeric($documentId)) {
            throw new RuntimeException("Document not found for relative_image_dir: {$relativeImageDir}");
        }

        return $this->documentIdsByImageDir[$relativeImageDir] = (int) $documentId;
    }

    /**
     * @param  array<string, mixed>  $entry
     */
    private function requiredString(array $entry, string $key, int $lineNumber): string
    {
        $value = $this->nullableString($entry[$key] ?? null);
        if ($value === null) {
            throw new RuntimeException("Missing required field [{$key}] at line {$lineNumber}");
        }

        return $value;
    }

    private function nullableString(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }

        $string = trim((string) $value);

        return $string === '' ? null : $string;
    }

    /**
     * @param  array<string, mixed>  $entry
     */
    private function requiredInt(array $entry, string $key, int $lineNumber): int
    {
        $value = $this->nullableInt($entry[$key] ?? null);
        if ($value === null) {
            throw new RuntimeException("Missing required integer field [{$key}] at line {$lineNumber}");
        }

        return $value;
    }

    private function nullableInt(mixed $value): ?int
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (is_int($value)) {
            return $value;
        }

        if (is_numeric($value)) {
            return (int) $value;
        }

        return null;
    }

    private function nullableFloat(mixed $value): ?float
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (! is_numeric($value)) {
            return null;
        }

        return round((float) $value, 4);
    }

    private function inferSubject(string $pdfName): string
    {
        $parts = explode('、', $pdfName);
        $subject = $parts[1] ?? null;

        if (is_string($subject) && in_array($subject, self::KNOWN_SUBJECTS, true)) {
            return $subject;
        }

        return 'その他';
    }
}
