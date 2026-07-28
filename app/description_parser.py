import re
from typing import List, Dict, Optional, Set
from .models import ReceiptItem


NON_PERSON_WORDS = {
    'i', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours', 'you', 'your',
    'the', 'a', 'an', 'and', 'or', 'but', 'had', 'has', 'have', 'was',
    'were', 'is', 'are', 'just', 'shared', 'common', 'everything', 'else',
    'rest', 'of', 'who', 'paid', 'bill', 'skipped', 'drinks', 'only',
    'both', 'three', 'four', 'two', 'one', 'none', 'all', 'some', 'every',
    'others', 'remaining', 'used', 'coupon', 'off', 'each', 'things', 'item',
    'items', 'food', 'order', 'total', 'pay', 'split', 'owe', 'owed',
    'dish', 'dishes', 'meal', 'meals', 'portion', 'included', 'excluding',
    'except', 'besides', 'also', 'too', 'with', 'without', 'between', 'among',
    'pc', 'qty', 'amount', 'price', 'ordered', 'consumed', 'ate', 'got',
    'took', 'enjoyed', 'his', 'her', 'its', 'their', 'this', 'that',
    'these', 'those', 'it', 'them', 'they', 'he', 'she', 'him',
    'cappuccino', 'sandwich', 'pasta', 'penne', 'arrabiata', 'lime',
    'soda', 'brownie', 'paneer', 'masala', 'dal', 'makhani', 'naan',
    'bread', 'rice', 'jeera', 'gulab', 'jamun', 'papad', 'pizza',
    'garlic', 'beer', 'beers', 'mojito', 'biryani', 'veg', 'mutton',
    'rogan', 'josh', 'raita', 'drinks', 'soft', 'chicken', 'butter',
    'fresh', 'grilled', 'margherita', 'craft', 'virgin', 'welcome',
    'coupon', 'pepsi', 'cola', 'water', 'thums', 'up', 'sprite',
}


ITEM_ALIASES = {
    'cappuccino': ['cappuccino', 'coffee'],
    'grilled chicken sandwich': ['sandwich', 'chicken sandwich'],
    'penne arrabiata': ['pasta', 'penne', 'arrabiata'],
    'fresh lime soda': ['lime soda', 'lime', 'soda'],
    'brownie': ['brownie'],
    'paneer butter masala': ['paneer', 'butter masala'],
    'dal makhani': ['dal', 'makhani'],
    'butter naan': ['naan', 'bread'],
    'jeera rice': ['rice', 'jeera'],
    'gulab jamun': ['gulab jamun'],
    'masala papad': ['papad'],
    'margherita pizza': ['pizza', 'margherita'],
    'arrabiata pasta': ['pasta', 'arrabiata'],
    'garlic bread': ['garlic bread', 'garlic'],
    'craft beer': ['beer', 'beers'],
    'virgin mojito': ['mojito'],
    'chicken biryani': ['chicken biryani'],
    'veg biryani': ['veg biryani'],
    'mutton rogan josh': ['rogan josh', 'mutton rogan'],
    'raita': ['raita'],
    'soft drinks': ['drinks', 'soft drinks'],
    'tomate de cacho': ['tomate', 'tomates', 'tomato', 'tomatoes'],
    'abacaxi': ['abacaxi', 'pineapple'],
    'batata cons. roxa': ['batata', 'potatoes', 'potato'],
    'ameixa rain. cla. emb.': ['ameixa', 'plums', 'plum'],
    'mozzarella sort.': ['mozzarella'],
    'queijo cabra': ['queijo cabra', 'goat cheese', 'cheese'],
    'queijo feta': ['queijo feta', 'feta'],
    'azeite gallo': ['azeite', 'olive oil', 'olive'],
    'cornichons': ['cornichons', 'pickles'],
    'branco reg ribatejo': ['branco', 'wine', 'ribatejo'],
    'agua de nascente': ['agua', 'water'],
}


def _get_aliases(item_name: str) -> List[str]:
    key = item_name.lower().strip()
    if key in ITEM_ALIASES:
        return [key] + ITEM_ALIASES[key]
    words = key.split()
    return [key] + [w for w in words if len(w) > 2]


def _item_name_in_text(item_name: str, text: str) -> bool:
    text_lower = text.lower()
    for alias in _get_aliases(item_name):
        if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
            return True
    return False


