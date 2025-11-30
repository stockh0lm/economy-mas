from __future__ import annotations

from typing import ClassVar


class LineageMixin:
    """Provide shared lineage ID handling for splitting agents."""

    _lineage_counters: ClassVar[dict[str, int]]

    def _init_lineage(self, unique_id: str) -> None:
        base_id, existing_suffix = self._parse_unique_id(unique_id)
        self._lineage_root_id = base_id
        self._ensure_lineage_counter(base_id, existing_suffix)

    @staticmethod
    def _parse_unique_id(unique_id: str) -> tuple[str, int]:
        if "_g" in unique_id:
            base_id, _, suffix_str = unique_id.partition("_g")
            try:
                return base_id, int(suffix_str)
            except ValueError:
                pass
        if "_child" in unique_id:
            base_id = unique_id.split("_child")[0]
            suffix = unique_id.count("_child")
            return base_id, suffix
        return unique_id, 0

    def _ensure_lineage_counter(self, base_id: str, suffix: int) -> None:
        counters = type(self)._lineage_counters
        current = counters.get(base_id)
        if current is None or suffix > current:
            counters[base_id] = suffix

    def _reserve_lineage_suffix(self) -> int:
        counters = type(self)._lineage_counters
        base_id = self._lineage_root_id
        next_suffix = counters.get(base_id, 0) + 1
        counters[base_id] = next_suffix
        return next_suffix

    def generate_next_id(self) -> str:
        """Generate the next unique ID for a child/spinoff agent."""
        next_suffix = self._reserve_lineage_suffix()
        return f"{self._lineage_root_id}_g{next_suffix}"

