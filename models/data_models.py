from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class CaseStatus(Enum):
    """Case status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class EvidenceType(Enum):
    """Evidence type enumeration"""
    FILE = "file"
    MEMORY = "memory"
    NETWORK = "network"
    REGISTRY = "registry"
    LOG = "log"
    OTHER = "other"

class AcquisitionType(Enum):
    """Acquisition type enumeration"""
    LOCAL = "local"
    REMOTE = "remote"
    LIVE = "live"
    DEAD = "dead"

@dataclass
class Location:
    """Location information for evidence"""
    path: str
    type: str = "file"  # file, directory, network, etc.
    description: Optional[str] = None
    size: Optional[int] = None
    hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Evidence:
    """Evidence item model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: EvidenceType = EvidenceType.FILE
    locations: List[Location] = field(default_factory=list)
    description: Optional[str] = None
    acquired_at: Optional[datetime] = None
    acquired_by: Optional[str] = None
    hash: Optional[str] = None
    size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None

@dataclass
class Case:
    """Case model for forensic investigations"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    number: str = ""
    name: str = ""
    status: CaseStatus = CaseStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    evidence: List[Evidence] = field(default_factory=list)
    locations: List[Location] = field(default_factory=list)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

@dataclass
class Agent:
    """Remote acquisition agent model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    location: str = ""
    version: Optional[str] = None
    status: str = "inactive"  # active, inactive, error
    last_seen: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TargetMachine:
    """Target machine for remote acquisition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ip_address: str = ""
    domain: Optional[str] = None
    hostname: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    description: Optional[str] = None
    credentials: Optional[Dict[str, str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AcquisitionSession:
    """Remote acquisition session model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    agent_id: str = ""
    target_id: str = ""
    type: AcquisitionType = AcquisitionType.REMOTE
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    evidence_collected: List[Evidence] = field(default_factory=list)
    error_message: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class User:
    """User model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "analyst"  # admin, analyst, viewer
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    preferences: Dict[str, Any] = field(default_factory=dict)

@dataclass
class APIResponse:
    """Standard API response model"""
    success: bool = True
    data: Optional[Any] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchCriteria:
    """Search criteria for filtering data"""
    query: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    sort_by: Optional[str] = None
    sort_order: str = "asc"  # asc, desc
    page: int = 1
    page_size: int = 20
    include_deleted: bool = False

@dataclass
class SearchResult:
    """Search result model"""
    items: List[Any] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    has_next: bool = False
    has_previous: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

# Utility functions for model operations
def case_to_dict(case: Case) -> Dict[str, Any]:
    """Convert Case model to dictionary"""
    return {
        "id": case.id,
        "number": case.number,
        "name": case.name,
        "status": case.status.value,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "created_by": case.created_by,
        "assigned_to": case.assigned_to,
        "description": case.description,
        "evidence_count": len(case.evidence),
        "locations_count": len(case.locations),
        "notes": case.notes,
        "metadata": case.metadata,
        "tags": case.tags
    }

def dict_to_case(data: Dict[str, Any]) -> Case:
    """Convert dictionary to Case model"""
    return Case(
        id=data.get("id", str(uuid.uuid4())),
        number=data.get("number", ""),
        name=data.get("name", ""),
        status=CaseStatus(data.get("status", "draft")),
        created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        created_by=data.get("created_by"),
        assigned_to=data.get("assigned_to"),
        description=data.get("description"),
        notes=data.get("notes"),
        metadata=data.get("metadata", {}),
        tags=data.get("tags", [])
    )

def evidence_to_dict(evidence: Evidence) -> Dict[str, Any]:
    """Convert Evidence model to dictionary"""
    return {
        "id": evidence.id,
        "name": evidence.name,
        "type": evidence.type.value,
        "locations": [
            {
                "path": loc.path,
                "type": loc.type,
                "description": loc.description,
                "size": loc.size,
                "hash": loc.hash,
                "metadata": loc.metadata
            }
            for loc in evidence.locations
        ],
        "description": evidence.description,
        "acquired_at": evidence.acquired_at.isoformat() if evidence.acquired_at else None,
        "acquired_by": evidence.acquired_by,
        "hash": evidence.hash,
        "size": evidence.size,
        "metadata": evidence.metadata,
        "tags": evidence.tags,
        "notes": evidence.notes
    }

def dict_to_evidence(data: Dict[str, Any]) -> Evidence:
    """Convert dictionary to Evidence model"""
    locations = []
    for loc_data in data.get("locations", []):
        locations.append(Location(
            path=loc_data.get("path", ""),
            type=loc_data.get("type", "file"),
            description=loc_data.get("description"),
            size=loc_data.get("size"),
            hash=loc_data.get("hash"),
            metadata=loc_data.get("metadata", {})
        ))
    
    return Evidence(
        id=data.get("id", str(uuid.uuid4())),
        name=data.get("name", ""),
        type=EvidenceType(data.get("type", "file")),
        locations=locations,
        description=data.get("description"),
        acquired_at=datetime.fromisoformat(data["acquired_at"]) if data.get("acquired_at") else None,
        acquired_by=data.get("acquired_by"),
        hash=data.get("hash"),
        size=data.get("size"),
        metadata=data.get("metadata", {}),
        tags=data.get("tags", []),
        notes=data.get("notes")
    ) 