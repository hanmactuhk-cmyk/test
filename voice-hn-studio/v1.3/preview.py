#!/usr/bin/env python3
"""Voice Hn Studio 1.3: emotional voice preview text + version bump."""
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ios")
speech = root / "HNVieNeuIOS/Sources/SpeechStudio.swift"
ui = root / "HNVieNeuIOS/Sources/HNVieNeuApp.swift"
plist = root / "HNVieNeuIOS/Support/Info.plist"

old = "Chào bạn đến với ứng dụng tạo giọng đọc Voice Hát nờ studio. Tool được tạo bởi Hoài nguyễn. Liên hệ: Zalo 0965043000 để được trợ giúp."
new = "Xin chào! Rất vui được chào đón bạn đến với Voice Hát Nờ Studio – ứng dụng tạo giọng đọc AI tự nhiên, sống động và đầy cảm xúc! Ứng dụng được phát triển bởi Hoài Nguyễn, với mong muốn mang đến cho bạn những trải nghiệm giọng đọc tuyệt vời nhất. Nếu cần hỗ trợ trong quá trình sử dụng, hãy liên hệ qua Zalo: 0965 043 000. Voice Hát Nờ Studio – Nơi mỗi câu chữ đều trở nên sống động!"
s = speech.read_text(encoding="utf-8")
assert s.count(old) == 1, "Expected original preview text exactly once"
s = s.replace(old, new)
assert s.count('preview-v2|') == 1
s = s.replace('preview-v2|', 'preview-v3|')
speech.write_text(s, encoding="utf-8")

u = ui.read_text(encoding="utf-8")
assert u.count('Voice Hn Studio · Phiên bản 1.2') == 1
assert 'ImportedVoiceAudio.copyIntoSandbox' in s
assert 'Đang tải và kiểm tra tệp âm thanh' in u
ui.write_text(u.replace('Voice Hn Studio · Phiên bản 1.2', 'Voice Hn Studio · Phiên bản 1.3'), encoding="utf-8")

p = plist.read_text(encoding="utf-8")
assert p.count('<string>1.2.0</string>') == 1
assert p.count('<string>4</string>') == 1
p = p.replace('<string>1.2.0</string>', '<string>1.3.0</string>')
p = p.replace('<string>4</string>', '<string>5</string>')
plist.write_text(p, encoding="utf-8")
print("PASS: Voice Hn Studio 1.3 expressive preview and scoped audio import retained")
