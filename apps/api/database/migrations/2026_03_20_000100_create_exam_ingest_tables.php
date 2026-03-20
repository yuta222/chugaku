<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('schools', function (Blueprint $table) {
            $table->id();
            $table->string('school_name')->unique();
            $table->string('prefecture')->nullable();
            $table->text('note')->nullable();
            $table->timestamps();
        });

        Schema::create('exams', function (Blueprint $table) {
            $table->id();
            $table->foreignId('school_id')->constrained()->restrictOnDelete();
            $table->unsignedSmallInteger('exam_year');
            $table->string('subject', 16);
            $table->string('exam_round')->default('');
            $table->string('source_system')->default('yotsuya_otsuka');
            $table->string('external_exam_key')->nullable();
            $table->timestamps();

            $table->unique(['school_id', 'exam_year', 'subject', 'exam_round']);
            $table->index(['school_id', 'exam_year', 'subject', 'exam_round']);
        });

        Schema::create('exam_documents', function (Blueprint $table) {
            $table->id();
            $table->foreignId('exam_id')->constrained()->cascadeOnDelete();
            $table->string('document_kind', 16);
            $table->string('pdf_name');
            $table->text('source_pdf_path')->nullable();
            $table->string('relative_source_pdf', 512)->nullable();
            $table->string('relative_image_dir', 512);
            $table->text('full_text_path')->nullable();
            $table->string('ocr_backend', 64)->nullable();
            $table->unsignedInteger('page_count')->default(0);
            $table->timestamps();

            $table->unique(['exam_id', 'document_kind', 'pdf_name']);
            $table->unique('relative_image_dir');
            $table->index(['exam_id', 'document_kind']);
            $table->index('relative_source_pdf');
        });

        Schema::create('document_pages', function (Blueprint $table) {
            $table->id();
            $table->foreignId('document_id')->constrained('exam_documents')->cascadeOnDelete();
            $table->unsignedInteger('page_no');
            $table->text('image_path')->nullable();
            $table->text('text_path')->nullable();
            $table->text('ocr_json_path')->nullable();
            $table->longText('page_text');
            $table->unsignedInteger('char_count')->default(0);
            $table->unsignedInteger('line_count')->default(0);
            $table->decimal('avg_confidence', 5, 4)->nullable();
            $table->timestamps();

            $table->unique(['document_id', 'page_no']);
            $table->index(['document_id', 'page_no']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('document_pages');
        Schema::dropIfExists('exam_documents');
        Schema::dropIfExists('exams');
        Schema::dropIfExists('schools');
    }
};
