import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import en from "./locales/en.json"
import ur from "./locales/ur.json"
import zh from "./locales/zh.json"

export type Language = "en" | "ur" | "zh"

export const LANGUAGES: { code: Language; label: string; nativeLabel: string; dir: "ltr" | "rtl" }[] = [
  { code: "en", label: "English",  nativeLabel: "English", dir: "ltr" },
  { code: "ur", label: "Urdu",     nativeLabel: "اردو",    dir: "rtl" },
  { code: "zh", label: "Chinese",  nativeLabel: "中文",     dir: "ltr" },
]

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ur: { translation: ur },
    zh: { translation: zh },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
})

export default i18n
