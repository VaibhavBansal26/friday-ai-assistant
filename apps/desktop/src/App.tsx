import { Command, Mic, Paperclip, Plus, Search, Shield, Sparkles, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import auroraCore from "./assets/friday-core-aurora.png";
import emberCore from "./assets/friday-core-ember.png";
import { speakStartupGreeting } from "./lib/voice";
import { ApprovalsView, AuditView, BrowserView, CodingView, ContentStudioView, DeviceView, FilesView, GmailView, IdeasView, JobsView, KnowledgeView, MemoryView, ProjectsView, SettingsView, TasksView, VideoStudioView, WorkspaceView } from "./components/OperationalViews";
import { CodeWorkspacePanel, EmailDraftList, NewEmailComposer, NewRepositoryPanel } from "./components/CreationPanels";
import { api } from "./lib/api";
import { useAppStore } from "./store/app";

const nav = ["Home", "Tasks", "Ideas", "Projects", "Jobs", "Resume", "Applications", "Email", "Calendar", "Coding", "Browser", "Device", "Files", "Knowledge", "Memory", "Content", "Video Studio", "Learning", "Approvals", "Audit Log", "Settings"];
export function App() {
  const voiceAutoStarted = useRef(false);
  const [theme, setThemeState] = useState<"aurora" | "ember">(() => localStorage.getItem("friday-theme") === "ember" ? "ember" : "aurora");
  const [sharedFiles, setSharedFiles] = useState<Array<{ id: string; name: string; kind: string }>>([]);
  const [shareStatus, setShareStatus] = useState("Share an image, video, or document with Friday.");
  const setTheme = (value: "aurora" | "ember") => { localStorage.setItem("friday-theme", value); setThemeState(value); };
  const { activeSection, setActiveSection, assistantState, transcript, userTranscript, voiceError, tasks, loadTasks, createTask, toggleTask, toggleVoiceCapture, approvals, loadApprovals, decideApproval, loadNotifications, settings, loadSettings, updateSettings, auditEvents, loadAuditEvents, projects, ideas, jobs, facts, memories, loadDomains, resumeClaims, applicationDrafts, emailThreads, calendarEvents, contentDrafts, videoProjects, learningConcepts, loadWorkspaces } = useAppStore();
  useEffect(() => { void loadTasks(); void loadApprovals(); void loadNotifications(); void loadSettings(); void loadAuditEvents(); void loadDomains(); void loadWorkspaces(); }, [loadTasks, loadApprovals, loadNotifications, loadSettings, loadAuditEvents, loadDomains, loadWorkspaces]);
  useEffect(() => {
    if (!settings?.voice_enabled || voiceAutoStarted.current || assistantState !== "idle") return;
    voiceAutoStarted.current = true;
    speakStartupGreeting();
    void toggleVoiceCapture();
  }, [settings?.voice_enabled, assistantState, toggleVoiceCapture]);
  const addTask = () => {
    const title = window.prompt("Task title");
    if (title?.trim()) void createTask(title.trim());
  };
  const shareFiles = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      try { setShareStatus(`Adding ${file.name}…`); const item = await api.uploadAttachment(file); setSharedFiles((current) => [...current, item]); setShareStatus(`${item.name} is available to Friday locally.`); }
      catch (reason) { setShareStatus(reason instanceof Error ? reason.message : "Attachment failed"); }
    }
  };

  return (
    <main className={`shell theme-${theme}`}>
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>F R I D A Y</span></div>
        <button className="search"><Search size={15} /><span>Search</span><kbd>⌘ K</kbd></button>
        <nav aria-label="Main navigation">
          {nav.map((item) => <button key={item} className={activeSection === item ? "nav-active" : ""} onClick={() => setActiveSection(item)}>{item}</button>)}
        </nav>
        <div className="security"><Shield size={15} /><div><strong>Local security</strong><span>All systems healthy</span></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">Friday · Private intelligence system</p><h1>{activeSection === "Home" ? "Command center" : activeSection}</h1></div><div className="topbar-actions"><div className="theme-switch"><button className={theme === "aurora" ? "selected" : ""} onClick={() => setTheme("aurora")}>Aurora</button><button className={theme === "ember" ? "selected" : ""} onClick={() => setTheme("ember")}>Ember</button></div><button className="icon-button" aria-label="Command menu"><Command size={18} /></button></div></header>
        {activeSection === "Tasks" && <TasksView tasks={tasks} toggle={(task) => void toggleTask(task)} />}
        {activeSection === "Projects" && <ProjectsView projects={projects} />}
        {activeSection === "Ideas" && <IdeasView ideas={ideas} />}
        {activeSection === "Jobs" && <JobsView jobs={jobs} />}
        {activeSection === "Knowledge" && <KnowledgeView facts={facts} />}
        {activeSection === "Memory" && <MemoryView memories={memories} />}
        {activeSection === "Resume" && <WorkspaceView eyebrow="Source-backed claims" title="Resume" empty="No verified resume claims." rows={resumeClaims.map((item) => ({ id: item.id, title: item.claim_text, detail: item.skills.join(", ") || "No skills tagged", status: "verified source" }))} />}
        {activeSection === "Applications" && <WorkspaceView eyebrow="Prepared, not auto-submitted" title="Applications" empty="No application drafts." rows={applicationDrafts.map((item) => ({ id: item.id, title: `${item.job.company} — ${item.job.title}`, detail: item.uploaded_files.length ? `${item.uploaded_files.length} approved file(s)` : "No files attached", status: item.status }))} />}
        {activeSection === "Email" && <><NewEmailComposer/><EmailDraftList/><GmailView threads={emailThreads} status={api.gmailStatus} configure={api.configureGmail} authorizationUrl={api.gmailAuthorizationUrl} sync={api.syncGmail} /></>}
        {activeSection === "Calendar" && <WorkspaceView eyebrow="Proposals and conflicts" title="Calendar" empty="No calendar events connected." rows={calendarEvents.map((item) => ({ id: item.id, title: item.title, detail: `${new Date(item.starts_at).toLocaleString()} – ${new Date(item.ends_at).toLocaleTimeString()}`, status: item.status }))} />}
        {activeSection === "Content" && <ContentStudioView drafts={contentDrafts} compose={async (input) => { const draft = await api.composeLinkedIn(input); await loadWorkspaces(); return draft; }} publishPreview={api.previewContentPublish} connection={api.linkedInStatus} configure={api.configureLinkedIn} authorizationUrl={api.linkedInAuthorizationUrl} publish={api.publishLinkedIn} />}
        {activeSection === "Video Studio" && <VideoStudioView projects={videoProjects} create={async (title, narration) => { await api.createVideoProject(title, narration); await loadWorkspaces(); }} render={api.renderVideoProject} />}
        {activeSection === "Device" && <DeviceView openApp={api.openApp} media={api.controlMedia} />}
        {activeSection === "Files" && <FilesView search={api.searchFiles} read={api.readFile} />}
        {activeSection === "Coding" && <><NewRepositoryPanel reload={async()=>{ await api.listGitHubRepositories(); }}/><CodeWorkspacePanel/><CodingView inspect={api.inspectRepository} commit={api.commitFiles} listRepositories={api.listGitHubRepositories} cloneRepository={api.cloneGitHubRepository} /></>}
        {activeSection === "Browser" && <BrowserView preview={api.previewBrowserForm} submit={api.submitBrowserForm} />}
        {activeSection === "Learning" && <WorkspaceView eyebrow="Active recall and review" title="Learning" empty="No learning concepts." rows={learningConcepts.map((item) => ({ id: item.id, title: item.name, detail: item.next_review_at ? `Next review ${new Date(item.next_review_at).toLocaleDateString()}` : "Review not scheduled", status: item.status }))} />}
        {activeSection === "Approvals" && <ApprovalsView approvals={approvals} decide={(approval, decision) => void decideApproval(approval, decision)} />}
        {activeSection === "Audit Log" && <AuditView events={auditEvents} />}
        {activeSection === "Settings" && <SettingsView settings={settings} update={(changes) => void updateSettings(changes)} />}
        {!["Tasks", "Projects", "Ideas", "Jobs", "Coding", "Browser", "Device", "Files", "Knowledge", "Memory", "Resume", "Applications", "Email", "Calendar", "Content", "Video Studio", "Learning", "Approvals", "Audit Log", "Settings"].includes(activeSection) && <div className="command-grid">
          <section className="core-stage">
            <div className="core-status"><span className="signal-dot"/><span>{assistantState === "idle" ? "Standing by" : assistantState}</span></div>
            <button className="core-button" onClick={() => void toggleVoiceCapture()} aria-label={["idle", "error", "completed"].includes(assistantState) ? "Start voice conversation" : "End voice conversation"}>
              <img src={theme === "aurora" ? auroraCore : emberCore} alt="Friday living voice core" />
            </button>
            <div className="signal-quality"><span>Signal quality</span><strong>{assistantState === "error" ? "Offline" : "98.7% clear"}</strong></div>
            <div className="permission"><Mic size={18}/><span>{voiceError ?? (assistantState === "idle" ? "Tap the core to begin" : assistantState === "listening" ? "Listening — speak now" : assistantState === "understanding" ? "Connecting microphone…" : assistantState === "speaking" ? "Friday is replying…" : "Microphone active")}</span></div>
          </section>
          <section className="conversation-panel">
            <div className="conversation-heading"><div><p className="eyebrow">Live conversation</p><h2>Friday</h2></div><span className="live-pill">{assistantState}</span></div>
            <div className="conversation-stream" aria-live="polite">
              <article className="turn turn-user"><small>You</small><p>{userTranscript}</p></article>
              <article className="turn turn-friday"><small>Friday</small><p>{transcript || "I’m ready. Speak naturally and I’ll stay with the conversation."}</p></article>
            </div>
            <button className={`conversation-action ${!["idle", "error", "completed"].includes(assistantState) ? "active" : ""}`} onClick={() => void toggleVoiceCapture()}>{!["idle", "error", "completed"].includes(assistantState) ? <Square size={16}/> : <Mic size={17}/>}<span>{!["idle", "error", "completed"].includes(assistantState) ? "End conversation" : "Retry conversation"}</span></button>
            <label className="attachment-action"><Paperclip size={16}/><span>Add image, video, or document</span><input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.txt,.md" onChange={(event) => void shareFiles(event.target.files)}/></label>
            <small className="attachment-status">{shareStatus}</small>
            {sharedFiles.length > 0 && <div className="attachment-list">{sharedFiles.map((file) => <span key={file.id}>{file.kind} · {file.name}</span>)}</div>}
          </section>
          <section className="intel-strip"><div><small>Next task</small><strong>{tasks[0]?.title ?? "Your focus queue is clear"}</strong></div><button onClick={addTask}><Plus size={16}/> Add task</button><div><small>Pending approval</small><strong>{approvals.filter((item) => item.status === "pending").length} waiting</strong></div></section>
        </div>}
      </section>
    </main>
  );
}
