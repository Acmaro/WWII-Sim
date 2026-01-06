"""
AI-Driven Ending Generation Service
"""

from typing import Dict, List
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from backend.core.agent import WorldState, CountryAgent, GameEnding


class EndingGenerator:
    """Ending generator"""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def generate_ending(
        self,
        world_state: WorldState,
        trigger_reason: str,
        player_country: str
    ) -> GameEnding:
        """
        Generate game ending based on current world state

        Args:
            world_state: Current world state
            trigger_reason: Reason for ending trigger
            player_country: Player-controlled country

        Returns:
            GameEnding: Generated ending data
        """

        # Collect game state information
        game_summary = self._build_game_summary(world_state, player_country)

        # Use LLM to generate ending narrative
        narrative = self._generate_narrative(
            game_summary,
            trigger_reason,
            world_state,
            player_country
        )

        # Generate country epilogues
        epilogue = self._generate_epilogue(world_state, player_country)

        # Determine ending type and winner
        ending_type, winner = self._determine_ending_type(
            world_state,
            trigger_reason,
            player_country
        )

        # Collect key events
        key_events = self._collect_key_events(world_state)

        # Build final statistics
        final_stats = self._build_final_stats(world_state)

        return GameEnding(
            ending_type=ending_type,
            winner=winner,
            trigger_reason=trigger_reason,
            narrative=narrative,
            epilogue=epilogue,
            final_stats=final_stats,
            key_events=key_events
        )

    def _build_game_summary(self, world_state: WorldState, player_country: str) -> str:
        """Build game summary"""
        summary_lines = [
            f"Game Time: {world_state.current_year}/{world_state.current_month}",
            f"Total Turns: {world_state.current_turn}",
            f"Player Country: {player_country}",
            "",
            "Country States:"
        ]

        for country, agent in world_state.agents.items():
            resources = agent.resources
            summary_lines.append(
                f"  {agent.country_name} ({country}):"
            )
            summary_lines.append(
                f"    Military: {resources.get('military', 100)}, "
                f"Economic: {resources.get('economic', 100)}, "
                f"Diplomatic: {resources.get('diplomatic', 100)}"
            )

            # Add action history (only last 2 to save context)
            if agent.action_history:
                recent_actions = agent.action_history[-2:]  # Last 2 actions only
                summary_lines.append(
                    f"    Recent Actions: {', '.join(recent_actions)}"
                )

        summary_lines.append("")
        summary_lines.append("Diplomatic Relations:")
        for country1 in world_state.diplomatic_relations:
            for country2, value in world_state.diplomatic_relations[country1].items():
                if country1 < country2:  # Avoid duplicates
                    agent1 = world_state.get_agent(country1)
                    agent2 = world_state.get_agent(country2)
                    summary_lines.append(
                        f"  {agent1.country_name} ↔ {agent2.country_name}: {value:.2f}"
                    )

        return "\n".join(summary_lines)

    def _generate_narrative(
        self,
        game_summary: str,
        trigger_reason: str,
        world_state: WorldState,
        player_country: str
    ) -> str:
        """Use LLM to generate ending narrative"""

        player_agent = world_state.get_agent(player_country)

        # Analyze player's strategic characteristics
        strategy_analysis = self._analyze_player_strategy(player_agent, world_state, player_country)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a historical novelist skilled at adapting WWII history into captivating stories.

Based on the provided game information, create an excellent historical narrative (400-600 words, CONCISE):

**Narrative Structure:**
1. **Opening** (10%): Briefly review key events that have occurred
2. **Body** (70%): Focus on depicting the fictional historical process from the current point to the war's end
   - Portray the fate of each nation going forward
   - Imagine key battles, conferences, and turning points
   - Show the evolution of the international landscape
3. **Conclusion** (20%): The post-war world order and the long-term fate of nations

**Writing Requirements:**
- Use epic narrative style, as if recounting real history
- Use country names, not pronouns like "the player" or "they"
- Do not use game terminology like "Turn X" or "selected"
- Don't simply list what happened, tell a complete story
- Depict specific scenes, figures, and events
- Focus on **simulating the future**, not recounting the past

**Forbidden:**
- "The player chose..."
- "In the first turn..."
- "They decided..."
- Direct data quotes ("Military 100")
- Chronicle-style narration

**Example Style:**
"In the autumn of 1939, the skies over Europe were shrouded in the clouds of war. After occupying Poland, the German Empire swiftly turned its gaze toward Western Europe... In the following years..." (NOT "Germany chose to attack Poland in turn 1...")"""),
            ("human", """Game Background Information:
{game_summary}

