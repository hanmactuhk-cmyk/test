#!/usr/bin/env python3
"""Keep ONNX boolean masks valid on onnxruntime-objc, which exposes no BOOL tensor type.

Rewrites *external* ctx_mask tensors as uint8 and immediately Casts to the
original BOOL tensor internally. Semantic output is unchanged.
"""
from pathlib import Path
import onnx
from onnx import TensorProto, helper

src = Path(__file__).resolve().parent.parent / "ios"
swift = src / "HNVieNeuIOS/Sources/OrtTensor.swift"
txt = swift.read_text()
before = "data = Data(x); dtype = .bool"
assert before in txt, "Unexpected Swift ORTValue bool constructor"
swift.write_text(txt.replace(before, "data = Data(x); dtype = .uInt8"))

for model_name in ("duration_predictor", "vector_estimator"):
    path = src / "Models" / (model_name + ".onnx")
    model = onnx.load(str(path))
    graph = model.graph
    inputs = [v for v in graph.input if v.name == "ctx_mask"]
    if len(inputs) != 1:
        raise ValueError(f"{model_name}: ctx_mask input not found: {[v.name for v in graph.input]}")
    mask = inputs[0]
    if mask.type.tensor_type.elem_type != TensorProto.BOOL:
        raise ValueError(f"{model_name}: ctx_mask expected BOOL, got {mask.type.tensor_type.elem_type}")
    name = "ctx_mask__bool_internal"
    if any(name == x for n in graph.node for x in n.output):
        raise ValueError("Mask cast name already used")
    count = 0
    for node in graph.node:
        for i, old in enumerate(node.input):
            if old == "ctx_mask":
                node.input[i] = name
                count += 1
    assert count > 0, f"{model_name}: ctx_mask has no consumers"
    mask.type.tensor_type.elem_type = TensorProto.UINT8
    graph.node.insert(0, helper.make_node("Cast", inputs=["ctx_mask"],
                                          outputs=[name], to=TensorProto.BOOL,
                                          name="HN_MaskU8ToBool"))
    onnx.save(model, str(path))
    onnx.checker.check_model(str(path))
    print(f"Patched {model_name}.onnx bool mask for iOS ({count} consumers)")
print("Fixed Swift ORT tensor type and converted ONNX graph inputs")
