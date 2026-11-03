import json
from typing import Any, Callable, Coroutine, Dict, List, Optional
from sqlalchemy import select

from app.core.logging import logger
from app.db.models import WikiNote
from app.db.session import async_session_factory
from app.domain.dag import detect_cycles_in_subtasks
from app.tools.sandbox import sandbox
from app.tools.web_guard import safe_fetch_url, search_web
from app.workspace.workspace_manager import workspace_manager
from app.orchestrator.company_memory import save_memory, search_memory

# Function schemas formatted for OpenAI tool calling spec
TOOL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "delegate": {
        "type": "function",
        "function": {
            "name": "delegate",
            "description": "Create subtasks and delegate them to other agents/roles in the corporate hierarchy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subtasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Clear title of the subtask"},
                                "role_key": {"type": "string", "description": "Role key of the assigned subordinate"},
                                "description": {"type": "string", "description": "Detailed requirements for the subtask"},
                                "acceptance_criteria": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Exact checklist criteria the deliverable must fulfill",
                                },
                                "depends_on": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Titles or IDs of other subtasks that must be done before this starts",
                                },
                            },
                            "required": ["title", "role_key", "description", "acceptance_criteria"],
                        },
                    }
                },
                "required": ["subtasks"],
            },
        },
    },
    "submit_deliverable": {
        "type": "function",
        "function": {
            "name": "submit_deliverable",
            "description": "Submit completed task deliverable for manager review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Concise executive summary of completed deliverable"},
                    "artifact_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of artifacts registered during this task",
                    },
                },
                "required": ["summary"],
            },
        },
    },
    "review_decision": {
        "type": "function",
        "function": {
            "name": "review_decision",
            "description": "Provide a formal review decision on a subordinate's deliverable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["approve", "revise", "escalate"],
                        "description": "approve if all criteria met; revise if corrections needed; escalate if blocked",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Specific feedback citing acceptance criteria one by one",
                    },
                },
                "required": ["decision", "notes"],
            },
        },
    },
    "request_help": {
        "type": "function",
        "function": {
            "name": "request_help",
            "description": "Request specialized assistance from shared support services (QA, Librarian, Researcher, Proofreader).",
            "parameters": {
                "type": "object",
                "properties": {
                    "role_or_service": {"type": "string", "description": "Target support service (e.g. librarian, qa_reviewer)"},
                    "question": {"type": "string", "description": "Precise assistance or research inquiry needed"},
                },
                "required": ["role_or_service", "question"],
            },
        },
    },
    "report_blocked": {
        "type": "function",
        "function": {
            "name": "report_blocked",
            "description": "Report that this task is blocked and cannot proceed without intervention.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Detailed explanation of why work is blocked"},
                },
                "required": ["reason"],
            },
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to your private agent directory inside the current project. Prefix shared/ for files intentionally shared with teammates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside your private agent folder; prefix shared/ for a deliberate handoff"},
                    "content": {"type": "string", "description": "File contents to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from your private agent directory. Prefix shared/ or artifacts/ to read project-shared files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside your private folder; use shared/ or artifacts/ to read shared project files"},
                },
                "required": ["path"],
            },
        },
    },
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in your private project folder. Use shared/ or artifacts/ to inspect shared project files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {"type": "string", "description": "Relative subdirectory in your private folder; shared/ or artifacts/ selects the shared project area", "default": ""},
                },
            },
        },
    },
    "create_artifact": {
        "type": "function",
        "function": {
            "name": "create_artifact",
            "description": "Register a permanent deliverable artifact (markdown, code, json, image_svg, text).",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["markdown", "code", "json", "image_svg", "text", "file"],
                        "description": "Category of artifact",
                    },
                    "title": {"type": "string", "description": "Display title for the artifact"},
                    "content": {"type": "string", "description": "Full content of the artifact"},
                },
                "required": ["kind", "title", "content"],
            },
        },
    },
    "run_code": {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute code in a restricted local subprocess (python or node) with your private project folder as the working directory; not a security boundary for untrusted production workloads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "node", "javascript"], "description": "Language interpreter"},
                    "code": {"type": "string", "description": "Source code to execute"},
                },
                "required": ["language", "code"],
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for up-to-date documentation or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    "fetch_url": {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and extract text content from a public web URL (SSRF guarded).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Public HTTP/HTTPS URL"},
                },
                "required": ["url"],
            },
        },
    },
    "wiki_search": {
        "type": "function",
        "function": {
            "name": "wiki_search",
            "description": "Search the shared corporate knowledge wiki notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords to search in company notes"},
                },
                "required": ["query"],
            },
        },
    },
    "wiki_write": {
        "type": "function",
        "function": {
            "name": "wiki_write",
            "description": "Write or update a company knowledge note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the note"},
                    "body": {"type": "string", "description": "Content of the note"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                },
                "required": ["title", "body"],
            },
        },
    },
}


