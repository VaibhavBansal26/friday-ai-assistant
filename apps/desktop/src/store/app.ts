import { create } from "zustand";
import { api, type ApplicationDraft, type Approval, type AuditEvent, type CalendarEvent, type ContentDraft, type EmailThread, type FridayNotification, type Idea, type JobPosting, type LearningConcept, type MemoryProposal, type Project, type ResumeClaim, type Task, type UserSettings, type VerifiedFact, type VideoProject } from "../lib/api";
import { deliverGrantedNotifications } from "../lib/notifications";
import { RealtimeVoiceSession } from "../lib/voice";

const voiceSession = new RealtimeVoiceSession();

export type AssistantState = "idle" | "listening" | "understanding" | "thinking" |
  "acting" | "waiting for approval" | "speaking" | "completed" | "error";

type State = {
  activeSection: string;
  assistantState: AssistantState;
  transcript: string;
  userTranscript: string;
  voiceError: string | null;
  tasks: Task[];
  tasksState: "loading" | "ready" | "offline";
  approvals: Approval[];
  approvalsState: "loading" | "ready" | "offline";
  notifications: FridayNotification[];
  settings: UserSettings | null;
  auditEvents: AuditEvent[];
  projects: Project[];
  ideas: Idea[];
  jobs: JobPosting[];
  facts: VerifiedFact[];
  memories: MemoryProposal[];
  resumeClaims: ResumeClaim[];
  applicationDrafts: ApplicationDraft[];
  emailThreads: EmailThread[];
  calendarEvents: CalendarEvent[];
  contentDrafts: ContentDraft[];
  videoProjects: VideoProject[];
  learningConcepts: LearningConcept[];
  setActiveSection: (value: string) => void;
  setAssistantState: (value: AssistantState) => void;
  setTranscript: (value: string) => void;
  toggleVoiceCapture: () => Promise<void>;
  loadTasks: () => Promise<void>;
  createTask: (title: string) => Promise<void>;
  toggleTask: (task: Task) => Promise<void>;
  loadApprovals: () => Promise<void>;
  decideApproval: (approval: Approval, decision: "approved_once" | "rejected") => Promise<void>;
  loadNotifications: () => Promise<void>;
  loadSettings: () => Promise<void>;
  updateSettings: (changes: Parameters<typeof api.updateSettings>[0]) => Promise<void>;
  loadAuditEvents: () => Promise<void>;
  loadDomains: () => Promise<void>;
  loadWorkspaces: () => Promise<void>;
};

