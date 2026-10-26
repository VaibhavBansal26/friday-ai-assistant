CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE fact_provenance AS ENUM ('verified_fact','retrieved_fact','user_provided_fact','inference','recommendation','unknown');
CREATE TYPE approval_status AS ENUM ('pending','approved_once','approved_session','rejected','expired');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO users (id) VALUES ('00000000-0000-4000-8000-000000000001')
ON CONFLICT (id) DO NOTHING;
CREATE TABLE user_profiles (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  display_name text,
  timezone text NOT NULL DEFAULT 'UTC',
  preferences jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE verified_facts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  namespace text NOT NULL, fact_key text NOT NULL, value jsonb NOT NULL,
  provenance fact_provenance NOT NULL, source_id uuid, verified_at timestamptz,
  expires_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, namespace, fact_key)
);
CREATE TABLE tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  title text NOT NULL, description text, status text NOT NULL DEFAULT 'inbox',
  priority text NOT NULL DEFAULT 'medium', category text NOT NULL DEFAULT 'general',
  due_at timestamptz, scheduled_start timestamptz, dependency_ids uuid[] NOT NULL DEFAULT '{}',
  completion_criteria jsonb NOT NULL DEFAULT '[]', created_by text NOT NULL,
  assigned_agent text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  name text NOT NULL, status text NOT NULL DEFAULT 'active', goal text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ideas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  problem text, target_user text, proposed_solution text, assumptions jsonb NOT NULL DEFAULT '[]',
  evidence jsonb NOT NULL DEFAULT '[]', risks jsonb NOT NULL DEFAULT '[]', decision_log jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), external_id text, source text NOT NULL, source_url text NOT NULL,
  canonical_apply_url text, company text NOT NULL, title text NOT NULL, description text NOT NULL,
  normalized jsonb NOT NULL DEFAULT '{}', published_at timestamptz, first_seen_at timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL, active boolean NOT NULL DEFAULT true, fingerprint text NOT NULL UNIQUE,
  raw_payload jsonb NOT NULL
);
CREATE TABLE job_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), job_id uuid NOT NULL REFERENCES jobs(id),
  scores jsonb NOT NULL, hard_disqualifiers jsonb NOT NULL DEFAULT '[]', missing_required jsonb NOT NULL DEFAULT '[]',
  recommended_resume_version_id uuid, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id, job_id)
);
CREATE TABLE applications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), job_id uuid NOT NULL REFERENCES jobs(id),
  status text NOT NULL DEFAULT 'draft', idempotency_key text NOT NULL UNIQUE, resume_version_id uuid,
  provider_confirmation_id text, provider_state text, submitted_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE resume_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), label text NOT NULL,
  content jsonb NOT NULL, source_version_id uuid REFERENCES resume_versions(id), approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE resume_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), resume_version_id uuid NOT NULL REFERENCES resume_versions(id) ON DELETE CASCADE,
  claim_text text NOT NULL, verified_fact_id uuid NOT NULL REFERENCES verified_facts(id), transformation_note text
);
CREATE TABLE approval_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), requesting_agent text NOT NULL,
  action text NOT NULL, target text NOT NULL, risk_level smallint NOT NULL CHECK (risk_level BETWEEN 0 AND 4),
  data_transmitted jsonb NOT NULL DEFAULT '[]', reversible boolean NOT NULL, expected_outcome text NOT NULL,
  preview jsonb NOT NULL DEFAULT '{}', status approval_status NOT NULL DEFAULT 'pending',
  idempotency_key text NOT NULL UNIQUE, decided_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), session_id uuid,
  event_type text NOT NULL, actor text NOT NULL, target_type text, target_id text,
  safe_payload jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE tool_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id), action_id uuid,
  tool_name text NOT NULL, status text NOT NULL, provider_result_id text, provider_result_url text,
  safe_result jsonb NOT NULL DEFAULT '{}', error_code text, started_at timestamptz NOT NULL, finished_at timestamptz
);
CREATE TABLE verification_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), action_id uuid NOT NULL, verified boolean NOT NULL,
  outcome text NOT NULL, evidence_tool_run_ids uuid[] NOT NULL DEFAULT '{}', missing_evidence jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_active_seen_idx ON jobs(active, last_seen_at DESC);
CREATE INDEX tasks_user_status_idx ON tasks(user_id, status, due_at);
CREATE INDEX audit_user_created_idx ON audit_events(user_id, created_at DESC);
