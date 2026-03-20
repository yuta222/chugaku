PRAGMA foreign_keys = ON;

CREATE TABLE schools (
    school_id INTEGER PRIMARY KEY,
    school_name TEXT NOT NULL UNIQUE,
    prefecture TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exams (
    exam_id INTEGER PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES schools (school_id) ON DELETE RESTRICT,
    exam_year INTEGER NOT NULL CHECK (exam_year >= 1900),
    subject TEXT NOT NULL CHECK (subject IN ('算数', '国語', '理科', '社会', 'その他')),
    exam_round TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT 'yotsuya_otsuka',
    external_exam_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (school_id, exam_year, subject, exam_round)
);

CREATE INDEX idx_exams_school_year_subject
    ON exams (school_id, exam_year, subject, exam_round);

CREATE TABLE exam_documents (
    document_id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams (exam_id) ON DELETE CASCADE,
    document_kind TEXT NOT NULL CHECK (document_kind IN ('問題', '回答', '解説', 'その他')),
    pdf_name TEXT NOT NULL,
    source_pdf_path TEXT,
    relative_source_pdf TEXT,
    relative_image_dir TEXT,
    full_text_path TEXT,
    ocr_backend TEXT,
    page_count INTEGER NOT NULL DEFAULT 0 CHECK (page_count >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exam_id, document_kind, pdf_name)
);

CREATE INDEX idx_exam_documents_exam_kind
    ON exam_documents (exam_id, document_kind);

CREATE TABLE document_pages (
    page_id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES exam_documents (document_id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL CHECK (page_no >= 1),
    image_path TEXT,
    text_path TEXT,
    ocr_json_path TEXT,
    page_text TEXT NOT NULL DEFAULT '',
    char_count INTEGER NOT NULL DEFAULT 0 CHECK (char_count >= 0),
    line_count INTEGER NOT NULL DEFAULT 0 CHECK (line_count >= 0),
    avg_confidence REAL CHECK (
        avg_confidence IS NULL OR (avg_confidence >= 0.0 AND avg_confidence <= 1.0)
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, page_no)
);

CREATE INDEX idx_document_pages_document_page
    ON document_pages (document_id, page_no);

CREATE TABLE taxonomy_versions (
    taxonomy_version_id INTEGER PRIMARY KEY,
    version_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'retired')),
    activated_at TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE taxonomy_nodes (
    taxonomy_node_id INTEGER PRIMARY KEY,
    taxonomy_version_id INTEGER NOT NULL REFERENCES taxonomy_versions (taxonomy_version_id) ON DELETE CASCADE,
    parent_node_id INTEGER REFERENCES taxonomy_nodes (taxonomy_node_id) ON DELETE RESTRICT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
    sort_key TEXT NOT NULL,
    is_assignable INTEGER NOT NULL DEFAULT 0 CHECK (is_assignable IN (0, 1)),
    is_other_bucket INTEGER NOT NULL DEFAULT 0 CHECK (is_other_bucket IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deprecated')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (taxonomy_version_id, code)
);

CREATE INDEX idx_taxonomy_nodes_parent
    ON taxonomy_nodes (parent_node_id);

CREATE INDEX idx_taxonomy_nodes_version_sort
    ON taxonomy_nodes (taxonomy_version_id, sort_key);

CREATE TABLE problems (
    problem_id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams (exam_id) ON DELETE CASCADE,
    parent_problem_id INTEGER REFERENCES problems (problem_id) ON DELETE CASCADE,
    problem_code TEXT NOT NULL,
    sort_order INTEGER NOT NULL CHECK (sort_order >= 1),
    display_title TEXT,
    problem_text TEXT,
    answer_text TEXT,
    explanation_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'published')),
    current_difficulty INTEGER CHECK (current_difficulty BETWEEN 1 AND 5),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exam_id, problem_code)
);

CREATE INDEX idx_problems_exam_sort
    ON problems (exam_id, sort_order);

CREATE INDEX idx_problems_parent
    ON problems (parent_problem_id);

CREATE TABLE problem_document_spans (
    problem_document_span_id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (problem_id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES exam_documents (document_id) ON DELETE CASCADE,
    span_role TEXT NOT NULL CHECK (span_role IN ('question', 'answer', 'explanation')),
    start_page INTEGER NOT NULL CHECK (start_page >= 1),
    end_page INTEGER NOT NULL CHECK (end_page >= start_page),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_problem_document_spans_problem
    ON problem_document_spans (problem_id);

CREATE INDEX idx_problem_document_spans_document
    ON problem_document_spans (document_id, start_page, end_page);

CREATE TABLE problem_labels (
    problem_label_id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (problem_id) ON DELETE CASCADE,
    taxonomy_node_id INTEGER NOT NULL REFERENCES taxonomy_nodes (taxonomy_node_id) ON DELETE RESTRICT,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    label_order INTEGER NOT NULL DEFAULT 1 CHECK (label_order >= 1),
    source_type TEXT NOT NULL CHECK (source_type IN ('human', 'llm', 'rule', 'imported')),
    source_detail TEXT,
    confidence REAL CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (problem_id, taxonomy_node_id)
);

CREATE INDEX idx_problem_labels_taxonomy
    ON problem_labels (taxonomy_node_id, is_primary);

CREATE UNIQUE INDEX idx_problem_labels_one_primary
    ON problem_labels (problem_id)
    WHERE is_primary = 1;

CREATE TABLE problem_difficulty_assessments (
    problem_difficulty_assessment_id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (problem_id) ON DELETE CASCADE,
    scale_code TEXT NOT NULL DEFAULT 'exam_math_5_v1',
    difficulty_level INTEGER NOT NULL CHECK (difficulty_level BETWEEN 1 AND 5),
    source_type TEXT NOT NULL CHECK (source_type IN ('human', 'llm', 'rule', 'imported')),
    source_detail TEXT,
    confidence REAL CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    ),
    rationale TEXT,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_problem_difficulty_problem_scale
    ON problem_difficulty_assessments (problem_id, scale_code, created_at DESC);

CREATE UNIQUE INDEX idx_problem_difficulty_one_current
    ON problem_difficulty_assessments (problem_id, scale_code)
    WHERE is_current = 1;

-- Optional:
-- 全文検索を DB に寄せるなら FTS5 を追加する。
-- CREATE VIRTUAL TABLE document_pages_fts
-- USING fts5(page_text, content='document_pages', content_rowid='page_id', tokenize='unicode61');
