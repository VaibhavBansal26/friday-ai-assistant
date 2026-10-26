export type TaskStatus = "inbox" | "planned" | "in_progress" | "blocked" |
  "waiting" | "completed" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export type Task = {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  category: string;
  completion_criteria: string[];
  created_at: string;
  updated_at: string;
};

export type ApprovalStatus = "pending" | "approved_once" | "approved_session" |
  "rejected" | "expired";

export type Approval = {
  id: string;
  action_id: string;
  status: ApprovalStatus;
  scope: string;
  decided_by: string | null;
  decided_at: string | null;
};

export type ActionPreview = {
  action: {
    id: string;
    agent: string;
    action: string;
    target: string;
    risk: number;
    data_transmitted: string[];
    reversible: boolean;
    expected_outcome: string;
    preview: Record<string, unknown>;
  };
  approval: Approval | null;
  allowed: boolean;
  reason: string;
};

export type FridayNotification = {
  id: string;
  title: string;
  body: string;
  severity: "info" | "success" | "warning" | "error";
  category: string;
  target_path: string | null;
  read: boolean;
  dismissed: boolean;
  created_at: string;
};

export type UserSettings = {
  user_id: string;
  privacy_preference: "standard" | "sensitive_local_preferred" | "local_only";
  notifications_enabled: boolean;
  voice_enabled: boolean;
  voice_speed: number;
  reduced_motion: boolean;
  default_model_route: string;
  external_writes_enabled: false;
  memory_writes_require_approval: boolean;
  updated_at: string;
};
export type UserSettingsUpdate = Partial<Pick<UserSettings,
  "privacy_preference" | "notifications_enabled" | "voice_enabled" | "voice_speed" |
  "reduced_motion" | "default_model_route" | "memory_writes_require_approval">>;

export type AuditEvent = {
  id: string;
  event_type: string;
  actor: string;
  target_type: string | null;
  target_id: string | null;
  safe_payload: Record<string, unknown>;
  created_at: string;
};

export type Project = { id: string; name: string; goal: string | null; status: string; updated_at: string };
export type Idea = { id: string; problem: string; target_user: string | null; proposed_solution: string | null; risks: string[]; open_questions: string[]; updated_at: string };
export type VerifiedFact = { id: string; namespace: string; fact_key: string; value: unknown; provenance: string; source_id: string | null; verified_at: string | null };
export type MemoryProposal = { id: string; content: string; sensitivity: string; confidence: string; status: string; contradiction_ids: string[]; created_at: string };
export type JobPosting = { id: string; company: string; title: string; location: string | null; remote_type: string; published_at: string | null; first_seen_at: string; canonical_apply_url: string | null; source_url: string; alert_match: string | null; evidence: { gmail_url?: string; sender?: string; subject?: string; received_at?: string; source_excerpt?: string } };
export type JobAlertIngestionResult = { source: string; source_message_url: string; reported_count: number; parsed_count: number; created_count: number; deduplicated_count: number; shortlist: JobPosting[]; applications_submitted: 0 };
export type ResumeClaim = { id: string; claim_text: string; skills: string[]; verified_fact_id: string; created_at: string };
export type ApplicationDraft = { id: string; job: JobPosting; status: string; application_url: string; uploaded_files: string[]; created_at: string };
export type EmailThread = { id: string; messages: Array<{ id: string; sender: string; subject: string; received_at: string }> };
export type EmailReplyDraft = { id: string; thread_id: string; recipients: string[]; subject: string; body: string; status: string };
export type CalendarEvent = { id: string; title: string; starts_at: string; ends_at: string; status: string; attendees: string[] };
export type ContentDraft = { id: string; platform: string; title: string; body: string; status: string; target_account: string; created_at: string };
export type LinkedInStatus = { configured: boolean; connected: boolean; redirect_uri: string };
export type PublicationEvidence = { platform: string; post_id: string | null; public_url: string | null; status: string | null };
export type VideoProject = { id: string; title: string; platform: string; status: string; width: number; height: number; created_at: string };
export type VideoRenderEvidence = { project_id: string; output_path: string; width: number; height: number; duration_seconds: number; fps: number; audio_stream_present: boolean; captions_present: boolean };
export type DeviceEvidence = { action: string; target: string; exit_code: number; verified: boolean };
export type FileSearchResult = { path: string; name: string; size: number; mime_type: string | null };
export type FileReadResult = { path: string; content: string; size: number };
export type RepositoryContext = { root: string; branch: string | null; dirty: boolean; changed_files: string[]; instruction_files: string[] };
export type GitHubRepository = { name: string; name_with_owner: string; url: string; description: string | null; is_private: boolean; cloned_path: string | null };
export type GitOperationEvidence = { operation: string; local_commit: string | null; remote_commit: string | null; pull_request_url: string | null };
export type BrowserFormPreview = { preview: { url: string; resulting_url: string; filled_fields: Record<string, string>; submitted: boolean; screenshot_path: string }; approval: Approval | null };
export type BrowserFormResult = { url: string; resulting_url: string; filled_fields: Record<string, string>; submitted: boolean; confirmation_detected: boolean; screenshot_path: string; verified: boolean };
export type LearningConcept = { id: string; name: string; status: string; confidence: string; accuracy: number | null; next_review_at: string | null };
export type Attachment = { id: string; name: string; kind: "image" | "video" | "document"; content_type: string; size: number; path: string };

