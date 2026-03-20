import AppKit
import Foundation
import Vision

enum OCRError: Error, CustomStringConvertible {
    case usage
    case inputMissing(String)
    case imageLoadFailed(String)
    case cgImageMissing(String)
    case requestFailed(String)
    case jsonEncodingFailed
    case writeFailed(String)

    var description: String {
        switch self {
        case .usage:
            return "Usage: ocr_image.swift <input_image> <output_json>"
        case .inputMissing(let path):
            return "Input image not found: \(path)"
        case .imageLoadFailed(let path):
            return "Failed to load image: \(path)"
        case .cgImageMissing(let path):
            return "Failed to create CGImage from: \(path)"
        case .requestFailed(let message):
            return "OCR request failed: \(message)"
        case .jsonEncodingFailed:
            return "Failed to encode OCR JSON"
        case .writeFailed(let path):
            return "Failed to write OCR JSON: \(path)"
        }
    }
}

struct BoundingBox: Codable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct OCRLine: Codable {
    let text: String
    let confidence: Double
    let boundingBox: BoundingBox

    enum CodingKeys: String, CodingKey {
        case text
        case confidence
        case boundingBox = "bounding_box"
    }
}

struct OCRResult: Codable {
    let text: String
    let lines: [OCRLine]
}

func writeStderr(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func parseArguments() throws -> (inputURL: URL, outputURL: URL) {
    let args = CommandLine.arguments
    guard args.count == 3 else {
        throw OCRError.usage
    }

    let inputURL = URL(fileURLWithPath: args[1])
    let outputURL = URL(fileURLWithPath: args[2])

    guard FileManager.default.fileExists(atPath: inputURL.path) else {
        throw OCRError.inputMissing(inputURL.path)
    }

    return (inputURL, outputURL)
}

func loadCGImage(from url: URL) throws -> CGImage {
    guard let image = NSImage(contentsOf: url) else {
        throw OCRError.imageLoadFailed(url.path)
    }

    var proposedRect = CGRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(forProposedRect: &proposedRect, context: nil, hints: nil) else {
        throw OCRError.cgImageMissing(url.path)
    }

    return cgImage
}

func recognizeText(in cgImage: CGImage) throws -> OCRResult {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["ja-JP", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        throw OCRError.requestFailed(error.localizedDescription)
    }

    let observations = request.results ?? []
    let lines = observations.compactMap { observation -> OCRLine? in
        guard let candidate = observation.topCandidates(1).first else {
            return nil
        }

        let box = observation.boundingBox
        return OCRLine(
            text: candidate.string,
            confidence: Double(candidate.confidence),
            boundingBox: BoundingBox(
                x: Double(box.origin.x),
                y: Double(box.origin.y),
                width: Double(box.size.width),
                height: Double(box.size.height)
            )
        )
    }

    let sortedLines = lines.sorted { lhs, rhs in
        if abs(lhs.boundingBox.y - rhs.boundingBox.y) > 0.01 {
            return lhs.boundingBox.y > rhs.boundingBox.y
        }
        return lhs.boundingBox.x < rhs.boundingBox.x
    }

    let joinedText = sortedLines.map(\.text).joined(separator: "\n")
    return OCRResult(text: joinedText, lines: sortedLines)
}

func writeJSON(_ result: OCRResult, to url: URL) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]

    guard let data = try? encoder.encode(result) else {
        throw OCRError.jsonEncodingFailed
    }

    let directoryURL = url.deletingLastPathComponent()
    try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)

    do {
        try data.write(to: url, options: .atomic)
    } catch {
        throw OCRError.writeFailed(url.path)
    }
}

func main() throws {
    let (inputURL, outputURL) = try parseArguments()
    let cgImage = try loadCGImage(from: inputURL)
    let result = try recognizeText(in: cgImage)
    try writeJSON(result, to: outputURL)
    print(result.text.count)
}

do {
    try main()
} catch let error as OCRError {
    writeStderr(error.description)
    exit(1)
} catch {
    writeStderr(String(describing: error))
    exit(1)
}
