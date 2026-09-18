-- Migration: dominium_registration_v2
-- Adds contact_email, rejection fields, and 'rejected' status value to dominium_profiles.
-- Do NOT modify 20260917202620_dominium_auth_schema.sql — this migration extends it.

-- 1. Add contact_email (optional, metadata only — never used as Supabase Auth credential)
ALTER TABLE public.dominium_profiles
    ADD COLUMN IF NOT EXISTS contact_email TEXT;

-- 2. Add rejection audit columns
ALTER TABLE public.dominium_profiles
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;

ALTER TABLE public.dominium_profiles
    ADD COLUMN IF NOT EXISTS rejected_by BIGINT REFERENCES public.dominium_profiles(id);

ALTER TABLE public.dominium_profiles
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- 3. Extend status CHECK to include 'rejected'
--    PostgreSQL does not support ALTER CONSTRAINT directly; drop and re-add.
ALTER TABLE public.dominium_profiles
    DROP CONSTRAINT IF EXISTS dominium_profiles_status_check;

ALTER TABLE public.dominium_profiles
    ADD CONSTRAINT dominium_profiles_status_check
    CHECK (status IN ('pending', 'active', 'disabled', 'rejected'));
