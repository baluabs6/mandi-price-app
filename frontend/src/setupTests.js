import "@testing-library/jest-dom";
import i18n from "./i18n";

// Tests assert against English copy for stability; force English
// regardless of the app's default (Hindi) or any persisted preference.
beforeAll(() => {
  i18n.changeLanguage("en");
});