class ToolExecutor:
    """Executes tools safely for a specific project, task, and agent context."""

    def __init__(self, project_id: str, task_id: Optional[str] = None, agent_id: Optional[str] = None) -> None:
        self.project_id = project_id
        self.task_id = task_id
        self.agent_id = agent_id
        if agent_id:
            workspace_manager.get_agent_dir(project_id, agent_id)

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Safely execute tool. Never raises an uncaught exception to the caller."""
        try:
            if tool_name == "write_file":
                rel = (
                    workspace_manager.write_agent_file(self.project_id, self.agent_id, args["path"], args["content"])
                    if self.agent_id else workspace_manager.write_file(self.project_id, args["path"], args["content"])
                )
                return {"success": True, "path": rel, "message": "File written successfully."}

            elif tool_name == "read_file":
                content = (
                    workspace_manager.read_agent_file(self.project_id, self.agent_id, args["path"])
                    if self.agent_id else workspace_manager.read_file(self.project_id, args["path"])
                )
                return {"success": True, "content": content}

            elif tool_name == "list_files":
                subpath = args.get("subpath", "")
                files = (
                    workspace_manager.list_agent_files(self.project_id, self.agent_id, subpath)
                    if self.agent_id else workspace_manager.list_files(self.project_id, subpath)
                )
                return {"success": True, "files": files}

            elif tool_name == "create_artifact":
                art = await workspace_manager.create_artifact(
                    project_id=self.project_id,
                    task_id=self.task_id,
                    agent_id=self.agent_id,
                    kind=args["kind"],
                    title=args["title"],
                    content=args["content"],
                )
                return {
                    "success": True,
                    "artifact_id": art.id,
                    "path": art.path,
                    "summary": art.summary,
                }

            elif tool_name == "run_code":
                proj_dir = (
                    workspace_manager.get_agent_dir(self.project_id, self.agent_id)
                    if self.agent_id else workspace_manager.get_project_dir(self.project_id)
                )
                ret_code, stdout, stderr = sandbox.execute(
                    language=args["language"],
                    code=args["code"],
                    cwd=proj_dir,
                )
                return {
                    "success": ret_code == 0,
                    "returncode": ret_code,
                    "stdout": stdout,
                    "stderr": stderr,
                }

            elif tool_name == "web_search":
                results = await search_web(args["query"])
                return {"success": True, "results": results}

            elif tool_name == "fetch_url":
                text = await safe_fetch_url(args["url"])
                return {"success": True, "content": text}

            elif tool_name == "wiki_search":
                notes = await search_memory(args.get("query", ""), self.project_id, 30)
                matches = [
                    {"id": n.id, "title": n.title, "tags": n.tags, "body": n.body, "project_id": n.project_id}
                    for n in notes
                ]
                return {"success": True, "matches": matches}

            elif tool_name == "wiki_write":
                note = await save_memory(
                    title=args["title"],
                    body=args["body"],
                    tags=args.get("tags", ""),
                    project_id=self.project_id,
                    created_by_agent_id=self.agent_id,
                )
                return {"success": True, "id": note.id, "message": "Company memory saved or updated."}

            elif tool_name == "delegate":
                # Validate DAG cycles
                subtasks = args.get("subtasks", [])
                detect_cycles_in_subtasks(subtasks)
                return {"success": True, "delegated_count": len(subtasks), "subtasks": subtasks}

            elif tool_name == "review_decision":
                return {
                    "success": False,
                    "error": "Formal acceptance reviews are handled by the review engine after submit_deliverable.",
                }

            elif tool_name == "request_help":
                return {
                    "success": False,
                    "error": "Support routing is not available yet. Use delegate to create a scoped support task.",
                }

            elif tool_name in ("submit_deliverable", "report_blocked"):
                return {"success": True, "action": tool_name, "args": args}

            else:
                return {"success": False, "error": f"Unknown tool: '{tool_name}'"}

        except Exception as exc:
            logger.error(f"Error in tool '{tool_name}': {exc}")
            return {"success": False, "error": str(exc)}
