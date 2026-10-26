CREATE TABLE IF NOT EXISTS job_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL UNIQUE,
  source_type text NOT NULL, base_url text, polling_tier text NOT NULL,
  last_polled_at timestamptz, next_poll_at timestamptz, enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  provider_message_id text NOT NULL, thread_id text NOT NULL, sender text NOT NULL,
  recipients jsonb NOT NULL, subject text NOT NULL, safe_body text NOT NULL,
  received_at timestamptz NOT NULL, raw_reference text, UNIQUE(user_id, provider_message_id)
);
CREATE TABLE IF NOT EXISTS email_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  email_id uuid REFERENCES emails(id), action_type text NOT NULL, status text NOT NULL,
  idempotency_key text NOT NULL UNIQUE, provider_result_id text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS calendar_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  provider_event_id text, title text NOT NULL, starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
  attendees jsonb NOT NULL DEFAULT '[]', status text NOT NULL, source_reference text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS repositories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  path text NOT NULL, remote_url text, default_branch text, instruction_hash text,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id, path)
);
CREATE TABLE IF NOT EXISTS coding_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  repository_id uuid NOT NULL REFERENCES repositories(id), goal text NOT NULL, status text NOT NULL,
  branch text, base_commit text, final_diff_hash text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS git_operations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  repository_id uuid NOT NULL REFERENCES repositories(id), operation text NOT NULL,
  local_commit text, remote_commit text, status text NOT NULL, approval_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pull_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  repository_id uuid NOT NULL REFERENCES repositories(id), provider_number integer,
  provider_url text, status text NOT NULL, head_commit text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pr_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), pull_request_id uuid NOT NULL REFERENCES pull_requests(id),
  provider_comment_id text, body_hash text NOT NULL, status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(pull_request_id, body_hash)
);
CREATE TABLE IF NOT EXISTS content_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  platform text NOT NULL, title text NOT NULL, body text NOT NULL, claims jsonb NOT NULL DEFAULT '[]',
  status text NOT NULL DEFAULT 'draft', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS video_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  title text NOT NULL, platform text NOT NULL, composition jsonb NOT NULL,
  render_evidence jsonb, status text NOT NULL DEFAULT 'storyboard', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS publication_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  content_project_id uuid REFERENCES content_projects(id), video_project_id uuid REFERENCES video_projects(id),
  platform text NOT NULL, provider_post_id text, provider_url text, status text NOT NULL,
  idempotency_key text NOT NULL UNIQUE, published_at timestamptz
);
CREATE TABLE IF NOT EXISTS learning_goals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  title text NOT NULL, target_date timestamptz, status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS study_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  learning_goal_id uuid REFERENCES learning_goals(id), objective text NOT NULL, exercise text NOT NULL,
  completion_criteria jsonb NOT NULL, score numeric, status text NOT NULL,
  scheduled_at timestamptz, completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS interview_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  mode text NOT NULL, role_type text NOT NULL, evaluation jsonb,
  started_at timestamptz NOT NULL, completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS workflow_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  workflow_type text NOT NULL, idempotency_key text NOT NULL UNIQUE, status text NOT NULL,
  retry_class text NOT NULL, maximum_attempts integer NOT NULL, attempt_count integer NOT NULL DEFAULT 0,
  timeout_seconds integer NOT NULL, approval_id uuid, compensation_action text,
  verification_state text NOT NULL, failure_reason text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS credentials_metadata (
  id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id), provider text NOT NULL,
  account_label text NOT NULL, scopes jsonb NOT NULL DEFAULT '[]', status text NOT NULL,
  expires_at timestamptz, last_accessed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS source_citations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
  source_type text NOT NULL, source_reference text NOT NULL, title text, excerpt text,
  published_at timestamptz, retrieved_at timestamptz NOT NULL DEFAULT now(), content_hash text
);

CREATE INDEX IF NOT EXISTS emails_user_thread_idx ON emails(user_id, thread_id, received_at);
CREATE INDEX IF NOT EXISTS calendar_user_time_idx ON calendar_events(user_id, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS workflow_user_status_idx ON workflow_runs(user_id, status, updated_at);
CREATE INDEX IF NOT EXISTS citations_user_source_idx ON source_citations(user_id, source_type);