export const useAppStore = create<State>((set) => ({
  activeSection: "Home",
  assistantState: "idle",
  transcript: "",
  userTranscript: "Speak naturally when Friday shows Listening.",
  voiceError: null,
  tasks: [],
  tasksState: "loading",
  approvals: [],
  approvalsState: "loading",
  notifications: [],
  settings: null,
  auditEvents: [],
  projects: [],
  ideas: [],
  jobs: [],
  facts: [],
  memories: [],
  resumeClaims: [],
  applicationDrafts: [],
  emailThreads: [],
  calendarEvents: [],
  contentDrafts: [],
  videoProjects: [],
  learningConcepts: [],
  setActiveSection: (activeSection) => set({ activeSection }),
  setAssistantState: (assistantState) => set({ assistantState }),
  setTranscript: (transcript) => set({ transcript }),
  toggleVoiceCapture: async () => {
    const state = useAppStore.getState();
    try {
      if (state.assistantState === "listening") {
        voiceSession.stop();
        set({ assistantState: "idle", transcript: "Voice conversation ended", voiceError: null });
        return;
      }
      set({ assistantState: "understanding", transcript: "Connecting voice…", voiceError: null });
      await voiceSession.start(api.exchangeRealtimeOffer, (status, message) => {
        const assistantState = status === "connecting" ? "understanding" : status === "speaking" ? "speaking" : status === "error" ? "error" : status;
        set((current) => ({
          assistantState,
          transcript: message ?? current.transcript,
          voiceError: status === "error" ? message ?? "Voice connection failed" : null,
        }));
      }, async (call) => {
        if (call.name === "describe_friday_capabilities") {
          return { success: true, agents: ["supervisor","voice","task-manager","idea-partner","research","personal-memory","knowledge-retrieval","job-discovery","job-matching","company-research","resume-tailoring","job-application","email-summary","email-reply","calendar","coding","code-review","github","ci-debugging","website-builder","design","design-qa","content-strategy","medium","linkedin","x","instagram","youtube","video-production","publishing","learning","mock-interviewer","study-planner","verification","security-policy","notification","spotify","browser-use"], connected: { gmail: true, github: true, spotify: true }, setup_required: ["twitter/x publishing OAuth"], approval_required: ["email sending","social publishing","GitHub repository creation","browser form submission","job submission"] };
        }
        if (call.name === "create_youtube_short_project") {
          const project = await api.createVideoProject(String(call.arguments.title ?? "YouTube Short"), String(call.arguments.narration ?? ""));
          await useAppStore.getState().loadWorkspaces();
          set({ activeSection: "Video Studio", transcript: `YouTube Short project created: ${project.title}` });
          return { success: true, project_id: project.id, workspace: "Video Studio", format: "1080x1920", uploaded: false };
        }
        if (call.name === "analyze_current_repository") {
          const repository = await api.inspectRepository();
          set({ activeSection: "Coding", transcript: `Repository inspected: ${repository.changed_files.length} changed files` });
          return { success: true, root: repository.root, branch: repository.branch, dirty: repository.dirty, changed_files: repository.changed_files, modified: false };
        }
        if (call.name === "list_github_repositories") {
          const repositories = await api.listGitHubRepositories();
          set({ activeSection: "Coding", transcript: `Loaded ${repositories.length} GitHub repositories.` });
          return { success: true, count: repositories.length, repositories: repositories.slice(0, 100).map((item) => ({ name: item.name, url: item.url, private: item.is_private, cloned: Boolean(item.cloned_path) })), workspace: "Coding" };
        }
        if (call.name === "clone_github_repository") {
          const requested = String(call.arguments.repository ?? "");
          const repository = await api.cloneGitHubRepository(requested);
          set({ activeSection: "Coding", transcript: `Cloned ${repository.name_with_owner} to ${repository.cloned_path}` });
          return { success: true, repository: repository.name_with_owner, local_path: repository.cloned_path, verified: Boolean(repository.cloned_path) };
        }
        if (call.name === "open_local_coding_folder") {
          const result = await api.openCodingFolder(String(call.arguments.path ?? ""));
          set({ activeSection: "Coding", transcript: result.opened ? `Opened ${result.path} in Finder.` : `Could not open ${result.path}.` });
          return { success: result.opened, path: result.path, opened: result.opened, application: "Finder", verified: result.opened };
        }
        if (call.name === "visualize_repository_structure") {
          const tree = await api.codingTree(String(call.arguments.path ?? ""));
          set({ activeSection: "Coding", transcript: `Loaded ${tree.entries.length} repository paths.` });
          return { success: true, root: tree.root, entry_count: tree.entries.length, entries: tree.entries.slice(0, 500), workspace: "Coding" };
        }
        if (call.name === "save_file_in_repository") {
          const result=await api.saveCodingFile(String(call.arguments.root??""),String(call.arguments.relative_path??""),String(call.arguments.content??""));
          set({activeSection:"Coding",transcript:`${result.edited?"Edited":"Created"} ${result.relative_path}`}); return {success:true,...result,verified:true};
        }
        if (call.name === "select_active_repository") { const result=await api.selectCodingWorkspace(String(call.arguments.path??""));set({activeSection:"Coding",transcript:`Active repository: ${result.path}`});return {success:result.selected,...result}; }
        if (call.name === "open_active_repository_in_vscode") { const result=await api.openWorkspaceVSCode();set({activeSection:"Coding",transcript:`Opened ${result.path} in VS Code.`});return {success:result.opened,...result,verified:result.opened}; }
        if (call.name === "open_file_in_vscode") { const result=await api.openFileVSCode(String(call.arguments.root??""),String(call.arguments.relative_path??""));set({activeSection:"Coding",transcript:`Opened ${result.relative_path} in VS Code.`});return {success:result.opened,...result,verified:result.opened}; }
        if (call.name === "read_repository_file") { const result=await api.readCodingFile(String(call.arguments.root??""),String(call.arguments.relative_path??""));set({activeSection:"Coding",transcript:`Read ${result.relative_path}`});return {success:true,...result}; }
        if (call.name === "replace_text_in_repository_file") { const result=await api.replaceCodingFileText(String(call.arguments.root??""),String(call.arguments.relative_path??""),String(call.arguments.old_text??""),String(call.arguments.new_text??""));set({activeSection:"Coding",transcript:`Edited ${result.relative_path}`});return {success:result.edited,...result,verified:result.edited}; }
        if (call.name === "run_safe_repository_command") { const command=Array.isArray(call.arguments.command)?call.arguments.command.map(String):[];const result=await api.runWorkspaceCommand(command);set({activeSection:"Coding",transcript:`Command finished with exit code ${result.exit_code}`});return {success:result.verified,...result}; }
        if (call.name === "request_git_push_approval") { const preview=await api.previewGitPush();await useAppStore.getState().loadApprovals();set({activeSection:"Approvals",transcript:preview.approval?`Push ready. Approve ${preview.approval.id} once.`:preview.reason});return {success:Boolean(preview.approval),approval_id:preview.approval?.id,pushed:false}; }
        if (call.name === "execute_approved_git_push") { const result=await api.executeGitPush(String(call.arguments.approval_id??""));set({activeSection:"Coding",transcript:`Pushed ${result.branch}: ${result.remote_commit.slice(0,12)}`});return {success:result.verified,...result}; }
        if (call.name === "request_github_repository_creation") {
          const preview = await api.previewGitHubRepositoryCreate(String(call.arguments.name ?? ""), String(call.arguments.description ?? ""), call.arguments.visibility === "public" ? "public" : "private");
          await useAppStore.getState().loadApprovals();
          set({ activeSection: "Approvals", transcript: preview.approval ? `Repository request ready. Approve ${preview.approval.id} once.` : preview.reason });
          return { success: Boolean(preview.approval), approval_id: preview.approval?.id, repository: call.arguments.name, visibility: call.arguments.visibility, created: false, next_step: "Approve once in Approvals, then execute from Coding" };
        }
        if (call.name === "execute_approved_github_repository_creation") {
          const repository = await api.createGitHubRepository(String(call.arguments.approval_id ?? ""));
          set({ activeSection: "Coding", transcript: `GitHub repository created: ${repository.url}` });
          return { success: true, created: true, name: repository.name_with_owner, url: repository.url, verified: true };
        }
        if (call.name === "create_learning_plan_topic") {
          const concept = await api.createLearningConcept(String(call.arguments.topic ?? ""));
          await useAppStore.getState().loadWorkspaces();
          set({ activeSection: "Learning", transcript: `Learning topic created: ${concept.name}` });
          return { success: true, concept_id: concept.id, topic: concept.name, workspace: "Learning" };
        }
        if (call.name === "read_approved_webpage") {
          const page = await api.readWebPage(String(call.arguments.url ?? ""));
          set({ activeSection: "Browser", transcript: `Read webpage: ${page.title}` });
          return { success: true, url: page.url, title: page.title, excerpt: page.text.slice(0, 8000) };
        }
        if (call.name === "create_task") {
          const title = String(call.arguments.title ?? "").trim();
          if (!title) throw new Error("Task title is required");
          const task = await api.createTask(title);
          set((current) => ({ activeSection: "Tasks", tasks: [...current.tasks, task], tasksState: "ready", transcript: `Task created: ${task.title}` }));
          return { success: true, task_id: task.id, title: task.title, workspace: "Tasks" };
        }
        if (call.name === "summarize_available_email") {
          const connection = await api.gmailStatus();
          if (!connection.connected) return { success: false, connected: false, reason: "Gmail authorization is not connected." };
          const threads = await api.syncGmail();
          set({ activeSection: "Email", emailThreads: threads });
          if (threads.length === 0) return { success: true, connected: true, today_count: 0, messages: [], reason: "Gmail is connected but no recent threads were returned." };
          const today = new Date().toDateString();
          const messages = threads.flatMap((thread) => thread.messages.map((message) => ({ thread_id: thread.id, sender: message.sender, subject: message.subject, received_at: message.received_at }))).filter((message) => new Date(message.received_at).toDateString() === today);
          return { success: true, connected: true, today_count: messages.length, messages };
        }
        if (call.name === "create_email_reply_draft") {
          const draft = await api.createEmailReplyDraft(String(call.arguments.thread_id ?? ""), String(call.arguments.body ?? ""));
          set({ activeSection: "Email", transcript: `Email draft created: ${draft.subject}` });
          return { success: true, draft_id: draft.id, subject: draft.subject, recipients: draft.recipients, sent: false, sending_requires_approval: true };
        }
        if (call.name === "create_new_email_draft") {
          const connection = await api.gmailStatus();
          if (!connection.connected) throw new Error("Connect Gmail before creating a sendable email draft");
          const recipients = Array.isArray(call.arguments.recipients) ? call.arguments.recipients.map(String) : [];
          const draft = await api.createEmailDraft(recipients, String(call.arguments.subject ?? ""), String(call.arguments.body ?? ""));
          set({ activeSection: "Email", transcript: `New email draft created: ${draft.subject}` });
          return { success: true, connected: true, draft_id: draft.id, recipients: draft.recipients, subject: draft.subject, sent: false, next_step: "Request send approval" };
        }
        if (call.name === "request_email_send_approval") {
          const preview = await api.previewEmailSend(String(call.arguments.draft_id ?? ""));
          await useAppStore.getState().loadApprovals();
          set({ activeSection: "Approvals", transcript: preview.approval ? `Email send ready. Approve ${preview.approval.id} once.` : preview.reason });
          return { success: Boolean(preview.approval), approval_id: preview.approval?.id, sent: false };
        }
        if (call.name === "execute_approved_email_send") {
          const evidence = await api.sendEmailDraft(String(call.arguments.draft_id ?? ""), String(call.arguments.approval_id ?? ""));
          set({ activeSection: "Email", transcript: `Email sent and verified: ${evidence.message_id}` });
          return { success: true, sent: true, message_id: evidence.message_id, thread_id: evidence.thread_id, recipient: evidence.recipient, verified: true };
        }
        if (call.name === "open_spotify") {
          const result = await api.openApp("Spotify");
          set({ activeSection: "Device", transcript: result.verified ? "Spotify opened." : "Spotify could not be opened." });
          return { success: result.verified, action: result.action, target: result.target };
        }
        if (call.name === "spotify_search") {
          const result = await api.searchSpotify(String(call.arguments.query ?? ""));
          set({ activeSection: "Device", transcript: result.verified ? `Playing ${result.target} on Spotify.` : "Spotify playback failed." });
          return { success: result.verified, action: result.action, target: result.target };
        }
        if (call.name === "create_linkedin_draft") {
          const draft = await api.composeLinkedIn({
            topic: String(call.arguments.topic ?? ""),
            audience: String(call.arguments.audience ?? "professional audience"),
            key_points: Array.isArray(call.arguments.key_points) ? call.arguments.key_points.map(String) : [],
            call_to_action: String(call.arguments.call_to_action ?? ""),
            tone: String(call.arguments.tone ?? "clear"),
          });
          await useAppStore.getState().loadWorkspaces();
          set({ activeSection: "Content", transcript: `Draft created: ${draft.title}` });
          return { success: true, draft_id: draft.id, title: draft.title, workspace: "Content", copyable: true, publishing_requires_approval: true };
        }
        throw new Error(`Unsupported Friday tool: ${call.name}`);
      }, (userTranscript) => set({ userTranscript }));
    } catch (error) {
      voiceSession.stop();
      set({
        assistantState: "error",
        voiceError: error instanceof Error ? error.message : "Voice capture failed",
      });
    }
  },
  loadTasks: async () => {
    try {
      set({ tasks: await api.listTasks(), tasksState: "ready" });
    } catch {
      set({ tasksState: "offline" });
    }
  },
  createTask: async (title) => {
    const task = await api.createTask(title);
    set((state) => ({ tasks: [...state.tasks, task], tasksState: "ready" }));
  },
  toggleTask: async (task) => {
    const status = task.status === "completed" ? "planned" : "completed";
    const updated = await api.updateTask(task.id, { status });
    set((state) => ({
      tasks: state.tasks.map((item) => item.id === updated.id ? updated : item),
    }));
  },
  loadApprovals: async () => {
    try {
      set({ approvals: await api.listApprovals(), approvalsState: "ready" });
    } catch {
      set({ approvalsState: "offline" });
    }
  },
  decideApproval: async (approval, decision) => {
    const updated = await api.decideApproval(
      approval.id,
      decision,
      "00000000-0000-4000-8000-000000000001",
    );
    set((state) => ({
      approvals: state.approvals.map((item) => item.id === updated.id ? updated : item),
    }));
  },
  loadNotifications: async () => {
    try {
      const notifications = await api.listNotifications();
      deliverGrantedNotifications(notifications);
      set({ notifications });
    } catch {
      // Notifications are non-critical; task and approval flows remain available offline.
    }
  },
  loadSettings: async () => {
    try {
      set({ settings: await api.getSettings() });
    } catch {
      set({ settings: null });
    }
  },
  updateSettings: async (changes) => {
    set({ settings: await api.updateSettings(changes) });
  },
  loadAuditEvents: async () => {
    try {
      set({ auditEvents: await api.listAuditEvents() });
    } catch {
      set({ auditEvents: [] });
    }
  },
  loadDomains: async () => {
    try {
      const [projects, ideas, jobs, facts, memories] = await Promise.all([
        api.listProjects(), api.listIdeas(), api.listJobs(), api.listFacts(), api.listMemories(),
      ]);
      set({ projects, ideas, jobs, facts, memories });
    } catch {
      set({ projects: [], ideas: [], jobs: [], facts: [], memories: [] });
    }
  },
  loadWorkspaces: async () => {
    void api.listEmailThreads().then((emailThreads) => set({ emailThreads })).catch(() => set({ emailThreads: [] }));
    try {
      const [resumeClaims, applicationDrafts, calendarEvents, contentDrafts, videoProjects, learningConcepts] = await Promise.all([
        api.listResumeClaims(), api.listApplicationDrafts(),
        api.listCalendarEvents(), api.listContentDrafts(), api.listVideoProjects(),
        api.listLearningConcepts(),
      ]);
      set({ resumeClaims, applicationDrafts, calendarEvents, contentDrafts, videoProjects, learningConcepts });
    } catch {
      set({ resumeClaims: [], applicationDrafts: [], calendarEvents: [], contentDrafts: [], videoProjects: [], learningConcepts: [] });
    }
  },
}));
