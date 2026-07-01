/**
 * §23.7 — Interview Question Panel.
 *
 * Fetches targeted interview questions for a shortlisted candidate,
 * probing their uncertain skills and validating strong claims.
 */
import { useEffect, useState } from "react";
import { fetchInterviewQuestions } from "../../lib/api";
import { useAppDispatch } from "../../store/hooks";
import { setInterviewQuestions, setError } from "../../store/slices/enterpriseSlice";
import type { InterviewQuestionsResponse, InterviewQuestion } from "@polyhire/shared-types";

interface Props {
  candidateId: string;
  roleTitle: string;
  claimedSkills: string[];
  uncertainSkills?: string[];
}

export function InterviewQuestionPanel({
  candidateId,
  roleTitle,
  claimedSkills,
  uncertainSkills = [],
}: Props) {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchInterviewQuestions({
      candidate_id: candidateId,
      role_title: roleTitle,
      claimed_skills: claimedSkills,
      uncertain_skills: uncertainSkills,
    })
      .then((res) => {
        if (cancelled) return;
        const data = res as InterviewQuestionsResponse;
        setQuestions(data.questions);
        dispatch(setInterviewQuestions({ candidateId, questions: data.questions }));
      })
      .catch((err) => {
        dispatch(setError(err instanceof Error ? err.message : "Question gen failed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId, roleTitle, claimedSkills, uncertainSkills, dispatch]);

  return (
    <div className="panel space-y-3 p-4">
      <h3 className="font-display text-sm text-starlight">Suggested Interview Questions</h3>
      {loading ? (
        <p className="text-xs text-primary/40">Generating questions...</p>
      ) : questions.length === 0 ? (
        <p className="text-xs text-primary/40">No questions available.</p>
      ) : (
        questions.map((q, i) => (
          <div key={i} className="border-l-2 border-gridline pl-3">
            <p className="text-sm">{q.question}</p>
            <p className="mt-1 text-xs text-primary/50">Probes: {q.probes_for}</p>
            {q.what_a_strong_answer_sounds_like && (
              <p className="mt-0.5 text-xs text-trust/70">
                Strong answer: {q.what_a_strong_answer_sounds_like}
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
}
