import logging

logger = logging.getLogger('smartlink.targeting.evaluator')


class TargetingRuleEvaluator:
    """
    Combine all targeting sub-rule results with AND/OR logic.
    AND: all rules must match (default)
    OR:  any rule must match
    """

    def evaluate(self, match_results: dict, logic: str = 'AND') -> bool:
        """
        Evaluate combined match result from all targeting services.

        Args:
            match_results: {'geo': True, 'device': False, 'time': True, ...}
            logic: 'AND' or 'OR'

        Returns:
            bool — True if traffic should be allowed through
        """
        if not match_results:
            # No targeting rules defined → allow all traffic
            return True

        results = list(match_results.values())

        if logic == 'AND':
            result = all(results)
        elif logic == 'OR':
            result = any(results)
        else:
            logger.warning(f"Unknown targeting logic '{logic}', defaulting to AND")
            result = all(results)

        logger.debug(
            f"Targeting evaluation [{logic}]: {match_results} → {result}"
        )
        return result

    def explain(self, match_results: dict, logic: str = 'AND') -> dict:
        """
        Return a detailed explanation of the targeting evaluation.
        Useful for debugging and admin tooling.
        """
        passed = [k for k, v in match_results.items() if v]
        failed = [k for k, v in match_results.items() if not v]
        final = self.evaluate(match_results, logic)

        return {
            'logic': logic,
            'final_result': final,
            'passed_rules': passed,
            'failed_rules': failed,
            'total_rules': len(match_results),
            'details': match_results,
        }
