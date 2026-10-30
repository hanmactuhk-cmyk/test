#!/usr/bin/env python3
"""Voice Hn Studio v1.2: import scoped/iCloud voice references locally and safely.
Apply only after the v1.1 source patch. Idempotent: rejects mismatched sources.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('ios')
swift = root / 'HNVieNeuIOS/Sources/HNVieNeuApp.swift'
studio = root / 'HNVieNeuIOS/Sources/SpeechStudio.swift'
plist = root / 'HNVieNeuIOS/Support/Info.plist'
ui = swift.read_text()
speech = studio.read_text()


def replace_once(text, old, new, description):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{description}: expected one exact anchor, found {n}')
    return text.replace(old, new, 1)

ui = replace_once(ui, 'import UniformTypeIdentifiers\n', 'import UniformTypeIdentifiers\nimport AVFoundation\n', 'add AVFoundation import')
ui = replace_once(ui, 'allowedContentTypes: [.audio]) { result in',
                  'allowedContentTypes: [.audio, UTType(filenameExtension: "mp3") ?? .audio, UTType(filenameExtension: "wav") ?? .audio, UTType(filenameExtension: "m4a") ?? .audio]) { result in', 'audio picker')
speech = replace_once(speech, '    @Published var isRecording = false\n',
                  '    @Published var isRecording = false\n    @Published var importing = false\n', 'importing flag')
speech = replace_once(speech, '    func importAudio(_ url: URL) { fileURL = url; fileName = url.lastPathComponent; errorText = nil }', '''    func importAudio(_ url: URL) {
        guard !busy && !isRecording && !importing else {
            errorText = "Đang thực hiện tác vụ khác. Vui lòng chọn lại sau khi hoàn thành."
            return
        }
        // URLs provided by Files are often security scoped and can represent iCloud
        // placeholders. Copy the actual bytes into our app sandbox BEFORE enrollment.
        importing = true
        fileURL = nil
        fileName = ""
        errorText = nil
        status = "Đang tải tệp âm thanh từ Tệp / iCloud…"
        Task.detached(priority: .userInitiated) { [weak self] in
            let outcome: Result<URL, Error>
            do { outcome = .success(try ImportedVoiceAudio.copyIntoSandbox(url)) }
            catch { outcome = .failure(error) }
            await MainActor.run {
                guard let self else { return }
                self.importing = false
                switch outcome {
                case .success(let localURL):
                    self.fileURL = localURL
                    self.fileName = url.lastPathComponent
                    self.status = "Đã nhập giọng mẫu: \\(url.lastPathComponent)"
                    self.errorText = nil
                case .failure(let error):
                    self.fileURL = nil
                    self.fileName = ""
                    self.status = ""
                    self.errorText = "Không nhập được tệp: \\(error.localizedDescription). Hãy mở Tệp, tải tệp từ iCloud về iPhone rồi chọn lại."
                }
            }
        }
    }''', 'secure sandbox importer')
speech = replace_once(speech, '        guard !busy, !isRecording else { return }',
                  '        guard !busy, !isRecording, !importing else { return }', 'clone create guard')
ui = replace_once(ui, '                    .disabled(clone.busy || clone.isRecording)\n',
                  '                    .disabled(clone.busy || clone.isRecording || clone.importing)\n', 'clone create disabled')
ui = replace_once(ui, '''                    }
                }.padding(16).glass()

                VStack(alignment: .leading, spacing: 12) {
                    numbered(2, "Đặt tên giọng"''', '''                    }
                    if clone.importing {
                        HStack(spacing: 9) {
                            ProgressView().tint(Theme.cyan)
                            Text("Đang tải và kiểm tra tệp âm thanh…")
                                .font(.caption).foregroundStyle(Theme.muted)
                        }.accessibilityLabel("Đang tải tệp giọng mẫu")
                    } else if !clone.fileName.isEmpty {
                        Label("Đã chọn: \\(clone.fileName)", systemImage: "checkmark.circle.fill")
                            .font(.caption).foregroundStyle(Theme.cyan)
                            .lineLimit(2)
                    }
                }.padding(16).glass()

                VStack(alignment: .leading, spacing: 12) {
                    numbered(2, "Đặt tên giọng"''', 'visible audio import progress')
ui = replace_once(ui, '                    .disabled(clone.busy || clone.isRecording || studio.busy || studio.previewBusyID != nil)',
                  '                    .disabled(clone.busy || clone.isRecording || clone.importing || studio.busy || studio.previewBusyID != nil)', 'cleanup disabled during import')
ui = replace_once(ui, 'Voice Hn Studio · Phiên bản 1.1', 'Voice Hn Studio · Phiên bản 1.2', 'UI version')

ui += '''

/// Copy a Files/iCloud/third-party document into a private persistent location.
/// The security-scope token and file coordinator are retained for the full copy,
/// including when iCloud File Provider must download the source first.
enum ImportedVoiceAudio {
    static func copyIntoSandbox(_ source: URL) throws -> URL {
        let fm = FileManager.default
        let ext = source.pathExtension.lowercased()
        guard ["mp3", "wav", "m4a", "aac", "aif", "aiff", "caf"].contains(ext) else {
            throw TTSError.invalidVoice("Hỗ trợ MP3, WAV, M4A, AAC, AIFF hoặc CAF. Hãy chuyển định dạng tệp này trước khi chọn")
        }
        let outputFolder = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ImportedVoiceSamples", isDirectory: true)
        try fm.createDirectory(at: outputFolder, withIntermediateDirectories: true)
        let didAccess = source.startAccessingSecurityScopedResource()
        defer { if didAccess { source.stopAccessingSecurityScopedResource() } }

        var coordinatedError: NSError?
        var copyError: Error?
        var target: URL?
        NSFileCoordinator(filePresenter: nil).coordinate(readingItemAt: source, options: [], error: &coordinatedError) { readableURL in
            do {
                let attributes = try fm.attributesOfItem(atPath: readableURL.path)
                let size = (attributes[.size] as? NSNumber)?.int64Value ?? 0
                guard size > 0 else { throw TTSError.invalidVoice("Tệp rỗng hoặc chưa tải về từ iCloud") }
                guard size <= 80 * 1_024 * 1_024 else { throw TTSError.invalidVoice("Tệp lớn hơn 80 MB. Hãy cắt đoạn giọng mẫu khoảng 5–15 giây") }
                let local = outputFolder.appendingPathComponent("voice-\\(UUID().uuidString).\\(ext)")
                try fm.copyItem(at: readableURL, to: local)
                do {
                    // Fail early if the selected audio codec cannot be decoded by iOS.
                    let audio = try AVAudioFile(forReading: local)
                    guard audio.length > 0 else { throw TTSError.invalidVoice("Tệp không chứa âm thanh") }
                } catch {
                    try? fm.removeItem(at: local)
                    throw error
                }
                target = local
            } catch { copyError = error }
        }
        if let error = copyError { throw error }
        if let error = coordinatedError { throw error }
        guard let target else { throw TTSError.invalidVoice("Không thể đọc tệp từ ứng dụng Tệp") }
        return target
    }
}
'''

speech = replace_once(speech, '''    private var recordingFolder: URL {
        documents.appendingPathComponent("SampleRecordings", isDirectory: true)
    }''', '''    private var recordingFolder: URL {
        documents.appendingPathComponent("SampleRecordings", isDirectory: true)
    }
    private var importedVoiceFolder: URL {
        documents.appendingPathComponent("ImportedVoiceSamples", isDirectory: true)
    }''', 'imported storage')
speech = replace_once(speech, 'temporaryBytes = Self.folderBytes(previewFolder) + Self.folderBytes(recordingFolder)',
                      'temporaryBytes = Self.folderBytes(previewFolder) + Self.folderBytes(recordingFolder) + Self.folderBytes(importedVoiceFolder)', 'cache size')
speech = replace_once(speech, 'for folder in [previewFolder, recordingFolder] {',
                      'for folder in [previewFolder, recordingFolder, importedVoiceFolder] {', 'cleanup imported reference temp')

old_plist = plist.read_text()
assert '<string>1.1.0</string>' in old_plist or '<string>1.0.0</string>' in old_plist, 'Expected v1 or v1.1 source plist'
ps = old_plist.replace('<string>1.1.0</string>', '<string>1.2.0</string>').replace('<string>1.0.0</string>', '<string>1.2.0</string>').replace('<string>3</string>', '<string>4</string>').replace('<string>2</string>', '<string>4</string>')

swift.write_text(ui)
studio.write_text(speech)
plist.write_text(ps)
print('Voice Hn Studio v1.2 audio importer patch applied successfully')