// Optional macOS Vision OCR for scanned public originals. No source is modified.
import Foundation
import Vision
import AppKit

for argument in CommandLine.arguments.dropFirst() {
    autoreleasepool {
        do {
            let url = URL(fileURLWithPath: argument)
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["zh-Hans", "en-US"]
            request.usesLanguageCorrection = false
            let handler = VNImageRequestHandler(url: url, options: [:])
            try handler.perform([request])
            let lines: [[String: Any]] = (request.results ?? []).compactMap { observation in
                guard let candidate = observation.topCandidates(1).first else { return nil }
                let box = observation.boundingBox
                return ["text": candidate.string, "confidence": candidate.confidence,
                        "bbox": [box.origin.x, box.origin.y, box.size.width, box.size.height]]
            }
            let result: [String: Any] = ["image": url.lastPathComponent, "lines": lines]
            let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
            print(String(data: data, encoding: .utf8)!)
        } catch {
            let result: [String: Any] = ["image": argument, "error": String(describing: error)]
            let data = try! JSONSerialization.data(withJSONObject: result)
            print(String(data: data, encoding: .utf8)!)
        }
    }
}
