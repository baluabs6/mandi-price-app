import React from "react";
import { useTranslation } from "react-i18next";

const LANGS = [
  { code: "hi", label: "हिन्दी" },
  { code: "te", label: "తెలుగు" },
  { code: "en", label: "English" },
];

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();

  return (
    <div className="lang-switcher" role="group" aria-label="Language selector">
      {LANGS.map((l) => (
        <button
          key={l.code}
          className={i18n.language === l.code ? "lang-btn active" : "lang-btn"}
          onClick={() => i18n.changeLanguage(l.code)}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