const API_BASE = import.meta.env.VITE_FRIDAY_API_URL ?? "http://127.0.0.1:8000/v1";
const LOCAL_USER_ID = "00000000-0000-4000-8000-000000000001";
let sessionGrant: { sessionId: string; token: string } | null = null;

async function ensureSession(): Promise<{ sessionId: string; token: string }> {
  if (sessionGrant) return sessionGrant;
  let response: Response | null = null;
  let lastError: unknown = null;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      response = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user_id: LOCAL_USER_ID }),
      });
      break;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => window.setTimeout(resolve, 350));
    }
  }
  if (!response) {
    const reason = lastError instanceof Error ? lastError.message : "local API unavailable";
    throw new Error(`Friday could not start its conversation service: ${reason}`);
  }
  if (!response.ok) throw new Error(`Friday session bootstrap failed (${response.status})`);
  const grant = await response.json() as { session: { id: string }; token: string };
  sessionGrant = { sessionId: grant.session.id, token: grant.token };
  return sessionGrant;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const grant = await ensureSession();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-friday-session": grant.sessionId,
      authorization: `Bearer ${grant.token}`,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`Friday API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function exchangeRealtimeOffer(sdp: string): Promise<string> {
  const grant = await ensureSession();
  const response = await fetch(`${API_BASE}/voice/realtime/session`, {
    method: "POST",
    headers: {
      "content-type": "application/sdp",
      "x-friday-session": grant.sessionId,
      authorization: `Bearer ${grant.token}`,
    },
    body: sdp,
  });
  if (!response.ok) {
    if (response.status === 402) throw new Error("Voice is ready, but the OpenAI API project needs credits or a higher spend limit.");
    let detail = "";
    try { detail = String((await response.json() as { detail?: string }).detail ?? ""); } catch { /* provider did not return JSON */ }
    throw new Error(detail || `Friday voice connection failed (${response.status})`);
  }
  return response.text();
}

async function uploadAttachment(file: File): Promise<Attachment> {
  const grant = await ensureSession();
  const response = await fetch(`${API_BASE}/attachments`, {
    method: "POST",
    headers: { "content-type": file.type || "application/octet-stream", "x-friday-filename": file.name, "x-friday-session": grant.sessionId, authorization: `Bearer ${grant.token}` },
    body: file,
  });
  if (!response.ok) throw new Error(`Attachment upload failed (${response.status})`);
  return response.json() as Promise<Attachment>;
}

export const api = {
  exchangeRealtimeOffer,
  uploadAttachment,
  listTasks: () => request<Task[]>("/tasks"),
  createTask: (title: string) => request<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify({ title, priority: "medium", category: "general" }),
  }),
  updateTask: (id: string, changes: Partial<Pick<Task, "status" | "priority" | "title">>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  listApprovals: () => request<Approval[]>("/approvals"),
  decideApproval: (id: string, status: "approved_once" | "rejected", userId: string) =>
    request<Approval>(`/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ status, user_id: userId }),
    }),
  listNotifications: () => request<FridayNotification[]>("/notifications"),
  markNotificationRead: (id: string) =>
    request<FridayNotification>(`/notifications/${id}/read`, { method: "POST" }),
  getSettings: () => request<UserSettings>("/settings"),
  updateSettings: (changes: UserSettingsUpdate) =>
    request<UserSettings>("/settings", { method: "PATCH", body: JSON.stringify(changes) }),
  listAuditEvents: () => request<AuditEvent[]>("/audit-events"),
  listProjects: () => request<Project[]>("/projects"),
  listIdeas: () => request<Idea[]>("/ideas"),
  listFacts: () => request<VerifiedFact[]>("/facts"),
  listMemories: () => request<MemoryProposal[]>("/memories/proposals"),
  listJobs: () => request<JobPosting[]>("/jobs"),
  ingestTodayMicrosoftCareersAlert: () => request<JobAlertIngestionResult>("/jobs/gmail/microsoft-alerts/today", { method: "POST" }),
  listResumeClaims: () => request<ResumeClaim[]>("/resume/claims"),
  listApplicationDrafts: () => request<ApplicationDraft[]>("/applications/drafts"),
  listEmailThreads: () => request<EmailThread[]>("/email/threads"),
  createEmailReplyDraft: (threadId: string, body: string) => request<EmailReplyDraft>(`/email/threads/${encodeURIComponent(threadId)}/reply-drafts`, { method: "POST", body: JSON.stringify({ body }) }),
  createEmailDraft: (recipients: string[], subject: string, body: string) => request<EmailReplyDraft>("/email/drafts", { method: "POST", body: JSON.stringify({ recipients, subject, body }) }),
  listEmailDrafts: () => request<EmailReplyDraft[]>("/email/drafts"),
  previewEmailSend: (draftId: string) => request<ActionPreview>(`/email/drafts/${draftId}/send-preview`, { method: "POST" }),
  sendEmailDraft: (draftId: string, approvalId: string) => request<{message_id:string;thread_id:string;status:string;recipient:string}>(`/email/drafts/${draftId}/send/${approvalId}`, { method: "POST" }),
  gmailStatus: () => request<{ configured: boolean; connected: boolean }>("/oauth/gmail/status"),
  configureGmail: (clientSecret: string) => request<{ configured: boolean; connected: boolean }>("/oauth/gmail/configure", { method: "POST", body: JSON.stringify({ client_secret: clientSecret }) }),
  gmailAuthorizationUrl: () => `${API_BASE}/oauth/gmail/start`,
  syncGmail: () => request<EmailThread[]>("/email/gmail/sync", { method: "POST" }),
  listCalendarEvents: () => request<CalendarEvent[]>("/calendar/events"),
  listContentDrafts: () => request<ContentDraft[]>("/content/drafts"),
  composeLinkedIn: (input: { topic: string; audience: string; key_points: string[]; call_to_action: string; tone: string }) => request<ContentDraft>("/content/linkedin/compose", { method: "POST", body: JSON.stringify({ ...input, target_account: "personal" }) }),
  previewContentPublish: (id: string) => request<ActionPreview>(`/content/drafts/${id}/publish-preview`, { method: "POST" }),
  linkedInStatus: () => request<LinkedInStatus>("/oauth/linkedin/status"),
  configureLinkedIn: (input: { client_id: string; client_secret: string; redirect_uri: string; author_urn?: string }) => request<LinkedInStatus>("/oauth/linkedin/configure", { method: "POST", body: JSON.stringify(input) }),
  linkedInAuthorizationUrl: () => `${API_BASE}/oauth/linkedin/start`,
  publishLinkedIn: (draftId: string, approvalId: string) => request<PublicationEvidence>(`/content/drafts/${draftId}/publish/${approvalId}`, { method: "POST" }),
  listVideoProjects: () => request<VideoProject[]>("/video/projects"),
  createVideoProject: (title: string, narration: string) => request<VideoProject>("/video/projects", {
    method: "POST",
    body: JSON.stringify({
      title,
      platform: "linkedin",
      aspect_ratio: "1:1",
      width: 1080,
      height: 1080,
      fps: 30,
      voice_provider: "local",
      scenes: [{ index: 0, narration, visual_description: title, duration_seconds: 5, asset_ids: [] }],
    }),
  }),
  renderVideoProject: (id: string) => request<VideoRenderEvidence>(`/video/projects/${id}/render-local`, { method: "POST" }),
  openApp: (appName: string) => request<DeviceEvidence>("/device/apps/open", { method: "POST", body: JSON.stringify({ app_name: appName }) }),
  controlMedia: (appName: string, command: "play_pause" | "next" | "previous") => request<DeviceEvidence>("/device/media/control", { method: "POST", body: JSON.stringify({ app_name: appName, command }) }),
  searchSpotify: (query: string) => request<DeviceEvidence>("/device/spotify/search", { method: "POST", body: JSON.stringify({ query }) }),
  readWebPage: (url: string) => request<{ url: string; title: string; text: string }>("/browser/read", { method: "POST", body: JSON.stringify({ url }) }),
  searchFiles: (query: string) => request<FileSearchResult[]>(`/files/search?query=${encodeURIComponent(query)}`),
  readFile: (path: string) => request<FileReadResult>("/files/read", { method: "POST", body: JSON.stringify({ path }) }),
  inspectRepository: () => request<RepositoryContext>("/coding/repository"),
  listGitHubRepositories: () => request<GitHubRepository[]>("/github/repositories"),
  cloneGitHubRepository: (repository: string) => request<GitHubRepository>("/github/repositories/clone", { method: "POST", body: JSON.stringify({ repository }) }),
  previewGitHubRepositoryCreate: (name:string, description:string, visibility:"private"|"public") => request<ActionPreview>("/github/repositories/create-preview", { method:"POST", body:JSON.stringify({name,description,visibility}) }),
  createGitHubRepository: (approvalId:string) => request<GitHubRepository>(`/github/repositories/create/${approvalId}`, { method:"POST" }),
  codingTree: (path:string) => request<{root:string;entries:Array<{path:string;kind:string;size:number}>}>("/coding/tree",{method:"POST",body:JSON.stringify({path})}),
  createCodingFile: (root:string,relativePath:string,content:string) => request<{path:string;relative_path:string;bytes:number;created:boolean}>("/coding/files",{method:"POST",body:JSON.stringify({root,relative_path:relativePath,content})}),
  saveCodingFile: (root:string,relativePath:string,content:string) => request<{path:string;relative_path:string;bytes:number;created:boolean;edited:boolean}>("/coding/files",{method:"PUT",body:JSON.stringify({root,relative_path:relativePath,content})}),
  openCodingFolder: (path:string) => request<{path:string;opened:boolean}>("/coding/folders/open",{method:"POST",body:JSON.stringify({path})}),
  selectCodingWorkspace: (path:string) => request<{path:string;selected:boolean}>("/coding/workspace/select",{method:"POST",body:JSON.stringify({path})}),
  openWorkspaceVSCode: () => request<{path:string;opened:boolean;application:string}>("/coding/workspace/open-vscode",{method:"POST"}),
  openFileVSCode: (root:string,relativePath:string) => request<{path:string;relative_path:string;opened:boolean;application:string}>("/coding/files/open-vscode",{method:"POST",body:JSON.stringify({root,relative_path:relativePath})}),
  readCodingFile: (root:string,relativePath:string) => request<{path:string;relative_path:string;content:string;bytes:number}>("/coding/files/read",{method:"POST",body:JSON.stringify({root,relative_path:relativePath})}),
  replaceCodingFileText: (root:string,relativePath:string,oldText:string,newText:string) => request<{path:string;relative_path:string;edited:boolean;bytes:number;replacements:number}>("/coding/files",{method:"PATCH",body:JSON.stringify({root,relative_path:relativePath,old_text:oldText,new_text:newText})}),
  runWorkspaceCommand: (command:string[]) => request<{command:string[];cwd:string;exit_code:number;stdout:string;stderr:string;verified:boolean}>("/coding/workspace/command",{method:"POST",body:JSON.stringify({command})}),
  previewGitPush: () => request<ActionPreview>("/coding/git/push-preview",{method:"POST"}),
  executeGitPush: (approvalId:string) => request<{root:string;branch:string;local_commit:string;remote_commit:string;verified:boolean}>(`/coding/git/push/${approvalId}`,{method:"POST"}),
  commitFiles: (message: string, paths: string[]) => request<GitOperationEvidence>("/coding/git/commit", { method: "POST", body: JSON.stringify({ message, paths }) }),
  previewBrowserForm: (url: string, fields: Record<string, string>, submitSelector: string, idempotencyKey: string) => request<BrowserFormPreview>("/browser/forms/preview", { method: "POST", body: JSON.stringify({ url, fields, submit_selector: submitSelector || null, idempotency_key: idempotencyKey }) }),
  submitBrowserForm: (approvalId: string) => request<BrowserFormResult>(`/browser/forms/${approvalId}/submit`, { method: "POST" }),
  listLearningConcepts: () => request<LearningConcept[]>("/learning/concepts"),
  createLearningConcept: (name: string) => request<LearningConcept>("/learning/concepts", { method: "POST", body: JSON.stringify({ name }) }),
};
