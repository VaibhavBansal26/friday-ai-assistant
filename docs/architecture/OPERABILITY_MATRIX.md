# Friday operability matrix

Verified on 2026-07-11. “Implemented” means a user can trigger the action from Friday and receive provider or local evidence of the result.

| Requested outcome | Operational now | Missing execution dependency |
|---|---:|---|
| Converse by voice | No | OpenAI API credit/limit; packaged gateway lifecycle |
| Generate LinkedIn script | Yes, local structured composer | Model-enhanced rewriting remains blocked by OpenAI quota; local scripting, copy, and approval preview are operational |
| Publish to LinkedIn | No | LinkedIn OAuth/API authorization, preview, explicit publish approval, provider post ID |
| Create video | Yes, local baseline | Rich generated visuals and Remotion remain; FFmpeg render, local narration, captions, and evidence are operational |
| Publish video | No | YouTube/platform OAuth, upload worker, explicit approval, provider video ID |
| Commit GitHub code | Yes, local verified commits | GitHub CLI is authorized; remote repository selection/creation is required for push and PR evidence |
| Control music or movies | Yes, allowlisted baseline | Music transport and app launch are operational; richer playback/search and TV/VLC adapters remain |
| Search personal files | Yes, authorized roots | Workspace search and safe text preview are operational; user folder picker and durable scopes remain |
| Modify personal files | No | Per-folder write scopes, preview/diff, explicit approval and rollback |
| Open Chrome and fill forms | Implemented, not live-verified | Worker/UI/approval flow is present; live Chrome launch was blocked by the current execution approval/usage limit |
| Task/project views | Yes, local foundation | Durable production persistence remains incomplete |

Safety rule: opening/reading can be permission-scoped; commits, publishing, submissions, purchases, messages, uploads, and destructive file changes must pause for explicit approval and retain evidence.
