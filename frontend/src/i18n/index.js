import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const resources = {
  en: {
    translation: {
      title: "Mandi Bhav — Daily Crop Prices",
      subtitle: "Know today's real market price before you sell.",
      select_state: "State",
      select_district: "District",
      select_crop: "Crop",
      all: "All",
      crop: "Crop",
      market: "Market",
      district: "District",
      min_price: "Min Price",
      max_price: "Max Price",
      modal_price: "Modal Price",
      unit: "per quintal",
      date: "Date",
      loading: "Loading prices...",
      no_data: "No price data for this selection yet.",
      trend_7d: "7-day trend",
      source_note: "Prices sourced from Agmarknet / data.gov.in government data.",
      per_quintal: "per quintal",
      per_kg: "per kg",
      load_more: "Load more",
      showing_of: "Showing {{shown}} of {{total}}",
      ask_placeholder: "Ask about a crop price, e.g. \"onion price in Hyderabad\"",
      ask_button: "Ask",
      ask_thinking: "Checking prices...",
      ask_error: "Could not get an answer right now.",
      ask_mic: "Speak your question",
      ask_listening: "Listening...",
      ask_speak: "Read aloud",
      ask_stop: "Stop reading",
      ask_sources: "Based on {{count}} price records",
      ask_new_chat: "Start new chat",
      ask_followup_placeholder: "Ask a follow-up, e.g. \"and in Warangal?\"",
      anomaly_badge: "Unusual price",
    },
  },
  hi: {
    translation: {
      title: "मंडी भाव — दैनिक फसल मूल्य",
      subtitle: "बेचने से पहले आज का असली बाज़ार भाव जानें।",
      select_state: "राज्य",
      select_district: "जिला",
      select_crop: "फसल",
      all: "सभी",
      crop: "फसल",
      market: "मंडी",
      district: "जिला",
      min_price: "न्यूनतम मूल्य",
      max_price: "अधिकतम मूल्य",
      modal_price: "सामान्य मूल्य",
      unit: "प्रति क्विंटल",
      date: "तारीख",
      loading: "भाव लोड हो रहे हैं...",
      no_data: "इस चयन के लिए अभी कोई डेटा नहीं है।",
      trend_7d: "7-दिन का रुझान",
      source_note: "मूल्य Agmarknet / data.gov.in सरकारी डेटा से लिए गए हैं।",
      per_quintal: "प्रति क्विंटल",
      per_kg: "प्रति किलो",
      load_more: "और देखें",
      showing_of: "{{total}} में से {{shown}} दिखाए जा रहे हैं",
      ask_placeholder: "किसी फसल के भाव के बारे में पूछें, जैसे \"हैदराबाद में प्याज का भाव\"",
      ask_button: "पूछें",
      ask_thinking: "भाव जांचे जा रहे हैं...",
      ask_error: "अभी उत्तर नहीं मिल सका।",
      ask_mic: "बोलकर पूछें",
      ask_listening: "सुन रहा है...",
      ask_speak: "सुनें",
      ask_stop: "सुनना बंद करें",
      ask_sources: "{{count}} भाव रिकॉर्ड के आधार पर",
      ask_new_chat: "नई बातचीत शुरू करें",
      ask_followup_placeholder: "आगे पूछें, जैसे \"और वारंगल में?\"",
      anomaly_badge: "असामान्य भाव",
    },
  },
  te: {
    translation: {
      title: "మండి ధరలు — రోజువారీ పంట ధరలు",
      subtitle: "అమ్మే ముందు ఈరోజు నిజమైన మార్కెట్ ధర తెలుసుకోండి.",
      select_state: "రాష్ట్రం",
      select_district: "జిల్లా",
      select_crop: "పంట",
      all: "అన్నీ",
      crop: "పంట",
      market: "మార్కెట్",
      district: "జిల్లా",
      min_price: "కనీస ధర",
      max_price: "గరిష్ట ధర",
      modal_price: "సాధారణ ధర",
      unit: "క్వింటాలుకు",
      date: "తేదీ",
      loading: "ధరలు లోడ్ అవుతున్నాయి...",
      no_data: "ఈ ఎంపికకు ఇంకా డేటా లేదు.",
      trend_7d: "7-రోజుల ధోరణి",
      source_note: "ధరలు Agmarknet / data.gov.in ప్రభుత్వ డేటా నుండి తీసుకోబడ్డాయి.",
      per_quintal: "క్వింటాలుకు",
      per_kg: "కిలోకు",
      load_more: "మరిన్ని చూడండి",
      showing_of: "{{total}} లో {{shown}} చూపబడుతున్నాయి",
      ask_placeholder: "పంట ధర గురించి అడగండి, ఉదా. \"హైదరాబాద్‌లో ఉల్లిపాయ ధర\"",
      ask_button: "అడగండి",
      ask_thinking: "ధరలు తనిఖీ చేస్తోంది...",
      ask_error: "ఇప్పుడు సమాధానం పొందడం సాధ్యం కాలేదు.",
      ask_mic: "మాట్లాడి అడగండి",
      ask_listening: "వింటోంది...",
      ask_speak: "వినండి",
      ask_stop: "చదవడం ఆపండి",
      ask_sources: "{{count}} ధర రికార్డుల ఆధారంగా",
      ask_new_chat: "కొత్త చాట్ ప్రారంభించండి",
      ask_followup_placeholder: "తదుపరి ప్రశ్న అడగండి, ఉదా. \"వరంగల్‌లో?\"",
      anomaly_badge: "అసాధారణ ధర",
    },
  },
};

const LANG_STORAGE_KEY = "mandi-bhav-lang";

function getInitialLanguage() {
  try {
    const saved = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (saved && resources[saved]) return saved;
  } catch (e) {
    // localStorage can throw in private-browsing/sandboxed contexts — fall
    // through to the default rather than crashing app boot.
  }
  return "hi"; // default to Hindi — target users are farmers, not urban English readers
}

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

// Persist the user's language choice across visits instead of resetting to
// Hindi on every reload.
i18n.on("languageChanged", (lng) => {
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lng);
  } catch (e) {
    // ignore storage errors (e.g. private browsing)
  }
});

export default i18n;
