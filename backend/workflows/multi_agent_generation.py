"""
Multi-Agent Event Generation Workflow

Enhanced from original EventGenerationWorkflow to support:
1. Agent personality traits affecting generation
2. World state context
3. Consideration of other agents' actions
"""

from typing import TypedDict, Annotated, Dict, List
import operator
from langchain.prompts import ChatPromptTemplate

from backend.workflows.event_generation import EventGenerationWorkflow
from backend.core.agent import CountryAgent, WorldState
from backend.core.models import BranchOptions, GameEvent


class MultiAgentGenerationState(TypedDict):
    """Multi-agent event generation state"""
    # Current agent information
    agent: CountryAgent

    # World state
    world_state: WorldState

    # Recent actions of other agents
    other_agents_actions: Dict[str, List[str]]  # country -> action names

    # Input (inherited from original workflow)
    country: str
    year: int
    month: int
    history_summary: str

    # Intermediate state
    rag_context: str
    draft_events: BranchOptions | None
    quality_metrics: object | None  # QualityMetrics
    quality_score: float

    # Output
    final_events: BranchOptions | None

    # Counter
    iterations: Annotated[int, operator.add]


class MultiAgentEventWorkflow(EventGenerationWorkflow):
    """Multi-agent event generation workflow"""

    def __init__(self, knowledge_base=None, llm=None):
        """Initialize multi-agent workflow"""
        # Call parent class initialization (but don't use its graph)
        super().__init__(knowledge_base, llm)
        # Build own graph
        self.graph = self._build_multi_agent_graph()

    def _build_multi_agent_graph(self):
        """Build multi-agent workflow graph"""
        from langgraph.graph import StateGraph, END

        workflow = StateGraph(MultiAgentGenerationState)

        # Add nodes (reuse parent class methods)
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("validate_quality", self.validate_quality)
        workflow.add_node("refine_events", self.refine_events)
        workflow.add_node("finalize", self.finalize)

        # Define edges
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_draft")
        workflow.add_edge("generate_draft", "validate_quality")

        # Conditional edges
        workflow.add_conditional_edges(
            "validate_quality",
            self.should_refine,
            {
                "refine": "refine_events",
                "finalize": "finalize"
            }
        )

        workflow.add_edge("refine_events", "validate_quality")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def generate_for_agent(
        self,
        agent: CountryAgent,
        world_state: WorldState,
        other_actions: Dict[str, List[str]] = None
    ) -> BranchOptions | None:
        """Generate events for specific agent"""

        print(f"\n[Multi-Agent Workflow] Generating events for {agent.country_name}...")

        # Prepare initial state
        initial_state = {
            "agent": agent,
            "world_state": world_state,
            "other_agents_actions": other_actions or {},
            "country": agent.country_code,
            "year": agent.current_year,
            "month": agent.current_month,
            "history_summary": self._build_agent_history(agent),
            "rag_context": "",
            "draft_events": None,
            "quality_metrics": None,
            "quality_score": 0.0,
            "final_events": None,
            "iterations": 0
        }

        # Execute workflow
        result = self.graph.invoke(initial_state)

        return result.get("final_events")

    def _build_agent_history(self, agent: CountryAgent) -> str:
        """Build agent history summary"""
        if not agent.action_history:
            return "Game start"

        # Take recent 3 actions
        recent = agent.action_history[-3:]
        return "Recent actions: " + ", ".join(recent)

    def retrieve_context(self, state: MultiAgentGenerationState):
        """Retrieve context (enhanced version)"""
        agent = state["agent"]
        world = state["world_state"]

        # 1. RAG retrieve historical events
        query = f"{agent.country_code} {agent.current_year}.{agent.current_month}"
        rag_results = []

        if self.knowledge_base:
            try:
                rag_results = self.knowledge_base.search(query, top_k=5)
            except Exception as e:
                print(f"[RAG Retrieval] Warning: {e}")

        # 2. Build world state context
        world_context = self._build_world_context(agent, world)

        # 3. Other agents' actions
        other_actions_context = self._build_other_actions_context(
            agent,
            state["other_agents_actions"]
        )

        # Combine context
        context_parts = []

        # RAG history
        if rag_results:
            context_parts.append("[Historical Event Reference]")
            for i, result in enumerate(rag_results, 1):
                event = result.event
                context_parts.append(
                    f"{i}. {event.year}.{event.month} - {event.name}\n"
                    f"   {event.description}"
                )

        # World state
        context_parts.append(world_context)

        # Other countries' actions
        if other_actions_context:
            context_parts.append(other_actions_context)

        state["rag_context"] = "\n\n".join(context_parts)

        return state

    def _build_world_context(self, agent: CountryAgent, world: WorldState) -> str:
        """Build world state context"""
        lines = ["[Current World Situation]"]

        # Diplomatic relations
        lines.append("Diplomatic Relations:")
        for country, other_agent in world.agents.items():
            if country == agent.country_code:
                continue

            relation = world.get_relation(agent.country_code, country)
            status = self._relation_status(relation)
            lines.append(f"  With {other_agent.country_name}: {relation:+.2f} ({status})")

        # Military power comparison
        lines.append("\nMilitary Power Comparison:")
        for country, power in world.military_power.items():
            lines.append(f"  {country}: {power}")

        return "\n".join(lines)

    def _build_other_actions_context(
        self,
        agent: CountryAgent,
        other_actions: Dict[str, List[str]]
    ) -> str:
        """Build other agents' actions context"""
        if not other_actions:
            return ""

        lines = ["[Other Countries' Recent Actions]"]
        for country, actions in other_actions.items():
            if country != agent.country_code and actions:
                latest = actions[-1] if actions else "No records"
                lines.append(f"  {country}: {latest}")

        return "\n".join(lines)

    def _relation_status(self, value: float) -> str:
        """Relation status"""
        if value >= 0.7:
            return "Allies"
        elif value >= 0.3:
            return "Friendly"
        elif value >= -0.3:
            return "Neutral"
        elif value >= -0.7:
            return "Hostile"
        else:
            return "At War"

    def generate_draft(self, state: MultiAgentGenerationState):
        """Generate draft (considering agent personality)"""
        agent = state["agent"]

        prompt = ChatPromptTemplate.from_template("""
You are the strategic advisor AI for {country_name}.

**IMPORTANT: Generate all content in English. Do not use Chinese, even if the context contains Chinese text.**

[Agent Personality Traits]
Aggression: {aggression} (0-1, higher = more inclined to military action)
Diplomacy: {diplomacy} (0-1, higher = more inclined to diplomatic means)
Economic Focus: {economic_focus} (0-1, higher = more emphasis on economic development)
Risk Tolerance: {risk_tolerance} (0-1, higher = more willing to take risks)

[Strategic Objectives]
{objectives}

[Historical Background and Current Situation]
{rag_context}

[Task]
Based on the Agent's personality traits and strategic objectives, generate 4 action options that align with the character's positioning.

[Requirements]
1. **Option type distribution should match Agent personality**:
   - If aggression >= 0.7: At least 2 military options
   - If diplomacy >= 0.7: At least 2 diplomatic options
   - If economic_focus >= 0.7: At least 2 economic options
   - Otherwise: One of each type (military, diplomatic, economic, political)

2. **Risk level should match risk_tolerance**:
   - High risk tolerance (>0.6): Can have bold, adventurous options
   - Low risk tolerance (<0.4): Options should be steady and conservative

3. Each option must:
   - Align with historical background and current situation
   - Consider relationships with other countries
   - Have CONCISE name (maximum 60 characters, prefer under 40)
   - Have BRIEF description (maximum 200 characters, prefer under 150)
   - Have reasonable likelihood score (0.0-1.0)

{format_instructions}

Output JSON directly, do not add markdown code block markers or explanatory text.
""")

        try:
            chain = prompt | self.llm | self.parser

            draft = chain.invoke({
                "country_name": agent.country_name,
                "aggression": agent.personality.get("aggression", 0.5),
                "diplomacy": agent.personality.get("diplomacy", 0.5),
                "economic_focus": agent.personality.get("economic_focus", 0.5),
                "risk_tolerance": agent.risk_tolerance,
                "objectives": "\n".join(f"- {obj}" for obj in agent.objectives),
                "rag_context": state.get("rag_context", ""),
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = draft
            state["iterations"] = 1

        except Exception as e:
            print(f"[Generate Draft] Failed: {e}")
            state["draft_events"] = None
            state["iterations"] = 1

        return state
