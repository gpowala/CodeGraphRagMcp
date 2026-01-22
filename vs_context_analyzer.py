"""
Visual Studio Debugging Context Analyzer

Designed for the real debugging workflow:
1. Developer loads crash dump in VS 2026
2. Loads symbols and navigates to crash location
3. Provides context to LLM for root cause analysis
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import re


class VSDebugContext:
    """Represents debugging context from Visual Studio"""
    
    def __init__(
        self,
        current_file: str,
        current_line: int,
        exception_info: str,
        call_stack: List[str],
        log_file_path: Optional[str] = None
    ):
        self.current_file = current_file
        self.current_line = current_line
        self.exception_info = exception_info
        self.call_stack = call_stack
        self.log_file_path = log_file_path
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_file": self.current_file,
            "current_line": self.current_line,
            "exception_info": self.exception_info,
            "call_stack": self.call_stack,
            "log_file_path": self.log_file_path
        }


async def analyze_vs_debug_context(
    current_file: str,
    current_line: int,
    exception_info: str,
    call_stack: List[str],
    log_content: Optional[str],
    db_pool,
    embedding_model
) -> Dict[str, Any]:
    """
    Analyze Visual Studio debugging context to find root cause
    
    Args:
        current_file: File path where you stopped in VS (e.g., "src\\database\\connection.cpp")
        current_line: Line number in VS debugger
        exception_info: Exception details from VS (e.g., "Access Violation reading 0x00000000")
        call_stack: List of stack frames from VS Call Stack window (with symbols loaded)
        log_content: Content of application log file (if provided)
        db_pool: Database connection pool
        embedding_model: Embedding model
    
    Returns:
        Analysis with:
        - crash_location_code: Code at crash point
        - execution_path: Code for each frame in call stack
        - root_cause_analysis: Likely root cause with reasoning
        - related_log_entries: Relevant log lines
        - similar_patterns: Similar code that might have same issue
    """
    
    analysis = {
        "crash_location": {},
        "execution_path": [],
        "log_analysis": {},
        "root_cause_hypothesis": [],
        "relevant_code_context": []
    }
    
    async with db_pool.acquire() as conn:
        # 1. Get code at crash location
        crash_code = await _get_code_at_location(
            conn, current_file, current_line
        )
        if crash_code:
            analysis["crash_location"] = {
                "file": current_file,
                "line": current_line,
                "entity": crash_code.get("qualified_name"),
                "code": crash_code.get("code"),
                "entity_range": f"{crash_code.get('start_line')}-{crash_code.get('end_line')}",
                "exception": exception_info
            }
        
        # 2. Parse call stack and get code for each frame
        parsed_stack = _parse_vs_call_stack(call_stack)
        
        for frame in parsed_stack:
            frame_code = None
            
            # Try to find by file and line
            if frame.get("file") and frame.get("line"):
                frame_code = await _get_code_at_location(
                    conn, frame["file"], frame["line"]
                )
            
            # Try to find by function name
            elif frame.get("function"):
                frame_code = await _find_by_function_name(
                    conn, frame["function"]
                )
            
            if frame_code:
                analysis["execution_path"].append({
                    "frame_info": frame,
                    "code": frame_code.get("code"),
                    "entity": frame_code.get("qualified_name"),
                    "file": frame_code.get("file_path"),
                    "lines": f"{frame_code.get('start_line')}-{frame_code.get('end_line')}"
                })
        
        # 3. Analyze logs if provided
        log_analysis = {}
        if log_content:
            log_analysis = _analyze_logs(
                log_content, 
                exception_info,
                parsed_stack
            )
            analysis["log_analysis"] = log_analysis
        
        # 4. Search for similar crash patterns using exception info
        if exception_info:
            query_embedding = embedding_model.encode(
                f"crash {exception_info} {crash_code.get('qualified_name', '') if crash_code else ''}"
            ).tolist()
            
            similar = await conn.fetch("""
                SELECT 
                    c.content,
                    f.path as file_path,
                    e.qualified_name,
                    c.start_line,
                    1 - (c.embedding <=> $1::vector) as similarity
                FROM code_chunks c
                JOIN files f ON c.file_id = f.id
                LEFT JOIN entities e ON c.entity_id = e.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT 5
            """, query_embedding)
            
            analysis["similar_patterns"] = [
                {
                    "file": row["file_path"],
                    "function": row["qualified_name"],
                    "code_snippet": row["content"][:300],
                    "similarity": float(row["similarity"]),
                    "line": row["start_line"]
                }
                for row in similar
                if float(row["similarity"]) > 0.3  # Only reasonably similar
            ]
        
        # 5. Build root cause hypothesis
        analysis["root_cause_hypothesis"] = _build_root_cause_hypothesis(
            crash_code,
            analysis["execution_path"],
            log_analysis,
            exception_info
        )
    
    return analysis


async def _get_code_at_location(conn, file_path: str, line_number: int) -> Optional[Dict]:
    """Get code entity at specific location"""
    # Normalize path (handle both forward and backslashes)
    normalized_path = Path(file_path).as_posix()
    file_name = Path(file_path).name
    
    result = await conn.fetchrow("""
        SELECT 
            e.qualified_name,
            e.type,
            e.signature,
            e.start_line,
            e.end_line,
            f.path as file_path,
            c.content as code
        FROM entities e
        JOIN files f ON e.file_id = f.id
        LEFT JOIN code_chunks c ON c.entity_id = e.id
        WHERE (f.path LIKE $1 OR f.path LIKE $2)
          AND e.start_line <= $3 
          AND e.end_line >= $3
        ORDER BY (e.end_line - e.start_line) ASC
        LIMIT 1
    """, f"%{file_name}%", f"%{normalized_path}%", line_number)
    
    return dict(result) if result else None


async def _find_by_function_name(conn, function_name: str) -> Optional[Dict]:
    """Find code by function name (fallback)"""
    # Clean up function name (remove parameters, etc.)
    clean_name = function_name.split('(')[0].strip()
    
    result = await conn.fetchrow("""
        SELECT 
            e.qualified_name,
            e.type,
            e.signature,
            e.start_line,
            e.end_line,
            f.path as file_path,
            c.content as code
        FROM entities e
        JOIN files f ON e.file_id = f.id
        LEFT JOIN code_chunks c ON c.entity_id = e.id
        WHERE e.qualified_name LIKE $1
           OR e.simple_name = $2
        ORDER BY LENGTH(e.qualified_name) ASC
        LIMIT 1
    """, f"%{clean_name}%", clean_name.split('::')[-1])
    
    return dict(result) if result else None


def _parse_vs_call_stack(call_stack: List[str]) -> List[Dict[str, Any]]:
    """
    Parse Visual Studio call stack (with symbols loaded)
    
    Examples of VS call stack formats:
    - MyApp.exe!Legacy::Database::ConnectionPool::release(DatabaseConnection * conn) Line 95 C++
    - MyApp.exe!MyNamespace::MyClass::method(int param) Line 123 C++
    - [External Code]
    - ntdll.dll!NtWaitForSingleObject() Unknown
    """
    frames = []
    
    for line in call_stack:
        line = line.strip()
        if not line or "[External Code]" in line:
            continue
        
        frame = {"raw": line}
        
        # Pattern: module!namespace::class::function(params) Line XX
        match = re.search(
            r'([^!]+)!(.+?)\((.*?)\)\s+Line\s+(\d+)',
            line
        )
        
        if match:
            frame["module"] = match.group(1)
            frame["function"] = match.group(2)
            frame["parameters"] = match.group(3)
            frame["line"] = int(match.group(4))
            
            # Try to extract file from later in the line
            # Format: ... C++ [path\to\file.cpp @ 95]
            file_match = re.search(r'\[(.+?\.(?:cpp|cc|cxx|h|hpp))\s*@\s*\d+\]', line)
            if file_match:
                frame["file"] = file_match.group(1)
        else:
            # Simpler pattern without line number
            match = re.search(r'([^!]+)!(.+)', line)
            if match:
                frame["module"] = match.group(1)
                frame["function"] = match.group(2).split('(')[0]
        
        if "function" in frame:
            frames.append(frame)
    
    return frames


def _analyze_logs(
    log_content: str,
    exception_info: str,
    parsed_stack: List[Dict]
) -> Dict[str, Any]:
    """
    Analyze log file for relevant entries
    
    Looks for:
    - Errors/warnings before crash
    - Function names from call stack
    - Related error messages
    - State information
    """
    lines = log_content.split('\n')
    
    analysis = {
        "errors_before_crash": [],
        "warnings_before_crash": [],
        "relevant_entries": [],
        "state_info": {}
    }
    
    # Keywords from exception and stack
    keywords = set()
    
    # Add words from exception
    if exception_info:
        keywords.update(exception_info.lower().split())
    
    # Add function names from stack
    for frame in parsed_stack:
        if "function" in frame:
            # Add simple function name
            simple_name = frame["function"].split("::")[-1]
            keywords.add(simple_name.lower())
    
    # Remove common words
    keywords -= {"the", "a", "an", "at", "in", "on", "line", "c++"}
    
    # Scan logs
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Check for errors
        if any(err in line_lower for err in ["error", "exception", "fatal", "critical"]):
            analysis["errors_before_crash"].append({
                "line_number": i + 1,
                "content": line.strip()
            })
        
        # Check for warnings
        elif any(warn in line_lower for warn in ["warning", "warn"]):
            analysis["warnings_before_crash"].append({
                "line_number": i + 1,
                "content": line.strip()
            })
        
        # Check for relevant keywords
        if any(keyword in line_lower for keyword in keywords):
            analysis["relevant_entries"].append({
                "line_number": i + 1,
                "content": line.strip()
            })
        
        # Extract state info (variable = value patterns)
        state_match = re.search(r'(\w+)\s*[=:]\s*([^\s,;]+)', line)
        if state_match:
            var_name = state_match.group(1)
            var_value = state_match.group(2)
            
            # Filter interesting variables
            if any(word in var_name.lower() for word in ["count", "size", "ptr", "handle", "connection"]):
                analysis["state_info"][var_name] = var_value
    
    # Keep only last 20 errors/warnings (most recent)
    analysis["errors_before_crash"] = analysis["errors_before_crash"][-20:]
    analysis["warnings_before_crash"] = analysis["warnings_before_crash"][-20:]
    analysis["relevant_entries"] = analysis["relevant_entries"][-30:]
    
    return analysis


def _build_root_cause_hypothesis(
    crash_code: Optional[Dict],
    execution_path: List[Dict],
    log_analysis: Dict,
    exception_info: str
) -> List[Dict[str, str]]:
    """
    Build hypotheses about root cause based on available information
    
    Returns list of hypotheses with reasoning
    """
    hypotheses = []
    
    # Hypothesis 1: Null pointer from exception type
    if "access violation" in exception_info.lower() or "0x00000000" in exception_info:
        hypotheses.append({
            "hypothesis": "Null pointer dereference",
            "reasoning": f"Exception '{exception_info}' indicates null pointer access",
            "look_for": "Check execution path for where pointer/object was initialized. Likely null check was missed.",
            "priority": "HIGH"
        })
    
    # Hypothesis 2: Object already deleted (use-after-free)
    if "0xdddddddd" in exception_info.lower() or "0xfeeefeee" in exception_info.lower():
        hypotheses.append({
            "hypothesis": "Use-after-free (accessing deleted object)",
            "reasoning": "Memory pattern suggests freed/deleted memory",
            "look_for": "Check call stack for cleanup/delete operations before this call",
            "priority": "CRITICAL"
        })
    
    # Hypothesis 3: Stack corruption
    if "stack" in exception_info.lower() or len(execution_path) > 100:
        hypotheses.append({
            "hypothesis": "Stack overflow or corruption",
            "reasoning": f"Deep call stack ({len(execution_path)} frames) or stack-related exception",
            "look_for": "Look for recursion or large stack allocations",
            "priority": "HIGH"
        })
    
    # Hypothesis 4: From error logs
    if log_analysis and log_analysis.get("errors_before_crash"):
        last_error = log_analysis["errors_before_crash"][-1]["content"]
        hypotheses.append({
            "hypothesis": "Error condition propagated to crash",
            "reasoning": f"Last error in log: '{last_error}'",
            "look_for": "Trace how this error condition was (mis)handled in call stack",
            "priority": "MEDIUM"
        })
    
    # Hypothesis 5: Resource exhaustion
    if log_analysis and any("pool" in entry["content"].lower() or "exhausted" in entry["content"].lower() 
                            for entry in log_analysis.get("relevant_entries", [])):
        hypotheses.append({
            "hypothesis": "Resource pool exhausted",
            "reasoning": "Logs mention pool exhaustion",
            "look_for": "Check if resource (connection/memory/handle) acquisition was checked for null/failure",
            "priority": "HIGH"
        })
    
    return hypotheses
