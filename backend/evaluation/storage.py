"""
Evaluation Storage System

Stores all evaluation data in database for reproducibility and regression detection.
Provides queryable interface for historical evaluation data.
"""

import json
import sqlite3
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import asdict
import asyncio
import logging

logger = logging.getLogger(__name__)

class EvaluationStorage:
    """Database storage for evaluation results and traces"""
    
    def __init__(self, db_path: str = "evaluation.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                test_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                subcategory TEXT,
                query TEXT NOT NULL,
                expected_answer TEXT,
                expected_citations TEXT,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Execution traces table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                prompts_sent TEXT NOT NULL,
                tool_calls_made TEXT NOT NULL,
                outputs_received TEXT NOT NULL,
                routing_decisions TEXT NOT NULL,
                total_latency_ms REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES test_cases (test_id)
            )
        """)
        
        # Evaluation scores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                answer_correctness REAL NOT NULL,
                citation_accuracy REAL NOT NULL,
                contradiction_resolution REAL NOT NULL,
                tool_efficiency REAL NOT NULL,
                context_compliance REAL NOT NULL,
                critique_agreement REAL NOT NULL,
                overall_score REAL NOT NULL,
                justification TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES test_cases (test_id)
            )
        """)
        
        # Evaluation runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY,
                total_tests INTEGER NOT NULL,
                execution_time_seconds REAL NOT NULL,
                summary TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Prompt rewrites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_rewrites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                old_prompt TEXT NOT NULL,
                new_prompt TEXT NOT NULL,
                diff_summary TEXT NOT NULL,
                justification TEXT NOT NULL,
                status TEXT NOT NULL,
                performance_delta REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs (run_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    async def store_test_result(self, run_id: str, test_case: 'TestCase', 
                           trace: 'ExecutionTrace', score: 'EvaluationScore'):
        """Store individual test result with full trace"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Store test case if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO test_cases 
                (test_id, category, subcategory, query, expected_answer, expected_citations, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                test_case.test_id, test_case.category.value, 
                test_case.subcategory.value if test_case.subcategory else None,
                test_case.query, test_case.expected_answer,
                json.dumps(test_case.expected_citations) if test_case.expected_citations else None,
                test_case.description
            ))
            
            # Store execution trace
            cursor.execute("""
                INSERT INTO execution_traces 
                (test_id, timestamp, prompts_sent, tool_calls_made, outputs_received, routing_decisions, total_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                test_case.test_id, trace.timestamp.isoformat(),
                json.dumps(trace.prompts_sent),
                json.dumps(trace.tool_calls_made),
                json.dumps(trace.outputs_received),
                json.dumps(trace.routing_decisions),
                trace.total_latency_ms
            ))
            
            # Store evaluation score
            cursor.execute("""
                INSERT INTO evaluation_scores 
                (test_id, answer_correctness, citation_accuracy, contradiction_resolution, 
                 tool_efficiency, context_compliance, critique_agreement, overall_score, justification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_case.test_id, score.answer_correctness, score.citation_accuracy,
                score.contradiction_resolution, score.tool_efficiency, score.context_compliance,
                score.critique_agreement, score.overall_score, score.justification
            ))
            
            conn.commit()
            logger.info(f"Stored test result for {test_case.test_id}")
            
        except Exception as e:
            logger.exception(f"Failed to store test result: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def store_evaluation_summary(self, run_id: str, summary: Dict[str, Any]):
        """Store evaluation run summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO evaluation_runs 
                (run_id, total_tests, execution_time_seconds, summary)
                VALUES (?, ?, ?, ?)
            """, (
                run_id, summary.get("total_tests", 0),
                summary.get("execution_time_seconds", 0.0),
                json.dumps(summary)
            ))
            
            conn.commit()
            logger.info(f"Stored evaluation summary for run {run_id}")
            
        except Exception as e:
            logger.exception(f"Failed to store evaluation summary: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def store_prompt_rewrite(self, run_id: str, test_id: str, agent_type: str,
                                old_prompt: str, new_prompt: str, diff_summary: str,
                                justification: str, status: str = 'pending',
                                performance_delta: Optional[float] = None):
        """Store proposed prompt rewrite for approval"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO prompt_rewrites 
                (run_id, test_id, agent_type, old_prompt, new_prompt, diff_summary, 
                 justification, status, performance_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, test_id, agent_type, old_prompt, new_prompt,
                diff_summary, justification, status, performance_delta
            ))
            
            conn.commit()
            logger.info(f"Stored prompt rewrite for {agent_type} - {test_id}")
            
        except Exception as e:
            logger.exception(f"Failed to store prompt rewrite: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def get_execution_trace(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full execution trace for a test case"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT et.timestamp, et.prompts_sent, et.tool_calls_made, 
                       et.outputs_received, et.routing_decisions, et.total_latency_ms
                FROM execution_traces et
                WHERE et.test_id = ?
                ORDER BY et.timestamp
            """, (test_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "test_id": test_id,
                    "timestamp": row[0],
                    "prompts_sent": json.loads(row[1]),
                    "tool_calls_made": json.loads(row[2]),
                    "outputs_received": json.loads(row[3]),
                    "routing_decisions": json.loads(row[4]),
                    "total_latency_ms": row[5]
                }
            return None
            
        except Exception as e:
            logger.exception(f"Failed to get execution trace: {e}")
            return None
        finally:
            conn.close()
    
    async def get_evaluation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent evaluation runs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT run_id, total_tests, execution_time_seconds, summary, created_at
                FROM evaluation_runs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            return [
                {
                    "run_id": row[0],
                    "total_tests": row[1],
                    "execution_time_seconds": row[2],
                    "summary": json.loads(row[3]),
                    "created_at": row[4]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.exception(f"Failed to get evaluation history: {e}")
            return []
        finally:
            conn.close()
    
    async def get_pending_rewrites(self) -> List[Dict[str, Any]]:
        """Get all pending prompt rewrites awaiting approval"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT pr.id, pr.run_id, pr.test_id, pr.agent_type, 
                       pr.diff_summary, pr.justification, pr.created_at
                FROM prompt_rewrites pr
                WHERE pr.status = 'pending'
                ORDER BY pr.created_at
            """)
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "run_id": row[1],
                    "test_id": row[2],
                    "agent_type": row[3],
                    "diff_summary": row[4],
                    "justification": row[5],
                    "created_at": row[6]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.exception(f"Failed to get pending rewrites: {e}")
            return []
        finally:
            conn.close()
    
    async def approve_rewrite(self, rewrite_id: int) -> bool:
        """Approve a prompt rewrite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE prompt_rewrites 
                SET status = 'approved', performance_delta = NULL
                WHERE id = ?
            """, (rewrite_id,))
            
            conn.commit()
            logger.info(f"Approved prompt rewrite {rewrite_id}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to approve rewrite: {e}")
            return False
        finally:
            conn.close()
    
    async def reject_rewrite(self, rewrite_id: int, reason: str) -> bool:
        """Reject a prompt rewrite with reason"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE prompt_rewrites 
                SET status = 'rejected', performance_delta = NULL
                WHERE id = ?
            """, (rewrite_id,))
            
            conn.commit()
            logger.info(f"Rejected prompt rewrite {rewrite_id}: {reason}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to reject rewrite: {e}")
            return False
        finally:
            conn.close()
    
    async def get_regression_comparison(self, run_id1: str, run_id2: str) -> Optional[Dict[str, Any]]:
        """Compare two evaluation runs to detect regressions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT es.run_id, es.summary
                FROM evaluation_runs es
                WHERE es.run_id IN (?, ?)
                ORDER BY es.created_at
            """, (run_id1, run_id2))
            
            rows = cursor.fetchall()
            if len(rows) != 2:
                return None
            
            summary1 = json.loads(rows[0][1])
            summary2 = json.loads(rows[1][1])
            
            # Calculate regression metrics
            regression = {
                "run_id_1": run_id1,
                "run_id_2": run_id2,
                "overall_delta": summary2.get("overall_average", 0) - summary1.get("overall_average", 0),
                "dimension_deltas": {},
                "regression_detected": False
            }
            
            # Compare each dimension
            for dim in ["answer_correctness", "citation_accuracy", "contradiction_resolution", 
                        "tool_efficiency", "context_compliance", "critique_agreement"]:
                avg1 = summary1.get("dimension_averages", {}).get(dim, 0)
                avg2 = summary2.get("dimension_averages", {}).get(dim, 0)
                delta = avg2 - avg1
                regression["dimension_deltas"][dim] = delta
                
                if delta < -0.1:  # Significant regression
                    regression["regression_detected"] = True
                    regression["regression_details"] = f"{dim} decreased by {abs(delta):.3f}"
            
            return regression
            
        except Exception as e:
            logger.exception(f"Failed to compare runs: {e}")
            return None
        finally:
            conn.close()
