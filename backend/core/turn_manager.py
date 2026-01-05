"""
Turn Management System
"""

from typing import Dict, Optional
from backend.core.agent import (
    WorldState, CountryAgent, ControlMode,
    TurnPhase, TurnResult
)
from backend.core.models import GameEvent


class TurnManager:
    """Turn manager"""

    def __init__(self, world_state: WorldState):
        self.world = world_state
        self.current_phase = TurnPhase.PLANNING
        self.pending_actions: Dict[str, GameEvent] = {}  # country -> action

    def get_current_turn(self) -> int:
        """Get current turn"""
        return self.world.current_turn

    def get_current_phase(self) -> TurnPhase:
        """Get current phase"""
        return self.current_phase

    def set_phase(self, phase: TurnPhase):
        """Set current phase"""
        self.current_phase = phase
        print(f"[Turn Manager] Entering phase: {phase.value}")

    def record_action(self, country: str, action: GameEvent):
        """Record country action"""
        self.pending_actions[country] = action
        print(f"[Turn Manager] {country} submitted action: {action.name}")

    def has_all_actions(self) -> bool:
        """Check if all actions have been collected"""
        for country, agent in self.world.agents.items():
            # Skip observers
            if agent.control_mode == ControlMode.OBSERVER:
                continue

            # Check if action is recorded
            if country not in self.pending_actions:
                return False

        return True

    def get_pending_action(self, country: str) -> Optional[GameEvent]:
        """Get pending action"""
        return self.pending_actions.get(country)

    def clear_pending_actions(self):
        """Clear pending actions"""
        self.pending_actions.clear()

    def execute_resolution(self) -> TurnResult:
        """Execute resolution phase"""
        print(f"\n{'='*70}")
        print(f"Turn {self.world.current_turn} Resolution")
        print(f"{'='*70}")

        # Collect all actions
        all_actions = {}
        for country, action in self.pending_actions.items():
            all_actions[country] = {
                "id": action.id,
                "name": action.name,
                "type": action.event_type,
                "description": action.description
            }
            print(f"  {country}: {action.name} ({action.event_type})")

        # Detect conflicts
        conflicts = self._detect_conflicts()

        # Calculate diplomatic impact
        diplomatic_changes = self._calculate_diplomatic_impact()

        # Calculate economic impact
        economic_changes = self._calculate_economic_impact()

        # Check if game has ended
        is_game_over, ending_trigger = self._check_game_ending()

        # Create result
        result = TurnResult(
            turn_number=self.world.current_turn,
            all_actions=all_actions,
            conflicts=conflicts,
            diplomatic_changes=diplomatic_changes,
            economic_changes=economic_changes,
            major_events=[],
            is_game_over=is_game_over,
            ending_trigger=ending_trigger
        )

        if is_game_over:
            print(f"\n[Game Over] {ending_trigger}")

        print(f"{'='*70}\n")

        return result

    def _check_game_ending(self) -> tuple[bool, Optional[str]]:
        """Check if game has ended"""

        # 1. Time limit: Reached May 1945 (end of WWII European theater)
        if self.world.current_year >= 1945 and self.world.current_month >= 5:
            return True, "Reached May 1945, European theater war ended"

        # 2. Turn limit: Exceeded 100 turns
        if self.world.current_turn >= 100:
            return True, "Game reached maximum turn limit"

        # 3. Military victory: A country's military resources reached 0
        for country, agent in self.world.agents.items():
            if agent.resources.get("military", 100) <= 0:
                return True, f"{agent.country_name} military forces completely collapsed"

        # 4. Economic collapse: A country's economic resources reached 0
        for country, agent in self.world.agents.items():
            if agent.resources.get("economic", 100) <= 0:
                return True, f"{agent.country_name} economy completely collapsed"

        # 5. Military hegemony: A country's military resources exceeded 250
        for country, agent in self.world.agents.items():
            if agent.resources.get("military", 100) >= 250:
                return True, f"{agent.country_name} established overwhelming military superiority"

        # 6. Total war: All countries taking military actions with low resources
        military_count = sum(
            1 for action in self.pending_actions.values()
            if action.event_type == "military"
        )
        if military_count == len(self.pending_actions):
            # Check if all countries have very low resources
            low_resource_count = sum(
                1 for agent in self.world.agents.values()
                if agent.resources.get("military", 100) < 50
                and agent.resources.get("economic", 100) < 50
            )
            if low_resource_count >= 2:
                return True, "All nations trapped in total war, resources depleted"

        # 7. Diplomatic isolation: A country has relations below -0.8 with all others
        for country1 in self.world.agents.keys():
            isolated = True
            for country2 in self.world.agents.keys():
                if country1 != country2:
                    relation = self.world.get_relation(country1, country2)
                    if relation >= -0.8:
                        isolated = False
                        break
            if isolated:
                agent = self.world.get_agent(country1)
                return True, f"{agent.country_name} fell into complete diplomatic isolation"

        return False, None

    def _detect_conflicts(self) -> list:
        """Detect military conflicts"""
        conflicts = []

        # Simplified version: Check if multiple countries selected military actions
        military_actions = []
        for country, action in self.pending_actions.items():
            if action.event_type == "military":
                military_actions.append((country, action))

        if len(military_actions) >= 2:
            # Multiple countries taking military actions, possible conflict
            for country, action in military_actions:
                conflicts.append({
                    "country": country,
                    "action": action.name,
                    "description": f"{country} taking military action: {action.name}"
                })

        return conflicts

    def _calculate_diplomatic_impact(self) -> list:
        """Calculate diplomatic impact"""
        changes = []

        # Simplified version: Military actions decrease relations, diplomatic actions improve them
        for country1, action1 in self.pending_actions.items():
            for country2 in self.world.agents.keys():
                if country1 == country2:
                    continue

                old_value = self.world.get_relation(country1, country2)

                # Adjust relations based on action type
                delta = 0.0
                if action1.event_type == "military":
                    delta = -0.1  # Military actions decrease relations
                elif action1.event_type == "diplomatic":
                    delta = 0.05  # Diplomatic actions improve relations

                if delta != 0:
                    self.world.update_relations(country1, country2, delta)
                    new_value = self.world.get_relation(country1, country2)

                    changes.append({
                        "country1": country1,
                        "country2": country2,
                        "old_value": round(old_value, 2),
                        "new_value": round(new_value, 2),
                        "delta": round(delta, 2),
                        "reason": f"{country1}'s {action1.event_type} action"
                    })

        return changes

    def _calculate_economic_impact(self) -> list:
        """Calculate economic impact"""
        changes = []

        for country, action in self.pending_actions.items():
            agent = self.world.get_agent(country)
            if not agent:
                continue

            # Consume/add resources based on action type
            if action.event_type == "military":
                # Military actions consume resources
                old_military = agent.resources.get("military", 100)
                agent.resources["military"] = max(0, old_military - 10)

                changes.append({
                    "country": country,
                    "resource": "military",
                    "old_value": old_military,
                    "new_value": agent.resources["military"],
                    "delta": -10,
                    "reason": f"Military action: {action.name}"
                })

            elif action.event_type == "economic":
                # Economic actions add resources
                old_economic = agent.resources.get("economic", 100)
                agent.resources["economic"] = min(200, old_economic + 5)

                changes.append({
                    "country": country,
                    "resource": "economic",
                    "old_value": old_economic,
                    "new_value": agent.resources["economic"],
                    "delta": 5,
                    "reason": f"Economic action: {action.name}"
                })

        return changes

    def advance_time(self):
        """Advance time"""
        self.world.current_month += 1

        if self.world.current_month > 12:
            self.world.current_month = 1
            self.world.current_year += 1

        self.world.current_turn += 1

        # Update all agents' time
        for agent in self.world.agents.values():
            agent.current_year = self.world.current_year
            agent.current_month = self.world.current_month

        print(f"[Turn Manager] Time advanced to {self.world.current_year}/{self.world.current_month}")

    def get_world_state(self) -> WorldState:
        """Get world state"""
        return self.world
