#!/usr/bin/env python3
"""Fetch genuine Turbo INT8 ONNX and MOSS codec for offline ARM64 iPhone release."""
from pathlib import Path
import json,shutil,urllib.request
from huggingface_hub import hf_hub_download
base=Path("ios/TurboModels")
model=base/"onnx";codec=base/"codec"
model.mkdir(parents=True,exist_ok=True)
codec.mkdir(parents=True,exist_ok=True)
model_files=["config.json","tokenizer.json","vieneu_prefill.onnx",
    "vieneu_decode_step.onnx","vieneu_acoustic_cached.onnx",
    "vieneu_backbone_shared.data","vieneu_v3_heads.npz"]
codec_files=["moss_audio_tokenizer_decode_full.onnx",
    "moss_audio_tokenizer_decode_shared.data",
    "moss_audio_tokenizer_encode.onnx","moss_audio_tokenizer_encode.data"]
for name in model_files:
    source=hf_hub_download("pnnbao-ump/VieNeu-TTS-v3-Turbo",filename="onnx_int8/"+name)
    target=model/name;shutil.copyfile(source,target)
    print("TURBO_INT8_MODEL",name,target.stat().st_size,flush=True)
for name in codec_files:
    source=hf_hub_download("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX",filename=name)
    target=codec/name;shutil.copyfile(source,target)
    print("TURBO_MOSS_CODEC",name,target.stat().st_size,flush=True)
with urllib.request.urlopen("https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/main/src/vieneu/assets/voices_v3_turbo.json",timeout=55) as response:
    data=response.read()
voices=json.loads(data)
assert isinstance(voices.get("presets"),dict) and voices["presets"]
(base/"voices_v3_turbo.json").write_bytes(data)
print("TURBO_VOICES",len(voices["presets"]),flush=True)
for k in model_files: assert (model/k).stat().st_size>500
for k in codec_files: assert (codec/k).stat().st_size>500
# No Nano graphs in the Turbo IPA.
for existing in Path("ios/Models").glob("*"):
    if existing.is_file(): existing.unlink()
print("TURBO_ONLY_MODEL_ASSETS_READY",flush=True)
