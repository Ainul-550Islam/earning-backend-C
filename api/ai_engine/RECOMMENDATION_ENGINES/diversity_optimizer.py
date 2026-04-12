"""
api/ai_engine/RECOMMENDATION_ENGINES/diversity_optimizer.py
============================================================
Diversity Optimizer — recommendation diversity ensure করো।
Echo chamber avoid, exploration encourage করো।
Maximal Marginal Relevance (MMR) algorithm।
"""
import logging
from typing import List, Dict
from ..utils import cosine_similarity
logger = logging.getLogger(__name__)

class DiversityOptimizer:
    """MMR-based diversity optimization for recommendations।"""

    def optimize(self, items: List[Dict], diversity_factor: float = 0.30,
                 count: int = None) -> List[Dict]:
        if not items: return []
        count  = count or len(items)
        if diversity_factor <= 0: return items[:count]
        selected   = [items[0]]
        candidates = items[1:]
        while candidates and len(selected) < count:
            best_score = -999
            best_item  = None
            for item in candidates:
                relevance = item.get('score', 0.5)
                max_sim   = self._max_similarity_to_selected(item, selected)
                mmr = (1 - diversity_factor) * relevance - diversity_factor * max_sim
                if mmr > best_score:
                    best_score = mmr
                    best_item  = item
            if best_item:
                selected.append({**best_item, 'diversity_score': round(best_score, 4)})
                candidates.remove(best_item)
            else:
                break
        return selected

    def _max_similarity_to_selected(self, item: Dict, selected: List[Dict]) -> float:
        cat    = item.get('category', '')
        engine = item.get('engine', '')
        max_sim = 0.0
        for sel in selected:
            sim = 0.0
            if cat and cat == sel.get('category', ''): sim += 0.6
            if engine and engine == sel.get('engine', ''): sim += 0.3
            max_sim = max(max_sim, sim)
        return max_sim

    def ensure_category_diversity(self, items: List[Dict],
                                   max_per_category: int = 3) -> List[Dict]:
        cat_counts: Dict[str, int] = {}
        result = []
        for item in items:
            cat = item.get('category', 'unknown')
            if cat_counts.get(cat, 0) < max_per_category:
                result.append(item)
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        return result

    def ensure_difficulty_mix(self, items: List[Dict],
                               easy: int = 4, medium: int = 4, hard: int = 2) -> List[Dict]:
        buckets = {'easy': [], 'medium': [], 'hard': []}
        misc    = []
        for item in items:
            diff = item.get('difficulty', 'medium')
            if diff in buckets:
                buckets[diff].append(item)
            else:
                misc.append(item)
        result  = buckets['easy'][:easy] + buckets['medium'][:medium] + buckets['hard'][:hard]
        result += misc[:max(0, (easy+medium+hard) - len(result))]
        return sorted(result, key=lambda x: x.get('score', 0), reverse=True)

    def novelty_boost(self, items: List[Dict], user_history: List[str],
                       boost_factor: float = 1.30) -> List[Dict]:
        seen = set(user_history)
        result = []
        for item in items:
            iid = item.get('item_id', '')
            if iid and iid not in seen:
                result.append({**item, 'score': round(item.get('score', 0.5) * boost_factor, 4), 'is_novel': True})
            else:
                result.append({**item, 'is_novel': False})
        return sorted(result, key=lambda x: x.get('score', 0), reverse=True)

    def compute_diversity_score(self, items: List[Dict]) -> float:
        if len(items) < 2: return 1.0
        cats = [item.get('category', '') for item in items if item.get('category')]
        unique_cats = len(set(cats))
        cat_diversity = unique_cats / max(len(cats), 1)
        engines = [item.get('engine', '') for item in items]
        unique_engines = len(set(engines))
        engine_diversity = unique_engines / max(len(engines), 1)
        return round((cat_diversity + engine_diversity) / 2, 4)
