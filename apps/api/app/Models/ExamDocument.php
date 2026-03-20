<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ExamDocument extends Model
{
    /** @use HasFactory<\Database\Factories\ExamDocumentFactory> */
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'exam_id',
        'document_kind',
        'pdf_name',
        'source_pdf_path',
        'relative_source_pdf',
        'relative_image_dir',
        'full_text_path',
        'ocr_backend',
        'page_count',
    ];

    /**
     * Get the exam that owns the document.
     */
    public function exam(): BelongsTo
    {
        return $this->belongsTo(Exam::class);
    }

    /**
     * Get the OCR pages for the document.
     */
    public function pages(): HasMany
    {
        return $this->hasMany(DocumentPage::class, 'document_id');
    }
}
