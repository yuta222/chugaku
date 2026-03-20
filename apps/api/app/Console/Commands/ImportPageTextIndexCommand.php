<?php

namespace App\Console\Commands;

use App\Services\Import\PageTextIndexImportService;
use Illuminate\Console\Command;

class ImportPageTextIndexCommand extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'app:import-page-text-index
                            {--index-root= : OCR index root. Defaults to ../data/derived/page-text-index from the workspace root.}';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Import OCR page-text JSONL files into the ingest tables.';

    /**
     * Execute the console command.
     */
    public function handle(PageTextIndexImportService $importService): int
    {
        $indexRoot = (string) ($this->option('index-root') ?: $this->defaultIndexRoot());
        $summary = $importService->import($indexRoot);

        $this->info("Imported OCR index from {$indexRoot}");
        $this->table(
            ['Metric', 'Count'],
            [
                ['schools', $summary['schools']],
                ['exams', $summary['exams']],
                ['documents', $summary['documents']],
                ['pages', $summary['pages']],
                ['documents_processed', $summary['documents_processed']],
                ['pages_processed', $summary['pages_processed']],
            ],
        );

        return self::SUCCESS;
    }

    private function defaultIndexRoot(): string
    {
        return dirname(base_path(), 2).DIRECTORY_SEPARATOR.'data'.DIRECTORY_SEPARATOR.'derived'.DIRECTORY_SEPARATOR.'page-text-index';
    }
}