{player_name}'s Strategic Characteristics:
{strategy_analysis}

Ending Trigger: {trigger_reason}

Please create a complete historical story, focusing on the historical process from 1939 to the war's end, and the post-war world order.""")
        ])

        chain = prompt | self.llm

        response = chain.invoke({
            "game_summary": game_summary,
            "strategy_analysis": strategy_analysis,
            "trigger_reason": trigger_reason,
            "player_name": player_agent.country_name
        })

        return response.content.strip()

    def _analyze_player_strategy(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str
    ) -> str:
        """Analyze player's strategic characteristics"""

        analysis_lines = []

        # 1. Action history analysis (LIMITED to last 5 actions to save context)
        if agent.action_history:
            # Only analyze recent actions to reduce context length
            actions = agent.action_history[-5:]  # Last 5 actions only
            analysis_lines.append(f"Actions Analyzed: {len(actions)} (recent)")

            # Count action types
            military_count = sum(1 for a in actions if any(k in a for k in ['军事', '进攻', '防御', '战争', 'Military', 'Attack', 'Defense', 'War']))
            diplomatic_count = sum(1 for a in actions if any(k in a for k in ['外交', '协议', '谈判', '联盟', 'Diplomatic', 'Agreement', 'Negotiation', 'Alliance']))
            economic_count = sum(1 for a in actions if any(k in a for k in ['经济', '生产', '工业', '资源', 'Economic', 'Production', 'Industry', 'Resource']))

            # Only include non-zero counts
            if military_count > 0:
                analysis_lines.append(f"Military focus: {military_count}/{len(actions)}")
            if diplomatic_count > 0:
                analysis_lines.append(f"Diplomatic focus: {diplomatic_count}/{len(actions)}")
            if economic_count > 0:
                analysis_lines.append(f"Economic focus: {economic_count}/{len(actions)}")

            # Determine dominant strategy
            if military_count > diplomatic_count and military_count > economic_count:
                analysis_lines.append("Strategy: Military Expansion")
            elif diplomatic_count > military_count and diplomatic_count > economic_count:
                analysis_lines.append("Strategy: Diplomacy First")
            elif economic_count > military_count and economic_count > diplomatic_count:
                analysis_lines.append("Strategy: Economic Development")
            else:
                analysis_lines.append("Strategy: Balanced")

            # Recent actions (only last 2)
            recent = actions[-2:] if len(actions) >= 2 else actions
            analysis_lines.append(f"Recent: {', '.join(recent)}")

        # 2. Diplomatic status
        allies = []
        enemies = []
        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                other_name = world_state.get_agent(other_country).country_name
                if relation > 0.3:
                    allies.append(other_name)
                elif relation < -0.5:
                    enemies.append(other_name)

        if allies:
            analysis_lines.append(f"Allied Relations: Established friendly relations with {', '.join(allies)}")
        if enemies:
            analysis_lines.append(f"Hostile Relations: Tensions with {', '.join(enemies)}")

        # 3. Resource status (auxiliary)
        resources = agent.resources
        analysis_lines.append(
            f"Final State: Military {resources.get('military', 100)}, "
            f"Economic {resources.get('economic', 100)}, "
            f"Diplomatic {resources.get('diplomatic', 100)}"
        )

        return "\n".join(analysis_lines)

    def _generate_epilogue(
        self,
        world_state: WorldState,
        player_country: str
    ) -> Dict[str, str]:
        """Generate country epilogues (using LLM to generate personalized content)"""

        epilogue = {}

        for country, agent in world_state.agents.items():
            # Generate personalized epilogue for each country
            epilogue_text = self._generate_country_epilogue(
                agent, world_state, country, country == player_country
            )
            epilogue[country] = epilogue_text

        return epilogue

    def _generate_country_epilogue(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str,
        is_player: bool
    ) -> str:
        """Generate epilogue for a single country"""

        # Analyze country characteristics
        resources = agent.resources
        military = resources.get('military', 100)
        economic = resources.get('economic', 100)

        # Analyze action history
        action_summary = ""
        if agent.action_history:
            military_count = sum(1 for a in agent.action_history if any(k in a for k in ['军事', '进攻', '防御', '战争', 'Military', 'Attack', 'Defense', 'War']))
            diplomatic_count = sum(1 for a in agent.action_history if any(k in a for k in ['外交', '协议', '谈判', '联盟', 'Diplomatic', 'Agreement', 'Negotiation', 'Alliance']))
            economic_count = sum(1 for a in agent.action_history if any(k in a for k in ['经济', '生产', '工业', '资源', 'Economic', 'Production', 'Industry', 'Resource']))

            if military_count > diplomatic_count and military_count > economic_count:
                action_summary = "Pursued military expansion strategy"
            elif diplomatic_count > 0:
                action_summary = "Focused on diplomatic maneuvering"
            elif economic_count > 0:
                action_summary = "Concentrated on economic development"

        # Diplomatic relations
        allies = []
        enemies = []
        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                other_name = world_state.get_agent(other_country).country_name
                if relation > 0.3:
                    allies.append(other_name)
                elif relation < -0.5:
                    enemies.append(other_name)

        # Use LLM to generate personalized description
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a historian specializing in writing about the fate of nations after WWII.

