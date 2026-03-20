import AppKit
import Foundation
import PDFKit

enum RenderError: Error, CustomStringConvertible {
    case usage
    case invalidDPI(String)
    case inputMissing(String)
    case openFailed(String)
    case pageMissing(Int)
    case bitmapFailed(Int)
    case graphicsContextFailed(Int)
    case pngEncodingFailed(Int)
    case createDirectoryFailed(String)
    case writeFailed(String)

    var description: String {
        switch self {
        case .usage:
            return "Usage: render_pdf.swift <input_pdf> <output_dir> <dpi>"
        case .invalidDPI(let value):
            return "Invalid DPI: \(value)"
        case .inputMissing(let path):
            return "Input PDF not found: \(path)"
        case .openFailed(let path):
            return "Failed to open PDF: \(path)"
        case .pageMissing(let index):
            return "Failed to load page \(index + 1)"
        case .bitmapFailed(let index):
            return "Failed to allocate bitmap for page \(index + 1)"
        case .graphicsContextFailed(let index):
            return "Failed to create graphics context for page \(index + 1)"
        case .pngEncodingFailed(let index):
            return "Failed to encode PNG for page \(index + 1)"
        case .createDirectoryFailed(let path):
            return "Failed to create output directory: \(path)"
        case .writeFailed(let path):
            return "Failed to write PNG: \(path)"
        }
    }
}

func writeStderr(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func parseArguments() throws -> (inputURL: URL, outputURL: URL, dpi: Int) {
    let args = CommandLine.arguments
    guard args.count == 4 else {
        throw RenderError.usage
    }

    let inputURL = URL(fileURLWithPath: args[1])
    let outputURL = URL(fileURLWithPath: args[2], isDirectory: true)
    guard let dpi = Int(args[3]), dpi > 0 else {
        throw RenderError.invalidDPI(args[3])
    }

    guard FileManager.default.fileExists(atPath: inputURL.path) else {
        throw RenderError.inputMissing(inputURL.path)
    }

    return (inputURL, outputURL, dpi)
}

func ensureDirectory(_ url: URL) throws {
    do {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    } catch {
        throw RenderError.createDirectoryFailed(url.path)
    }
}

func renderPage(_ page: PDFPage, pageIndex: Int, dpi: Int, outputURL: URL) throws {
    let bounds = page.bounds(for: .mediaBox)
    let scale = CGFloat(dpi) / 72.0
    let pixelWidth = max(Int(ceil(bounds.width * scale)), 1)
    let pixelHeight = max(Int(ceil(bounds.height * scale)), 1)

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: pixelWidth,
        pixelsHigh: pixelHeight,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        throw RenderError.bitmapFailed(pageIndex)
    }

    bitmap.size = NSSize(width: bounds.width, height: bounds.height)

    guard let graphicsContext = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw RenderError.graphicsContextFailed(pageIndex)
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = graphicsContext

    let context = graphicsContext.cgContext
    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: pixelWidth, height: pixelHeight))
    context.interpolationQuality = .high
    context.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: context)

    NSGraphicsContext.restoreGraphicsState()

    guard let data = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncodingFailed(pageIndex)
    }

    do {
        try data.write(to: outputURL, options: .atomic)
    } catch {
        throw RenderError.writeFailed(outputURL.path)
    }
}

func main() throws {
    let (inputURL, outputURL, dpi) = try parseArguments()
    try ensureDirectory(outputURL)

    guard let document = PDFDocument(url: inputURL) else {
        throw RenderError.openFailed(inputURL.path)
    }

    let pageCount = document.pageCount
    for pageIndex in 0..<pageCount {
        try autoreleasepool {
            guard let page = document.page(at: pageIndex) else {
                throw RenderError.pageMissing(pageIndex)
            }
            let filename = String(format: "page-%04d.png", pageIndex + 1)
            let destination = outputURL.appendingPathComponent(filename)
            try renderPage(page, pageIndex: pageIndex, dpi: dpi, outputURL: destination)
        }
    }

    print(pageCount)
}

do {
    try main()
} catch let error as RenderError {
    writeStderr(error.description)
    exit(1)
} catch {
    writeStderr(String(describing: error))
    exit(1)
}
