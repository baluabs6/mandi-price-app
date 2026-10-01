import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

// BCP-47 tags for the browser speech APIs, keyed by the app's UI language.
const SPEECH_LANG = { en: "en-IN", hi: "hi-IN", te: "te-IN" };
const MAX_HISTORY = 6;

function getSpeechRecognition() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export default function AskAssistant() {
  const { t, i18n } = useTranslation();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState([]); // [{ question, answer }]
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [listening, setListening] = useState(false);
  const [speakingIdx, setSpeakingIdx] = useState(null);
  const recognitionRef = useRef(null);

  const SpeechRecognition = getSpeechRecognition();
  const speechOut = canSpeak();

  // Stop any microphone / speech output when the component goes away.
  useEffect(
    () => () => {
      if (recognitionRef.current) recognitionRef.current.abort();
      if (canSpeak()) window.speechSynthesis.cancel();
    },
    []
  );

  // Recent turns as chat history for the backend, so follow-ups work.
  const buildHistory = () =>
    turns
      .flatMap((turn) => [
        { role: "user", content: turn.question },
        { role: "assistant", content: turn.answer.answer },
      ])
      .slice(-MAX_HISTORY);

  const ask = (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);

    api
      .ask(trimmed, i18n.language, buildHistory())
      .then((answer) => {
        setTurns((prev) => [...prev, { question: trimmed, answer }]);
        setQuestion("");
      })
      .catch(() => setError(t("ask_error")))
      .finally(() => setLoading(false));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(question);
  };

  const startListening = () => {
    if (!SpeechRecognition || listening) return;
    const recognition = new SpeechRecognition();
    recognition.lang = SPEECH_LANG[i18n.language] || "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript || "";
      setQuestion(transcript.slice(0, 500));
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  };

  const toggleSpeak = (idx, text) => {
    if (!speechOut) return;
    if (speakingIdx === idx) {
      window.speechSynthesis.cancel();
      setSpeakingIdx(null);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = SPEECH_LANG[i18n.language] || "en-IN";
    utterance.onend = () => setSpeakingIdx(null);
    utterance.onerror = () => setSpeakingIdx(null);
    setSpeakingIdx(idx);
    window.speechSynthesis.speak(utterance);
  };

  const resetChat = () => {
    if (speechOut) window.speechSynthesis.cancel();
    setSpeakingIdx(null);
    setTurns([]);
    setError(null);
    setQuestion("");
  };

  const placeholder = turns.length ? t("ask_followup_placeholder") : t("ask_placeholder");

  return (
    <div className="ask-assistant">
      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder}
          maxLength={500}
          aria-label={placeholder}
        />
        {SpeechRecognition && (
          <button
            type="button"
            className={`ask-icon-btn${listening ? " is-active" : ""}`}
            onClick={startListening}
            disabled={loading || listening}
            aria-label={t("ask_mic")}
            title={listening ? t("ask_listening") : t("ask_mic")}
          >
            🎤
          </button>
        )}
        <button type="submit" disabled={loading || !question.trim()}>
          {t("ask_button")}
        </button>
      </form>

      {listening && <p className="status-msg ask-status">{t("ask_listening")}</p>}

      {turns.map((turn, idx) => (
        <div className="ask-turn" key={idx}>
          <p className="ask-question">{turn.question}</p>
          <div className="ask-answer">
            <p>{turn.answer.answer}</p>
            {speechOut && (
              <button
                type="button"
                className="ask-speak-btn"
                onClick={() => toggleSpeak(idx, turn.answer.answer)}
              >
                {speakingIdx === idx ? `⏹ ${t("ask_stop")}` : `🔊 ${t("ask_speak")}`}
              </button>
            )}
            {!turn.answer.assistant_enabled && (
              <p className="ask-degraded-note">
                (AI assistant not fully configured on this deployment — showing the latest raw record instead.)
              </p>
            )}
            {Array.isArray(turn.answer.sources) && turn.answer.sources.length > 0 && (
              <details className="ask-sources">
                <summary>{t("ask_sources", { count: turn.answer.sources.length })}</summary>
                <ul>
                  {turn.answer.sources.map((s, i) => (
                    <li key={i}>
                      {s.crop} · {s.market}, {s.district} — Rs {s.modal_price}/quintal ({s.date})
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
      ))}

      {loading && <p className="status-msg ask-status">{t("ask_thinking")}</p>}
      {error && <p className="error-msg">{error}</p>}

      {turns.length > 0 && (
        <button type="button" className="ask-reset-btn" onClick={resetChat}>
          {t("ask_new_chat")}
        </button>
      )}
    </div>
  );
}