Please describe this country's post-war development and fate in 1-2 sentences (50-80 words).

Requirements:
- Based on the country's performance during the war and final state
- Descriptions should be specific and vivid, avoid templates
- Don't use pronouns like "this country", use the country name directly
- Don't quote specific numbers
- Depict long-term impact (from a decades-long perspective)"""),
            ("human", """Country: {country_name}

Performance During War: {action_summary}
Final Military Status: {military_status}
Final Economic Status: {economic_status}
Allied Relations: {allies}
Hostile Relations: {enemies}
Is Player Country: {is_player}

Please describe this country's post-war fate and development.""")
        ])

        # Determine status
        military_status = "Strong" if military >= 120 else ("Moderate" if military >= 60 else "Weak")
        economic_status = "Prosperous" if economic >= 120 else ("Stable" if economic >= 60 else "Struggling")

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "country_name": agent.country_name,
                "action_summary": action_summary or "Pursued balanced development strategy",
                "military_status": military_status,
                "economic_status": economic_status,
                "allies": ", ".join(allies) if allies else "No clear allies",
                "enemies": ", ".join(enemies) if enemies else "No clear enemies",
                "is_player": "Yes" if is_player else "No"
            })

            return response.content.strip()
        except Exception as e:
            # If LLM call fails, use simple fallback
            if military <= 20 or economic <= 20:
                return f"{agent.country_name} fell into a long post-war reconstruction, requiring decades to recover."
            elif military >= 150 and economic >= 150:
                return f"{agent.country_name} became a post-war superpower, dominating the new world order."
            else:
                return f"{agent.country_name} embarked on a path of revival, gradually restoring its national strength."

    def _determine_ending_type(
        self,
        world_state: WorldState,
        trigger_reason: str,
        player_country: str
    ) -> tuple[str, str]:
        """
        Determine ending type and winner

        Considers:
        1. Resource status (but not the only criterion)
        2. Diplomatic relationship network
        3. Action history (strategic choices)
        4. Turn result trends
        """

        player_agent = world_state.get_agent(player_country)

        # Check if any country has completely collapsed (clear defeat)
        for country, agent in world_state.agents.items():
            if agent.resources.get('military', 100) <= 0 or agent.resources.get('economic', 100) <= 0:
                if country == player_country:
                    return "defeat", None
                # Even if enemy country collapses, not necessarily a victory - depends on overall situation

        # Evaluate player's strategic score
        player_score = self._calculate_strategic_score(player_agent, world_state, player_country)

        # Evaluate average score of other countries
        other_scores = []
        for country, agent in world_state.agents.items():
            if country != player_country:
                score = self._calculate_strategic_score(agent, world_state, country)
                other_scores.append(score)

        avg_other_score = sum(other_scores) / len(other_scores) if other_scores else 0

        print(f"[Ending Determination] Player strategic score: {player_score:.1f}")
        print(f"[Ending Determination] Other countries average score: {avg_other_score:.1f}")

        # Determine ending based on strategic score
        score_diff = player_score - avg_other_score

        if score_diff > 15:
            return "victory", player_country
        elif score_diff < -15:
            return "defeat", None
        else:
            return "historical", None

    def _calculate_strategic_score(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str
    ) -> float:
        """
        Calculate strategic score (0-100)

        Considers multiple dimensions:
        - Resource balance (30 points)
        - Diplomatic relations (25 points)
        - Strategic consistency (25 points)
        - Action diversity (20 points)
        """
        score = 0.0

        # 1. Resource balance (30 points) - not just total, but balance
        resources = agent.resources
        military = resources.get('military', 100)
        economic = resources.get('economic', 100)
        diplomatic = resources.get('diplomatic', 100)

        # Total resources (15 points)
        total_resources = military + economic + diplomatic
        score += min(15, total_resources / 20)

        # Resource balance (15 points) - none should be too low
        min_resource = min(military, economic, diplomatic)
        if min_resource >= 80:
            score += 15
        elif min_resource >= 60:
            score += 10
        elif min_resource >= 40:
            score += 5

        # 2. Diplomatic relations (25 points)
        diplomatic_score = 0
        relation_count = 0

        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                relation_count += 1

                # Positive relations add points, negative subtract
                if relation > 0.5:
                    diplomatic_score += 15  # Strong ally
                elif relation > 0:
                    diplomatic_score += 8   # Friendly
                elif relation > -0.5:
                    diplomatic_score += 0   # Neutral
                else:
                    diplomatic_score -= 5   # Hostile

        if relation_count > 0:
            score += min(25, max(0, diplomatic_score / relation_count * 25))

        # 3. Strategic consistency (25 points) - analyze action history
        if agent.action_history:
            actions = agent.action_history

            # Count action type distribution
            action_types = {}
            for action in actions:
                # Simple action type judgment (based on keywords)
                if any(keyword in action for keyword in ['军事', '进攻', '防御', '部队', '战争', 'Military', 'Attack', 'Defense', 'Troops', 'War']):
                    action_types['military'] = action_types.get('military', 0) + 1
                elif any(keyword in action for keyword in ['外交', '协议', '谈判', '联盟', '关系', 'Diplomatic', 'Agreement', 'Negotiation', 'Alliance', 'Relations']):
                    action_types['diplomatic'] = action_types.get('diplomatic', 0) + 1
                elif any(keyword in action for keyword in ['经济', '生产', '工业', '资源', '贸易', 'Economic', 'Production', 'Industry', 'Resource', 'Trade']):
                    action_types['economic'] = action_types.get('economic', 0) + 1

            total_actions = len(actions)
            if total_actions > 0:
                # Clear strategic direction (one type dominant but not all) adds points
                if action_types:
                    max_type_count = max(action_types.values())
                    max_ratio = max_type_count / total_actions

                    if 0.4 <= max_ratio <= 0.7:  # Dominant strategy but also flexible
                        score += 20
                    elif 0.3 <= max_ratio < 0.4 or 0.7 < max_ratio <= 0.8:
                        score += 12
                    else:
                        score += 5  # Too scattered or too uniform
                else:
                    score += 5

                # Action quantity bonus (more active)
                score += min(5, total_actions / 2)

        # 4. Action diversity (20 points) - not repeating single strategy
        if agent.action_history:
            unique_actions = len(set(agent.action_history))
            diversity_ratio = unique_actions / len(agent.action_history)
            score += diversity_ratio * 20

        return min(100, score)

    def _collect_key_events(self, world_state: WorldState) -> List[str]:
        """Collect key historical events"""
        key_events = []

        # Extract from all Agent action histories (mixed chronological order)
        # Collect all actions from each country
        all_actions = []
        for country, agent in world_state.agents.items():
            if agent.action_history:
                for i, action in enumerate(agent.action_history):
                    all_actions.append({
                        'country': agent.country_name,
                        'action': action,
                        'turn': i + 1  # Estimated turn number
                    })

        # Sort by turn (chronological order)
        all_actions.sort(key=lambda x: x['turn'])

        # Select most important events (prioritize military and diplomatic)
        important_actions = []
        for action_info in all_actions:
            action = action_info['action']
            # Military and diplomatic actions priority
            if any(keyword in action for keyword in ['军事', '进攻', '防御', '战争', '外交', '协议', '联盟', 'Military', 'Attack', 'Defense', 'War', 'Diplomatic', 'Agreement', 'Alliance']):
                important_actions.append(action_info)
            elif len(important_actions) < 10:  # Ensure at least some events
                important_actions.append(action_info)

        # Limit quantity, select at most 8 key events
        important_actions = important_actions[:8]

        # Format as strings
        for action_info in important_actions:
            key_events.append(f"{action_info['country']}: {action_info['action']}")

        return key_events

    def _build_final_stats(self, world_state: WorldState) -> Dict[str, any]:
        """Build final statistics"""
        stats = {
            "total_turns": world_state.current_turn,
            "end_date": f"{world_state.current_year}/{world_state.current_month}",
            "countries": {}
        }

        for country, agent in world_state.agents.items():
            stats["countries"][country] = {
                "name": agent.country_name,
                "resources": {
                    "military": agent.resources.get('military', 100),
                    "economic": agent.resources.get('economic', 100),
                    "diplomatic": agent.resources.get('diplomatic', 100)
                },
                "total_actions": len(agent.action_history)
            }

        return stats
