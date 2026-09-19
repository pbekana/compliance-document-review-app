ALTER TABLE document_revisions
    ADD COLUMN IF NOT EXISTS cloudinary_public_id VARCHAR(500);
