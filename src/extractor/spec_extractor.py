"""
Specification Extractor for competitor product scraping.

This module extracts product specification fields from HTML pages using
BeautifulSoup with multiple fallback strategies for resilience.

Key features:
- Multi-strategy extraction (label-based, position-based, regex-based)
- Confidence scoring (0.0-1.0) based on extraction method
- Graceful handling of missing/invalid data
- Support for multi-language field aliases
- List field handling with JSON array output
"""

import re
import json
from dataclasses import dataclass
from typing import Dict, Optional, List, Any, Tuple
from bs4 import BeautifulSoup, Tag
from collections import defaultdict

from .field_registry import FieldRegistry
from .parsers.resolution_parser import ResolutionParser
from .parsers.stream_parser import StreamParser
from .parsers.range_parser import RangeParser
from src.core.types import SpecRecord


@dataclass
class ExtractionResult:
    """Result of a field extraction attempt."""
    field_code: str
    raw_value: Optional[str]
    normalized_value: Optional[str]
    confidence: float
    extraction_method: str  # label_match, position_inference, regex_fallback
    issues: List[str]


class SpecExtractor:
    """
    Extract specification fields from HTML product pages.

    Extraction strategies (in order of preference):
    1. Label-based matching: Find field label, extract corresponding value
    2. Position-based inference: Extract from known table structures
    3. Regex fallback: Pattern matching for known value formats

    Each extraction includes confidence scoring:
    - 1.0: Exact label match in structured table
    - 0.8: Fuzzy label match or inferred position
    - 0.6: Regex pattern match without label context
    - 0.0: Failed extraction
    """

    # Regex patterns for common value formats
    PATTERNS = {
        "resolution": re.compile(r'(\d{3,5})\s*[xX×]\s*(\d{3,5})'),
        "fps": re.compile(r'(\d+)\s*fps', re.IGNORECASE),
        "distance": re.compile(r'(\d+(?:\.\d+)?)\s*(m|meters?|ft|feet)\b', re.IGNORECASE),
        "aperture": re.compile(r'f\/?\s*([\d.]+)', re.IGNORECASE),
    }

    def __init__(self):
        """Initialize the extractor with specialized parsers."""
        self.resolution_parser = ResolutionParser()
        self.stream_parser = StreamParser()
        self.range_parser = RangeParser()
        self.field_registry = FieldRegistry()

    def extract_all_fields(
        self,
        html_content: str,
        source_url: str = ""
    ) -> Tuple[Dict[str, ExtractionResult], List[str]]:
        """
        Extract all known fields from HTML content.

        Args:
            html_content: Raw HTML string of the product page
            source_url: URL of the page (for logging/debugging)

        Returns:
            Tuple of:
            - Dict mapping field_code to ExtractionResult
            - List of warning messages
        """
        soup = BeautifulSoup(html_content, 'lxml')
        results = {}
        warnings = []

        # Find all potential specification containers
        spec_containers = self._find_spec_containers(soup)

        if not spec_containers:
            warnings.append(f"No specification containers found on page {source_url}")
            # Return empty results for all fields
            for field_code in self.field_registry.get_all_field_codes():
                results[field_code] = ExtractionResult(
                    field_code=field_code,
                    raw_value=None,
                    normalized_value=None,
                    confidence=0.0,
                    extraction_method="none",
                    issues=["No specification containers found"]
                )
            return results, warnings

        # Extract each field using multiple strategies
        for field_code in self.field_registry.get_all_field_codes():
            field_def = self.field_registry.get_field(field_code)

            # Special handling for fields that require page-level inference
            if field_code == "stream_count":
                result = self._extract_stream_count_by_inference(soup)
                results[field_code] = result
                continue

            if field_code == "supplement_light_type":
                result = self._extract_supplement_light_type_by_inference(soup)
                results[field_code] = result
                continue

            if field_code == "deep_learning_function_categories":
                result = self._extract_smart_events(soup)
                results[field_code] = result
                continue

            # Strategy 1: Label-based extraction
            result = self._extract_by_label(
                soup,
                field_code,
                field_def
            )

            # Strategy 2: If label-based failed, try position-based
            if result.confidence == 0.0 and spec_containers:
                result = self._extract_by_position(
                    spec_containers[0],
                    field_code,
                    field_def
                )

            # Strategy 3: Last resort regex extraction
            if result.confidence == 0.0:
                result = self._extract_by_regex(
                    soup,
                    field_code,
                    field_def
                )

            results[field_code] = result

        # Post-processing for Dahua-specific field mappings
        self._post_process_dahua_fields(results, soup)

        return results, warnings

    def _post_process_dahua_fields(self, results: Dict[str, ExtractionResult], soup: BeautifulSoup):
        """Handle Dahua-specific field mappings and corrections."""
        
        # Directly search for IP rating in table (Dahua uses "Protection" -> "IP67")
        anti_corrosion_result = results.get("approval_anti_corrosion_protection")
        if not anti_corrosion_result or anti_corrosion_result.confidence == 0.0:
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    # Exact match for "Protection" label with IP rating value
                    if label == "Protection" and re.search(r'IP\d{2}', value):
                        results["approval_anti_corrosion_protection"] = ExtractionResult(
                            field_code="approval_anti_corrosion_protection",
                            raw_value=value,
                            normalized_value=value,
                            confidence=1.0,
                            extraction_method="dahua_protection_table",
                            issues=[]
                        )
                        break
        
        # Handle combined supplement light types (IR + Warm Light)
        sup_light_result = results.get("supplement_light_type")
        if (sup_light_result and 
            sup_light_result.raw_value == "Warm Light" and
            "ir" in soup.get_text().lower()):
            # This is actually IR + Warm Light combo
            results["supplement_light_type"] = ExtractionResult(
                field_code="supplement_light_type",
                raw_value="IR + Warm Light",
                normalized_value="IR + Warm Light",
                confidence=0.9,
                extraction_method="dahua_post_process",
                issues=[]
            )

    def _find_spec_containers(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Find potential specification containers in the HTML.

        Looks for common patterns:
        - Tables with "specification" in class/id
        - Div lists with spec-like structure
        - Description lists (dl/dt/dd)
        - Hikvision-specific: div.main-item

        Returns:
            List of BeautifulSoup Tag objects
        """
        containers = []

        # Hikvision-specific: div.main-item structure
        main_items = soup.find_all('div', class_='main-item')
        if main_items:
            # Wrap in a parent div for easier processing
            containers.append(main_items[0].parent)
            return containers

        # Try specification tables
        spec_tables = soup.find_all('table', class_=re.compile(r'spec', re.I))
        containers.extend(spec_tables)

        # Try div-based specs
        spec_divs = soup.find_all('div', class_=re.compile(r'spec|param|detail', re.I))
        containers.extend(spec_divs)

        # Try description lists
        dls = soup.find_all('dl')
        containers.extend(dls)

        # If no specific containers found, look for any table
        if not containers:
            tables = soup.find_all('table')
            if tables:
                containers.append(tables[0])

        return containers

    def _extract_by_label(
        self,
        soup: BeautifulSoup,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """
        Extract field value by finding its label in the page.

        Searches for field label (or any alias) and extracts the corresponding value.

        Args:
            soup: BeautifulSoup object
            field_code: Field code to extract
            field_def: FieldDefinition object

        Returns:
            ExtractionResult with confidence score
        """
        search_terms = field_def.get_all_search_terms()

        for term in search_terms:
            # Try different HTML structures
            result = self._try_label_in_table(soup, term, field_code, field_def)
            if result.confidence > 0:
                return result

            result = self._try_label_in_list(soup, term, field_code, field_def)
            if result.confidence > 0:
                return result

            result = self._try_label_in_dl(soup, term, field_code, field_def)
            if result.confidence > 0:
                return result

        # No label match found
        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="label_match_failed",
            issues=[]
        )

    def _try_label_in_table(
        self,
        soup: BeautifulSoup,
        label: str,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """Extract from table structure (label in one cell, value in adjacent cell)."""
        # First try Hikvision-specific structure: div.main-item > div.item-title
        main_items = soup.find_all('div', class_='main-item')
        if main_items:
            label_lower = label.lower()
            for item in main_items:
                title_div = item.find('div', class_='item-title')
                if title_div:
                    title_text = title_div.get_text(strip=True).lower()
                    # Check for exact match or contains match
                    if title_text == label_lower or label_lower in title_text:
                        # Value is in item-title-detail div (Hikvision structure)
                        value_div = item.find('div', class_='item-title-detail')
                        if value_div:
                            return self._parse_text_value(
                                value_div.get_text(strip=True),
                                field_code,
                                field_def,
                                confidence=1.0,
                                method="label_match_hikvision",
                                soup=soup
                            )

        # Try Hikvision alternative: li.tech-specs-items-description-list
        spec_items = soup.find_all('li', class_='tech-specs-items-description-list')
        if spec_items:
            label_lower = label.lower()
            for item in spec_items:
                title_span = item.find('span', class_='tech-specs-items-description__title')
                if title_span:
                    title_text = title_span.get_text(strip=True).lower()
                    if title_text == label_lower or label_lower in title_text:
                        value_span = item.find('span', class_='tech-specs-items-description__description')
                        if value_span:
                            return self._parse_text_value(
                                value_span.get_text(strip=True),
                                field_code,
                                field_def,
                                confidence=1.0,
                                method="label_match_hikvision_alt",
                                soup=soup
                            )

        # Standard table extraction (fallback)
        rows = soup.find_all('tr')
        label_lower = label.lower()

        for row in rows:
            cells = row.find_all(['td', 'th'])
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True).lower()
                if label_lower in cell_text and len(cell_text) < 100:
                    # Found label, extract value from next cell
                    if i + 1 < len(cells):
                        value_cell = cells[i + 1]
                        return self._parse_value_from_cell(
                            value_cell,
                            field_code,
                            field_def,
                            confidence=1.0,
                            method="label_match_table",
                            soup=soup
                        )

        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="label_match_table_failed",
            issues=[]
        )

    def _try_label_in_list(
        self,
        soup: BeautifulSoup,
        label: str,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """Extract from list structure (label in one item, value in next or same)."""
        list_items = soup.find_all('li')
        label_lower = label.lower()

        for i, item in enumerate(list_items):
            item_text = item.get_text(strip=True).lower()
            if label_lower in item_text and len(item_text) < 100:
                # Check if value is in the same item (after colon/space)
                full_text = item.get_text(strip=True)
                if ':' in full_text or '：' in full_text:
                    parts = re.split(r'[:：]', full_text, 1)
                    if len(parts) == 2:
                        return self._parse_text_value(
                            parts[1].strip(),
                            field_code,
                            field_def,
                            confidence=0.9,
                            method="label_match_list",
                            soup=soup
                        )

                # Check if value is in next item
                if i + 1 < len(list_items):
                    next_item = list_items[i + 1]
                    return self._parse_value_from_cell(
                        next_item,
                        field_code,
                        field_def,
                        confidence=0.8,
                        method="label_match_list_next",
                        soup=soup
                    )

        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="label_match_list_failed",
            issues=[]
        )

    def _try_label_in_dl(
        self,
        soup: BeautifulSoup,
        label: str,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """Extract from description list (dt=term, dd=definition)."""
        dts = soup.find_all('dt')
        label_lower = label.lower()

        for dt in dts:
            dt_text = dt.get_text(strip=True).lower()
            if label_lower in dt_text:
                # Find the next dd element
                dd = dt.find_next_sibling('dd')
                if dd:
                    return self._parse_value_from_cell(
                        dd,
                        field_code,
                        field_def,
                        confidence=1.0,
                        method="label_match_dl",
                        soup=soup
                    )

        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="label_match_dl_failed",
            issues=[]
        )

    def _extract_by_position(
        self,
        container: Tag,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """
        Extract field value by positional inference.

        This is a fallback that tries to guess the value based on common
        positional patterns in spec tables.

        Args:
            container: Container element to search within
            field_code: Field code to extract
            field_def: FieldDefinition object

        Returns:
            ExtractionResult with confidence score
        """
        # For some fields, we can infer likely positions
        position_hints = {
            "max_resolution": 0,  # Often first row
            "image_sensor": 1,
            "lens_type": 2,
        }

        if field_code in position_hints:
            target_row = position_hints[field_code]
            rows = container.find_all('tr')

            if target_row < len(rows):
                cells = rows[target_row].find_all(['td', 'th'])
                if len(cells) >= 2:
                    return self._parse_value_from_cell(
                        cells[1],
                        field_code,
                        field_def,
                        confidence=0.7,
                        method="position_inference",
                        soup=None
                    )

        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="position_inference_failed",
            issues=[]
        )

    def _extract_by_regex(
        self,
        soup: BeautifulSoup,
        field_code: str,
        field_def
    ) -> ExtractionResult:
        """
        Extract field value using regex pattern matching.

        This is the last resort strategy that searches for known value
        patterns anywhere in the page.

        Args:
            soup: BeautifulSoup object
            field_code: Field code to extract
            field_def: FieldDefinition object

        Returns:
            ExtractionResult with confidence score
        """
        full_text = soup.get_text()

        # Field-specific regex patterns
        if field_code == "max_resolution":
            match = self.PATTERNS["resolution"].search(full_text)
            if match:
                raw = f"{match.group(1)}x{match.group(2)}"
                normalized = self.resolution_parser.normalize(raw)
                return ExtractionResult(
                    field_code=field_code,
                    raw_value=raw,
                    normalized_value=normalized,
                    confidence=0.6,
                    extraction_method="regex_fallback",
                    issues=[]
                )

        elif field_code == "supplement_light_range":
            match = self.PATTERNS["distance"].search(full_text)
            if match:
                raw = match.group(0)
                normalized = self.range_parser.normalize(raw)
                return ExtractionResult(
                    field_code=field_code,
                    raw_value=raw,
                    normalized_value=normalized,
                    confidence=0.6,
                    extraction_method="regex_fallback",
                    issues=[]
                )

        elif field_code == "aperture":
            match = self.PATTERNS["aperture"].search(full_text)
            if match:
                raw = match.group(0)
                normalized = f"f/{match.group(1)}"
                return ExtractionResult(
                    field_code=field_code,
                    raw_value=raw,
                    normalized_value=normalized,
                    confidence=0.6,
                    extraction_method="regex_fallback",
                    issues=[]
                )

        return ExtractionResult(
            field_code=field_code,
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="regex_fallback_failed",
            issues=[]
        )

    def _parse_value_from_cell(
        self,
        cell: Tag,
        field_code: str,
        field_def,
        confidence: float,
        method: str,
        soup: BeautifulSoup = None
    ) -> ExtractionResult:
        """
        Parse value from a table cell or list item.

        Handles different value types (text, numbers, lists) and applies
        appropriate normalization.

        Args:
            cell: BeautifulSoup Tag containing the value
            field_code: Field code being extracted
            field_def: FieldDefinition object
            confidence: Base confidence score
            method: Extraction method name
            soup: Optional BeautifulSoup object for page-level inference

        Returns:
            ExtractionResult with parsed and normalized value
        """
        text = cell.get_text(strip=True)

        # Handle empty values
        if not text or text.lower() in ['-', 'n/a', 'none', '']:
            return ExtractionResult(
                field_code=field_code,
                raw_value=None,
                normalized_value=None,
                confidence=0.0,
                extraction_method=method,
                issues=["Empty cell value"]
            )

        # Handle list fields (multiple values)
        if field_def.value_type == "list_text":
            return self._parse_list_value(
                cell,
                field_code,
                field_def,
                confidence,
                method
            )

        # Handle individual field types
        return self._parse_text_value(
            text,
            field_code,
            field_def,
            confidence,
            method,
            soup=soup
        )

    def _parse_list_value(
        self,
        cell: Tag,
        field_code: str,
        field_def,
        confidence: float,
        method: str
    ) -> ExtractionResult:
        """
        Parse a list field value from a cell.

        List fields may contain multiple values separated by commas,
        bullets, or multiple elements.

        Args:
            cell: BeautifulSoup Tag containing the value(s)
            field_code: Field code being extracted
            field_def: FieldDefinition object
            confidence: Base confidence score
            method: Extraction method name

        Returns:
            ExtractionResult with values as JSON array
        """
        # Try to find multiple child elements (e.g., <li> items)
        items = cell.find_all('li')
        if items:
            values = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
        else:
            # Split by common separators
            text = cell.get_text(strip=True)
            values = re.split(r'[,;，、\n]', text)
            values = [v.strip() for v in values if v.strip()]

        if not values:
            return ExtractionResult(
                field_code=field_code,
                raw_value=None,
                normalized_value=None,
                confidence=0.0,
                extraction_method=method,
                issues=["No list items found"]
            )

        # Store as JSON array
        raw_json = json.dumps(values, ensure_ascii=False)

        return ExtractionResult(
            field_code=field_code,
            raw_value=raw_json,
            normalized_value=raw_json,  # No additional normalization for lists
            confidence=confidence,
            extraction_method=method,
            issues=[]
        )

    def _parse_text_value(
        self,
        text: str,
        field_code: str,
        field_def,
        confidence: float,
        method: str,
        soup: BeautifulSoup = None
    ) -> ExtractionResult:
        """
        Parse and normalize a text field value.

        Applies field-specific normalization based on the field type.

        Args:
            text: Raw text value
            field_code: Field code being extracted
            field_def: FieldDefinition object
            confidence: Base confidence score
            method: Extraction method name

        Returns:
            ExtractionResult with normalized value
        """
        raw_value = text
        normalized_value = text  # Default: no normalization

        # Apply field-specific normalization
        try:
            if field_code == "max_resolution":
                normalized_value = self.resolution_parser.normalize(text)

            elif field_code == "main_stream_max_fps_resolution":
                normalized_value = self.stream_parser.normalize(text)

            elif field_code == "supplement_light_range":
                normalized_value = self.range_parser.normalize(text)

            elif field_code == "aperture":
                normalized_value = self._normalize_aperture(text)

            elif field_code == "stream_count":
                normalized_value = self._parse_stream_count(text)

            elif field_code == "supplement_light_type":
                normalized_value = self._infer_supplement_light_type(text, soup)

            # For other text fields, use basic cleanup
            else:
                normalized_value = self._cleanup_text(text)

        except Exception as e:
            return ExtractionResult(
                field_code=field_code,
                raw_value=raw_value,
                normalized_value=None,
                confidence=confidence * 0.5,  # Lower confidence on parse error
                extraction_method=method,
                issues=[f"Normalization error: {str(e)}"]
            )

        return ExtractionResult(
            field_code=field_code,
            raw_value=raw_value,
            normalized_value=normalized_value,
            confidence=confidence,
            extraction_method=method,
            issues=[]
        )

    def _normalize_aperture(self, text: str) -> str:
        """
        Normalize aperture value to f/number format.

        Args:
            text: Raw aperture text

        Returns:
            Normalized aperture in f/number format
        """
        # Extract numeric value
        match = re.search(r'([\d.]+)', text)
        if match:
            return f"f/{match.group(1)}"
        return text

    def _infer_supplement_light_type(self, text: str, soup: BeautifulSoup = None) -> str:
        """
        Infer supplement light type from text or page context.

        Look for keywords like "IR", "LED", "White light", "Laser" in the text
        or in related fields like "Wavelength", "IR Range" on the page.

        Args:
            text: Raw text to analyze
            soup: BeautifulSoup object for page-level inference

        Returns:
            Inferred light type (e.g., "IR", "White Light", "Laser")
        """
        text_lower = text.lower()

        # Direct keyword matching in the input text
        if 'white light' in text_lower:
            return "White Light"
        if 'laser' in text_lower:
            return "Laser"
        if 'led' in text_lower and 'ir led' not in text_lower:
            return "LED"

        # Page-level inference if soup is available
        if soup:
            page_text = soup.get_text().lower()

            # Check for "IR Range" field (strong indicator for IR)
            if re.search(r'ir\s+range', page_text):
                return "IR"

            # Check for "Wavelength" with typical IR wavelengths
            if re.search(r'wavelength.*\b(850|940|880|870)\b', page_text):
                return "IR"

            # Check for "Infrared" keyword
            if 'infrared' in page_text:
                return "IR"

            # Check for white light indicators
            if re.search(r'white\s+light', page_text):
                return "White Light"

        # Check input text for IR/Infrared
        if 'infrared' in text_lower or ('ir' in text_lower and 'wire' not in text_lower):
            return "IR"

        return ""

    def _extract_supplement_light_type_by_inference(self, soup: BeautifulSoup) -> ExtractionResult:
        """
        Extract supplement light type by page-level inference.

        Looks for "IR Range", "Wavelength", "Infrared", "White Light" keywords
        on the page to determine the light type.

        Args:
            soup: BeautifulSoup object

        Returns:
            ExtractionResult with inferred light type
        """
        page_text = soup.get_text().lower()

        # Check for "IR Range" field (strong indicator for IR)
        if re.search(r'ir\s+range', page_text):
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="IR",
                normalized_value="IR",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for "Wavelength" with typical IR wavelengths
        if re.search(r'wavelength.*\b(850|940|880|870)\b', page_text):
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="IR",
                normalized_value="IR",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for "Infrared" keyword
        if 'infrared' in page_text:
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="IR",
                normalized_value="IR",
                confidence=0.9,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for white light indicators
        if re.search(r'white\s+light', page_text):
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="White Light",
                normalized_value="White Light",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for warm light (Dahua uses this term)
        if re.search(r'warm\s+light', page_text):
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="Warm Light",
                normalized_value="Warm Light",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for laser
        if 'laser' in page_text:
            return ExtractionResult(
                field_code="supplement_light_type",
                raw_value="Laser",
                normalized_value="Laser",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # No light type information found
        return ExtractionResult(
            field_code="supplement_light_type",
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="page_inference_failed",
            issues=["No supplement light type information found on page"]
        )

    def _extract_smart_events(self, soup: BeautifulSoup) -> ExtractionResult:
        """
        Extract smart events/deep learning functions from product pages.

        Handles both Hikvision (main-item structure) and Dahua (table structure).

        Args:
            soup: BeautifulSoup object

        Returns:
            ExtractionResult with smart event list as JSON array
        """
        # First try Hikvision main-item structure
        main_items = soup.find_all('div', class_='main-item')
        for item in main_items:
            title_div = item.find('div', class_='item-title')
            if title_div:
                title_text = title_div.get_text(strip=True).lower()
                # Match "Smart Event" or similar
                if 'smart event' in title_text or 'smart' in title_text:
                    detail_div = item.find('div', class_='item-title-detail')
                    if detail_div:
                        value = detail_div.get_text(strip=True)
                        # Parse comma-separated values
                        items = [item.strip() for item in value.split(',') if item.strip()]
                        if items:
                            raw_json = json.dumps(items, ensure_ascii=False)
                            return ExtractionResult(
                                field_code="deep_learning_function_categories",
                                raw_value=raw_json,
                                normalized_value=raw_json,
                                confidence=1.0,
                                extraction_method="smart_event_hikvision",
                                issues=[]
                            )

        # Try table-based extraction (Dahua and others)
        rows = soup.find_all('tr')
        smart_functions = []
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label_cell = cells[0]
                value_cell = cells[1]
                label_text = label_cell.get_text(strip=True).lower()
                value_text = value_cell.get_text(strip=True)
                
                # Check for Dahua-specific intelligence fields
                if any(kw in label_text for kw in ['ivs', 'smd', 'acupick', 'ai ssa', 'smart search', 'face detection']):
                    # Extract the function name from label
                    func_name = label_cell.get_text(strip=True)
                    if func_name and value_text.lower() not in ['no', 'off', 'none']:
                        smart_functions.append(func_name)
                
                # Check for general intelligence keywords
                elif any(kw in label_text for kw in ['intelligence', 'smart', 'deep learning', 'analytics']):
                    if value_text and value_text.lower() not in ['no', 'off', 'none']:
                        # First, try to find <li> elements
                        lis = value_cell.find_all('li')
                        if lis:
                            funcs = [li.get_text(strip=True) for li in lis if li.get_text(strip=True)]
                            smart_functions.extend(funcs)
                        # Then, try to extract specific functions from value
                        elif ',' in value_text or ';' in value_text:
                            # Split by comma/semicolon
                            funcs = [f.strip() for f in re.split(r'[;,]', value_text) if f.strip()]
                            smart_functions.extend(funcs)
                        else:
                            # Single function
                            smart_functions.append(value_text)

        if smart_functions:
            # Deduplicate while preserving order
            seen = set()
            unique_funcs = []
            for f in smart_functions:
                if f not in seen:
                    seen.add(f)
                    unique_funcs.append(f)
            
            raw_json = json.dumps(unique_funcs, ensure_ascii=False)
            return ExtractionResult(
                field_code="deep_learning_function_categories",
                raw_value=raw_json,
                normalized_value=raw_json,
                confidence=0.9,
                extraction_method="smart_event_table",
                issues=[]
            )

        # No smart events found
        return ExtractionResult(
            field_code="deep_learning_function_categories",
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="smart_event_not_found",
            issues=["No deep learning functions found on page"]
        )

    def _extract_stream_count_by_inference(self, soup: BeautifulSoup) -> ExtractionResult:
        """
        Extract stream count by page-level inference.

        Looks for "Third Stream", "Sub Stream", "Main Stream" labels on the page
        to determine the total number of streams.

        Args:
            soup: BeautifulSoup object

        Returns:
            ExtractionResult with inferred stream count
        """
        page_text = soup.get_text()

        # Check for "Third stream" keyword
        if re.search(r'third\s+stream', page_text, re.IGNORECASE):
            return ExtractionResult(
                field_code="stream_count",
                raw_value="3",
                normalized_value="3",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for "Sub stream" keyword (implies 2 streams)
        if re.search(r'sub\s+stream', page_text, re.IGNORECASE):
            return ExtractionResult(
                field_code="stream_count",
                raw_value="2",
                normalized_value="2",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # Check for "Main stream" only (implies 1 stream)
        if re.search(r'main\s+stream', page_text, re.IGNORECASE):
            return ExtractionResult(
                field_code="stream_count",
                raw_value="1",
                normalized_value="1",
                confidence=1.0,
                extraction_method="page_inference",
                issues=[]
            )

        # No stream information found
        return ExtractionResult(
            field_code="stream_count",
            raw_value=None,
            normalized_value=None,
            confidence=0.0,
            extraction_method="page_inference_failed",
            issues=["No stream information found on page"]
        )

    def _parse_stream_count(self, text: str, soup: BeautifulSoup = None) -> str:
        """
        Parse stream count from text.

        If page contains "Third stream" or similar keywords, infer 3 streams.
        If page contains "Sub stream" but no "Third stream", infer 2 streams.
        Otherwise, try to extract a number from text.

        Args:
            text: Raw text containing stream information
            soup: BeautifulSoup object for page-level inference

        Returns:
            String representation of stream count
        """
        if soup:
            page_text = soup.get_text()
            # Check for "Third stream" at page level
            if re.search(r'third\s+stream', page_text, re.IGNORECASE):
                return "3"
            # Check for "Sub stream" but no "Third stream"
            if re.search(r'sub\s+stream', page_text, re.IGNORECASE):
                return "2"
            # Check for "Main stream" only (single stream)
            if re.search(r'main\s+stream', page_text, re.IGNORECASE):
                return "1"

        # Fallback: check in the text itself
        if re.search(r'third\s+stream', text, re.IGNORECASE):
            return "3"
        if re.search(r'sub\s+stream', text, re.IGNORECASE):
            return "2"

        # Try to extract a number
        match = re.search(r'(\d+)', text)
        if match:
            return match.group(1)

        return ""
        if match:
            return match.group(1)

        return ""

    def _cleanup_text(self, text: str) -> str:
        """
        Basic text cleanup for non-specialized fields.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove common artifacts
        text = text.strip()
        return text

    def to_spec_records(
        self,
        extraction_results: Dict[str, ExtractionResult],
        run_id: str,
        brand: str,
        series_l1: str,
        series_l2: str,
        model: str
    ) -> List[SpecRecord]:
        """
        Convert ExtractionResult dict to list of SpecRecord.

        Args:
            extraction_results: Dict from extract_all_fields()
            run_id: Run identifier
            brand: Brand name
            series_l1: Series level 1
            series_l2: Series level 2
            model: Product model

        Returns:
            List of SpecRecord objects with successful extractions only
        """
        spec_records = []

        for field_code, result in extraction_results.items():
            # Only include fields with successful extraction
            if result.raw_value is not None and result.confidence > 0:
                spec_records.append(SpecRecord(
                    run_id=run_id,
                    brand=brand,
                    series_l1=series_l1,
                    series_l2=series_l2,
                    model=model,
                    field_code=field_code,
                    raw_value=result.raw_value,
                    normalized_value=result.normalized_value,
                    unit=self.field_registry.get_canonical_unit(field_code),
                    is_manual_override=False
                ))

        return spec_records
