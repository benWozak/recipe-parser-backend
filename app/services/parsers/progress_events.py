"""
Progress event system for real-time parsing status updates.
Provides structured events for streaming parsing progress to frontend.
"""
import time
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProgressPhase(Enum):
    """Parsing phases in order of execution"""
    INITIALIZING = "initializing"
    RATE_LIMITING = "rate_limiting"
    TRYING_SCRAPERS = "trying_scrapers"
    SCRAPERS_FAILED = "scrapers_failed"
    TRYING_MANUAL = "trying_manual"
    MANUAL_BLOCKED = "manual_blocked"
    TRYING_BROWSER = "trying_browser"
    PARSING_CONTENT = "parsing_content"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressStatus(Enum):
    """Status of current operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class ProgressEvent:
    """Structured progress event data"""
    event_id: str
    phase: ProgressPhase
    status: ProgressStatus
    message: str
    timestamp: float
    
    # Optional detailed information
    method: Optional[str] = None  # e.g., "recipe-scrapers", "manual", "browser"
    attempt: Optional[int] = None
    total_attempts: Optional[int] = None
    duration_ms: Optional[int] = None
    
    # Metadata and context
    metadata: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
    suggestions: Optional[List[str]] = None
    
    # Progress indicators
    progress_percent: Optional[int] = None
    estimated_remaining_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "event_id": self.event_id,
            "phase": self.phase.value,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "method": self.method,
            "attempt": self.attempt,
            "total_attempts": self.total_attempts,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata or {},
            "error_details": self.error_details,
            "suggestions": self.suggestions or [],
            "progress_percent": self.progress_percent,
            "estimated_remaining_ms": self.estimated_remaining_ms,
        }
    
    def to_sse_format(self) -> str:
        """Format as Server-Sent Event"""
        data = json.dumps(self.to_dict())
        return f"data: {data}\n\n"


class ProgressEventEmitter:
    """Emits progress events during parsing operations"""
    
    def __init__(self, url: str, session_id: str):
        self.url = url
        self.session_id = session_id
        self.start_time = time.time()
        self.event_counter = 0
        self.current_phase = ProgressPhase.INITIALIZING
        self.events: List[ProgressEvent] = []
        self.listeners: List[Callable[[ProgressEvent], None]] = []
        
        # Phase timing for progress estimation
        self.phase_start_times: Dict[ProgressPhase, float] = {}
        self.phase_durations: Dict[ProgressPhase, float] = {}
        
        # Expected phase durations (in seconds) for progress estimation
        self.expected_durations = {
            ProgressPhase.INITIALIZING: 0.5,
            ProgressPhase.RATE_LIMITING: 2.0,
            ProgressPhase.TRYING_SCRAPERS: 5.0,
            ProgressPhase.TRYING_MANUAL: 8.0,
            ProgressPhase.TRYING_BROWSER: 15.0,
            ProgressPhase.PARSING_CONTENT: 2.0,
            ProgressPhase.VALIDATING: 1.0,
        }
    
    def add_listener(self, listener: Callable[[ProgressEvent], None]) -> None:
        """Add event listener"""
        self.listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[ProgressEvent], None]) -> None:
        """Remove event listener"""
        if listener in self.listeners:
            self.listeners.remove(listener)
    
    def emit_event(
        self,
        phase: ProgressPhase,
        status: ProgressStatus,
        message: str,
        method: Optional[str] = None,
        attempt: Optional[int] = None,
        total_attempts: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None,
        suggestions: Optional[List[str]] = None
    ) -> ProgressEvent:
        """Emit a progress event"""
        
        # Update phase tracking
        current_time = time.time()
        if phase != self.current_phase:
            if self.current_phase in self.phase_start_times:
                duration = current_time - self.phase_start_times[self.current_phase]
                self.phase_durations[self.current_phase] = duration
            
            self.current_phase = phase
            self.phase_start_times[phase] = current_time
        
        # Calculate progress and estimates
        progress_percent = self._calculate_progress_percent()
        estimated_remaining = self._estimate_remaining_time()
        duration_ms = int((current_time - self.start_time) * 1000)
        
        # Create event
        self.event_counter += 1
        event = ProgressEvent(
            event_id=f"{self.session_id}-{self.event_counter}",
            phase=phase,
            status=status,
            message=message,
            timestamp=current_time,
            method=method,
            attempt=attempt,
            total_attempts=total_attempts,
            duration_ms=duration_ms,
            metadata=metadata,
            error_details=error_details,
            suggestions=suggestions,
            progress_percent=progress_percent,
            estimated_remaining_ms=estimated_remaining
        )
        
        # Store and emit
        self.events.append(event)
        logger.debug(f"Progress event: {phase.value} - {message}")
        
        # Notify listeners
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in progress event listener: {e}")
        
        return event
    
    def _calculate_progress_percent(self) -> int:
        """Calculate overall progress percentage"""
        phase_weights = {
            ProgressPhase.INITIALIZING: 5,
            ProgressPhase.RATE_LIMITING: 10,
            ProgressPhase.TRYING_SCRAPERS: 25,
            ProgressPhase.TRYING_MANUAL: 35,
            ProgressPhase.TRYING_BROWSER: 50,
            ProgressPhase.PARSING_CONTENT: 85,
            ProgressPhase.VALIDATING: 95,
            ProgressPhase.COMPLETED: 100,
            ProgressPhase.FAILED: 0,
        }
        
        base_progress = phase_weights.get(self.current_phase, 0)
        
        # Add sub-progress within current phase if available
        if self.current_phase in self.phase_start_times:
            phase_elapsed = time.time() - self.phase_start_times[self.current_phase]
            expected_duration = self.expected_durations.get(self.current_phase, 5.0)
            phase_progress = min(1.0, phase_elapsed / expected_duration)
            
            # Get next phase weight for interpolation
            phase_list = list(ProgressPhase)
            current_idx = phase_list.index(self.current_phase)
            if current_idx < len(phase_list) - 1:
                next_phase = phase_list[current_idx + 1]
                next_weight = phase_weights.get(next_phase, base_progress + 10)
                base_progress += int((next_weight - base_progress) * phase_progress)
        
        return min(100, max(0, base_progress))
    
    def _estimate_remaining_time(self) -> Optional[int]:
        """Estimate remaining time in milliseconds"""
        if self.current_phase in [ProgressPhase.COMPLETED, ProgressPhase.FAILED]:
            return 0
        
        # Calculate based on expected durations
        remaining_phases = []
        phase_list = list(ProgressPhase)
        current_idx = phase_list.index(self.current_phase)
        
        # Add remaining time for current phase
        if self.current_phase in self.phase_start_times:
            phase_elapsed = time.time() - self.phase_start_times[self.current_phase]
            expected_duration = self.expected_durations.get(self.current_phase, 5.0)
            remaining_in_phase = max(0, expected_duration - phase_elapsed)
            remaining_phases.append(remaining_in_phase)
        
        # Add time for future phases
        for i in range(current_idx + 1, len(phase_list)):
            phase = phase_list[i]
            if phase in [ProgressPhase.COMPLETED, ProgressPhase.FAILED]:
                break
            expected = self.expected_durations.get(phase, 5.0)
            remaining_phases.append(expected)
        
        total_remaining = sum(remaining_phases)
        return int(total_remaining * 1000) if total_remaining > 0 else None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of parsing session"""
        current_time = time.time()
        total_duration = current_time - self.start_time
        
        return {
            "session_id": self.session_id,
            "url": self.url,
            "start_time": self.start_time,
            "total_duration_ms": int(total_duration * 1000),
            "current_phase": self.current_phase.value,
            "total_events": len(self.events),
            "progress_percent": self._calculate_progress_percent(),
            "estimated_remaining_ms": self._estimate_remaining_time(),
            "phase_durations": {
                phase.value: duration for phase, duration in self.phase_durations.items()
            }
        }


