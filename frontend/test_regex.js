const text = "Article 67 creates an advisory forum, outlines its balanced membership, and specifies that the Commission appoints its members.\n\n[Chunk 2, Lines 1-3]";

const regex = /\[\s*Chunk\s+(\d+),\s*Lines?\s+(\d+)(?:\s*-\s*(\d+))?\s*\]|\[\s*Page\s+(\d+),\s*BBOX:\s*([\d\.,\s]+)\s*\]/gi;
const parts = [];
let lastIdx = 0;

let match;
while ((match = regex.exec(text)) !== null) {
  parts.push(text.substring(lastIdx, match.index));
  
  if (match[1]) {
    const chunkIdx = parseInt(match[1]) - 1;
    const lineStart = parseInt(match[2]);
    const lineEnd = match[3] ? parseInt(match[3]) : lineStart;
    
    parts.push({
      type: 'BUTTON',
      chunkIdx,
      lineStart,
      lineEnd
    });
  } else if (match[4]) {
    const page = parseInt(match[4]);
    parts.push({
      type: 'LEGACY_BUTTON',
      page
    });
  }
  
  lastIdx = regex.lastIndex;
}
parts.push(text.substring(lastIdx));

console.log(JSON.stringify(parts, null, 2));
