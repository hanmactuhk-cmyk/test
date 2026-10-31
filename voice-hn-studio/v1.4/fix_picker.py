#!/usr/bin/env python3
"""Voice Hn Studio 1.4: select MP3/WAV/M4A from iOS Files/iCloud using asCopy."""
from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("ios")
ui_file=root/"HNVieNeuIOS/Sources/HNVieNeuApp.swift"
speech_file=root/"HNVieNeuIOS/Sources/SpeechStudio.swift"
plist=root/"HNVieNeuIOS/Support/Info.plist"
ui=ui_file.read_text()
speech=speech_file.read_text()
p=plist.read_text()

def swap(s,a,b,label):
    n=s.count(a)
    if n!=1: raise RuntimeError(f"{label}: expected one anchor, found {n}")
    return s.replace(a,b,1)

old='''        .fileImporter(isPresented: $showingImportAudio, allowedContentTypes: [.audio, UTType(filenameExtension: "mp3") ?? .audio, UTType(filenameExtension: "wav") ?? .audio, UTType(filenameExtension: "m4a") ?? .audio]) { result in
            switch result { case .success(let url): clone.importAudio(url); case .failure(let error): clone.errorText = error.localizedDescription }
        }'''
new='''        .sheet(isPresented: $showingImportAudio) {
            VoiceAudioDocumentPicker(isPresented: $showingImportAudio) { selectedURL in
                clone.importAudio(selectedURL)
            }
        }'''
ui=swap(ui,old,new,"document picker")
assert "enum ImportedVoiceAudio {" in ui
ui=ui[:ui.index("enum ImportedVoiceAudio {")]+r'''
enum ImportedVoiceAudio {
    static func copyIntoSandbox(_ source: URL) throws -> URL {
        let fm = FileManager.default
        let ext = source.pathExtension.lowercased()
        guard ["mp3", "wav", "m4a", "aac", "aif", "aiff", "caf"].contains(ext) else {
            throw TTSError.invalidVoice("Hỗ trợ MP3, WAV, M4A, AAC, AIFF, CAF. Tệp này có đuôi: \(ext.isEmpty ? "không rõ" : ext)")
        }
        let folder = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ImportedVoiceSamples", isDirectory: true)
        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        let access = source.startAccessingSecurityScopedResource()
        defer { if access { source.stopAccessingSecurityScopedResource() } }
        let target = folder.appendingPathComponent("voice-\(UUID().uuidString).\(ext)")
        do {
            do {
                try fm.copyItem(at: source, to: target)
            } catch {
                var coordinatedError: NSError?
                var innerError: Error?
                NSFileCoordinator(filePresenter: nil).coordinate(readingItemAt: source, options: [], error: &coordinatedError) { readable in
                    do { try fm.copyItem(at: readable, to: target) }
                    catch { innerError = error }
                }
                if let innerError { throw innerError }
                if let coordinatedError { throw coordinatedError }
            }
            let attrs = try fm.attributesOfItem(atPath: target.path)
            let size = (attrs[.size] as? NSNumber)?.int64Value ?? 0
            guard size > 0 else { throw TTSError.invalidVoice("Tệp rỗng hoặc chưa tải từ iCloud về máy.") }
            guard size <= 80 * 1_024 * 1_024 else { throw TTSError.invalidVoice("Tệp vượt 80 MB. Hãy chọn đoạn ghi âm 5–15 giây.") }
            // Validate audio on clone, not at pick time: some valid MP3s fail the
            // AVAudioFile preflight and were rejected before showing 'Đã chọn'.
            return target
        } catch {
            try? fm.removeItem(at: target)
            throw error
        }
    }
}

/// Let the user pick any file – some audio files are reported as generic data.
/// asCopy imports cloud/third-party files into our app before processing.
private struct VoiceAudioDocumentPicker: UIViewControllerRepresentable {
    @Binding var isPresented: Bool
    let onPick: (URL) -> Void

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
        picker.allowsMultipleSelection = false
        picker.delegate = context.coordinator
        return picker
    }
    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        let parent: VoiceAudioDocumentPicker
        init(parent: VoiceAudioDocumentPicker) { self.parent = parent }
        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            if let url = urls.first { parent.onPick(url) }
            parent.isPresented = false
        }
        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            parent.isPresented = false
        }
    }
}
'''
assert "ImportedVoiceAudio.copyIntoSandbox(url)" in speech
assert "clone.importing" in ui
assert "Đang tải và kiểm tra tệp âm thanh" in ui
assert "Rất vui được chào đón" in speech
ui=swap(ui,"Voice Hn Studio · Phiên bản 1.3","Voice Hn Studio · Phiên bản 1.4","UI version")
p=swap(p,"<string>1.3.0</string>","<string>1.4.0</string>","CFBundleShortVersionString")
p=swap(p,"<string>5</string>","<string>6</string>","CFBundleVersion")
ui_file.write_text(ui)
plist.write_text(p)
print("PASS: iOS document picker asCopy, MP3/WAV/M4A import, friendly errors, Voice Hn Studio v1.4")
