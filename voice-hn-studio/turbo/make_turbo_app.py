#!/usr/bin/env python3
"""Replace all Nano execution paths in Voice Hn Studio with real V3 Turbo ONNX.
Called AFTER the v1.4 UI fixes. Never bundle Nano graphs as a disguised Turbo.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else "ios")
swift=root/"HNVieNeuIOS/Sources"
speech=swift/"SpeechStudio.swift"
app=swift/"HNVieNeuApp.swift"
audio=swift/"AudioUtils.swift"
bridge=root/"HNVieNeuIOS/Support/HNVieNeu-Bridging-Header.h"
project=root/"project.yml"
doc=speech.read_text(encoding="utf8")

def replace_once(src, old, new, what):
    count=src.count(old)
    if count!=1: raise RuntimeError(f"{what}: expected one match, got {count}")
    return src.replace(old,new,1)

first=doc.index('        if let path = try? Assets.dataURL("voices_v3_nano.json"),')
last=doc.index("        let personal = CloneVoiceStore.all().map {",first)
doc=doc[:first]+'''        let preset = TurboVoiceEngine.availableVoices()
        let shades: [Color] = [.cyan, .pink, .orange, .mint, .purple, .blue]
        choices = preset.enumerated().map { idx, entry in
            VoiceChoice(id: entry.id, title: entry.id, detail: entry.detail,
                        symbol: "waveform", tint: shades[idx % shades.count], isPersonal: false)
        }
        if selectedVoice.isEmpty { selectedVoice = TurboVoiceEngine.defaultVoice() }
'''+doc[last:]
doc=replace_once(doc,"let personal = CloneVoiceStore.all().map {",
                     "let personal = CloneVoiceStore.all().filter { TurboVoiceStore.referenceURL(id: $0.id) != nil }.map {","use only Turbo clones")
doc=doc.replace("guard Assets.ready else {","guard TurboVoiceEngine.ready else {")
doc=replace_once(doc,"let engine = try NanoEngine()\n                let samples = try engine.synthesize(copy, settings: args) { done, total in\n                    Task { @MainActor in self.progress = \"Đã tạo \\(done)/\\(total) đoạn\" }\n                }",
                "let samples = try TurboVoiceEngine.synthesize(copy, voiceID: chosen)","Turbo creation")
doc=replace_once(doc,"let engine = try NanoEngine()\n                let options = TTSSettings(voice: voiceID, steps: 8, cfg: 3,\n                                          sway: -1, speed: 1, seed: 20261031)\n                let samples = try engine.synthesize(script, settings: options)",
                "let samples = try TurboVoiceEngine.synthesize(script, voiceID: voiceID)","Turbo per-voice preview")
doc=replace_once(doc,"Int(Double(sampleCount) / 24_000)","Int(Double(sampleCount) / 48_000)","48k output duration")
doc=replace_once(doc,"preview-v3|","preview-v4-turbo|","preview cache invalidation")
doc=replace_once(doc,"    func reload() { saved = CloneVoiceStore.all() }",
                "    func reload() { saved = CloneVoiceStore.all().filter { TurboVoiceStore.referenceURL(id: $0.id) != nil } }","Turbo clone list")
doc=replace_once(doc,"guard Assets.cloneReady else","guard TurboVoiceEngine.ready else","Turbo clone readiness")
doc=replace_once(doc,
'''                let encoder = try CloneEngine()
                let profile = try encoder.enroll(referenceURL: url, name: label, description: desc) { message in
                    Task { @MainActor in self.status = message }
                }''',
'''                let profile = try TurboVoiceStore.save(reference: url, name: label, description: desc)''',"save reference WAV for Turbo zero-shot cloning")
doc=replace_once(doc,"try CloneVoiceStore.delete(id); reload()","try TurboVoiceStore.delete(id: id); reload()","delete Turbo voice with WAV")
speech.write_text(doc,encoding="utf8")

a=audio.read_text()
a=replace_once(a,"static let sampleRate = 24_000","static let sampleRate = 48_000","48k WAV writer")
audio.write_text(a)
ap=app.read_text()
ap=replace_once(ap,"Voice Hn Studio · Phiên bản 1.4","Voice Hn Studio · Phiên bản 1.5","app version")
app.write_text(ap)

b=bridge.read_text()
b += '\n#import "TurboBridge.h"\n'
bridge.write_text(b)

pr=project.read_text()
pr=replace_once(pr,'OTHER_LDFLAGS: "$(inherited) -lc++ -lresolv"',
    'OTHER_LDFLAGS: "$(inherited) -lc++ -lresolv -all_load -framework Accelerate -lhn-turbo -lvieneu-tts-core -lllama -lggml -lggml-base -lggml-cpu -lggml-blas"', "Turbo C++ link flags")
pr=replace_once(pr,'HEADER_SEARCH_PATHS: "$(inherited) $(PROJECT_DIR)/Native/include"',
    'HEADER_SEARCH_PATHS: "$(inherited) $(PROJECT_DIR)/Native/include"\n    LIBRARY_SEARCH_PATHS: "$(inherited) $(PROJECT_DIR)/Native/lib"',"Turbo iOS C++ library path")
pr=replace_once(pr,'''      - path: Data
        type: folder
        buildPhase: resources''', '''      - path: Data
        type: folder
        buildPhase: resources
      - path: TurboModels
        type: folder
        buildPhase: resources''',"Turbo ONNX bundled assets")
project.write_text(pr)

plist=root/"HNVieNeuIOS/Support/Info.plist"
p=plist.read_text()
p=replace_once(p,"<string>1.4.0</string>","<string>1.5.0</string>","CFBundleShortVersionString")
p=replace_once(p,"<string>6</string>","<string>7</string>","CFBundleVersion")
plist.write_text(p)

header=root/"Native/include/TurboBridge.h"
header.parent.mkdir(parents=True,exist_ok=True)
header.write_text(r'''#ifndef HN_TURBO_BRIDGE_H
#define HN_TURBO_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Returns null on success; otherwise an error C string valid until next call.
const char* HNTurboSynthesize(const char* modelDir, const char* codecDir,
    const char* voicesPath, const char* text, const char* preset,
    const char* referenceWav, float** output, int32_t* count);
void HNTurboRelease(float* samples);
#ifdef __cplusplus
}
#endif
#endif
''')

bridgecpp=root/"TurboBridge.cpp"
bridgecpp.write_text(r'''#include "TurboBridge.h"
#include "vieneu_tts.h"
#include <cstdlib>
#include <cstring>
#include <exception>
#include <string>
#include <mutex>
namespace { std::mutex lock; thread_local std::string lastError; }
extern "C" const char* HNTurboSynthesize(
    const char* modelDir, const char* codecDir, const char* voicesPath,
    const char* text, const char* preset, const char* referenceWav,
    float** output, int32_t* count) {
    std::lock_guard<std::mutex> guard(lock);
    *output = nullptr; *count = 0;
    try {
        struct vieneu_init_params_v2 init{};
        vieneu_init_v2_default_params(&init);
        init.profile = "vieneu-v3-onnx";
        init.model_dir = modelDir;
        init.onnx_dir = modelDir;
        init.codec_dir = codecDir;
        init.voices_json_path = voicesPath;
        init.n_threads = 4;
        struct vieneu_context* ctx = vieneu_init_v2(&init);
        if (!ctx) {
            lastError = vieneu_last_error();
            return lastError.c_str();
        }
        struct vieneu_tts_params_v3 tts{};
        vieneu_tts_v3_default_params(&tts);
        tts.text = text;
        tts.voice_id = (preset && preset[0]) ? preset : nullptr;
        tts.ref_audio_path = (referenceWav && referenceWav[0]) ? referenceWav : nullptr;
        tts.max_new_frames = 300;
        tts.max_chars = 250;
        tts.apply_watermark = false;
        struct vieneu_audio result{};
        const int rc=vieneu_synthesize_v3(ctx,&tts,&result);
        if (rc!=0 || !result.samples || result.n_samples<=0) {
            lastError=vieneu_last_error();
            vieneu_audio_free(&result);
            vieneu_free(ctx);
            return lastError.c_str();
        }
        *output=result.samples;
        *count=result.n_samples;
        result.samples=nullptr;
        vieneu_free(ctx);
        return nullptr;
    } catch(const std::exception& e) {
        lastError=e.what();
        return lastError.c_str();
    } catch(...) {
        lastError="Lỗi Turbo không xác định";
        return lastError.c_str();
    }
}
extern "C" void HNTurboRelease(float* samples) { free(samples); }
''')

turbo=swift/"TurboVoiceEngine.swift"
turbo.write_text(r'''import AVFoundation
import Foundation

/// Real VieNeu v3 Turbo INT8, ONNX CPU inference (48 kHz). No Nano fallback.
enum TurboVoiceEngine {
    static var modelDir: URL? { Bundle.main.url(forResource: "TurboModels", withExtension: nil)?.appendingPathComponent("onnx") }
    static var codecDir: URL? { Bundle.main.url(forResource: "TurboModels", withExtension: nil)?.appendingPathComponent("codec") }
    static var voicesURL: URL? { Bundle.main.url(forResource: "TurboModels", withExtension: nil)?.appendingPathComponent("voices_v3_turbo.json") }
    static var ready: Bool {
        guard let m=modelDir, let c=codecDir, let v=voicesURL else { return false }
        let fm=FileManager.default
        let required=[m.appendingPathComponent("vieneu_prefill.onnx"),
                      m.appendingPathComponent("vieneu_decode_step.onnx"),
                      m.appendingPathComponent("vieneu_acoustic_cached.onnx"),
                      m.appendingPathComponent("vieneu_backbone_shared.data"),
                      m.appendingPathComponent("vieneu_v3_heads.npz"),
                      c.appendingPathComponent("moss_audio_tokenizer_decode_full.onnx"),
                      c.appendingPathComponent("moss_audio_tokenizer_decode_shared.data"),
                      c.appendingPathComponent("moss_audio_tokenizer_encode.onnx"),
                      c.appendingPathComponent("moss_audio_tokenizer_encode.data"),v]
        return required.allSatisfy { fm.fileExists(atPath: $0.path) }
    }
    static func voicesJSON() -> [String: Any] {
        guard let v=voicesURL, let d=try? Data(contentsOf:v),
              let json=try? JSONSerialization.jsonObject(with:d) as? [String:Any] else { return [:] }
        return json
    }
    static func availableVoices() -> [(id:String,detail:String)] {
        let v=voicesJSON()
        guard let p=v["presets"] as? [String:[String:Any]] else { return [] }
        return p.keys.sorted().map { key in
            let detail=(p[key]?["description"] as? String) ?? "Giọng đọc tự nhiên"
            return (id:key,detail:detail)
        }
    }
    static func defaultVoice() -> String {
        (voicesJSON()["default_voice"] as? String) ?? availableVoices().first?.id ?? ""
    }
    static func synthesize(_ text:String, voiceID:String) throws -> [Float] {
        guard ready, let model=modelDir?.path, let codec=codecDir?.path, let presets=voicesURL?.path else {
            throw TTSError.missingAssets("TurboModels – hãy cài lại bản Turbo đầy đủ")
        }
        let ref=TurboVoiceStore.referenceURL(id: voiceID)?.path ?? ""
        if voiceID.hasPrefix("mine-") && ref.isEmpty { throw TTSError.invalidVoice("Giọng clone này không có tệp tham chiếu Turbo, vui lòng clone lại.") }
        let preset=ref.isEmpty ? voiceID : ""
        var values: UnsafeMutablePointer<Float>?
        var count: Int32=0
        var message: String?
        model.withCString { m in codec.withCString { c in presets.withCString { v in
            text.withCString { t in preset.withCString { p in ref.withCString { f in
                if let error=HNTurboSynthesize(m,c,v,t,p,f,&values,&count) { message=String(cString:error) }
            } } }
        } } }
        if let message { throw TTSError.inferenceFailure(message) }
        guard let ptr=values, count>0 else { throw TTSError.noGeneratedAudio }
        defer { HNTurboRelease(ptr) }
        return Array(UnsafeBufferPointer(start:ptr,count:Int(count)))
    }
}

/// Keep the real reference WAV (not Nano embeddings), one per voice.
enum TurboVoiceStore {
    private static var root: URL {
        FileManager.default.urls(for:.documentDirectory,in:.userDomainMask)[0]
            .appendingPathComponent("MyVoices",isDirectory:true)
    }
    static func referenceURL(id:String) -> URL? {
        guard id.hasPrefix("mine-"), !id.contains("/"), !id.contains("..") else { return nil }
        let url=root.appendingPathComponent(id).appendingPathExtension("wav")
        return FileManager.default.fileExists(atPath:url.path) ? url : nil
    }
    static func save(reference: URL,name:String,description:String) throws -> SavedVoice {
        let clean=name.trimmingCharacters(in:.whitespacesAndNewlines)
        guard !clean.isEmpty else { throw TTSError.invalidVoice("Hãy đặt tên cho giọng") }
        let source=try SampleAudio.load(url:reference,maxSeconds:30)
        guard source.duration >= 1.0 else { throw TTSError.invalidVoice("Mẫu giọng quá ngắn. Nên dùng 5–15 giây.") }
        let wav=SampleAudio.resample(source.samples,from:source.sampleRate,to:48_000)
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let result=SavedVoice(id:"mine-"+UUID().uuidString.lowercased(),
                             name:clean,description:description,createdAt:Date(),speaker_emb:[],style:[])
        let refURL=root.appendingPathComponent(result.id).appendingPathExtension("wav")
        try WAVWriter.save(wav,to:refURL)
        do {
            let encoded=try JSONEncoder().encode(result)
            try encoded.write(to:root.appendingPathComponent(result.id).appendingPathExtension("json"),options:.atomic)
            return result
        } catch {
            try? FileManager.default.removeItem(at:refURL)
            throw error
        }
    }
    static func delete(id:String) throws {
        guard id.hasPrefix("mine-"), !id.contains("/"), !id.contains("..") else { return }
        try? FileManager.default.removeItem(at:root.appendingPathComponent(id).appendingPathExtension("wav"))
        try CloneVoiceStore.delete(id)
    }
}
''')
assert "NanoEngine()" not in doc
assert "CloneEngine()" not in doc
assert "TurboVoiceEngine.synthesize" in doc
assert "TurboModels" in pr
print("TURBO_APP_PATCH_OK; Swift is now wired to true V3 Turbo ONNX, all original Nano execution paths replaced")
