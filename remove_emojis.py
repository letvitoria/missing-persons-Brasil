import re

file_path = 'web_scraping.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove emojis e caracteres especiais problemáticos mantendo acentos
content_limpo = ''.join(
    c for c in content if ord(c) < 127 or (128 <= ord(c) <= 255 and c not in '✔️✅❌📊🔎🛑🕵🕵️📄ℹ⚠🚀🆕📸️')
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content_limpo)

print('Emojis removidos com sucesso!')
