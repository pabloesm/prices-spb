-- Adds availability bookkeeping to scanned_products (see store_products_remote.py).
-- Additive and nullable: safe to apply while the previous code is still running.
ALTER TABLE scanned_products
    ADD COLUMN IF NOT EXISTS unavailable_since TIMESTAMP,
    ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP;
