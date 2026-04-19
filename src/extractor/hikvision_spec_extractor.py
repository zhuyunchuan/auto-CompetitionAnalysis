"""
Hikvision-specific specification extractor (v2).

This module implements extraction logic optimized for Hikvision's actual
page structure using a label-value pattern matching approach.

Extraction strategy:
1. Find all li elements with "label\nvalue" structure
2. Match labels to known field names (case-insensitive)
3. Normalize values according to field type
4. Infer missing fields when possible (e.g., stream count from Third Stream)
"""

import re
import json
from typing import List, Optional, Dict, Set
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, NavigableString

from src.core.types import SpecRecord
from src.extractor.field_registry import FieldRegistry


class HikvisionSpecExtractor:
    """
    Hikvision-specific extractor for product specification pages.

    Uses pattern matching to find field-value pairs in li elements.
    """

    # Field label mappings (actual labels seen on Hikvision pages)
    FIELD_LABELS: Dict[str, List[str]] = {
        "image_sensor": ["Image Sensor"],
        "max_resolution": ["Max. Resolution", "Max Resolution"],
        "lens_type": ["Lens Type"],
        "aperture": ["Aperture"],
        "supplement_light_range": ["IR Range", "Supplement Light Range", "IR Distance"],
        "main_stream_max_fps_resolution": ["Main Stream"],
        "sub_stream": ["Sub Stream", "Sub-stream"],
        "third_stream": ["Third Stream"],
        "interface_items": ["Communication Interface", "Network Interface"],
        "video_output": ["Video Output"],
        "onboard_storage": ["On-board Storage", "On board Storage"],
        "smart_event": ["Smart Event"],
        "approval_protection": ["Protection", "IP Rating"],
        "approval_anti_corrosion_protection": ["Anti-Corrosion Protection", "Anti-Corrosion"],
    }

    def __init__(self):
        """Initialize the extractor."""
        self.field_registry = FieldRegistry()

    def extract_specs(
        self,
        html_content: str,
        product_url: str = ""
    ) -> List[SpecRecord]:
        """
        Extract all specification fields from Hikvision product page.

        Args:
            html_content: Raw HTML string
            product_url: Product URL (for debugging)

        Returns:
            List of SpecRecord objects
        """
        soup = BeautifulSoup(html_content, 'lxml')
        results = []

        # Find all field-value pairs
        field_values = self._find_all_field_values(soup)

        # Extract each known field
        for field_code in self.field_registry.get_all_field_codes():
            raw_value = self._get_value_for_field(field_code, field_values, soup)

            if raw_value:
                normalized = self._normalize_field(field_code, raw_value, soup)
                results.append(SpecRecord(
                    run_id="",  # Will be set by caller
                    brand="hikvision",
                    series_l1="",
                    series_l2="",
                    product_model="",
                    field_code=field_code,
                    raw_value=raw_value,
                    normalized_value=normalized,
                    unit=self.field_registry.get_canonical_unit(field_code),
                    is_manual_override=False
                ))

        return results

    def _find_all_field_values(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Find all field-value pairs in the page.

        Scans all li elements and extracts those with "label\nvalue" structure.

        Returns:
            Dict mapping label → value
        """
        field_values = {}

        all_lis = soup.find_all('li')
        for li in all_lis:
            label, value = self._extract_label_and_value(li)
            if label and value:
                # Normalize label for matching
                label_normalized = label.strip()
                if label_normalized not in field_values:  # Keep first occurrence
                    field_values[label_normalized] = value

        return field_values

    def _extract_label_and_value(self, li: Tag) -> tuple[Optional[str], str]:
        """
        Extract label and value from a li element.

        The li contains:
        - Label as the first line
        - Value as subsequent lines

        Returns:
            (label, value) tuple, or (None, "") if not a valid spec field
        """
        # Get all text content
        full_text = li.get_text(separator='\n', strip=False)

        # Split by newline and clean up
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]

        if not lines:
            return None, ""

        # First line is the label
        label = lines[0]

        # Rest is the value (join remaining lines)
        value = ' '.join(lines[1:]) if len(lines) > 1 else ""

        # Validate: label should be short, value should exist
        if len(label) > 100:  # Too long to be a field label
            return None, ""

        return label, value

    def _get_value_for_field(
        self,
        field_code: str,
        field_values: Dict[str, str],
        soup: BeautifulSoup
    ) -> Optional[str]:
        """Find the value for a field in the field_values dict."""
        # Special cases
        if field_code == "stream_count":
            # Infer from Third Stream
            return self._infer_stream_count(soup)
        elif field_code == "supplement_light_type":
            # Infer from IR Range
            return self._infer_light_type(soup)
        elif field_code == "deep_learning_function_categories":
            # Use Smart Event value
            if "Smart Event" in field_values:
                return field_values["Smart Event"]

        # Standard label matching
        if field_code in self.FIELD_LABELS:
            for label in self.FIELD_LABELS[field_code]:
                # Try exact match
                if label in field_values:
                    return field_values[label]

                # Try case-insensitive match
                label_lower = label.lower()
                for field_label, value in field_values.items():
                    if field_label.lower() == label_lower:
                        return value

                    # Try substring match (label is contained in field_label)
                    if label_lower in field_label.lower():
                        return value

        return None

    def _infer_stream_count(self, soup: BeautifulSoup) -> Optional[int]:
        """
        Infer stream count from presence of Third Stream.

        If "Third Stream" exists → 3 streams
        Otherwise → 2 streams
        """
        page_text = soup.get_text()

        if re.search(r'Third Stream', page_text, re.IGNORECASE):
            return 3
        elif re.search(r'Sub Stream|Sub-stream', page_text, re.IGNORECASE):
            return 2

        return None

    def _infer_light_type(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Infer supplement light type from page content.

        If "IR Range" or "IR" is mentioned → "IR"
        """
        page_text = soup.get_text()

        if re.search(r'\bIR\s+Range\b', page_text, re.IGNORECASE):
            return "IR"

        if re.search(r'\bIR\b', page_text, re.IGNORECASE):
            # Make sure it's not just a random word
            context = soup.get_text()
            if 'Range' in context or 'Illuminator' in context:
                return "IR"

        return None

    def _normalize_field(
        self,
        field_code: str,
        raw_value: str,
        soup: BeautifulSoup
    ) -> Optional[str]:
        """Normalize a raw value according to field type."""

        try:
            if field_code == "main_stream_max_fps_resolution":
                return self._normalize_main_stream(raw_value)
            elif field_code == "supplement_light_range":
                return self._normalize_distance(raw_value)
            elif field_code == "aperture":
                return self._normalize_aperture(raw_value)
            elif field_code == "deep_learning_function_categories":
                return self._normalize_smart_events(raw_value)
            elif field_code == "interface_items":
                return self._normalize_interfaces(raw_value, soup)
            elif field_code == "max_resolution":
                return self._normalize_resolution(raw_value)

            return raw_value
        except Exception:
            return raw_value

    def _normalize_main_stream(self, raw_value: str) -> Optional[str]:
        """
        Extract main stream max FPS and resolution.

        Example input:
        "50Hz: 20 fps (3840 × 2160), 25 fps (3072 × 1728, ...)"

        Extract: 20fps@3840x2160
        """
        # Find the highest resolution (first in list usually)
        match = re.search(r'(\d+)\s*fps\s*\((\d+)\s*[×xX]\s*(\d+)\)', raw_value)
        if match:
            fps = match.group(1)
            width = match.group(2)
            height = match.group(3)
            return f"{fps}fps@{width}x{height}"

        return raw_value

    def _normalize_distance(self, raw_value: str) -> Optional[float]:
        """
        Extract distance value in meters.

        Examples:
        "Up to 30 m" → 30.0
        "30 m" → 30.0
        """
        # Extract number and unit
        match = re.search(r'(\d+(?:\.\d+)?)\s*(m|meter|meters)\b', raw_value, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    def _normalize_aperture(self, raw_value: str) -> str:
        """
        Normalize aperture to f/number format.

        Examples:
        "F1.6" → "f/1.6"
        "f/1.6" → "f/1.6"
        """
        # Extract numeric value
        match = re.search(r'([\d.]+)', raw_value)
        if match:
            return f"f/{match.group(1)}"
        return raw_value

    def _normalize_smart_events(self, raw_value: str) -> str:
        """
        Normalize smart event list to JSON array.

        Example input:
        "Line crossing detection, intrusion detection, unattended baggage, object removal, face detection, scene change detection"

        Output: JSON array of function categories
        """
        # Split by common separators
        events = re.split(r'[,;，、]', raw_value)
        events = [e.strip() for e in events if e.strip()]

        # Map to function categories
        categories = set()
        for event in events:
            event_lower = event.lower()
            if 'line crossing' in event_lower:
                categories.add("Line Crossing Detection")
            elif 'intrusion' in event_lower:
                categories.add("Intrusion Detection")
            elif 'unattended' in event_lower or 'baggage' in event_lower:
                categories.add("Unattended Baggage Detection")
            elif 'object removal' in event_lower:
                categories.add("Object Removal Detection")
            elif 'face' in event_lower:
                categories.add("Face Detection")
            elif 'scene change' in event_lower:
                categories.add("Scene Change Detection")

        if categories:
            return json.dumps(sorted(list(categories)), ensure_ascii=False)

        return raw_value

    def _normalize_interfaces(self, raw_value: str, soup: BeautifulSoup) -> str:
        """
        Normalize interface items to JSON array.

        Collects all interface-related fields.
        """
        interfaces = []

        if raw_value:
            interfaces.append(raw_value.strip())

        # Check for other interface fields
        all_lis = soup.find_all('li')
        for li in all_lis:
            label, value = self._extract_label_and_value(li)
            if label and value:
                label_lower = label.lower()
                if any(term in label_lower for term in ['video output', 'on-board', 'on board', 'storage']):
                    if value.strip() and value.strip() != "No":
                        interfaces.append(value.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_interfaces = []
        for iface in interfaces:
            if iface not in seen:
                seen.add(iface)
                unique_interfaces.append(iface)

        if unique_interfaces:
            return json.dumps(unique_interfaces, ensure_ascii=False)

        return raw_value

    def _normalize_resolution(self, raw_value: str) -> str:
        """
        Normalize resolution to WIDTHxHEIGHT format.

        Examples:
        "3840 × 2160" → "3840x2160"
        "1920×1080" → "1920x1080"
        """
        # Normalize the multiplication symbol
        normalized = re.sub(r'\s*[×xX]\s*', 'x', raw_value.strip())
        return normalized