class DescriptionParser:
    def parse(self, description: str, items: List[ReceiptItem]) -> dict:
        assumptions = []
        flags = []
        people = self._extract_people(description)
        paid_by = self._extract_payer(description, people)
        if paid_by is None:
            flags.append("No payer mentioned in description — cannot determine who paid")

        personal: Dict[int, str] = {}
        personal_each: Dict[int, List[str]] = {}
        assignments: Dict[int, List[str]] = {}

        sentences = re.split(r'[.;!]', description)

        for idx, item in enumerate(items):
            item_lower = item.name.lower()
            assigned = False
            aliases = _get_aliases(item.name)

            for sentence in sentences:
                s = sentence.strip()
                if not s:
                    continue
                s_lower = s.lower()

                if not _item_name_in_text(item.name, s):
                    continue

                for alias in aliases:
                    m = re.search(r'([A-Z][a-z]+)\s+(?:had|took|ordered|got|ate)\b.*' + re.escape(alias), s, re.IGNORECASE)
                    if m:
                        person = m.group(1)
                        if person in people:
                            personal[idx] = person
                            assigned = True
                            break
                if assigned:
                    break

                m = re.search(r'([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+each\s+(?:had|ordered|got)\b', s, re.IGNORECASE)
                if m and _item_name_in_text(item.name, s):
                    p1, p2 = m.group(1), m.group(2)
                    who = [p for p in [p1, p2] if p in people]
                    if who:
                        personal_each[idx] = who
                        assigned = True
                        break

                m = re.search(r'([A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+)+)\s+each\s+(?:had|ordered|got)\b', s, re.IGNORECASE)
                if m and _item_name_in_text(item.name, s):
                    who_text = m.group(1)
                    who = [p for p in people if p in who_text]
                    if who:
                        personal_each[idx] = who
                        assigned = True
                        break

                m = re.search(r'were\s+(.+?)\s+only\b', s, re.IGNORECASE)
                if m and _item_name_in_text(item.name, s):
                    who_text = m.group(1)
                    who = [p for p in people if p.lower() in who_text.lower()]
                    if who:
                        assignments[idx] = who
                        assigned = True
                        break

                shared_match = re.search(r'shared\s+(?:just\s+|by\s+|between\s+|among\s+)(.+)', s_lower)
                if shared_match and _item_name_in_text(item.name, s):
                    who_text = shared_match.group(1)
                    who = [p for p in people if p.lower() in who_text]
                    if who and len(who) < len(people):
                        assignments[idx] = who
                        assigned = True
                        break

                shared_match2 = re.search(r'(\w+(?:\s+and\s+\w+)+)\s+shared\b', s_lower)
                if shared_match2 and _item_name_in_text(item.name, s):
                    who_text = shared_match2.group(1)
                    who = [p for p in people if p.lower() in who_text]
                    if who and len(who) < len(people):
                        assignments[idx] = who
                        assigned = True
                        break

                possessive = re.search(r'\b([A-Z][a-z]+)[\'\u2019]s\b', s)
                if possessive and _item_name_in_text(item.name, s):
                    person = possessive.group(1)
                    if person in people:
                        personal[idx] = person
                        assigned = True
                        break

                had_pattern = re.search(r'\b([A-Z][a-z]+)\s+had\b', s)
                if had_pattern and _item_name_in_text(item.name, s):
                    person = had_pattern.group(1)
                    if person in people:
                        personal[idx] = person
                        assigned = True
                        break

            if not assigned:
                all_shared = any(
                    ('common to all' in s.lower() or 'everything else' in s.lower())
                    for s in sentences
                )
                if all_shared:
                    assignments[idx] = list(people)
                else:
                    assignments[idx] = list(people)
                    assumptions.append(f"'{item.name}' not clearly assigned — assumed shared by all")

        food_words_in_desc = re.findall(r'\b([a-z]{4,})\b', description.lower())
        bill_item_names = set()
        for item in items:
            for alias in _get_aliases(item.name):
                bill_item_names.add(alias.lower())

        people_names = set(p.lower() for p in people)
        desc_food_candidates = set()
        for word in food_words_in_desc:
            if word not in NON_PERSON_WORDS and word not in bill_item_names and word not in people_names and len(word) > 3:
                desc_food_candidates.add(word)

        if desc_food_candidates:
            flags.append(
                f"Description mentions food/drink items not found on the bill: {', '.join(sorted(desc_food_candidates)[:3])} — cannot verify these items"
            )

        return {
            "people": people,
            "assignments": assignments,
            "personal": personal,
            "personal_each": personal_each,
            "paid_by": paid_by,
            "assumptions": assumptions,
            "flags": flags,
        }

    def _extract_people(self, description: str) -> List[str]:
        dash_match = re.search(r'[\u2014\u2013—–]\s*(.+?)[\s]*[.;]', description)
        if dash_match:
            names_text = dash_match.group(1)
            found = [n.strip() for n in re.findall(r'([A-Z][a-z]+)', names_text)]
            if found:
                return list(dict.fromkeys(found))

        found_names = re.findall(r'\b([A-Z][a-z]+)\b', description)
        people = []
        seen: Set[str] = set()
        for name in found_names:
            if name.lower() not in NON_PERSON_WORDS and name not in seen:
                people.append(name)
                seen.add(name)
        return people

    def _extract_payer(self, description: str, people: List[str]) -> Optional[str]:
        patterns = [
            (r'([A-Z][a-z]+)\s+paid\b', 1),
            (r'paid\s+by\s+([A-Z][a-z]+)', 1),
            (r'([A-Z][a-z]+)\s+footed\b', 1),
        ]
        for pattern, group in patterns:
            m = re.search(pattern, description)
            if m:
                name = m.group(group)
                if name in people:
                    return name
        if re.search(r'\bI\s+paid\b', description):
            return people[0] if people else None
        return None
