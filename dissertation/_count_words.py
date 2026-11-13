import re
from pathlib import Path

text = Path(__file__).with_name("DISSERTATION_DRAFT.md").read_text(encoding="utf-8")
body = text.split("<!-- WORD_COUNT_START -->")[1].split("<!-- WORD_COUNT_END -->")[0]
abstract = text.split("## Abstract")[1].split("## Acknowledgements")[0]
pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9'+-]*")
print("chapter_words", len(pattern.findall(body)))
print("abstract_words", len(pattern.findall(abstract)))
print("combined", len(pattern.findall(body)) + len(pattern.findall(abstract)))
parts = re.split(r"\n# Chapter ", body)
for part in parts[1:]:
    title = part.split("\n", 1)[0]
    print(f"{len(pattern.findall(part)):5}  Chapter {title}")