class ProgressEventStream:
    """Manages streaming of progress events via Server-Sent Events"""
    
    def __init__(self):
        self.active_sessions: Dict[str, ProgressEventEmitter] = {}
        self.session_streams: Dict[str, List[asyncio.Queue]] = {}
    
    def create_session(self, url: str, session_id: str) -> ProgressEventEmitter:
        """Create new progress tracking session"""
        emitter = ProgressEventEmitter(url, session_id)
        self.active_sessions[session_id] = emitter
        self.session_streams[session_id] = []
        
        # Add listener to forward events to streams
        def forward_to_streams(event: ProgressEvent):
            if session_id in self.session_streams:
                for queue in self.session_streams[session_id]:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning(f"Progress event queue full for session {session_id}")
        
        emitter.add_listener(forward_to_streams)
        return emitter
    
    def get_session(self, session_id: str) -> Optional[ProgressEventEmitter]:
        """Get existing session"""
        return self.active_sessions.get(session_id)
    
    async def subscribe_to_session(self, session_id: str) -> AsyncGenerator[ProgressEvent, None]:
        """Subscribe to progress events for a session"""
        if session_id not in self.session_streams:
            return
        
        queue = asyncio.Queue(maxsize=100)
        self.session_streams[session_id].append(queue)
        
        try:
            while True:
                try:
                    # Wait for next event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                    
                    # Stop streaming if session is complete
                    if event.phase in [ProgressPhase.COMPLETED, ProgressPhase.FAILED]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    continue
                    
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            if session_id in self.session_streams:
                if queue in self.session_streams[session_id]:
                    self.session_streams[session_id].remove(queue)
    
    def cleanup_session(self, session_id: str):
        """Clean up completed session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.session_streams:
            del self.session_streams[session_id]
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all active sessions"""
        return {
            session_id: emitter.get_summary()
            for session_id, emitter in self.active_sessions.items()
        }


# Global progress event stream instance
progress_stream = ProgressEventStream()