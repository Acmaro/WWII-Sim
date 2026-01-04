"""
AI Decision System
"""

import json
from typing import List
from langchain.prompts import ChatPromptTemplate

from backend.core.agent import CountryAgent, WorldState
from backend.core.models import GameEvent


class AIDecisionMaker:
    """AI decision system"""

    def __init__(self, llm):
        self.llm = llm

    def select_best_action(
        self,
        agent: CountryAgent,
        options: List[GameEvent],
        world_state: WorldState
    ) -> GameEvent:
        """Select best action"""

        print(f"\n[AI Decision] {agent.country_name} is analyzing {len(options)} options...")

        # Build decision prompt
        prompt = ChatPromptTemplate.from_template("""
You are the supreme decision-making AI for {country_name}.

【Current Situation】
Time: {year}/{month}
Military Power: {military_power}
Economic Strength: {economic_strength}
Diplomatic Points: {diplomatic_points}

【Diplomatic Relations】
{diplomatic_relations}

【Strategic Objectives】
{objectives}

【Personality Traits】
Aggression: {aggression} (0-1, higher = more inclined to military action)
Diplomacy: {diplomacy} (0-1, higher = more inclined to diplomatic means)
Economic Focus: {economic_focus} (0-1, higher = more emphasis on economic development)
Risk Tolerance: {risk_tolerance} (0-1, higher = more willing to take risks)

【Available Actions】
{options}

【Evaluation Criteria】
1. Objective Alignment: Does the action help achieve strategic objectives
2. Risk Assessment: Are the potential risks within acceptable range
3. Timing Judgment: Is now the optimal time to execute this action
4. International Impact: Impact on diplomatic relations
5. Resource Cost: Are sufficient resources available for this action
6. Personality Match: Does the action align with the Agent's personality traits

Selection based on personality traits:
- If aggression is high: Prioritize military type
- If diplomacy is high: Prioritize diplomatic type
- If economic_focus is high: Prioritize economic type

Please analyze each option and select the optimal action.

Output format (pure JSON, no markdown markers):
{{
  "selected_action_id": "action_id",
  "reasoning": "reason for selection (within 50 words)",
  "expected_outcome": "expected result",
  "risk_level": 0.5
}}
""")

        # Format options
        options_text = self._format_options(options)

        # Format diplomatic relations
        relations_text = self._format_relations(agent, world_state)

        # Invoke LLM
        try:
            response = self.llm.invoke(
                prompt.format(
                    country_name=agent.country_name,
                    year=agent.current_year,
                    month=agent.current_month,
                    military_power=agent.resources.get("military", 100),
                    economic_strength=agent.resources.get("economic", 100),
                    diplomatic_points=agent.resources.get("diplomatic", 100),
                    diplomatic_relations=relations_text,
                    objectives="\n".join(f"- {obj}" for obj in agent.objectives),
                    aggression=agent.personality.get("aggression", 0.5),
                    diplomacy=agent.personality.get("diplomacy", 0.5),
                    economic_focus=agent.personality.get("economic_focus", 0.5),
                    risk_tolerance=agent.risk_tolerance,
                    options=options_text
                )
            )

            # Parse response
            content = response.content.strip()

            # Remove possible markdown code block markers
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            decision = json.loads(content)
            selected_id = decision["selected_action_id"]

            # Log decision reasoning
            print(f"[AI Decision] {agent.country_name} selected: {selected_id}")
            print(f"  Reasoning: {decision['reasoning']}")
            print(f"  Risk: {decision.get('risk_level', 0.5):.1%}\n")

            # Find selected action
            selected_action = next(
                (opt for opt in options if opt.id == selected_id),
                None
            )

            if selected_action is None:
                print(f"[AI Decision] Warning: Action ID={selected_id} not found, using first option")
                selected_action = options[0]

            return selected_action

        except Exception as e:
            print(f"[AI Decision] Error: {e}")
            print(f"[AI Decision] Falling back to first option")
            return options[0]

    def _format_options(self, options: List[GameEvent]) -> str:
        """Format options list"""
        lines = []
        for i, opt in enumerate(options, 1):
            lines.append(
                f"{i}. [{opt.event_type}] {opt.name} (ID: {opt.id})\n"
                f"   Description: {opt.description}\n"
                f"   Historical Likelihood: {opt.likelihood:.1%}"
            )
        return "\n\n".join(lines)

    def _format_relations(self, agent: CountryAgent, world: WorldState) -> str:
        """Format diplomatic relations"""
        lines = []
        for country, other_agent in world.agents.items():
            if country == agent.country_code:
                continue

            relation = world.get_relation(agent.country_code, country)
            status = self._relation_status(relation)

            lines.append(
                f"With {other_agent.country_name}: {relation:+.2f} ({status})"
            )

        return "\n".join(lines) if lines else "No diplomatic relations recorded"

    def _relation_status(self, value: float) -> str:
        """Relation status description"""
        if value >= 0.7:
            return "Allied"
        elif value >= 0.3:
            return "Friendly"
        elif value >= -0.3:
            return "Neutral"
        elif value >= -0.7:
            return "Hostile"
        else:
            return "At War"
