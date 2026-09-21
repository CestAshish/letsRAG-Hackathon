# Extraction Report

## Issues Encountered
- The EU AI Act PDF was actually pretty clean compared to most PDFs.

## Actions Taken
- Wrote a simple `clean` function to split the text by newlines and then join them back with spaces. 
- Used a regex (`re.sub`) to replace multiple spaces with a single space to make the text cleaner for the AI.
