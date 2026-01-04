"""
LangGraph Event Generation Workflow

Implements auto-iterative optimization event generation using StateGraph:
Retrieve → Generate → Validate → [Refine Loop] → Finalize
"""

from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

from backend.core.models import BranchOptions, QualityMetrics, GameEvent
from backend.core.llm import get_llm
from backend.core.config import settings


# ============================================================================
# State Definition
# ============================================================================

class EventGenerationState(TypedDict):
    """Event generation workflow state"""
    # Input
    country: str
    year: int
    month: int
    history_summary: str

    # Intermediate state
    rag_context: str
    draft_events: BranchOptions | None
    quality_metrics: QualityMetrics | None
    quality_score: float

    # Output
    final_events: BranchOptions | None

    # Counter (accumulate)
    iterations: Annotated[int, operator.add]


# ============================================================================
# Event Generation Workflow Class
# ============================================================================

class EventGenerationWorkflow:
    """Event generation workflow"""

    def __init__(self, knowledge_base=None, llm=None):
        """
        Initialize workflow

        Args:
            knowledge_base: RAG knowledge base (optional)
            llm: LLM instance (optional, uses global instance by default)
        """
        self.knowledge_base = knowledge_base
        self.llm = llm or get_llm()
        self.parser = PydanticOutputParser(pydantic_object=BranchOptions)

        # Build workflow graph
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build LangGraph workflow"""

        workflow = StateGraph(EventGenerationState)

        # Add nodes
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("validate_quality", self.validate_quality)
        workflow.add_node("refine_events", self.refine_events)
        workflow.add_node("finalize", self.finalize)

        # Define edges
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_draft")
        workflow.add_edge("generate_draft", "validate_quality")

        # Conditional edge: decide path based on quality
        workflow.add_conditional_edges(
            "validate_quality",
            self.should_refine,
            {
                "refine": "refine_events",
                "finalize": "finalize"
            }
        )

        # Re-validate after refinement
        workflow.add_edge("refine_events", "validate_quality")

        # End after finalization
        workflow.add_edge("finalize", END)

        return workflow.compile()

    # ------------------------------------------------------------------------
    # Node Implementations
    # ------------------------------------------------------------------------

    def retrieve_context(self, state: EventGenerationState) -> EventGenerationState:
        """
        Node 1: RAG Retrieve Historical Context

        Retrieve relevant historical events from knowledge base as generation context
        """
        if self.knowledge_base is None:
            state["rag_context"] = "(Knowledge base not configured)"
            return state

        query = f"{state['country']} {state['year']}.{state['month']}"

        try:
            results = self.knowledge_base.search(query, top_k=5)

            # Format context
            context_parts = []
            for i, result in enumerate(results, 1):
                event = result.event  # RAGResult is Pydantic object
                score = result.score
                context_parts.append(
                    f"{i}. {event.year}.{event.month} - "
                    f"{event.name} (relevance: {score:.2f})\n"
                    f"   {event.description}"
                )

            state["rag_context"] = "\n\n".join(context_parts)

        except Exception as e:
            print(f"RAG retrieval failed: {e}")
            state["rag_context"] = "(Retrieval failed)"

        return state

    def generate_draft(self, state: EventGenerationState) -> EventGenerationState:
        """
        Node 2: Generate Event Draft

        Use LLM to generate initial event options
        """
        # Build prompt
        prompt = ChatPromptTemplate.from_template(
            """You are a WWII history expert and game designer.

【Historical Background Reference】
{rag_context}

【Current Game Situation】
Country: {country}
Time: {year}/{month}
History: {history_summary}

【Task】
Generate 4 different strategic options for {country}.

【Requirements】
1. The 4 options must have completely different types:
   - military
   - diplomatic
   - economic
   - political

2. Each option must:
   - Align with historical background and current situation
   - Have clear actions and expected results
   - Have reasonable likelihood score (0.0-1.0)
   - Have concise description (20-80 words, shorter is better)

3. Options should cover different strategic directions:
   - Aggressive offensive
   - Steady expansion
   - Defensive consolidation
   - Diplomatic/political

4. The reasoning field should explain why these options are reasonable and diverse

{format_instructions}

Output JSON directly, do not add markdown code block markers or explanatory text.
"""
        )

        try:
            # Build chain
            chain = prompt | self.llm | self.parser

            # Invoke
            draft = chain.invoke({
                "country": state["country"],
                "year": state["year"],
                "month": state["month"],
                "history_summary": state.get("history_summary", "Game start"),
                "rag_context": state.get("rag_context", ""),
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = draft
            state["iterations"] = 1  # Accumulate count

        except Exception as e:
            print(f"Generation failed: {e}")
            # Create empty placeholder
            state["draft_events"] = None
            state["iterations"] = 1

        return state

    def validate_quality(self, state: EventGenerationState) -> EventGenerationState:
        """
        Node 3: Quality Validation

        Multi-dimensional quality assessment
        """
        if state["draft_events"] is None:
            state["quality_score"] = 0.0
            state["quality_metrics"] = QualityMetrics(
                format_valid=0.0,
                diversity=0.0,
                consistency=0.0,
                historical_accuracy=0.0
            )
            return state

        events = state["draft_events"]

        # Evaluate each dimension
        metrics = QualityMetrics(
            format_valid=self._check_format(events),
            diversity=self._check_diversity(events),
            consistency=self._check_consistency(events, state),
            historical_accuracy=self._check_historical(events)
        )

        state["quality_metrics"] = metrics
        state["quality_score"] = metrics.overall_score

        return state

    def refine_events(self, state: EventGenerationState) -> EventGenerationState:
        """
        Node 4: Refinement

        Improve events based on validation results
        """
        # Check if draft_events is None
        if state["draft_events"] is None:
            print("   [WARNING] draft_events is None, skipping refinement")
            return state

        metrics = state["quality_metrics"]
        if metrics is None:
            return state

        # Identify issues
        issues = []
        if metrics.format_valid < 0.8:
            issues.append("Format incomplete or non-standard")
        if metrics.diversity < 0.8:
            issues.append("Option types not diverse enough, duplicate types exist")
        if metrics.consistency < 0.8:
            issues.append("Time or country information inconsistent")
        if metrics.historical_accuracy < 0.8:
            issues.append("Historical likelihood scores unreasonable")

        if not issues:
            return state

        # Build refinement prompt
        prompt = ChatPromptTemplate.from_template(
            """The following events have quality issues. Please improve them.

