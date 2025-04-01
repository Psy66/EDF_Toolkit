# core/event_processor.py
import re
from typing import Dict, Optional, Set
from typing_extensions import Final

class EventProcessor:
	"""Handler for generating event names and processing events."""

	EXCLUDED_NAMES: Final[Set[str]] = {
		"stimFlash", "Артефакт", "Начало печати", "Окончание печати",
		"Эпилептиформная активность", '''Комплекс "острая волна - медленная волна"''',
		"Множественные спайки и острые волны", "Разрыв записи"
	}

	TRANSLATIONS: Final[Dict[str, str]] = {
		"Фоновая запись": "Baseline",
		"Открывание глаз": "EyesOpen",
		"Закрывание глаз": "EyesClosed",
		"Без стимуляции": "Rest",
		"Фотостимуляция": "PhoticStim",
		"После фотостимуляции": "PostPhotic",
		"Встроенный фотостимулятор": "Photic",
		"Встроенный слуховой стимулятор": "Auditory",
		"Остановка стимуляции": "StimOff",
		"Гипервентиляция": "Hypervent",
		"После гипервентиляции": "PostHypervent",
		"Бодрствование": "Awake"
	}

	@classmethod
	def _clean_event_name(cls, name: str) -> Optional[str]:
		"""Cleans event name: removes brackets/parentheses, checks excluded names, translates to English."""
		cleaned_name = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()

		if cleaned_name in cls.EXCLUDED_NAMES or name in cls.EXCLUDED_NAMES:
			return None

		if not cleaned_name:
			return name if name else "Unknown"

		for ru_name, en_name in cls.TRANSLATIONS.items():
			if ru_name in cleaned_name:
				if "Photic" in en_name or "Auditory" in en_name:
					freq_match = re.search(r'(\d+)\s*Гц', name)
					tone_match = re.search(r'Тон\s*(\d+)\s*Гц', name)
					if tone_match:
						return f"{en_name}{tone_match.group(1)}Hz"
					elif freq_match:
						return f"{en_name}{freq_match.group(1)}Hz"
				return en_name

		return cleaned_name

	@classmethod
	def get_event_name(cls, evt_code: int, ev_id: Dict[str, int]) -> Optional[str]:
		"""Returns the event name based on its code."""
		name = next((name for name, code in ev_id.items() if code == evt_code), "Unknown")
		return cls._clean_event_name(name)

	@classmethod
	def generate_segment_name(cls, base_name: Optional[str], existing_names: Set[str]) -> str:
		"""Generates a unique name for a segment."""
		base = base_name if base_name is not None else "Unknown"
		seg_name = base
		counter = 1
		while seg_name in existing_names:
			seg_name = f"{base}_{counter}"
			counter += 1
		return seg_name