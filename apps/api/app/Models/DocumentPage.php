<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class DocumentPage extends Model
{
    /** @use HasFactory<\Database\Factories\DocumentPageFactory> */
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'document_id',
        'page_no',
        'image_path',
        'text_path',
        'ocr_json_path',
        'page_text',
        'char_count',
        'line_count',
        'avg_confidence',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'avg_confidence' => 'float',
    ];

    /**
     * Get the document that owns the page.
     */
    public function document(): BelongsTo
    {
        return $this->belongsTo(ExamDocument::class, 'document_id');
    }
}
