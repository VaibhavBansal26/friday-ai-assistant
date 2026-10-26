import { useState } from "react";
import { Code2, Send, Shield } from "lucide-react";
import { api } from "../lib/api";

export function NewEmailComposer() {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [draftId, setDraftId] = useState("");
  const [approvalId, setApprovalId] = useState("");
  const [status, setStatus] = useState("Create a new email draft. Sending always requires approve-once authorization.");
  const createDraft = async () => {
    try {
      const draft = await api.createEmailDraft(to.split(",").map((value) => value.trim()).filter(Boolean), subject, body);
      setDraftId(draft.id); setApprovalId(""); setStatus("Draft saved locally. Request send approval when ready.");
    } catch (reason) { setStatus(reason instanceof Error ? reason.message : "Draft creation failed"); }
  };
  const preview = async () => {
    try {
      const result = await api.previewEmailSend(draftId); const id = result.approval?.id ?? "";
      setApprovalId(id); setStatus(id ? `Approve ${id} in Approvals, then return here.` : result.reason);
    } catch (reason) { setStatus(reason instanceof Error ? reason.message : "Send preview failed"); }
  };
  const send = async () => {
    try {
      const evidence = await api.sendEmailDraft(draftId, approvalId);
      setStatus(`Sent and verified: Gmail message ${evidence.message_id}`); setTo(""); setSubject(""); setBody(""); setDraftId(""); setApprovalId("");
    } catch (reason) { setStatus(reason instanceof Error ? reason.message : "Email send failed"); }
  };
  return <section className="wide-panel"><div className="view-heading"><div><p className="eyebrow">Approval-gated Gmail</p><h2>Compose new email</h2></div><Send/></div><div className="safety-banner"><Shield size={16}/><span>{status}</span></div><div className="browser-form"><label>Recipients<input value={to} onChange={(event)=>setTo(event.target.value)} placeholder="recipient@example.com"/></label><label>Subject<input value={subject} onChange={(event)=>setSubject(event.target.value)}/></label><label>Message<textarea value={body} onChange={(event)=>setBody(event.target.value)}/></label><button className="button button--quiet" disabled={!to||!subject||!body} onClick={()=>void createDraft()}>Create draft</button><button className="button button--quiet" disabled={!draftId} onClick={()=>void preview()}>Request approval</button><button className="button button--primary" disabled={!approvalId} onClick={()=>void send()}>Send approved email</button></div></section>;
}

export function NewRepositoryPanel({ reload }: { reload: () => Promise<void> }) {
  const [name,setName]=useState(""); const [description,setDescription]=useState(""); const [visibility,setVisibility]=useState<"private"|"public">("private"); const [approvalId,setApprovalId]=useState(""); const [status,setStatus]=useState("Create a GitHub repository after explicit approval.");
  const preview=async()=>{try{const result=await api.previewGitHubRepositoryCreate(name,description,visibility);const id=result.approval?.id??"";setApprovalId(id);setStatus(id?`Approve ${id} in Approvals, then return here.`:result.reason);}catch(reason){setStatus(reason instanceof Error?reason.message:"Preview failed");}};
  const create=async()=>{try{const repo=await api.createGitHubRepository(approvalId);setStatus(`Created and verified: ${repo.url}`);setName("");setDescription("");setApprovalId("");await reload();}catch(reason){setStatus(reason instanceof Error?reason.message:"Repository creation failed");}};
  return <section className="wide-panel"><div className="view-heading"><div><p className="eyebrow">Connected GitHub account</p><h2>Create repository</h2></div><Code2/></div><div className="safety-banner"><Shield size={16}/><span>{status}</span></div><div className="browser-form"><label>Name<input value={name} onChange={(event)=>setName(event.target.value)} placeholder="new-project"/></label><label>Description<input value={description} onChange={(event)=>setDescription(event.target.value)}/></label><label>Visibility<select value={visibility} onChange={(event)=>setVisibility(event.target.value as "private"|"public")}><option value="private">Private</option><option value="public">Public</option></select></label><button className="button button--quiet" disabled={!name} onClick={()=>void preview()}>Request creation approval</button><button className="button button--primary" disabled={!approvalId} onClick={()=>void create()}>Create approved repository</button></div></section>;
}

export function EmailDraftList() {
  const [drafts,setDrafts]=useState<Array<{id:string;recipients:string[];subject:string;body:string}>>([]); const [status,setStatus]=useState("Select Refresh to load voice and form drafts.");
  const reload=async()=>{try{const items=await api.listEmailDrafts();setDrafts(items);setStatus(`${items.length} visible draft(s)`);}catch(reason){setStatus(reason instanceof Error?reason.message:"Drafts unavailable");}};
  return <section className="wide-panel"><div className="view-heading"><div><p className="eyebrow">Local Gmail drafts</p><h2>Email drafts</h2></div><button className="button button--quiet" onClick={()=>void reload()}>Refresh</button></div><div className="safety-banner"><Shield size={16}/><span>{status}</span></div><div className="task-list">{drafts.map(draft=><div className="data-row" key={draft.id}><span><strong>{draft.subject}</strong><small>To: {draft.recipients.join(", ")}</small><small>{draft.body}</small></span></div>)}</div></section>;
}

export function CodeWorkspacePanel() {
  const [root,setRoot]=useState(""); const [entries,setEntries]=useState<Array<{path:string;kind:string;size:number}>>([]); const [file,setFile]=useState(""); const [content,setContent]=useState(""); const [status,setStatus]=useState("Enter a cloned repository path to visualize and work with it.");
  const load=async()=>{try{const tree=await api.codingTree(root);setRoot(tree.root);setEntries(tree.entries);setStatus(`Visualizing ${tree.entries.length} paths`);}catch(reason){setStatus(reason instanceof Error?reason.message:"Tree failed");}};
  const create=async()=>{try{const result=await api.saveCodingFile(root,file,content);setStatus(`${result.edited?"Edited":"Created"} ${result.relative_path} (${result.bytes} bytes)`);setFile("");setContent("");await load();}catch(reason){setStatus(reason instanceof Error?reason.message:"File save failed");}};
  const open=async()=>{try{const result=await api.openCodingFolder(root);setStatus(result.opened?`Opened ${result.path} in Finder`:"Finder open failed");}catch(reason){setStatus(reason instanceof Error?reason.message:"Open failed");}};
  return <section className="wide-panel"><div className="view-heading"><div><p className="eyebrow">Repository visualization</p><h2>Code workspace</h2></div><Code2/></div><div className="safety-banner"><Shield size={16}/><span>{status}</span></div><div className="browser-form"><label>Local repository folder<input value={root} onChange={event=>setRoot(event.target.value)}/></label><button className="button button--quiet" disabled={!root} onClick={()=>void load()}>Visualize structure</button><button className="button button--quiet" disabled={!root} onClick={()=>void open()}>Open in Finder</button><label>New file path<input value={file} onChange={event=>setFile(event.target.value)} placeholder="src/new-file.ts"/></label><label>File content<textarea value={content} onChange={event=>setContent(event.target.value)}/></label><button className="button button--primary" disabled={!root||!file} onClick={()=>void create()}>Create file</button></div><pre className="file-preview">{entries.map(item=>`${item.kind==="folder"?"📁":"📄"} ${item.path}`).join("\n")||"Repository structure will appear here."}</pre></section>;
}
