"""Evidence-backed feedback generator grounded strictly in evaluation metrics."""

from typing import Any, Dict, List


class FeedbackGenerator:
    """Generates strengths, missing concepts, and actionable improvement suggestions."""

    @classmethod
    def generate(
        cls,
        category: str,
        overall_score: float,
        relevance_res: Dict[str, Any],
        keyword_res: Dict[str, Any],
        rubric_res: Dict[str, Any],
        completeness_res: Dict[str, Any],
        star_res: Dict[str, Any],
        structure_score: float,
    ) -> Dict[str, Any]:
        """Produce structured feedback strictly supported by observed evaluation signals."""
        strengths: List[str] = []
        suggestions: List[str] = []
        missing_concepts: List[str] = list(keyword_res.get("missing_keywords", []))

        matched_keywords = keyword_res.get("matched_keywords", [])
        if matched_keywords:
            shown = ", ".join(matched_keywords[:5])
            strengths.append(f"Addressed relevant concepts: {shown}.")

        if relevance_res.get("score", 0.0) >= 65.0:
            strengths.append("Response stays focused on the core question prompt.")
        elif relevance_res.get("is_off_topic"):
            suggestions.append("Address the specific question prompt directly with concrete domain details.")

        if rubric_res.get("score", 0.0) >= 65.0:
            strengths.append("Covered key evaluation criteria from the answer rubric.")
        elif rubric_res.get("missing_points"):
            first_missing = rubric_res["missing_points"][0]
            suggestions.append(f"Expand on rubric expectations such as: {first_missing}.")

        if completeness_res.get("has_reasoning_or_examples"):
            strengths.append("Included reasoning or concrete examples to support claims.")
        else:
            suggestions.append("Support your points with concrete examples, trade-offs, or clear reasoning.")

        if completeness_res.get("needs_more_detail"):
            suggestions.append(
                f"Provide a fuller explanation (current response is {completeness_res.get('word_count', 0)} words)."
            )

        if missing_concepts:
            shown_missing = ", ".join(missing_concepts[:5])
            suggestions.append(f"Incorporate missing expected concepts where relevant: {shown_missing}.")

        # Category-specific STAR feedback only when applicable
        if star_res.get("applicable"):
            components = star_res.get("components") or {}
            present_parts = [k.capitalize() for k, v in components.items() if v]
            missing_parts = [m.capitalize() for m in star_res.get("missing_components", [])]
            if len(present_parts) >= 3:
                strengths.append(f"Demonstrated STAR structure ({', '.join(present_parts)}).")
            if missing_parts:
                suggestions.append(
                    f"Strengthen behavioral STAR structure by adding: {', '.join(missing_parts)}."
                )
        elif structure_score >= 70.0:
            strengths.append("Organized the response clearly across multiple structured points.")

        if not strengths:
            strengths.append("Provided an initial response that can be expanded with deeper detail.")
        if not suggestions:
            suggestions.append("Strong coverage overall; consider quantifying impact or edge-case trade-offs.")

        cat_label = (category or "general").lower()
        summary = (
            f"Evaluated {cat_label} response with an overall heuristic score of {overall_score:.1f}/100 "
            f"(relevance {relevance_res['score']:.1f}, keywords {keyword_res['score']:.1f}, "
            f"rubric {rubric_res['score']:.1f}, completeness {completeness_res['score']:.1f})."
        )

        return {
            "strengths": strengths,
            "missing_concepts": missing_concepts,
            "improvement_suggestions": suggestions,
            "summary": summary,
        }
