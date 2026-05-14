"""Answer Service for CRUD operations on question answers."""

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AnswerType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.answer import Answer
from app.models.question import Question

logger = logging.getLogger(__name__)


class AnswerService:
    """Service for answer CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize answer service.

        Args:
            session: Database session
        """
        self.session = session

    async def create_answer(
        self,
        question_id: int,
        answer_text: str,
        answer_type: str = AnswerType.INCORRECT.value,
        explanation: str | None = None,
        is_common_misconception: bool = False,
        display_order: int = 0,
    ) -> Answer:
        """Create a new answer for a question.

        Args:
            question_id: Question ID
            answer_text: Text of the answer
            answer_type: Type of answer (correct/incorrect/partial)
            explanation: Optional explanation
            is_common_misconception: Whether this is a common mistake
            display_order: Display order among sibling answers

        Returns:
            Created answer

        Raises:
            NotFoundError: If question not found
            ValidationError: If answer_type is invalid or answer_text is empty
            ConflictError: If adding a second correct answer to the same question
        """
        result = await self.session.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()
        if not question:
            raise NotFoundError(f"Question not found: {question_id}")

        valid_types = {t.value for t in AnswerType}
        if answer_type not in valid_types:
            raise ValidationError(
                f"Invalid answer_type: {answer_type}",
                details={"valid_types": list(valid_types)},
            )

        if not answer_text.strip():
            raise ValidationError("answer_text cannot be empty")

        # Enforce single correct answer per question
        if answer_type == AnswerType.CORRECT.value and question.correct_answer:
            raise ConflictError(
                f"Question {question_id} already has a correct answer "
                f"(id={question.correct_answer.id}). Update or delete it first.",
                details={"existing_correct_id": question.correct_answer.id},
            )

        answer = Answer(
            question_id=question_id,
            answer_text=answer_text.strip(),
            answer_type=answer_type,
            explanation=explanation,
            is_common_misconception=is_common_misconception,
            display_order=display_order,
        )

        self.session.add(answer)
        await self.session.commit()
        await self.session.refresh(answer)

        logger.info(
            f"Created answer {answer.id} for question {question_id} (type={answer_type})"
        )
        return answer

    async def get_answer(self, answer_id: int) -> Answer:
        """Get answer by ID.

        Args:
            answer_id: Answer ID

        Returns:
            Answer instance

        Raises:
            NotFoundError: If answer not found
        """
        result = await self.session.execute(
            select(Answer).where(Answer.id == answer_id)
        )
        answer = result.scalar_one_or_none()

        if not answer:
            raise NotFoundError(f"Answer not found: {answer_id}")

        return answer

    async def list_answers(self, question_id: int) -> Sequence[Answer]:
        """List all answers for a question ordered by display_order.

        Args:
            question_id: Question ID

        Returns:
            List of answers ordered by display_order, then id
        """
        result = await self.session.execute(
            select(Answer)
            .where(Answer.question_id == question_id)
            .order_by(Answer.display_order.asc(), Answer.id.asc())
        )
        return result.scalars().all()

    async def update_answer(
        self,
        answer_id: int,
        answer_text: str | None = None,
        answer_type: str | None = None,
        explanation: str | None = None,
        is_common_misconception: bool | None = None,
        display_order: int | None = None,
    ) -> Answer:
        """Update answer fields.

        Args:
            answer_id: Answer ID
            answer_text: New answer text
            answer_type: New answer type (correct/incorrect/partial)
            explanation: New explanation
            is_common_misconception: Whether this is a common mistake
            display_order: New display order

        Returns:
            Updated answer

        Raises:
            NotFoundError: If answer not found
            ValidationError: If parameters are invalid
            ConflictError: If promoting to correct when another correct exists
        """
        answer = await self.get_answer(answer_id)

        if answer_text is not None:
            if not answer_text.strip():
                raise ValidationError("answer_text cannot be empty")
            answer.answer_text = answer_text.strip()

        if answer_type is not None:
            valid_types = {t.value for t in AnswerType}
            if answer_type not in valid_types:
                raise ValidationError(
                    f"Invalid answer_type: {answer_type}",
                    details={"valid_types": list(valid_types)},
                )

            # Guard: promoting to correct when another correct answer already exists
            if (
                answer_type == AnswerType.CORRECT.value
                and answer.answer_type != AnswerType.CORRECT.value
            ):
                q_result = await self.session.execute(
                    select(Question).where(Question.id == answer.question_id)
                )
                question = q_result.scalar_one_or_none()
                if (
                    question
                    and question.correct_answer
                    and question.correct_answer.id != answer_id
                ):
                    raise ConflictError(
                        f"Question already has a correct answer "
                        f"(id={question.correct_answer.id}). Update or delete it first.",
                        details={"existing_correct_id": question.correct_answer.id},
                    )

            answer.answer_type = answer_type

        if explanation is not None:
            answer.explanation = explanation

        if is_common_misconception is not None:
            answer.is_common_misconception = is_common_misconception

        if display_order is not None:
            answer.display_order = display_order

        await self.session.commit()
        await self.session.refresh(answer)

        logger.info(f"Updated answer {answer_id}")
        return answer

    async def delete_answer(self, answer_id: int) -> bool:
        """Delete an answer.

        Args:
            answer_id: Answer ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If answer not found
        """
        answer = await self.get_answer(answer_id)

        await self.session.delete(answer)
        await self.session.commit()

        logger.info(f"Deleted answer {answer_id}")
        return True

    async def reorder_answers(
        self,
        question_id: int,
        ordered_ids: list[int],
    ) -> Sequence[Answer]:
        """Reorder answers for a question by reassigning display_order.

        Args:
            question_id: Question ID
            ordered_ids: Answer IDs in the desired display order

        Returns:
            Updated list of answers

        Raises:
            ValidationError: If ordered_ids don't exactly match the question's answers
        """
        answers = list(await self.list_answers(question_id))
        existing_ids = {a.id for a in answers}

        if set(ordered_ids) != existing_ids:
            raise ValidationError(
                "ordered_ids must contain exactly the question's answer IDs",
                details={
                    "expected": sorted(existing_ids),
                    "received": sorted(ordered_ids),
                },
            )

        answer_map = {a.id: a for a in answers}
        for order, answer_id in enumerate(ordered_ids):
            answer_map[answer_id].display_order = order

        await self.session.commit()
        return await self.list_answers(question_id)
