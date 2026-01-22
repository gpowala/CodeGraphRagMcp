"""
Crash Dump Analysis Module
Helps developers navigate codebase using crash dumps and logs
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path


class CrashDumpAnalyzer:
    """Parse crash dumps and logs to extract actionable information"""
    
    def __init__(self):
        # Common crash dump patterns
        self.stack_frame_patterns = [
            # MSVC format: module!namespace::class::function+offset
            r'([a-zA-Z0-9_]+\.(?:dll|exe))!([a-zA-Z0-9_:]+)(?:\+0x[0-9a-f]+)?',
            # GDB format: #0  function (args) at file.cpp:line
            r'#\d+\s+(?:0x[0-9a-f]+\s+in\s+)?([a-zA-Z0-9_:]+)\s*\([^)]*\)\s+at\s+([^:]+):(\d+)',
            # Simple format: function_name at file.cpp:123
            r'([a-zA-Z0-9_:]+)\s+at\s+([^:]+):(\d+)',
            # Windows minidump: module!function
            r'([a-zA-Z0-9_]+)!([a-zA-Z0-9_:]+)',
        ]
        
        # Log error patterns
        self.error_patterns = [
            # Access violation
            r'(?:Access violation|Segmentation fault|SIGSEGV)',
            # Null pointer
            r'(?:null pointer|nullptr|NULL pointer)',
            # Memory errors
            r'(?:heap corruption|buffer overflow|use after free|double free)',
            # Assertion failures
            r'Assertion.*failed',
            # Exception messages
            r'(?:Exception|Error):\s*(.+)',
        ]
    
    def parse_stack_trace(self, stack_trace: str) -> List[Dict[str, Any]]:
        """
        Parse a stack trace and extract function names, files, and line numbers
        
        Returns list of frames with:
        - function: qualified function name
        - file: source file path (if available)
        - line: line number (if available)
        - module: DLL/EXE name (if available)
        """
        frames = []
        lines = stack_trace.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try each pattern
            for pattern in self.stack_frame_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    frame = {'raw': line}
                    
                    if len(groups) == 2:
                        # module!function or dll!namespace::function
                        frame['module'] = groups[0]
                        frame['function'] = groups[1]
                    elif len(groups) == 3:
                        # function at file:line
                        frame['function'] = groups[0]
                        frame['file'] = groups[1]
                        frame['line'] = int(groups[2])
                    
                    frames.append(frame)
                    break
        
        return frames
    
    def extract_error_context(self, log_text: str) -> Dict[str, Any]:
        """
        Extract error context from log text
        
        Returns:
        - error_type: type of error
        - error_message: the actual error message
        - context_lines: surrounding log lines
        """
        lines = log_text.split('\n')
        error_info = {
            'error_type': 'unknown',
            'error_message': '',
            'context_lines': []
        }
        
        for i, line in enumerate(lines):
            # Check for error patterns
            for pattern in self.error_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    error_info['error_type'] = pattern.split('|')[0].strip('(?:')
                    error_info['error_message'] = match.group(0)
                    
                    # Extract context (5 lines before and after)
                    start = max(0, i - 5)
                    end = min(len(lines), i + 6)
                    error_info['context_lines'] = lines[start:end]
                    error_info['error_line_index'] = i - start
                    
                    return error_info
        
        return error_info
    
    def extract_variable_values(self, log_text: str) -> Dict[str, str]:
        """
        Extract variable values from log/dump
        
        Common formats:
        - variable = value
        - variable: value
        - [variable] = value
        """
        variables = {}
        
        patterns = [
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^\n]+)',
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^\n]+)',
            r'\[([a-zA-Z_][a-zA-Z0-9_]*)\]\s*=\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, log_text)
            for match in matches:
                var_name = match.group(1)
                var_value = match.group(2).strip()
                
                # Filter out non-interesting values
                if var_value and len(var_value) < 200:
                    variables[var_name] = var_value
        
        return variables


async def analyze_crash_dump(dump_text: str, log_text: str, db_pool, embedding_model) -> Dict[str, Any]:
    """
    Main function to analyze a crash dump and return relevant code locations
    
    Args:
        dump_text: Stack trace or crash dump text
        log_text: Application logs around the crash
        db_pool: Database connection pool
        embedding_model: Embedding model for semantic search
    
    Returns:
        Dictionary with:
        - crash_summary: High-level summary
        - stack_frames: Parsed stack trace
        - relevant_code: Code chunks from the codebase
        - similar_crashes: Previously seen similar issues (if tracked)
    """
    analyzer = CrashDumpAnalyzer()
    
    # Parse stack trace
    frames = analyzer.parse_stack_trace(dump_text)
    
    # Extract error context from logs
    error_context = analyzer.extract_error_context(log_text)
    
    # Extract variable values
    variables = analyzer.extract_variable_values(dump_text + "\n" + log_text)
    
    # Find code for each stack frame
    frame_code = []
    async with db_pool.acquire() as conn:
        for frame in frames:
            code_info = {}
            
            # Try to find by function name
            if 'function' in frame:
                # Search for entity by qualified name or simple name
                entity = await conn.fetchrow("""
                    SELECT e.*, f.path as file_path, c.content as code
                    FROM entities e
                    JOIN files f ON e.file_id = f.id
                    LEFT JOIN code_chunks c ON c.entity_id = e.id
                    WHERE e.qualified_name LIKE $1 OR e.simple_name = $2
                    ORDER BY c.id
                    LIMIT 1
                """, f"%{frame['function']}%", frame['function'].split('::')[-1])
                
                if entity:
                    code_info['entity'] = dict(entity)
                    code_info['frame'] = frame
                    
                    # If we have file and line from dump, highlight that
                    if 'file' in frame and 'line' in frame:
                        code_info['crash_line'] = frame['line']
            
            # Try to find by file path
            elif 'file' in frame:
                entity = await conn.fetchrow("""
                    SELECT e.*, f.path as file_path, c.content as code
                    FROM files f
                    LEFT JOIN entities e ON e.file_id = f.id
                    LEFT JOIN code_chunks c ON c.file_id = f.id
                    WHERE f.path LIKE $1 AND e.start_line <= $2 AND e.end_line >= $2
                    ORDER BY e.id
                    LIMIT 1
                """, f"%{Path(frame['file']).name}%", frame.get('line', 0))
                
                if entity:
                    code_info['entity'] = dict(entity)
                    code_info['frame'] = frame
                    code_info['crash_line'] = frame.get('line')
            
            if code_info:
                frame_code.append(code_info)
        
        # Semantic search using error message
        similar_code = []
        if error_context['error_message']:
            # Create search query from error context
            search_query = f"{error_context['error_type']} {error_context['error_message']}"
            query_embedding = embedding_model.encode(search_query).tolist()
            
            # Search for similar code patterns
            similar = await conn.fetch("""
                SELECT 
                    c.content,
                    f.path as file_path,
                    e.qualified_name,
                    c.start_line,
                    c.end_line,
                    1 - (c.embedding <=> $1::vector) as similarity
                FROM code_chunks c
                JOIN files f ON c.file_id = f.id
                LEFT JOIN entities e ON c.entity_id = e.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT 5
            """, query_embedding)
            
            similar_code = [dict(row) for row in similar]
    
    return {
        'crash_summary': {
            'error_type': error_context['error_type'],
            'error_message': error_context['error_message'],
            'top_frame': frames[0] if frames else None,
            'frame_count': len(frames),
            'variables': variables
        },
        'stack_frames': frames,
        'frame_code': frame_code,
        'error_context': error_context,
        'similar_code': similar_code
    }


async def find_code_by_symbol(symbol: str, db_pool) -> List[Dict[str, Any]]:
    """
    Quick lookup of code by symbol name (for manual dump analysis)
    """
    async with db_pool.acquire() as conn:
        results = await conn.fetch("""
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
            ORDER BY e.qualified_name
            LIMIT 10
        """, f"%{symbol}%", symbol.split('::')[-1])
        
        return [dict(row) for row in results]


async def find_code_at_location(file_path: str, line_number: int, db_pool) -> Optional[Dict[str, Any]]:
    """
    Find the code entity at a specific file location
    """
    async with db_pool.acquire() as conn:
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
            WHERE f.path LIKE $1 
              AND e.start_line <= $2 
              AND e.end_line >= $2
            ORDER BY (e.end_line - e.start_line) ASC  -- Smallest enclosing entity
            LIMIT 1
        """, f"%{Path(file_path).name}%", line_number)
        
        return dict(result) if result else None
