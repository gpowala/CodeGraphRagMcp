"""
C++ Code Parser using tree-sitter
Extracts entities, relationships, and creates intelligent chunks
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser, Node
import re

CPP_LANGUAGE = Language(tscpp.language(), "cpp")

@dataclass
class Entity:
    """Represents a code entity (class, function, etc.)"""
    type: str  # class, function, namespace, struct, enum, typedef
    simple_name: str
    qualified_name: str
    signature: Optional[str]
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    is_public: bool
    parent_id: Optional[int]
    complexity_score: int
    metadata: Dict[str, Any]

@dataclass
class Relationship:
    """Represents a relationship between entities"""
    from_entity: str  # qualified name
    to_entity: str    # qualified name or raw symbol
    relationship_type: str  # calls, inherits, includes, uses, overrides
    context: str
    line_number: int

@dataclass
class CodeChunk:
    """Represents a chunk of code for embedding"""
    entity_name: Optional[str]
    chunk_type: str  # implementation, declaration, comment_block, mixed
    content: str
    start_line: int
    end_line: int
    metadata: Dict[str, Any]

class CppParser:
    """Parse C++ code and extract entities, relationships, and chunks"""
    
    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(CPP_LANGUAGE)
        self.current_namespace: List[str] = []
        self.current_class: Optional[str] = None
        
    def parse_file(self, file_path: Path, content: str) -> Tuple[List[Entity], List[Relationship], List[CodeChunk]]:
        """Parse a C++ file and return entities, relationships, and chunks"""
        tree = self.parser.parse(bytes(content, "utf8"))
        
        entities = []
        relationships = []
        chunks = []
        
        self.current_namespace = []
        self.current_class = None
        
        # Extract entities
        self._extract_entities(tree.root_node, content, entities, relationships)
        
        # Extract chunks
        chunks = self._create_chunks(entities, content)
        
        # Extract relationships (includes, calls, etc.)
        self._extract_relationships(tree.root_node, content, relationships)
        
        return entities, relationships, chunks
    
    def _extract_entities(self, node: Node, content: str, entities: List[Entity], 
                         relationships: List[Relationship], parent_name: Optional[str] = None):
        """Recursively extract entities from AST"""
        
        # Namespace declaration
        if node.type == "namespace_definition":
            namespace_node = node.child_by_field_name("name")
            if namespace_node:
                namespace_name = self._get_node_text(namespace_node, content)
                self.current_namespace.append(namespace_name)
                
                # Process namespace body
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        self._extract_entities(child, content, entities, relationships, "::".join(self.current_namespace))
                
                self.current_namespace.pop()
            return
        
        # Class/Struct declaration
        elif node.type in ["class_specifier", "struct_specifier"]:
            name_node = node.child_by_field_name("name")
            if name_node:
                simple_name = self._get_node_text(name_node, content)
                qualified_name = self._build_qualified_name(simple_name)
                
                # Extract base classes (inheritance)
                base_clause = node.child_by_field_name("base_clause")
                if base_clause:
                    for base in self._extract_base_classes(base_clause, content):
                        relationships.append(Relationship(
                            from_entity=qualified_name,
                            to_entity=base,
                            relationship_type="inherits",
                            context=f"class {simple_name} : {base}",
                            line_number=node.start_point[0] + 1
                        ))
                
                entity = Entity(
                    type="class" if node.type == "class_specifier" else "struct",
                    simple_name=simple_name,
                    qualified_name=qualified_name,
                    signature=f"{node.type.replace('_specifier', '')} {simple_name}",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    is_public=True,
                    parent_id=None,  # Will be resolved later
                    complexity_score=0,
                    metadata={"has_templates": self._has_template_params(node)}
                )
                entities.append(entity)
                
                # Process class body
                old_class = self.current_class
                self.current_class = qualified_name
                
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        self._extract_entities(child, content, entities, relationships, qualified_name)
                
                self.current_class = old_class
            return
        
        # Function declaration/definition
        elif node.type in ["function_definition", "function_declarator"]:
            # Get function name
            declarator = node if node.type == "function_declarator" else node.child_by_field_name("declarator")
            if declarator:
                name_node = self._get_function_name_node(declarator)
                if name_node:
                    simple_name = self._get_node_text(name_node, content)
                    qualified_name = self._build_qualified_name(simple_name)
                    
                    # Build signature
                    signature = self._extract_function_signature(node, content)
                    
                    # Calculate complexity (simple heuristic: count if/for/while/switch)
                    complexity = self._calculate_complexity(node, content)
                    
                    entity = Entity(
                        type="function",
                        simple_name=simple_name,
                        qualified_name=qualified_name,
                        signature=signature,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        is_public=self._is_public(node),
                        parent_id=None,
                        complexity_score=complexity,
                        metadata={
                            "is_definition": node.type == "function_definition",
                            "has_templates": self._has_template_params(node.parent) if node.parent else False
                        }
                    )
                    entities.append(entity)
            return
        
        # Enum declaration
        elif node.type == "enum_specifier":
            name_node = node.child_by_field_name("name")
            if name_node:
                simple_name = self._get_node_text(name_node, content)
                qualified_name = self._build_qualified_name(simple_name)
                
                entity = Entity(
                    type="enum",
                    simple_name=simple_name,
                    qualified_name=qualified_name,
                    signature=f"enum {simple_name}",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    is_public=True,
                    parent_id=None,
                    complexity_score=0,
                    metadata={}
                )
                entities.append(entity)
            return
        
        # Recursively process children
        for child in node.children:
            self._extract_entities(child, content, entities, relationships, parent_name)
    
    def _extract_relationships(self, node: Node, content: str, relationships: List[Relationship]):
        """Extract call relationships and includes"""
        
        # Include statements
        if node.type == "preproc_include":
            include_path = None
            for child in node.children:
                if child.type in ["string_literal", "system_lib_string"]:
                    include_path = self._get_node_text(child, content).strip('"<>')
                    break
            
            if include_path:
                relationships.append(Relationship(
                    from_entity="",  # File-level relationship
                    to_entity=include_path,
                    relationship_type="includes",
                    context=self._get_node_text(node, content),
                    line_number=node.start_point[0] + 1
                ))
        
        # Function calls
        elif node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node:
                called_function = self._get_node_text(function_node, content)
                # We'll record this and resolve to actual entity later
                relationships.append(Relationship(
                    from_entity="",  # Will be filled in context
                    to_entity=called_function,
                    relationship_type="calls",
                    context=self._get_node_text(node, content)[:200],  # Truncate long calls
                    line_number=node.start_point[0] + 1
                ))
        
        # Recursively process children
        for child in node.children:
            self._extract_relationships(child, content, relationships)
    
    def _create_chunks(self, entities: List[Entity], content: str) -> List[CodeChunk]:
        """Create intelligent chunks from entities"""
        chunks = []
        lines = content.splitlines()
        
        for entity in entities:
            # Get the entity code
            entity_lines = lines[entity.start_line - 1:entity.end_line]
            entity_code = "\n".join(entity_lines)
            
            # Determine chunk type
            if entity.type == "function" and entity.metadata.get("is_definition"):
                chunk_type = "implementation"
            elif entity.type == "function":
                chunk_type = "declaration"
            elif entity.type in ["class", "struct"]:
                chunk_type = "declaration"
            else:
                chunk_type = "mixed"
            
            # For large entities, create multiple chunks
            if len(entity_lines) > 100:
                # Split into smaller chunks (e.g., by method for classes)
                # For now, just take the first 100 lines
                chunk_code = "\n".join(entity_lines[:100])
                chunks.append(CodeChunk(
                    entity_name=entity.qualified_name,
                    chunk_type=chunk_type,
                    content=chunk_code,
                    start_line=entity.start_line,
                    end_line=entity.start_line + 100,
                    metadata={"truncated": True, "original_end": entity.end_line}
                ))
            else:
                chunks.append(CodeChunk(
                    entity_name=entity.qualified_name,
                    chunk_type=chunk_type,
                    content=entity_code,
                    start_line=entity.start_line,
                    end_line=entity.end_line,
                    metadata={}
                ))
            
            # Extract comment blocks before the entity (often contain important context)
            if entity.start_line > 1:
                # Look backwards for comment block
                comment_lines = []
                for i in range(entity.start_line - 2, max(-1, entity.start_line - 20), -1):
                    line = lines[i].strip()
                    if line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                        comment_lines.insert(0, lines[i])
                    elif line == "":
                        continue
                    else:
                        break
                
                if len(comment_lines) > 2:  # Only if substantial comment
                    comment_text = "\n".join(comment_lines)
                    chunks.append(CodeChunk(
                        entity_name=entity.qualified_name,
                        chunk_type="comment_block",
                        content=comment_text + "\n\n" + entity_code[:200],  # Include snippet
                        start_line=entity.start_line - len(comment_lines),
                        end_line=entity.start_line,
                        metadata={"comment_for": entity.qualified_name}
                    ))
        
        return chunks
    
    # Helper methods
    
    def _get_node_text(self, node: Node, content: str) -> str:
        """Get text content of a node"""
        return content[node.start_byte:node.end_byte]
    
    def _build_qualified_name(self, simple_name: str) -> str:
        """Build fully qualified name with namespace and class context"""
        parts = []
        if self.current_namespace:
            parts.extend(self.current_namespace)
        if self.current_class:
            parts.append(self.current_class.split("::")[-1])  # Just the class name
        parts.append(simple_name)
        return "::".join(parts)
    
    def _get_function_name_node(self, declarator: Node) -> Optional[Node]:
        """Extract function name from declarator"""
        if declarator.type == "function_declarator":
            declarator = declarator.child_by_field_name("declarator")
        
        if declarator:
            if declarator.type == "identifier":
                return declarator
            elif declarator.type in ["qualified_identifier", "field_identifier"]:
                # Return the last identifier
                for child in reversed(declarator.children):
                    if child.type in ["identifier", "field_identifier"]:
                        return child
            elif declarator.type == "destructor_name":
                return declarator
        
        return None
    
    def _extract_function_signature(self, node: Node, content: str) -> str:
        """Extract function signature"""
        # This is simplified - full signature extraction is complex
        declarator = node if node.type == "function_declarator" else node.child_by_field_name("declarator")
        if declarator:
            return self._get_node_text(declarator, content)
        return ""
    
    def _extract_base_classes(self, base_clause: Node, content: str) -> List[str]:
        """Extract base class names from inheritance clause"""
        bases = []
        for child in base_clause.children:
            if child.type == "type_identifier":
                bases.append(self._get_node_text(child, content))
            elif child.type == "qualified_identifier":
                bases.append(self._get_node_text(child, content))
        return bases
    
    def _has_template_params(self, node: Optional[Node]) -> bool:
        """Check if node has template parameters"""
        if not node:
            return False
        return node.type == "template_declaration"
    
    def _is_public(self, node: Node) -> bool:
        """Determine if a member is public (simplified)"""
        # In a real implementation, track access specifiers
        return True
    
    def _calculate_complexity(self, node: Node, content: str) -> int:
        """Calculate cyclomatic complexity (simplified)"""
        complexity = 1  # Base complexity
        
        def count_control_flow(n: Node):
            nonlocal complexity
            if n.type in ["if_statement", "while_statement", "for_statement", 
                         "switch_statement", "case_statement", "catch_clause"]:
                complexity += 1
            for child in n.children:
                count_control_flow(child)
        
        count_control_flow(node)
        return complexity

def parse_cpp_file(file_path: Path, content: str) -> Tuple[List[Entity], List[Relationship], List[CodeChunk]]:
    """Convenience function to parse a C++ file"""
    parser = CppParser()
    return parser.parse_file(file_path, content)
