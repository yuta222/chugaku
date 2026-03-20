<?php

namespace Tests\Feature;

use App\Models\DocumentPage;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class ImportPageTextIndexCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_links_relative_source_pdf_and_image_paths_via_documents(): void
    {
        $indexRoot = sys_get_temp_dir().DIRECTORY_SEPARATOR.'page-text-index-'.bin2hex(random_bytes(8));
        File::ensureDirectoryExists($indexRoot);
        $this->beforeApplicationDestroyed(fn () => File::deleteDirectory($indexRoot));

        File::put($indexRoot.DIRECTORY_SEPARATOR.'pdfs.jsonl', $this->jsonLine([
            'relative_image_dir' => '開成中学校/2025/問題/2025、算数、開成中学校、問題',
            'source_pdf' => '/tmp/source/2025-kaisei-math.pdf',
            'relative_source_pdf' => '開成中学校/2025/問題/2025、算数、開成中学校、問題.pdf',
            'school' => '開成中学校',
            'year' => '2025',
            'kind' => '問題',
            'pdf_name' => '2025、算数、開成中学校、問題',
            'page_count' => 1,
            'full_text_path' => '/tmp/source/full_text.txt',
            'backend' => 'swift-vision',
        ]));

        File::put($indexRoot.DIRECTORY_SEPARATOR.'pages.jsonl', $this->jsonLine([
            'school' => '開成中学校',
            'year' => '2025',
            'kind' => '問題',
            'pdf_name' => '2025、算数、開成中学校、問題',
            'source_pdf' => '/tmp/source/2025-kaisei-math.pdf',
            'relative_source_pdf' => '開成中学校/2025/問題/2025、算数、開成中学校、問題.pdf',
            'relative_image_dir' => '開成中学校/2025/問題/2025、算数、開成中学校、問題',
            'page' => 1,
            'image_path' => '/tmp/render/page-0001.png',
            'text_path' => '/tmp/render/page-0001.txt',
            'ocr_json_path' => '/tmp/render/page-0001.json',
            'char_count' => 123,
            'line_count' => 9,
            'avg_confidence' => 0.98765,
            'text' => '初回OCR',
        ]));

        $this->artisan('app:import-page-text-index', ['--index-root' => $indexRoot])
            ->expectsOutputToContain("Imported OCR index from {$indexRoot}")
            ->assertExitCode(0);

        File::put($indexRoot.DIRECTORY_SEPARATOR.'pages.jsonl', $this->jsonLine([
            'school' => '開成中学校',
            'year' => '2025',
            'kind' => '問題',
            'pdf_name' => '2025、算数、開成中学校、問題',
            'source_pdf' => '/tmp/source/2025-kaisei-math.pdf',
            'relative_source_pdf' => '開成中学校/2025/問題/2025、算数、開成中学校、問題.pdf',
            'relative_image_dir' => '開成中学校/2025/問題/2025、算数、開成中学校、問題',
            'page' => 1,
            'image_path' => '/tmp/render/page-0001-updated.png',
            'text_path' => '/tmp/render/page-0001.txt',
            'ocr_json_path' => '/tmp/render/page-0001.json',
            'char_count' => 456,
            'line_count' => 12,
            'avg_confidence' => 0.76543,
            'text' => '更新後OCR',
        ]));

        $this->artisan('app:import-page-text-index', ['--index-root' => $indexRoot])->assertExitCode(0);

        $page = DocumentPage::query()->with('document')->sole();

        $this->assertSame('/tmp/render/page-0001-updated.png', $page->image_path);
        $this->assertSame('更新後OCR', $page->page_text);
        $this->assertSame('開成中学校/2025/問題/2025、算数、開成中学校、問題.pdf', $page->document->relative_source_pdf);
        $this->assertSame('開成中学校/2025/問題/2025、算数、開成中学校、問題', $page->document->relative_image_dir);
        $this->assertDatabaseCount('exam_documents', 1);
        $this->assertDatabaseCount('document_pages', 1);
    }

    /**
     * @param  array<string, mixed>  $payload
     */
    private function jsonLine(array $payload): string
    {
        return json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES).PHP_EOL;
    }
}
