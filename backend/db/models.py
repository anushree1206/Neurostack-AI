from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean,
    DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.database import Base
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    query = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, running, done, failed
    final_answer = Column(Text, nullable=True)
    provenance_map = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    events = relationship("ExecutionEvent", back_populates="job", order_by="ExecutionEvent.sequence")
    tool_calls = relationship("ToolCallLog", back_populates="job")


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    agent_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    input_hash = Column(String, nullable=True)
    output_hash = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)
    content = Column(JSON, nullable=True)
    policy_violation = Column(String, nullable=True)

    job = relationship("Job", back_populates="events")


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    agent_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    attempt = Column(Integer, default=0)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    latency_ms = Column(Float, nullable=True)
    accepted = Column(Boolean, nullable=True)
    failure_mode = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    job = relationship("Job", back_populates="tool_calls")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(String, primary_key=True, default=gen_uuid)
    run_label = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    summary = Column(JSON, nullable=True)
    prompt_versions = Column(JSON, nullable=True)

    results = relationship("EvalResult", back_populates="run")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("eval_runs.id"), nullable=False)
    case_id = Column(String, nullable=False)
    case_category = Column(String, nullable=False)
    query = Column(Text, nullable=False)
    job_id = Column(String, nullable=True)
    final_answer = Column(Text, nullable=True)
    score_correctness = Column(Float, nullable=True)
    score_citation = Column(Float, nullable=True)
    score_contradiction = Column(Float, nullable=True)
    score_tool_efficiency = Column(Float, nullable=True)
    score_budget_compliance = Column(Float, nullable=True)
    score_critique_agreement = Column(Float, nullable=True)
    score_overall = Column(Float, nullable=True)
    justifications = Column(JSON, nullable=True)
    prompts_used = Column(JSON, nullable=True)
    tool_calls_made = Column(JSON, nullable=True)
    passed = Column(Boolean, default=True)
    timestamp = Column(DateTime, server_default=func.now())

    run = relationship("EvalRun", back_populates="results")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, nullable=False)
    dimension = Column(String, nullable=False)
    original_prompt = Column(Text, nullable=False)
    proposed_prompt = Column(Text, nullable=False)
    diff = Column(Text, nullable=True)
    justification = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, approved, rejected
    eval_run_id = Column(String, ForeignKey("eval_runs.id"), nullable=True)
    delta_score = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
