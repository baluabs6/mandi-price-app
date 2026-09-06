import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export default function AskAssistant() {
  const { t, i18n } = useTranslation();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setAnswer(null);

    api
      .ask(trimmed, i18n.language)
      .then(setAnswer)
      .catch(() => setError(t("ask_error")))
      .finally(() => setLoading(false));
  };

  return (
    <div className="ask-assistant">
      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("ask_placeholder")}
          maxLength={500}
          aria-label={t("ask_placeholder")}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {t("ask_button")}
        </button>
      </form>

      {loading && <p className="status-msg ask-status">{t("ask_thinking")}</p>}
      {error && <p className="error-msg">{error}</p>}

      {answer && (
        <div className="ask-answer">
          <p>{answer.answer}</p>
          {!answer.assistant_enabled && (
            <p className="ask-degraded-note">
              (AI assistant not fully configured on this deployment — showing the latest raw record instead.)
            </p>
          )}
        </div>
      )}
    </div>
  );
}
