import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { setJdLanguage } from "../../store/slices/uiSlice";

export function LanguageToggle() {
  const dispatch = useAppDispatch();
  const language = useAppSelector((s) => s.ui.jdLanguage);
  const capabilities = useAppSelector((s) => s.pipeline.capabilities);
  const canTranslate = capabilities?.hindi_translation ?? false;

  if (!canTranslate) return null;

  return (
    <button
      type="button"
      onClick={() => dispatch(setJdLanguage(language === "en" ? "hi" : "en"))}
      className={`badge cursor-pointer ${language === "hi" ? "badge-trust" : "badge-neutral"}`}
    >
      {language === "en" ? "EN" : "हिंदी"}
    </button>
  );
}