【Original Events】
{draft_events}

【Identified Issues】
{issues}

【Improvement Requirements】
1. If types are not diverse enough: Ensure 4 options have completely different types (one each of military, diplomatic, economic, political)
2. If consistency is insufficient: Check that year={year}, month={month}, country={country} are correct
3. If historical accuracy is insufficient: Adjust likelihood scores to better match historical reality

Keep other high-quality parts unchanged.

{format_instructions}

Output the improved JSON directly.
"""
        )

        try:
            chain = prompt | self.llm | self.parser

            improved = chain.invoke({
                "draft_events": state["draft_events"].model_dump_json(indent=2),
                "issues": "\n".join(f"- {issue}" for issue in issues),
                "year": state["year"],
                "month": state["month"],
                "country": state["country"],
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = improved
            state["iterations"] = 1  # Accumulate

        except Exception as e:
            print(f"Refinement failed: {e}")
            state["iterations"] = 1

        return state

    def finalize(self, state: EventGenerationState) -> EventGenerationState:
        """
        Node 5: Finalization

        Mark complete and save final result
        """
        if state["draft_events"] is not None:
            # Add metadata
            state["draft_events"].generation_metadata = {
                "iterations": state.get("iterations", 0),
                "quality_score": state.get("quality_score", 0.0),
                "quality_metrics": state["quality_metrics"].model_dump() if state.get("quality_metrics") else None
            }

        state["final_events"] = state["draft_events"]
        return state

    # ------------------------------------------------------------------------
    # Conditional Logic
    # ------------------------------------------------------------------------

    def should_refine(self, state: EventGenerationState) -> str:
        """
        Decide whether refinement is needed

        Returns:
            "refine" - Continue refinement
            "finalize" - Complete
        """
        quality = state.get("quality_score", 0.0)
        iterations = state.get("iterations", 0)

        # Quality meets threshold
        if quality >= settings.QUALITY_THRESHOLD:
            return "finalize"

        # Too many iterations
        if iterations >= settings.MAX_GENERATION_RETRIES:
            return "finalize"

        # Need refinement
        return "refine"

    # ------------------------------------------------------------------------
    # Quality Check Helper Methods
    # ------------------------------------------------------------------------

    def _check_format(self, events: BranchOptions) -> float:
        """Check format correctness"""
        if len(events.branches) == 4:
            return 1.0
        return len(events.branches) / 4.0

    def _check_diversity(self, events: BranchOptions) -> float:
        """Check diversity (types should not repeat)"""
        if not events.branches:
            return 0.0

        types = [e.event_type for e in events.branches]
        unique_types = len(set(types))

        # Expect 4 different types
        return unique_types / 4.0

    def _check_consistency(self, events: BranchOptions, state: EventGenerationState) -> float:
        """Check consistency (time, country)"""
        if not events.branches:
            return 0.0

        score = 1.0
        for event in events.branches:
            # Time consistency
            if event.year != state["year"] or event.month != state["month"]:
                score -= 0.25

        return max(0.0, score)

    def _check_historical(self, events: BranchOptions) -> float:
        """Check historical accuracy (likelihood reasonableness)"""
        if not events.branches:
            return 0.0

        # Check if likelihood is in reasonable range
        likelihoods = [e.likelihood for e in events.branches]
        avg = sum(likelihoods) / len(likelihoods)

        # Average should be between 0.3-0.8
        if 0.3 <= avg <= 0.8:
            return 0.9
        else:
            return 0.6

    # ------------------------------------------------------------------------
    # Public Interface
    # ------------------------------------------------------------------------

    def generate(
        self,
        country: str,
        year: int,
        month: int,
        history_summary: str = ""
    ) -> BranchOptions | None:
        """
        Generate event branches

        Args:
            country: Country code
            year: Year
            month: Month
            history_summary: History summary

        Returns:
            Generated branch options
        """
        # Prepare initial state
        initial_state = {
            "country": country,
            "year": year,
            "month": month,
            "history_summary": history_summary or "Game start",
            "iterations": 0,
            "quality_score": 0.0
        }

        # Execute workflow
        result = self.graph.invoke(initial_state)

        return result.get("final_events")


# ============================================================================
# Convenience Functions
# ============================================================================

def create_event_generation_workflow(knowledge_base=None) -> EventGenerationWorkflow:
    """
    Create event generation workflow instance

    Args:
        knowledge_base: RAG knowledge base (optional)

    Returns:
        Workflow instance
    """
    return EventGenerationWorkflow(knowledge_base=knowledge_base)
