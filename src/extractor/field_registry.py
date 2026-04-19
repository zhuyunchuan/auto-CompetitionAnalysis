"""
Field Registry for the competitor product scraping system.

This module provides a centralized registry of all field codes defined in
field_dictionary_v1.md, including their metadata such as field name,
required status, value type, canonical unit, and comparison rule.

This is a frozen contract for Phase 1 parallel development.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Set


@dataclass(frozen=True)
class FieldDefinition:
    """Definition of a single field in the specification dictionary."""
    field_code: str
    field_name: str
    required: bool
    value_type: str  # text, number_or_text, integer, list_text
    canonical_unit: Optional[str]  # None for text/list fields
    comparison_rule: str
    aliases: List[str]

    def get_all_search_terms(self) -> Set[str]:
        """Get all search terms including field code and aliases."""
        return {self.field_code, self.field_name, *self.aliases}


class FieldRegistry:
    """
    Centralized registry of field definitions from field_dictionary_v1.md.

    This provides metadata for all 19 Phase 1 fields, including:
    - Field codes and names
    - Required status
    - Value types
    - Canonical units
    - Comparison rules
    - Multi-language aliases (English/Chinese)
    """

    # Field definitions from field_dictionary_v1.md
    _FIELDS: Dict[str, FieldDefinition] = {
        "image_sensor": FieldDefinition(
            field_code="image_sensor",
            field_name="Image Sensor",
            required=True,
            value_type="text",
            canonical_unit=None,
            comparison_rule="exact_or_alias",
            aliases=["Image Sensor", "图像传感器"]
        ),
        "max_resolution": FieldDefinition(
            field_code="max_resolution",
            field_name="Max. Resolution",
            required=True,
            value_type="text",
            canonical_unit="px",
            comparison_rule="normalized_resolution",
            aliases=["Max. Resolution", "最大分辨率"]
        ),
        "lens_type": FieldDefinition(
            field_code="lens_type",
            field_name="Lens Type",
            required=True,
            value_type="text",
            canonical_unit=None,
            comparison_rule="exact_or_alias",
            aliases=["Lens Type", "镜头类型"]
        ),
        "aperture": FieldDefinition(
            field_code="aperture",
            field_name="Aperture",
            required=True,
            value_type="text",
            canonical_unit="f",
            comparison_rule="normalized_aperture",
            aliases=["Aperture", "光圈"]
        ),
        "supplement_light_type": FieldDefinition(
            field_code="supplement_light_type",
            field_name="Supplement Light Type",
            required=True,
            value_type="text",
            canonical_unit=None,
            comparison_rule="exact_or_alias",
            aliases=["Supplement Light Type", "补光灯类型", "IR Type", "IR LED", "Supplement Light", "Infrared", "Illuminator Number", "Illuminator Type"]
        ),
        "supplement_light_range": FieldDefinition(
            field_code="supplement_light_range",
            field_name="Supplement Light Range",
            required=True,
            value_type="number_or_text",
            canonical_unit="m",
            comparison_rule="normalized_distance",
            aliases=["Supplement Light Range", "补光距离", "IR Range", "IR Distance", "Illumination Distance"]
        ),
        "main_stream_max_fps_resolution": FieldDefinition(
            field_code="main_stream_max_fps_resolution",
            field_name="Main Stream Max FPS@Resolution",
            required=True,
            value_type="text",
            canonical_unit="fps+px",
            comparison_rule="normalized_fps_resolution",
            aliases=["Main Stream", "主码流", "Main Stream Max FPS@Resolution", "Video Frame Rate", "Frame Rate"]
        ),
        "stream_count": FieldDefinition(
            field_code="stream_count",
            field_name="Stream Count",
            required=True,
            value_type="integer",
            canonical_unit="count",
            comparison_rule="numeric_compare",
            aliases=["Stream Count", "码流数量", "Third Stream", "Stream Capability"]
        ),
        "interface_items": FieldDefinition(
            field_code="interface_items",
            field_name="Interface",
            required=True,
            value_type="list_text",
            canonical_unit=None,
            comparison_rule="set_compare",
            aliases=["Interface", "接口", "Network Port", "Audio Input", "Alarm Input", "Audio Output", "Alarm Output"]
        ),
        "deep_learning_function_categories": FieldDefinition(
            field_code="deep_learning_function_categories",
            field_name="Deep Learning Function Categories",
            required=True,
            value_type="list_text",
            canonical_unit=None,
            comparison_rule="set_compare",
            aliases=["Deep Learning Function", "深度学习功能", "Smart Event", "Intelligence", "Smart Features", "Analytics", "IVS Functions", "AI Functions", "IVS", "SMD", "AcuPick"]
        ),
        "approval_protection": FieldDefinition(
            field_code="approval_protection",
            field_name="Approval.Protection",
            required=True,
            value_type="text",
            canonical_unit="grade",
            comparison_rule="exact_or_alias",
            aliases=["Protection", "防护", "IP67", "IK10", "Protection"]
        ),
        "approval_anti_corrosion_protection": FieldDefinition(
            field_code="approval_anti_corrosion_protection",
            field_name="Approval.Anti-Corrosion Protection",
            required=True,
            value_type="text",
            canonical_unit="grade",
            comparison_rule="exact_or_alias",
            aliases=["Anti-Corrosion Protection", "防腐等级"]
        ),
    }

    @classmethod
    def get_field(cls, field_code: str) -> Optional[FieldDefinition]:
        """
        Get field definition by field code.

        Args:
            field_code: The field code to look up

        Returns:
            FieldDefinition if found, None otherwise
        """
        return cls._FIELDS.get(field_code)

    @classmethod
    def get_all_field_codes(cls) -> Set[str]:
        """Get all field codes defined in Phase 1."""
        return set(cls._FIELDS.keys())

    @classmethod
    def get_required_field_codes(cls) -> Set[str]:
        """Get all required field codes."""
        return {
            code for code, definition in cls._FIELDS.items()
            if definition.required
        }

    @classmethod
    def get_fields_by_type(cls, value_type: str) -> List[FieldDefinition]:
        """
        Get all fields of a specific value type.

        Args:
            value_type: The value type to filter by (e.g., "text", "list_text")

        Returns:
            List of FieldDefinition objects matching the type
        """
        return [
            definition for definition in cls._FIELDS.values()
            if definition.value_type == value_type
        ]

    @classmethod
    def find_field_by_alias(cls, alias: str) -> Optional[FieldDefinition]:
        """
        Find a field definition by searching through all aliases.

        Args:
            alias: The alias to search for (case-insensitive)

        Returns:
            FieldDefinition if a match is found, None otherwise
        """
        alias_lower = alias.lower().strip()
        for definition in cls._FIELDS.values():
            if alias_lower in [term.lower() for term in definition.get_all_search_terms()]:
                return definition
        return None

    @classmethod
    def get_canonical_unit(cls, field_code: str) -> Optional[str]:
        """
        Get the canonical unit for a field code.

        Args:
            field_code: The field code to look up

        Returns:
            Canonical unit string if field has a unit, None otherwise
        """
        definition = cls.get_field(field_code)
        return definition.canonical_unit if definition else None

    @classmethod
    def is_required(cls, field_code: str) -> bool:
        """
        Check if a field is required.

        Args:
            field_code: The field code to check

        Returns:
            True if field is required, False otherwise
        """
        definition = cls.get_field(field_code)
        return definition.required if definition else False

    @classmethod
    def is_list_field(cls, field_code: str) -> bool:
        """
        Check if a field stores list values.

        Args:
            field_code: The field code to check

        Returns:
            True if field is a list field, False otherwise
        """
        definition = cls.get_field(field_code)
        return definition.value_type == "list_text" if definition else False
