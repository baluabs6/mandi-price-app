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
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: "hi", // default to Hindi — target users are farmers, not urban English readers
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
