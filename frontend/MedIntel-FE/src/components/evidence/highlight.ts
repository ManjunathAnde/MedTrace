// Locate a claim's quote inside its passage the way the verifier's L1 check
// does: case-insensitive, any whitespace between words, straight or curly
// quotes, any dash. Returns [start, end) in the passage, or null.

const CHAR_CLASSES: Record<string, string> = {
  "'": "['‘’‚‛]", "‘": "['‘’‚‛]", "’": "['‘’‚‛]",
  '"': '["“”„‟]', "“": '["“”„‟]', "”": '["“”„‟]',
  "-": "[-–—]", "–": "[-–—]", "—": "[-–—]",
};

function wordPattern(word: string) {
  return Array.from(word)
    .map((ch) => CHAR_CLASSES[ch] ?? ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("");
}

export function findQuote(passage: string, quote: string): [number, number] | null {
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return null;
  const match = new RegExp(words.map(wordPattern).join("\\s+"), "i").exec(passage);
  return match ? [match.index, match.index + match[0].length] : null;
}
