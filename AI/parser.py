import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_move_index(response: str, legal_moves: list) -> dict | None:
    text = response.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "move_index" in data:
            idx = data["move_index"]
            if isinstance(idx, int) and 0 <= idx < len(legal_moves):
                return legal_moves[idx]
            logger.warning(f"move_index {idx} out of range (0-{len(legal_moves)-1})")
            return None
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^{}]*"move_index"\s*:\s*(\d+)[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            idx = data["move_index"]
            if 0 <= idx < len(legal_moves):
                return legal_moves[idx]
            logger.warning(f"Extracted move_index {idx} out of range")
            return None
        except (json.JSONDecodeError, KeyError):
            pass

    numbers = re.findall(r'\b(\d+)\b', text)
    for num_str in numbers:
        idx = int(num_str)
        if 0 <= idx < len(legal_moves):
            logger.info(f"Recovered move_index {idx} from fallback number extraction")
            return legal_moves[idx]

    logger.warning(f"Could not parse any move index from response: {text[:200]}")
    return None