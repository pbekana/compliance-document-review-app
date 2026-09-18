ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS cloudinary_public_id VARCHAR(500);